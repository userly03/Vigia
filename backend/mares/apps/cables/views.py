"""
API pública y de solo lectura del Vigía.

- GET /api/v1/cables/          cables como GeoJSON (se guarda en caché una hora)
- GET /api/v1/cables/amarres/  puntos de amarre como GeoJSON
- GET /api/v1/cables/buques/   buques AIS en vivo como GeoJSON, con su estado y nivel de atención respecto de los
                               cables, más los buques que dejaron de transmitir dentro de un corredor

Todo es público: son datos que ya circulan abiertos (AIS, trazados de cables). No expone nada de incidentes.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path

from django.contrib.gis.db.models.functions import AsGeoJSON
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from mares.apps.detection.models import AISPosicion
from mares.apps.detection.tasks import _AIS_CACHE_KEY_PREFIX, _AIS_INDEX_KEY

from . import deriva, estados
from .deriva import fuerzas_para
from .models import Cable, PuntoAmarre, Sello

logger = logging.getLogger('mares.cables')

CACHE_GEOJSON_S = 3600
CACHE_BUQUES_S = 10          # la respuesta es pública: se comparte entre visitantes para no recalcularla por cada uno
MAX_BUQUES = 12000
HISTORIAL_H = 6
SILENCIO_MIN = 45


# ─── lectura del AIS en vivo ──────────────────────────────────────────────────

def _parse_ts(iso: str | None) -> datetime | None:
    try:
        dt = datetime.fromisoformat((iso or '').replace('Z', '+00:00'))
        return dt if dt.tzinfo else dt.replace(tzinfo=dt_timezone.utc)
    except (ValueError, TypeError):
        return None


def posiciones_vivas() -> list[dict]:
    """Posiciones válidas del caché de Redis que alimenta el monitor de AISstream."""
    raw_index = cache.get(_AIS_INDEX_KEY)
    if not raw_index:
        return []
    mmsis = json.loads(raw_index) if isinstance(raw_index, str) else list(raw_index)
    valores = cache.get_many([f'{_AIS_CACHE_KEY_PREFIX}{m}' for m in mmsis])
    out: list[dict] = []
    for v in valores.values():
        try:
            p = json.loads(v) if isinstance(v, str) else v
            lat, lng = float(p['lat']), float(p['lng'])
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            continue
        p['lat'], p['lng'] = lat, lng
        out.append(p)
        if len(out) >= MAX_BUQUES:
            break
    return out


# ─── consultas espaciales ─────────────────────────────────────────────────────

def _arrays(posiciones: list[dict], idxs: list[int] | None = None):
    idxs = list(range(len(posiciones))) if idxs is None else idxs
    return idxs, [posiciones[i]['lng'] for i in idxs], [posiciones[i]['lat'] for i in idxs]


def _radio_m() -> float:
    return float(getattr(settings, 'CABLES_CORREDOR_M', 2000))


def _grados(radio_m: float) -> float:
    """Margen en grados para prefiltrar por caja (≥ el radio; 1° ≈ 111 km)."""
    return radio_m / 111000.0 * 1.5 + 0.01


# Pertenencia al corredor en dos ramas: con polígono (índice espacial) y, para los tramos sin polígono (los que
# tocan el antimeridiano: por construcción sólo existen a menos de 0,1° de ±180°, de ahí el filtro ABS(lon) > 179,5), por distancia directa con prefiltro de caja. Un OR en el JOIN haría un producto cartesiano.
_CANDIDATOS = """
  SELECT {sel}, c.slug, c.nombre, {pt} AS pt, t.geom
  FROM {src}
  JOIN cables_tramo t ON ST_Intersects(t.corredor, {pt})
  JOIN cables_cable c ON c.id = t.cable_id
  UNION ALL
  SELECT {sel}, c.slug, c.nombre, {pt} AS pt, t.geom
  FROM {src}
  JOIN cables_tramo t ON t.corredor IS NULL AND ABS(ST_X({pt})) > 179.5 AND t.geom && ST_Expand({pt}, %(grados)s)
                     AND ST_DWithin(t.geom::geography, {pt}::geography, %(radio)s)
  JOIN cables_cable c ON c.id = t.cable_id
