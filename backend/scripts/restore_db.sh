#!/bin/bash
# Restaura una copia hecha con backup_db.sh en la base indicada.
# Uso:  DATABASE_URL=postgis://... bash scripts/restore_db.sh archivo.dump
# ATENCIÓN: borra y recrea los objetos existentes en esa base. Probar SIEMPRE primero en una base de prueba.
set -euo pipefail
ARCHIVO="${1:?Indique el archivo .dump}"
: "${DATABASE_URL:?Defina DATABASE_URL}"
URL="${DATABASE_URL/#postgis:\/\//postgres://}"

DESTINO=$(echo "${URL%%\?*}" | sed -E 's#(://[^:]+):[^@]*@#\1:***@#')
echo "Se restaurará '$ARCHIVO' sobre: $DESTINO"
read -r -p "Escriba RESTAURAR para continuar: " R
[ "$R" = "RESTAURAR" ] || { echo "Cancelado."; exit 1; }

psql "$URL" -c 'CREATE EXTENSION IF NOT EXISTS postgis;' || echo 'AVISO: no se pudo crear PostGIS; la restauración fallará en las tablas con geometrías.'
pg_restore --clean --if-exists --no-owner --no-privileges --dbname="$URL" "$ARCHIVO"
echo "Restauración terminada. Verifique: python manage.py showmigrations | grep '\[ \]'  y  /health/"
