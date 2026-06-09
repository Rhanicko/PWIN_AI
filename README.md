# 🛰️ PWIN AI — Philippine Weather Intelligence Network

A next-generation, AI-powered **weather command center for the Philippines**.
Live, province-level weather monitoring with a futuristic, glassmorphism
"mission-control" interface — it tells you **what** weather is happening,
**where**, **when** it started, **when** it may end, **why**, **who** is
affected, and **how severe** it is, for all 17 regions and 82 provinces.

> **Runs out of the box with zero API keys.** It uses the free
> [Open-Meteo](https://open-meteo.com) API, [Leaflet](https://leafletjs.com) +
> free dark map tiles, [RainViewer](https://www.rainviewer.com) radar, and a
> built-in rule-based meteorological AI. Add keys to unlock MySQL, OpenWeatherMap,
> Mapbox and OpenAI.

---

## ✨ Features

| Area | What you get |
|------|--------------|
| **Live map** | Leaflet dark GIS map, province status markers, rain radar, temperature overlay, click-to-inspect popups |
| **Province intelligence** | Temp, feels-like, humidity, wind + direction, gusts, pressure, visibility, UV, cloud, rain status & chance |
| **Event engine** | Classifies thunderstorms, heavy/moderate/light rain, strong winds, heat — with PAGASA-style intensity bands |
| **AI explanations** | Plain-language *what / where / when / why / who / how-severe* + recommended precautions |
| **Affected provinces** | Auto-detected list with severity, risk score, cause, start/end times, impact summary |
| **Alert center** | Heavy rainfall, thunderstorm, flood, landslide, wind, heat and coastal hazard alerts |
| **Forecasts** | 24-hour hourly outlook (chart + strip) and 7-day forecast |
| **Risk scoring** | Composite 0–100 score + flood/landslide/wind/heat/coastal hazard inference |
| **Real-time** | WebSocket push on every refresh, auto-reconnect, last-updated timestamps |
| **Natural language** | "Is it raining in Cebu?" / "Where is it raining?" |
| **National brief** | AI-generated headline + summary of the national weather situation |

---

## 🧱 Tech Stack

- **Frontend:** HTML5, CSS3, modern JS, Tailwind (CDN), Leaflet GL, Chart.js, GSAP
- **Backend:** Python 3.13, FastAPI, Uvicorn, AsyncIO, WebSockets, background scheduler
- **Database:** MySQL 8.x (XAMPP) via SQLAlchemy 2.0 ORM — with automatic SQLite fallback
- **AI/Analytics:** Rule-based meteorological engine (+ optional OpenAI), Pandas/NumPy/scikit-learn ready
- **Data:** Open-Meteo (default), RainViewer radar, OpenWeatherMap/WeatherAPI (optional)

---

## 🚀 Quick Start (zero config)

### Option A — one command

**Windows:**
```bat
run.bat
```
**macOS / Linux:**
```bash
chmod +x run.sh && ./run.sh
```

Then open **http://localhost:8000** 🎉
(The first data refresh of all 82 provinces takes a few seconds — the map
fills in live via WebSocket.)

### Option B — manual

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env        # Windows  (or: cp .env.example .env)

uvicorn app.main:app --reload --port 8000
```

The app serves both the API and the frontend from the same origin, so just
visit `http://localhost:8000`. Interactive API docs: `http://localhost:8000/docs`.

---

## 🐬 Using MySQL with XAMPP (optional but recommended)

By default, if MySQL isn't reachable the app uses a local `backend/pwin_ai.db`
SQLite file so it always boots. To use XAMPP MySQL for durable history:

1. **Start XAMPP** → start the **MySQL** module (Apache not required).
2. Open **phpMyAdmin** → `http://localhost/phpmyadmin`.
3. Create the database + tables: **Import** → choose `database/schema.sql` → **Go**.
   *(Or run `mysql -u root < database/schema.sql`.)*
4. In `backend/.env` set your credentials (XAMPP default is user `root`, empty password):
   ```env
   DB_USER=root
   DB_PASSWORD=
   DB_HOST=127.0.0.1
   DB_PORT=3306
   DB_NAME=pwin_ai
   ```
5. Restart the server. The health endpoint will report `"db_backend": "mysql"`.

> The backend also auto-creates the core tables via SQLAlchemy on first run, so
> importing `schema.sql` is optional — but it adds the full normalised design
> (history per metric, storm tracks, risk records, RBAC, audit logs).

---

## 🔑 Optional upgrades (.env)

| Key | Effect |
|-----|--------|
| `OPENAI_API_KEY` | National brief becomes LLM-authored (else rule-based) |
| `MAPBOX_TOKEN` | Use Mapbox dark style instead of free CARTO tiles |
| `OPENWEATHER_API_KEY` / `WEATHERAPI_KEY` | Reserved hooks for alternate providers |
| `REFRESH_INTERVAL_SECONDS` | How often to refresh (default 600s) |
| `ADMIN_USER` / `ADMIN_PASS` | Admin credentials for the **⟳ Sync** button (default `admin` / `pwin-admin`) |

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Status, DB backend, AI engine, last refresh |
| GET | `/api/config` | Frontend config (center, tokens, engine) |
| GET | `/api/map` | Province markers + national summary |
| GET | `/api/provinces` | Light list of all provinces |
| GET | `/api/province/{name}` | Full intelligence for one province |
| GET | `/api/affected` | Auto-detected affected provinces |
| GET | `/api/alerts` | Active weather alerts |
| GET | `/api/national` | National AI brief |
| GET | `/api/forecast/{name}` | Hourly + 7-day forecast |
| GET | `/api/search?q=` | Search provinces/cities/regions |
| POST | `/api/query` | Natural-language weather question |
| POST | `/api/refresh` | Force refresh (admin token) |
| POST | `/api/auth/login` | Get an admin token |
| WS | `/ws/live` | Live push of refreshes + alerts |

---

## 🗂️ Project Structure

```
wheather forecast philippines/
├── run.bat / run.sh             # one-command launchers
├── README.md
├── database/
│   └── schema.sql               # full MySQL schema (XAMPP-ready)
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   └── app/
│       ├── main.py              # FastAPI app, routes, WebSocket, static
│       ├── config.py            # settings (env-driven)
│       ├── database.py          # engine + MySQL→SQLite fallback
│       ├── models.py            # SQLAlchemy ORM models
│       ├── schemas.py           # Pydantic schemas
│       ├── security.py          # PBKDF2 + HMAC tokens (RBAC)
│       ├── data/ph_locations.py # 17 regions, 82 provinces, cities
│       └── services/
│           ├── weather_client.py  # Open-Meteo async client
│           ├── classifier.py      # event classification rule engine
│           ├── risk.py            # risk scoring + hazard inference
│           ├── ai_explainer.py    # AI/rule-based explanations
│           ├── engine.py          # orchestration pipeline + seeding
│           ├── scheduler.py       # background refresh worker
│           └── state.py           # live state + WebSocket manager
└── frontend/
    ├── index.html               # command-center layout
    ├── css/styles.css           # futuristic glassmorphism theme
    └── js/
        ├── api.js               # API client + WS + utilities
        ├── map.js               # Leaflet map + radar/heat layers
        ├── charts.js            # Chart.js outlook
        └── app.js               # application controller
```

---

## 🧠 How the intelligence works

```
 Open-Meteo (live)  →  classifier  →  risk scorer  →  AI explainer
        │                  │              │               │
   normalised         event type     0-100 score    what/where/when/
   conditions +       + severity +   + flood/land-   why/who/how +
   24h/7d forecast    cause + timing slide/wind/heat precautions
        │                                              │
        └──────────►  engine.refresh_all()  ◄──────────┘
                            │
        persist (MySQL) ◄───┼───► live state ───► WebSocket broadcast ───► UI
```

- **Cause inference** uses Philippine seasonality + geography (Habagat, Amihan,
  ITCZ, shear line, easterlies, LPA, tropical cyclone, local convection).
- **Rainfall intensity** follows PAGASA-style bands (light → torrential).
- **Risk** combines rain intensity, thunder, wind/gusts, heat index, and 24h
  rainfall totals, then derives flood/landslide/wind/heat/coastal hazards.

---

## 🔒 Security notes

- API keys live in `.env` (never commit it).
- Admin actions require an HMAC-signed bearer token (RBAC: admin/operator/viewer).
- Inputs validated via Pydantic / FastAPI; ORM parameterization prevents SQL
  injection; the frontend escapes user/text content.
- For production: set a strong `SECRET_KEY`, real `ADMIN_PASS`, restrict
  `CORS_ORIGINS`, run behind HTTPS, and swap PBKDF2/HMAC for passlib + JWT.

---

## 📜 Data attribution

Weather data © [Open-Meteo](https://open-meteo.com) (CC-BY 4.0), with automatic
failover to © [MET Norway](https://api.met.no) (NLOD/CC-BY 4.0) · Radar ©
[RainViewer](https://www.rainviewer.com) · Map tiles © OpenStreetMap & CARTO ·
Official PH advisories: [PAGASA](https://www.pagasa.dost.gov.ph). PWIN AI is an
analysis/visualization layer — always defer to official PAGASA bulletins for
life-safety decisions.
