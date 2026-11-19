"""Registro de cada petición: método, ruta, estado, duración e IP del cliente (con un identificador para seguirla)."""
import logging
import time
import uuid
from typing import Callable

from django.http import HttpRequest, HttpResponse

from mares.apps.core.network import get_client_ip

request_logger = logging.getLogger('mares.requests')


class RequestLoggingMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        inicio = time.monotonic()
        request_id = uuid.uuid4().hex[:12]
        request.mares_request_id = request_id  # type: ignore[attr-defined]

        response = self.get_response(request)

        request_logger.info(
            'method=%s path=%s status=%d duration_ms=%.1f ip=%s request_id=%s',
            request.method, request.path, response.status_code, (time.monotonic() - inicio) * 1000,
            get_client_ip(request), request_id,
        )
        return response
