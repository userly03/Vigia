"""
Estado de un buque respecto de un cable. Reglas simples y explícitas, SIN validar con incidentes reales.

Los umbrales son heurísticas de partida: un buque que arrastra el ancla puede ir a 2–4 nudos y uno fondeado a
~0; ninguna de las dos cosas se distingue sólo con la velocidad. Por eso la salida es un NIVEL DE ATENCIÓN, no una
acusación, y la API devuelve los umbrales usados (`METODO`).
"""
from __future__ import annotations

SOG_NO_DISPONIBLE = 102.3        # el estándar AIS usa 102,3 nudos para «velocidad no disponible»
UMBRAL_PARADO_KN = 0.5
UMBRAL_LENTO_KN = 3.0
MINUTOS_ALTO = 60                # permanencia lenta o parada dentro del corredor para subir a ALTO
RADIO_AMARRE_M = 3000            # cerca de un punto de amarre un buque parado suele estar atracado
HABITUAL_MIN_BUQUES = 5          # buques DISTINTOS detenidos en una misma celda para considerarla puerto o rada
HABITUAL_CELDA_GRADOS = 0.02     # ≈ 2 km
HABITUAL_HORAS = 24
INMOVIL_RADIO_M = 250            # un buque fondeado gira alrededor de su ancla (radio de la cadena): hasta ~250 m sigue «en su sitio»
RECORRIDO_MIN_KM = 15.0          # recorrido continuo dentro del corredor, en marcha, para marcarlo (informativo)
RECORRIDO_HUECO_MIN = 25         # si entre dos posiciones pasan más minutos, no se pueden unir en un recorrido
INMOVIL_MIN_H = 3.0              # horas de pista sin salir de ese radio para considerarlo inmóvil

METODO = {
    'umbral_parado_kn': UMBRAL_PARADO_KN,
    'umbral_lento_kn': UMBRAL_LENTO_KN,
    'minutos_para_alto': MINUTOS_ALTO,
    'radio_amarre_m': RADIO_AMARRE_M,
    'habitual_min_buques': HABITUAL_MIN_BUQUES,
    'habitual_celda_km': round(HABITUAL_CELDA_GRADOS * 111.2),
    'habitual_horas': HABITUAL_HORAS,
    'inmovil_radio_m': INMOVIL_RADIO_M,
    'inmovil_min_h': INMOVIL_MIN_H,
    'recorrido_min_km': RECORRIDO_MIN_KM,
    'recorrido_hueco_min': RECORRIDO_HUECO_MIN,
    'nota': 'Heurísticas sin validar con incidentes reales. Nivel de atención, no acusación. Un buque que declara estar amarrado no genera alerta.',
}

PARADO, LENTO, TRANSITO, SIN_DATO, ATRACADO = 'parado', 'lento', 'transito', 'sin_dato', 'atracado'
NAV_ATRACADO = 5   # NavigationalStatus del AIS: 5 = amarrado (en muelle). El buque lo declara a mano.


def clasificar(sog: float | None, nav: int | None = None) -> str:
    """
    Estado por velocidad sobre el fondo (nudos). Si el buque declara estar amarrado (nav = 5) es «atracado»:
    no genera alerta. OJO: el estado de navegación lo teclea la tripulación y puede estar mal o desactualizado.
    """
    if nav == NAV_ATRACADO:
        return ATRACADO
    if sog is None:
        return SIN_DATO
    try:
        v = float(sog)
    except (TypeError, ValueError):
        return SIN_DATO
    if v != v or v < 0 or v >= SOG_NO_DISPONIBLE:
        return SIN_DATO
    if v < UMBRAL_PARADO_KN:
        return PARADO
    if v < UMBRAL_LENTO_KN:
        return LENTO
    return TRANSITO


