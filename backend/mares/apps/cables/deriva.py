"""
Prueba de la deriva pasiva: ¿el movimiento observado de un buque se explica sólo por la corriente y el viento?

Idea. Un buque sin propulsión se mueve con la corriente más una fracción del viento (la «deriva por viento» o
windage). Si lo que se observó coincide con eso, el buque está a la deriva (sin gobierno o con el motor parado).
Si el agua y el viento lo arrastrarían pero está quieto, está sujeto al fondo (fondeado o amarrado). Si se mueve
distinto de lo que le haría el agua, hay propulsión o algo que lo retiene o lo arrastra (p. ej. un ancla).

Es una prueba de HIPÓTESIS con su incertidumbre, no un veredicto:
  - corrientes y viento vienen de modelos (Open-Meteo: corrientes ~8 km de resolución, no resuelven mareas finas
    ni la costa) y el viento arrastra distinto a cada casco: se usa VIENTO_K = 2,5 % con una tolerancia que lo cubre;
  - no está validada con incidentes reales (ver `manage.py validar_deriva_pasiva` para la coherencia con lo que
    declaran los propios buques, que tampoco es una verdad fiable).

Fuente de las fuerzas: Open-Meteo.com (CC BY 4.0, uso no comercial gratuito, con límite de llamadas).
"""
from __future__ import annotations

import logging
import math
from datetime import datetime

import requests
from django.core.cache import cache

logger = logging.getLogger('mares.cables.deriva')

KMH_POR_NUDO = 1.852
VIENTO_K = 0.025          # fracción del viento (10 m) que arrastra a un casco; la incertidumbre real es ~1–4 %
MIN_MUESTRAS = 3
MIN_MINUTOS = 30
UMBRAL_QUIETO_KN = 0.3    # por debajo, el buque está esencialmente quieto (el ruido del GPS es de decenas de metros)
TOL_BASE_KN = 0.4         # incertidumbre de la corriente del modelo (≈ 0,2 m/s) más el ruido de la posición
TOL_VIENTO = 0.015        # incertidumbre del windage: ±1,5 % del viento
# Tolerancia por región, MEDIDA contra boyas reales (scripts/maury_valida.py --regiones todas; 12 boyas por región como máximo,
# 40 días cada una; datos en validacion_datos/maury_valida.json). Se usa el error p90 del modelo de Copernicus redondeado hacia arriba:
#   Mar del Norte (horario, mareas) p90 0,61-0,77 → 0,7 · Mediterráneo 0,73 → 0,8 · Mar Rojo/Golfo 1,00 → 1,0
#   Taiwán 0,93-1,08 → 1,0 · Perú 0,44 → 0,5 · Báltico 0,34 → 0,4 (es el valor por defecto).
# Con 1,0 kn la prueba casi no discrimina a un buque lento: es lo que el modelo permite en esas regiones, y se dice en pantalla.
# Fuera de estas cajas NO está medido: se usa 0,4 sin respaldo. Pocas boyas y pocos años: indicativo.
TOL_REGIONES = [  # ((lat_min, lat_max, lon_min, lon_max), tolerancia kn, nombre): gana la primera que contenga el punto
    ((51.0, 61.0, -4.0, 9.0), 0.7, 'Mar del Norte'),
    ((30.0, 46.0, -6.0, 36.0), 0.8, 'Mediterráneo'),
    ((12.0, 30.0, 32.0, 60.0), 1.0, 'Mar Rojo y Golfo'),
    ((20.0, 28.0, 117.0, 125.0), 1.0, 'Taiwán'),
    ((-20.0, 0.0, -85.0, -70.0), 0.5, 'Perú'),
]
TOL_COSTA_KN = 0.3        # tolerancia extra si la corriente es la del agua cercana y no la de la celda (hasta ≥10 km)
CELDA = 0.1               # las fuerzas se piden y se guardan por celdas de 0,1°
CACHE_S = 3600
URL_CORRIENTES = 'https://marine-api.open-meteo.com/v1/marine'
URL_VIENTO = 'https://api.open-meteo.com/v1/forecast'
ATRIBUCION = 'Corrientes y viento: Open-Meteo.com (CC BY 4.0, uso no comercial)'

