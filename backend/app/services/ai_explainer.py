# -*- coding: utf-8 -*-
"""
AI weather explanation engine.

Generates plain-language, emergency-ready explanations of what is happening,
where, when it started, when it may end, why, who is affected and how severe it
is. Works fully offline using a deterministic rule-based narrative engine; if
``OPENAI_API_KEY`` is configured it upgrades national reports and (optionally)
per-province explanations to LLM-authored prose.
"""

from __future__ import annotations

import logging
from datetime import datetime

from ..config import settings
from .classifier import severity_rank

log = logging.getLogger("pwin.ai")

# --- Cause -> mechanism explanation ---------------------------------------
CAUSE_WHY = {
    "Southwest Monsoon (Habagat)":
        "the Southwest Monsoon (Habagat) is funneling warm, moisture-rich air "
        "across the western seaboard, fueling persistent rain and showers.",
    "Monsoon-enhanced thunderstorms":
        "the monsoon flow is feeding extra moisture into building storm clouds, "
        "intensifying thunderstorm development.",
    "Northeast Monsoon (Amihan)":
        "the Northeast Monsoon (Amihan) is pushing cool, moist air against the "
        "eastern sections, producing cloudy skies and rain along windward areas.",
    "Shear line / frontal system":
        "a shear line — where cold northeasterly air meets warm easterly air — "
        "is triggering clusters of rain over the area.",
    "Intertropical Convergence Zone (ITCZ)":
        "the Intertropical Convergence Zone (ITCZ), a belt of converging winds "
        "near the equator, is generating widespread cloudiness and rain.",
    "Easterlies":
        "warm, humid easterly winds from the Pacific are carrying moisture inland, "
        "sparking scattered showers and thunderstorms.",
    "Low-pressure area activity":
        "a low-pressure area is enhancing convection and drawing in moist air, "
        "leading to unsettled, rainy weather.",
    "Tropical cyclone influence":
        "the circulation of a tropical cyclone is driving strong winds and heavy "
        "rain across the region.",
    "Localized convective thunderstorms":
        "intense daytime heating has destabilized the atmosphere, allowing towering "
        "thunderclouds to develop locally.",
    "Localized thunderstorms":
        "localized heating and humidity are fueling isolated thunderstorms.",
    "Warm, dry conditions":
        "a dominant ridge of high pressure and strong sunshine are keeping skies "
        "mostly clear and temperatures elevated.",
    "Surge of the Northeast Monsoon":
        "a surge in the Northeast Monsoon is strengthening winds across exposed "
        "and coastal areas.",
    "Surge of the Southwest Monsoon":
        "a surge in the Southwest Monsoon is strengthening winds and enhancing rain.",
    "Pressure gradient winds":
        "a tight pressure gradient is producing gusty winds over the area.",
}

EVENT_WHAT = {
    "thunderstorm": "Thunderstorms with lightning and gusty downpours",
    "heavy_rain": "Heavy rainfall",
    "moderate_rain": "Moderate, steady rainfall",
    "light_rain": "Light rain and passing showers",
    "showers": "Scattered showers",
    "strong_winds": "Strong, potentially damaging winds",
    "windy": "Breezy to windy conditions",
    "heat": "Hot and humid conditions with elevated heat index",
    "cloudy": "Overcast, cloudy skies",
    "clear": "Fair and generally clear weather",
}

SEVERITY_PHRASE = {
    "info": "minor and low-impact",
    "advisory": "noticeable but manageable",
    "watch": "potentially disruptive — stay alert",
    "warning": "dangerous — take protective action",
    "critical": "extremely dangerous — act immediately",
}


