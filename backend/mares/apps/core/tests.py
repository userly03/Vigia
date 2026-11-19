from django.test import TestCase


class RutasBaseTests(TestCase):
    """Las rutas que no son del producto pero que cualquiera puede visitar: raíz, documentación y salud."""

    def test_la_raiz_de_la_api_dice_quien_es_y_donde_estan_los_datos(self):
        r = self.client.get('/api/')
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d['service'], 'Vigía')
        self.assertEqual(d['endpoints']['cables'], '/api/v1/cables/')

    def test_la_documentacion_interactiva_responde(self):
        self.assertEqual(self.client.get('/api/docs/').status_code, 200)
        self.assertEqual(self.client.get('/api/redoc/').status_code, 200)

    def test_la_salud_informa_base_de_datos_y_redis(self):
        r = self.client.get('/health/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['checks'], {'database': 'ok', 'redis': 'ok'})
