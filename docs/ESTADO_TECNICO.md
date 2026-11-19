# Vigía (Mares global)

*18-nov-2026. Estado real de lo construido y medido; el botón de recibo, el panel «Lo medido» y el replay se verificaron en el navegador. Lo no verificado lleva **[sin verificar]**. Resumen para el jurado, con el problema, las pantallas y las reglas explicadas: [`PITCH.md`](PITCH.md).*

## Qué es
La pantalla principal (`/`) es un **globo 3D público** con los cables submarinos del mundo y los buques que pasan por encima, en vivo. Marca con un **nivel de atención** (ALTO / MEDIO / BAJO) a los buques lentos o parados sobre un cable, y para cada uno hace una **prueba de deriva pasiva**: ¿se mueve como lo movería el agua, está sujeto al fondo, o se mueve de un modo que el agua no explica?

## Cómo arrancarlo (demo local)
1. **Base de datos con PostGIS.** El PostGIS del Postgres del sistema en la máquina de desarrollo tiene la biblioteca rota (`postgis-3.so: undefined symbol: heap_datum_check`), así que ahí no se pueden crear tablas con geometría. Usar un contenedor PostGIS y apuntar `DATABASE_URL` a él. (Arreglo probable, no probado: actualizar juntos `postgresql18*` y `postgis*` del sistema.)
2. `cd backend && python manage.py migrate && python manage.py cargar_cables` (~700 cables y ~1 900 puntos de amarre de submarinecablemap.com; calcula los tramos y corredores; ~20 s).
3. **AIS real:** con `AISSTREAM_API_KEY` en `backend/.env`, el worker `monitor_aisstream` escucha las zonas de `AISSTREAM_ZONAS` (`settings/base.py`). Sin clave o sin cobertura: `python manage.py simular_ais --buques 300` genera tráfico **SIMULADO** (rotulado «SIM ·», MMSI 9990…; la pantalla lo avisa). Los escenarios guionados del simulador demuestran cada veredicto con la corriente y el viento reales del punto.
4. `python manage.py runserver 8001`; en `frontend/`: `NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1 npm run dev -- -p 3001`. Abrir http://localhost:3001.
5. **Validar la prueba de deriva** (necesita ≥ 40 min de AIS acumulado): `python manage.py validar_deriva_pasiva --horas 2`. Guarda `backend/mares/apps/cables/validacion_datos/deriva_pasiva.json`.
6. La **tarea periódica** `mares.cables.precalentar_buques` (Celery beat, cada 15 s, con cerrojo contra apilamiento) deja la respuesta en caché 45 s: la petición tarda ~0,1 s (medido con 3 300 buques; la tarea tarda ~7 s). Sin la tarea, la primera petición calcula bajo demanda (~10 s en frío).
7. **Recibo de una alerta:** en la tarjeta del buque, «Descargar recibo». Verificar con `python3 scripts/verificar_recibo.py recibo-….json` (recalcula el SHA-256 sin usar código del proyecto). El hash prueba que el archivo no cambió; no que los datos de origen sean correctos.

## La prueba de deriva pasiva
Un buque sin propulsión se mueve con la corriente más una fracción del viento. Con la pista de las últimas 3 h (≥ 3 posiciones y ≥ 30 min) se ajusta una recta (mínimos cuadrados) y se compara con `corriente + 2,5 % del viento`, con tolerancia `base regional + 1,5 % del viento` (la base va de 0,4 kn a 1,0 kn según la región, medida contra boyas reales: ver «Corrientes del modelo frente a boyas reales»; es la incertidumbre del modelo de corrientes y del arrastre del viento sobre cada casco):

| Veredicto | Qué significa | Efecto en el nivel |
|---|---|---|
| **deriva** | Se mueve como el agua y el viento lo moverían | MEDIO (ALTO si lleva ≥ 60 min) |
| **fijo** | El agua lo arrastraría y no se mueve: fondeado o amarrado | BAJO (MEDIO si ≥ 60 min) |
| **propulsión** | Se mueve distinto de lo que haría el agua | ALTO si va lento |
| **indeterminado** | Está quieto y el agua casi no lo movería: no se puede distinguir | regla simple |