def _fmt_time(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    return dt.strftime("%I:%M %p, %b %d").lstrip("0")


def _precautions(event: dict, risk: dict) -> list[str]:
    et = event["event_type"]
    hz = risk.get("hazards", {})
    out: list[str] = []
    if et in ("heavy_rain", "moderate_rain") or "flood" in hz:
        out += [
            "Avoid crossing flooded roads and swollen waterways.",
            "Prepare to move valuables and vehicles to higher ground.",
        ]
    if "landslide" in hz:
        out.append("Residents near hills and steep slopes should watch for landslides.")
    if et == "thunderstorm":
        out += [
            "Stay indoors and away from windows during lightning.",
            "Unplug sensitive electronics; avoid open fields and tall trees.",
        ]
    if et == "strong_winds" or "wind" in hz:
        out += [
            "Secure loose roofing, signage and outdoor objects.",
            "Postpone sea travel for small vessels.",
        ]
    if "coastal" in hz:
        out.append("Coastal communities should watch for big waves and storm surge.")
    if et == "heat" or "heat" in hz:
        out += [
            "Stay hydrated and limit outdoor activity from 10 AM to 4 PM.",
            "Check on the elderly, children and outdoor workers.",
        ]
    if et in ("clear", "cloudy") and not out:
        out.append("No special precautions needed — typical day-to-day conditions.")
    if risk.get("risk_level") in ("severe", "extreme"):
        out.append("Monitor PAGASA bulletins and local disaster office advisories.")
    # de-duplicate while preserving order
    seen, uniq = set(), []
    for p in out:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq


def explain_event(province: dict, current: dict, event: dict, risk: dict) -> dict:
    """Rule-based per-province explanation (the always-available engine)."""
    et = event["event_type"]
    name = province["name"]
    region = province.get("region", "")
    what_base = EVENT_WHAT.get(et, "Notable weather")
    intensity = event.get("rain_intensity", "none")

    if et in ("heavy_rain", "moderate_rain", "light_rain") and intensity != "none":
        what = f"{what_base} ({intensity} intensity) is being observed over {name}."
    else:
        what = f"{what_base} over {name}."

    where = f"{name}, {region}" + (
        f", centered near {province.get('capital')}" if province.get("capital") else ""
    )

    if event.get("started_at"):
        when_started = f"Began around {_fmt_time(event['started_at'])} (PHT)."
    elif event.get("incoming_rain_at"):
        when_started = f"Not yet ongoing — rain may arrive by {_fmt_time(event['incoming_rain_at'])} (PHT)."
    else:
        when_started = "Ongoing as part of today's prevailing conditions."

    if event.get("expected_end"):
        when_end = f"Likely to ease by {_fmt_time(event['expected_end'])} (PHT)."
    elif et in ("clear", "cloudy"):
        when_end = "No significant change expected in the next several hours."
    else:
        when_end = "Conditions may persist; monitor short-range updates."

    why = "Currently, " + CAUSE_WHY.get(
        event.get("cause", ""), "prevailing weather patterns are shaping local conditions."
    )

    sev = event["severity"]
    how_severe = (
        f"Severity is rated **{sev.upper()}** ({SEVERITY_PHRASE.get(sev, '')}). "
        f"Composite risk score {risk['risk_score']}/100 — {risk['risk_level'].upper()} risk."
    )
    who = f"Communities across {name}" + (
        f" and nearby parts of {region}" if region else ""
    ) + " are most directly affected."

    return {
        "what": what,
        "where": where,
        "when_started": when_started,
        "when_end": when_end,
        "why": why,
        "who": who,
        "how_severe": how_severe,
        "severity": sev,
        "confidence": risk["confidence"],
        "precautions": _precautions(event, risk),
        "engine": "rule-engine",
    }


def national_report(stats: dict, top_affected: list[dict]) -> dict:
    """Generate the national headline + body (rule engine, OpenAI optional)."""
    rule = _national_report_rule(stats, top_affected)
    if settings.OPENAI_API_KEY:
        try:
            return _national_report_openai(stats, top_affected, rule)
        except Exception as exc:  # noqa: BLE001
            log.warning("OpenAI national report failed, using rule engine: %s", exc)
    return rule


def _national_report_rule(stats: dict, top_affected: list[dict]) -> dict:
    raining = stats["provinces_raining"]
    affected = stats["provinces_affected"]
    total = stats["provinces_total"]
    sev = stats["highest_severity"]

    if affected == 0:
        headline = "Generally fair weather prevails across the Philippines"
    elif sev in ("critical", "warning"):
        headline = f"Hazardous weather affecting {affected} province(s) — {sev.upper()} level"
    else:
        headline = f"Active weather across {affected} of {total} provinces"

    lines = [
        f"As of {_fmt_time(stats['generated_at'])} PHT, {raining} province(s) are "
        f"experiencing rain and {affected} are under notable weather conditions.",
    ]
    if top_affected:
        names = ", ".join(p["name"] for p in top_affected[:5])
        causes = {p["cause"] for p in top_affected[:5]}
        lines.append(
            f"The most affected areas are {names}. "
            f"Main driver(s): {', '.join(sorted(causes))}."
        )
        worst = top_affected[0]
        lines.append(
            f"{worst['name']} shows the highest risk ({worst['risk_level'].upper()}, "
            f"score {worst['risk_score']}/100) due to {worst['cause'].lower()}."
        )
    else:
        lines.append("No provinces are currently flagged for hazardous weather.")
    if stats.get("avg_temp_c") is not None:
        lines.append(f"National average temperature is about {stats['avg_temp_c']}°C.")
    if stats.get("temp_anomalies"):
        lines.append(
            f"{stats['temp_anomalies']} province(s) are showing temperatures "
            "notably away from their local norm."
        )

    return {"headline": headline, "body": " ".join(lines), "engine": "rule-engine"}


def _national_report_openai(stats: dict, top_affected: list[dict], fallback: dict) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    facts = {
        "generated_at": stats["generated_at"],
        "provinces_total": stats["provinces_total"],
        "provinces_raining": stats["provinces_raining"],
        "provinces_affected": stats["provinces_affected"],
        "active_alerts": stats["active_alerts"],
        "highest_severity": stats["highest_severity"],
        "avg_temp_c": stats.get("avg_temp_c"),
        "top_affected": [
            {k: p[k] for k in ("name", "region", "event_type", "severity",
                               "risk_level", "risk_score", "cause")}
            for p in top_affected[:8]
        ],
    }
    prompt = (
        "You are a Philippine meteorological operations analyst. Using ONLY the "
        "JSON facts below, write a concise national weather intelligence brief. "
        "Return a one-line headline, then 3-4 sentences: what is happening, where, "
        "why, and what the public should watch. Calm, clear, emergency-ready tone. "
        "Do not invent data.\n\nFACTS:\n" + str(facts)
    )
    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=350,
    )
    text = resp.choices[0].message.content.strip()
    headline, _, body = text.partition("\n")
    return {
        "headline": headline.strip("# ").strip() or fallback["headline"],
        "body": body.strip() or fallback["body"],
        "engine": "openai",
    }


