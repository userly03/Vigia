"""
Descarga y carga los cables submarinos y sus puntos de amarre.

  python manage.py cargar_cables                      # baja de submarinecablemap.com
  python manage.py cargar_cables --archivo-cables c.json --archivo-amarres a.json

AVISO: los datos son de TeleGeography y su licencia para uso comercial no está confirmada. Se descargan aquí,
no se versionan en git, y la interfaz muestra la atribución.
"""
import json
import urllib.request

from django.core.management.base import BaseCommand, CommandError

from mares.apps.cables.loader import cargar
from mares.apps.cables.models import CableTramo

URL_CABLES = 'https://www.submarinecablemap.com/api/v3/cable/cable-geo.json'
URL_AMARRES = 'https://www.submarinecablemap.com/api/v3/landing-point/landing-point-geo.json'


def _bajar(url: str) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': 'mares-cables/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 (URL fija, https)
            return json.load(r)
    except Exception as exc:  # red, JSON inválido…
        raise CommandError(f'No se pudo descargar {url}: {exc}') from exc


def _leer(path: str) -> dict:
    with open(path, encoding='utf-8') as f:
        return json.load(f)


class Command(BaseCommand):
    help = 'Carga cables submarinos y puntos de amarre (TeleGeography).'

    def add_arguments(self, parser):
        parser.add_argument('--archivo-cables')
        parser.add_argument('--archivo-amarres')
        parser.add_argument('--corredor-m', type=float, default=None, help='Ancho del corredor a cada lado (m).')

    def handle(self, *args, **opts):
        cables = _leer(opts['archivo_cables']) if opts['archivo_cables'] else _bajar(URL_CABLES)
        amarres = _leer(opts['archivo_amarres']) if opts['archivo_amarres'] else _bajar(URL_AMARRES)
        res = cargar(cables, amarres, opts['corredor_m'])
        self.stdout.write(self.style.SUCCESS(f'Cables: {res["cables"]} · puntos de amarre: {res["amarres"]} · borrados: {res["borrados"]}'))
        sin = CableTramo.objects.filter(corredor__isnull=True).count()
        self.stdout.write(f'Tramos de vigilancia: {res["tramos"]} (sin polígono, por tocar ±180°: {sin})')
        self.stdout.write(self.style.WARNING('Datos © TeleGeography (submarinecablemap.com). Licencia comercial NO confirmada.'))
