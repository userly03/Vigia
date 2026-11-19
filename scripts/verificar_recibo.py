#!/usr/bin/env python3
"""
Verifica un recibo descargado de la pantalla del Vigía, sin usar nada del proyecto.

    python3 scripts/verificar_recibo.py recibo-123456789-ab12cd34.json

Recalcula el SHA-256 del contenido (JSON con claves ordenadas, sin espacios) y lo compara con el hash del archivo.
Coincidir significa que el archivo NO se alteró desde que se generó. NO significa que los datos de origen
(AIS, corrientes del modelo) sean correctos: eso hay que juzgarlo con las fuentes y los límites que el propio
recibo declara.
"""
import hashlib
import json
import sys


def main(ruta: str) -> int:
    with open(ruta, encoding='utf-8') as f:
        r = json.load(f)
    canon = json.dumps(r['contenido'], sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    calculado = hashlib.sha256(canon.encode('utf-8')).hexdigest()
    ok = calculado == r['sha256']
    c = r['contenido']
    if 'buque' in c:                                   # recibo de una alerta
        print(f"Banner: {c.get('banner')}\nBuque: {c['buque'].get('nombre')} (MMSI {c['buque'].get('mmsi')}) · nivel {c.get('nivel')}")
    else:                                              # informe de una investigación de cable
        print(f"Informe ({c.get('formato')}): cable {c['cable'].get('nombre')} · últimas {c['ventana'].get('horas')} h · {c.get('barcos_incluidos')} de {c.get('total_barcos')} barcos")
    print(f"Hash del archivo : {r['sha256']}\nHash recalculado : {calculado}")
    print('RESULTADO: el contenido NO fue alterado.' if ok else 'RESULTADO: el contenido NO coincide con su hash (alterado o corrupto).')
    return 0 if ok else 1


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
