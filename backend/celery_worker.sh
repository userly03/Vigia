#!/bin/bash
# Celery workers para MARES
# Uso:
#   bash celery_worker.sh            — worker general (simulaciones + tasks periódicas)
#   bash celery_worker.sh beat       — beat scheduler (tareas periódicas)
#   bash celery_worker.sh aisstream  — monitor AISstream permanente (WebSocket)

cd "$(dirname "$0")"
source ../.venv/bin/activate
export $(cat .env | grep -v '^#' | xargs)
export DJANGO_SETTINGS_MODULE=mares.config.settings.development

MODE="${1:-worker}"

case "$MODE" in
  beat)
    echo "Iniciando Celery Beat..."
    celery -A mares.config.celery beat --loglevel=info
    ;;
  aisstream)
    echo "Iniciando monitor AISstream (permanente)..."
    python manage.py start_aisstream
    ;;
  *)
    echo "Iniciando Celery Worker (celery + periodic)..."
    celery -A mares.config.celery worker --loglevel=info -Q celery,periodic
    ;;
esac
