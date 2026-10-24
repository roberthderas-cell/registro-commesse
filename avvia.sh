#!/usr/bin/env bash
# Avvia backend (porta 8000) e frontend (porta 5173) in sviluppo. Ctrl+C li ferma entrambi.
set -e
cd "$(dirname "$0")"
if [ ! -d backend/.venv ]; then
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -r backend/requirements-dev.txt
fi
[ -d frontend/node_modules ] || npm --prefix frontend install
[ -f backend/fonti.yaml ] || cp backend/fonti.example.yaml backend/fonti.yaml
[ -f backend/data/erp_demo.db ] || (cd backend && .venv/bin/python scripts/crea_erp_demo.py)
trap 'kill 0' EXIT
(cd backend && .venv/bin/uvicorn app.main:app --port 8000 --reload --reload-dir app) &
npm --prefix frontend run dev -- --host 127.0.0.1 &
sleep 3
echo
echo "  Registro Commesse:  http://127.0.0.1:5173"
echo "  Documentazione API: http://127.0.0.1:8000/docs"
echo
wait