Fuente de corrientes y viento: **Open-Meteo.com (CC BY 4.0, gratuito solo para uso no comercial, con límite de llamadas)** `[licencia comercial: sin verificar]`. Código: `backend/mares/apps/cables/deriva.py`. En pantalla: panel con los números y, en el mapa, la pista real (puntos), lo observado (línea blanca) y lo que haría el agua (línea cian punteada) a 3 h.

## Qué se construyó
- **Backend** (`backend/mares/apps/cables/`): `Cable`, `CableTramo` (tramos de ~50 km con corredor de 2 km), `PuntoAmarre`; `estados.py` (reglas puras); `deriva.py` (prueba y fuerzas); API pública sin sesión `GET /api/v1/cables/`, `/cables/amarres/`, `/cables/buques/`; comandos `cargar_cables`, `simular_ais`, `validar_deriva_pasiva`.
- **Monitor AIS** (`detection/tasks.py`, `ais_history.py`, modelo `AISPosicion.nav`): zonas configurables; guarda el estado de navegación declarado; el índice de Redis ya no se reescribe en cada mensaje, no crece sin límite y no se pisa entre procesos.
- **Frontend** (`frontend/src/components/globe/`, `src/lib/cables.ts`): globo MapLibre con cables luminosos y pulsos de datos, buques con flecha de rumbo, anillos de alerta, panel de mando, cobertura por zona y «cómo se calcula».
- **Pruebas:** suite completa del backend **92, todas OK** (corrida del 18-nov tras la última edición, en un entorno creado solo con `requirements.txt`; 78 son de la app de cables). El frontend no tiene ejecutor de pruebas: se verifica con `tsc`, `next lint`, `next build`, `frontend/tools/probar_replay.mts` y el cruce del hash del recibo contra Python. Se comprobó rompiendo a propósito reglas clave: las pruebas fallaron en cada caso.

## Falsa alarma sistemática encontrada y corregida: buques amarrados en puerto (18-nov)
Al revisar la pantalla con tráfico real, los primeros ALTO eran barcos amarrados en puertos (archipiélago de Estocolmo, Kristiansand…) con ~5 h a 0 kn a unos cientos de metros del cable, que ni el punto de amarre (3 km) ni las zonas habituales (≥ 5 buques) reconocían. Regla nueva (`estados.horas_inmovil`): si el buque no salió de **250 m** durante ≥ **3 h** de pista, **el ALTO baja a MEDIO** (no arrastra ni deriva; sigue siendo un fondeo o atraque sobre el corredor). «Propulsión» se mantiene en ALTO (puede ser un buque que se sostiene con sus máquinas). En una foto de tráfico real los ALTO pasaron de 20 a 9; **no se sabe cuántos de los restantes son reales**. La tarjeta lo explica y el recibo lo registra. Un buque fondeado con cadena larga puede girar más de 250 m y seguir contando como no inmóvil.
**Límite de diseño que conviene decir:** las reglas de «lento/parado» detectan fondeos sobre el corredor, **no un arrastre a velocidad de navegación** **[no verificado con datos de incidentes: no los tenemos]**.

## Señal informativa: recorrido largo dentro del corredor (18-nov)
Para no ser ciegos a un buque que avanza con el ancla abajo, se marca (sin subir su nivel) al buque **en marcha (≥ 3 kn) que lleva ≥ 15 km seguidos dentro de un corredor**, con posiciones separadas ≤ 25 min (con huecos no se une). Medición con AIS real (8 h, 12 062 buques): **11 buques ≥ 15 km seguidos, 30 ≥ 10 km, 5 ≥ 20 km** — muy selectiva, y todos eran tráfico normal de 8–33 kn por rutas paralelas a cables. **No sabemos si un arrastre real se vería así** (no hay incidentes); por eso es *informativa*: lista en pantalla y entra en los sellos (`recorridos`) para compararla después con fallos reales, igual que las alertas. Una primera versión de la medición dio cifras inflaladas (unía posiciones separadas por horas); el corte por hueco lo corrige y tiene prueba con mutación.