"""


def en_corredor(posiciones: list[dict]) -> dict[int, tuple[str, str, float]]:
    """{índice: (slug, nombre, distancia_m)} del cable más cercano cuyo corredor contiene al buque."""
    if not posiciones:
        return {}
    idxs, lons, lats = _arrays(posiciones)
    cand = _CANDIDATOS.format(sel='p.idx', pt='p.pt', src='p')
    with connection.cursor() as cur:
        cur.execute(
            f"""
            WITH p AS (
              SELECT t.idx, ST_SetSRID(ST_MakePoint(t.lon, t.lat), 4326) AS pt
              FROM unnest(%(idx)s::int[], %(lon)s::float8[], %(lat)s::float8[]) AS t(idx, lon, lat)
            ), cand AS ({cand})
            SELECT DISTINCT ON (idx) idx, slug, nombre, ST_Distance(geom::geography, pt::geography) AS dist_m
            FROM cand ORDER BY idx, dist_m
            """,
            {'idx': idxs, 'lon': lons, 'lat': lats, 'radio': _radio_m(), 'grados': _grados(_radio_m())},
        )
        return {i: (s, n, float(d)) for i, s, n, d in cur.fetchall()}


def cerca_de_amarre(posiciones: list[dict], idxs: list[int]) -> set[int]:
    if not idxs:
        return set()
    ids, lons, lats = _arrays(posiciones, idxs)
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT t.idx
            FROM unnest(%s::int[], %s::float8[], %s::float8[]) AS t(idx, lon, lat)
            JOIN cables_punto_amarre a
              ON a.geom && ST_Expand(ST_SetSRID(ST_MakePoint(t.lon, t.lat), 4326),
                                     %s / GREATEST(COS(RADIANS(t.lat)), 0.05), %s)   -- prefiltro por caja: usa el índice espacial
             AND ST_DWithin(a.geom::geography, ST_SetSRID(ST_MakePoint(t.lon, t.lat), 4326)::geography, %s)
            """,
            [ids, lons, lats, _grados(estados.RADIO_AMARRE_M), _grados(estados.RADIO_AMARRE_M), estados.RADIO_AMARRE_M],
        )
        return {r[0] for r in cur.fetchall()}


def historial_en_corredor(mmsis: list[str]) -> dict[str, list[tuple]]:
    """{mmsi: [(ts, sog, dentro, lat, lon), …]} de las últimas HISTORIAL_H horas, de la más reciente a la más antigua."""
    if not mmsis:
        return {}
    out: dict[str, list[tuple]] = {}
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT h.mmsi, h.timestamp, h.velocidad_nudos, ST_Y(h.posicion), ST_X(h.posicion),
                   (EXISTS (SELECT 1 FROM cables_tramo t WHERE ST_Intersects(t.corredor, h.posicion))
                    OR EXISTS (SELECT 1 FROM cables_tramo t
                               WHERE t.corredor IS NULL AND ABS(ST_X(h.posicion)) > 179.5 AND t.geom && ST_Expand(h.posicion, %s)
                                 AND ST_DWithin(t.geom::geography, h.posicion::geography, %s))) AS dentro
            FROM detection_ais_posicion h
            WHERE h.mmsi = ANY(%s) AND h.timestamp > %s
            ORDER BY h.mmsi, h.timestamp DESC
            """,
            [_grados(_radio_m()), _radio_m(), mmsis, timezone.now() - timedelta(hours=HISTORIAL_H)],
        )
        for mmsi, ts, sog, lat, lon, dentro in cur.fetchall():
            out.setdefault(mmsi, []).append((ts, sog, dentro, lat, lon))
    return out


def celdas_habituales() -> set[tuple[int, int]]:
    """
    Celdas de ~2 km donde, en las últimas HABITUAL_HORAS h, se detuvieron (< 0,5 kn) al menos HABITUAL_MIN_BUQUES buques
    DISTINTOS: puertos y radas. Se aprende del propio historial AIS; con poco historial detecta menos. Caché de 10 min.
    """
    clave = 'cables:habituales'
    guardado = cache.get(clave)
    if guardado is not None:
        return {tuple(c) for c in guardado}
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT round(ST_Y(posicion) / %(c)s)::int, round(ST_X(posicion) / %(c)s)::int
            FROM detection_ais_posicion
            WHERE timestamp > %(desde)s AND velocidad_nudos < 0.5 AND mmsi NOT LIKE '9990%%'
            GROUP BY 1, 2 HAVING count(DISTINCT mmsi) >= %(n)s
            """,
            {'c': estados.HABITUAL_CELDA_GRADOS, 'desde': timezone.now() - timedelta(hours=estados.HABITUAL_HORAS), 'n': estados.HABITUAL_MIN_BUQUES},
        )
        celdas = {(i, j) for i, j in cur.fetchall()}
    cache.set(clave, [list(c) for c in celdas], 600)
    return celdas


