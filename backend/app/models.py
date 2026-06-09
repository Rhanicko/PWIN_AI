"""
SQLAlchemy ORM models.

These mirror the relational schema in ``database/schema.sql``. The core tables
power the live platform; the schema file additionally documents the full
normalised design (rainfall_records, storm_tracks, risk records, RBAC, etc.).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)

    provinces: Mapped[list["Province"]] = relationship(back_populates="region")


class Province(Base):
    __tablename__ = "provinces"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    capital: Mapped[str] = mapped_column(String(128), default="")
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)

    region: Mapped["Region"] = relationship(back_populates="provinces")
    cities: Mapped[list["City"]] = relationship(back_populates="province")
    readings: Mapped[list["WeatherReading"]] = relationship(back_populates="province")


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    province_id: Mapped[int] = mapped_column(ForeignKey("provinces.id"), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)

    province: Mapped["Province"] = relationship(back_populates="cities")


class WeatherStation(Base):
    __tablename__ = "weather_stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    province_id: Mapped[int] = mapped_column(ForeignKey("provinces.id"), index=True)
    source: Mapped[str] = mapped_column(String(64), default="open-meteo")
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)


class WeatherReading(Base):
    """A point-in-time snapshot of current conditions for a province."""

    __tablename__ = "weather_readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    province_id: Mapped[int] = mapped_column(ForeignKey("provinces.id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
    source: Mapped[str] = mapped_column(String(64), default="open-meteo")

    temperature_c: Mapped[float | None] = mapped_column(Float)
    feels_like_c: Mapped[float | None] = mapped_column(Float)
    humidity_pct: Mapped[float | None] = mapped_column(Float)
    wind_speed_kmh: Mapped[float | None] = mapped_column(Float)
    wind_dir_deg: Mapped[float | None] = mapped_column(Float)
    wind_gust_kmh: Mapped[float | None] = mapped_column(Float)
    pressure_hpa: Mapped[float | None] = mapped_column(Float)
    visibility_km: Mapped[float | None] = mapped_column(Float)
    uv_index: Mapped[float | None] = mapped_column(Float)
    cloud_cover_pct: Mapped[float | None] = mapped_column(Float)
    precip_mm: Mapped[float | None] = mapped_column(Float)
    precip_prob_pct: Mapped[float | None] = mapped_column(Float)
    condition_code: Mapped[int | None] = mapped_column(Integer)
    condition_text: Mapped[str | None] = mapped_column(String(128))
    is_raining: Mapped[bool] = mapped_column(Boolean, default=False)

    province: Mapped["Province"] = relationship(back_populates="readings")

    __table_args__ = (
        Index("ix_reading_province_time", "province_id", "observed_at"),
    )


class WeatherForecast(Base):
    """Hourly/daily forecast rows stored as a JSON snapshot per province."""

    __tablename__ = "weather_forecasts"

    id: Mapped[int] = mapped_column(primary_key=True)
    province_id: Mapped[int] = mapped_column(ForeignKey("provinces.id"), index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="daily")  # hourly|daily
    horizon_days: Mapped[int] = mapped_column(Integer, default=7)
    payload: Mapped[dict] = mapped_column(JSON)


class WeatherEvent(Base):
    """A classified weather event affecting a province (e.g. heavy rain)."""

    __tablename__ = "weather_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    province_id: Mapped[int] = mapped_column(ForeignKey("provinces.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)  # info|advisory|watch|warning|critical
    cause: Mapped[str] = mapped_column(String(128), default="")
    rain_intensity: Mapped[str] = mapped_column(String(32), default="none")
    risk_level: Mapped[str] = mapped_column(String(32), default="low")
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.6)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    expected_end: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    summary: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class WeatherAlert(Base):
    __tablename__ = "weather_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    province_id: Mapped[int | None] = mapped_column(ForeignKey("provinces.id"), index=True)
    areas: Mapped[dict] = mapped_column(JSON, default=dict)  # provinces/cities affected
    reason: Mapped[str] = mapped_column(Text, default="")
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(64), default="PWIN AI")
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class AIReport(Base):
    __tablename__ = "ai_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(32), default="national")  # national|region|province
    scope_ref: Mapped[str] = mapped_column(String(128), default="PH")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
    engine: Mapped[str] = mapped_column(String(32), default="rule-engine")  # rule-engine|openai
    headline: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text, default="")


class AIEventExplanation(Base):
    __tablename__ = "ai_event_explanations"

    id: Mapped[int] = mapped_column(primary_key=True)
    province_id: Mapped[int] = mapped_column(ForeignKey("provinces.id"), index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    engine: Mapped[str] = mapped_column(String(32), default="rule-engine")
    what: Mapped[str] = mapped_column(Text, default="")
    where: Mapped[str] = mapped_column(Text, default="")
    when_started: Mapped[str] = mapped_column(String(255), default="")
    when_end: Mapped[str] = mapped_column(String(255), default="")
    why: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(32), default="info")
    confidence: Mapped[float] = mapped_column(Float, default=0.6)
    precautions: Mapped[dict] = mapped_column(JSON, default=list)


# --- Auth / audit (RBAC) ----------------------------------------------------
class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(128))
    detail: Mapped[str] = mapped_column(Text, default="")
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
