#!/usr/bin/env bash
# Levanta Vigía en segundo plano: API (Django) + pantalla (Next.js) + monitor AIS.
#
#   bash scripts/levantar.sh              # tráfico REAL (necesita AISSTREAM_API_KEY en backend/.env)
#   bash scripts/levantar.sh --simulado   # tráfico SIMULADO (se rotula «SIM ·»)
#   bash scripts/apagar.sh                # para todo
#
# Ya deben estar corriendo PostgreSQL/PostGIS y Redis (ver el README). Variables opcionales:
#   API_PORT (8001) · WEB_PORT (3001) · PYTHON (por defecto .venv/bin/python)
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$RAIZ/.venv/bin/python}"
API_PORT="${API_PORT:-8001}"
WEB_PORT="${WEB_PORT:-3001}"
RUN="$RAIZ/.run"
mkdir -p "$RUN"

[ -x "$PY" ] || { echo "No encuentro Python en $PY. Crea el entorno: python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt"; exit 1; }
[ -d "$RAIZ/frontend/node_modules" ] || { echo "Faltan las dependencias de la web. Ejecuta: cd frontend && npm install"; exit 1; }
if ls "$RUN"/*.pid >/dev/null 2>&1; then echo "Ya hay procesos registrados en .run/. Ejecuta primero: bash scripts/apagar.sh"; exit 1; fi
redis-cli ping >/dev/null 2>&1 || echo "AVISO: Redis no responde (redis-cli ping). La API y el monitor lo necesitan."

cd "$RAIZ/backend"
echo "Preparando la base de datos…"
"$PY" manage.py migrate --noinput >/dev/null
if [ "$("$PY" manage.py shell -c 'from mares.apps.cables.models import Cable; print(Cable.objects.count())' 2>/dev/null | tail -1)" = "0" ]; then
  echo "Cargando los cables (solo la primera vez, ~20 s)…"
  "$PY" manage.py cargar_cables
fi

# setsid: cada proceso va en su propio grupo, para poder pararlo entero (npm deja procesos hijos).
lanzar() {
  local nombre="$1"; shift
  setsid nohup "$@" > "$RUN/$nombre.log" 2>&1 &
  echo $! > "$RUN/$nombre.pid"
  echo "  ✔ $nombre arriba (PID $!)  ·  registro: .run/$nombre.log"
}

lanzar api "$PY" manage.py runserver "$API_PORT" --noreload
if [ "${1:-}" = "--simulado" ]; then
  lanzar ais-simulado "$PY" manage.py simular_ais --buques 300
elif grep -qE '^AISSTREAM_API_KEY=.+' "$RAIZ/backend/.env" 2>/dev/null || [ -n "${AISSTREAM_API_KEY:-}" ]; then
  lanzar ais "$PY" manage.py monitor_ais
else
  echo "  ⚠ No hay AISSTREAM_API_KEY: sin barcos reales. Usa: bash scripts/levantar.sh --simulado"
fi
cd "$RAIZ/frontend"
NEXT_PUBLIC_API_URL="http://localhost:$API_PORT/api/v1" lanzar web npm run dev -- -p "$WEB_PORT"

echo
echo "Listo. Abre http://localhost:$WEB_PORT  (la primera carga tarda ~15 s; los barcos aparecen al cabo de unos minutos)"
echo "Para parar todo: bash scripts/apagar.sh"