## Corrientes del modelo frente a boyas reales («Maury-valida», 18-nov)
`python3 scripts/maury_valida.py` (necesita `pip install -r scripts/requirements-maury.txt` y `copernicusmarine login`, que hace la persona). Compara el reanálisis de Copernicus (Mar del Norte: `cmems_mod_nws_phy-uv_my_7km-2D_PT1H-i`, horario con mareas; Báltico: `cmems_mod_bal_phy_my_P1D-m`, medias diarias) con boyas del Global Drifter Program de NOAA (CC BY 4.0). **24 boyas-región (las 12 con más datos por región, 40 días cada una), 0 descargas fallidas.** Resultado (`validacion_datos/maury_valida.json`, también en el panel «Lo medido»):

| Caso | Boyas | Error mediano | p90 | Dentro de 0,4 kn |
|---|---|---|---|---|
| Báltico, medias diarias, boya con ancla (~15 m) | 5 | 0,17 kn | 0,34 kn | **95 %** |
| Mar del Norte, horario, boya con ancla | 5 | 0,28 kn | 0,77 kn | **69 %** |
| Mar del Norte, horario, boya sin ancla (sup.+viento) | 8 | 0,27 kn | 0,65 kn | **73 %** |

- **Ampliado a seis regiones el mismo día** (`--regiones todas`, 72 boyas-región; el reanálisis global de 1/12° con medias diarias fuera de Europa), con un resultado importante: **el modelo de corrientes es mucho peor fuera del Báltico**.

| Región (modelo en superficie, boyas con ancla salvo la fila Báltico) | Boyas | Error mediano | p90 | Dentro de 0,4 kn | Tolerancia ahora |
|---|---|---|---|---|---|
| Báltico (medias diarias) | 4 | 0,17 kn | 0,34 | 95 % | 0,4 |
| Perú | 12 | 0,21 kn | 0,44 | 85 % | 0,5 |
| Mar del Norte (horario, 3 h vs instante) | 7 | 0,22 kn | 0,66 | 77 % | 0,7 |
| Mediterráneo | 12 | 0,36 kn | 0,73 | 56 % | 0,8 |
| Taiwán | 6 | 0,38 kn | 0,93 | 53 % | 1,0 |
| Mar Rojo y Golfo | 9 | 0,47 kn | 1,00 | 42 % | 1,0 |

- **Qué cambió en el código:** `deriva.TOL_REGIONES` fija la tolerancia de cada región en el p90 medido, redondeado hacia arriba (antes: 0,4 kn para todos por suposición). **Costo:** con 1,0 kn la prueba casi no discrimina a un buque lento en Mar Rojo o Taiwán; es lo que el modelo permite allí, y la tarjeta lo avisa. Con AIS real (1 126 buques, composición distinta a la corrida anterior, por eso no es comparable punto a punto): de 493 declarados «amarrado», 3 «deriva» (0,6 %) y 3 «propulsión»; con motor y en movimiento, «propulsión» 66 % (antes 77 %), «deriva» 9 %. Un cambio de una tabla, reversible.
- **¿Ayuda un modelo regional de mayor resolución? Casi nada (medido).** Mediterráneo, mismas 12 boyas: modelo global de 1/12° (~8 km) mediana 0,36 kn, p90 0,73, 56 % dentro de 0,4 kn; reanálisis regional de 4,2 km (`cmems_mod_med_phy-cur_my_4.2km_P1D-m`) mediana 0,33 kn, p90 0,72, 62 %. Una mejora pequeña: el error no se debe sobre todo a la resolución (probable: remolinos, arrastre del viento sobre la boya, diferencia de profundidad; **no se separó la causa**). Por eso **no** se integró en producción (exigiría credenciales de Copernicus en el servidor para una ganancia marginal).
- **Fuera de estas seis cajas la tolerancia NO está medida** (0,4 kn sin respaldo).
- **Promediar el modelo en la misma ventana de 3 h** que la velocidad del buque mejora el error solo un 5–7 % (mediana 0,27→0,26 kn): no compensa las llamadas extra; no se implementó.
- **El modelo frente a «sin corriente»:** error mediano 0,27 kn contra 0,40 kn de la rapidez de la boya: en el Mar del Norte el modelo explica una parte modesta del movimiento.
- **Límites:** se valida el modelo de Copernicus, no el de Open-Meteo (su histórico 1993-2019 no se puede consultar; sí se comprobó que Open-Meteo varía con la marea); boyas con ancla miden a ~15 m y el modelo a superficie; las sin ancla incluyen el arrastre del viento, sin separar; pocas boyas y pocos años (indicativo, no definitivo).

