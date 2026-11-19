"""
Persistencia del historial AIS.

monitor_aisstream recibe decenas de mensajes por segundo; escribir cada uno a Postgres
sería inviable y poco útil. Aquí se muestrea (1 posición por barco cada
AIS_HISTORY_INTERVAL_SECONDS), se acumula en memoria y se vuelca por lotes.
La persistencia nunca debe tumbar el monitor: cualquier error se registra y se descarta.
"""
import logging
import time
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.contrib.gis.geos import Point
from django.utils import timezone

logger = logging.getLogger('mares.detection.ais_history')

_MAX_BUFFER = 5000  # tope de seguridad si la BD está caída
_BUFFER: list[dict] = []
_LAST_SAVED: dict[str, float] = {}
_last_flush = time.monotonic()


def _interval() -> int:
    return getattr(settings, 'AIS_HISTORY_INTERVAL_SECONDS', 600)


def _batch_size() -> int:
    return getattr(settings, 'AIS_HISTORY_BATCH_SIZE', 200)


def _flush_every() -> int:
    return getattr(settings, 'AIS_HISTORY_FLUSH_SECONDS', 60)


def _parse_ts(iso: str | None) -> datetime:
    try:
        dt = datetime.fromisoformat(iso.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dt_timezone.utc)
        return dt
    except Exception:
        return timezone.now()


def record_position(position: dict) -> bool:
    """
    Encola la posición si ya pasó el intervalo de muestreo para ese MMSI.
    Devuelve True si se encoló. No toca la BD.
    """
    mmsi = position.get('mmsi')
    lat, lng = position.get('lat'), position.get('lng')
    if not mmsi or lat is None or lng is None:
        return False
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return False

    now = time.monotonic()
    last = _LAST_SAVED.get(mmsi)
    if last is not None and now - last < _interval():
        return False
    _LAST_SAVED[mmsi] = now

    if len(_BUFFER) >= _MAX_BUFFER:
        _BUFFER.pop(0)
    _BUFFER.append(position)
    return True


def should_flush() -> bool:
    if not _BUFFER:
        return False
    return len(_BUFFER) >= _batch_size() or time.monotonic() - _last_flush >= _flush_every()


def flush() -> int:
    """Vuelca el buffer a la BD (síncrono). Devuelve filas escritas; ante error conserva el buffer."""
    global _last_flush
    from mares.apps.detection.models import AISPosicion

    _last_flush = time.monotonic()
    if not _BUFFER:
        return 0
    rows = list(_BUFFER)
    try:
        AISPosicion.objects.bulk_create([
            AISPosicion(
                mmsi=p['mmsi'],
                vessel_name=(p.get('vessel_name') or '')[:100],
                posicion=Point(float(p['lng']), float(p['lat']), srid=4326),
                timestamp=_parse_ts(p.get('timestamp')),
                velocidad_nudos=p.get('velocidad_nudos'),
                rumbo=p.get('rumbo'),
                nav=p.get('nav'),
            )
            for p in rows
        ])
    except Exception as exc:
        logger.error('No se pudo guardar historial AIS (%d filas) | error=%s', len(rows), exc)
        return 0
    del _BUFFER[:len(rows)]
    return len(rows)


def purge_old(retention_days: int | None = None) -> int:
    """Borra posiciones más viejas que la retención. Devuelve filas eliminadas."""
    from mares.apps.detection.models import AISPosicion

    days = retention_days or getattr(settings, 'AIS_HISTORY_RETENTION_DAYS', 60)
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = AISPosicion.objects.filter(timestamp__lt=cutoff).delete()
    return deleted
