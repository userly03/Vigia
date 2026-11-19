"""
Monitor de AIS en vivo (AISstream, estaciones terrestres): deja la última posición de cada barco en Redis y,
muestreada cada ~10 min, en la tabla de historial. Es la entrada de datos del Guardián.
"""
import logging
import time

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('mares.detection.tasks')

_AISSTREAM_WS_URL = 'wss://stream.aisstream.io/v0/stream'
_AIS_TTL_SECONDS = 900  # 15 minutos
_AIS_INDEX_KEY = 'ais:live:mmsi_index'
_AIS_CACHE_KEY_PREFIX = 'ais:live:'
_BACKOFF_INITIAL = 1.0
_BACKOFF_MAX = 60.0
_POSITIONS_PER_LOG = 25
_AIS_MONITOR_NO_LIMIT_SEC = 10 * 365 * 24 * 3600  # ~10 años


@shared_task(
    bind=True,
    name='mares.detection.monitor_aisstream',
    max_retries=None,
    acks_late=True,
    ignore_result=True,
    # None no desactiva el límite: Celery cae al global (CELERY_TASK_SOFT_TIME_LIMIT=270 s) y
    # mataba el monitor cada ~4,5 min. Se fija un valor efectivamente infinito.
    time_limit=_AIS_MONITOR_NO_LIMIT_SEC,
    soft_time_limit=_AIS_MONITOR_NO_LIMIT_SEC,
)
def monitor_aisstream(self) -> None:
    """
    Worker permanente que mantiene conexión WebSocket a AISstream.
    Almacena posiciones AIS en Redis con TTL 15 min.
    Reconexión automática con backoff exponencial 1s→2s→4s→8s→max 60s.
    """
    import asyncio

    api_key = getattr(settings, 'AISSTREAM_API_KEY', '').strip()
    if not api_key:
        logger.warning(
            'AISSTREAM_API_KEY no configurada — monitor_aisstream no iniciado. '
            'Configure settings.AISSTREAM_API_KEY para activar AIS en tiempo real.'
        )
        return

    logger.info('monitor_aisstream iniciando | task_id=%s', self.request.id)

    try:
        asyncio.run(_run_aisstream_loop(api_key))
    except Exception as exc:
        logger.error('monitor_aisstream error fatal | error=%s', exc, exc_info=True)
        raise self.retry(countdown=60, exc=exc)


async def _run_aisstream_loop(api_key: str) -> None:
    """Bucle principal con reconexión exponencial. Corre hasta que el proceso termine."""
    import asyncio
    import json

    try:
        import websockets
    except ImportError:
        logger.error(
            'websockets no instalado — instalar con: pip install websockets. '
            'monitor_aisstream no puede continuar.'
        )
        return

    backoff = _BACKOFF_INITIAL
    positions_received = 0
    connect_count = 0

    while True:
        connect_count += 1
        logger.info(
            'AISstream conectando | intento=%d | url=%s',
            connect_count, _AISSTREAM_WS_URL,
        )
        try:
            async with websockets.connect(
                _AISSTREAM_WS_URL,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                subscribe_msg = json.dumps({
                    'APIKey': api_key,
                    'BoundingBoxes': list(settings.AISSTREAM_BOUNDING_BOXES),
                    'FiltersShipMMSI': [],
                    'FilterMessageTypes': ['PositionReport'],
                })
                await ws.send(subscribe_msg)
                backoff = _BACKOFF_INITIAL
                logger.info('AISstream conectado y suscrito | intento=%d', connect_count)

                async for raw_message in ws:
                    try:
                        message = json.loads(raw_message)
                        if positions_received < 3:
                            logger.info(
                                'AISstream primer mensaje #%d | type=%s | keys=%s',
                                positions_received + 1,
                                message.get('MessageType', 'unknown'),
                                sorted(message.keys()),
                            )
                        await _process_ais_message(message)
                        positions_received += 1
                        if positions_received % _POSITIONS_PER_LOG == 0:
                            logger.info(
                                'AISstream posiciones recibidas | total=%d | uptime_intento=%d',
                                positions_received, connect_count,
                            )
                    except json.JSONDecodeError as exc:
                        logger.warning('AISstream parse error | error=%s', exc)
                    except Exception as exc:
                        logger.error(
                            'AISstream procesar mensaje error | error=%s',
                            exc, exc_info=True,
                        )

        except Exception as exc:
            logger.error(
                'AISstream desconectado | intento=%d | error=%s | backoff=%.1fs',
                connect_count, exc, backoff,
            )

        if connect_count % 10 == 0:
            logger.warning(
                'AISstream lleva %d reconexiones consecutivas — '
                'verificar API key, conectividad o estado del servicio en stream.aisstream.io',
                connect_count,
            )

        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, _BACKOFF_MAX)