## Alertas selladas (validación posterior)
Cada hora (`mares.cables.sellar_alertas`, minuto 5) se guarda un **sello** con las alertas ALTO/MEDIO de buques **reales** (nunca simulados) y el hash del sello anterior. API pública `GET /api/v1/cables/sellos/` (últimos 100, con comprobación de integridad); `python manage.py sellar_alertas [--verificar]`; verificador sin dependencias del proyecto: `python3 scripts/verificar_sellos.py <URL o archivo>`. **Límite:** la cadena prueba el orden dentro de nuestra base; quien la opera podría reescribirla entera. Para fijar la fecha hay que publicar el último hash fuera (p. ej. un commit). **Aún no hay resultados:** el siguiente paso es comparar con fallos de cable reportados públicamente, y un resultado «sin eventos» también se publica.

## Corriente cerca de la costa (18-nov, segunda pasada)
Donde la celda de 0,1° no tiene corriente (tierra/costa), se toma la del **agua más cercana hasta 3 celdas (~33 km)**; el resultado lleva `aprox_km`, la pantalla lo avisa y la tolerancia crece hasta +0,3 kn (a ≥ 10 km). Con 8 h de AIS real y 1 500 buques: **evaluados 1 152 (77 %) frente a 903 (60 %)** con la versión anterior (ventana de 2 h; no es una comparación idéntica). Entre 229 declarados «amarrado»: 1 «deriva», 26 «fijo», 2 «propulsión», 200 «indeterminado». Con motor y en movimiento: 86 % «propulsión». En vivo, 0 de 168 buques en corredor sin dato; 6 con corriente aproximada (~11 km). **La aproximación no está validada contra corrientes medidas**: solo se comprobó que no inventa deriva en amarrados.
Hallazgo: Open-Meteo devolvió 429 (límite de llamadas) cuando la búsqueda de agua multiplicó las peticiones; una validación hecha en ese estado salió falsa y se descartó. Ahora: un fallo de la API se recuerda 60 s (no como «sin dato» permanente) y las celdas de tierra se recuerdan 24 h.

## Lo que se midió

### Cobertura del AIS gratuito (una ventana de ~100 s)
| Zona | Buques reales |
|---|---|
| Mar del Norte y Canal | ~5 300 |
| Báltico | ~1 550 |
| Mediterráneo oriental | ~130 |
| Estrecho de Taiwán | ~10 |
| Pacífico noreste / Chile norte | 11 / 2 |
| **Mar Rojo, Golfo Pérsico, Perú y Pacífico sur** | **0** |

**El AIS gratuito de AISstream solo cubre bien Europa del norte.** Las zonas de más interés geopolítico quedan ciegas; hace falta AIS satelital (de pago) u otra fuente.

### Validación de la prueba de deriva (903 buques reales con pista y dato de agua, ventana de 2 h)
El estado de navegación lo declara la tripulación y suele estar desactualizado, así que **mide consistencia, no acierto**:

| Declarado | n | deriva | fijo | propulsión | indeterminado |
|---|---|---|---|---|---|
| amarrado | 149 | 0 % | 23 % | **1 %** | 76 % |
| con motor y moviéndose | 266 | 2 % | 3 % | **88 %** | 8 % |
| con motor pero sin moverse | 268 | 0 % | 24 % | 0 % | 75 % |
| amarrado pero su SOG llegó a ≥ 3 kn | 16 | 12 % | 19 % | 69 % | 0 % |
| a vela | 17 | 18 % | 41 % | 18 % | 24 % |

