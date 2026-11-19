"""
Alertas selladas: cada hora se guarda, con un hash encadenado, la lista de alertas ALTO/MEDIO con datos REALES.

El hash de un sello es SHA-256 de `hash_anterior + "\n" + JSON canónico del contenido` (claves ordenadas, sin espacios,
sin escapar no-ASCII). Cualquiera puede recalcularlo con `python3 scripts/verificar_sellos.py`.
"""
from __future__ import annotations

import hashlib
import json

from django.db import transaction
from django.utils import timezone

from .models import Sello

VERSION = 'sello-vigia/1'
NIVELES = ('ALTO', 'MEDIO')


def canonico(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def calcular_hash(hash_anterior: str, contenido: dict) -> str:
    return hashlib.sha256(f'{hash_anterior}\n{canonico(contenido)}'.encode('utf-8')).hexdigest()


def extraer_recorridos(data: dict) -> list[dict]:
    """Buques reales en marcha con un recorrido largo continuo dentro de un corredor (señal INFORMATIVA, no alerta)."""
    out = []
    for f in data['features']:
        p = f['properties']
        if p.get('simulado') or not p.get('recorrido_km'):
            continue
        out.append({'mmsi': p['mmsi'], 'nombre': p.get('nombre') or '', 'recorrido_km': p['recorrido_km'], 'sog_kn': p.get('sog'),
                    'cable': p.get('cable_nombre'), 'lat': round(f['geometry']['coordinates'][1], 4), 'lng': round(f['geometry']['coordinates'][0], 4)})
    return sorted(out, key=lambda a: str(a['mmsi']))


def extraer_alertas(data: dict) -> list[dict]:
    """Alertas reales (nunca simuladas) del resultado de BuquesView, ordenadas por MMSI para que el contenido sea estable."""
    out = []
    for f in data['features']:
        p = f['properties']
        if p.get('simulado') or p.get('alerta') not in NIVELES:
            continue
        pr = p.get('prueba') or {}
        out.append({
            'mmsi': p['mmsi'], 'nombre': p.get('nombre') or '', 'nivel': p['alerta'], 'minutos': p.get('minutos'),
            'cable': p.get('cable_nombre'), 'dist_m': p.get('dist_m'), 'estado': p.get('estado'), 'sog_kn': p.get('sog'),
            'habitual': bool(p.get('habitual')), 'veredicto': pr.get('veredicto'), 'aprox_km': pr.get('aprox_km'),
            'lat': round(f['geometry']['coordinates'][1], 4), 'lng': round(f['geometry']['coordinates'][0], 4),
            'ultima_posicion': p.get('ts'),
        })
    return sorted(out, key=lambda a: str(a['mmsi']))


@transaction.atomic
def sellar(data: dict) -> Sello:
    """Crea el siguiente sello de la cadena con las alertas reales de `data`."""
    ultimo = Sello.objects.select_for_update().order_by('-ts', '-id').first()
    ahora = timezone.now()
    contenido = {
        'formato': VERSION, 'ts': ahora.isoformat(), 'datos_generados': data['meta']['generado'],
        'buques_reales': data['meta']['total'] - data['meta']['simulados'], 'alertas': extraer_alertas(data), 'recorridos': extraer_recorridos(data),
    }
    anterior = ultimo.hash if ultimo else ''
    return Sello.objects.create(ts=ahora, contenido=contenido, hash_anterior=anterior, hash=calcular_hash(anterior, contenido))


def verificar(sellos: list[Sello]) -> list[str]:
    """Problemas de la cadena (lista vacía = íntegra). `sellos` en orden cronológico."""
    problemas = []
    previo = None
    for s in sellos:
        if calcular_hash(s.hash_anterior, s.contenido) != s.hash:
            problemas.append(f'sello {s.id}: el contenido no coincide con su hash')
        if previo is not None and s.hash_anterior != previo.hash:
            problemas.append(f'sello {s.id}: no encadena con el anterior (¿falta o se alteró uno?)')
        previo = s
    return problemas
