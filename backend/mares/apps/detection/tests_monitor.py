from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class MonitorAisTests(SimpleTestCase):
    @override_settings(AISSTREAM_API_KEY='')
    def test_sin_clave_explica_que_hacer_y_no_arranca(self):
        with self.assertRaises(CommandError) as e:
            call_command('monitor_ais')
        self.assertIn('simular_ais', str(e.exception))

    @override_settings(AISSTREAM_API_KEY='   ')
    def test_una_clave_en_blanco_cuenta_como_ausente(self):
        with self.assertRaises(CommandError):
            call_command('monitor_ais')
