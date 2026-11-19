"""Historial de posiciones AIS (la memoria que necesitan las capas del Guardián: pistas, replay, zonas habituales)."""
import logging

from django.contrib.gis.db import models as gis_models
from django.db import models

logger = logging.getLogger('mares.detection')


class AISPosicion(models.Model):
    """
    Historial de posiciones AIS muestreadas (una por barco cada AIS_HISTORY_INTERVAL_SECONDS).

    Es la materia prima de la prueba de deriva, los recorridos, el replay y las zonas habituales. No se puede
    reconstruir hacia atrás: lo que no se guarda hoy se pierde. Se purga pasados AIS_HISTORY_RETENTION_DAYS días.
    """

    id = models.BigAutoField(primary_key=True)
    mmsi = models.CharField(max_length=15)
    vessel_name = models.CharField(max_length=100, blank=True, default='')
    posicion = gis_models.PointField(srid=4326)
    timestamp = models.DateTimeField(help_text='Instante de la posición según AIS (UTC)')
    velocidad_nudos = models.FloatField(null=True, blank=True)
    rumbo = models.FloatField(null=True, blank=True)
    nav = models.SmallIntegerField(
        null=True, blank=True,
        help_text='NavigationalStatus del AIS (0 con motor, 1 fondeado, 2 sin gobierno, 5 amarrado, 7 pescando…). Lo declara la tripulación.',
    )

    class Meta:
        db_table = 'detection_ais_posicion'
        verbose_name = 'Posición AIS'
        verbose_name_plural = 'Posiciones AIS'
        indexes = [
            models.Index(fields=['mmsi', 'timestamp'], name='idx_aispos_mmsi_ts'),
            models.Index(fields=['timestamp'], name='idx_aispos_ts'),
        ]

    def __str__(self) -> str:
        return f'AIS {self.mmsi} {self.timestamp:%Y-%m-%d %H:%M}'
