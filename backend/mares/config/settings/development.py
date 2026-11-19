from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ['*']

CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

DATABASES['default']['CONN_MAX_AGE'] = 0
DATABASES['default']['TEST'] = {
    'NAME': 'maresv1_test',
}

LOGGING['loggers']['mares']['level'] = 'DEBUG'
LOGGING['loggers']['django.db.backends']['level'] = 'INFO'

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

INSTALLED_APPS += ['django.contrib.admindocs']

REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
    'rest_framework.renderers.JSONRenderer',
    'rest_framework.renderers.BrowsableAPIRenderer',
]
