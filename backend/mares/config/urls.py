from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.utils import timezone
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


def health_check(request):
    from django.db import connection
    db_ok = True
    try:
        connection.ensure_connection()
    except Exception:
        db_ok = False

    # Redis sostiene la caché de la API y el índice de AIS en vivo: sin él el servicio está degradado.
    redis_ok = True
    try:
        from django.core.cache import cache
        cache.set('_health_ping', '1', timeout=5)
        redis_ok = cache.get('_health_ping') == '1'
    except Exception:
        redis_ok = False

    ok = db_ok and redis_ok
    return JsonResponse(
        {
            'status': 'ok' if ok else 'degraded',
            'timestamp': timezone.now().isoformat(),
            'checks': {'database': 'ok' if db_ok else 'error', 'redis': 'ok' if redis_ok else 'error'},
        },
        status=200 if ok else 503,
    )


def api_root(request):
    return JsonResponse({
        'service': 'Vigía',
        'version': 'v1',
        'endpoints': {'cables': '/api/v1/cables/', 'docs': '/api/docs/', 'health': '/health/'},
    })


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health-check'),
    path('api/', api_root, name='api-root'),
    path('api/v1/cables/', include('mares.apps.cables.urls', namespace='cables')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