Lectura honesta:
- **No inventa deriva:** ninguno de 149 amarrados fue clasificado «deriva».
- **Reconoce el movimiento con motor** (88 %), y detecta declaraciones viejas: buques que dicen «amarrado» pero circulan a más de 3 kn (uno era un ferry a 18 kn). Ahí la prueba acierta y la declaración está mal.
- **Discrimina poco:** el 75 % de los buques quietos sale «indeterminado», porque el agua casi no los movería. Solo distingue «fijo» cuando el agua es fuerte.
- **Cobertura limitada:** a **597 de 1 500** buques (40 %) no se pudo evaluar por falta de dato de corriente (el modelo, de ~8 km, no llega a la costa ni a puertos). Justo donde ocurren la mayoría de los daños por ancla.
- **No hay un incidente real de arrastre de ancla** con el que comparar.

### Ruido de alertas (tráfico real, ~8 800 buques, ~890 en corredor)
- **La prueba de deriva casi no reduce el ruido:** cambió el nivel de solo 33 de 400 alertas (16 ALTO→MEDIO, 13 MEDIO→ALTO, 4 MEDIO→BAJO). Su valor es **explicar**, no filtrar. *(Corrijo lo que esperaba antes.)*
- **Zonas de estacionamiento habitual** (celdas de ~2 km donde ≥ 5 buques distintos se detuvieron en 24 h; 523 aprendidas del propio AIS con poco historial): bajaron las alertas ALTO+MEDIO de **152 a 111 (−27 %)**, con 42 reclasificadas a BAJO. Siguen quedando ~110 alertas de atención entre ~8 800 buques; **no se sabe cuántas son falsas**.

### Rendimiento
12 000 buques contra 40 778 tramos de cable: ~1,8 s para el cruce espacial. Petición completa: ~10 s en frío, ~0,25 s con caché.

## Límites que hay que decir en voz alta
- **Los umbrales son heurísticas sin validar con incidentes reales.** El nivel es «atención», no acusación: ninguna regla distingue con certeza un fondeo legítimo de un arrastre de ancla.
- **Las corrientes y el viento son de un modelo** (Open-Meteo, ~8 km). Sin dato cerca de la costa (40 % de los casos en la validación).
- **El windage (2,5 %) es una constante**: cada casco arrastra distinto.
- **«Silencio en corredor»** puede ser salir del alcance de los receptores.
- **Cables:** datos de TeleGeography, **licencia comercial sin confirmar**; no se versionan en git; la pantalla los atribuye.
- **Corrientes/viento:** Open-Meteo, no comercial.
- El estado «amarrado» lo teclea la tripulación y suele estar viejo.
- Los cables que cruzan el antimeridiano (±180°) se parten y los tramos pegados a él no tienen polígono (se resuelven por distancia directa).
- Las zonas habituales se aprenden del historial: con poco historial detectan menos.

## Replay de las últimas horas (18-nov)
Botón «Replay 3 h»: reproduce las últimas 3 h de los buques con atención (ALTO/MEDIO) o con recorrido largo (hasta 150). `GET /api/v1/cables/replay/?horas=3` (público, 0,5–6 h, caché de 30 s) entrega por buque su pista `[minutos antes del final, lng, lat, sog]` de la base de historial, cerrada con la posición actual. La interpolación es **lineal entre posiciones guardadas cada ~10 min** (no es la trayectoria real entre ellas); un buque aparece cuando existe su primera posición de la ventana. La cámara va a donde están los buques. Interpolación en `frontend/src/lib/replay.ts`, comprobada sin navegador con `node --experimental-strip-types frontend/tools/probar_replay.mts` (esa comprobación encontró y corrigió un punto repetido en el rastro). **Verificado en pantalla** (deslizador, pausa, puntos con el color del nivel); con buques casi inmóviles los rastros no se aprecian: se ven mejor en los de recorrido largo. Tres pruebas del backend.

