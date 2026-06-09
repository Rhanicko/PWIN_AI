# -*- coding: utf-8 -*-
"""
Async weather data client.

Default provider is Open-Meteo (https://open-meteo.com) which is free and needs
no API key, making the platform run out of the box. The same normalised
structure is produced regardless of provider so the rest of the pipeline does
not care which source was used.

Returned structure (per location):
{
  "source": "open-meteo",
  "observed_at": "<iso>",
  "current": { ...normalised condition fields... },
  "hourly":  [ {time, temp_c, precip_mm, precip_prob, code, ...}, ... ],
  "daily":   [ {date, code, tmax, tmin, precip_sum, precip_prob, ...}, ... ],
}
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

import httpx

from ..config import settings

log = logging.getLogger("pwin.weather")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
MET_NO_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
USER_AGENT = "PWIN-AI/1.0 (Philippine Weather Intelligence Network; kirbymalasan@gmail.com)"

# WMO weather interpretation codes -> (text, icon hint, severity bias)
WMO = {
    0: ("Clear sky", "clear"),
    1: ("Mainly clear", "clear"),
    2: ("Partly cloudy", "partly-cloudy"),
    3: ("Overcast", "cloudy"),
    45: ("Fog", "fog"),
    48: ("Rime fog", "fog"),
    51: ("Light drizzle", "drizzle"),
    53: ("Moderate drizzle", "drizzle"),
    55: ("Dense drizzle", "drizzle"),
    56: ("Freezing drizzle", "drizzle"),
    57: ("Dense freezing drizzle", "drizzle"),
    61: ("Slight rain", "rain"),
    63: ("Moderate rain", "rain"),
    65: ("Heavy rain", "rain-heavy"),
    66: ("Freezing rain", "rain"),
    67: ("Heavy freezing rain", "rain-heavy"),
    71: ("Slight snow", "snow"),
    73: ("Moderate snow", "snow"),
    75: ("Heavy snow", "snow"),
    77: ("Snow grains", "snow"),
    80: ("Light rain showers", "showers"),
    81: ("Rain showers", "showers"),
    82: ("Violent rain showers", "rain-heavy"),
    85: ("Snow showers", "snow"),
    86: ("Heavy snow showers", "snow"),
    95: ("Thunderstorm", "thunder"),
    96: ("Thunderstorm w/ hail", "thunder"),
    99: ("Severe thunderstorm w/ hail", "thunder"),
}

RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}


def code_text(code: int | None) -> str:
    if code is None:
        return "Unknown"
    return WMO.get(int(code), ("Unknown", "clear"))[0]


def code_icon(code: int | None) -> str:
    if code is None:
        return "clear"
    return WMO.get(int(code), ("Unknown", "clear"))[1]


def wind_dir_label(deg: float | None) -> str:
    if deg is None:
        return ""
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[int((deg % 360) / 22.5 + 0.5) % 16]


def _nearest_hour_index(times: list[str], now_iso: str | None) -> int:
    """Find the hourly array index closest to 'now' (or current.time)."""
    if not times:
        return 0
    target = None
    if now_iso:
        try:
            target = datetime.fromisoformat(now_iso)
        except ValueError:
            target = None
    if target is None:
        target = datetime.now()
    best_i, best_diff = 0, None
    for i, t in enumerate(times):
        try:
            dt = datetime.fromisoformat(t)
        except ValueError:
            continue
        diff = abs((dt - target).total_seconds())
        if best_diff is None or diff < best_diff:
            best_i, best_diff = i, diff
    return best_i


CURRENT_FIELDS = (
    "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,"
    "precipitation,rain,weather_code,cloud_cover,surface_pressure,pressure_msl,"
    "wind_speed_10m,wind_direction_10m,wind_gusts_10m"
)
HOURLY_FIELDS = (
    "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,"
    "weather_code,cloud_cover,visibility,wind_speed_10m,wind_direction_10m,uv_index"
)
DAILY_FIELDS = (
    "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
    "precipitation_probability_max,wind_speed_10m_max,uv_index_max,sunrise,sunset"
)


def _base_params(forecast_days: int = 7) -> dict:
    return {
        "timezone": "Asia/Manila",
        "forecast_days": forecast_days,
        "past_days": 1,  # ~24h history for "when did it start" detection
        "current": CURRENT_FIELDS,
        "hourly": HOURLY_FIELDS,
        "daily": DAILY_FIELDS,
    }


# Transient statuses worth retrying (rate-limit + upstream gateway hiccups).
RETRY_STATUS = {429, 500, 502, 503, 504}


async def _get_with_retry(client: httpx.AsyncClient, params: dict, attempts: int = 3) -> dict | list:
    """GET Open-Meteo with bounded exponential backoff on rate-limit/transient 5xx.

    Delays are capped so a single request never blocks the refresh for long.
    """
    delay = 1.0
    last_exc: Exception | None = None
    resp = None
    for i in range(attempts):
        try:
            resp = await client.get(OPEN_METEO_URL, params=params, timeout=20.0)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_exc = exc
            if i < attempts - 1:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 3.0)
                continue
            raise
        if resp.status_code in RETRY_STATUS and i < attempts - 1:
            await asyncio.sleep(delay)
            delay = min(delay * 2, 3.0)
            continue
        resp.raise_for_status()
        return resp.json()
    if last_exc:
        raise last_exc
    resp.raise_for_status()
    return resp.json()


async def fetch_open_meteo(
    client: httpx.AsyncClient, lat: float, lon: float, forecast_days: int = 7
) -> dict:
    params = {**_base_params(forecast_days), "latitude": lat, "longitude": lon}
    data = await _get_with_retry(client, params)
    if isinstance(data, list):
        data = data[0]
    return _normalise_open_meteo(data)


async def fetch_open_meteo_batch(
    client: httpx.AsyncClient, locs: list[dict], forecast_days: int = 7
) -> dict[str, dict]:
    """Fetch many locations in ONE request (Open-Meteo multi-coordinate API).

    Dramatically cuts request volume (avoids rate limits) and latency.
    `locs` = [{"key","lat","lon"}, ...]; returns {key: normalised_payload}.
    """
    params = {
        **_base_params(forecast_days),
        "latitude": ",".join(str(l["lat"]) for l in locs),
        "longitude": ",".join(str(l["lon"]) for l in locs),
    }
    data = await _get_with_retry(client, params)
    if isinstance(data, dict):
        data = [data]
    out: dict[str, dict] = {}
    for loc, d in zip(locs, data):
        out[loc["key"]] = _normalise_open_meteo(d)
    return out


def _normalise_open_meteo(data: dict) -> dict:
    cur = data.get("current", {}) or {}
    hourly = data.get("hourly", {}) or {}
    daily = data.get("daily", {}) or {}

    htimes = hourly.get("time", []) or []
    idx = _nearest_hour_index(htimes, cur.get("time"))

    def h(key, default=None):
        arr = hourly.get(key) or []
        return arr[idx] if idx < len(arr) else default

    code = cur.get("weather_code")
    visibility_m = h("visibility")
    uv = h("uv_index")
    if uv is None:
        uvmax = daily.get("uv_index_max") or []
        uv = uvmax[0] if uvmax else None

    current = {
        "temperature_c": cur.get("temperature_2m"),
        "feels_like_c": cur.get("apparent_temperature"),
        "humidity_pct": cur.get("relative_humidity_2m"),
        "wind_speed_kmh": cur.get("wind_speed_10m"),
        "wind_dir_deg": cur.get("wind_direction_10m"),
        "wind_dir_label": wind_dir_label(cur.get("wind_direction_10m")),
        "wind_gust_kmh": cur.get("wind_gusts_10m"),
        "pressure_hpa": cur.get("surface_pressure") or cur.get("pressure_msl"),
        "visibility_km": round(visibility_m / 1000.0, 1) if visibility_m is not None else None,
        "uv_index": uv,
        "cloud_cover_pct": cur.get("cloud_cover"),
        "precip_mm": cur.get("precipitation"),
        "precip_prob_pct": h("precipitation_probability"),
        "condition_code": code,
        "condition_text": code_text(code),
        "icon": code_icon(code),
        "is_raining": bool(cur.get("rain", 0) and cur.get("rain", 0) > 0)
        or (code in RAIN_CODES),
    }

    # Build a compact hourly series (next 24h from current index)
    hourly_series = []
    for i in range(idx, min(idx + 24, len(htimes))):
        hourly_series.append({
            "time": htimes[i],
            "temp_c": _at(hourly, "temperature_2m", i),
            "humidity_pct": _at(hourly, "relative_humidity_2m", i),
            "precip_mm": _at(hourly, "precipitation", i),
            "precip_prob": _at(hourly, "precipitation_probability", i),
            "code": _at(hourly, "weather_code", i),
            "cloud": _at(hourly, "cloud_cover", i),
            "wind_kmh": _at(hourly, "wind_speed_10m", i),
        })

    daily_series = []
    dtimes = daily.get("time", []) or []
    for i in range(len(dtimes)):
        daily_series.append({
            "date": dtimes[i],
            "code": _at(daily, "weather_code", i),
            "text": code_text(_at(daily, "weather_code", i)),
            "tmax": _at(daily, "temperature_2m_max", i),
            "tmin": _at(daily, "temperature_2m_min", i),
            "precip_sum": _at(daily, "precipitation_sum", i),
            "precip_prob": _at(daily, "precipitation_probability_max", i),
            "wind_max": _at(daily, "wind_speed_10m_max", i),
            "uv_max": _at(daily, "uv_index_max", i),
            "sunrise": _at(daily, "sunrise", i),
            "sunset": _at(daily, "sunset", i),
        })

    return {
        "source": "open-meteo",
        "observed_at": cur.get("time") or datetime.now(timezone.utc).isoformat(),
        "current": current,
        "hourly": hourly_series,
        "daily": daily_series,
        # Full series (past + future) + the "now" index, used by the
        # classifier to estimate when an event started and when it may end.
        "series": {
            "time": htimes,
            "precip": hourly.get("precipitation") or [],
            "prob": hourly.get("precipitation_probability") or [],
            "code": hourly.get("weather_code") or [],
            "wind": hourly.get("wind_speed_10m") or [],
        },
        "now_index": idx,
    }


def _at(block: dict, key: str, i: int):
    arr = block.get(key) or []
    return arr[i] if i < len(arr) else None


# ---------------------------------------------------------------------------
# MET Norway (api.met.no) — free fallback provider, no API key (UA required).
# ---------------------------------------------------------------------------
def _met_symbol(sym: str | None) -> tuple[int, int]:
    """MET Norway symbol_code -> (WMO-ish code, pseudo rain probability %)."""
    s = (sym or "").lower()
    if "thunder" in s:
        return 95, 85
    if "heavyrain" in s:
        return 65, 90
    if "heavysnow" in s:
        return 75, 80
    if "snow" in s:
        return 73, 70
    if "sleet" in s:
        return 67, 70
    if "rainshowers" in s or "showers" in s:
        return 81, 65
    if "lightrain" in s or "drizzle" in s:
        return 61, 60
    if "rain" in s:
        return 63, 75
    if "fog" in s:
        return 45, 30
    if "partlycloudy" in s or "fair" in s:
        return 2, 18
    if "cloudy" in s:
        return 3, 25
    if "clear" in s:
        return 1, 5
    return 3, 20


def _met_local(utc_iso: str) -> str:
    """Convert MET Norway UTC time to Asia/Manila naive ISO (UTC+8)."""
    try:
        dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
        return (dt.astimezone(timezone.utc) + timedelta(hours=8)).replace(tzinfo=None).isoformat()
    except Exception:  # noqa: BLE001
        return utc_iso


def _apparent_temp(t, rh, wind_kmh):
    """Australian Apparent Temperature (feels-like) approximation."""
    if t is None:
        return None
    try:
        e = (rh if rh is not None else 50) / 100.0 * 6.105 * math.exp(17.27 * t / (237.7 + t))
        ws = (wind_kmh or 0) / 3.6
        return round(t + 0.33 * e - 0.70 * ws - 4.0, 1)
    except Exception:  # noqa: BLE001
        return round(t, 1)


async def fetch_met_no(client: httpx.AsyncClient, lat: float, lon: float) -> dict:
    resp = await client.get(
        MET_NO_URL, params={"lat": round(lat, 4), "lon": round(lon, 4)}, timeout=20.0
    )
    resp.raise_for_status()
    return _normalise_met_no(resp.json())


def _normalise_met_no(data: dict) -> dict:
    ts = data.get("properties", {}).get("timeseries", []) or []
    times, temps, precs, probs, codes, winds, humid, clouds, press, wdir = (
        [], [], [], [], [], [], [], [], [], []
    )
    for entry in ts:
        inst = entry.get("data", {}).get("instant", {}).get("details", {}) or {}
        nxt1 = entry.get("data", {}).get("next_1_hours", {}) or {}
        nxt6 = entry.get("data", {}).get("next_6_hours", {}) or {}
        sym = (nxt1.get("summary") or nxt6.get("summary") or {}).get("symbol_code")
        code, prob = _met_symbol(sym)
        precip = (nxt1.get("details") or {}).get("precipitation_amount")
        if precip is None:
            p6 = (nxt6.get("details") or {}).get("precipitation_amount")
            precip = (p6 / 6.0) if p6 is not None else 0.0
        times.append(_met_local(entry.get("time", "")))
        temps.append(inst.get("air_temperature"))
        precs.append(precip)
        probs.append(prob)
        codes.append(code)
        winds.append(round((inst.get("wind_speed") or 0) * 3.6, 1))
        humid.append(inst.get("relative_humidity"))
        clouds.append(inst.get("cloud_area_fraction"))
        press.append(inst.get("air_pressure_at_sea_level"))
        wdir.append(inst.get("wind_from_direction"))

    idx = _nearest_hour_index(times, datetime.now().isoformat())
    wind = winds[idx] if idx < len(winds) else 0
    temp = temps[idx] if idx < len(temps) else None
    rh = humid[idx] if idx < len(humid) else None
    code = codes[idx] if idx < len(codes) else None

    current = {
        "temperature_c": temp,
        "feels_like_c": _apparent_temp(temp, rh, wind),
        "humidity_pct": rh,
        "wind_speed_kmh": wind,
        "wind_dir_deg": wdir[idx] if idx < len(wdir) else None,
        "wind_dir_label": wind_dir_label(wdir[idx] if idx < len(wdir) else None),
        "wind_gust_kmh": wind,  # MET compact has no gust; use sustained wind
        "pressure_hpa": press[idx] if idx < len(press) else None,
        "visibility_km": None,
        "uv_index": None,
        "cloud_cover_pct": clouds[idx] if idx < len(clouds) else None,
        "precip_mm": precs[idx] if idx < len(precs) else 0.0,
        "precip_prob_pct": probs[idx] if idx < len(probs) else 0,
        "condition_code": code,
        "condition_text": code_text(code),
        "icon": code_icon(code),
        "is_raining": (precs[idx] if idx < len(precs) else 0) >= 0.1 or code in RAIN_CODES,
    }

    hourly = [{
        "time": times[i], "temp_c": temps[i], "humidity_pct": humid[i],
        "precip_mm": precs[i], "precip_prob": probs[i], "code": codes[i],
        "cloud": clouds[i], "wind_kmh": winds[i],
    } for i in range(idx, min(idx + 24, len(times)))]

    days: "OrderedDict[str, dict]" = OrderedDict()
    for i in range(len(times)):
        d = times[i][:10]
        info = days.setdefault(d, {"temps": [], "precip": 0.0, "prob": 0, "codes": []})
        if temps[i] is not None:
            info["temps"].append(temps[i])
        info["precip"] += precs[i] or 0
        info["prob"] = max(info["prob"], probs[i])
        info["codes"].append(codes[i])
    daily = []
    for d, info in list(days.items())[:7]:
        tmps = info["temps"]
        dcode = max(set(info["codes"]), key=info["codes"].count) if info["codes"] else None
        daily.append({
            "date": d, "code": dcode, "text": code_text(dcode),
            "tmax": max(tmps) if tmps else None, "tmin": min(tmps) if tmps else None,
            "precip_sum": round(info["precip"], 1), "precip_prob": info["prob"],
            "wind_max": None, "uv_max": None, "sunrise": None, "sunset": None,
        })

    return {
        "source": "met-norway",
        "observed_at": times[idx] if idx < len(times) else datetime.now().isoformat(),
        "current": current,
        "hourly": hourly,
        "daily": daily,
        "series": {"time": times, "precip": precs, "prob": probs, "code": codes, "wind": winds},
        "now_index": idx,
    }


async def fetch_location(client: httpx.AsyncClient, lat: float, lon: float) -> dict:
    """Fetch a single location from the configured primary provider."""
    # Hook point: branch on settings.PRIMARY_PROVIDER for OWM/WeatherAPI.
    return await fetch_open_meteo(client, lat, lon)


# Locations per multi-coordinate request (keeps URLs well under limits).
CHUNK_SIZE = 30


async def fetch_many(locations: list[dict]) -> dict[str, dict]:
    """Fetch weather for many locations using batched multi-coordinate requests.

    Resilient + time-bounded: a failed chunk is split ONCE into halves and
    retried; if still failing it is skipped (logged). The engine keeps the
    previous snapshot for any skipped province, so a transient provider outage
    degrades gracefully instead of hanging the refresh.
    """
    results: dict[str, dict] = {}
    chunks = [locations[i:i + CHUNK_SIZE] for i in range(0, len(locations), CHUNK_SIZE)]
    sem = asyncio.Semaphore(max(1, min(settings.FETCH_CONCURRENCY, 4)))

    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        async def grab(chunk: list[dict]) -> bool:
            try:
                results.update(await fetch_open_meteo_batch(client, chunk))
                return True
            except Exception as exc:  # noqa: BLE001
                log.warning("Open-Meteo batch of %d failed: %s", len(chunk), exc)
                return False

        async def worker(chunk: list[dict]):
            async with sem:
                if await grab(chunk):
                    return
                if len(chunk) > 1:  # split once, retry each half
                    mid = len(chunk) // 2
                    for sub in (chunk[:mid], chunk[mid:]):
                        await grab(sub)

        await asyncio.gather(*(worker(c) for c in chunks))

        # --- Fallback: MET Norway for anything Open-Meteo couldn't deliver ---
        missing = [loc for loc in locations if loc["key"] not in results]
        if missing:
            log.warning("Open-Meteo delivered %d/%d; MET Norway fallback for %d province(s).",
                        len(results), len(locations), len(missing))
            sem2 = asyncio.Semaphore(6)

            async def fb(loc: dict):
                async with sem2:
                    try:
                        results[loc["key"]] = await fetch_met_no(client, loc["lat"], loc["lon"])
                    except Exception as exc:  # noqa: BLE001
                        log.warning("MET Norway failed for %s: %s", loc.get("key"), exc)

            await asyncio.gather(*(fb(loc) for loc in missing))
    return results
