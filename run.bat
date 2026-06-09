@echo off
REM ============================================================
REM  PWIN AI - one-command launcher (Windows)
REM  Creates a venv, installs deps, and starts the server.
REM ============================================================
setlocal

cd /d "%~dp0backend"

if not exist ".venv" (
    echo [PWIN] Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

REM Force UTF-8 so weather text (em-dashes, °, etc.) renders correctly
REM regardless of the Windows system locale (avoids cp1252 mojibake).
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo [PWIN] Installing dependencies...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt

if not exist ".env" (
    echo [PWIN] Creating .env from template...
    copy .env.example .env >nul
)

echo.
echo [PWIN] Starting server at http://localhost:8090
echo [PWIN] Press CTRL+C to stop.
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8090 --reload

endlocal
