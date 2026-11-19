"""
python manage.py sellar_alertas            # crea un sello ahora
python manage.py sellar_alertas --verificar  # recalcula toda la cadena y dice si está íntegra
"""
from django.core.management.base import BaseCommand, CommandError

from mares.apps.cables import sellos
from mares.apps.cables.models import Sello
from mares.apps.cables.views import BuquesView


class Command(BaseCommand):
    help = 'Sella las alertas reales actuales en la cadena de hashes, o verifica la cadena.'

    def add_arguments(self, parser):
        parser.add_argument('--verificar', action='store_true')

    def handle(self, *args, **o):
        if o['verificar']:
            cadena = list(Sello.objects.order_by('ts', 'id'))
            problemas = sellos.verificar(cadena)
            self.stdout.write(f'{len(cadena)} sellos.')
            if problemas:
                raise CommandError('CADENA ROTA:\n' + '\n'.join(problemas))
            self.stdout.write(self.style.SUCCESS('Cadena íntegra.'))
            return
        s = sellos.sellar(BuquesView.refrescar(45))
        self.stdout.write(f'Sello {s.hash} · {len(s.contenido["alertas"])} alertas reales')
