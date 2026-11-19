import json
from datetime import timedelta

from unittest import mock

from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from mares.apps.cables import estados
from mares.apps.cables.loader import agrupar_cables, cargar, partir_antimeridiano
from mares.apps.cables.models import Cable, PuntoAmarre
from mares.apps.detection.models import AISPosicion


class EstadosTests(SimpleTestCase):
    def test_clasificar_por_velocidad(self):
        self.assertEqual(estados.clasificar(0.0), estados.PARADO)
        self.assertEqual(estados.clasificar(0.49), estados.PARADO)
        self.assertEqual(estados.clasificar(0.5), estados.LENTO)
        self.assertEqual(estados.clasificar(2.9), estados.LENTO)
        self.assertEqual(estados.clasificar(3.0), estados.TRANSITO)
        self.assertEqual(estados.clasificar(14), estados.TRANSITO)

    def test_amarrado_no_genera_alerta(self):
        self.assertEqual(estados.clasificar(0.0, nav=5), estados.ATRACADO)
        self.assertEqual(estados.clasificar(8.0, nav=5), estados.ATRACADO)     # lo declarado manda
        self.assertEqual(estados.clasificar(0.0, nav=1), estados.PARADO)       # fondeado sigue contando
        self.assertIsNone(estados.nivel_alerta(estados.ATRACADO, True, minutos_lento=999))

    def test_velocidad_no_disponible_o_invalida(self):
        for v in (None, 102.3, 150, -1, 'x', float('nan')):
            self.assertEqual(estados.clasificar(v), estados.SIN_DATO, v)

    def test_nivel_alerta(self):
        f = estados.nivel_alerta
        self.assertIsNone(f(estados.PARADO, en_corredor=False))
        self.assertIsNone(f(estados.TRANSITO, en_corredor=True))
        self.assertIsNone(f(estados.SIN_DATO, en_corredor=True))
        self.assertEqual(f(estados.LENTO, True, minutos_lento=10), 'MEDIO')
        self.assertEqual(f(estados.PARADO, True, minutos_lento=59.9), 'MEDIO')
        self.assertEqual(f(estados.PARADO, True, minutos_lento=60), 'ALTO')
        self.assertEqual(f(estados.PARADO, True, minutos_lento=500, cerca_de_amarre=True), 'BAJO')
        # cerca de un amarre pero en movimiento lento: no se rebaja
        self.assertEqual(f(estados.LENTO, True, minutos_lento=500, cerca_de_amarre=True), 'ALTO')

    def test_nivel_con_veredicto_de_deriva_pasiva(self):
        f = estados.nivel_alerta
        self.assertEqual(f(estados.LENTO, True, 10, veredicto='propulsion'), 'ALTO')
        self.assertEqual(f(estados.PARADO, True, 10, veredicto='propulsion'), 'MEDIO')   # parado no es propulsión: regla simple
        self.assertEqual(f(estados.LENTO, True, 10, veredicto='deriva'), 'MEDIO')
        self.assertEqual(f(estados.LENTO, True, 60, veredicto='deriva'), 'ALTO')
        self.assertEqual(f(estados.PARADO, True, 10, veredicto='fijo'), 'BAJO')
        self.assertEqual(f(estados.PARADO, True, 60, veredicto='fijo'), 'MEDIO')
        self.assertEqual(f(estados.PARADO, True, 500, veredicto='indeterminado'), 'ALTO')
        self.assertIsNone(f(estados.TRANSITO, True, 10, veredicto='propulsion'))

    def test_zona_habitual_baja_el_nivel_salvo_propulsion(self):
        f = estados.nivel_alerta
        self.assertEqual(f(estados.PARADO, True, 500, habitual=True), 'BAJO')              # antes habría sido ALTO
        self.assertEqual(f(estados.LENTO, True, 10, veredicto='deriva', habitual=True), 'BAJO')
        self.assertEqual(f(estados.LENTO, True, 10, veredicto='propulsion', habitual=True), 'ALTO')   # se mueve y el agua no lo explica
        self.assertIsNone(f(estados.TRANSITO, True, 10, habitual=True))

    def test_recorrido_continuo_km(self):
        from datetime import datetime, timedelta, timezone as tz
        t0 = datetime(2026, 11, 18, 10, 0, tzinfo=tz.utc)
        # 7 posiciones cada 10 min a 0,05° de longitud en el ecuador (≈ 5,6 km por tramo): ≈ 33 km
        seguido = [(t0 + timedelta(minutes=10 * k), 0.0, 0.05 * k, True) for k in range(7)]
        self.assertAlmostEqual(estados.recorrido_continuo_km(seguido), 6 * 0.05 * 111.32, places=1)
        self.assertEqual(estados.recorrido_continuo_km(seguido[::-1]), estados.recorrido_continuo_km(seguido))   # el orden da igual
        salio = [(t0 + timedelta(minutes=10 * k), 0.0, 0.05 * k, k != 2) for k in range(7)]                       # sale del corredor en k=2
        self.assertAlmostEqual(estados.recorrido_continuo_km(salio), 3 * 0.05 * 111.32, places=1)                 # solo cuenta lo posterior
        hueco = [(t0, 0.0, 0.0, True), (t0 + timedelta(minutes=40), 0.0, 0.3, True)]
        self.assertEqual(estados.recorrido_continuo_km(hueco), 0.0)                                              # 40 min sin datos: no se une
        self.assertEqual(estados.recorrido_continuo_km([(t0, 0.0, 0.0, False), (t0 - timedelta(minutes=5), 0.0, 0.01, True)]), 0.0)

    def test_horas_inmovil(self):
        from datetime import datetime, timedelta, timezone as tz
        t0 = datetime(2026, 11, 18, 10, 0, tzinfo=tz.utc)
        quieto = [(t0 + timedelta(minutes=30 * k), 59.3120 + (k % 2) * 0.0004, 18.1300) for k in range(11)]   # 5 h, ~45 m de vaivén
        self.assertAlmostEqual(estados.horas_inmovil(quieto), 5.0, places=2)
        deriva = quieto[:-1] + [(t0 + timedelta(hours=5), 59.3200, 18.1300)]                                    # un punto a ~1 km
        self.assertEqual(estados.horas_inmovil(deriva), 0.0)
        self.assertEqual(estados.horas_inmovil(quieto[:1]), 0.0)

    def test_inmovil_baja_alto_a_medio_pero_no_la_propulsion(self):
        self.assertEqual(estados.nivel_alerta('parado', True, 300), 'ALTO')
        self.assertEqual(estados.nivel_alerta('parado', True, 300, inmovil_h=5.0), 'MEDIO')
        self.assertEqual(estados.nivel_alerta('parado', True, 300, inmovil_h=2.0), 'ALTO')               # menos de 3 h: no cuenta
        self.assertEqual(estados.nivel_alerta('lento', True, 300, veredicto='propulsion', inmovil_h=5.0), 'ALTO')

    def test_minutos_lento_consecutivos(self):
        t = timezone.now()
        m = lambda mins, sog, dentro: (t - timedelta(minutes=mins), sog, dentro)  # noqa: E731
        self.assertEqual(estados.minutos_lento_consecutivos([]), 0.0)
        # lento 0, 10, 20 min atrás dentro del corredor; a los 30 min iba rápido -> se corta
        self.assertAlmostEqual(estados.minutos_lento_consecutivos([m(0, 1, True), m(10, 0, True), m(20, 2, True), m(30, 9, True)]), 20.0)
        # salió del corredor a los 15 min: se corta ahí
        self.assertAlmostEqual(estados.minutos_lento_consecutivos([m(0, 1, True), m(10, 1, True), m(15, 1, False), m(20, 1, True)]), 10.0)
        # la muestra más reciente ya no es lenta
        self.assertEqual(estados.minutos_lento_consecutivos([m(0, 12, True), m(10, 0, True)]), 0.0)


