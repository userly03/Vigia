import math
from datetime import datetime, timedelta, timezone as tz
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase

from mares.apps.cables import deriva

T0 = datetime(2026, 11, 18, 12, 0, tzinfo=tz.utc)


def pistas(ve_kn, vn_kn, n=6, paso_min=10, lat=55.0, lon=11.0, ruido_m=0.0):
    """Muestras [(t, lat, lon)] de un buque que se mueve con velocidad constante (nudos, este/norte)."""
    out = []
    for k in range(n):
        s = k * paso_min * 60
        dx, dy = ve_kn * 1852 / 3600 * s, vn_kn * 1852 / 3600 * s
        dx += ruido_m * (1 if k % 2 else -1)
        out.append((T0 + timedelta(seconds=s), lat + dy / 110_540.0, lon + dx / (111_320.0 * math.cos(math.radians(lat)))))
    return out


class ObservadaTests(SimpleTestCase):
    def test_recupera_la_velocidad(self):
        o = deriva.velocidad_observada(pistas(1.0, 0.5))
        self.assertAlmostEqual(o['ve_kn'], 1.0, delta=0.02)
        self.assertAlmostEqual(o['vn_kn'], 0.5, delta=0.02)
        self.assertAlmostEqual(o['rapidez_kn'], math.hypot(1.0, 0.5), delta=0.02)
        self.assertAlmostEqual(o['rumbo'], math.degrees(math.atan2(1.0, 0.5)), delta=1.5)

    def test_quieto_con_ruido_de_gps_da_cero(self):
        o = deriva.velocidad_observada(pistas(0, 0, ruido_m=15))
        self.assertLess(o['rapidez_kn'], 0.1)

    def test_pocas_muestras_o_poco_tiempo_no_concluyen(self):
        self.assertIsNone(deriva.velocidad_observada(pistas(1, 0, n=2)))
        self.assertIsNone(deriva.velocidad_observada(pistas(1, 0, n=4, paso_min=5)))   # 15 min < 30

    def test_el_orden_de_entrada_da_igual(self):
        p = pistas(0.8, -0.3)
        a = deriva.velocidad_observada(p)
        b = deriva.velocidad_observada(list(reversed(p)))
        self.assertAlmostEqual(a['ve_kn'], b['ve_kn'])


class EsperadaTests(SimpleTestCase):
    def test_corriente_hacia_el_este(self):
        e = deriva.esperada({'corriente_kn': 1.0, 'corriente_hacia': 90, 'viento_kn': 0, 'viento_desde': 0})
        self.assertAlmostEqual(e['ve_kn'], 1.0, places=6)
        self.assertAlmostEqual(e['vn_kn'], 0.0, places=6)

    def test_el_viento_arrastra_hacia_donde_sopla(self):
        # viento DEL norte (0°) empuja hacia el sur
        e = deriva.esperada({'corriente_kn': 0, 'corriente_hacia': 0, 'viento_kn': 20, 'viento_desde': 0})
        self.assertAlmostEqual(e['vn_kn'], -20 * deriva.VIENTO_K, places=6)
        self.assertAlmostEqual(e['ve_kn'], 0.0, places=6)


class VeredictoTests(SimpleTestCase):
    F = {'corriente_kn': 1.0, 'corriente_hacia': 90, 'viento_kn': 10, 'viento_desde': 270}   # viento del oeste -> este

    def _obs(self, ve, vn):
        return deriva.velocidad_observada(pistas(ve, vn))

    def test_deriva_coincide_con_lo_esperado(self):
        e = deriva.esperada(self.F)
        r = deriva.veredicto(self._obs(e['ve_kn'], e['vn_kn']), self.F)
        self.assertEqual(r['veredicto'], deriva.DERIVA)
        self.assertLess(r['residuo_kn'], 0.05)

    def test_fijo_si_el_agua_lo_moveria_y_no_se_mueve(self):
        r = deriva.veredicto(self._obs(0, 0), self.F)
        self.assertEqual(r['veredicto'], deriva.FIJO)

    def test_quieto_sin_fuerzas_no_se_puede_decir(self):
        calma = {'corriente_kn': 0.1, 'corriente_hacia': 0, 'viento_kn': 2, 'viento_desde': 0}
        self.assertEqual(deriva.veredicto(self._obs(0, 0), calma)['veredicto'], deriva.INDETERMINADO)

    def test_propulsion_si_se_mueve_distinto_del_agua(self):
        # el agua va al este a ~1,25 kn; el buque va al norte a 2 kn
        self.assertEqual(deriva.veredicto(self._obs(0, 2.0), self.F)['veredicto'], deriva.PROPULSION)

    def test_contra_la_corriente_es_propulsion(self):
        self.assertEqual(deriva.veredicto(self._obs(-1.5, 0), self.F)['veredicto'], deriva.PROPULSION)

    def test_la_tolerancia_crece_con_el_viento(self):
        f2 = dict(self.F, viento_kn=30)
        self.assertGreater(deriva.veredicto(self._obs(0, 0), f2)['tolerancia_kn'], deriva.veredicto(self._obs(0, 0), self.F)['tolerancia_kn'])


