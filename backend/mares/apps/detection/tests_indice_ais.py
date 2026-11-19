"""El índice de MMSI vistos del monitor de AISstream: no debe reescribirse en cada mensaje ni crecer sin límite."""
import json
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase

from mares.apps.detection import tasks


class IndiceAisTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        tasks._VISTOS.clear()
        tasks._ultimo_indice = None

    def _indice(self):
        raw = cache.get(tasks._AIS_INDEX_KEY)
        return set(json.loads(raw)) if raw else set()

    def test_mmsi_nuevo_entra_al_indice_de_inmediato(self):
        tasks._actualizar_indice(cache, '111')
        tasks._actualizar_indice(cache, '222')
        self.assertEqual(self._indice(), {'111', '222'})

    def test_mmsi_conocido_no_reescribe_el_indice_antes_del_intervalo(self):
        tasks._actualizar_indice(cache, '111')
        with mock.patch.object(cache, 'set') as sset, mock.patch.object(cache, 'get') as sget:
            with mock.patch.object(tasks.time, 'monotonic', return_value=tasks._VISTOS['111'] + 5):
                tasks._actualizar_indice(cache, '111')
        sset.assert_not_called()
        sget.assert_not_called()

    def test_al_vencer_el_intervalo_se_poda_lo_que_ya_no_se_ve(self):
        tasks._actualizar_indice(cache, 'viejo')
        t0 = tasks._VISTOS['viejo']
        tasks._VISTOS['activo'] = t0 + 2000          # visto "hace poco"
        with mock.patch.object(tasks.time, 'monotonic', return_value=t0 + 2000):
            tasks._actualizar_indice(cache, 'activo')   # conocido, intervalo vencido -> reescribe y poda
        self.assertEqual(self._indice(), {'activo'})
        self.assertNotIn('viejo', tasks._VISTOS)

    def test_no_pisa_los_mmsi_que_escribio_otro_proceso(self):
        # otro proceso dejó su MMSI en el índice y su posición sigue en Redis
        cache.set(tasks._AIS_INDEX_KEY, json.dumps(['ajeno']), 900)
        cache.set(f'{tasks._AIS_CACHE_KEY_PREFIX}ajeno', '{}', 900)
        tasks._actualizar_indice(cache, 'mio')
        t0 = tasks._VISTOS['mio']
        with mock.patch.object(tasks.time, 'monotonic', return_value=t0 + 61):
            tasks._actualizar_indice(cache, 'mio')   # intervalo vencido: reescribe
        self.assertEqual(self._indice(), {'ajeno', 'mio'})
