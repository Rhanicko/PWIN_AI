#!/usr/bin/env bash
# ============================================================
#  PWIN AI - one-command launcher (macOS / Linux)
# ============================================================
set -e
cd "$(dirname "$0")/backend"

if [ ! -d ".venv" ]; then
  echo "[PWIN] Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

# Force UTF-8 so weather text (em-dashes, °, etc.) renders correctly
# regardless of the system locale.
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

echo "[PWIN] Installing dependencies..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "[PWIN] Creating .env from template..."
  cp .env.example .env
fi

echo ""
echo "[PWIN] Starting server at http://localhost:8090"
echo "[PWIN] Press CTRL+C to stop."
echo ""
python -m uvicorn app.main:app --host 0.0.0.0 --port 8090 --reload
