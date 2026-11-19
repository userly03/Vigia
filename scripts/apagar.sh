#!/usr/bin/env bash
# Para lo que arrancó scripts/levantar.sh (cada proceso con su grupo, sin usar pkill).
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$RAIZ/.run"
hubo=0
for f in "$RUN"/*.pid; do
  [ -e "$f" ] || continue
  hubo=1
  pid="$(cat "$f")"
  if kill -0 "$pid" 2>/dev/null; then kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null; echo "  ✔ parado $(basename "$f" .pid) (PID $pid)"
  else echo "  · $(basename "$f" .pid) ya no estaba corriendo"; fi
  rm -f "$f"
done
[ "$hubo" = 1 ] || echo "No había nada registrado en .run/."
