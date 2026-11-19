#!/bin/bash
# Arranque por rol. En Railway: un servicio por rol con la misma imagen y SERVICE_ROLE distinto.
#   web (por defecto) · worker · beat · ais
set -euo pipefail
cd "$(dirname "$0")"
ROLE="${SERVICE_ROLE:-web}"

case "$ROLE" in
  web)
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
    exec gunicorn mares.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-3}" --timeout 60 \
         --access-logfile - --error-logfile -
    ;;
  worker)
    exec celery -A mares.config.celery worker -l info -Q celery,periodic -c "${WORKER_CONCURRENCY:-3}"
    ;;
  beat)
    exec celery -A mares.config.celery beat -l info
    ;;
  ais)
    exec python manage.py start_aisstream
    ;;
  *)
    echo "SERVICE_ROLE desconocido: $ROLE (web|worker|beat|ais)" >&2
    exit 2
    ;;
esac