def es_habitual(lat: float, lon: float, celdas: set[tuple[int, int]]) -> bool:
    i, j = round(lat / estados.HABITUAL_CELDA_GRADOS), round(lon / estados.HABITUAL_CELDA_GRADOS)
    return any((i + di, j + dj) in celdas for di in (-1, 0, 1) for dj in (-1, 0, 1))


def silencios_en_corredor() -> list[dict]:
    """
    Buques cuya última posición guardada cayó dentro de un corredor y no han vuelto a transmitir en SILENCIO_MIN min.
    OJO: puede ser que simplemente salieron del alcance de los receptores; es un indicio, no una prueba.
    """
    ahora = timezone.now()
    cand = _CANDIDATOS.format(sel='u.mmsi, u.vessel_name, u.timestamp, u.posicion', pt='u.posicion', src='ult u')
    with connection.cursor() as cur:
        cur.execute(
            f"""
            WITH ult AS (
              SELECT DISTINCT ON (mmsi) mmsi, vessel_name, posicion, timestamp
              FROM detection_ais_posicion
              WHERE timestamp > %(desde)s
              ORDER BY mmsi, timestamp DESC
            ), cand AS ({cand})
            SELECT DISTINCT ON (mmsi) mmsi, vessel_name, ST_Y(posicion), ST_X(posicion), timestamp, slug, nombre,
                   ST_Distance(geom::geography, pt::geography) AS dist_m
            FROM cand
            WHERE timestamp < %(hasta)s
            ORDER BY mmsi, dist_m
            """,
            {'desde': ahora - timedelta(hours=HISTORIAL_H), 'hasta': ahora - timedelta(minutes=SILENCIO_MIN),
             'radio': _radio_m(), 'grados': _grados(_radio_m())},
        )
        filas = cur.fetchall()
    filas.sort(key=lambda f: f[4], reverse=True)
    return [
        {
            'mmsi': m, 'nombre': n or '', 'lat': lat, 'lng': lng, 'ultima': ts.isoformat(),
            'minutos_sin_senal': round((ahora - ts).total_seconds() / 60.0),
            'cable': s, 'cable_nombre': cn, 'distancia_m': round(d),
        }
        for m, n, lat, lng, ts, s, cn, d in filas[:100]
    ]


# ─── vistas ───────────────────────────────────────────────────────────────────

class _Publica(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]


