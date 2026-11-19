# Vigía

**Los cables submarinos del mundo, bajo vigilancia.** Un globo público y en vivo que muestra qué buques están lentos o parados sobre un cable submarino y, con la corriente y el viento reales del lugar, si el agua explica su movimiento. Sin iniciar sesión.

> Proyecto de concurso. Está medido con datos reales y declara sus límites: **no acusa a nadie** y **no está validado con incidentes reales de arrastre de ancla**. Detalle para el jurado: [`docs/PITCH.md`](docs/PITCH.md). Estado técnico y mediciones: [`docs/ESTADO_TECNICO.md`](docs/ESTADO_TECNICO.md).

![Vigía en acción: abrir una alerta, ver su prueba de deriva y la leyenda](docs/img/vigia-demo.gif)

| El globo, con los cables y los buques | Una alerta con su prueba de deriva pasiva |
|---|---|
| ![El globo](docs/img/globo.jpg) | ![Alerta con prueba de deriva](docs/img/alerta-deriva.jpg) |

*Capturas con tráfico AIS real. La leyenda de la pantalla está en [`docs/img/leyenda.jpg`](docs/img/leyenda.jpg).*

---

## El problema que resolvemos
Casi todo el tráfico de datos entre continentes viaja por cables en el fondo del mar **[cifra exacta sin verificar; ver el pitch]**. Cada año se dañan unos 150–200 y entre el 70 y el 86 % por **anclas y redes de pesca** (según la fuente). Reparar uno tarda semanas y cuesta millones. En 2024 el *Yi Peng 3* arrastró un ancla ~180 millas por el Báltico y dañó dos cables, y ni la investigación pudo concluir si fue a propósito.

El dolor de quien vigila: un barco **lento o parado sobre un cable** puede estar atracado, fondeado esperando, **a la deriva**, sosteniéndose con sus máquinas o **arrastrando el ancla**. Desde la posición sola no se distinguen. Hoy es una sospecha; Vigía da una **razón física, medible y contestable**.

## Qué hace
1. Dibuja ~700 cables reales y un **corredor de 2 km** a cada lado.
2. Escucha a los barcos por **AIS** en vivo (AISstream, estaciones en tierra).
3. Da un **nivel de atención** (ALTO / MEDIO / BAJO) a los barcos lentos o parados dentro de un corredor.
4. Hace la **prueba de deriva pasiva**: compara lo que el barco se movió con lo que se movería **sin motor** (corriente + 2,5 % del viento, de Open-Meteo). Resultado: *deriva*, *fijo*, *propulsión* o *indeterminado*.
5. Baja las falsas alarmas: aprende puertos y radas del propio AIS, reconoce barcos amarrados e inmóviles durante horas.
6. Deja evidencia: **recibo** descargable por alerta, **sellos** horarios encadenados con hash y un panel público de **lo medido**.

## Qué se ve en la pantalla (`/`)
Pasa el ratón por cada contador y título: la propia pantalla explica qué significa.
- **Encabezado** con cinco contadores: *Buques*, *En corredor*, *Atención alta*, *Media*, *Silencios*.
- **Globo 3D** con los cables luminosos y los barcos; anillos rojo / ámbar / celeste sobre los que tienen atención.
- **Atención** (lista de barcos a mirar), **Silencios en corredor** (barcos que dejaron de emitir) y **Recorridos largos** (informativo).
- **Zonas escuchadas:** dónde vemos y dónde **no** («sin señal»).
- **Tarjeta del barco** con la prueba de deriva (observado frente a lo que haría el agua), avisos y **descarga del recibo**.
- **Botones:** *Leyenda* (cómo leer el mapa), *Cómo se calcula*, *Lo medido* (validaciones con fecha y límites) y *Replay 3 h*.
- **Pulsa un cable** para **investigar** qué barcos estuvieron sobre él en las últimas 6, 24 o 72 h, y descargar un **informe** sellado con hash.
- Todo dato simulado lleva el banner **SIMULADO**.

Explicación pantalla por pantalla, reglas exactas y guion de demostración: secciones 5, 6 y 11 del [pitch](docs/PITCH.md).

## Lo que está medido (y lo que no)
| Medido | Resultado |
|---|---|
| Error del modelo de corrientes frente a boyas reales (NOAA), 6 regiones | Báltico 95 %, Perú 85 %, Mar del Norte 77 %, Mediterráneo 56 %, Taiwán 53 %, Mar Rojo 42 % de casos dentro de 0,4 kn → tolerancia por región |
| Consistencia con el estado declarado por los barcos (AIS real) | 3 de 493 «amarrados» salen «deriva» (0,6 %) |
| Rendimiento | API ~0,1 s con la tarea de precalentado; cálculo completo 4–6 s con ~8 400 barcos |
| Pruebas | 92 del backend, todas OK |