def _normalize_ais_timestamp(raw: str | None) -> str:
    """Convert AISstream Go-format timestamp to ISO 8601 for JS Date() compatibility.

    AISstream sends: "2026-06-26 17:05:37.208460848 +0000 UTC"
    We return:       "2026-06-26T17:05:37.208Z"
    """
    import re
    if not raw:
        return timezone.now().isoformat()
    try:
        clean = re.sub(r'\s+UTC$', '', raw.strip())       # remove trailing " UTC"
        clean = re.sub(r'\s*\+00:?00', 'Z', clean)        # " +0000" or " +00:00" → "Z"
        clean = clean.replace(' ', 'T', 1)                 # space between date and time → T
        clean = re.sub(r'(\.\d{3})\d+', r'\1', clean)    # truncate nanoseconds → ms
        return clean
    except Exception:
        return timezone.now().isoformat()


# Índice de MMSI vistos. Antes se leía, ampliaba y reescribía en CADA mensaje (O(N) por mensaje) y nunca se
# podaba, de modo que con zonas de miles de buques era inviable y crecía sin límite. Ahora: un MMSI nuevo se añade
# al índice de Redis; el resto sólo actualiza su posición, y cada _INDICE_CADA_S segundos el índice se reescribe
# con los vistos en los últimos _AIS_TTL_SECONDS (así se poda y se renueva su caducidad).
_VISTOS: dict[str, float] = {}
_INDICE_CADA_S = 60.0
_ultimo_indice: float | None = None


def _actualizar_indice(cache, mmsi: str) -> None:
    import json

    global _ultimo_indice
    ahora = time.monotonic()
    nuevo = mmsi not in _VISTOS
    _VISTOS[mmsi] = ahora
    if _ultimo_indice is None:
        _ultimo_indice = ahora

    if ahora - _ultimo_indice >= _INDICE_CADA_S:
        # Poda: sólo los vistos en los últimos _AIS_TTL_SECONDS (sus posiciones en Redis aún no caducaron).
        for m in [m for m, t in _VISTOS.items() if ahora - t > _AIS_TTL_SECONDS]:
            del _VISTOS[m]
        # Se conservan también los MMSI del índice previo cuya posición sigue en Redis (aunque los haya escrito
        # otro proceso): así dos escritores no se pisan, y lo que ya caducó se poda.
        actual = cache.get(_AIS_INDEX_KEY)
        previos = set(json.loads(actual) if isinstance(actual, str) else (actual or []))
        vivos = set(_VISTOS)
        if previos - vivos:
            existentes = cache.get_many([f'{_AIS_CACHE_KEY_PREFIX}{m}' for m in previos - vivos])
            vivos |= {m for m in previos - vivos if f'{_AIS_CACHE_KEY_PREFIX}{m}' in existentes}
        cache.set(_AIS_INDEX_KEY, json.dumps(list(vivos)), _AIS_TTL_SECONDS)
        _ultimo_indice = ahora
    elif nuevo:
        actual = cache.get(_AIS_INDEX_KEY)
        conjunto = set(json.loads(actual) if isinstance(actual, str) else (actual or []))
        conjunto.add(mmsi)
        cache.set(_AIS_INDEX_KEY, json.dumps(list(conjunto)), _AIS_TTL_SECONDS)


async def _process_ais_message(message: dict) -> None:
    """Almacena posición AIS en Redis y detecta GAP si no hay señal >2h."""
    import json
    from django.core.cache import cache

    msg_type = message.get('MessageType', '')
    if msg_type != 'PositionReport':
        return

    meta = message.get('MetaData', {})
    pos_report = message.get('Message', {}).get('PositionReport', {})

    mmsi = str(meta.get('MMSI', '')).strip()
    if not mmsi:
        return

    lat = pos_report.get('Latitude')
    lng = pos_report.get('Longitude')
    if lat is None or lng is None:
        return

    vessel_name = meta.get('ShipName', '').strip()
    timestamp = _normalize_ais_timestamp(meta.get('time_utc'))

    position_data = {
        'mmsi': mmsi,
        'vessel_name': vessel_name,
        'lat': float(lat),
        'lng': float(lng),
        'timestamp': timestamp,
        'velocidad_nudos': pos_report.get('Sog'),
        'rumbo': pos_report.get('Cog'),
        'nav': pos_report.get('NavigationalStatus'),
        'bandera': '',
    }

    cache_key = f'{_AIS_CACHE_KEY_PREFIX}{mmsi}'
    position_json = json.dumps(position_data)
    cache.set(cache_key, position_json, _AIS_TTL_SECONDS)

    _actualizar_indice(cache, mmsi)

    await _persist_ais_history(position_data)


async def _persist_ais_history(position_data: dict) -> None:
    """Muestrea y guarda historial AIS por lotes. Nunca propaga errores al monitor."""
    import asyncio
    from mares.apps.detection import ais_history

    try:
        ais_history.record_position(position_data)
        if ais_history.should_flush():
            await asyncio.to_thread(ais_history.flush)
    except Exception as exc:
        logger.error('Historial AIS error | error=%s', exc)


@shared_task(name='mares.detection.purge_ais_history', ignore_result=True)
def purge_ais_history() -> int:
    """Elimina posiciones AIS fuera de la ventana de retención."""
    from mares.apps.detection import ais_history

    deleted = ais_history.purge_old()
    logger.info('purge_ais_history | eliminadas=%d', deleted)
    return deleted
