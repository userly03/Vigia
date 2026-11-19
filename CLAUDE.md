# CLAUDE.md — Vigía (reglas del proyecto)

## Qué es
**Vigía**: vigilancia global y en vivo de los cables submarinos. Un globo público que muestra qué buques están lentos o parados sobre un cable y, con la corriente y el viento reales del lugar, si el agua explica su movimiento. Proyecto de concurso; **no acusa a nadie** y **no está validado con incidentes reales**.
Antes se llamó MARES (sistema de rescate); esa parte se eliminó por completo (historia en `docs/ESTADO_TECNICO.md`, sección «Historia»).

## Dónde mirar primero
- `README.md` — qué es, cómo arrancarlo, API, verificación.
- `docs/ESTADO_TECNICO.md` — estado real, mediciones, límites, pendiente.
- `docs/PITCH.md` — el problema, la pantalla, las reglas y las preguntas del jurado.
- `docs/PROPUESTAS.md` — ideas y próximos pasos.

## Stack
Python 3.12 · Django 4.2 + DRF · PostGIS · Redis · Celery · Next.js 14 + React 18 + TypeScript · MapLibre GL.
Apps del backend: `cables` (el producto), `detection` (monitor AIS e historial), `core` (registro de peticiones). El paquete Python se sigue llamando `mares` por historia; el nombre público es **Vigía** (se cambia en `frontend/src/lib/marca.ts`).

## Reglas que no se rompen
1. **Nada simulado sin etiqueta.** Todo dato simulado dice SIMULADO en pantalla y en el recibo (`simular_ais`, MMSI 9990…).
2. **Lo no verificado se dice.** Escribir **[sin verificar]** en vez de afirmar. No prometer ganar ni ingresos. Distinguir «nuevo para el jurado» de «nuevo en el mundo».
3. **Nivel de atención, no acusación.** Ninguna regla distingue con certeza un fondeo legítimo de un arrastre de ancla.
4. **Las pruebas no usan la red.** Las llamadas a Open-Meteo se parchean (`fuerzas_para`). Antes de decir «pasan», correrlas tras la última edición.
5. **Secretos.** `backend/.env` NO se versiona (repositorio público; está en `.gitignore`). La plantilla es `backend/.env.example`. No leer ni repetir los valores del `.env` en respuestas ni escribirlos en documentos.
6. **Los umbrales y tolerancias salen de mediciones** (ver `docs/ESTADO_TECNICO.md`); si se cambian, actualizar el pitch y su registro de cambios.
7. Confirmar antes de borrar; usar la etiqueta git `mares-sar-v1` para recuperar el sistema de rescate.

## Comandos
```bash
bash scripts/backend.sh [--simulado]    # terminal 1: API + monitor AIS (requiere PostGIS y Redis corriendo)
bash scripts/frontend.sh                # terminal 2: la pantalla
bash scripts/levantar.sh / apagar.sh    # lo mismo todo en segundo plano
cd backend && python manage.py monitor_ais     # solo el monitor AIS real (sin Celery)
cd backend && python manage.py test                     # pruebas (necesitan PostGIS de pruebas)
cd backend && python manage.py cargar_cables            # cables y puntos de amarre (TeleGeography)
cd backend && python manage.py simular_ais --buques 300 # tráfico SIMULADO
cd frontend && npx tsc --noEmit && npx next lint && npx next build
sysmap check                                            # trinquete de calidad
```
Regenerar el esquema de la API tras tocar vistas: `cd backend && DJANGO_SETTINGS_MODULE=mares.config.settings.development python manage.py spectacular --format openapi-json --file openapi.json`.

## Trampas conocidas
- El PostGIS del Postgres de algunas distribuciones (Fedora) puede estar roto (`undefined symbol: heap_datum_check`): usar un contenedor `postgis/postgis`.
- Open-Meteo devuelve 429 si se multiplican las peticiones: un fallo de la API no debe guardarse como «sin dato».
- `pkill -f` puede matar la propia shell: matar por PID.
- La primera petición a `/api/v1/cables/buques/` tarda ~10 s en frío; la tarea `precalentar_buques` la mantiene en ~0,1 s.