def nivel_alerta(
    estado: str,
    en_corredor: bool,
    minutos_lento: float = 0.0,
    cerca_de_amarre: bool = False,
    veredicto: str | None = None,
    habitual: bool = False,
    inmovil_h: float = 0.0,
) -> str | None:
    """
    Nivel de atención: None | 'BAJO' | 'MEDIO' | 'ALTO'.

    Sin veredicto de la prueba de deriva pasiva (faltan muestras o fuerzas):
    - fuera del corredor, en tránsito o amarrado: sin alerta;
    - parado cerca de un punto de amarre: BAJO (probablemente atracado);
    - lento o parado en el corredor: MEDIO, y ALTO si lleva al menos MINUTOS_ALTO así.
    Con veredicto (ver deriva.py):
    - 'propulsion' yendo lento: ALTO. Se mueve y el agua no lo explica: propulsión, o algo lo arrastra;
    - 'deriva': MEDIO (sin gobierno sobre un cable), ALTO si lleva MINUTOS_ALTO o más;
    - 'fijo': BAJO, MEDIO si lleva MINUTOS_ALTO o más. Fondeado sobre un cable es una infracción, no un arrastre.
    En una zona de estacionamiento habitual (puerto o rada: ≥ HABITUAL_MIN_BUQUES buques distintos detenidos en la misma celda)
    un buque parado o lento es BAJO, salvo que la prueba diga «propulsión» (se mueve y el agua no lo explica).
    Un buque INMÓVIL (≥ INMOVIL_MIN_H horas sin salir de INMOVIL_RADIO_M) no arrastra ni deriva: el ALTO baja a MEDIO (sigue
    siendo un fondeo o atraque sobre el corredor, pero no una trayectoria). «Propulsión» se mantiene en ALTO (puede ser un buque
    que se sostiene en el sitio con sus máquinas, p. ej. de posicionamiento dinámico).
    """
    if not en_corredor or estado in (TRANSITO, SIN_DATO, ATRACADO):
        return None
    if cerca_de_amarre and estado == PARADO:
        return 'BAJO'
    largo = minutos_lento >= MINUTOS_ALTO
    if habitual and veredicto != 'propulsion':
        return 'BAJO'
    if veredicto == 'propulsion' and estado == LENTO:
        return 'ALTO'
    if veredicto == 'fijo':
        return 'MEDIO' if largo else 'BAJO'
    nivel = 'ALTO' if largo else 'MEDIO'          # 'deriva' o sin veredicto
    if nivel == 'ALTO' and inmovil_h >= INMOVIL_MIN_H:
        return 'MEDIO'
    return nivel


def minutos_lento_consecutivos(muestras: list[tuple]) -> float:
    """
    `muestras`: [(datetime, sog, en_corredor, …), ...] (los campos extra se ignoran) ordenadas de la MÁS RECIENTE a la más antigua.
    Devuelve los minutos que el buque lleva, sin interrupción, lento o parado DENTRO del corredor,
    contados desde la muestra más reciente hacia atrás.
    """
    if not muestras:
        return 0.0
    mas_reciente = muestras[0][0]
    ultimo_ok = None
    for m in muestras:
        ts, sog, dentro = m[0], m[1], m[2]
        if dentro and clasificar(sog) in (PARADO, LENTO):
            ultimo_ok = ts
        else:
            break
    if ultimo_ok is None:
        return 0.0
    return max(0.0, (mas_reciente - ultimo_ok).total_seconds() / 60.0)


def horas_inmovil(puntos: list[tuple]) -> float:
    """
    `puntos`: [(datetime, lat, lon), …] en cualquier orden. Si TODOS caen a menos de INMOVIL_RADIO_M del punto medio
    devuelve las horas que cubre la pista; si no (o con una sola muestra) devuelve 0.
    """
    import math
    if len(puntos) < 2:
        return 0.0
    la = sorted(p[1] for p in puntos)[len(puntos) // 2]
    lo = sorted(p[2] for p in puntos)[len(puntos) // 2]
    k = math.cos(math.radians(la))
    for _, y, x in puntos:
        if math.hypot((y - la) * 111_320.0, (x - lo) * 111_320.0 * k) > INMOVIL_RADIO_M:
            return 0.0
    ts = [p[0] for p in puntos]
    return (max(ts) - min(ts)).total_seconds() / 3600.0


def recorrido_continuo_km(puntos: list[tuple]) -> float:
    """
    `puntos`: [(datetime, lat, lon, dentro_del_corredor), …] en cualquier orden. Kilómetros que lleva el buque, hasta su posición
    más reciente, DENTRO del corredor sin interrupción: se corta si sale del corredor o si faltan más de RECORRIDO_HUECO_MIN
    minutos entre dos posiciones (con huecos no se sabe qué hizo). 0 si la posición más reciente está fuera del corredor.
    """
    import math
    orden = sorted(puntos, key=lambda p: p[0], reverse=True)
    if not orden or not orden[0][3]:
        return 0.0
    km = 0.0
    for a, b in zip(orden, orden[1:]):
        if not b[3] or (a[0] - b[0]).total_seconds() > RECORRIDO_HUECO_MIN * 60:
            break
        km += math.hypot((a[1] - b[1]) * 111.32, (a[2] - b[2]) * 111.32 * math.cos(math.radians(a[1])))
    return km
