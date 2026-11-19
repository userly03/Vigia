"""
Genera tráfico AIS SIMULADO para probar y demostrar el Vigía sin depender de AISstream.

TODO lo que escribe va rotulado: cada posición lleva `simulado: true`, los nombres empiezan por «SIM ·», los MMSI por
«9990», y la API y la pantalla lo muestran. Nada de esto es tráfico real ni debe presentarse como tal.

  python manage.py simular_ais --buques 400            # corre hasta Ctrl+C
  python manage.py simular_ais --ciclos 1 --sin-historial

Incluye escenarios guionados sobre cables reales de la base, uno por cada veredicto de la prueba de deriva pasiva:
un buque que avanza despacio sobre un cable sin que el agua lo explique (propulsión → ALTO), uno que va a la deriva
con la corriente y el viento reales de ese punto (deriva), uno fondeado (fijo), uno amarrado junto a un punto de
amarre (BAJO) y uno que deja de transmitir dentro de un corredor (silencio).
"""
import json
import math
import random
import time
from datetime import timedelta

from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from mares.apps.cables import deriva
from mares.apps.detection import tasks as ais_tasks
from mares.apps.detection.models import AISPosicion

PREFIJO = '9990'


def _caja(zona):
    (lat1, lon1), (lat2, lon2) = zona
    return min(lat1, lat2), min(lon1, lon2), max(lat1, lat2), max(lon1, lon2)


def _punto_en_cable(caja, rng, cerca_de_amarre=False):
    """(slug, nombre, lon, lat, rumbo_del_cable) de un punto sobre un cable real dentro de la caja, o None."""
    lat0, lon0, lat1, lon1 = caja
    sql = """
      SELECT c.slug, c.nombre, ST_X(q.pt), ST_Y(q.pt),
             degrees(ST_Azimuth(ST_LineInterpolatePoint(t.geom, 0.45), ST_LineInterpolatePoint(t.geom, 0.55)))
      FROM cables_tramo t JOIN cables_cable c ON c.id = t.cable_id
      CROSS JOIN LATERAL (SELECT ST_LineInterpolatePoint(t.geom, 0.5) AS pt) q
      {extra}
      WHERE t.corredor IS NOT NULL AND ST_Within(q.pt, ST_MakeEnvelope(%s, %s, %s, %s, 4326))
      ORDER BY random() LIMIT 1
    """
    if cerca_de_amarre:
        extra = "JOIN cables_punto_amarre a ON ST_DWithin(a.geom::geography, q.pt::geography, 1800)"
    else:
        extra = ''
    with connection.cursor() as cur:
        cur.execute(sql.format(extra=extra), [lon0, lat0, lon1, lat1])
        return cur.fetchone()


class Buque:
    def __init__(self, mmsi, nombre, lon, lat, sog, rumbo, caja, fijo=False, nav=0, recto=False):
        self.mmsi, self.nombre, self.lon, self.lat = mmsi, nombre, lon, lat
        self.sog, self.rumbo, self.caja, self.fijo = sog, rumbo, caja, fijo
        self.nav, self.recto = nav, recto      # recto: rumbo constante (sin el vaivén aleatorio)

    def avanzar(self, dt_s, rng):
        if self.fijo or self.sog < 0.3:
            self.lat += rng.uniform(-1, 1) * 1e-5
            self.lon += rng.uniform(-1, 1) * 1e-5
            return
        km = self.sog * 1.852 * dt_s / 3600.0
        r = math.radians(self.rumbo)
        self.lat += km * math.cos(r) / 111.195
        self.lon += km * math.sin(r) / (111.195 * max(0.2, math.cos(math.radians(self.lat))))
        lat0, lon0, lat1, lon1 = self.caja
        if not (lat0 < self.lat < lat1):
            self.rumbo = (180 - self.rumbo) % 360
            self.lat = min(max(self.lat, lat0 + 1e-3), lat1 - 1e-3)
        if not (lon0 < self.lon < lon1):
            self.rumbo = (360 - self.rumbo) % 360
            self.lon = min(max(self.lon, lon0 + 1e-3), lon1 - 1e-3)
        if not self.recto:
            self.rumbo = (self.rumbo + random.uniform(-1.5, 1.5)) % 360

    def publicar(self):
        pos = {
            'mmsi': self.mmsi, 'vessel_name': self.nombre, 'lat': self.lat, 'lng': self.lon,
            'timestamp': timezone.now().isoformat(), 'velocidad_nudos': round(self.sog, 1),
            'rumbo': round(self.rumbo, 1), 'nav': self.nav, 'bandera': '', 'simulado': True,
        }
        cache.set(f'ais:live:{self.mmsi}', json.dumps(pos), 900)
        ais_tasks._actualizar_indice(cache, self.mmsi)


