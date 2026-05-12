#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "=== Patentis ==="

# Backend
cd "$ROOT/backend"

if [ ! -d ".venv" ]; then
  echo "Creating Python virtual environment…"
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "  !! Created backend/.env — add your GROQ_API_KEY before continuing."
  echo "     Get one free at https://console.groq.com"
  echo ""
  exit 0
fi

# Verify key is set
source .env
if [ -z "$GROQ_API_KEY" ] || [ "$GROQ_API_KEY" = "gsk_..." ]; then
  echo "ERROR: Set GROQ_API_KEY in backend/.env (get one at https://console.groq.com)"
  exit 1
fi

uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
echo "Backend → http://localhost:8000"

# Frontend
cd "$ROOT/frontend"
[ ! -d "node_modules" ] && npm install
npm run dev &
FRONTEND_PID=$!
echo "Frontend → http://localhost:5173"

echo ""
echo "Patentis is ready → http://localhost:5173"
echo "Ctrl+C to stop."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