**No sabemos:** cuántas alertas son falsas; si un arrastre real se vería como nuestras señales; la cobertura fuera de Europa del norte (el AIS gratuito vio 0 barcos en Mar Rojo, Golfo y Perú). Los límites completos están en la sección 9 del pitch.

---

## Estructura del repositorio
```
backend/                  Django 4.2 + DRF + PostGIS + Redis + Celery
  mares/apps/cables/      EL PRODUCTO: cables, estados, prueba de deriva, sellos, API pública
  mares/apps/detection/   monitor AIS (AISstream) e historial de posiciones
  mares/apps/core/        registro de peticiones
frontend/                 Next.js 14 + React 18 + TypeScript + MapLibre (globo)
  src/app/page.tsx        la pantalla pública
  src/components/globe/   globo, panel de mando, «Lo medido»
  src/lib/marca.ts        el nombre del producto (se cambia ahí)
scripts/                  verificar_recibo.py, verificar_sellos.py, maury_valida.py
docs/                     pitch, estado técnico, plan, propuestas
```
(El paquete de Python se llama `mares` por historia; el nombre público es **Vigía**.)

## Requisitos
- Python 3.12 · Node.js 18+ · Redis 7
- **PostgreSQL con PostGIS 3** (lo más simple es un contenedor; ver abajo)
- Opcional: una clave gratuita de **AISstream** para tráfico real; sin ella, el simulador (rotulado SIMULADO)

## Qué NO está en el repositorio (hay que instalarlo)
Por tamaño (GitHub rechaza archivos de más de 100 MB) se dejaron fuera solo cosas que se regeneran con un comando; todo lo demás está tal cual. **`backend/.env` tampoco se sube** (lleva claves): se crea a partir de `backend/.env.example`, ver «Configuración (`backend/.env`)».
| Falta | Peso | Cómo se obtiene |
|---|---|---|
| `frontend/node_modules/` | ~550 MB | `cd frontend && npm install` |
| `frontend/.next/` | ~130 MB | se crea solo con `npm run dev` o `npm run build` |
| `.venv/` y `backend/.venv/` (entorno de Python) | ~1,3 GB | `python3 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt` |
| `backend/mares/storage/` (cachés de Copernicus) | ~670 MB | se descargan solas cuando hacen falta (solo las usan antiguas funciones de pronóstico; Vigía no las necesita) |
| La base de datos (PostGIS) y Redis | — | ver «Puesta en marcha»: un contenedor `postgis/postgis` y `redis`; luego `migrate` y `cargar_cables` |

## Levantarlo: ¿cuántos comandos son?
**No son solo dos** (uno de Django y otro de React): Vigía necesita **cinco piezas corriendo**.

| Pieza | Para qué | Cómo se arranca |
|---|---|---|
| **PostgreSQL con PostGIS** | guarda cables, historial AIS y sellos | un contenedor (se hace una vez) |
| **Redis** | guarda la última posición de cada barco y la caché | un contenedor (una vez) |
| **API (Django)** | sirve los datos en el puerto 8001 | `python manage.py runserver 8001` |
| **Pantalla (Next.js / React)** | la web en el puerto 3001 | `npm run dev -- -p 3001` |
| **Monitor AIS** | trae los barcos en vivo (sin él, no hay barcos) | `python manage.py monitor_ais` (real) o `python manage.py simular_ais` (SIMULADO) |
| *(opcional)* Celery worker + beat | precalienta la API y sella las alertas cada hora | `bash backend/celery_worker.sh` y `bash backend/celery_worker.sh beat` |

### Lo fácil: dos comandos, uno por terminal
Con la base de datos y Redis ya corriendo y todo instalado (ver «Instalación»), desde la raíz del repositorio:
```bash
# Terminal 1 — BACKEND: prepara la base, arranca la API y el monitor de barcos (Ctrl+C para los dos)
bash scripts/backend.sh              # barcos REALES (usa AISSTREAM_API_KEY de tu backend/.env)
bash scripts/backend.sh --simulado   # o barcos SIMULADOS (rotulados «SIM ·»)

# Terminal 2 — FRONTEND: la pantalla (Ctrl+C para parar)
bash scripts/frontend.sh
```
Abre http://localhost:3001. La primera carga tarda ~15 s y los barcos aparecen al cabo de unos minutos. La primera vez, `backend.sh` también migra la base y carga los cables (~20 s); `frontend.sh` instala las dependencias si faltan. La salida del backend lleva etiquetas (`[api]`, `[barcos]`) para distinguir qué proceso habla.

