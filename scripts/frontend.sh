#!/usr/bin/env bash
# FRONTEND (la pantalla) en una terminal. Ctrl+C para parar.
#
#   bash scripts/frontend.sh
#
# Variables opcionales: API_PORT (8001, donde corre el backend) · WEB_PORT (3001)
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
API_PORT="${API_PORT:-8001}"
WEB_PORT="${WEB_PORT:-3001}"

cd "$RAIZ/frontend"
[ -d node_modules ] || { echo "Instalando dependencias de la web (solo la primera vez)…"; npm install; }
echo "Pantalla: http://localhost:$WEB_PORT  (la primera carga tarda ~15 s)  ·  Ctrl+C para parar."
NEXT_PUBLIC_API_URL="http://localhost:$API_PORT/api/v1" exec npm run dev -- -p "$WEB_PORT"
