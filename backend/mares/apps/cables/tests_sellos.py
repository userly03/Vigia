import hashlib
import json
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from . import sellos
from .models import Sello


def _f(mmsi, alerta, simulado=False, lng=1.0, lat=55.0):
    return {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lng, lat]},
            'properties': {'mmsi': mmsi, 'nombre': 'N' + mmsi, 'alerta': alerta, 'simulado': simulado, 'minutos': 70,
                           'cable_nombre': 'C-1', 'dist_m': 300, 'estado': 'parado', 'sog': 0.1, 'ts': '2026-11-18T10:00:00+00:00',
                           'prueba': {'veredicto': 'fijo'}}}


def _rec(mmsi, km, simulado=False):
    f = _f(mmsi, None, simulado=simulado)
    f['properties']['recorrido_km'] = km
    return f


def _data(*feats):
    return {'features': list(feats), 'meta': {'generado': '2026-11-18T10:00:01+00:00', 'total': len(feats), 'simulados': sum(1 for f in feats if f['properties']['simulado'])}}


class SellosTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_solo_alertas_reales_alto_o_medio_y_en_orden_estable(self):
        d = _data(_f('300', 'MEDIO'), _f('100', 'ALTO'), _f('200', 'BAJO'), _f('999', 'ALTO', simulado=True), _f('400', None))
        self.assertEqual([a['mmsi'] for a in sellos.extraer_alertas(d)], ['100', '300'])

    def test_la_cadena_encadena_y_se_verifica(self):
        a = sellos.sellar(_data(_f('100', 'ALTO')))
        b = sellos.sellar(_data(_f('100', 'MEDIO')))
        self.assertEqual(a.hash_anterior, '')
        self.assertEqual(b.hash_anterior, a.hash)
        self.assertEqual(sellos.verificar([a, b]), [])

    def test_el_hash_es_el_sha256_documentado(self):
        s = sellos.sellar(_data(_f('100', 'ALTO')))
        canon = json.dumps(s.contenido, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        self.assertEqual(s.hash, hashlib.sha256(f'\n{canon}'.encode()).hexdigest())

    def test_alterar_un_sello_rompe_la_cadena(self):
        a = sellos.sellar(_data(_f('100', 'ALTO')))
        b = sellos.sellar(_data(_f('100', 'MEDIO')))
        a.contenido['alertas'][0]['nivel'] = 'BAJO'
        self.assertTrue(sellos.verificar([a, b]))

    def test_quitar_un_sello_del_medio_rompe_el_encadenado(self):
        a = sellos.sellar(_data(_f('1', 'ALTO')))
        b = sellos.sellar(_data(_f('2', 'ALTO')))
        c = sellos.sellar(_data(_f('3', 'ALTO')))
        self.assertTrue(any('no encadena' in p for p in sellos.verificar([a, c])))
        self.assertEqual(sellos.verificar([a, b, c]), [])

    def test_endpoint_publico_y_detecta_alteracion(self):
        sellos.sellar(_data(_f('100', 'ALTO')))
        sellos.sellar(_data(_f('100', 'MEDIO')))
        r = self.client.get('/api/v1/cables/sellos/')
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d['total'], 2)
        self.assertTrue(d['integra_en_lo_mostrado'])
        s = Sello.objects.order_by('ts', 'id').first()
        s.contenido = {**s.contenido, 'buques_reales': 12345}
        s.save()
        self.assertFalse(self.client.get('/api/v1/cables/sellos/').json()['integra_en_lo_mostrado'])

    def test_la_tarea_sella_y_esta_programada_cada_hora(self):
        from mares.apps.cables import tasks
        from mares.config.celery import app
        with mock.patch('mares.apps.cables.views.fuerzas_para', side_effect=lambda pts: [None for _ in pts]):
            h = tasks.sellar_alertas()
        self.assertEqual(Sello.objects.get().hash, h)
        e = [v for v in app.conf.beat_schedule.values() if v['task'] == 'mares.cables.sellar_alertas']
        self.assertEqual(len(e), 1)


class ValidacionTests(TestCase):
    def test_devuelve_lo_que_hay_y_none_si_falta(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'deriva_pasiva.json').write_text(json.dumps({'evaluados': 5}), encoding='utf-8')
            with mock.patch('mares.apps.cables.views.RUTA_VALIDACION', Path(d)):
                r = self.client.get('/api/v1/cables/validacion/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['deriva_pasiva']['evaluados'], 5)
        self.assertIsNone(r.json()['corrientes_vs_boyas'])

    def test_un_archivo_corrupto_no_rompe(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'deriva_pasiva.json').write_text('{no es json', encoding='utf-8')
            with mock.patch('mares.apps.cables.views.RUTA_VALIDACION', Path(d)):
                self.assertIsNone(self.client.get('/api/v1/cables/validacion/').json()['deriva_pasiva'])


class RecorridosEnSelloTests(TestCase):
    def test_los_recorridos_reales_se_sellan_aparte_de_las_alertas(self):
        s = sellos.sellar(_data(_f('100', 'ALTO'), _rec('300', 22.5), _rec('900', 40.0, simulado=True)))
        self.assertEqual([a['mmsi'] for a in s.contenido['alertas']], ['100'])
        self.assertEqual([r['mmsi'] for r in s.contenido['recorridos']], ['300'])      # el simulado no entra
        self.assertEqual(s.contenido['recorridos'][0]['recorrido_km'], 22.5)
