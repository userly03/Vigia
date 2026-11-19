# Mares global: Vigía + Corrientes medidas por la flota

*18-nov-2026. Lo verificado lleva fuente; mi juicio lleva **[mi estimación]**; lo que no pude confirmar lleva **[sin verificar]**. Nada de esto está probado en código: es un plan.*

## 1. La idea en una frase

Mares deja de ser «un calculador de polígonos de rescate de Perú» y pasa a ser **un observatorio global del tráfico marítimo sobre la infraestructura submarina**, que además **mide las corrientes con los propios barcos**. El rescate queda como un modo secundario.

Las dos opciones que elegiste se refuerzan entre sí:
- **Opción 2 (cables):** ¿qué buque amenaza un cable?
- **Opción 3 (Maury 2.0):** ¿qué corriente mueve a ese buque? Sin esa respuesta no se distingue un barco que se deja llevar por el agua de uno que arrastra el ancla.

## 2. Los cables, explicados

**Qué son.** Más del 95 % del tráfico internacional de datos viaja por cables en el fondo del mar **[no verifiqué esta cifra en esta sesión]**. Un corte deja países o regiones lentas o sin conexión hasta que un barco especial lo repara.

**Cuánto pasa y cuánto cuesta ([fuente](https://www.submarinenetworks.com/en/nv/insights/statistics-on-subsea-cable-fault-and-repair)):**
- Unas **150–200 fallas al año**.
- **70–86 %** las causan la pesca y el anclaje; según la fuente varía (el 86 % viene de un resumen de un proveedor, no del original).
- Reparar un cable de telecomunicaciones cuesta **US$0,5–3 M** según la fuente, y tarda de 2 a 8 semanas.

**Por qué hoy es noticia.** En noviembre de 2024 el carguero *Yi Peng 3* arrastró un ancla unas **180 millas náuticas** por el Báltico y dañó dos cables; la investigación sueca no pudo concluir si fue a propósito ([Baird Maritime](https://www.bairdmaritime.com/security/incidents/swedish-probe-inconclusive-on-evidence-of-deliberate-cable-damage-by-chinese-ship)). Se atribuyó también al *Eagle S* un arrastre de unos 60 millas ([UNITED24](https://united24media.com/latest-news/finland-finds-anchor-tracks-linking-russian-shadow-fleet-tanker-to-cable-damage-4790)); las cifras de longitud varían entre fuentes.

**Qué hace el sistema.** Dibuja cada cable y un «corredor» a su alrededor. Cada buque que entra recibe un estado: *en tránsito*, *parado*, *fondeado*, *a la deriva* o *posible arrastre*. Las alertas se disparan por señales como quedarse quieto sobre el cable, ir lento a rumbo cambiante, o apagar el AIS dentro del corredor.

## 3. La pieza que solo Mares puede aportar: «la prueba de la deriva pasiva»

Un buque lento sobre un cable puede estar **a la deriva** (inofensivo, o en emergencia) o **dando propulsión / arrastrando el ancla**. Mares ya tiene un motor de deriva con corrientes y viento reales. Se simula **cómo se movería el buque si no tuviera motor** desde su último punto «bajo propulsión» y se compara con su track observado:
- Si coincide, el estado es **DERIVA**.
- Si no coincide, es **PROPULSIÓN o POSIBLE ARRASTRE**.

Es una prueba de hipótesis con la incertidumbre impresa, no una acusación. **[Mi idea; no la vi publicada, pero mi búsqueda fue corta]**. Una fuente que revisé menciona usar corriente y viento para comprobar si la deriva explica un track, como un primer paso manual ([blog de Windward](https://windward.ai/blog/subsea-cable-surveys-are-converging-on-the-same-behavioral-signature/); es texto de un proveedor, no un estudio). La automatización con un motor de deriva es lo que aportarían.

## 4. Maury 2.0: corrientes medidas por la flota

**Qué es.** Los barcos que van a la deriva o con rumbo constante son «boyas» involuntarias. Con su AIS se estima la corriente y se compara con Copernicus y con derivadores reales. El nombre viene de las Cartas Piloto de Maury (siglo XIX).

**Honestidad: no es nuevo en el mundo.**
- La empresa **eOdyn** ya vende corrientes derivadas del AIS (producto SeaWaze) desde 2015, y el proyecto **ADEOS** de Copernicus Marine lo validó con altímetros, radares y derivadores ([ADEOS](https://marine.copernicus.eu/about/research-development-projects/2022-2024/adeos)).
- Hay métodos publicados: reconstrucción variacional con AIS ([Benaïchouche et al. 2021](https://www.doi.org/10.3390/RS13163162)) y estela Kelvin ([TU Delft 2024](https://repository.tudelft.nl/record/uuid:78621047-5aa1-40a5-8acd-853e6c8b5800)).
- Lo que sí es de ustedes: **integrarlo con la detección de cables** (separar corriente de propulsión) y **validarlo con derivadores globales** con un marcador abierto.

**Riesgos:** separar la velocidad del buque en el agua de la corriente es difícil; maniobras y viento contaminan; puede salir un resultado nulo. Se publica igual.

## 5. ¿Alguien pagaría? (la respuesta honesta)

**Lo que sí hay:**
- Un problema que cuesta dinero real (ver §2) y un mercado que ya existe: **Windward** publica informes trimestrales de riesgo de cables y vende inteligencia de comportamiento ([Windward](https://windward.ai/knowledge-base/q2-2026-undersea-cables-risk-report/)); **Gatehouse Maritime** vende un producto de monitoreo de cables con AIS, radar y satélite ([Gatehouse](https://gatehousemaritime.com/solutions/critical-offshore-and-subsea-infrastructure-protection/monitor-protect-subsea-cables-and-pipelines/)).
- Señal de gasto público: un blog de Windward cita un paquete de la Comisión Europea de €347 M para cables submarinos (feb-2026). **No lo verifiqué en la fuente primaria.**

**Lo que juega en contra:**
- **Esos competidores combinan satélite, radar, radiofrecuencia y AIS satelital.** Windward sostiene que el AIS solo ya no basta. Con AIS gratuito de estaciones en tierra, Mares llega peor justo en alta mar.
- **Datos de cables:** TeleGeography los vende con **licencia anual de pago**; existe una copia pública en GitHub, pero **no pude confirmar su licencia** ([TeleGeography](https://www2.telegeography.com/license-geocoded-map-data)). Para un concurso suele alcanzar con citar; para vender, no.
- **AISstream** (su fuente) es gratuito, de estaciones en tierra, y pide a los usuarios comerciales abrir un issue; **no pude ver sus términos ni límites** ([AISstream](https://aisstream.io)).
- **No encontré precios públicos** de ninguno de estos servicios.

**Mi lectura [mi estimación]:**
- *Para el concurso:* muy fuerte (tema de actualidad, geopolítico, vistoso).
- *Como negocio:* hay clientes que pagan por cables, pero **un equipo de 3–5 con datos gratuitos no compite hoy con Windward o Gatehouse**. Un nicho creíble sería operadores pequeños o regionales que no pueden pagar a esos proveedores, **pero no tengo evidencia de que existan ni de cuánto pagarían**. Con tus reglas (sin contactos, solo internet), la forma de averiguarlo es publicar una demo abierta y medir interés, como en el plan de RECIBO.
- *Maury 2.0:* sirve como pieza científica y de credibilidad; **no la venderían sola**, porque eOdyn ya existe.

## 6. Lo que se elimina de Mares (propuesta, **nada se borra hasta que confirmes**)

Primero se crea una etiqueta en git (`mares-sar-v1`) para poder volver. Esto es lo que dice `CLAUDE.md` sobre cada pieza; **no he leído el código de cada vista**.

| Vista o módulo | Propuesta | Motivo |
|---|---|---|
| `/mapa` | **Conservar y rehacer** | Base del mapa global |
| `/deteccion` → pestaña AIS en vivo | **Conservar** (pasa a ser núcleo) | Es la entrada de datos |
| `/deteccion` → «GAP events» de GFW | Eliminar | Son eventos de pesca, no silencios de AIS (lo reconocieron ante el jurado) |
| `/deteccion` → NAVTEX | Eliminar | El proveedor devuelve 410 (retirado) |
| `/vigilancia` | Eliminar o fusionar | Capa SAR de GFW sin acceso al dataset + reportes manuales de Perú |
| `/recursos` | Eliminar | Recursos de capitanías peruanas |
| `/metricas` | Eliminar y reemplazar | Métricas SAR por capitanía; se sustituye por el marcador de validación |
| `/boyas`, `/rutas-3d` | Archivar (quitar del menú) | «Más de lo mismo»; no sirven a cables |
| `/incidentes/[slug]` y `/i/[slug]` | **Conservar como modo secundario** | Cuando una alerta es un buque a la deriva, abre el rescate |
| `/login` (PIN de capitanía) | Cambiar a acceso abierto de solo lectura | Un producto global no puede depender de capitanías peruanas |

## 7. Plan de implementación **[mi estimación, sin haber probado nada]**

**Fase 0 (1–2 días): decidir con datos.**
- Etiquetar el repo; sin borrar nada todavía.
- Contar cuántas posiciones AIS recibe AISstream cerca de 5 corredores de cables elegidos (costeros y de mar abierto).
- Confirmar la licencia de los datos de cables y los límites de AISstream.
- **Criterio de parada:** si la cobertura en los corredores es casi nula, se reduce el alcance a zonas costeras densas.

**Fase 1 (semana 1): Guardián de cables.**
- Cargar un conjunto pequeño de cables (10–20) con corredor de unos km.
- Ingerir AIS **solo dentro de esos corredores** y por cuadrículas (no global completo: sería ~decenas de millones de filas por día, **[mi estimación]**).
- Clasificar estados y generar alertas simples. Pantalla: mapa global + panel de alertas.

**Fase 2 (semana 2): la prueba de la deriva pasiva.**
- Adaptar el motor de deriva a un buque. Hay que generalizar la capa de viento (`core/met.py` está pensada para Perú; **comprobar**).
- Salida: «consistente con deriva» o «no consistente», con incertidumbre.
- Medir la **tasa de falsas alertas por cable y por semana** con tráfico real. Ese número es una prueba honesta, aunque no haya incidentes.

**Fase 3 (semana 3): Maury 2.0.**
- Identificar tramos de buques a la deriva en el AIS guardado; estimar corriente; comparar con Copernicus y con derivadores globales (el mismo producto que ya usan).
- Marcador: error de la estimación de la flota frente al modelo frente a «no se mueve».

**Fase 4 (semana 4): validación con un incidente real y pulido.**
- Reproducir el *Yi Peng 3* o el *Eagle S* con AIS histórico. **El archivo histórico de la Autoridad Marítima Danesa se pide por formulario y puede tener costo; no confirmé la ubicación actual ni las condiciones** ([DMA](https://www.dma.dk/safety-at-sea/navigational-information/ais-data/ais-data-management-policy-)). Si no se consigue, la demostración se rotula **SIMULADO**.
- Modo secundario: de una alerta de deriva abrir el rescate.

**Esfuerzo total [mi estimación]:** ~4 semanas con un desarrollador; ~2 con tres a cinco.

## 8. Qué mostraría ante el jurado
1. Un mapa **global** en vivo con cables y buques; alertas reales.
2. **La prueba de la deriva pasiva:** el track real contra la simulación sin motor, con su incertidumbre.
3. **El marcador de Maury 2.0:** quién estima mejor la corriente (flota, modelo o «no se mueve») con derivadores reales.
4. **Una tasa de falsas alertas medida**, en vez de afirmar que «detecta amenazas».
5. El rescate como último paso, ya no como protagonista.

## 9. Lo que no sé
- Si AISstream cubre los corredores elegidos.
- Los términos comerciales de AISstream y de los datos de cables.
- Si el AIS histórico de incidentes reales es accesible.
- Si la prueba de la deriva pasiva separa bien deriva de propulsión; solo el experimento lo dice.
- Si alguien pagaría; no hay precios públicos ni contactos.