DERIVA, FIJO, PROPULSION, INDETERMINADO = 'deriva', 'fijo', 'propulsion', 'indeterminado'


# ─── geometría y vectores (este, norte) en nudos ──────────────────────────────

def vector(rapidez_kn: float, grados: float) -> tuple[float, float]:
    """Vector (este, norte) de una rapidez y un rumbo medido en grados desde el norte, hacia donde VA."""
    r = math.radians(grados)
    return rapidez_kn * math.sin(r), rapidez_kn * math.cos(r)


def rapidez_rumbo(ve: float, vn: float) -> tuple[float, float]:
    return math.hypot(ve, vn), (math.degrees(math.atan2(ve, vn)) + 360.0) % 360.0


def velocidad_observada(muestras: list[tuple[datetime, float, float]]) -> dict | None:
    """
    Velocidad media del buque ajustando una recta a su posición en el tiempo (mínimos cuadrados).
    `muestras`: [(instante, lat, lon), …]. Devuelve None si hay menos de MIN_MUESTRAS o abarcan < MIN_MINUTOS.
    """
    m = sorted(muestras, key=lambda x: x[0])
    if len(m) < MIN_MUESTRAS:
        return None
    t0, lat0, lon0 = m[0]
    minutos = (m[-1][0] - t0).total_seconds() / 60.0
    if minutos < MIN_MINUTOS:
        return None
    kx = 111_320.0 * math.cos(math.radians(lat0))
    ky = 110_540.0
    ts = [(t - t0).total_seconds() for t, _, _ in m]
    xs = [(lon - lon0) * kx for _, _, lon in m]
    ys = [(lat - lat0) * ky for _, lat, _ in m]
    n = len(ts)
    tm = sum(ts) / n
    sxx = sum((t - tm) ** 2 for t in ts)
    if sxx == 0:
        return None

    def pendiente_y_resto(v: list[float]) -> tuple[float, float]:
        vm = sum(v) / n
        b = sum((t - tm) * (x - vm) for t, x in zip(ts, v)) / sxx
        resto = math.sqrt(sum((x - (vm + b * (t - tm))) ** 2 for t, x in zip(ts, v)) / n)
        return b, resto

    bx, rx = pendiente_y_resto(xs)
    by, ry = pendiente_y_resto(ys)
    ve, vn = bx * 3600 / 1852.0, by * 3600 / 1852.0          # m/s -> nudos
    rapidez, rumbo = rapidez_rumbo(ve, vn)
    return {
        've_kn': ve, 'vn_kn': vn, 'rapidez_kn': rapidez, 'rumbo': rumbo,
        'resto_m': math.hypot(rx, ry), 'muestras': n, 'minutos': round(minutos),
    }


def tolerancia_base(lat: float, lon: float) -> float:
    """Tolerancia base (kn) para la corriente del modelo en ese punto: la medida de su región, o TOL_BASE_KN."""
    for (a, b, c, e), tol, _nombre in TOL_REGIONES:
        if a <= lat <= b and c <= lon <= e:
            return tol
    return TOL_BASE_KN


def esperada(fuerzas: dict) -> dict:
    """Velocidad que tendría un casco SIN propulsión: corriente + VIENTO_K × viento (que sopla hacia lo opuesto de 'desde')."""
    ce, cn = vector(fuerzas['corriente_kn'], fuerzas['corriente_hacia'])
    we, wn = vector(fuerzas['viento_kn'] * VIENTO_K, (fuerzas['viento_desde'] + 180.0) % 360.0)
    ve, vn = ce + we, cn + wn
    rapidez, rumbo = rapidez_rumbo(ve, vn)
    return {'ve_kn': ve, 'vn_kn': vn, 'rapidez_kn': rapidez, 'rumbo': rumbo}


