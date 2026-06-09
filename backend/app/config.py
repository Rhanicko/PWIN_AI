"""
Centralised configuration. Reads from environment / .env file.

The platform is designed to run *out of the box*:
  * No weather API key required  -> uses Open-Meteo (free, no auth).
  * No database configured        -> falls back to a local SQLite file.
  * No OpenAI key                 -> uses the built-in rule-based explainer.
Add keys in .env to unlock OpenWeatherMap, MySQL/XAMPP and OpenAI.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv optional
    pass

BASE_DIR = Path(__file__).resolve().parent.parent  # .../backend


def _bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # --- App ---------------------------------------------------------------
    APP_NAME: str = "Philippine Weather Intelligence Network"
    APP_SHORT: str = "PWIN AI"
    VERSION: str = "1.0.0"
    DEBUG: bool = _bool("DEBUG", True)

    # --- Server ------------------------------------------------------------
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # --- Database ----------------------------------------------------------
    # Example MySQL (XAMPP): mysql+pymysql://root:@127.0.0.1:3306/pwin_ai
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT: str = os.getenv("DB_PORT", "3306")
    DB_NAME: str = os.getenv("DB_NAME", "pwin_ai")
    # If set, this wins. Otherwise we build a MySQL URL, and main.py will fall
    # back to SQLite automatically if MySQL is unreachable.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    USE_SQLITE_FALLBACK: bool = _bool("USE_SQLITE_FALLBACK", True)
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", str(BASE_DIR / "pwin_ai.db"))

    # --- Weather data providers -------------------------------------------
    # Open-Meteo needs no key. Others are optional upgrades.
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")
    WEATHERAPI_KEY: str = os.getenv("WEATHERAPI_KEY", "")
    PRIMARY_PROVIDER: str = os.getenv("PRIMARY_PROVIDER", "open-meteo")

    # --- AI ----------------------------------------------------------------
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # --- Map / frontend ----------------------------------------------------
    MAPBOX_TOKEN: str = os.getenv("MAPBOX_TOKEN", "")  # optional; Leaflet used otherwise

    # --- Scheduler ---------------------------------------------------------
    REFRESH_INTERVAL_SECONDS: int = int(os.getenv("REFRESH_INTERVAL_SECONDS", "300"))
    # Limit concurrent outbound weather requests to be a good API citizen
    FETCH_CONCURRENCY: int = int(os.getenv("FETCH_CONCURRENCY", "8"))

    # --- Security ----------------------------------------------------------
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "720"))
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")

    @property
    def sqlalchemy_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        pwd = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
        return (
            f"mysql+pymysql://{self.DB_USER}{pwd}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            "?charset=utf8mb4"
        )

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{self.SQLITE_PATH}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
