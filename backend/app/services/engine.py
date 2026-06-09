# -*- coding: utf-8 -*-
"""
Intelligence engine — orchestrates the full refresh pipeline.

  fetch (Open-Meteo) -> classify event -> score risk -> AI explanation
  -> derive alerts -> national report -> persist -> update live state -> broadcast

Also seeds the reference geography (regions/provinces/cities) on first run.
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta

from sqlalchemy import select

from ..data import ph_locations as geo
from ..database import SessionLocal
from .. import models
from . import ai_explainer, analytics, classifier, risk, weather_client
from .state import manager, now_iso, state

log = logging.getLogger("pwin.engine")

SEV_EXPIRY_HOURS = {"info": 3, "advisory": 4, "watch": 6, "warning": 8, "critical": 12}

ALERT_CATEGORY = {
    "thunderstorm": "Thunderstorm Warning",
    "heavy_rain": "Heavy Rainfall Warning",
    "moderate_rain": "Rainfall Advisory",
    "light_rain": "Rainfall Advisory",
    "strong_winds": "Strong Wind Warning",
    "windy": "Wind Advisory",
    "heat": "Heat Advisory",
}
HAZARD_ALERT = {
    "flood": ("Flood Risk", "Flooding possible in low-lying and poorly drained areas."),
    "landslide": ("Landslide Risk", "Saturated slopes may give way in hilly terrain."),
    "coastal": ("Coastal Hazard", "Rough seas and big waves expected along the coast."),
}


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------
def seed_reference_data() -> None:
    """Populate regions/provinces/cities if empty (idempotent)."""
    db = SessionLocal()
    try:
        if db.scalar(select(models.Region).limit(1)):
            return
        log.info("Seeding reference geography…")
        region_ids: dict[str, int] = {}
        for r in geo.REGIONS:
            row = models.Region(code=r["code"], name=r["name"], lat=r["lat"], lon=r["lon"])
            db.add(row)
            db.flush()
            region_ids[r["code"]] = row.id

        prov_ids: dict[str, int] = {}
        for p in geo.PROVINCES:
            row = models.Province(
                name=p["name"], region_id=region_ids[p["region"]],
                capital=p.get("capital", ""), lat=p["lat"], lon=p["lon"],
            )
            db.add(row)
            db.flush()
            prov_ids[p["name"]] = row.id

        for c in geo.CITIES:
            pid = prov_ids.get(c["province"])
            if pid:
                db.add(models.City(name=c["name"], province_id=pid,
                                   lat=c["lat"], lon=c["lon"]))
        db.commit()
        log.info("Seed complete: %d regions, %d provinces, %d cities.",
                 len(geo.REGIONS), len(geo.PROVINCES), len(geo.CITIES))
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        log.warning("Seeding failed (continuing without DB): %s", exc)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Snapshot building
# ---------------------------------------------------------------------------
def _build_condition(current: dict, event: dict) -> dict:
    return {
        "temperature_c": current.get("temperature_c"),
        "feels_like_c": current.get("feels_like_c"),
        "humidity_pct": current.get("humidity_pct"),
        "wind_speed_kmh": current.get("wind_speed_kmh"),
        "wind_dir_deg": current.get("wind_dir_deg"),
        "wind_dir_label": current.get("wind_dir_label"),
        "wind_gust_kmh": current.get("wind_gust_kmh"),
        "pressure_hpa": current.get("pressure_hpa"),
        "visibility_km": current.get("visibility_km"),
        "uv_index": current.get("uv_index"),
        "cloud_cover_pct": current.get("cloud_cover_pct"),
        "precip_mm": current.get("precip_mm"),
        "precip_prob_pct": current.get("precip_prob_pct"),
        "condition_code": current.get("condition_code"),
        "condition_text": current.get("condition_text"),
        "icon": current.get("icon"),
        "is_raining": current.get("is_raining", False),
        "rain_intensity": event.get("rain_intensity", "none"),
    }


def _province_alerts(prov: dict, event: dict, rsk: dict) -> list[dict]:
    alerts: list[dict] = []
    sev = event["severity"]
    issued = now_iso()
    expires = (datetime.now() + timedelta(hours=SEV_EXPIRY_HOURS.get(sev, 4))).isoformat(timespec="seconds")
    areas = [prov["name"]] + ([prov["capital"]] if prov.get("capital") else [])

    if sev in ("watch", "warning", "critical") and event["event_type"] in ALERT_CATEGORY:
        first_prec = ai_explainer._precautions(event, rsk)
        alerts.append({
            "title": f"{ALERT_CATEGORY[event['event_type']]} — {prov['name']}",
            "category": ALERT_CATEGORY[event["event_type"]],
            "severity": sev,
            "province": prov["name"],
            "region": prov["region"],
            "areas": areas,
            "reason": event["cause"],
            "recommended_action": first_prec[0] if first_prec else "Monitor official advisories.",
            "issued_at": issued,
            "expires_at": event.get("expected_end") or expires,
            "source": "PWIN AI",
        })

    for hz, hzlevel in rsk.get("hazards", {}).items():
        if hz in HAZARD_ALERT and hzlevel in ("moderate", "high"):
            title, reason = HAZARD_ALERT[hz]
            alerts.append({
                "title": f"{title} — {prov['name']}",
                "category": title,
                "severity": "warning" if hzlevel == "high" else "watch",
                "province": prov["name"],
                "region": prov["region"],
                "areas": areas,
                "reason": reason + f" Driver: {event['cause']}.",
                "recommended_action": "Follow local disaster office guidance.",
                "issued_at": issued,
                "expires_at": expires,
                "source": "PWIN AI",
            })
    return alerts


def _affected_dict(snap: dict) -> dict:
    ev = snap["event"]
    return {
        "name": snap["name"],
        "region": snap["region"],
        "region_code": snap["region_code"],
        "lat": snap["lat"],
        "lon": snap["lon"],
        "event_type": ev["event_type"],
        "severity": ev["severity"],
        "rain_intensity": ev["rain_intensity"],
        "risk_level": ev["risk_level"],
        "risk_score": ev["risk_score"],
        "cause": ev["cause"],
        "started_at": ev.get("started_at"),
        "updated_at": snap["updated_at"],
        "expected_end": ev.get("expected_end"),
        "impact_summary": snap["explanation"]["what"],
        "affected_areas": [snap["name"]] + ([snap["capital"]] if snap.get("capital") else []),
    }


# ---------------------------------------------------------------------------
# Refresh cycle
# ---------------------------------------------------------------------------
async def refresh_all(broadcast: bool = True) -> dict:
    if state.refreshing:
        log.info("Refresh already in progress; skipping.")
        return state.national
    state.refreshing = True
    log.info("Starting refresh of %d provinces…", len(geo.PROVINCES))
    try:
        locations = [
            {"key": p["name"], "lat": p["lat"], "lon": p["lon"]} for p in geo.PROVINCES
        ]
        fetched = await weather_client.fetch_many(locations)

        # Update the data-driven baselines / anomaly model from stored history.
        try:
            analytics.intel.update_baselines(_load_recent_readings())
        except Exception as exc:  # noqa: BLE001
            log.warning("Analytics baseline update skipped: %s", exc)

        snapshots: dict[str, dict] = {}
        all_alerts: list[dict] = []
        anomaly_count = 0

        for p in geo.PROVINCES:
            payload = fetched.get(p["name"])
            if not payload:
                # keep previous snapshot if available (graceful degradation)
                if p["name"] in state.provinces:
                    snapshots[p["name"]] = state.provinces[p["name"]]
                continue

            prov = {
                "name": p["name"],
                "region": geo.region_name(p["region"]),
                "region_code": p["region"],
                "capital": p.get("capital", ""),
                "lat": p["lat"],
                "lon": p["lon"],
            }
            current = payload["current"]
            event_raw = classifier.classify(prov, payload)
            rsk = risk.compute_risk(prov, current, event_raw, payload)
            explanation = ai_explainer.explain_event(prov, current, event_raw, rsk)

            # Data-driven analysis: trend, anomaly, refined confidence
            an = analytics.intel.analyze(prov, payload, current, rsk["confidence"])
            explanation["analysis"] = an["analysis_text"]
            explanation["confidence"] = an["confidence"]
            if an["label"]:
                anomaly_count += 1

            event = {
                "event_type": event_raw["event_type"],
                "severity": event_raw["severity"],
                "cause": event_raw["cause"],
                "rain_intensity": event_raw["rain_intensity"],
                "risk_level": rsk["risk_level"],
                "risk_score": rsk["risk_score"],
                "confidence": an["confidence"],
                "started_at": event_raw.get("started_at"),
                "expected_end": event_raw.get("expected_end"),
                "incoming_rain_at": event_raw.get("incoming_rain_at"),
                "summary": explanation["what"],
                "hazards": rsk.get("hazards", {}),
                "trend": an["temp_trend"],
                "rain_trend": an["rain_trend"],
                "temp_anomaly_c": an["temp_anomaly_c"],
                "anomaly": an["label"],
            }
            affected = classifier.is_affected(event_raw)
            prov_alerts = _province_alerts(prov, event_raw, rsk)
            all_alerts.extend(prov_alerts)

            snapshots[p["name"]] = {
                **prov,
                "updated_at": payload.get("observed_at") or now_iso(),
                "source": payload.get("source", "open-meteo"),
                "condition": _build_condition(current, event_raw),
                "event": event if affected else None,
                "affected": affected,
                "alerts": [a["title"] for a in prov_alerts],
                "explanation": explanation,
                "forecast": {"hourly": payload.get("hourly", []),
                             "daily": payload.get("daily", [])},
            }

        # --- National summary ---
        temps = [s["condition"]["temperature_c"] for s in snapshots.values()
                 if s["condition"].get("temperature_c") is not None]
        affected_list = [s for s in snapshots.values() if s.get("affected") and s.get("event")]
        affected_sorted = sorted(affected_list, key=lambda s: s["event"]["risk_score"], reverse=True)
        top_affected = [_affected_dict(s) for s in affected_sorted]

        highest = "info"
        for s in affected_list:
            if classifier.severity_rank(s["event"]["severity"]) > classifier.severity_rank(highest):
                highest = s["event"]["severity"]

        stats = {
            "generated_at": now_iso(),
            "provinces_total": len(snapshots),
            "provinces_raining": sum(1 for s in snapshots.values() if s["condition"]["is_raining"]),
            "provinces_affected": len(affected_list),
            "active_alerts": len(all_alerts),
            "highest_severity": highest,
            "avg_temp_c": round(statistics.fmean(temps), 1) if temps else None,
            "temp_anomalies": anomaly_count,
        }
        report = ai_explainer.national_report(stats, top_affected)
        national = {**stats, **report, "top_affected": top_affected[:40]}

        # --- Commit to live state ---
        state.provinces = snapshots
        state.alerts = sorted(
            all_alerts,
            key=lambda a: classifier.severity_rank(a["severity"]),
            reverse=True,
        )
        state.national = national
        state.last_refresh = stats["generated_at"]

        _persist(snapshots, state.alerts, national)

        if broadcast:
            await manager.broadcast({
                "type": "refresh",
                "national": national,
                "alerts": state.alerts[:50],
                "provinces": [_map_marker(s) for s in snapshots.values()],
                "last_refresh": state.last_refresh,
            })
        log.info("Refresh complete: %d affected, %d alerts.",
                 stats["provinces_affected"], stats["active_alerts"])
        return national
    finally:
        state.refreshing = False


def _map_marker(snap: dict) -> dict:
    """Compact per-province payload for map markers."""
    c = snap["condition"]
    ev = snap.get("event") or {}
    return {
        "name": snap["name"],
        "region": snap["region"],
        "region_code": snap["region_code"],
        "lat": snap["lat"],
        "lon": snap["lon"],
        "temp": c.get("temperature_c"),
        "icon": c.get("icon"),
        "condition_text": c.get("condition_text"),
        "is_raining": c.get("is_raining"),
        "rain_intensity": c.get("rain_intensity"),
        "affected": snap.get("affected", False),
        "severity": ev.get("severity", "info"),
        "risk_level": ev.get("risk_level", "low"),
        "risk_score": ev.get("risk_score", 0),
        "event_type": ev.get("event_type", "clear"),
    }


# ---------------------------------------------------------------------------
# Persistence (best-effort; never breaks the live feed)
# ---------------------------------------------------------------------------
def _persist(snapshots: dict, alerts: list[dict], national: dict) -> None:
    db = SessionLocal()
    try:
        prov_rows = {p.name: p.id for p in db.scalars(select(models.Province)).all()}
        if not prov_rows:
            return  # not seeded (e.g. DB offline)

        # Readings + events
        for name, snap in snapshots.items():
            pid = prov_rows.get(name)
            if not pid:
                continue
            c = snap["condition"]
            db.add(models.WeatherReading(
                province_id=pid, source=snap["source"],
                temperature_c=c.get("temperature_c"), feels_like_c=c.get("feels_like_c"),
                humidity_pct=c.get("humidity_pct"), wind_speed_kmh=c.get("wind_speed_kmh"),
                wind_dir_deg=c.get("wind_dir_deg"), wind_gust_kmh=c.get("wind_gust_kmh"),
                pressure_hpa=c.get("pressure_hpa"), visibility_km=c.get("visibility_km"),
                uv_index=c.get("uv_index"), cloud_cover_pct=c.get("cloud_cover_pct"),
                precip_mm=c.get("precip_mm"), precip_prob_pct=c.get("precip_prob_pct"),
                condition_code=c.get("condition_code"), condition_text=c.get("condition_text"),
                is_raining=bool(c.get("is_raining")),
            ))
            if snap.get("event"):
                ev = snap["event"]
                db.add(models.WeatherEvent(
                    province_id=pid, event_type=ev["event_type"], severity=ev["severity"],
                    cause=ev["cause"], rain_intensity=ev["rain_intensity"],
                    risk_level=ev["risk_level"], risk_score=ev["risk_score"],
                    confidence=ev["confidence"], summary=ev["summary"], active=True,
                    started_at=_parse(ev.get("started_at")),
                    expected_end=_parse(ev.get("expected_end")),
                ))

        # Alerts: deactivate previous, insert current
        db.query(models.WeatherAlert).filter(models.WeatherAlert.active == True).update(  # noqa: E712
            {models.WeatherAlert.active: False}
        )
        for a in alerts:
            db.add(models.WeatherAlert(
                title=a["title"], category=a["category"], severity=a["severity"],
                province_id=prov_rows.get(a.get("province")), areas={"areas": a.get("areas", [])},
                reason=a["reason"], recommended_action=a["recommended_action"],
                expires_at=_parse(a.get("expires_at")), source=a["source"], active=True,
            ))

        db.add(models.AIReport(
            scope="national", scope_ref="PH", engine=national.get("engine", "rule-engine"),
            headline=national.get("headline", ""), body=national.get("body", ""),
        ))
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        log.warning("Persist skipped (%s)", exc)
    finally:
        db.close()


def _parse(iso: str | None):
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        return None


def _load_recent_readings(limit: int = 5000) -> list[dict]:
    """Load recent stored readings (joined to province name) for analytics."""
    db = SessionLocal()
    try:
        rows = db.execute(
            select(
                models.Province.name,
                models.WeatherReading.temperature_c,
                models.WeatherReading.humidity_pct,
                models.WeatherReading.wind_speed_kmh,
                models.WeatherReading.pressure_hpa,
                models.WeatherReading.precip_mm,
            )
            .join(models.Province, models.WeatherReading.province_id == models.Province.id)
            .order_by(models.WeatherReading.observed_at.desc())
            .limit(limit)
        ).all()
        return [
            {
                "province": r[0], "temperature_c": r[1], "humidity_pct": r[2],
                "wind_speed_kmh": r[3], "pressure_hpa": r[4], "precip_mm": r[5],
            }
            for r in rows
        ]
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not load readings for analytics: %s", exc)
        return []
    finally:
        db.close()
