"""
Mide la COHERENCIA de la prueba de deriva pasiva con lo que declaran los propios buques (estado de navegación AIS).

  python manage.py validar_deriva_pasiva --horas 3

Para cada buque con pista suficiente en el historial, calcula el veredicto y lo cruza con su estado declarado
(0 con motor, 1 fondeado, 2 sin gobierno, 5 amarrado, 7 pescando, 8 a vela…).

LÍMITES, que el resultado repite: el estado de navegación lo teclea la tripulación y suele estar mal o sin actualizar,
así que NO es una verdad de referencia; las corrientes son de un modelo de ~8 km (no resuelve puertos ni mareas
finas); y no hay incidentes reales de arrastre de ancla con los que comparar. Es una medida de consistencia, no de acierto.
"""
import json
import statistics
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from mares.apps.cables import deriva
from mares.apps.detection.models import AISPosicion

NAV = {0: 'con motor', 1: 'fondeado', 2: 'sin gobierno', 3: 'maniobra restringida', 5: 'amarrado', 7: 'pescando', 8: 'a vela'}
SALIDA = Path(__file__).resolve().parents[2] / 'validacion_datos' / 'deriva_pasiva.json'


class Command(BaseCommand):
    help = 'Coherencia de la prueba de deriva pasiva con el estado de navegación declarado.'

    def add_arguments(self, parser):
        parser.add_argument('--horas', type=float, default=3.0, help='Ventana de historial a usar.')
        parser.add_argument('--max', type=int, default=600, help='Máximo de buques a evaluar.')
        parser.add_argument('--min-muestras', type=int, default=4)

    def handle(self, *args, **o):
        desde = timezone.now() - timedelta(hours=o['horas'])
        pistas = defaultdict(list)
        navs = defaultdict(list)
        sogs = defaultdict(list)
        for mmsi, ts, pos, nav, sog in (AISPosicion.objects.filter(timestamp__gte=desde).exclude(mmsi__startswith='9990')
                                        .order_by('mmsi', 'timestamp').values_list('mmsi', 'timestamp', 'posicion', 'nav', 'velocidad_nudos').iterator()):
            pistas[mmsi].append((ts, pos.y, pos.x))
            if sog is not None and sog < 102:
                sogs[mmsi].append(sog)
            if nav is not None:
                navs[mmsi].append(nav)

        obs = {}
        for mmsi, m in pistas.items():
            if len(m) >= o['min_muestras'] and navs.get(mmsi):
                r = deriva.velocidad_observada(m)
                if r:
                    obs[mmsi] = r
        self.stdout.write(f'{len(pistas)} buques con historial · {len(obs)} con pista suficiente '
                          f'(≥{o["min_muestras"]} muestras y ≥{deriva.MIN_MINUTOS} min con estado declarado)')
        if not obs:
            self.stderr.write('Nada que evaluar: deja correr el monitor AIS más tiempo (1 muestra por buque cada 10 min).')
            return

        elegidos = list(obs)[:o['max']]
        fuerzas = deriva.fuerzas_para([(pistas[m][-1][1], pistas[m][-1][2]) for m in elegidos])
        tabla: dict[str, Counter] = defaultdict(Counter)
        sin_fuerzas = 0
        residuos = []
        for mmsi, f in zip(elegidos, fuerzas):
            if not f:
                sin_fuerzas += 1
                continue
            r = deriva.veredicto(obs[mmsi], f)
            nav = Counter(navs[mmsi]).most_common(1)[0][0]       # el estado más frecuente en la ventana
            nombre = NAV.get(nav, f'otro ({nav})')
            smax = max(sogs[mmsi], default=0.0)
            # La declaración puede estar desactualizada: se separa a quien la contradice con su propia velocidad.
            if nav in (1, 5) and smax >= 3.0:
                nombre += ' · pero su SOG llegó a ≥3 kn (declaración vieja)'
            elif nav == 0 and smax < 0.5:
                nombre += ' · pero sin moverse (SOG < 0,5 kn)'
            tabla[nombre][r['veredicto']] += 1
            residuos.append(r['residuo_kn'])

        evaluados = sum(sum(c.values()) for c in tabla.values())
        self.stdout.write(f'\nEvaluados con fuerzas: {evaluados} (sin dato de corriente/viento: {sin_fuerzas})\n')
        cab = ['deriva', 'fijo', 'propulsion', 'indeterminado']
        self.stdout.write(f'{"declarado":58s} {"n":>5s} ' + ' '.join(f'{c:>13s}' for c in cab))
        for nombre, c in sorted(tabla.items(), key=lambda kv: -sum(kv[1].values())):
            n = sum(c.values())
            self.stdout.write(f'{nombre:58s} {n:5d} ' + ' '.join(f'{c[k]:5d} ({100 * c[k] / n:3.0f}%)' for k in cab))

        resumen = {
            'generado': timezone.now().isoformat(), 'ventana_h': o['horas'], 'buques_con_historial': len(pistas),
            'buques_con_pista': len(obs), 'evaluados': evaluados, 'sin_fuerzas': sin_fuerzas,
            'residuo_kn_mediana': round(statistics.median(residuos), 3) if residuos else None,
            'parametros': {'viento_k': deriva.VIENTO_K, 'tol_base_kn': deriva.TOL_BASE_KN, 'tol_viento': deriva.TOL_VIENTO,
                           'min_minutos': deriva.MIN_MINUTOS, 'quieto_kn': deriva.UMBRAL_QUIETO_KN},
            'tabla': {k: dict(v) for k, v in tabla.items()},
            'fuente_fuerzas': deriva.ATRIBUCION,
            'limites': [
                'El estado de navegación lo declara la tripulación y suele estar mal o desactualizado: no es verdad de referencia.',
                'Corrientes de un modelo de ~8 km: no resuelve puertos, canales ni mareas finas.',
                'No hay incidentes reales de arrastre de ancla para comparar: mide consistencia, no acierto.',
            ],
        }
        SALIDA.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'\nGuardado en {SALIDA}'))