## Investigar un cable (19-nov)
`GET /api/v1/cables/<slug>/historial/?horas=24` (público; 1–72 h; caché de 30 s): barcos que estuvieron dentro del corredor de **ese** cable según el historial AIS (una posición cada ~10 min, ~60 días). Por barco: minutos dentro, minutos lento (< 3 kn), velocidad mínima y media, último aviso y última posición; ordenados por tiempo lento; hasta 100. Los huecos de datos de más de 25 min no cuentan como tiempo dentro. Consulta con índice espacial por tramo: 10–70 ms con datos reales. En pantalla: pulsar un cable → «Investigar últimas 6 / 24 / 72 h» y «Descargar informe» (JSON con hash, verificable con `scripts/verificar_recibo.py`). **Límite:** estar sobre un cable no prueba que lo dañara, y un barco con el AIS apagado o fuera de alcance no aparece.

## Defectos de pantalla encontrados con el navegador (19-nov)
- **Cables que no volvían:** si la primera petición de cables fallaba, el error lo borraba la siguiente consulta de barcos que sí salía bien y los cables no se pedían de nuevo. Ahora se reintentan con espera creciente y se avisa.
- **Flechas de los barcos que nunca se dibujaron:** con `icon-rotation-alignment: 'map'` y rumbo variable, la proyección de globo de MapLibre no dibuja nada (medido: 0 de 3 811). Se usa `'viewport'` y se resta el giro del mapa.
- **Barcos casi invisibles:** puntos de 2 px y color pálido; ahora más grandes, con borde y mejor contraste, más una **Leyenda**.
- **Mapa vacío tras recrearse:** el aviso de «mapa listo» no se reiniciaba; ahora sí. Se añadió aviso si el navegador pierde el contexto gráfico (con un falso positivo propio descubierto y corregido: MapLibre lo pierde a propósito al destruir un mapa).

## Rendimiento (18-nov)
`cerca_de_amarre` convertía a `geography` y no usaba el índice espacial: 4,7 s con 394 buques lentos. Con prefiltro por caja (corregido por latitud): 0,02 s, **resultado idéntico verificado con datos reales (245 de 394)**. El cálculo completo con ~8 400 buques bajó de 9–12 s a 4–6 s.

## Historia: de MARES (rescate) a Vigía
El proyecto nació como **MARES**, un sistema de búsqueda y rescate marítimo para capitanías peruanas. El 18-nov-2026 se convirtió en **Vigía**, un producto distinto: la parte de rescate (usuarios, capitanías, incidentes, simulación de deriva con OpenDrift, mapa de incidentes) **se eliminó por completo**, junto con la capa de eventos de pesca de GFW, NAVTEX y las métricas de capitanía. En el camino se corrigieron errores concretos: una falsa alarma sistemática (barcos amarrados en puerto), el modelo de tolerancia (medido contra boyas reales), consultas lentas, una función que se tragaba errores, una contraseña de desarrollo escrita en el código y archivos de entorno versionados. Se conserva solo lo que Vigía usa: `cables` (el producto), `detection` (el monitor AIS) y `core` (registro de peticiones).
- El código y los documentos del sistema de rescate siguen en el historial de git (etiqueta `mares-sar-v1`) y una copia de los documentos está en `~/Documentos/Mares-A-archivo-SAR/`.
- **Deuda declarada:** (1) dos importaciones dentro de funciones que sysmap ve como ciclos se dejaron; (2) falta un archivo `LICENSE` (lo elige quien publique el repositorio); (3) el baseline de `sysmap` registra los hallazgos aceptados.

## Pendiente
- **Maury 2.0** (corrientes medidas por la flota): no está hecha. La infraestructura (pistas + modelo de agua) ya existe.
- **Validar con un incidente real** (*Yi Peng 3*, *Eagle S*): el AIS histórico danés se pide por formulario **[condiciones sin confirmar]**.
- **Más cobertura de AIS:** AIS satelital o receptores propios para Mar Rojo, Golfo Pérsico, Perú.
- **Validar la corriente aproximada** contra corrientes medidas (derivadores, radar HF); hoy solo se midió que no inventa deriva. Un 23 % de los buques de la validación sigue sin dato.
- **Corregir PostGIS** en la máquina de desarrollo.
- Licencias: confirmar TeleGeography y Open-Meteo antes de cualquier uso comercial.
