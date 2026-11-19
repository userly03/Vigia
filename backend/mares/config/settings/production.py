import environ

from .base import *  # noqa: F401, F403

env = environ.Env()

DEBUG = False

SECRET_KEY = env('SECRET_KEY')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS')  # requerido — no default
CORS_ALLOW_CREDENTIALS = True

# Sin valor por defecto: producción nunca debe caer a las credenciales de desarrollo.
DATABASES['default'] = env.db('DATABASE_URL')
DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'
DATABASES['default']['CONN_MAX_AGE'] = 60
DATABASES['default']['OPTIONS'] = {
    'connect_timeout': 10,
    'sslmode': env('DB_SSLMODE', default='require'),
}

# Railway termina TLS en un único proxy; ajustar por env si cambia la topología.
TRUSTED_PROXY_COUNT = env.int('TRUSTED_PROXY_COUNT', default=1)

# Detrás del proxy de Railway la petición llega por HTTP: sin esta cabecera SECURE_SSL_REDIRECT
# redirige sin fin (bucle). Solo es seguro porque TRUSTED_PROXY_COUNT indica que hay un proxy delante.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

CSP_DEFAULT_SRC = ("'none'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'",)
CSP_IMG_SRC = ("'self'", 'data:')
CSP_FONT_SRC = ("'self'",)
CSP_CONNECT_SRC = ("'self'",)
CSP_FRAME_ANCESTORS = ("'none'",)

CACHES['default']['OPTIONS']['PASSWORD'] = env('REDIS_PASSWORD', default='')

LOGGING['root']['level'] = 'WARNING'
LOGGING['loggers']['mares']['level'] = 'INFO'

STATIC_ROOT = env('STATIC_ROOT', default=str(BASE_DIR / 'staticfiles'))
MEDIA_ROOT = env('MEDIA_ROOT', default=str(BASE_DIR / 'media'))

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