class CablesView(_Publica):
    @extend_schema(responses={200: OpenApiTypes.OBJECT}, summary='Cables submarinos (GeoJSON)')
    def get(self, request: Request) -> Response:
        data = cache.get('cables:geojson')
        if data is None:
            filas = Cable.objects.annotate(gj=AsGeoJSON('geom', precision=3)).values(
                'slug', 'nombre', 'color', 'longitud_km', 'gj', 'fuente',
            )
            data = {
                'type': 'FeatureCollection',
                'features': [
                    {
                        'type': 'Feature',
                        'geometry': json.loads(f['gj']),
                        'properties': {
                            'slug': f['slug'], 'nombre': f['nombre'], 'color': f['color'],
                            'longitud_km': round(f['longitud_km']) if f['longitud_km'] else None,
                        },
                    }
                    for f in filas
                ],
                'atribucion': 'Datos de cables © TeleGeography (submarinecablemap.com)',
            }
            cache.set('cables:geojson', data, CACHE_GEOJSON_S)
        resp = Response(data)
        resp['Cache-Control'] = 'public, max-age=300'
        return resp


class AmarresView(_Publica):
    @extend_schema(responses={200: OpenApiTypes.OBJECT}, summary='Puntos de amarre (GeoJSON)')
    def get(self, request: Request) -> Response:
        data = cache.get('cables:amarres')
        if data is None:
            data = {
                'type': 'FeatureCollection',
                'features': [
                    {
                        'type': 'Feature',
                        'geometry': {'type': 'Point', 'coordinates': [round(p.geom.x, 4), round(p.geom.y, 4)]},
                        'properties': {'nombre': p.nombre, 'pais': p.pais},
                    }
                    for p in PuntoAmarre.objects.all()
                ],
            }
            cache.set('cables:amarres', data, CACHE_GEOJSON_S)
        resp = Response(data)
        resp['Cache-Control'] = 'public, max-age=300'
        return resp


METODO_DERIVA = {
    'viento_k': deriva.VIENTO_K, 'tolerancia_base_kn': deriva.TOL_BASE_KN, 'tolerancia_viento': deriva.TOL_VIENTO,
    'min_muestras': deriva.MIN_MUESTRAS, 'min_minutos': deriva.MIN_MINUTOS, 'quieto_kn': deriva.UMBRAL_QUIETO_KN,
}
MAX_PRUEBAS = 300
VENTANA_PRUEBA_H = 3


def _compacta(r: dict) -> dict:
    """Lo mínimo que necesita la pantalla para dibujar y explicar el veredicto."""
    o, e, f = r['obs'], r['esperada'], r['fuerzas']
    return {
        'veredicto': r['veredicto'], 'obs_kn': round(o['rapidez_kn'], 2), 'obs_rumbo': round(o['rumbo']),
        'obs_ve': round(o['ve_kn'], 3), 'obs_vn': round(o['vn_kn'], 3),
        'esp_kn': round(e['rapidez_kn'], 2), 'esp_rumbo': round(e['rumbo']), 'esp_ve': round(e['ve_kn'], 3), 'esp_vn': round(e['vn_kn'], 3),
        'residuo_kn': round(r['residuo_kn'], 2), 'tol_kn': round(r['tolerancia_kn'], 2), 'tol_base_kn': round(f.get('tol_base_kn', deriva.TOL_BASE_KN), 2),
        'corriente_kn': round(f['corriente_kn'], 2), 'corriente_hacia': round(f['corriente_hacia']), 'aprox_km': f.get('aprox_km', 0),
        'viento_kn': round(f['viento_kn'], 1), 'viento_desde': round(f['viento_desde']),
        'muestras': o['muestras'], 'minutos': o['minutos'], 'pista': r.get('pista', []),
    }


