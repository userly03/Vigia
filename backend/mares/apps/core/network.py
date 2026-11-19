from django.conf import settings


def get_client_ip(request) -> str:
    """
    IP del cliente que no se puede falsificar con X-Forwarded-For.

    Cada proxy de confianza agrega la IP de su peer al final de X-Forwarded-For,
    así que con N proxies la IP real es la N-ésima desde la derecha. Todo lo que
    esté a la izquierda lo controla el cliente y se ignora.

    TRUSTED_PROXY_COUNT=0 (por defecto): se usa REMOTE_ADDR e ignora el header.
    """
    remote_addr = request.META.get('REMOTE_ADDR', '')
    proxies = getattr(settings, 'TRUSTED_PROXY_COUNT', 0)
    if proxies <= 0:
        return remote_addr

    hops = [h.strip() for h in request.META.get('HTTP_X_FORWARDED_FOR', '').split(',') if h.strip()]
    if len(hops) < proxies:
        return remote_addr
    return hops[-proxies]
