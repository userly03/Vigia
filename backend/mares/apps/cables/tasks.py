"""Tarea periódica que mantiene tibia la respuesta de /api/v1/cables/buques/ (sin ella, la primera visita tarda ~10 s)."""
import logging

from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger('mares.cables')

# La tarea corre cada INTERVALO_S segundos y deja la respuesta TTL_S segundos: si la tarea muere, la caché caduca
# sola y la vista vuelve a calcular bajo demanda (más lento, pero sin datos viejos).
INTERVALO_S = 15
TTL_S = 45


@shared_task(name='mares.cables.precalentar_buques')
def precalentar_buques() -> int | None:
    from .views import BuquesView
    # Cerrojo: si una pasada anterior sigue calculando (tráfico grande, API lenta), esta no se apila detrás de ella.
    if not cache.add('cables:precalentando', 1, 60):
        logger.info('Precalentado omitido: la pasada anterior sigue en curso')
        return None
    try:
        data = BuquesView.refrescar(TTL_S)
    finally:
        cache.delete('cables:precalentando')
    logger.info('Buques precalentados | total=%s | en_corredor=%s', data['meta']['total'], data['meta']['en_corredor'])
    return data['meta']['total']


@shared_task(name='mares.cables.sellar_alertas')
def sellar_alertas() -> str | None:
    """Cada hora: sella las alertas reales del momento (usa la respuesta en caché si está fresca)."""
    from .sellos import sellar
    from .views import BuquesView
    data = cache.get('cables:buques') or BuquesView.refrescar(TTL_S)
    s = sellar(data)
    logger.info('Sello creado | hash=%s | alertas=%d', s.hash[:12], len(s.contenido['alertas']))
    return s.hash