class BuquesView(_Publica):
    @extend_schema(responses={200: OpenApiTypes.OBJECT}, summary='Buques en vivo y su nivel de atención respecto de los cables')
    def get(self, request: Request) -> Response:
        data = cache.get('cables:buques')
        if data is None:
            data = self.refrescar(CACHE_BUQUES_S)
        return Response(data)

    @staticmethod
    def refrescar(ttl_s: int) -> dict:
        """Calcula la respuesta y la deja en la caché compartida `ttl_s` segundos (la usan la vista y la tarea periódica)."""
        data = BuquesView._construir()
        cache.set('cables:buques', data, ttl_s)
        return data

    @staticmethod
    def _pruebas(pos: list[dict], candidatos: list[int], hist: dict) -> tuple[dict[int, dict], dict]:
        """
        ({índice: resultado de la prueba de deriva pasiva}, estadísticas) para los buques lentos o parados del corredor.
        Estadísticas: cuántos tenían pista suficiente y a cuántos les faltó el dato de corriente (típico cerca de la costa).
        """
        desde = timezone.now() - timedelta(hours=VENTANA_PRUEBA_H)
        obs: dict[int, dict] = {}
        pistas: dict[int, list] = {}
        # con tope de evaluaciones se prefiere a quien tiene más pista: es de quien más se puede concluir
        prioritarios = sorted(candidatos, key=lambda i: -len(hist.get(str(pos[i].get('mmsi')), [])))
        for i in prioritarios[:MAX_PRUEBAS]:
            p = pos[i]
            ts = _parse_ts(p.get('timestamp')) or timezone.now()
            muestras = [(ts, p['lat'], p['lng'])] + [(h[0], h[3], h[4]) for h in hist.get(str(p.get('mmsi')), []) if h[0] >= desde]
            o = deriva.velocidad_observada(muestras)
            if o:
                obs[i] = o
                pistas[i] = [[round(m[2], 5), round(m[1], 5)] for m in sorted(muestras, key=lambda x: x[0])][-24:]
        if not obs:
            return {}, {'con_pista': 0, 'sin_agua': 0}
        idx = list(obs)
        fuerzas = fuerzas_para([(pos[i]['lat'], pos[i]['lng']) for i in idx])
        res = {i: {**deriva.veredicto(obs[i], f), 'pista': pistas[i]} for i, f in zip(idx, fuerzas) if f}
        return res, {'con_pista': len(idx), 'sin_agua': len(idx) - len(res)}

    @staticmethod
    def _construir() -> dict:
        pos = posiciones_vivas()
        dentro = en_corredor(pos)

        lentos = [i for i in dentro if estados.clasificar(pos[i].get('velocidad_nudos'), pos[i].get('nav')) in (estados.PARADO, estados.LENTO)]
        amarre = cerca_de_amarre(pos, lentos)
        en_marcha = [i for i in dentro if estados.clasificar(pos[i].get('velocidad_nudos'), pos[i].get('nav')) == estados.TRANSITO]
        hist = historial_en_corredor([str(pos[i].get('mmsi')) for i in lentos + en_marcha])
        n_recorridos = 0

        pruebas, est_pruebas = BuquesView._pruebas(pos, lentos, hist)
        habituales = celdas_habituales() if lentos else set()

        conteo = {'ALTO': 0, 'MEDIO': 0, 'BAJO': 0}
        feats = []
        for i, p in enumerate(pos):
            est = estados.clasificar(p.get('velocidad_nudos'), p.get('nav'))
            cab = dentro.get(i)
            minutos = 0.0
            nivel = None
            prueba = pruebas.get(i)
            if cab:
                ts = _parse_ts(p.get('timestamp')) or timezone.now()
                muestras = [(ts, p.get('velocidad_nudos'), True)] + list(hist.get(str(p.get('mmsi')), []))
                minutos = estados.minutos_lento_consecutivos(muestras)
                hab = bool(habituales) and es_habitual(p['lat'], p['lng'], habituales)
                inmovil = estados.horas_inmovil([(ts, p['lat'], p['lng'])] + [(h[0], h[3], h[4]) for h in hist.get(str(p.get('mmsi')), [])]) if est in (estados.PARADO, estados.LENTO) else 0.0
                nivel = estados.nivel_alerta(est, True, minutos, i in amarre, prueba['veredicto'] if prueba else None, hab, inmovil)
                if nivel:
                    conteo[nivel] += 1
                rec = estados.recorrido_continuo_km([(ts, p['lat'], p['lng'], True)] + [(h[0], h[3], h[4], h[2]) for h in hist.get(str(p.get('mmsi')), [])]) if est == estados.TRANSITO else 0.0
            props = {
                'mmsi': p.get('mmsi'), 'nombre': p.get('vessel_name') or '', 'sog': p.get('velocidad_nudos'),
                'cog': p.get('rumbo'), 'nav': p.get('nav'), 'estado': est, 'ts': p.get('timestamp'), 'simulado': bool(p.get('simulado')),
            }
            if cab:
                props.update(cable=cab[0], cable_nombre=cab[1], dist_m=round(cab[2]), minutos=round(minutos), alerta=nivel, habitual=hab, inmovil_h=round(inmovil, 1))
                if rec >= estados.RECORRIDO_MIN_KM:
                    props['recorrido_km'] = round(rec, 1)
                    if not p.get('simulado'):
                        n_recorridos += 1
            if prueba:
                props['prueba'] = _compacta(prueba)
            feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [p['lng'], p['lat']]}, 'properties': props})

        return {
            'type': 'FeatureCollection',
            'features': feats,
            'meta': {
                'generado': timezone.now().isoformat(),
                'total': len(feats), 'en_corredor': len(dentro), 'alertas': conteo, 'recorridos': n_recorridos,
                'simulados': sum(1 for f in feats if f['properties']['simulado']),
                'metodo': {**estados.METODO, 'deriva': METODO_DERIVA},
                'pruebas': {'evaluadas': len(pruebas), **est_pruebas, 'atribucion': deriva.ATRIBUCION},
                'zonas': [{'nombre': n, 'caja': c} for n, c in getattr(settings, 'AISSTREAM_ZONAS', {}).items()],
            },
            'silencios': silencios_en_corredor(),
        }


