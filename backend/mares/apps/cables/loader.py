"""
Carga de cables y puntos de amarre desde GeoJSON (formato de submarinecablemap.com).

Cada cable llega como varios Feature con el mismo `properties.id` (un tramo por Feature); aquí se agrupan.
Los tramos que cruzan el antimeridiano (±180°) se parten, porque PostGIS y el mapa los dibujarían como una
línea que atraviesa el mundo entero.
"""
from __future__ import annotations

from django.contrib.gis.geos import LineString, MultiLineString, Point
from django.db import transaction
from django.utils.text import slugify

from .models import Cable, PuntoAmarre


def _lon(lon: float) -> float:
    return ((lon + 180.0) % 360.0) - 180.0 if lon < -180.0 or lon > 180.0 else lon


def partir_antimeridiano(linea: list) -> list[list[list[float]]]:
    """Parte una línea [[lon,lat],…] donde salta más de 180° de longitud. Descarta partes de <2 puntos."""
    partes: list[list[list[float]]] = []
    actual: list[list[float]] = []
    previa: float | None = None
    for pt in linea:
        lon, lat = _lon(float(pt[0])), float(pt[1])
        if previa is not None and abs(lon - previa) > 180.0:
            if len(actual) >= 2:
                partes.append(actual)
            actual = []
        actual.append([lon, lat])
        previa = lon
    if len(actual) >= 2:
        partes.append(actual)
    return partes


def agrupar_cables(fc: dict) -> dict[str, dict]:
    """{slug: {'nombre','color','lineas':[[[lon,lat],…],…]}}; ignora lo que no sea línea."""
    cables: dict[str, dict] = {}
    for f in (fc or {}).get('features', []):
        props = f.get('properties') or {}
        geom = f.get('geometry') or {}
        slug = props.get('id')
        if not slug:
            continue
        if geom.get('type') == 'LineString':
            lineas = [geom.get('coordinates') or []]
        elif geom.get('type') == 'MultiLineString':
            lineas = geom.get('coordinates') or []
        else:
            continue
        d = cables.setdefault(slug, {'nombre': props.get('name') or slug, 'color': props.get('color') or '', 'lineas': []})
        for linea in lineas:
            d['lineas'].extend(partir_antimeridiano(linea))
    return {k: v for k, v in cables.items() if v['lineas']}


def _pais(nombre: str) -> str:
    return nombre.rsplit(',', 1)[1].strip() if ',' in nombre else ''


@transaction.atomic
def cargar(fc_cables: dict, fc_amarres: dict | None = None, corredor_m: float | None = None) -> dict:
    """Sincroniza la base con los GeoJSON: crea, actualiza y borra lo que ya no viene. Devuelve un resumen."""
    cables = agrupar_cables(fc_cables)
    for slug, d in cables.items():
        geom = MultiLineString(*[LineString(l, srid=4326) for l in d['lineas']], srid=4326)
        Cable.objects.update_or_create(
            slug=slug[:120], defaults={'nombre': d['nombre'][:200], 'color': d['color'][:9], 'geom': geom},
        )
    borrados = 0
    if cables:
        sobran = Cable.objects.exclude(slug__in=[s[:120] for s in cables])
        borrados = sobran.count()      # (delete() también cuenta los tramos en cascada)
        sobran.delete()

    n_amarres = 0
    if fc_amarres is not None:
        vistos = []
        for f in fc_amarres.get('features', []):
            props = f.get('properties') or {}
            geom = f.get('geometry') or {}
            if geom.get('type') != 'Point' or not props.get('id'):
                continue
            lon, lat = _lon(float(geom['coordinates'][0])), float(geom['coordinates'][1])
            nombre = props.get('name') or props['id']
            slug = (slugify(props['id']) or props['id'])[:160]
            PuntoAmarre.objects.update_or_create(
                slug=slug, defaults={'nombre': nombre[:200], 'pais': _pais(nombre)[:80], 'geom': Point(lon, lat, srid=4326)},
            )
            vistos.append(slug)
            n_amarres += 1
        if vistos:
            PuntoAmarre.objects.exclude(slug__in=vistos).delete()

    tramos = Cable.reconstruir_tramos(corredor_m)
    return {'cables': len(cables), 'borrados': borrados, 'amarres': n_amarres, **tramos}