class LoaderTests(TestCase):
    def test_partir_antimeridiano(self):
        partes = partir_antimeridiano([[170, 0], [179, 1], [-179, 2], [-170, 3]])
        self.assertEqual(len(partes), 2)
        self.assertEqual(partes[0][-1], [179, 1])
        self.assertEqual(partes[1][0], [-179, 2])

    def test_longitudes_fuera_de_rango_se_normalizan(self):
        partes = partir_antimeridiano([[170, 0], [190, 1]])  # 190 -> -170: salta, se parte y la 2ª parte queda corta
        self.assertEqual(partes, [])

    def test_agrupar_une_tramos_del_mismo_cable(self):
        fc = {'features': [
            {'properties': {'id': 'a', 'name': 'A', 'color': '#111'}, 'geometry': {'type': 'MultiLineString', 'coordinates': [[[0, 0], [1, 0]]]}},
            {'properties': {'id': 'a', 'name': 'A', 'color': '#111'}, 'geometry': {'type': 'LineString', 'coordinates': [[1, 0], [2, 0]]}},
            {'properties': {'id': 'b'}, 'geometry': {'type': 'Point', 'coordinates': [0, 0]}},   # se ignora
            {'properties': {}, 'geometry': {'type': 'LineString', 'coordinates': [[0, 0], [1, 1]]}},  # sin id
        ]}
        cab = agrupar_cables(fc)
        self.assertEqual(list(cab), ['a'])
        self.assertEqual(len(cab['a']['lineas']), 2)

    def test_cargar_crea_corredor_y_sincroniza(self):
        fc = {'features': [{'properties': {'id': 'x', 'name': 'X'}, 'geometry': {'type': 'LineString', 'coordinates': [[0, 0], [0.5, 0]]}}]}
        am = {'features': [{'properties': {'id': 'l-1', 'name': 'Lima, Peru'}, 'geometry': {'type': 'Point', 'coordinates': [0, 0]}}]}
        res = cargar(fc, am)
        self.assertEqual(res, {'cables': 1, 'borrados': 0, 'amarres': 1, 'tramos': 2, 'sin_corredor': 0})
        c = Cable.objects.get(slug='x')
        self.assertEqual(c.tramos.count(), 2)  # 55,6 km a tramos de 50 km
        self.assertAlmostEqual(c.longitud_km, 55.6, delta=0.5)
        self.assertEqual(PuntoAmarre.objects.get().pais, 'Peru')
        # una segunda carga sin ese cable lo borra
        fc2 = {'features': [{'properties': {'id': 'y', 'name': 'Y'}, 'geometry': {'type': 'LineString', 'coordinates': [[1, 1], [2, 1]]}}]}
        res = cargar(fc2, am)
        self.assertEqual(res['borrados'], 1)
        self.assertEqual(list(Cable.objects.values_list('slug', flat=True)), ['y'])


