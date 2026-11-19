"""
Monitor AIS en PRIMER PLANO y sin Celery: escucha AISstream y deja la última posición de cada barco en Redis y, cada ~10 min,
en el historial de la base de datos. Ctrl+C para parar.

  python manage.py monitor_ais

Necesita AISSTREAM_API_KEY en backend/.env. Sin clave: `python manage.py simular_ais` (datos SIMULADOS, rotulados).
(La variante con Celery, `start_aisstream`, hace lo mismo pero dentro de un worker.)
"""
import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Escucha AISstream en primer plano (sin Celery). Ctrl+C para parar.'

    def handle(self, *args, **options):
        clave = (getattr(settings, 'AISSTREAM_API_KEY', '') or '').strip()
        if not clave:
            raise CommandError('Falta AISSTREAM_API_KEY en backend/.env. Sin clave, usa: python manage.py simular_ais (datos SIMULADOS).')
        from mares.apps.detection.tasks import _run_aisstream_loop
        self.stdout.write('Escuchando AISstream… (Ctrl+C para parar)')
        try:
            asyncio.run(_run_aisstream_loop(clave))
        except KeyboardInterrupt:
            self.stdout.write('Detenido.')