def veredicto(obs: dict, fuerzas: dict) -> dict:
    """Compara lo observado con la deriva pasiva esperada."""
    esp = esperada(fuerzas)
    residuo = math.hypot(obs['ve_kn'] - esp['ve_kn'], obs['vn_kn'] - esp['vn_kn'])
    tol = fuerzas.get('tol_base_kn', TOL_BASE_KN) + TOL_VIENTO * fuerzas['viento_kn'] + TOL_COSTA_KN * min(1.0, fuerzas.get('aprox_km', 0.0) / 10.0)
    s, e = obs['rapidez_kn'], esp['rapidez_kn']
    if s < UMBRAL_QUIETO_KN:
        # Quieto. Sólo es informativo si el agua y el viento lo moverían: entonces algo lo sujeta.
        v = FIJO if e >= tol else INDETERMINADO
    elif residuo <= tol:
        v = DERIVA
    else:
        v = PROPULSION
    return {
        'veredicto': v, 'obs': obs, 'esperada': esp, 'residuo_kn': residuo, 'tolerancia_kn': tol,
        'fuerzas': fuerzas,
    }


# ─── fuerzas (corriente y viento) desde Open-Meteo, con caché por celda ───────

def _celda(lat: float, lon: float) -> tuple[float, float]:
    return round(round(lat / CELDA) * CELDA, 1), round(round(lon / CELDA) * CELDA, 1)


def _clave(c: tuple[float, float]) -> str:
    return f'cables:fuerzas:{c[0]:.1f}:{c[1]:.1f}'


def _consulta(url: str, celdas: list[tuple[float, float]], actual: str, extra: dict | None = None) -> list[dict] | None:
    params = {
        'latitude': ','.join(str(c[0]) for c in celdas), 'longitude': ','.join(str(c[1]) for c in celdas),
        'current': actual, **(extra or {}),
    }
    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        d = r.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning('Open-Meteo no respondió | api=%s | puntos=%d | error=%s', url.split('/')[2], len(celdas), str(exc)[:60])
        return None
    return d if isinstance(d, list) else [d]


MAX_ANILLO = 3            # si la celda es tierra, se busca agua hasta 3 celdas (~33 km) a la redonda
_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


def _vecinos(c: tuple[float, float], anillo: int) -> list[tuple[float, float]]:
    """Celdas a `anillo` celdas de distancia en 8 direcciones, de la más cercana a la más lejana."""
    return [(round(c[0] + dy * anillo * CELDA, 1), round(c[1] + dx * anillo * CELDA, 1)) for dy, dx in _DIRS]


def _corriente_de(item) -> tuple[float, float] | None:
    try:
        a = item['current']
        if a['ocean_current_velocity'] is None or a['ocean_current_direction'] is None:
            return None
        return a['ocean_current_velocity'] / KMH_POR_NUDO, float(a['ocean_current_direction'])
    except (TypeError, KeyError):
        return None


def _clave_agua(c: tuple[float, float]) -> str:
    return f'cables:agua:{c[0]:.1f}:{c[1]:.1f}'


def _corrientes_de(celdas: list[tuple[float, float]]) -> dict | None:
    """
    {celda: (kn, hacia) | None} para cada celda; None si la API falló (no se recuerda nada). Que una celda no tenga
    corriente (tierra) es permanente y se recuerda 24 h; así cada celda de tierra se consulta una sola vez al día.
    """
    claves = {c: _clave_agua(c) for c in celdas}
    hay = cache.get_many(list(claves.values()))
    out: dict = {c: hay[k] if hay[k] != 'tierra' else None for c, k in claves.items() if k in hay}
    faltan = [c for c in celdas if c not in out]
    for i in range(0, len(faltan), 80):
        lote = faltan[i:i + 80]
        r = _consulta(URL_CORRIENTES, lote, 'ocean_current_velocity,ocean_current_direction')
        if r is None or len(r) != len(lote):
            return None
        for c, item in zip(lote, r):
            cor = _corriente_de(item)
            out[c] = cor
            cache.set(claves[c], cor if cor else 'tierra', CACHE_S if cor else 86400)
    return out


