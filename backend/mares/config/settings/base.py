import glob
from datetime import timedelta
from pathlib import Path

import environ

env = environ.Env()

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
environ.Env.read_env(BASE_DIR / '.env')

# ─── GDAL / GEOS — detección automática del entorno virtual ───────────────────
# Si libgdal no está en las rutas estándar del sistema (e.g. Railway, Fedora sin
# paquete gdal), usamos la que viene empaquetada con pyogrio en el venv.
# Django lee settings.GDAL_LIBRARY_PATH (atributo de módulo) antes de setup().
_venv_gdal = glob.glob(str(BASE_DIR.parent / '.venv/lib/python*/site-packages/pyogrio.libs/libgdal-*.so.*'))
if _venv_gdal:
    GDAL_LIBRARY_PATH = _venv_gdal[0]

SECRET_KEY = env('SECRET_KEY')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'corsheaders',
]

LOCAL_APPS = [
    'mares.apps.core',
    'mares.apps.detection',
    'mares.apps.cables',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'mares.apps.core.middleware.RequestLoggingMiddleware',
]

ROOT_URLCONF = 'mares.config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'mares.wsgi.application'

DATABASES = {
    'default': env.db('DATABASE_URL', default='postgis://localhost:5432/maresv1'),
}
DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'

# Toda la API del producto es pública y de solo lectura: sin autenticación de usuarios. El panel /admin/ usa el usuario estándar de Django.
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'anon': '600/minute'},
}

CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 270
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_RESULT_EXPIRES = timedelta(hours=24)

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'RETRY_ON_TIMEOUT': True,
            'MAX_CONNECTIONS': 100,
            'CONNECTION_POOL_KWARGS': {'max_connections': 100},
        },
        'KEY_PREFIX': 'mares',
        'TIMEOUT': 300,
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'structured': {
            'format': '%(asctime)s %(levelname)s %(name)s %(process)d %(thread)d %(message)s',
            'datefmt': '%Y-%m-%dT%H:%M:%S',
        },
        'verbose': {
            'format': '%(asctime)s %(levelname)-8s %(name)s:%(lineno)d %(message)s',
            'datefmt': '%Y-%m-%dT%H:%M:%S',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file_general': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'mares.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 10,
            'formatter': 'structured',
            'encoding': 'utf-8',
        },
    },
    'root': {
        'handlers': ['console', 'file_general'],
        'level': 'WARNING',
    },
    'loggers': {
        'mares': {
            'handlers': ['console', 'file_general'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console', 'file_general'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

LANGUAGE_CODE = 'es'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

AISSTREAM_API_KEY = env('AISSTREAM_API_KEY', default='')

# Proxies de confianza delante de Django (ver mares.apps.core.network.get_client_ip).
# 0 = sin proxy: se usa REMOTE_ADDR e ignora X-Forwarded-For.
TRUSTED_PROXY_COUNT = env.int('TRUSTED_PROXY_COUNT', default=0)

# Historial AIS (detection.ais_history): 1 posición por barco cada N s, volcado por lotes.
AIS_HISTORY_INTERVAL_SECONDS = env.int('AIS_HISTORY_INTERVAL_SECONDS', default=600)
AIS_HISTORY_RETENTION_DAYS = env.int('AIS_HISTORY_RETENTION_DAYS', default=60)

# Cables submarinos (apps.cables): ancho del corredor de vigilancia a cada lado del cable.
CABLES_CORREDOR_M = env.int('CABLES_CORREDOR_M', default=2000)

# Zonas que escucha el monitor de AISstream: cada una es [[lat1, lon1], [lat2, lon2]] (esquinas opuestas).
# Se eligieron por tener cables y tráfico, y por incidentes recientes. La cobertura real de cada zona (AISstream es
# de estaciones en tierra) hay que MEDIRLA: lejos de la costa puede ser casi nula.
AISSTREAM_ZONAS = {
    'Perú y Pacífico sur': [[-20, -85], [5, -65]],
    'Chile norte': [[-40, -85], [-20, -65]],
    'Pacífico noreste': [[-5, -100], [15, -65]],
    'Báltico': [[53.5, 9.0], [66.0, 30.5]],
    'Mar del Norte y Canal': [[48.5, -6.0], [61.0, 9.0]],
    'Estrecho de Taiwán': [[21.0, 116.0], [28.5, 124.5]],
    'Mar Rojo y Golfo de Adén': [[11.0, 32.0], [30.0, 52.0]],
    'Golfo Pérsico y Ormuz': [[23.0, 48.0], [30.5, 58.5]],
    'Mediterráneo oriental': [[30.0, 25.0], [37.5, 36.5]],
}
AISSTREAM_BOUNDING_BOXES = list(AISSTREAM_ZONAS.values())

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── API Documentation ────────────────────────────────────────────────────────
INSTALLED_APPS += ['drf_spectacular']

REST_FRAMEWORK_DEFAULT = REST_FRAMEWORK.copy()
REST_FRAMEWORK['DEFAULT_SCHEMA_CLASS'] = 'drf_spectacular.openapi.AutoSchema'

SPECTACULAR_SETTINGS = {
    'TITLE': 'API de Vigía',
    'DESCRIPTION': 'Vigilancia de cables submarinos: cables, buques con nivel de atención, replay, sellos y validaciones. Pública y de solo lectura.',
    'VERSION': '1.0.0',
}
