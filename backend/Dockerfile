# MARES — imagen única para web, worker, beat y monitor AIS (el rol se elige con SERVICE_ROLE, ver start.sh).
# Construir desde backend/:  docker build -t mares-backend .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1

# GEOS del sistema (GeoDjango lo carga con find_library). GDAL NO se instala: settings/base.py usa el que trae pyogrio
# dentro de ../.venv relativo a backend/, por eso el entorno virtual vive en /app/.venv.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libgeos-dev curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app/backend
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN chmod +x start.sh && mkdir -p mares/storage logs

ENV DJANGO_SETTINGS_MODULE=mares.config.settings.production
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s CMD curl -fsS "http://localhost:${PORT:-8000}/health/" || exit 1
CMD ["./start.sh"]