def _corriente_cercana(sin: list[tuple[float, float]]) -> dict[tuple[float, float], tuple[float, float, float]]:
    """
    Para celdas sin corriente (tierra o costa), la del agua más cercana hasta MAX_ANILLO celdas:
    {celda: (kn, hacia, distancia_km)}. Es una APROXIMACIÓN: la corriente de la costa difiere de la de mar abierto.
    """
    out: dict = {}
    pendientes = list(sin)
    for anillo in range(1, MAX_ANILLO + 1):
        if not pendientes:
            break
        cand = {v for c in pendientes for v in _vecinos(c, anillo)}
        datos = _corrientes_de(sorted(cand))
        if datos is None:                       # la API falló: no se concluye nada (y no se recuerda)
            break
        for c in pendientes:
            for v in _vecinos(c, anillo):
                cor = datos.get(v)
                if cor:
                    km = math.hypot((v[0] - c[0]) * 111.0, (v[1] - c[1]) * 111.0 * math.cos(math.radians(c[0])))
                    out[c] = (cor[0], cor[1], km)
                    break
        pendientes = [c for c in pendientes if c not in out]
    return out


def fuerzas_para(puntos: list[tuple[float, float]]) -> list[dict | None]:
    """
    Corriente y viento en cada punto (lat, lon): {'corriente_kn','corriente_hacia','viento_kn','viento_desde','aprox_km'}
    o None. `aprox_km` es 0 si la corriente es la de la propia celda y >0 si se tomó la del agua más cercana.
    Se agrupan por celdas de 0,1° y se guardan CACHE_S segundos. Un fallo de la API (red, límite de llamadas) NO se
    recuerda como «sin dato»: se reintenta en 60 s.
    """
    celdas = [_celda(lat, lon) for lat, lon in puntos]
    unicas = list(dict.fromkeys(celdas))
    guardado = cache.get_many([_clave(c) for c in unicas])
    faltan = [c for c in unicas if _clave(c) not in guardado]
    for i in range(0, len(faltan), 40):
        lote = faltan[i:i + 40]
        vie = _consulta(URL_VIENTO, lote, 'wind_speed_10m,wind_direction_10m', {'wind_speed_unit': 'kn'})
        cor = _corrientes_de(lote)
        if vie is None or cor is None or len(vie) != len(lote):
            for c in lote:                                  # fallo de la API: reintentar pronto, sin concluir «sin dato»
                guardado[_clave(c)] = {'sin_dato': True}
                cache.set(_clave(c), guardado[_clave(c)], 60)
            continue
        parcial: dict = {}
        for k, c in enumerate(lote):
            try:
                b = vie[k]['current']
                if b['wind_speed_10m'] is None or b['wind_direction_10m'] is None:
                    continue
                parcial[c] = ({'viento_kn': float(b['wind_speed_10m']), 'viento_desde': float(b['wind_direction_10m'])}, cor.get(c))
            except (TypeError, KeyError, IndexError):
                continue
        cercana = _corriente_cercana([c for c, (_, a) in parcial.items() if a is None])
        for c in lote:
            f = None
            if c in parcial:
                viento, actual = parcial[c]
                if actual:
                    f = {'corriente_kn': actual[0], 'corriente_hacia': actual[1], 'aprox_km': 0.0, **viento}
                elif c in cercana:
                    kn, hacia, km = cercana[c]
                    f = {'corriente_kn': kn, 'corriente_hacia': hacia, 'aprox_km': round(km, 1), **viento}
            if f:
                f['tol_base_kn'] = tolerancia_base(*c)
            guardado[_clave(c)] = f if f else {'sin_dato': True}
            cache.set(_clave(c), guardado[_clave(c)], CACHE_S if f else 600)
    out = []
    for c in celdas:
        f = guardado.get(_clave(c))
        out.append(None if not f or f.get('sin_dato') else f)
    return out
