#!/usr/bin/env python3
"""
Verifica la cadena pública de alertas selladas del Vigía, sin usar nada del proyecto.

    python3 scripts/verificar_sellos.py http://localhost:8001/api/v1/cables/sellos/
    python3 scripts/verificar_sellos.py sellos.json          # una respuesta guardada

Recalcula el hash de cada sello (SHA-256 de hash_anterior + salto de línea + JSON canónico del contenido) y comprueba
que cada uno encadena con el anterior. Íntegra = nadie alteró ni quitó sellos DENTRO de lo mostrado. No prueba que
existieran antes de un suceso: para eso hay que publicar el último hash fuera de la base de datos (p. ej. en el repositorio).
"""
import hashlib
import json
import sys
import urllib.request


def cargar(fuente: str) -> dict:
    if fuente.startswith('http'):
        with urllib.request.urlopen(fuente, timeout=30) as r:
            return json.load(r)
    with open(fuente, encoding='utf-8') as f:
        return json.load(f)


def main(fuente: str) -> int:
    d = cargar(fuente)
    sellos = list(reversed(d['sellos']))          # la API los entrega del más nuevo al más viejo
    problemas, previo = [], None
    for s in sellos:
        canon = json.dumps(s['contenido'], sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        if hashlib.sha256(f"{s['hash_anterior']}\n{canon}".encode('utf-8')).hexdigest() != s['hash']:
            problemas.append(f"{s['ts']}: el contenido no coincide con su hash")
        if previo and s['hash_anterior'] != previo['hash']:
            problemas.append(f"{s['ts']}: no encadena con el sello anterior")
        previo = s
    n_alertas = sum(len(s['contenido']['alertas']) for s in sellos)
    print(f"{len(sellos)} sellos mostrados (de {d['total']}), {n_alertas} alertas reales en total.")
    if sellos:
        print(f"Último hash: {sellos[-1]['hash']}  ← publíquelo fuera para fijar su fecha")
    print('RESULTADO: cadena íntegra.' if not problemas else 'RESULTADO: CADENA ROTA\n  ' + '\n  '.join(problemas))
    return 0 if not problemas else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]) if len(sys.argv) == 2 else sys.exit(__doc__))
