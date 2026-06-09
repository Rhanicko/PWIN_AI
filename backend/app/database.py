"""
Database engine + session management.

Tries MySQL (XAMPP) first using the configured URL. If the connection fails
and USE_SQLITE_FALLBACK is on, it transparently switches to a local SQLite
file so the platform always boots. The active backend is recorded in
``ACTIVE_BACKEND`` for display in the UI / health endpoint.
"""

from __future__ import annotations

import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

log = logging.getLogger("pwin.db")


class Base(DeclarativeBase):
    pass


def _build_engine() -> tuple[Engine, str]:
    """Return (engine, backend_label). Falls back to SQLite if MySQL fails."""
    url = settings.sqlalchemy_url
    try:
        engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_recycle=1800,
            future=True,
        )
        # Probe the connection so we know early whether MySQL is reachable.
        with engine.connect():
            pass
        log.info("Connected to MySQL backend.")
        return engine, "mysql"
    except Exception as exc:  # noqa: BLE001
        if not settings.USE_SQLITE_FALLBACK:
            raise
        log.warning("MySQL unavailable (%s). Falling back to SQLite.", exc)
        engine = create_engine(
            settings.sqlite_url,
            connect_args={"check_same_thread": False},
            future=True,
        )
        return engine, "sqlite"


engine, ACTIVE_BACKEND = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables (idempotent)."""
    from . import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
    log.info("Database tables ensured on %s backend.", ACTIVE_BACKEND)
