# -*- coding: utf-8 -*-
"""
Weather intelligence / analytics layer.

Adds a data-driven brain on top of the rule engine:

  * Forecast TREND analysis      — temperature & rainfall direction over the
                                   next hours (numpy linear fit).
  * ANOMALY detection            — per-province temperature z-score against a
                                   baseline LEARNED from the readings stored in
                                   MySQL (falls back to a climatological prior
                                   until enough history accumulates).
  * Multivariate "unusual conditions" — a scikit-learn IsolationForest trained
                                   on the accumulated [temp, humidity, wind,
                                   pressure, precip] readings across all
                                   provinces; flags atypical combinations.
  * Confidence refinement        — based on short-range forecast consistency.

Everything degrades gracefully: if numpy/sklearn are unavailable or there is
little history, it still returns sensible output.
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime

log = logging.getLogger("pwin.analytics")

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    _HAS_SK = True
except Exception:  # pragma: no cover
    _HAS_SK = False

# Rough climatological daytime-temperature priors by region (°C). Used only as a
# baseline until a province has accumulated enough of its own observations.
CLIMO = {
    "CAR": 22.0, "NCR": 31.0, "R1": 30.0, "R2": 31.0, "R3": 32.0, "R4A": 31.0,
    "R4B": 31.0, "R5": 30.5, "R6": 31.0, "R7": 31.0, "R8": 30.5, "R9": 31.0,
    "R10": 30.5, "R11": 31.0, "R12": 31.0, "R13": 30.5, "BARMM": 31.0,
}
CLIMO_STD = 3.0
MIN_HISTORY = 8          # samples before we trust a province's own baseline
IFOREST_MIN_ROWS = 80    # rows before training the multivariate model
FEATURES = ["temperature_c", "humidity_pct", "wind_speed_kmh", "pressure_hpa", "precip_mm"]


class WeatherIntelligence:
    def __init__(self) -> None:
        self._prov_stats: dict[str, tuple[float, float, int]] = {}  # name -> (mean,std,n)
        self._iforest = None
        self._scaler = None
        self._n_samples = 0
        self._trained_at: str | None = None

    # ------------------------------------------------------------------
    # Training / baselines
    # ------------------------------------------------------------------
    def update_baselines(self, readings: list[dict]) -> None:
        """Recompute per-province temp baselines and (re)train the anomaly model.

        `readings`: list of {province, temperature_c, humidity_pct,
        wind_speed_kmh, pressure_hpa, precip_mm}.
        """
        if not readings:
            return
        # Per-province temperature mean/std
        by_prov: dict[str, list[float]] = {}
        for r in readings:
            t = r.get("temperature_c")
            if t is not None:
                by_prov.setdefault(r["province"], []).append(float(t))
        stats: dict[str, tuple[float, float, int]] = {}
        for name, temps in by_prov.items():
            n = len(temps)
            mean = statistics.fmean(temps)
            std = statistics.pstdev(temps) if n > 1 else CLIMO_STD
            stats[name] = (mean, max(std, 1.0), n)
        self._prov_stats = stats

        # Multivariate IsolationForest on complete rows
        self._n_samples = len(readings)
        if _HAS_SK and np is not None and len(readings) >= IFOREST_MIN_ROWS:
            try:
                matrix = [
                    [r.get(f) for f in FEATURES] for r in readings
                    if all(r.get(f) is not None for f in FEATURES)
                ]
                if len(matrix) >= IFOREST_MIN_ROWS:
                    X = np.array(matrix, dtype=float)
                    self._scaler = StandardScaler().fit(X)
                    self._iforest = IsolationForest(
                        n_estimators=120, contamination=0.06, random_state=42
                    ).fit(self._scaler.transform(X))
                    self._trained_at = datetime.now().isoformat(timespec="seconds")
                    log.info("Anomaly model trained on %d rows (%d provinces).",
                             len(matrix), len(stats))
            except Exception as exc:  # noqa: BLE001
                log.warning("IsolationForest training skipped: %s", exc)

    # ------------------------------------------------------------------
    # Per-province analysis
    # ------------------------------------------------------------------
    def analyze(self, prov: dict, payload: dict, current: dict, risk_conf: float = 0.6) -> dict:
        trend = self._trends(payload)
        anom = self._anomaly(prov, current)
        conf = self._confidence(payload, risk_conf)

        notes: list[str] = []
        if anom["label"]:
            notes.append(
                f"Temperature is {abs(anom['temp_anomaly_c']):.1f}°C "
                f"{'above' if anom['temp_anomaly_c'] > 0 else 'below'} the local "
                f"{'baseline' if anom['n'] >= MIN_HISTORY else 'seasonal norm'} ({anom['label']})."
            )
        if anom["unusual"]:
            notes.append("Atmospheric readings form an atypical combination for this area.")

        analysis_text = trend["summary"]
        if notes:
            analysis_text += " " + " ".join(notes)

        return {
            **trend,
            **anom,
            "confidence": conf,
            "notes": notes,
            "analysis_text": analysis_text.strip(),
        }

    # ------------------------------------------------------------------
    def _trends(self, payload: dict) -> dict:
        hourly = payload.get("hourly", []) or []
        temps = [h.get("temp_c") for h in hourly[:12] if h.get("temp_c") is not None]
        probs = [h.get("precip_prob") or 0 for h in hourly[:12]]

        # temperature direction over next ~12h
        delta = 0.0
        if len(temps) >= 2:
            if np is not None and len(temps) >= 4:
                slope = float(np.polyfit(range(len(temps)), temps, 1)[0])
                delta = slope * (len(temps) - 1)
            else:
                delta = temps[-1] - temps[0]
        temp_trend = "rising" if delta >= 1.5 else "falling" if delta <= -1.5 else "steady"

        # rainfall direction
        near = statistics.fmean(probs[:3]) if probs[:3] else 0
        later = statistics.fmean(probs[3:9]) if probs[3:9] else near
        if max(probs) < 20:
            rain_trend = "none"
        elif later - near >= 15:
            rain_trend = "increasing"
        elif near - later >= 15:
            rain_trend = "easing"
        else:
            rain_trend = "steady"

        peak_pct, peak_at = 0, None
        for h in hourly[:24]:
            p = h.get("precip_prob") or 0
            if p > peak_pct:
                peak_pct, peak_at = p, h.get("time")

        # human summary
        bits = []
        if temp_trend == "rising":
            bits.append(f"Temperatures trending up (~{abs(delta):.0f}°C over ~12h)")
        elif temp_trend == "falling":
            bits.append(f"Temperatures trending down (~{abs(delta):.0f}°C over ~12h)")
        else:
            bits.append("Temperatures holding steady")
        if rain_trend == "increasing":
            bits.append(f"rain chances rising toward {peak_pct}%")
        elif rain_trend == "easing":
            bits.append("rain chances easing")
        elif rain_trend == "steady" and max(probs) >= 40:
            bits.append(f"persistent rain chances (~{int(near)}%)")
        elif rain_trend == "none":
            bits.append("little to no rain expected")
        summary = "; ".join(bits) + "."

        return {
            "temp_trend": temp_trend,
            "temp_delta_12h": round(delta, 1),
            "rain_trend": rain_trend,
            "peak_rain_pct": peak_pct,
            "peak_rain_at": peak_at,
            "summary": summary,
        }

    def _anomaly(self, prov: dict, current: dict) -> dict:
        temp = current.get("temperature_c")
        name = prov["name"]
        mean, std, n = self._prov_stats.get(name, (None, CLIMO_STD, 0))
        if n < MIN_HISTORY or mean is None:
            mean = CLIMO.get(prov.get("region_code", ""), 31.0)
            std = CLIMO_STD
        std = max(std, 1.5)

        z, anomaly_c, label = 0.0, 0.0, None
        if temp is not None:
            z = (temp - mean) / std
            anomaly_c = temp - mean
            if z >= 2.0:
                label = "unusually warm"
            elif z <= -2.0:
                label = "unusually cool"

        unusual = False
        if self._iforest is not None and self._scaler is not None and np is not None:
            vec = [current.get(f) for f in FEATURES]
            if all(v is not None for v in vec):
                try:
                    Xs = self._scaler.transform(np.array([vec], dtype=float))
                    unusual = bool(self._iforest.predict(Xs)[0] == -1)
                except Exception:  # noqa: BLE001
                    unusual = False

        return {
            "temp_z": round(z, 2),
            "temp_anomaly_c": round(anomaly_c, 1),
            "label": label,
            "unusual": unusual,
            "baseline_mean": round(mean, 1),
            "n": n,
        }

    def _confidence(self, payload: dict, risk_conf: float) -> float:
        hourly = payload.get("hourly", []) or []
        probs = [h.get("precip_prob") or 0 for h in hourly[:12]]
        # Consistent short-range forecast -> more confident
        consistency = 0.0
        if len(probs) >= 4:
            spread = statistics.pstdev(probs)
            consistency = 0.9 if spread < 12 else 0.75 if spread < 25 else 0.6
        conf = max(risk_conf, consistency) if consistency else risk_conf
        return round(min(0.95, conf), 2)

    # ------------------------------------------------------------------
    def status(self) -> dict:
        return {
            "anomaly_model": "isolation-forest" if self._iforest is not None else "warming-up",
            "samples": self._n_samples,
            "provinces_tracked": len(self._prov_stats),
            "trained_at": self._trained_at,
            "sklearn": _HAS_SK,
            "numpy": np is not None,
        }


intel = WeatherIntelligence()