class SellosView(_Publica):
    @extend_schema(responses={200: OpenApiTypes.OBJECT}, summary='Cadena pública de alertas selladas (más recientes primero)')
    def get(self, request: Request) -> Response:
        from . import sellos
        total = Sello.objects.count()
        ult = list(Sello.objects.order_by('-ts', '-id')[:100])
        problemas = sellos.verificar(list(reversed(ult)))
        return Response({
            'total': total,
            'integra_en_lo_mostrado': not problemas, 'problemas': problemas,
            'explicacion': 'Cada sello incluye el hash del anterior; el hash es SHA-256 de hash_anterior + salto de línea + JSON canónico del contenido. '
                           'La cadena prueba el orden dentro de esta base de datos; para probar que existía antes de un suceso hay que publicar el último hash fuera.',
            'sellos': [{'ts': s.ts.isoformat(), 'hash': s.hash, 'hash_anterior': s.hash_anterior, 'contenido': s.contenido} for s in ult],
        })


RUTA_VALIDACION = Path(__file__).resolve().parent / 'validacion_datos'


def _leer_validacion(nombre: str) -> dict | None:
    try:
        return json.loads((RUTA_VALIDACION / nombre).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


class ValidacionView(_Publica):
    """Marcador público: las mediciones guardadas por los comandos de validación, con su fecha y sus límites."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT}, summary='Cifras medidas de la prueba de deriva y de la validación de corrientes')
    def get(self, request: Request) -> Response:
        return Response({
            'deriva_pasiva': _leer_validacion('deriva_pasiva.json'),      # manage.py validar_deriva_pasiva
            'corrientes_vs_boyas': _leer_validacion('maury_valida.json'),   # scripts/maury_valida.py
        })


REPLAY_MAX_BUQUES = 150
REPLAY_MAX_H = 6


class ReplayView(_Publica):
    """Pistas de las últimas horas de los buques con atención (ALTO/MEDIO) o con recorrido largo, para reproducirlas en pantalla."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT}, summary='Pistas recientes de los buques con atención, para el replay')
    def get(self, request: Request) -> Response:
        try:
            horas = min(max(float(request.query_params.get('horas', 3)), 0.5), REPLAY_MAX_H)
        except ValueError:
            horas = 3.0
        clave = f'cables:replay:{horas}'
        data = cache.get(clave)
        if data is None:
            data = self._construir(horas)
            cache.set(clave, data, 30)
        return Response(data)

    @staticmethod
    def _construir(horas: float) -> dict:
        base = cache.get('cables:buques') or BuquesView.refrescar(45)
        orden = {'ALTO': 0, 'MEDIO': 1}
        elegidos = []
        for f in base['features']:
            p = f['properties']
            nivel = p.get('alerta') if p.get('alerta') in orden else None
            if nivel or p.get('recorrido_km'):
                elegidos.append((orden.get(nivel, 2), -(p.get('minutos') or 0), f))
        elegidos.sort(key=lambda x: (x[0], x[1]))
        elegidos = [e[2] for e in elegidos[:REPLAY_MAX_BUQUES]]
        hasta = _parse_ts(base['meta']['generado']) or timezone.now()
        desde = hasta - timedelta(hours=horas)
        mmsis = [str(f['properties']['mmsi']) for f in elegidos]
        pistas: dict[str, list] = {m: [] for m in mmsis}
        for mmsi, ts, pos, sog in AISPosicion.objects.filter(mmsi__in=mmsis, timestamp__gte=desde, timestamp__lte=hasta).order_by('mmsi', 'timestamp').values_list('mmsi', 'timestamp', 'posicion', 'velocidad_nudos'):
            pistas[mmsi].append([round((hasta - ts).total_seconds() / 60.0, 1), round(pos.x, 5), round(pos.y, 5), sog])
        buques = []
        for f in elegidos:
            p = f['properties']
            pista = pistas[str(p['mmsi'])]
            pista.append([0.0, round(f['geometry']['coordinates'][0], 5), round(f['geometry']['coordinates'][1], 5), p.get('sog')])   # la posición actual cierra la pista
            pista.sort(key=lambda m: -m[0])   # de la más antigua a la más reciente
            buques.append({'mmsi': p['mmsi'], 'nombre': p.get('nombre') or '', 'nivel': p.get('alerta'), 'recorrido_km': p.get('recorrido_km'),
                           'cable': p.get('cable_nombre'), 'simulado': bool(p.get('simulado')), 'pista': pista})
        return {'hasta': hasta.isoformat(), 'horas': horas, 'buques': buques,
                'nota': 'Cada punto de la pista es [minutos antes de «hasta», lng, lat, sog en nudos]. Las posiciones se guardan cada ~10 min: entre ellas se interpola en línea recta.'}


HISTORIAL_MAX_H = 72
HISTORIAL_MAX_BUQUES = 100


def barcos_sobre_cable(cable_id: int, horas: float) -> list[dict]:
    """
    Barcos que estuvieron dentro del corredor de UN cable en las últimas `horas`, según el historial AIS guardado (una posición
    por barco cada ~10 min). Para cada uno: cuánto tiempo estuvo dentro, cuánto de ese tiempo fue lento o parado y su última posición.
    Ordenados por tiempo lento: el primero es el que más tiempo se quedó casi quieto sobre el cable.
    """
    desde = timezone.now() - timedelta(hours=horas)
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM (
              SELECT h.id, h.mmsi, h.vessel_name AS nombre, h.timestamp AS ts, h.velocidad_nudos AS sog, h.nav,
                     ST_Y(h.posicion) AS lat, ST_X(h.posicion) AS lon
              FROM cables_tramo t
              JOIN detection_ais_posicion h ON h.timestamp > %(desde)s AND h.posicion && t.corredor AND ST_Intersects(t.corredor, h.posicion)
              WHERE t.cable_id = %(cable)s AND t.corredor IS NOT NULL
              UNION
              SELECT h.id, h.mmsi, h.vessel_name, h.timestamp, h.velocidad_nudos, h.nav, ST_Y(h.posicion), ST_X(h.posicion)
              FROM cables_tramo t
              JOIN detection_ais_posicion h ON h.timestamp > %(desde)s AND ABS(ST_X(h.posicion)) > 179.5
                   AND h.posicion && ST_Expand(t.geom, %(grados)s) AND ST_DWithin(t.geom::geography, h.posicion::geography, %(radio)s)
              WHERE t.cable_id = %(cable)s AND t.corredor IS NULL
            ) q ORDER BY q.mmsi, q.ts
            """,
            {'desde': desde, 'cable': cable_id, 'grados': _grados(_radio_m()), 'radio': _radio_m()},
        )
        filas = cur.fetchall()

    por: dict[str, list] = {}
    for _id, mmsi, nombre, ts, sog, nav, lat, lon in filas:
        por.setdefault(mmsi, []).append((ts, sog, nav, lat, lon, nombre))

    def valida(v):
        return v is not None and 0 <= v < estados.SOG_NO_DISPONIBLE

    out = []
    for mmsi, xs in por.items():
        dentro_min = lento_min = 0.0
        for a, b in zip(xs, xs[1:]):
            gap = (b[0] - a[0]).total_seconds() / 60.0
            if gap > estados.RECORRIDO_HUECO_MIN:            # con un hueco de datos no se sabe qué hizo: no se cuenta
                continue
            dentro_min += gap
            if valida(a[1]) and a[1] < estados.UMBRAL_LENTO_KN:
                lento_min += gap
        sogs = [x[1] for x in xs if valida(x[1])]
        ultimo = xs[-1]
        out.append({
            'mmsi': mmsi, 'nombre': next((x[5] for x in reversed(xs) if x[5]), ''), 'simulado': str(mmsi).startswith('999'),
            'desde': xs[0][0].isoformat(), 'hasta': ultimo[0].isoformat(), 'posiciones': len(xs),
            'minutos_dentro': round(dentro_min), 'minutos_lento': round(lento_min),
            'sog_min_kn': round(min(sogs), 1) if sogs else None, 'sog_medio_kn': round(sum(sogs) / len(sogs), 1) if sogs else None,
            'nav_declarado': ultimo[2], 'ultima': {'lat': round(ultimo[3], 4), 'lng': round(ultimo[4], 4)},
        })
    out.sort(key=lambda b: (-b['minutos_lento'], -b['minutos_dentro'], b['mmsi']))
    return out


class HistorialCableView(_Publica):
    """Para investigar un incidente: quién estuvo sobre este cable en las últimas horas."""

    @extend_schema(responses={200: OpenApiTypes.OBJECT}, summary='Barcos que estuvieron sobre un cable en las últimas horas')
    def get(self, request: Request, slug: str) -> Response:
        try:
            horas = min(max(float(request.query_params.get('horas', 24)), 1.0), float(HISTORIAL_MAX_H))
        except ValueError:
            horas = 24.0
        cable = Cable.objects.filter(slug=slug).first()
        if cable is None:
            return Response({'detail': 'Cable no encontrado.'}, status=404)
        clave = f'cables:historial:{slug}:{horas}'
        data = cache.get(clave)
        if data is None:
            barcos = barcos_sobre_cable(cable.pk, horas)
            ahora = timezone.now()
            data = {
                'cable': {'slug': cable.slug, 'nombre': cable.nombre}, 'horas': horas,
                'desde': (ahora - timedelta(hours=horas)).isoformat(), 'hasta': ahora.isoformat(),
                'total_barcos': len(barcos), 'barcos': barcos[:HISTORIAL_MAX_BUQUES],
                'aviso': 'Solo aparecen barcos que emitieron AIS y que nuestros receptores captaron (guardamos una posición cada ~10 min, durante unos 60 días). '
                         'Un barco con el AIS apagado o fuera de alcance no aparece. Estar aquí no prueba que dañara el cable.',
            }
            cache.set(clave, data, 30)
        return Response(data)