def _reply(question, answer, matched=None):
    return {"question": question, "answer": answer, "engine": "rule-engine",
            "matched_provinces": matched or []}


def _t(c):
    v = c.get("temperature_c")
    return round(v) if v is not None else "?"


def answer_question(question: str, provinces_index: dict) -> dict:
    """Natural-language query over current province snapshots.

    Handles: specific provinces, "where is it raining", hottest/coldest,
    active alerts/warnings, region summaries, and forecast/tomorrow questions.
    """
    q = question.lower().strip()
    snaps = provinces_index
    if not snaps:
        return _reply(question, "Weather data is still loading — try again in a moment.")

    matched = sorted(
        [name for name in snaps if name.lower() in q],
        key=len, reverse=True,
    )

    # --- Superlatives -----------------------------------------------------
    temp_named = [(n, s["condition"].get("temperature_c")) for n, s in snaps.items()
                  if s["condition"].get("temperature_c") is not None]
    if any(w in q for w in ("hottest", "warmest", "highest temp")):
        n, t = max(temp_named, key=lambda x: x[1])
        return _reply(question, f"{n} is currently the hottest at {round(t)}°C.", [n])
    if any(w in q for w in ("coldest", "coolest", "lowest temp")):
        n, t = min(temp_named, key=lambda x: x[1])
        return _reply(question, f"{n} is currently the coolest at {round(t)}°C.", [n])

    # --- Alerts / warnings ------------------------------------------------
    if any(w in q for w in ("alert", "warning", "danger", "severe", "affected")):
        sev_named = [(n, s["event"]) for n, s in snaps.items()
                     if s.get("event") and severity_rank(s["event"]["severity"]) >= severity_rank("watch")]
        sev_named.sort(key=lambda x: x[1]["risk_score"], reverse=True)
        if not sev_named:
            return _reply(question, "No provinces are under watch/warning-level conditions right now.")
        names = [n for n, _ in sev_named[:10]]
        return _reply(
            question,
            f"{len(sev_named)} province(s) are under elevated weather: "
            + ", ".join(f"{n} ({e['severity']})" for n, e in sev_named[:8])
            + ("…" if len(sev_named) > 8 else "."),
            names,
        )

    # --- Where is it raining ---------------------------------------------
    if "rain" in q and not matched:
        raining = [n for n, s in snaps.items() if s["condition"]["is_raining"]]
        if raining:
            return _reply(question,
                          f"It is currently raining in {len(raining)} province(s): "
                          + ", ".join(raining[:15]) + ("…" if len(raining) > 15 else "."),
                          raining[:15])
        return _reply(question, "No provinces are reporting rain right now.")

    # --- Region summary ---------------------------------------------------
    for code, rname in [(s["region_code"], s["region"]) for s in snaps.values()]:
        if rname.lower() in q:
            members = [s for s in snaps.values() if s["region"] == rname]
            rain_n = sum(1 for s in members if s["condition"]["is_raining"])
            aff_n = sum(1 for s in members if s.get("affected"))
            return _reply(question,
                          f"{rname}: {len(members)} provinces, {rain_n} with rain, "
                          f"{aff_n} under notable weather.",
                          [s["name"] for s in members[:6]])

    # --- Specific province/provinces -------------------------------------
    if matched:
        tomorrow = any(w in q for w in ("tomorrow", "forecast", "next", "later", "week"))
        parts = []
        for name in matched[:4]:
            s = snaps[name]
            c, ev = s["condition"], (s.get("event") or {})
            if tomorrow:
                daily = (s.get("forecast", {}) or {}).get("daily", [])
                if len(daily) >= 2:
                    d = daily[1]
                    parts.append(f"{name} tomorrow: {d.get('text','')}, "
                                 f"{round(d.get('tmin') or 0)}–{round(d.get('tmax') or 0)}°C, "
                                 f"{d.get('precip_prob') or 0}% chance of rain.")
                    continue
            rain = "raining" if c["is_raining"] else "not raining"
            line = (f"{name}: {c.get('condition_text','')}, {_t(c)}°C, currently {rain}"
                    + (f" — {ev.get('event_type','').replace('_',' ')} ({ev.get('severity','')})" if ev else ""))
            an = s.get("explanation", {}).get("analysis")
            parts.append(line + (f". {an}" if an else "."))
        return _reply(question, " ".join(parts), matched[:4])

    return _reply(
        question,
        "Try: 'is it raining in Cebu?', 'where is it raining?', 'hottest province', "
        "'any warnings?', 'forecast for Davao del Sur', or a region like 'Bicol Region'.",
    )
