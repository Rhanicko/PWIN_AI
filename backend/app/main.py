# -*- coding: utf-8 -*-
"""
PWIN AI — FastAPI application entrypoint.

Serves the REST API, the live WebSocket feed, and the static futuristic frontend.
On startup it ensures the database schema, seeds reference geography, and starts
the background refresh scheduler.

Run:  uvicorn app.main:app --reload   (from the backend/ directory)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .data import ph_locations as geo
from .database import ACTIVE_BACKEND, init_db
from .security import create_token, verify_token
from .services import ai_explainer, analytics, engine
from .services.scheduler import scheduler
from .services.state import manager, state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("pwin")

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

# Pre-built search index (provinces, cities, regions)
SEARCH_INDEX = (
    [{"type": "province", "name": p["name"], "region": geo.region_name(p["region"]),
      "lat": p["lat"], "lon": p["lon"]} for p in geo.PROVINCES]
    + [{"type": "city", "name": c["name"], "province": c["province"],
        "lat": c["lat"], "lon": c["lon"]} for c in geo.CITIES]
    + [{"type": "region", "name": r["name"], "code": r["code"],
        "lat": r["lat"], "lon": r["lon"]} for r in geo.REGIONS]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting %s v%s …", settings.APP_NAME, settings.VERSION)
    try:
        init_db()
        engine.seed_reference_data()
    except Exception as exc:  # noqa: BLE001
        log.warning("DB init/seed issue (continuing): %s", exc)
    scheduler.start()
    yield
    await scheduler.stop()


app = FastAPI(title=settings.APP_NAME, version=settings.VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================================================
#  Helpers
# ===========================================================================
def _ai_engine_label() -> str:
    return "openai" if settings.OPENAI_API_KEY else "rule-engine"


def _require_admin(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    payload = verify_token(authorization.split(" ", 1)[1])
    if not payload or payload.get("role") not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return payload


def _forecast_summary(daily: list[dict]) -> str:
    if not daily:
        return "Forecast data is being prepared."
    wettest = max(daily, key=lambda d: (d.get("precip_prob") or 0))
    tmax = max((d.get("tmax") or -99) for d in daily)
    tmin = min((d.get("tmin") or 99) for d in daily)
    rainy_days = sum(1 for d in daily if (d.get("precip_prob") or 0) >= 50)
    parts = [
        f"Over the next {len(daily)} days, temperatures range {round(tmin)}–{round(tmax)}°C.",
    ]
    if rainy_days:
        parts.append(f"{rainy_days} day(s) carry a high (≥50%) chance of rain, "
                     f"peaking on {wettest.get('date')} ({wettest.get('precip_prob')}%).")
    else:
        parts.append("Mostly dry conditions are expected with low rain chances.")
    return " ".join(parts)


# ===========================================================================
#  API routes
# ===========================================================================
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": settings.VERSION,
        "db_backend": ACTIVE_BACKEND,
        "primary_provider": settings.PRIMARY_PROVIDER,
        "ai_engine": _ai_engine_label(),
        "last_refresh": state.last_refresh,
        "provinces_loaded": len(state.provinces),
        "analytics": analytics.intel.status(),
    }


@app.get("/api/config")
async def config():
    return {
        "app_name": settings.APP_NAME,
        "app_short": settings.APP_SHORT,
        "version": settings.VERSION,
        "mapbox_token": settings.MAPBOX_TOKEN,
        "refresh_interval": settings.REFRESH_INTERVAL_SECONDS,
        "primary_provider": settings.PRIMARY_PROVIDER,
        "ai_engine": _ai_engine_label(),
        "center": geo.PH_CENTER,
    }


@app.get("/api/regions")
async def regions():
    return geo.REGIONS


@app.get("/api/cities")
async def cities():
    return geo.CITIES


@app.get("/api/map")
async def map_data():
    """Markers for every province + national summary (drives the main map)."""
    markers = [engine._map_marker(s) for s in state.provinces.values()]
    return {
        "markers": markers,
        "national": state.national,
        "last_refresh": state.last_refresh,
        "center": geo.PH_CENTER,
    }


@app.get("/api/provinces")
async def provinces():
    """Light list of all provinces with current condition + event summary."""
    out = []
    for s in state.provinces.values():
        c = s["condition"]
        ev = s.get("event") or {}
        out.append({
            "name": s["name"], "region": s["region"], "region_code": s["region_code"],
            "capital": s.get("capital", ""), "lat": s["lat"], "lon": s["lon"],
            "updated_at": s["updated_at"], "source": s["source"],
            "temperature_c": c.get("temperature_c"), "condition_text": c.get("condition_text"),
            "icon": c.get("icon"), "is_raining": c.get("is_raining"),
            "rain_intensity": c.get("rain_intensity"), "affected": s.get("affected", False),
            "severity": ev.get("severity", "info"), "risk_level": ev.get("risk_level", "low"),
            "event_type": ev.get("event_type", "clear"),
        })
    out.sort(key=lambda x: x["name"])
    return {"count": len(out), "provinces": out, "last_refresh": state.last_refresh}


@app.get("/api/province/{name}")
async def province_detail(name: str):
    snap = state.provinces.get(name)
    if not snap:
        # case-insensitive fallback
        for k, v in state.provinces.items():
            if k.lower() == name.lower():
                snap = v
                break
    if not snap:
        raise HTTPException(status_code=404, detail=f"Province '{name}' not found")
    detail = dict(snap)
    detail["forecast_summary"] = _forecast_summary(snap.get("forecast", {}).get("daily", []))
    return detail


@app.get("/api/affected")
async def affected():
    nat = state.national or {}
    return {
        "count": nat.get("provinces_affected", 0),
        "highest_severity": nat.get("highest_severity", "info"),
        "provinces": nat.get("top_affected", []),
        "last_refresh": state.last_refresh,
    }


@app.get("/api/alerts")
async def alerts():
    return {"count": len(state.alerts), "alerts": state.alerts, "last_refresh": state.last_refresh}


@app.get("/api/national")
async def national():
    return state.national or {"headline": "Initializing weather intelligence…",
                              "body": "First data refresh is in progress."}


@app.get("/api/forecast/{name}")
async def forecast(name: str):
    snap = state.provinces.get(name)
    if not snap:
        raise HTTPException(status_code=404, detail=f"Province '{name}' not found")
    fc = snap.get("forecast", {})
    return {
        "province": name,
        "generated_at": snap["updated_at"],
        "hourly": fc.get("hourly", []),
        "daily": fc.get("daily", []),
        "summary": _forecast_summary(fc.get("daily", [])),
    }


@app.get("/api/search")
async def search(q: str = "", limit: int = 12):
    q = q.strip().lower()
    if not q:
        return {"results": []}
    results = [item for item in SEARCH_INDEX if q in item["name"].lower()]
    # province/city matches first
    results.sort(key=lambda i: (i["type"] != "province", i["type"] != "city",
                                not i["name"].lower().startswith(q)))
    return {"results": results[:limit]}


@app.post("/api/query")
async def nl_query(body: dict):
    question = (body or {}).get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required")
    full_index = {name: s for name, s in state.provinces.items()}
    return ai_explainer.answer_question(question, full_index)


@app.post("/api/refresh")
async def manual_refresh(_: dict = Depends(_require_admin)):
    await engine.refresh_all(broadcast=True)
    return {"status": "refreshed", "last_refresh": state.last_refresh}


@app.post("/api/auth/login")
async def login(body: dict):
    """Demo admin login. Default credentials: admin / pwin-admin (change in prod)."""
    username = (body or {}).get("username", "")
    password = (body or {}).get("password", "")
    import os
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASS", "pwin-admin")
    if username == admin_user and password == admin_pass:
        return {"token": create_token(username, role="admin"), "role": "admin"}
    raise HTTPException(status_code=401, detail="Invalid credentials")


# ===========================================================================
#  WebSocket live feed
# ===========================================================================
@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await manager.connect(ws)
    # Push current state immediately on connect
    try:
        await ws.send_json({
            "type": "snapshot",
            "national": state.national,
            "alerts": state.alerts[:50],
            "provinces": [engine._map_marker(s) for s in state.provinces.values()],
            "last_refresh": state.last_refresh,
        })
        while True:
            # Keep the connection alive; ignore inbound except 'ping'
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:  # noqa: BLE001
        await manager.disconnect(ws)


# ===========================================================================
#  Static frontend (mounted LAST so API routes take precedence)
# ===========================================================================
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        return {"app": settings.APP_NAME, "docs": "/docs",
                "note": "Frontend directory not found; API is live."}
