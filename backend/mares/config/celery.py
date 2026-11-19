import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mares.config.settings.development')

app = Celery('mares')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Sella cada hora las alertas reales (validación posterior, sin poder ajustar el resultado)
    'sellar-alertas-cables-hourly': {
        'task': 'mares.cables.sellar_alertas',
        'schedule': crontab(minute=5),
        'options': {'queue': 'periodic'},
    },
    # Mantiene lista la respuesta pública de buques (la primera visita tardaría ~10 s)
    'precalentar-buques-cables': {
        'task': 'mares.cables.precalentar_buques',
        'schedule': 15.0,
        'options': {'queue': 'periodic'},
    },
    # Purga del historial AIS — diaria a las 03:00 UTC
    'purge-ais-history-daily-03h': {
        'task': 'mares.detection.purge_ais_history',
        'schedule': crontab(minute=0, hour=3),
        'options': {'queue': 'periodic'},
    },
    # monitor_aisstream corre como worker permanente (no beat):
    #   bash celery_worker.sh aisstream
}

app.conf.task_routes = {
    'mares.detection.*': {'queue': 'periodic'},
}

app.conf.task_annotations = {
    # monitor_aisstream: los límites van en el decorador (valor efectivamente infinito).
    # Aquí había time_limit/soft_time_limit = None: pisaba al decorador y Celery aplicaba el
    # global de 270 s, matando el monitor AIS cada ~4,5 minutos.
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
