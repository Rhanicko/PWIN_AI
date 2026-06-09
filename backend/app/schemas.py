"""Pydantic schemas for API request/response validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class RegionOut(BaseModel):
    code: str
    name: str
    lat: float
    lon: float


class ConditionOut(BaseModel):
    temperature_c: Optional[float] = None
    feels_like_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    wind_dir_deg: Optional[float] = None
    wind_dir_label: Optional[str] = None
    wind_gust_kmh: Optional[float] = None
    pressure_hpa: Optional[float] = None
    visibility_km: Optional[float] = None
    uv_index: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    precip_mm: Optional[float] = None
    precip_prob_pct: Optional[float] = None
    condition_code: Optional[int] = None
    condition_text: Optional[str] = None
    is_raining: bool = False
    rain_intensity: str = "none"


class EventOut(BaseModel):
    event_type: str
    severity: str
    cause: str
    rain_intensity: str
    risk_level: str
    risk_score: float
    confidence: float
    started_at: Optional[str] = None
    expected_end: Optional[str] = None
    summary: str = ""


class ExplanationOut(BaseModel):
    what: str
    where: str
    when_started: str
    when_end: str
    why: str
    who: str = ""
    how_severe: str = ""
    severity: str
    confidence: float
    precautions: list[str] = []
    engine: str = "rule-engine"


class ProvinceWeatherOut(BaseModel):
    id: Optional[int] = None
    name: str
    region: str
    region_code: str
    capital: str = ""
    lat: float
    lon: float
    updated_at: Optional[str] = None
    source: str = "open-meteo"
    condition: ConditionOut
    event: Optional[EventOut] = None
    alerts: list[str] = []


class AffectedProvinceOut(BaseModel):
    name: str
    region: str
    region_code: str
    lat: float
    lon: float
    event_type: str
    severity: str
    rain_intensity: str
    risk_level: str
    risk_score: float
    cause: str
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    expected_end: Optional[str] = None
    impact_summary: str
    affected_areas: list[str] = []


class AlertOut(BaseModel):
    id: Optional[int] = None
    title: str
    category: str
    severity: str
    province: Optional[str] = None
    region: Optional[str] = None
    areas: list[str] = []
    reason: str
    recommended_action: str
    issued_at: Optional[str] = None
    expires_at: Optional[str] = None
    source: str = "PWIN AI"


class ForecastOut(BaseModel):
    province: str
    generated_at: str
    hourly: list[dict[str, Any]] = []
    daily: list[dict[str, Any]] = []
    summary: str = ""


class NationalSummaryOut(BaseModel):
    generated_at: str
    provinces_total: int
    provinces_raining: int
    provinces_affected: int
    active_alerts: int
    highest_severity: str
    avg_temp_c: Optional[float] = None
    headline: str
    body: str
    engine: str
    top_affected: list[AffectedProvinceOut] = []


class HealthOut(BaseModel):
    status: str
    version: str
    db_backend: str
    primary_provider: str
    ai_engine: str
    last_refresh: Optional[str] = None
    provinces_loaded: int


class NLQueryIn(BaseModel):
    question: str


class NLQueryOut(BaseModel):
    question: str
    answer: str
    engine: str
    matched_provinces: list[str] = []
