#!/bin/bash
# Copia de seguridad de la base de datos de MARES (formato custom de pg_dump, comprimido).
#
# Uso:   DATABASE_URL=postgis://usuario:clave@host:5432/base  bash scripts/backup_db.sh [directorio] [dias_de_retencion]
# Por defecto: ./backups, 14 días. El cliente pg_dump debe ser de versión >= la del servidor.
# Programarlo (cron / servicio cron de Railway), p. ej. cada día 03:00:   0 3 * * *  bash scripts/backup_db.sh
# Copiar el archivo FUERA del servidor (S3/Drive/otro proveedor): una copia en la misma máquina no protege de perderla.
set -euo pipefail

DEST="${1:-./backups}"
RETENCION_DIAS="${2:-14}"
: "${DATABASE_URL:?Defina DATABASE_URL}"

# pg_dump no entiende el esquema postgis://
URL="${DATABASE_URL/#postgis:\/\//postgres://}"
mkdir -p "$DEST"
ARCHIVO="$DEST/mares_$(date -u +%Y%m%dT%H%M%SZ).dump"

pg_dump --format=custom --compress=6 --no-owner --no-privileges --file="$ARCHIVO" "$URL"

# Verificación mínima: el archivo debe ser legible y no estar vacío
pg_restore --list "$ARCHIVO" > /dev/null
TAM=$(stat -c %s "$ARCHIVO" 2>/dev/null || stat -f %z "$ARCHIVO")
if [ "$TAM" -lt 1024 ]; then
  echo "ERROR: la copia pesa $TAM bytes, parece vacía" >&2
  exit 1
fi
echo "OK $ARCHIVO ($TAM bytes)"

# Retención
find "$DEST" -name 'mares_*.dump' -type f -mtime +"$RETENCION_DIAS" -print -delete
