from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Lanza el worker permanente monitor_aisstream vía Celery'

    def handle(self, *args, **options):
        api_key = getattr(settings, 'AISSTREAM_API_KEY', '').strip()
        if not api_key:
            self.stderr.write(self.style.ERROR(
                'AISSTREAM_API_KEY no configurada. '
                'Agregar al .env antes de lanzar el monitor.'
            ))
            return

        from mares.apps.detection.tasks import monitor_aisstream
        result = monitor_aisstream.delay()
        self.stdout.write(self.style.SUCCESS(
            f'monitor_aisstream enviado al worker | task_id={result.id}'
        ))
        self.stdout.write(
            'El worker procesa la tarea en background. '
            'Verificar logs con: celery -A mares.config.celery flower'
        )