class Command(BaseCommand):
    help = 'Genera tráfico AIS SIMULADO (rotulado) sobre las zonas y cables reales de la base.'

    def add_arguments(self, parser):
        parser.add_argument('--buques', type=int, default=400)
        parser.add_argument('--intervalo', type=float, default=5.0, help='Segundos entre actualizaciones.')
        parser.add_argument('--ciclos', type=int, default=0, help='0 = hasta Ctrl+C.')
        parser.add_argument('--semilla', type=int, default=7)
        parser.add_argument('--sin-historial', action='store_true')

    def handle(self, *args, **o):
        rng = random.Random(o['semilla'])
        zonas = {n: _caja(z) for n, z in settings.AISSTREAM_ZONAS.items()}
        nombres = list(zonas)
        buques: list[Buque] = []
        ahora = timezone.now()
        hist: list[AISPosicion] = []

        def escenario(clave, nombre, zona, ve=0.0, vn=0.0, rumbo_cable=False, sog_cable=0.0, minutos_hist=0, nav=0,
                      amarre=False, silencio_min=0, con_agua=False, agua_fuerte=False):
            """Un buque guionado. Se mueve con (ve, vn) nudos; con `rumbo_cable` avanza a `sog_cable` nudos a lo largo del cable;
            con `con_agua` va a la deriva con la corriente y el viento REALES de ese punto (Open-Meteo)."""
            pto, f = None, None
            for _ in range(15 if (con_agua or rumbo_cable or agua_fuerte) else 1):       # se busca un punto con datos de agua (y, para la deriva, que se mueva)
                pto = _punto_en_cable(zonas[zona], rng, cerca_de_amarre=amarre)
                if not pto:
                    break
                if con_agua or rumbo_cable or agua_fuerte:
                    f = deriva.fuerzas_para([(pto[3] + 0.002, pto[2])])[0]
                    minimo = 0.8 if con_agua else 1.1 if agua_fuerte else 0.0   # que el agua mueva lo bastante para distinguir
                    if f and deriva.esperada(f)['rapidez_kn'] >= minimo:
                        break
            if not pto or ((con_agua or rumbo_cable or agua_fuerte) and not f):
                self.stderr.write(f'  (sin cable o sin corriente utilizable en «{zona}»: escenario {clave} omitido)')
                return
            slug, cable, lon, lat, az = pto
            lat += 0.002
            if con_agua:
                e = deriva.esperada(f)
                ve, vn = e['ve_kn'], e['vn_kn']
            elif rumbo_cable:
                ve, vn = deriva.vector(sog_cable, az)
            rapidez, rumbo = deriva.rapidez_rumbo(ve, vn)
            mmsi = f'{PREFIJO}{clave}'
            if silencio_min:
                for k in range(0, 4):
                    hist.append(AISPosicion(mmsi=mmsi, vessel_name=nombre, posicion=Point(lon, lat, srid=4326),
                                            timestamp=ahora - timedelta(minutes=silencio_min + 10 * k), velocidad_nudos=0.2, nav=nav))
                self.stdout.write(f'  {nombre}: silencio en «{cable}» ({zona})')
                return
            kx = 111_320.0 * math.cos(math.radians(lat))
            for k in range(1, minutos_hist // 10 + 1):       # pista hacia atrás con la misma velocidad
                s = k * 600
                hist.append(AISPosicion(
                    mmsi=mmsi, vessel_name=nombre, timestamp=ahora - timedelta(seconds=s), velocidad_nudos=round(rapidez, 1), nav=nav,
                    posicion=Point(lon - ve * 1852 / 3600 * s / kx, lat - vn * 1852 / 3600 * s / 110_540.0, srid=4326),
                ))
            buques.append(Buque(mmsi, nombre, lon, lat, rapidez, rumbo, zonas[zona], fijo=rapidez < 0.3, nav=nav, recto=True))
            self.stdout.write(f'  {nombre}: sobre «{cable}» ({zona}) a {rapidez:.1f} kn')

        self.stdout.write('Escenarios guionados (SIMULADOS):')
        escenario('001', 'SIM · PROPULSIÓN (avanza 1,8 kn por el cable)', 'Báltico', rumbo_cable=True, sog_cable=1.8, minutos_hist=60)
        escenario('002', 'SIM · DERIVA (con el agua y el viento reales)', 'Mar del Norte y Canal', con_agua=True, minutos_hist=70)
        escenario('003', 'SIM · FIJO (fondeado 90 min)', 'Mar del Norte y Canal', nav=1, minutos_hist=90, agua_fuerte=True)
        escenario('004', 'SIM · AMARRADO (junto a un punto de amarre)', 'Mar del Norte y Canal', nav=0, amarre=True)
        escenario('005', 'SIM · SILENCIO', 'Mar Rojo y Golfo de Adén', silencio_min=120)

        n = max(0, o['buques'])
        for i in range(n):
            zona = rng.choice(nombres)
            lat0, lon0, lat1, lon1 = zonas[zona]
            parado = rng.random() < 0.08
            buques.append(Buque(
                f'{PREFIJO}{1000 + i}', f'SIM · {i:04d}', rng.uniform(lon0, lon1), rng.uniform(lat0, lat1),
                0.0 if parado else rng.uniform(7, 18), rng.uniform(0, 360), zonas[zona],
            ))

        if hist and not o['sin_historial']:
            AISPosicion.objects.filter(mmsi__startswith=PREFIJO).delete()
            AISPosicion.objects.bulk_create(hist)
        self.stdout.write(self.style.WARNING(f'{len(buques)} buques SIMULADOS (MMSI {PREFIJO}…). Ctrl+C para detener.'))

        ciclo = 0
        try:
            while True:
                for b in buques:
                    b.avanzar(o['intervalo'], rng)
                    b.publicar()
                ciclo += 1
                if o['ciclos'] and ciclo >= o['ciclos']:
                    break
                time.sleep(o['intervalo'])
        except KeyboardInterrupt:
            self.stdout.write('\nDetenido.')
