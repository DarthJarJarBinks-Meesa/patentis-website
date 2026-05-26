#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "=== Patentis ==="

# Backend
cd "$ROOT/backend"

[ -f ".env" ] && source .env

# Use the venv's uvicorn if it exists, otherwise fall back to PATH
UVICORN=".venv/bin/uvicorn"
[ ! -f "$UVICORN" ] && UVICORN="uvicorn"

$UVICORN main:app --reload --port 8000 &
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
