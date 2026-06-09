"""
Risk scoring + secondary-hazard inference (flood / landslide / wind / heat).

Produces a 0-100 composite risk score and a discrete risk level, plus derived
hazard flags used to drive the alert center. Uses simple, explainable weights
rather than a black box so operators can reason about the output.
"""

from __future__ import annotations

from .classifier import RAIN_LEVEL

RISK_LEVELS = ["low", "moderate", "high", "severe", "extreme"]


def _level_from_score(score: float) -> str:
    if score >= 85:
        return "extreme"
    if score >= 65:
        return "severe"
    if score >= 45:
        return "high"
    if score >= 25:
        return "moderate"
    return "low"


def compute_risk(province: dict, current: dict, event: dict, payload: dict) -> dict:
    """Return {risk_score, risk_level, confidence, hazards: {...}}."""
    score = 0.0

    intensity = event.get("rain_intensity", "none")
    score += RAIN_LEVEL.get(intensity, 0) * 14  # up to 70 for torrential

    if event.get("is_thunder"):
        score += 15

    wind = current.get("wind_speed_kmh") or 0
    gust = current.get("wind_gust_kmh") or wind
    if gust >= 88:
        score += 30
    elif gust >= 62:
        score += 20
    elif gust >= 45:
        score += 10
    elif gust >= 30:
        score += 4

    feels = current.get("feels_like_c")
    if feels is not None:
        if feels >= 41:
            score += 18
        elif feels >= 37:
            score += 10
        elif feels >= 33:
            score += 4

    # Sustained rainfall over the next 24h amplifies flood/landslide risk
    daily = payload.get("daily") or []
    rain_24h = daily[0].get("precip_sum") if daily else None
    if rain_24h:
        if rain_24h >= 100:
            score += 18
        elif rain_24h >= 50:
            score += 10
        elif rain_24h >= 25:
            score += 4

    score = max(0.0, min(100.0, score))
    level = _level_from_score(score)

    # --- Derived hazards ---
    hazards: dict[str, str] = {}
    rl = RAIN_LEVEL.get(intensity, 0)
    if rl >= 3 or (rain_24h or 0) >= 50:
        hazards["flood"] = "high" if (rl >= 4 or (rain_24h or 0) >= 100) else "moderate"
    if rl >= 3 and province.get("region_code") in {"CAR", "R2", "R8", "R11", "R13"}:
        # mountainous / typhoon-prone -> landslide susceptibility
        hazards["landslide"] = "high" if rl >= 4 else "moderate"
    elif rl >= 4:
        hazards["landslide"] = "moderate"
    if gust >= 62:
        hazards["wind"] = "high" if gust >= 88 else "moderate"
    if feels is not None and feels >= 37:
        hazards["heat"] = "high" if feels >= 41 else "moderate"
    if event.get("is_thunder"):
        hazards["thunderstorm"] = "moderate"
    # Coastal hazard for high winds in coastal/island provinces
    if gust >= 55 and province.get("region_code") in {
        "R4B", "R5", "R8", "R2", "BARMM", "R13", "NCR", "R1",
    }:
        hazards["coastal"] = "moderate"

    # --- Confidence ---
    # Higher when current obs and short-range forecast agree.
    confidence = 0.6
    prob = current.get("precip_prob_pct")
    if prob is not None:
        if current.get("is_raining") and prob >= 60:
            confidence = 0.85
        elif not current.get("is_raining") and prob <= 20:
            confidence = 0.8
        else:
            confidence = 0.65
    if intensity in ("intense", "torrential"):
        confidence = max(confidence, 0.8)

    return {
        "risk_score": round(score, 1),
        "risk_level": level,
        "confidence": round(confidence, 2),
        "hazards": hazards,
        "rain_24h_mm": rain_24h,
    }
