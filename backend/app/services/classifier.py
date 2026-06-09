"""
Weather event classification rule engine.

Pure-Python meteorological heuristics that turn a normalised weather payload
into a classified event: type, rain intensity, severity, probable cause, and
estimated start / end times. No external services required.

Thresholds follow PAGASA-style rainfall intensity bands and common wind/heat
advisory levels so output reads like an operational weather product.
"""

from __future__ import annotations

from datetime import datetime

from .weather_client import RAIN_CODES, code_text

# --- Region groupings used for seasonal cause inference --------------------
# Western seaboard: exposed to the Southwest Monsoon (Habagat)
WEST_REGIONS = {"R1", "R3", "R4A", "R4B", "R6", "NCR", "CAR"}
# Eastern seaboard: exposed to the Northeast Monsoon (Amihan), shear line, easterlies
EAST_REGIONS = {"R2", "R5", "R8", "R13", "R7"}
# Mindanao / low latitudes: frequently under the ITCZ
MINDANAO_REGIONS = {"R9", "R10", "R11", "R12", "BARMM", "R13"}

SEVERITY_ORDER = ["info", "advisory", "watch", "warning", "critical"]


def severity_rank(sev: str) -> int:
    return SEVERITY_ORDER.index(sev) if sev in SEVERITY_ORDER else 0


def rain_intensity_from_mm(mm: float | None) -> str:
    """PAGASA-style hourly rainfall intensity bands."""
    if mm is None or mm < 0.1:
        return "none"
    if mm < 2.5:
        return "light"
    if mm < 7.5:
        return "moderate"
    if mm < 15:
        return "heavy"          # ~ Yellow
    if mm < 30:
        return "intense"        # ~ Orange
    return "torrential"         # ~ Red


RAIN_LEVEL = {"none": 0, "light": 1, "moderate": 2, "heavy": 3, "intense": 4, "torrential": 5}


def _is_rainy(series: dict, i: int) -> bool:
    if i < 0 or i >= len(series.get("time", [])):
        return False
    precip = series["precip"][i] if i < len(series["precip"]) else None
    code = series["code"][i] if i < len(series["code"]) else None
    # Trust the measured precipitation series when present (it's the real signal);
    # fall back to the weather code only when precip is missing.
    if precip is not None:
        return precip >= 0.1
    return code in RAIN_CODES


def _rain_window(series: dict, now_i: int) -> tuple[str | None, str | None]:
    """Estimate (started_at, expected_end) ISO strings for an ongoing rain event."""
    times = series.get("time", [])
    if not times or now_i >= len(times):
        return None, None

    # Walk backwards to find the start of the current rainy stretch.
    start_i = now_i
    while start_i - 1 >= 0 and _is_rainy(series, start_i - 1):
        start_i -= 1

    # Walk forward to find where it eases (2 consecutive dry hours = ended).
    end_i = now_i
    n = len(times)
    while end_i + 1 < n:
        if not _is_rainy(series, end_i + 1) and not _is_rainy(series, min(end_i + 2, n - 1)):
            break
        end_i += 1

    started = times[start_i] if start_i <= now_i else None
    expected_end = times[min(end_i + 1, n - 1)] if end_i + 1 < n else None
    return started, expected_end


def _next_rain_start(series: dict, now_i: int, horizon: int = 24) -> str | None:
    times = series.get("time", [])
    for i in range(now_i, min(now_i + horizon, len(times))):
        if _is_rainy(series, i):
            return times[i]
    return None


def _month_of(payload: dict) -> int:
    try:
        return datetime.fromisoformat(payload.get("observed_at", "")).month
    except Exception:  # noqa: BLE001
        return datetime.now().month


def infer_cause(region_code: str, event_type: str, month: int,
                wind_label: str, wind_kmh: float) -> str:
    """Heuristic meteorological cause for the Philippines by season + geography."""
    sw_monsoon = month in (6, 7, 8, 9)
    ne_monsoon = month in (12, 1, 2)
    shear_season = month in (12, 1, 2, 3)
    hot_dry = month in (3, 4, 5)
    blows_from_sw = wind_label in {"SW", "SSW", "WSW", "S", "W"}
    blows_from_ne = wind_label in {"NE", "NNE", "ENE", "N", "E"}

    if event_type in ("strong_winds",) and wind_kmh >= 62:
        return "Tropical cyclone influence"
    if event_type == "thunderstorm":
        if sw_monsoon and region_code in WEST_REGIONS:
            return "Monsoon-enhanced thunderstorms"
        return "Localized convective thunderstorms"
    if event_type in ("heavy_rain", "moderate_rain", "light_rain", "showers"):
        if sw_monsoon and (region_code in WEST_REGIONS or blows_from_sw):
            return "Southwest Monsoon (Habagat)"
        if ne_monsoon and (region_code in EAST_REGIONS or blows_from_ne):
            return "Northeast Monsoon (Amihan)"
        if shear_season and region_code in EAST_REGIONS:
            return "Shear line / frontal system"
        if region_code in MINDANAO_REGIONS:
            return "Intertropical Convergence Zone (ITCZ)"
        if region_code in EAST_REGIONS:
            return "Easterlies"
        return "Low-pressure area activity"
    if event_type == "heat":
        return "Warm, dry conditions" + (" (Amihan transition)" if hot_dry else "")
    if event_type == "windy":
        if ne_monsoon:
            return "Surge of the Northeast Monsoon"
        if sw_monsoon:
            return "Surge of the Southwest Monsoon"
        return "Pressure gradient winds"
    return "Prevailing weather pattern"