**¿Prefieres una sola terminal?** `bash scripts/levantar.sh` arranca todo en segundo plano (registros en `.run/`) y `bash scripts/apagar.sh` lo para.

### A mano (tres terminales)
```bash
# Terminal 1 — API
source .venv/bin/activate && cd backend && python manage.py runserver 8001
# Terminal 2 — web
cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1 npm run dev -- -p 3001
# Terminal 3 — barcos (elige UNO)
source .venv/bin/activate && cd backend && python manage.py monitor_ais        # real
source .venv/bin/activate && cd backend && python manage.py simular_ais --buques 300   # simulado
```

## Instalación (se hace una sola vez)
```bash
# 1. Base de datos y Redis (contenedores). Usuario, contraseña y base deben coincidir con DATABASE_URL de tu backend/.env
#    (con el .env.example: usuario vigia, base vigia).
docker run -d --name vigia-pg -p 5432:5432 \
  -e POSTGRES_USER=vigia -e POSTGRES_PASSWORD='<la misma contraseña de DATABASE_URL>' -e POSTGRES_DB=vigia \
  postgis/postgis:15-3.4
docker run -d --name vigia-redis -p 6379:6379 redis:7

# 2. Backend (entorno de Python en la RAÍZ del repositorio: .venv)
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

# 2b. Tu configuración: copia la plantilla y rellénala (ver «Configuración»)
cp backend/.env.example backend/.env

# 3. Web
cd frontend && npm install && cd ..

# 4. Base de datos: tablas y cables
cd backend
python manage.py migrate
python manage.py cargar_cables      # ~700 cables y ~1 900 puntos de amarre (TeleGeography); ~20 s
```
**Consejos:** deja el monitor AIS corriendo **≥ 40 minutos** antes de presentar (la prueba de deriva, los recorridos largos y el replay necesitan historial). La primera petición a la API tarda ~10 s en frío; con la tarea `precalentar_buques` (Celery) activa, ~0,1 s.

> **Nota:** el PostGIS que trae el Postgres de algunas distribuciones (p. ej. Fedora) puede estar roto (`undefined symbol: heap_datum_check`). Si te pasa, usa el contenedor de arriba. Si ya tienes Postgres en el puerto 5432, cambia el puerto del contenedor (`-p 5433:5432`) y el de `DATABASE_URL`.

### Configuración (`backend/.env`)
El archivo `backend/.env` **no está en el repositorio**: se crea con `cp backend/.env.example backend/.env` y se rellena. La plantilla comentada es [`backend/.env.example`](backend/.env.example). **Guarda una copia de tus valores reales en un gestor de contraseñas**; es lo que necesitas si cambias de equipo.

