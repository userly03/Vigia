#!/usr/bin/env bash
# BACKEND en UNA terminal: prepara la base de datos y arranca la API (Django) + el monitor de barcos AIS a la vez.
# Ctrl+C para parar los dos.
#
#   bash scripts/backend.sh              # barcos REALES (necesita AISSTREAM_API_KEY en backend/.env)
#   bash scripts/backend.sh --simulado   # barcos SIMULADOS (se rotulan «SIM ·»)
#
# Requisitos ya corriendo: PostgreSQL/PostGIS y Redis (ver el README). Variables opcionales: API_PORT (8001) · PYTHON
set -uo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-$RAIZ/.venv/bin/python}"
API_PORT="${API_PORT:-8001}"

[ -x "$PY" ] || { echo "No encuentro Python en $PY. Crea el entorno: python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt"; exit 1; }
redis-cli ping >/dev/null 2>&1 || echo "AVISO: Redis no responde (redis-cli ping). La API y el monitor lo necesitan."

cd "$RAIZ/backend" || exit 1
echo "Preparando la base de datos…"
"$PY" manage.py migrate --noinput >/dev/null || { echo "No pude migrar: ¿está corriendo PostGIS y es correcta DATABASE_URL en backend/.env?"; exit 1; }
if [ "$("$PY" manage.py shell -c 'from mares.apps.cables.models import Cable; print(Cable.objects.count())' 2>/dev/null | tail -1)" = "0" ]; then
  echo "Cargando los cables (solo la primera vez, ~20 s)…"
  "$PY" manage.py cargar_cables || exit 1
fi

PIDS=()
parar() { echo; echo "Parando API y monitor…"; kill "${PIDS[@]}" 2>/dev/null; wait 2>/dev/null; exit 0; }
trap parar INT TERM

"$PY" manage.py runserver "$API_PORT" --noreload > >(sed -u 's/^/[api] /') 2>&1 &
PIDS+=($!)
if [ "${1:-}" = "--simulado" ]; then
  "$PY" manage.py simular_ais --buques 300 > >(sed -u 's/^/[barcos simulados] /') 2>&1 &
  PIDS+=($!)
elif grep -qE '^AISSTREAM_API_KEY=.+' "$RAIZ/backend/.env" 2>/dev/null || [ -n "${AISSTREAM_API_KEY:-}" ]; then
  "$PY" manage.py monitor_ais > >(sed -u 's/^/[barcos] /') 2>&1 &
  PIDS+=($!)
else
  echo "⚠ No hay AISSTREAM_API_KEY: sin barcos reales. Usa: bash scripts/backend.sh --simulado"
fi

echo "Backend arriba: API en http://localhost:$API_PORT  ·  Ctrl+C para parar todo."
wait