def classify(province: dict, payload: dict) -> dict:
    """
    province: {"name","region_code","region","lat","lon", ...}
    payload:  normalised weather payload from weather_client
    returns:  classified event dict
    """
    cur = payload.get("current", {})
    series = payload.get("series", {})
    now_i = payload.get("now_index", 0)
    month = _month_of(payload)

    precip = cur.get("precip_mm") or 0
    prob = cur.get("precip_prob_pct") or 0
    code = cur.get("condition_code")
    wind = cur.get("wind_speed_kmh") or 0
    gust = cur.get("wind_gust_kmh") or wind
    feels = cur.get("feels_like_c")
    temp = cur.get("temperature_c")
    wind_label = cur.get("wind_dir_label", "")
    is_raining = cur.get("is_raining", False)

    intensity = rain_intensity_from_mm(precip)
    is_thunder = code in {95, 96, 99}

    # --- Determine the dominant event type ---
    if gust >= 88 or wind >= 62:
        # Tropical-cyclone-force winds are the headline hazard, even with rain.
        event_type = "strong_winds"
    elif is_thunder:
        event_type = "thunderstorm"
    elif RAIN_LEVEL[intensity] >= 3:
        event_type = "heavy_rain"
    elif intensity == "moderate":
        event_type = "moderate_rain"
    elif intensity in ("light",) or (is_raining and intensity == "none"):
        event_type = "light_rain"
    elif gust >= 62 or wind >= 45:
        event_type = "strong_winds"
    elif (feels is not None and feels >= 37) or (temp is not None and temp >= 36):
        # Only flag a heat *event* near heat-advisory territory, not merely a
        # warm, humid tropical afternoon (which is the baseline here).
        event_type = "heat"
    elif wind >= 30:
        event_type = "windy"
    elif (code in (2, 3)) or (cur.get("cloud_cover_pct") or 0) >= 70:
        event_type = "cloudy"
    else:
        event_type = "clear"

    # --- Severity ---
    severity = "info"
    if event_type == "thunderstorm":
        severity = "warning" if RAIN_LEVEL[intensity] >= 3 else "watch"
    elif event_type == "heavy_rain":
        severity = {"heavy": "watch", "intense": "warning", "torrential": "critical"}.get(intensity, "watch")
    elif event_type == "moderate_rain":
        severity = "advisory"
    elif event_type == "light_rain":
        severity = "info"
    elif event_type == "strong_winds":
        severity = "critical" if gust >= 88 else "warning" if gust >= 62 else "watch"
    elif event_type == "heat":
        # event only triggers at feels >= 37, so this is advisory or above
        severity = "warning" if (feels or 0) >= 41 else "advisory"
    elif event_type == "windy":
        severity = "advisory"

    # --- Timing ---
    if is_raining or RAIN_LEVEL[intensity] > 0 or is_thunder:
        started_at, expected_end = _rain_window(series, now_i)
    elif event_type in ("heat", "windy", "strong_winds"):
        started_at, expected_end = payload.get("observed_at"), None
    else:
        started_at, expected_end = None, None

    incoming = None
    if not is_raining:
        incoming = _next_rain_start(series, now_i)

    cause = infer_cause(province.get("region_code", ""), event_type, month, wind_label, max(wind, gust))

    return {
        "event_type": event_type,
        "rain_intensity": intensity,
        "is_thunder": is_thunder,
        "severity": severity,
        "cause": cause,
        "started_at": started_at,
        "expected_end": expected_end,
        "incoming_rain_at": incoming,
        "condition_text": cur.get("condition_text") or code_text(code),
        "month": month,
    }


def is_affected(event: dict) -> bool:
    """A province is 'affected' if it has notable, actionable weather.

    Plain warm/cloudy/clear/breezy baseline conditions are NOT flagged; rain of
    any intensity, thunderstorms, strong winds, and any advisory-or-above event
    (incl. heat advisories) are.
    """
    et = event["event_type"]
    if et in ("clear", "cloudy"):
        return False
    rain_types = ("light_rain", "moderate_rain", "heavy_rain", "showers")
    if et in rain_types or et in ("thunderstorm", "strong_winds"):
        return True
    # heat / windy only count once they reach advisory or above
    return severity_rank(event["severity"]) >= severity_rank("advisory")