| Variable | ¿Obligatoria? | Qué es y de dónde sale |
|---|---|---|
| `SECRET_KEY` | sí | Clave de Django. La generas tú: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `ALLOWED_HOSTS` | sí | `localhost,127.0.0.1` en local |
| `DATABASE_URL` | sí | `postgis://USUARIO:CONTRASEÑA@localhost:5432/vigia`; debe coincidir con el contenedor de PostGIS |
| `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | sí | Con Redis local: los valores del `.env.example` sirven tal cual |
| `AISSTREAM_API_KEY` | para barcos **reales** | Clave **gratuita** de [aisstream.io](https://aisstream.io) (entras con GitHub y creas una API key). Sin ella: `bash scripts/backend.sh --simulado` |
| `CABLES_CORREDOR_M`, `AIS_HISTORY_INTERVAL_SECONDS`, `AIS_HISTORY_RETENTION_DAYS` | no | Ajustes; tienen valor por defecto |
| `CORS_ALLOWED_ORIGINS`, `REDIS_PASSWORD`, `DB_SSLMODE`, `TRUSTED_PROXY_COUNT` | solo producción | Ver `settings/production.py` |

**APIs externas que usa el proyecto**
| Servicio | Para qué | ¿Hay que registrarse? |
|---|---|---|
| [AISstream](https://aisstream.io) | posiciones de barcos en vivo | **Sí**, clave gratuita en `AISSTREAM_API_KEY` |
| [Open-Meteo](https://open-meteo.com) (corriente marina y viento) | prueba de deriva pasiva | No (uso no comercial, sin clave) |
| [TeleGeography](https://github.com/telegeography/www.submarinecablemap.com) | cables y puntos de amarre | No (datos abiertos; los carga `cargar_cables`) |
| [Copernicus Marine](https://marine.copernicus.eu) | **solo** para medir el modelo de corrientes (`scripts/maury_valida.py`) | Cuenta gratuita; se inicia con `copernicusmarine login` (se guarda fuera del repo, no va en `.env`) |

Las variables de Global Fishing Watch y otras que aparecen en versiones antiguas del `.env` **no las lee el código actual**; no hacen falta.

## API pública (sin sesión, solo lectura)
| Ruta | Qué entrega |
|---|---|
| `GET /api/v1/cables/` | cables (GeoJSON) |
| `GET /api/v1/cables/amarres/` | puntos de amarre |
| `GET /api/v1/cables/buques/` | barcos en vivo, nivel de atención, prueba de deriva, silencios, método |
| `GET /api/v1/cables/replay/?horas=3` | pistas recientes de los barcos con atención |
| `GET /api/v1/cables/<slug>/historial/?horas=24` | barcos que estuvieron sobre un cable en las últimas horas (investigar un incidente; hasta 72 h) |
| `GET /api/v1/cables/sellos/` | cadena pública de alertas selladas |
| `GET /api/v1/cables/validacion/` | cifras medidas con fecha y límites |

Documentación interactiva: `/api/docs/`. Salud del servicio: `/health/`. El panel `/admin/` usa un usuario de Django que creas tú (`python manage.py createsuperuser`).

## Verificación
```bash
# Pruebas del backend (necesitan una base PostGIS de pruebas)
cd backend && python manage.py test

# Frontend
cd frontend && npx tsc --noEmit && npx next lint && npx next build
node --experimental-strip-types frontend/tools/probar_replay.mts

# Comprobar un recibo o la cadena de sellos SIN usar el código del proyecto
python3 scripts/verificar_recibo.py recibo-<mmsi>-<hash>.json
python3 scripts/verificar_sellos.py http://localhost:8001/api/v1/cables/sellos/

# Medir la prueba de deriva con AIS real acumulado
cd backend && python manage.py validar_deriva_pasiva --horas 8

# Medir el modelo de corrientes frente a boyas reales (necesita: copernicusmarine login)
pip install pandas xarray netCDF4 copernicusmarine numpy
python3 scripts/maury_valida.py --regiones todas

# Mapa del código y trinquete de calidad
sysmap check
```

## Seguridad
- **`backend/.env` no se sube** (está en `.gitignore`). Se crea desde `backend/.env.example`; guarda tus valores reales en un gestor de contraseñas, porque si pierdes el equipo no hay otra copia.
- La API es pública y de solo lectura, con límite de peticiones por IP.
- Los recibos y sellos prueban que un archivo **no cambió**; no prueban que los datos de origen sean correctos.

## Historia
El proyecto nació como **MARES**, un sistema de búsqueda y rescate marítimo. Vigía es un producto distinto y **no incluye** esa parte. El sistema anterior sigue en el historial de git (etiqueta `mares-sar-v1`).

## Para saber más (Google o una IA)
- Términos útiles para buscar: *submarine cable faults anchoring statistics ICPC*, *Yi Peng 3 cable damage Baltic*, *AIS gap detection subsea cable*, *ship leeway windage coefficient*, *Global Drifter Program hourly data*.
- Preguntas para un asistente de IA, cómo verificar lo que responda y fuentes por tema: **sección 12 del [pitch](docs/PITCH.md)**.
- Análisis del problema con fuentes: [`docs/PLAN_GLOBAL_CABLES_Y_CORRIENTES.md`](docs/PLAN_GLOBAL_CABLES_Y_CORRIENTES.md). Ideas y próximos pasos: [`docs/PROPUESTAS.md`](docs/PROPUESTAS.md).

## Datos y atribuciones
- **Cables y puntos de amarre:** TeleGeography ([submarinecablemap.com](https://www.submarinecablemap.com)); licencia para uso comercial **sin confirmar**.
- **AIS:** AISstream (estaciones terrestres; cobertura parcial).
- **Corriente y viento:** Open-Meteo.com (CC BY 4.0, uso no comercial).
- **Validación de corrientes:** Copernicus Marine Service (reanálisis) y Global Drifter Program de NOAA (CC BY 4.0).
- **Mapa base:** Esri.