def _poner_vivo(mmsi, lon, lat, sog, nombre='', ts=None, nav=None):
    cache.set(f'ais:live:{mmsi}', json.dumps({
        'mmsi': mmsi, 'vessel_name': nombre, 'lat': lat, 'lng': lon, 'velocidad_nudos': sog, 'rumbo': 90.0, 'nav': nav,
        'timestamp': (ts or timezone.now()).isoformat(),
    }), 900)


def _indice(*mmsis):
    cache.set('ais:live:mmsi_index', json.dumps(list(mmsis)), 900)


class ApiCablesTests(TestCase):
    """Cable a lo largo del ecuador de 0° a 0,5°E; corredor de 2 km. Punto de amarre en (0,0)."""

    @classmethod
    def setUpTestData(cls):
        cargar(
            {'features': [{'properties': {'id': 'eq', 'name': 'Ecuador-1', 'color': '#0ff'}, 'geometry': {'type': 'LineString', 'coordinates': [[0, 0], [0.5, 0]]}}]},
            {'features': [{'properties': {'id': 'p0', 'name': 'Punto Cero, Atlantis'}, 'geometry': {'type': 'Point', 'coordinates': [0, 0]}}]},
        )

    def setUp(self):
        cache.clear()
        p = mock.patch('mares.apps.cables.views.fuerzas_para', side_effect=lambda pts: [None for _ in pts])   # las pruebas no usan la red
        p.start()
        self.addCleanup(p.stop)

    def test_cables_es_publico_y_devuelve_geojson(self):
        r = self.client.get('/api/v1/cables/')   # sin sesión
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d['type'], 'FeatureCollection')
        self.assertEqual(d['features'][0]['properties']['nombre'], 'Ecuador-1')
        self.assertEqual(d['features'][0]['geometry']['type'], 'MultiLineString')
        self.assertIn('TeleGeography', d['atribucion'])

    def test_amarres_es_publico(self):
        r = self.client.get('/api/v1/cables/amarres/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['features'][0]['properties']['pais'], 'Atlantis')

    def test_buques_vacio_sin_ais(self):
        r = self.client.get('/api/v1/cables/buques/')
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d['features'], [])
        self.assertEqual(d['meta']['total'], 0)
        self.assertIn('umbral_lento_kn', d['meta']['metodo'])
        self.assertTrue(d['meta']['zonas'])

    def _buques(self):
        r = self.client.get('/api/v1/cables/buques/')
        self.assertEqual(r.status_code, 200)
        d = r.json()
        return {f['properties']['mmsi']: f['properties'] for f in d['features']}, d

    def test_niveles_de_atencion(self):
        _poner_vivo('100', 0.25, 0.005, 0.0, 'PARADO EN CABLE')        # ~550 m del cable, parado, sin historial
        _poner_vivo('200', 0.25, 0.005, 12.0, 'EN TRANSITO')           # misma posición pero navegando
        _poner_vivo('300', 0.25, 0.50, 0.0, 'LEJOS')                   # a ~55 km
        _poner_vivo('400', 0.25, 0.01, 1.0, 'LENTO DESDE HACE RATO')   # ~1,1 km, lento
        _poner_vivo('500', 0.01, 0.002, 0.0, 'ATRACADO')               # ~1,1 km del amarre
        _indice('100', '200', '300', '400', '500')
        ahora = timezone.now()
        for k in range(1, 11):  # 100 min de historial lento dentro del corredor para '400'
            AISPosicion.objects.create(mmsi='400', posicion=Point(0.25, 0.01, srid=4326), timestamp=ahora - timedelta(minutes=10 * k), velocidad_nudos=1.0)

        b, d = self._buques()
        self.assertEqual(b['100']['estado'], 'parado')
        self.assertEqual(b['100']['cable'], 'eq')
        self.assertEqual(b['100']['alerta'], 'MEDIO')
        self.assertLess(b['100']['dist_m'], 700)
        self.assertEqual(b['200']['estado'], 'transito')
        self.assertIsNone(b['200']['alerta'])
        self.assertNotIn('cable', b['300'])
        self.assertEqual(b['400']['alerta'], 'ALTO')
        self.assertGreaterEqual(b['400']['minutos'], 60)
        self.assertEqual(b['500']['alerta'], 'BAJO')
        self.assertEqual(d['meta']['en_corredor'], 4)
        self.assertEqual(d['meta']['alertas'], {'ALTO': 1, 'MEDIO': 1, 'BAJO': 1})

    def test_buque_quieto_horas_en_corredor_es_medio_y_el_que_se_mueve_sigue_alto(self):
        _poner_vivo('700', 0.25, 0.005, 0.0, 'QUIETO 5 H')
        _poner_vivo('710', 0.25, 0.006, 0.3, 'SE MUEVE')
        _indice('700', '710')
        ahora = timezone.now()
        for k in range(1, 31):   # 5 h cada 10 min
            AISPosicion.objects.create(mmsi='700', posicion=Point(0.25, 0.005 + (k % 2) * 0.0002, srid=4326), timestamp=ahora - timedelta(minutes=10 * k), velocidad_nudos=0.0)
            AISPosicion.objects.create(mmsi='710', posicion=Point(0.25 + k * 0.0006, 0.006, srid=4326), timestamp=ahora - timedelta(minutes=10 * k), velocidad_nudos=0.3)
        b, _ = self._buques()
        self.assertEqual(b['700']['alerta'], 'MEDIO')
        self.assertGreaterEqual(b['700']['inmovil_h'], 3)
        self.assertEqual(b['710']['alerta'], 'ALTO')
        self.assertEqual(b['710']['inmovil_h'], 0)

    def test_recorrido_largo_en_marcha_dentro_del_corredor_se_marca_sin_subir_el_nivel(self):
        _poner_vivo('800', 0.45, 0.005, 12.0, 'LARGO')      # en marcha, ~550 m del cable
        _poner_vivo('810', 0.45, 0.005, 12.0, 'CON HUECO')
        _poner_vivo('820', 0.45, 0.005, 12.0, 'CRUZA')
        _indice('800', '810', '820')
        ahora = timezone.now()
        for k in range(1, 7):                                  # 6 posiciones cada 10 min, ≈ 3,7 km cada una → ≈ 22 km dentro
            AISPosicion.objects.create(mmsi='800', posicion=Point(0.45 - 0.0333 * k, 0.005, srid=4326), timestamp=ahora - timedelta(minutes=10 * k), velocidad_nudos=12.0)
            AISPosicion.objects.create(mmsi='810', posicion=Point(0.45 - 0.0333 * k, 0.005, srid=4326), timestamp=ahora - timedelta(minutes=40 * k), velocidad_nudos=12.0)   # cada 40 min
            AISPosicion.objects.create(mmsi='820', posicion=Point(0.45 - 0.0333 * k, 0.05 + 0.01 * k, srid=4326), timestamp=ahora - timedelta(minutes=10 * k), velocidad_nudos=12.0)   # viene de fuera
        b, d = self._buques()
        self.assertGreaterEqual(b['800']['recorrido_km'], 15)
        self.assertIsNone(b['800']['alerta'])                  # informativo: en marcha no genera nivel
        self.assertNotIn('recorrido_km', b['810'])
        self.assertNotIn('recorrido_km', b['820'])
        self.assertEqual(d['meta']['recorridos'], 1)

    def test_buque_amarrado_en_corredor_no_alerta(self):
        _poner_vivo('50', 0.25, 0.005, 0.0, 'EN MUELLE', nav=5)
        _poner_vivo('51', 0.25, 0.005, 0.0, 'FONDEADO', nav=1)
        _indice('50', '51')
        b, d = self._buques()
        self.assertEqual(b['50']['estado'], 'atracado')
        self.assertIsNone(b['50']['alerta'])
        self.assertEqual(b['51']['alerta'], 'MEDIO')   # anclar sobre un cable es justo lo que se vigila
        self.assertEqual(d['meta']['alertas'], {'ALTO': 0, 'MEDIO': 1, 'BAJO': 0})

    def test_el_historial_fuera_del_corredor_no_cuenta(self):
        _poner_vivo('600', 0.25, 0.005, 0.0)
        _indice('600')
        AISPosicion.objects.create(mmsi='600', posicion=Point(0.25, 0.5, srid=4326), timestamp=timezone.now() - timedelta(minutes=90), velocidad_nudos=0.0)
        b, _ = self._buques()
        self.assertEqual(b['600']['alerta'], 'MEDIO')   # llegó hace poco: no hay 60 min dentro

    def test_silencio_en_corredor(self):
        AISPosicion.objects.create(mmsi='700', vessel_name='SE FUE', posicion=Point(0.25, 0.003, srid=4326),
                                   timestamp=timezone.now() - timedelta(hours=2), velocidad_nudos=0.2)
        AISPosicion.objects.create(mmsi='800', vessel_name='RECIENTE', posicion=Point(0.25, 0.003, srid=4326),
                                   timestamp=timezone.now() - timedelta(minutes=10), velocidad_nudos=0.2)
        AISPosicion.objects.create(mmsi='900', vessel_name='FUERA', posicion=Point(0.25, 0.5, srid=4326),
                                   timestamp=timezone.now() - timedelta(hours=2), velocidad_nudos=0.2)
        _, d = self._buques()
        mm = {s['mmsi']: s for s in d['silencios']}
        self.assertEqual(list(mm), ['700'])
        self.assertAlmostEqual(mm['700']['minutos_sin_senal'], 120, delta=2)
        self.assertEqual(mm['700']['cable'], 'eq')

    def test_posiciones_corruptas_se_ignoran(self):
        cache.set('ais:live:1', 'esto no es json', 900)
        cache.set('ais:live:2', json.dumps({'mmsi': '2', 'lat': 999, 'lng': 0}), 900)
        _poner_vivo('3', 0.25, 0.005, 0.0)
        _indice('1', '2', '3')
        b, _ = self._buques()
        self.assertEqual(list(b), ['3'])