def _resp(items):
    m = mock.Mock()
    m.raise_for_status = lambda: None
    m.json = lambda: items
    return m


class FuerzasTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def _api(self):
        cor = lambda lat, lon: {'current': {'ocean_current_velocity': 3.704, 'ocean_current_direction': 90}}   # 3,704 km/h = 2 kn
        vie = lambda lat, lon: {'current': {'wind_speed_10m': 12.0, 'wind_direction_10m': 180}}

        def get(url, params=None, timeout=None):
            n = len(params['latitude'].split(','))
            return _resp([(cor if 'marine' in url else vie)(0, 0) for _ in range(n)])
        return get

    def test_convierte_unidades_y_agrupa_por_celda(self):
        with mock.patch.object(deriva.requests, 'get', side_effect=self._api()) as g:
            f = deriva.fuerzas_para([(55.01, 11.02), (55.04, 11.03), (36.0, -5.5)])
        self.assertAlmostEqual(f[0]['corriente_kn'], 2.0, places=3)
        self.assertEqual(f[0]['corriente_hacia'], 90.0)
        self.assertEqual(f[0]['viento_kn'], 12.0)
        self.assertEqual(f[0], f[1])                    # misma celda de 0,1°
        self.assertEqual(g.call_count, 2)                # una llamada de corrientes y otra de viento para las 2 celdas

    def test_segunda_peticion_sale_de_la_cache(self):
        with mock.patch.object(deriva.requests, 'get', side_effect=self._api()) as g:
            deriva.fuerzas_para([(55.0, 11.0)])
            deriva.fuerzas_para([(55.0, 11.0)])
        self.assertEqual(g.call_count, 2)                # sólo las 2 llamadas de la primera

    def test_si_la_api_falla_devuelve_none_sin_romper(self):
        with mock.patch.object(deriva.requests, 'get', side_effect=deriva.requests.ConnectionError('sin red')):
            self.assertEqual(deriva.fuerzas_para([(55.0, 11.0)]), [None])

    def test_dato_nulo_se_trata_como_sin_dato(self):
        malo = lambda url, params=None, timeout=None: _resp([{'current': {'ocean_current_velocity': None, 'ocean_current_direction': None, 'wind_speed_10m': 5, 'wind_direction_10m': 1}}])
        with mock.patch.object(deriva.requests, 'get', side_effect=malo):
            self.assertEqual(deriva.fuerzas_para([(55.0, 11.0)]), [None])


class CostaTests(SimpleTestCase):
    """Celdas de tierra: se toma la corriente del agua más cercana, etiquetada, y se ensancha la tolerancia."""

    def setUp(self):
        cache.clear()

    def _api(self):
        def get(url, params=None, timeout=None):
            lats = [float(x) for x in params['latitude'].split(',')]
            if 'marine' in url:
                # la celda pedida (55.0) es tierra; hay agua 0,2° al norte
                return _resp([{'current': {'ocean_current_velocity': 1.852 if abs(la - 55.2) < 1e-6 else None,
                                           'ocean_current_direction': 45 if abs(la - 55.2) < 1e-6 else None}} for la in lats])
            return _resp([{'current': {'wind_speed_10m': 10.0, 'wind_direction_10m': 270}} for _ in lats])
        return get

    def test_usa_el_agua_mas_cercana_y_lo_declara(self):
        with mock.patch.object(deriva.requests, 'get', side_effect=self._api()):
            f = deriva.fuerzas_para([(55.0, 11.0)])[0]
        self.assertIsNotNone(f)
        self.assertAlmostEqual(f['corriente_kn'], 1.0, places=3)
        self.assertGreater(f['aprox_km'], 15)
        self.assertLess(f['aprox_km'], 25)

    def test_sin_agua_en_el_radio_sigue_siendo_sin_dato(self):
        def seco(url, params=None, timeout=None):
            n = len(params['latitude'].split(','))
            if 'marine' in url:
                return _resp([{'current': {'ocean_current_velocity': None, 'ocean_current_direction': None}} for _ in range(n)])
            return _resp([{'current': {'wind_speed_10m': 5, 'wind_direction_10m': 1}} for _ in range(n)])
        with mock.patch.object(deriva.requests, 'get', side_effect=seco):
            self.assertEqual(deriva.fuerzas_para([(55.0, 11.0)]), [None])

    def test_la_tolerancia_crece_con_la_aproximacion(self):
        obs = {'ve_kn': 0, 'vn_kn': 0, 'rapidez_kn': 0.0, 'rumbo': 0, 'muestras': 5, 'minutos': 60}
        f = {'corriente_kn': 1.0, 'corriente_hacia': 0, 'viento_kn': 0.0, 'viento_desde': 0}
        a = deriva.veredicto(obs, f)['tolerancia_kn']
        b = deriva.veredicto(obs, {**f, 'aprox_km': 20.0})['tolerancia_kn']
        self.assertAlmostEqual(b - a, deriva.TOL_COSTA_KN, places=6)


class FalloDeLaApiTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_un_fallo_de_la_api_no_se_recuerda_como_sin_dato_mucho_tiempo(self):
        with mock.patch.object(deriva.requests, 'get', side_effect=deriva.requests.ConnectionError('429')), \
                mock.patch.object(deriva.cache, 'set') as guardar:
            self.assertEqual(deriva.fuerzas_para([(55.0, 11.0)]), [None])
        ttls = [c.args[2] for c in guardar.call_args_list if c.args[0] == deriva._clave((55.0, 11.0))]
        self.assertEqual(ttls, [60])

    def test_una_celda_de_tierra_se_consulta_una_sola_vez(self):
        llamadas = []

        def get(url, params=None, timeout=None):
            n = len(params['latitude'].split(','))
            llamadas.append((url, n))
            if 'marine' in url:
                return _resp([{'current': {'ocean_current_velocity': None, 'ocean_current_direction': None}} for _ in range(n)])
            return _resp([{'current': {'wind_speed_10m': 5, 'wind_direction_10m': 1}} for _ in range(n)])
        with mock.patch.object(deriva.requests, 'get', side_effect=get):
            deriva.fuerzas_para([(55.0, 11.0)])
            n1 = len(llamadas)
            cache.delete(deriva._clave((55.0, 11.0)))          # se olvida el resultado final, no el hecho de que es tierra
            deriva.fuerzas_para([(55.0, 11.0)])
        marinas_2 = [u for u, _ in llamadas[n1:] if 'marine' in u]
        self.assertEqual(marinas_2, [])


class ToleranciaRegionalTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_mar_del_norte_usa_la_tolerancia_medida_y_el_resto_la_base(self):
        self.assertEqual(deriva.tolerancia_base(54.0, 7.0), 0.7)
        self.assertEqual(deriva.tolerancia_base(55.0, 11.0), deriva.TOL_BASE_KN)     # Kattegat/Báltico
        self.assertEqual(deriva.tolerancia_base(-12.0, -77.0), 0.5)                   # Perú: medido
        self.assertEqual(deriva.tolerancia_base(14.0, 42.0), 1.0)                     # Mar Rojo: el modelo se equivoca mucho
        self.assertEqual(deriva.tolerancia_base(40.0, -40.0), deriva.TOL_BASE_KN)     # Atlántico: no medido

    def test_la_tolerancia_regional_entra_en_el_veredicto(self):
        obs = {'ve_kn': 0.6, 'vn_kn': 0.0, 'rapidez_kn': 0.6, 'rumbo': 90, 'muestras': 6, 'minutos': 90}
        f = {'corriente_kn': 0.0, 'corriente_hacia': 0, 'viento_kn': 0.0, 'viento_desde': 0}
        self.assertEqual(deriva.veredicto(obs, f)['veredicto'], deriva.PROPULSION)                     # 0,6 > 0,4
        self.assertEqual(deriva.veredicto(obs, {**f, 'tol_base_kn': 0.7})['veredicto'], deriva.DERIVA)   # 0,6 ≤ 0,7

    def test_fuerzas_para_lleva_la_tolerancia_de_su_celda(self):
        def get(url, params=None, timeout=None):
            n = len(params['latitude'].split(','))
            if 'marine' in url:
                return _resp([{'current': {'ocean_current_velocity': 1.852, 'ocean_current_direction': 0}} for _ in range(n)])
            return _resp([{'current': {'wind_speed_10m': 5, 'wind_direction_10m': 1}} for _ in range(n)])
        with mock.patch.object(deriva.requests, 'get', side_effect=get):
            norte, kattegat = deriva.fuerzas_para([(54.0, 7.0), (55.0, 11.0)])
        self.assertEqual(norte['tol_base_kn'], 0.7)
        self.assertEqual(kattegat['tol_base_kn'], deriva.TOL_BASE_KN)