class AntimeridianoTests(TestCase):
    """Un cable que cruza ±180° no puede tener polígono de corredor (saldría de ancho mundial): se usa distancia directa."""

    @classmethod
    def setUpTestData(cls):
        cargar({'features': [{'properties': {'id': 'pac', 'name': 'Pacifico-1'}, 'geometry': {
            'type': 'LineString', 'coordinates': [[178, 10], [179.95, 10], [-179.95, 10], [-178, 10]]}}]})

    def setUp(self):
        cache.clear()
        p = mock.patch('mares.apps.cables.views.fuerzas_para', side_effect=lambda pts: [None for _ in pts])   # las pruebas no usan la red
        p.start()
        self.addCleanup(p.stop)

    def test_corredor_nulo_y_cable_partido(self):
        c = Cable.objects.get(slug='pac')
        self.assertEqual(len(c.geom), 2)           # dos partes, una a cada lado del antimeridiano
        self.assertGreaterEqual(c.tramos.filter(corredor__isnull=True).count(), 1)   # los que tocan ±180° no tienen polígono
        self.assertGreaterEqual(c.tramos.filter(corredor__isnull=False).count(), 1)
        self.assertGreater(c.longitud_km, 300)

    def test_buque_cerca_del_cable_sin_corredor_se_detecta(self):
        _poner_vivo('10', 179.8, 10.005, 0.0, 'CERCA')     # ~550 m del último tramo del lado este (sin polígono)
        _poner_vivo('11', 179.8, 10.2, 0.0, 'LEJOS')       # ~22 km
        _poner_vivo('12', -179.8, 10.005, 0.0, 'OTRO LADO')  # ~550 m del primer tramo del lado oeste (sin polígono)
        _indice('10', '11', '12')
        r = self.client.get('/api/v1/cables/buques/')
        b = {f['properties']['mmsi']: f['properties'] for f in r.json()['features']}
        self.assertEqual(b['10']['cable'], 'pac')
        self.assertEqual(b['10']['alerta'], 'MEDIO')
        self.assertNotIn('cable', b['11'])
        self.assertEqual(b['12']['cable'], 'pac')

    def test_silencio_en_cable_sin_corredor(self):
        AISPosicion.objects.create(mmsi='13', posicion=Point(179.8, 10.005, srid=4326),
                                   timestamp=timezone.now() - timedelta(hours=2), velocidad_nudos=0.0)
        r = self.client.get('/api/v1/cables/buques/')
        self.assertEqual([s['mmsi'] for s in r.json()['silencios']], ['13'])


class ApiDerivaPasivaTests(TestCase):
    """Cable a lo largo del ecuador de 0° a 0,5°E. El agua se simula (la API real no se llama en las pruebas)."""

    @classmethod
    def setUpTestData(cls):
        cargar({'features': [{'properties': {'id': 'eq', 'name': 'Ecuador-1'}, 'geometry': {'type': 'LineString', 'coordinates': [[0, 0], [0.5, 0]]}}]})

    def setUp(self):
        cache.clear()

    def _pista(self, mmsi, ve_kn, minutos, nav=0, lon_ahora=0.2, lat=0.004):
        """Buque que ahora está en lon_ahora y que durante `minutos` min se movió con ve_kn hacia el este."""
        ahora = timezone.now()
        for k in range(1, minutos // 10 + 1):
            lon = lon_ahora - ve_kn * 1852 / 3600 * (k * 600) / 111_320.0
            AISPosicion.objects.create(mmsi=mmsi, posicion=Point(lon, lat, srid=4326), timestamp=ahora - timedelta(minutes=10 * k),
                                       velocidad_nudos=abs(ve_kn), nav=nav)
        _poner_vivo(mmsi, lon_ahora, lat, abs(ve_kn), nav=nav)
        _indice(mmsi)

    def _get(self, corriente_kn=1.0, hacia=90, viento=0.0):
        f = {'corriente_kn': corriente_kn, 'corriente_hacia': hacia, 'viento_kn': viento, 'viento_desde': 0}
        with mock.patch('mares.apps.cables.views.fuerzas_para', side_effect=lambda pts: [f for _ in pts]):
            r = self.client.get('/api/v1/cables/buques/')
        self.assertEqual(r.status_code, 200)
        d = r.json()
        return {x['properties']['mmsi']: x['properties'] for x in d['features']}, d

    def test_deriva_con_la_corriente_es_media_y_alta_si_dura(self):
        self._pista('1', ve_kn=1.0, minutos=50)       # se movió con el agua durante 50 min
        b, d = self._get()
        self.assertEqual(b['1']['prueba']['veredicto'], 'deriva')
        self.assertEqual(b['1']['alerta'], 'MEDIO')
        pista = b['1']['prueba']['pista']
        self.assertGreaterEqual(len(pista), 5)                      # la pista real, de la más vieja a la más reciente
        self.assertLess(pista[0][0], pista[-1][0])                  # iba hacia el este
        cache.clear()
        self._pista('2', ve_kn=1.0, minutos=90)
        b, _ = self._get()
        self.assertEqual(b['2']['prueba']['veredicto'], 'deriva')
        self.assertEqual(b['2']['alerta'], 'ALTO')

    def test_fijo_al_fondo_pese_a_la_corriente_baja_el_nivel(self):
        self._pista('3', ve_kn=0.0, minutos=40, nav=1)
        b, _ = self._get()
        self.assertEqual(b['3']['prueba']['veredicto'], 'fijo')
        self.assertEqual(b['3']['alerta'], 'BAJO')       # sin la prueba habría sido MEDIO
        cache.clear()
        self._pista('4', ve_kn=0.0, minutos=90, nav=1)
        b, _ = self._get()
        self.assertEqual(b['4']['alerta'], 'MEDIO')      # fondeado 90 min sobre el cable

    def test_se_mueve_lento_contra_el_agua_es_propulsion_y_sube_a_alto(self):
        self._pista('5', ve_kn=2.0, minutos=40)           # va a 2 kn hacia el este...
        b, _ = self._get(corriente_kn=1.0, hacia=270)     # ...y el agua lo empuja al oeste
        self.assertEqual(b['5']['prueba']['veredicto'], 'propulsion')
        self.assertEqual(b['5']['alerta'], 'ALTO')
        self.assertGreater(b['5']['prueba']['residuo_kn'], b['5']['prueba']['tol_kn'])

    def test_con_tope_se_evalua_primero_a_quien_tiene_mas_pista(self):
        self._pista('8', ve_kn=1.0, minutos=70)           # mucha pista
        for k in range(20):                                # relleno sin pista
            _poner_vivo(f'9{k:02d}', 0.3 + k * 0.001, 0.004, 0.0)
        _indice('8', *[f'9{k:02d}' for k in range(20)])
        with mock.patch('mares.apps.cables.views.MAX_PRUEBAS', 1):
            b, _ = self._get()
        self.assertIn('prueba', b['8'])                    # con tope 1 se evaluó el de más pista, no uno cualquiera

    def test_sin_pista_suficiente_se_usa_la_regla_simple(self):
        _poner_vivo('6', 0.2, 0.004, 0.0)
        _indice('6')
        b, d = self._get()
        self.assertNotIn('prueba', b['6'])
        self.assertEqual(b['6']['alerta'], 'MEDIO')
        self.assertEqual(d['meta']['pruebas']['evaluadas'], 0)

    def test_si_falla_la_api_de_fuerzas_no_rompe(self):
        self._pista('7', ve_kn=1.0, minutos=50)
        with mock.patch('mares.apps.cables.views.fuerzas_para', side_effect=lambda pts: [None for _ in pts]):
            r = self.client.get('/api/v1/cables/buques/')
        self.assertEqual(r.status_code, 200)
        p = {x['properties']['mmsi']: x['properties'] for x in r.json()['features']}['7']
        self.assertNotIn('prueba', p)
        self.assertEqual(p['alerta'], 'MEDIO')
        self.assertEqual(r.json()['meta']['pruebas'], {**r.json()['meta']['pruebas'], 'evaluadas': 0, 'con_pista': 1, 'sin_agua': 1})   # lo dice, no lo calla


class ZonasHabitualesTests(TestCase):
    """Un puerto o rada se aprende del historial: muchos buques DISTINTOS detenidos en la misma celda de ~2 km."""

    @classmethod
    def setUpTestData(cls):
        cargar({'features': [{'properties': {'id': 'eq', 'name': 'Ecuador-1'}, 'geometry': {'type': 'LineString', 'coordinates': [[0, 0], [0.5, 0]]}}]})

    def setUp(self):
        cache.clear()
        p = mock.patch('mares.apps.cables.views.fuerzas_para', side_effect=lambda pts: [None for _ in pts])
        p.start()
        self.addCleanup(p.stop)

    def _detenidos(self, n, lon, lat=0.004, distintos=True):
        ahora = timezone.now()
        for k in range(n):
            AISPosicion.objects.create(mmsi=f'7{k:03d}' if distintos else '7000', posicion=Point(lon, lat, srid=4326),
                                       timestamp=ahora - timedelta(minutes=10 * (k + 1)), velocidad_nudos=0.0)

    def _buques(self):
        r = self.client.get('/api/v1/cables/buques/')
        return {f['properties']['mmsi']: f['properties'] for f in r.json()['features']}

    def test_cinco_buques_distintos_detenidos_forman_una_zona_habitual(self):
        self._detenidos(5, lon=0.25)
        _poner_vivo('1', 0.25, 0.004, 0.0, 'EN LA RADA')
        _poner_vivo('2', 0.40, 0.004, 0.0, 'AISLADO')            # otra zona, sin historial de estacionamiento
        _indice('1', '2')
        b = self._buques()
        self.assertTrue(b['1']['habitual'])
        self.assertEqual(b['1']['alerta'], 'BAJO')
        self.assertFalse(b['2']['habitual'])
        self.assertEqual(b['2']['alerta'], 'MEDIO')

    def test_un_solo_buque_parado_muchas_veces_no_hace_una_zona(self):
        self._detenidos(8, lon=0.25, distintos=False)             # el mismo buque 8 veces: es un buque, no un puerto
        _poner_vivo('1', 0.25, 0.004, 0.0)
        _indice('1')
        self.assertFalse(self._buques()['1']['habitual'])

    def test_los_simulados_no_cuentan_para_aprender_zonas(self):
        ahora = timezone.now()
        for k in range(6):
            AISPosicion.objects.create(mmsi=f'9990{k:03d}', posicion=Point(0.25, 0.004, srid=4326), timestamp=ahora - timedelta(minutes=10 * (k + 1)), velocidad_nudos=0.0)
        _poner_vivo('1', 0.25, 0.004, 0.0)
        _indice('1')
        self.assertFalse(self._buques()['1']['habitual'])


class PrecalentadoTests(TestCase):
    def setUp(self):
        cache.clear()
        p = mock.patch('mares.apps.cables.views.fuerzas_para', side_effect=lambda pts: [None for _ in pts])
        p.start()
        self.addCleanup(p.stop)

    def test_la_tarea_deja_la_respuesta_en_cache_y_la_vista_no_recalcula(self):
        from mares.apps.cables import tasks, views
        self.assertIsNone(cache.get('cables:buques'))
        tasks.precalentar_buques()
        self.assertIsNotNone(cache.get('cables:buques'))
        with mock.patch.object(views.BuquesView, '_construir', side_effect=AssertionError('no debía recalcular')):
            self.assertEqual(self.client.get('/api/v1/cables/buques/').status_code, 200)

    def test_sin_tarea_la_vista_calcula_bajo_demanda(self):
        self.assertEqual(self.client.get('/api/v1/cables/buques/').status_code, 200)
        self.assertIsNotNone(cache.get('cables:buques'))

    def test_esta_programada_y_el_ttl_cubre_el_intervalo(self):
        from mares.apps.cables import tasks
        from mares.config.celery import app
        e = [v for v in app.conf.beat_schedule.values() if v['task'] == 'mares.cables.precalentar_buques']
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0]['schedule'], tasks.INTERVALO_S)
        self.assertGreater(tasks.TTL_S, tasks.INTERVALO_S)

    def test_no_se_apila_si_la_pasada_anterior_sigue(self):
        from mares.apps.cables import tasks
        cache.add('cables:precalentando', 1, 60)
        self.assertIsNone(tasks.precalentar_buques())
        self.assertIsNone(cache.get('cables:buques'))

    def test_el_cerrojo_se_libera_aunque_falle(self):
        from mares.apps.cables import tasks, views
        with mock.patch.object(views.BuquesView, '_construir', side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                tasks.precalentar_buques()
        self.assertIsNone(cache.get('cables:precalentando'))


class BeatTests(SimpleTestCase):
    def test_el_planificador_solo_tiene_las_tareas_del_producto(self):
        from mares.config.celery import app
        tareas = {v['task'] for v in app.conf.beat_schedule.values()}
        self.assertEqual(tareas, {'mares.cables.sellar_alertas', 'mares.cables.precalentar_buques', 'mares.detection.purge_ais_history'})
class ReplayTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cargar(
            {'features': [{'properties': {'id': 'eq', 'name': 'Ecuador-1', 'color': '#0ff'}, 'geometry': {'type': 'LineString', 'coordinates': [[0, 0], [0.5, 0]]}}]},
            {'features': []},
        )

    def setUp(self):
        cache.clear()
        p = mock.patch('mares.apps.cables.views.fuerzas_para', side_effect=lambda pts: [None for _ in pts])
        p.start()
        self.addCleanup(p.stop)

    def test_devuelve_la_pista_ordenada_y_cerrada_en_la_posicion_actual(self):
        _poner_vivo('100', 0.25, 0.005, 0.0, 'PARADO EN CABLE')
        _poner_vivo('200', 0.25, 0.005, 12.0, 'EN TRANSITO')         # sin atención: no entra
        _indice('100', '200')
        ahora = timezone.now()
        for k in (3, 2, 1):                                           # se crean fuera de orden a propósito
            AISPosicion.objects.create(mmsi='100', posicion=Point(0.25 - 0.001 * k, 0.005, srid=4326), timestamp=ahora - timedelta(minutes=30 * k), velocidad_nudos=0.0)
        r = self.client.get('/api/v1/cables/replay/?horas=3')
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual([b['mmsi'] for b in d['buques']], ['100'])
        pista = d['buques'][0]['pista']
        minutos = [m[0] for m in pista]
        self.assertEqual(minutos, sorted(minutos, reverse=True))        # de la más antigua a la más reciente
        self.assertEqual(pista[-1][0], 0.0)                              # termina en la posición actual
        self.assertEqual(len(pista), 4)
        self.assertAlmostEqual(pista[-1][1], 0.25, places=3)

    def test_la_ventana_se_acota_y_un_valor_malo_no_rompe(self):
        _poner_vivo('100', 0.25, 0.005, 0.0)
        _indice('100')
        self.assertEqual(self.client.get('/api/v1/cables/replay/?horas=99').json()['horas'], 6)
        self.assertEqual(self.client.get('/api/v1/cables/replay/?horas=abc').json()['horas'], 3.0)

    def test_el_historial_fuera_de_la_ventana_no_entra(self):
        _poner_vivo('100', 0.25, 0.005, 0.0)
        _indice('100')
        AISPosicion.objects.create(mmsi='100', posicion=Point(0.1, 0.005, srid=4326), timestamp=timezone.now() - timedelta(hours=5), velocidad_nudos=0.0)
        pista = self.client.get('/api/v1/cables/replay/?horas=3').json()['buques'][0]['pista']
        self.assertEqual(len(pista), 1)


class HistorialCableTests(TestCase):
    """Cable a lo largo del ecuador de 0° a 0,5°E; corredor de 2 km."""

    @classmethod
    def setUpTestData(cls):
        cargar(
            {'features': [{'properties': {'id': 'eq', 'name': 'Ecuador-1', 'color': '#0ff'}, 'geometry': {'type': 'LineString', 'coordinates': [[0, 0], [0.5, 0]]}}]},
            {'features': []},
        )

    def setUp(self):
        cache.clear()

    def _pos(self, mmsi, lon, lat, hace_min, sog, nombre=''):
        AISPosicion.objects.create(mmsi=mmsi, vessel_name=nombre, posicion=Point(lon, lat, srid=4326),
                                   timestamp=timezone.now() - timedelta(minutes=hace_min), velocidad_nudos=sog)

    def test_lista_quien_estuvo_dentro_y_ordena_por_tiempo_lento(self):
        for k in range(7):                                        # A: 60 min casi quieto, cada 10 min
            self._pos('700', 0.25, 0.005, 60 - 10 * k, 0.2, 'QUIETO')
        for k in range(3):                                        # C: de paso a 12 kn
            self._pos('710', 0.10 + 0.05 * k, 0.005, 30 - 10 * k, 12.0, 'DE PASO')
        self._pos('720', 0.25, 0.5, 20, 0.0, 'LEJOS')              # B: a ~55 km del cable
        self._pos('730', 0.25, 0.005, 100 * 60, 0.0, 'VIEJO')      # D: hace 100 h, fuera de la ventana de 24 h
        r = self.client.get('/api/v1/cables/eq/historial/?horas=24')
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual([b['mmsi'] for b in d['barcos']], ['700', '710'])      # solo los de dentro, el más lento primero
        a, c = d['barcos']
        self.assertEqual(a['minutos_lento'], 60)
        self.assertEqual(a['minutos_dentro'], 60)
        self.assertEqual(c['minutos_lento'], 0)
        self.assertEqual(a['nombre'], 'QUIETO')
        self.assertEqual(d['total_barcos'], 2)
        self.assertIn('no prueba', d['aviso'])

    def test_un_hueco_de_datos_no_cuenta_como_tiempo_dentro(self):
        self._pos('740', 0.25, 0.005, 90, 0.1)
        self._pos('740', 0.25, 0.005, 50, 0.1)                     # 40 min sin datos entre las dos
        b = self.client.get('/api/v1/cables/eq/historial/').json()['barcos'][0]
        self.assertEqual(b['minutos_dentro'], 0)
        self.assertEqual(b['posiciones'], 2)

    def test_cable_inexistente_da_404_y_la_ventana_se_acota(self):
        self.assertEqual(self.client.get('/api/v1/cables/no-existe/historial/').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/cables/eq/historial/?horas=9999').json()['horas'], 72.0)
        self.assertEqual(self.client.get('/api/v1/cables/eq/historial/?horas=abc').json()['horas'], 24.0)

    def test_los_simulados_se_marcan(self):
        self._pos('999000001', 0.25, 0.005, 20, 0.0, 'SIM · PRUEBA')
        b = self.client.get('/api/v1/cables/eq/historial/').json()['barcos'][0]
        self.assertTrue(b['simulado'])
