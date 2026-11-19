# Pitch — Vigía

*Documento vivo: se actualiza con cada cambio (ver «Registro de cambios» al final). Cada cifra sale de `docs/ESTADO_TECNICO.md` o de una medición citada ahí; lo no verificado lleva **[sin verificar]**; mi juicio lleva **[estimación]**. Nada aquí promete ganar, ingresos ni que un cliente pagaría.*

**Índice:** 1 En una frase · 2 El problema · 3 A quién le duele y qué resolvemos · 4 Qué hace, en 6 pasos · 5 Lo que se ve en pantalla · 6 Reglas exactas · 7 Qué es nuevo y qué no · 8 Evidencia medida · 9 Límites · 10 Preguntas duras · 11 Guion de 3 minutos y lista de demo · 12 Cómo seguir investigando (Google / IA) · 13 Glosario · 14 Qué pedimos · Registro de cambios

---

## 1. En una frase
**Un globo público y en vivo que muestra qué buques están lentos o parados sobre un cable submarino y, para cada uno, responde con la corriente y el viento reales de ese punto: ¿se está dejando llevar por el agua, está sujeto al fondo, o se mueve de un modo que el agua no explica?**

**En 30 segundos (para decirlo en voz alta):** *«Casi todo el internet entre continentes viaja por cables en el fondo del mar. Cada año se dañan unos 150 a 200, y la mayoría por anclas y redes de pesca. Cuando un barco se queda lento o parado sobre un cable, hoy solo hay una sospecha: ¿está fondeado sin más, a la deriva, o arrastrando el ancla? Vigía lo muestra en un globo, en vivo y sin iniciar sesión, y responde con física —corriente y viento del lugar— si el agua explica su movimiento. Todo con su incertidumbre, sus límites y un recibo verificable. No acusamos a nadie: damos una razón medible para mirar.»*

---

## 2. El problema, explicado desde cero

**2.1 Qué son los cables submarinos.** Son cables de fibra óptica tendidos en el fondo del mar que unen países y continentes. Por ellos pasa la mayor parte del tráfico internacional de datos **[cifra exacta no verificada en esta sesión; búsquedas sugeridas en la sección 12]**. No son satélites: es infraestructura física, cara y muy expuesta.

**2.2 Qué pasa cuando se dañan.** Regiones enteras pueden quedar lentas o desconectadas hasta que un barco especializado repare el cable. Según una fuente del sector: **2 a 8 semanas** de reparación y **US$ 0,5–3 millones** por cable de telecomunicaciones ([submarinenetworks.com](https://www.submarinenetworks.com/en/nv/insights/statistics-on-subsea-cable-fault-and-repair); es una fuente especializada, no un estudio revisado).

**2.3 Cuánto ocurre y por qué.** Unas **150–200 fallas al año**; entre el **70 y el 86 %** las causan la **pesca y el anclaje** (la cifra de 86 % viene de un resumen de un proveedor, no del original; las fuentes varían). Es decir: casi siempre es un barco, casi siempre sin mala intención.

**2.4 Por qué hoy es noticia.** En noviembre de 2024 el carguero *Yi Peng 3* arrastró un ancla unas **180 millas náuticas** por el Báltico y dañó dos cables; la investigación sueca **no pudo concluir** si fue a propósito ([Baird Maritime](https://www.bairdmaritime.com/security/incidents/swedish-probe-inconclusive-on-evidence-of-deliberate-cable-damage-by-chinese-ship)). Al *Eagle S* se le atribuyó un arrastre de unas 60 millas ([UNITED24](https://united24media.com/latest-news/finland-finds-anchor-tracks-linking-russian-shadow-fleet-tanker-to-cable-damage-4790)); las longitudes varían entre fuentes. Esto convirtió un problema técnico en un tema de seguridad.

**2.5 Por qué es difícil de vigilar.** Casi todos los barcos emiten su posición por AIS (un aviso de radio público). Pero un barco **quieto sobre un cable** puede estar en cinco situaciones muy distintas, y desde la posición sola no se distinguen:

| Situación | ¿Peligro para el cable? |
|---|---|
| Atracado o amarrado en un puerto cercano | No |
| Fondeado esperando (rada, mal tiempo, turno de puerto) | Bajo, pero anclar sobre un cable es una infracción |
| **A la deriva** (sin gobierno, avería): se mueve con el agua | Posible: el ancla puede enganchar |
| Sosteniéndose en el sitio con sus máquinas (p. ej. buques de posicionamiento dinámico) | Depende |
| **Arrastrando el ancla** | Sí: es lo que rompe cables |

El que vigila necesita separar esas situaciones. **Esa es la pregunta que Vigía intenta responder con datos físicos.**

---

## 3. A quién le duele, y qué resolvemos

*Los usuarios de abajo son **hipótesis**: no tenemos contactos ni datos de clientes y no hemos validado con ninguno quién usaría o pagaría esto.*

| Quién | Su dolor hoy | Qué le da Vigía | Qué NO le da |
|---|---|---|---|
| **Operador de un cable** (centro de operaciones de red) | «Hay un barco lento sobre mi cable. ¿Llamo a la guardia costera o es un fondeo normal?» Hoy es sospecha y ruido | Una lista ordenada por nivel de atención, con **por qué**: si el agua lo explica o no, con números, y un recibo para escalar el caso | La confirmación de un arrastre; cobertura en alta mar sin receptores |
| **Autoridad marítima / guardia costera** | Cientos de barcos; decidir a cuál contactar por radio primero | Priorización, barcos que «desaparecieron» (silencios) y recorridos largos sobre un corredor | Una decisión legal ni una prueba judicial |
| **Analista, investigador o periodista** | Reconstruir qué hizo un barco y con qué evidencia | Replay de 3 h, pista real, datos abiertos, **alertas selladas** (no se pueden retocar a posteriori) y verificadores independientes | Datos históricos largos (guardamos horas, no años) |
| **Jurado, estudiantes, público** | Un problema invisible: nadie ve los cables | Un globo que lo hace visible y entendible en 90 segundos | — |

**Qué dolores concretos atacamos:**
1. **Sospecha sin explicación** → damos la explicación física («el agua lo movería a X nudos hacia Y; observamos Z»).
2. **Falsas alarmas por puertos y fondeos normales** → aprendemos puertos y radas del propio AIS, y reconocemos los barcos amarrados.
3. **Cajas negras** → todo es contestable: reglas visibles, recibo por alerta, panel de lo medido.
4. **Falta de evidencia** → las alertas se sellan cada hora con un hash encadenado para validarlas *después*, sin poder ajustar el resultado.
5. **Falsa seguridad** → mostramos dónde **no** vemos («sin señal») y qué datos son simulados.

**Quién NO debería usarlo (todavía):** nadie para acusar a un barco ni para una decisión operativa crítica: los umbrales son heurísticas **sin validar con incidentes reales** (sección 9).

---

## 4. Qué hace, en 6 pasos (lenguaje simple)

*Analogía: si sueltas una botella en un río, se mueve con la corriente y un poco con el viento. Si una «botella» se mueve distinto, algo la retiene o la empuja.*

1. **Dibujamos los cables.** Unos 700 cables reales y ~1 900 puntos de amarre (TeleGeography). Alrededor de cada uno, un **corredor de 2 km a cada lado**, cortado en tramos de ~50 km.
2. **Escuchamos a los barcos.** AIS en vivo (AISstream, estaciones en tierra), en 9 zonas configurables. Es información que los barcos emiten públicamente.
3. **Clasificamos cada barco dentro de un corredor:** en tránsito, lento (< 3 nudos), parado (< 0,5 nudos) o atracado (lo declara el propio barco). Un barco **lento o parado en el corredor** recibe un **nivel de atención**: ALTO, MEDIO o BAJO.
4. **La prueba de deriva pasiva.** Pedimos la corriente y el viento del punto (Open-Meteo). Calculamos cuánto se movería un casco **sin motor** (corriente + 2,5 % del viento) y lo comparamos con lo observado en las últimas 3 horas. Cuatro resultados: **deriva** (se mueve como el agua), **fijo** (el agua lo arrastraría y no se mueve: fondeado o amarrado), **propulsión** (se mueve distinto de lo que haría el agua) o **indeterminado** (está quieto y el agua casi no lo movería: no se puede decir).
5. **Bajamos el ruido con conocimiento del mundo real:** puertos y radas aprendidos del AIS, barcos amarrados cerca de un punto de amarre y barcos inmóviles durante horas (no arrastran ni derivan).
6. **Dejamos evidencia:** un **recibo** descargable por alerta (regla exacta, números, fuentes, límites y un hash), **sellos** horarios encadenados con las alertas reales, y un panel público de **lo medido**.

---

## 5. Lo que se ve en la pantalla

Se abre en `/` (sin iniciar sesión). De arriba abajo:

**Encabezado.** «VIGÍA» (el nombre), el lema, la hora UTC y cinco contadores (pasa el ratón por cada uno: la pantalla explica qué significa):
- **Buques:** cuántos hay en pantalla (reales; los simulados se avisan aparte).
- **En corredor:** cuántos están dentro de 2 km de algún cable.
- **Atención alta / Media:** cuántos tienen nivel ALTO y MEDIO.
- **Silencios:** barcos que estaban en un corredor y dejaron de emitir.

**Banner fucsia «TRÁFICO SIMULADO».** Aparece si hay buques simulados (nombres «SIM ·»). **Nada simulado va sin esta etiqueta.**

**El globo 3D.** Los cables brillan con pulsos de colores; los barcos son puntos (al acercarse, flechas con su rumbo). Un anillo **rojo** (ALTO), **ámbar** (MEDIO) o **celeste** (BAJO) rodea a los barcos con atención. Se puede girar, acercar y pulsar un barco o un cable.

**Columna izquierda.**
- **Atención:** lista ordenada. Cada fila: nombre, sobre qué cable, nivel · minutos así · velocidad · distancia al cable. Pulsar lleva la cámara hasta el barco y abre su tarjeta. «(+N bajas)» cuenta los de nivel BAJO.
- **Silencios en corredor:** barcos que desaparecieron dentro de un corredor. *Puede ser que salieran del alcance de los receptores: es un indicio, no una prueba.*
- **Recorridos largos (informativo):** barcos en marcha que llevan ≥ 15 km seguidos dentro de un corredor. **No es una alerta**: muchas rutas van paralelas a un cable.

**Columna derecha: «Zonas escuchadas».** Barras por zona con cuántos barcos vemos. **«Sin señal» en rojo = ahí no vemos nada** (hoy: Perú y Pacífico sur, Mar Rojo y Golfo de Adén, Golfo Pérsico y Ormuz): es falta de cobertura gratuita, no ausencia de barcos.

**La tarjeta de un barco.** MMSI (su identificador), estado, velocidad, rumbo, cable, distancia, y el nivel con los minutos. Según el caso muestra avisos: *inmóvil desde hace N h*, *zona de estacionamiento habitual*, *recorrido largo*. Y el panel **«Prueba de deriva pasiva»**:
- **Observado:** velocidad y rumbo reales (ajuste a su pista de 3 h).
- **Si fuera a la deriva:** lo que haría el agua con el viento.
- **Diferencia y tolerancia:** si la diferencia supera la tolerancia, el movimiento no lo explica el agua.
- **Corriente y viento** del punto, y cuántas posiciones tiene la pista.
- Un aviso **ámbar** si la corriente es *aproximada* (el modelo no tiene dato en ese punto y se tomó el agua más cercana).
- En el mapa: **puntos blancos** = su pista real; **línea blanca** = lo observado proyectado 3 h; **línea cian punteada** = lo que habría hecho el agua.
- **«Descargar recibo de esta alerta»:** archivo con la regla exacta, los números, las fuentes, los límites y un hash SHA-256.

**Pulsar un cable — «Investigar».** La tarjeta del cable dice con honestidad que **Vigía vigila lo que pasa encima del cable, no sabe si el cable funciona**. Con los botones **6 h / 24 h / 72 h** lista los barcos que estuvieron sobre ese cable en ese tiempo, primero los que más tiempo estuvieron casi quietos (minutos lento, minutos dentro, velocidad mínima, último aviso). Pulsar un barco lleva la cámara hasta él. «Descargar informe» guarda esa lista con un hash, igual que el recibo. **Es lo que serviría si un cable falla: saber quién estaba cerca antes.** No prueba culpa.

**Botones de abajo.**
- **Leyenda:** explica cada símbolo del mapa (cables, puntos blancos / ámbar / naranja / grises, flechas, anillos, puntos de amarre, zonas).
- **Cómo se calcula:** los umbrales y reglas con sus valores actuales, y el estado de los sellos.
- **Lo medido:** panel público con lo que hemos medido (consistencia con el AIS real y error del modelo de corrientes frente a boyas reales en seis regiones), con fecha y límites.
- **Replay 3 h:** un deslizador reproduce las últimas 3 horas de los barcos con atención. Hay una posición real cada ~10 minutos; entre ellas se interpola en línea recta.

**Código de colores:** ALTO = rojo · MEDIO = ámbar · BAJO = celeste · informativo = azul · SIMULADO = fucsia.

---

## 6. Reglas exactas (todo contestable)

| Regla | Valor | Qué significa |
|---|---|---|
| Parado / lento | < 0,5 kn / < 3 kn | Velocidad sobre el fondo |
| Corredor | 2 km a cada lado, tramos de ~50 km | Dónde se vigila |
| Atracado | el barco declara estado «amarrado» (AIS 5) | Sin alerta (ese estado lo teclea la tripulación y suele estar viejo) |
| Cerca de amarre | ≤ 3 km de un punto de amarre y parado | BAJO |
| Permanencia | ≥ 60 min lento o parado en el corredor | Sube a ALTO |
| Zona habitual | ≥ 5 barcos distintos detenidos en una celda de ~2 km en 24 h | Puerto o rada aprendido: BAJO (salvo «propulsión») |
| Inmóvil | ≥ 3 h sin salir de 250 m | El ALTO baja a MEDIO: no arrastra ni deriva |
| Recorrido largo | en marcha y ≥ 15 km seguidos en un corredor (posiciones separadas ≤ 25 min) | **Solo informativo**; se sella |
| Prueba de deriva | ≥ 3 posiciones y ≥ 30 min, ventana de 3 h; «quieto» < 0,3 kn | Ajuste de recta por mínimos cuadrados |
| Esperado sin motor | corriente + 2,5 % del viento | El viento arrastra al casco (*windage*) |
| Tolerancia | base **por región** (0,4 kn por defecto; 0,5 Perú; 0,7 Mar del Norte; 0,8 Mediterráneo; 1,0 Mar Rojo y Taiwán) + 1,5 % del viento (+ hasta 0,3 kn si la corriente es aproximada) | Medida contra boyas reales (sección 8) |

| Veredicto de la prueba | Efecto en el nivel |
|---|---|
| **deriva** | MEDIO (ALTO si ≥ 60 min) |
| **fijo** | BAJO (MEDIO si ≥ 60 min) |
| **propulsión** yendo lento | ALTO |
| **indeterminado** | regla simple: MEDIO (ALTO si ≥ 60 min) |

---

## 7. Qué es nuevo y qué no
- **Nuevo para este jurado:** el producto entero (distinto del sistema de rescate presentado antes). Reutiliza el motor de corrientes y viento y la disciplina de «regla contestable + recibo».
- **No es nuevo en el mundo:** vigilar cables con AIS ya lo venden [Windward](https://windward.ai/blog/subsea-cable-surveys-are-converging-on-the-same-behavioral-signature/) y [Gatehouse Maritime](https://gatehousemaritime.com/solutions/critical-offshore-and-subsea-infrastructure-protection/monitor-protect-subsea-cables-and-pipelines/), con satélite y radar. Las corrientes derivadas de AIS las vende eOdyn (proyecto [ADEOS](https://marine.copernicus.eu/about/research-development-projects/2022-2024/adeos) de Copernicus). **No competimos con ellos en cobertura de alta mar.**
- **Lo que sí aportamos y no encontramos publicado [búsqueda corta, sin verificar]:** una prueba automática y abierta que separa *deriva pasiva* de *propulsión o ancla arrastrada* usando corriente y viento del punto; un **recibo verificable** por alerta; **alertas selladas** para validar después; y la **medición del error del modelo de corrientes frente a boyas reales** para fijar la tolerancia con datos y no con suposiciones.

---

## 8. Evidencia medida (tráfico real, no promesas)
| Qué | Resultado | Cómo leerlo |
|---|---|---|
| Buques declarados «amarrado» que la prueba llama «deriva» | **3 de 493 (0,6 %)**; «propulsión»: 3 | No inventa deriva donde el buque está atracado |
| Buques con motor y en movimiento que reconoce como propulsión | **66 %** (152 de 232); «deriva» 9 % | Reconoce el movimiento propio (antes 77–86 % con tolerancia fija de 0,4 kn: al ampliarla en regiones donde el modelo falla, la prueba se abstiene más) |
| Declaraciones viejas detectadas | 89 buques «amarrados» que llegaron a ≥ 3 kn (uno, un ferry a 18 kn) | La prueba acierta y el estado declarado está mal |
| Cobertura de corriente en la validación | **75 %** (1 126 de 1 500), antes 60 % | Mejora por usar el agua más cercana en costa, **etiquetada como aproximada** |
| Zonas de estacionamiento aprendidas del AIS | alertas ALTO+MEDIO **−27 %** (152→111, medido antes de las demás reglas) | Reduce ruido |
| Buques inmóviles ≥ 3 h en 250 m (barcos amarrados en puerto) | ALTO **20 → 9** en una foto de tráfico real | Corrige una falsa alarma sistemática; no sabemos cuántos de los 9 son reales |
| Señal «recorrido largo» en el corredor | 11 de 12 062 buques en 8 h; 4–5 de ~810 en corredor en vivo | Selectiva; todos tráfico normal; **sin validar** con incidentes |
| Latencia de la API | **~0,1 s** con la tarea de precalentado; cálculo completo **4–6 s** con ~8 400 buques (antes 9–12 s) | La consulta de amarres pasó de 4,7 s a 0,02 s con resultado idéntico |

Validación: AIS real de Europa del norte y el Mediterráneo (8 h, 1 500 buques); mide **consistencia con lo declarado, no acierto** (el estado declarado lo teclea la tripulación). La mezcla de buques cambia entre corridas, así que las cifras de distintos días no son comparables punto a punto.

### 8.1 Corrientes contra boyas reales (medido 18-nov)
Comparamos las corrientes de reanálisis de Copernicus con boyas a la deriva de NOAA en seis regiones (72 boyas-región). **El modelo es bueno en el Báltico (95 % de los casos dentro de 0,4 kn) y en Perú (85 %), regular en el Mar del Norte (77 %) y malo en el Mediterráneo (56 %), Taiwán (53 %) y Mar Rojo (42 %).** En vez de suponer una tolerancia, fijamos una por región con el error medido (0,4 a 1,0 kn). Costo declarado: donde el modelo falla, la prueba casi no discrimina a un buque lento, y la pantalla lo dice. Pocas boyas por región; se valida el modelo de Copernicus, no el de Open-Meteo.

| Región | Boyas | Error mediano | Error p90 | Casos dentro de 0,4 kn | Tolerancia que usamos |
|---|---|---|---|---|---|
| Báltico (medias diarias) | 4 | 0,17 kn | 0,34 kn | **95 %** | 0,4 kn |
| Perú | 12 | 0,21 kn | 0,44 kn | **85 %** | 0,5 kn |
| Mar del Norte (horario, con mareas) | 7 | 0,22 kn | 0,66 kn | **77 %** | 0,7 kn |
| Mediterráneo | 12 | 0,36 kn | 0,73 kn | **56 %** | 0,8 kn |
| Taiwán | 6 | 0,38 kn | 0,93 kn | **53 %** | 1,0 kn |
| Mar Rojo y Golfo | 9 | 0,47 kn | 1,00 kn | **42 %** | 1,0 kn |

**¿Y un modelo mejor?** Probamos el reanálisis regional del Mediterráneo (4,2 km) con las mismas boyas: 62 % dentro de 0,4 kn frente a 56 % del global. Una mejora pequeña; la resolución no es el cuello de botella.

*Boyas con ancla flotante (~15 m) contra el modelo en superficie; en el Báltico y el resto, medias diarias; en el Mar del Norte, boya promediada 3 h contra el modelo en un instante. Fuente: boyas del Global Drifter Program (NOAA, CC BY 4.0) y reanálisis de Copernicus Marine. Datos en `backend/mares/apps/cables/validacion_datos/maury_valida.json`; se reproduce con `scripts/maury_valida.py --regiones todas`. Máximo 12 boyas por región y 40 días por boya: indicativo, no definitivo.*

## 9. Límites: lo que NO sabemos (lo decimos nosotros antes que el jurado)
- **No hay un incidente real de arrastre de ancla** con el que comparar. Los umbrales son heurísticas. Empezamos a acumular evidencia con las **alertas selladas**; **aún no hay resultados**, solo la cadena. *Siguiente paso:* reproducir *Yi Peng 3* / *Eagle S* con AIS histórico **[acceso y condiciones sin confirmar]**.
- **La prueba discrimina poco entre buques quietos:** ~70 % de los que están quietos sale «indeterminado», porque el agua casi no los movería (y en Mar Rojo o Taiwán casi ninguno se puede decidir, ver el cuadro). Su valor es **explicar**, no filtrar: en una medición previa cambió el nivel de solo 33 de 400 alertas.
- **AIS gratuito = Europa del norte.** En Mar Rojo, Golfo Pérsico y Perú vimos 0 buques. Para esas zonas hace falta AIS satelital o receptores propios.
- **Siguen decenas de alertas de atención entre miles de buques** y **no sabemos cuántas son falsas.** Ya encontramos y corregimos una clase sistemática (barcos amarrados en puerto); puede haber otras.
- **Las reglas de lento/parado no capturan un arrastre a velocidad de navegación** **[sin verificar: no tenemos datos de incidentes]**. Añadimos una señal *informativa* (recorrido largo en el corredor) y la sellamos para validarla después; **no sabemos si un arrastre real se vería así**.
- **Corriente cerca de la costa:** es de un modelo (~8 km). Donde falta usamos el agua más cercana (≤ ~33 km), lo etiquetamos y ensanchamos la tolerancia; es una aproximación.
- **Licencias:** cables de TeleGeography y corrientes de Open-Meteo (uso no comercial) **sin confirmar para uso comercial.**
- **Maury 2.0** (corrientes medidas con la propia flota) **no está construida**; con decenas de buques a la deriva sería circular. En su lugar medimos el modelo contra boyas reales (arriba). Fuera de las seis regiones medidas la tolerancia **no está medida**.

## 10. Preguntas duras del jurado
- **«¿Qué pasa si un cable se destruye por accidente o a propósito?»** Vigía **no lo detecta**: no sabe si un cable funciona, solo vigila lo que pasa encima. Lo que sí hace es dejar la memoria: con *Investigar* se ve qué barcos estuvieron sobre ese cable en las 6, 24 o 72 h anteriores y se descarga un informe sellado. Para detectar el corte en sí harían falta otras señales (caídas de tráfico de internet en los países conectados, avisos de los operadores); es una de nuestras propuestas, no algo construido. Nota: no todo corte se ve desde fuera, porque el tráfico se reencamina por otros cables ([Cloudflare](https://blog.cloudflare.com/q1-2024-internet-disruption-summary)).
- **«¿Y en zonas de guerra, como el Mar Rojo o el Golfo?»** Ahí **no vemos casi nada**: el AIS gratuito viene de receptores en tierra y no hay (zonas «sin señal»). Y aunque hubiera, **las posiciones pueden ser falsas**: en el Mar Rojo y el Golfo Pérsico se han reportado interferencias de GPS y AIS que desplazan a los barcos o los dibujan en círculos o sobre tierra, y algunos operadores apagan el AIS ([UKMTO, vía Freight News](https://www.freightnews.co.za/article/ukmto-warns-of-ais-jamming-in-red-sea-region), [Inside GNSS](https://insidegnss.com/gnss-interference-complicates-navigation-as-hormuz-shipping-disruption-deepens/); son medios del sector, no datos oficiales). Por eso Vigía muestra esas zonas como ciegas en vez de aparentar cobertura. Una vía para ver algo allí: la presencia de buques de Global Fishing Watch (satélite, una posición por barco y hora, con ~3–4 días de retraso, uso no comercial; [documentación](https://globalfishingwatch.org/our-apis/documentation)), que no sirve para alertas en vivo pero sí para investigar.
- **«¿El cable solo es mar?»** El mapa dibuja el trazado completo que publica TeleGeography, incluidos los tramos que llegan a tierra (los puntos celestes son los puntos de amarre). La vigilancia por barcos solo tiene sentido en el agua y cerca de la costa.
- **«¿Detecta sabotaje?»** No. Marca atención y explica si el movimiento es compatible con el agua. Distinguir un fondeo legítimo de un arrastre intencional no es posible con estas señales; ni la investigación sueca del *Yi Peng 3* pudo concluirlo.
- **«¿Cuántas falsas alarmas?»** En una foto de tráfico real: ~95 alertas ALTO+MEDIO (19 ALTO) entre ~8 400 barcos. Redujimos ruido con zonas habituales (−27 %) y con la regla de inmóvil (ALTO 20→9), pero la tasa de falsas **no está medida** porque no hay verdad de referencia.
- **«¿Por qué no lo hace Windward?»** Lo hacen, con más datos y de pago. Nuestro ángulo: abierto, explicable, con recibo verificable y barato. Si alguien lo pagaría **no lo sabemos**; no tenemos contactos ni precios públicos.
- **«¿Los datos son reales?»** Cables y AIS, sí. Corriente y viento son de un modelo. Todo lo simulado dice SIMULADO en pantalla y en el recibo.
- **«¿Es legítimo mostrar barcos?»** El AIS es una emisión pública de radio que los barcos hacen para ser vistos; no usamos datos privados. Aun así, un nivel de atención no es una acusación y la pantalla lo dice.
- **«¿Por qué AIS terrestre y no satélite?»** Porque es gratuito y abierto. El costo es la cobertura: en Mar Rojo, Golfo y Perú vimos 0 barcos. Los incidentes europeos conocidos ocurrieron en zonas que sí cubrimos.
- **«¿Cómo sé que no cambiaron los resultados después?»** Cada alerta puede descargarse como recibo con hash, y cada hora se sella la lista de alertas en una cadena de hashes. Ambos se verifican con scripts independientes (`scripts/verificar_recibo.py`, `scripts/verificar_sellos.py`). **Límite:** la cadena prueba el orden dentro de nuestra base; para fijar la fecha hay que publicar el último hash fuera.
- **«¿Qué fue del sistema de rescate (MARES)?»** El proyecto nació como un sistema de búsqueda y rescate para capitanías peruanas. Vigía es un producto distinto y **no incluye** esa parte: sin usuarios, sin capitanías, sin login. La API y la pantalla son públicas y de solo lectura.

---

## 11. Guion de 3 minutos y lista de demo

**Guion**
1. *(20 s)* El problema: un barco lento sobre un cable. ¿Inocente o arrastre? Un dato: 150–200 cables dañados al año, casi todos por anclas y pesca.
2. *(40 s)* Globo en vivo; zoom a una alerta real. Explicar los contadores y «sin señal».
3. *(60 s)* La prueba: pista, línea del agua, números, veredicto. Un caso simulado y rotulado que muestre deriva, fijo y propulsión.
4. *(20 s)* **Replay 3 h** de un barco con atención.
5. *(20 s)* El recibo y su verificación con el script; los sellos.
6. *(20 s)* **Lo medido** y lo que no sabemos (el cuadro de corrientes contra boyas).

**Antes de presentar (lista de comprobación)**
- Base de datos con PostGIS y cables cargados (`cargar_cables`); API y frontend arriba.
- Monitor AIS corriendo **≥ 40 minutos** antes (el replay, los recorridos y la prueba necesitan historial). Con la tarea `precalentar_buques` activa, la pantalla responde en ~0,1 s.
- Si no hay AIS real: `simular_ais` y decirlo en voz alta (se ve el banner SIMULADO).
- Tener abierto `/` y, aparte, el panel «Lo medido».
- Plan B si cae la red: las capturas y el recibo de ejemplo.

---

## 12. Cómo seguir investigando (Google o una IA)

**Dónde buscar lo esencial (fuentes que existen):** el **ICPC** (International Cable Protection Committee), **TeleGeography** (mapa y estadísticas de cables submarinos), informes de **Windward** y **Gatehouse Maritime** sobre cables, la **Organización Marítima Internacional (OMI/IMO)** para el AIS, **Global Fishing Watch**, el **Servicio Marino de Copernicus** (corrientes), el **Global Drifter Program de NOAA** (boyas) y **AISstream** (AIS gratuito).

**Frases para buscar en Google** (en inglés rinden más):
- `submarine cable faults causes anchoring fishing statistics ICPC`
- `Yi Peng 3 cable damage Baltic Sea investigation anchor drag`
- `Eagle S cable damage Finland anchor drag investigation`
- `AIS gap detection subsea cable anchor dragging`
- `ship leeway windage coefficient drift model` (cuánto empuja el viento a un casco)
- `AIS navigational status values moored at anchor not under command`
- `Global Drifter Program hourly drifter velocity data`
- `Copernicus Marine ocean currents reanalysis validation drifters`
- `how many submarine cables are there TeleGeography` (para comprobar la cifra de ~95 % del tráfico)

**Preguntas útiles para un asistente de IA** (copia y pega):
- *«Explícame con ejemplos cómo se corta un cable submarino por un ancla y por qué un barco a la deriva puede engancharlo.»*
- *«¿Qué diferencia hay, en datos AIS, entre un barco fondeado, a la deriva y arrastrando el ancla? ¿Qué señales los separan y cuáles no?»*
- *«Resume qué se sabe públicamente del caso Yi Peng 3 y del Eagle S, y qué sigue sin conocerse. Cita fuentes.»*
- *«Dame un listado de proveedores comerciales de monitoreo de cables submarinos y en qué se diferencian de un sistema abierto basado en AIS terrestre.»*
- *«¿Qué es el windage de un barco y qué porcentaje del viento suele usarse para estimar su deriva?»*
- *«Actúa como jurado escéptico y hazme las 10 preguntas más difíciles sobre un detector de arrastre de ancla basado en AIS gratuito.»*

**Cómo usar bien a una IA con este tema:** pídele **fuentes con enlace** y ábrelas; desconfía de cifras sin fuente (las IA pueden inventar datos o confundir casos); contrasta cualquier número con una fuente primaria antes de ponerlo en una diapositiva; y si algo no se puede verificar, escríbelo como lo hacemos aquí: **[sin verificar]**.

**Dentro del proyecto:** `docs/ESTADO_TECNICO.md` (estado técnico y mediciones), `docs/PLAN_GLOBAL_CABLES_Y_CORRIENTES.md` (el análisis del problema con fuentes), `docs/PROPUESTAS.md` (ideas y próximos pasos) y el [README](../README.md).

---

## 13. Glosario
- **AIS:** sistema por el que los barcos emiten por radio su identidad, posición, velocidad y rumbo.
- **MMSI:** número de 9 dígitos que identifica a un barco en el AIS.
- **SOG / COG:** velocidad y rumbo *sobre el fondo* (lo que el barco realmente avanza).
- **Nudo (kn):** una milla náutica por hora (≈ 1,85 km/h).
- **Corredor:** franja de 2 km a cada lado de un cable que se vigila.
- **Deriva pasiva:** movimiento de un casco sin propulsión, empujado por la corriente y el viento.
- **Windage:** empuje del viento sobre la parte del casco fuera del agua.
- **Fondeado / amarrado:** sujeto al fondo por el ancla / atracado a un muelle.
- **Posicionamiento dinámico:** barcos que se sostienen en un punto con sus máquinas, sin ancla.
- **Reanálisis:** modelo del océano ajustado a observaciones, para años pasados.
- **Boya a la deriva (drifter):** boya con GPS que se mueve con la corriente; mide la corriente real.
- **p90:** el error que supera solo el 10 % de los casos.
- **Hash (SHA-256):** huella digital de un archivo; si cambia una letra, cambia el hash.
- **SIMULADO:** dato inventado para demostrar; siempre rotulado.

---

## 14. Qué pedimos / siguiente paso
Validar con un incidente real (AIS histórico de *Yi Peng 3* o *Eagle S*), ampliar la cobertura con AIS satelital o receptores propios, y confirmar licencias. **Ninguna cifra de ingresos ni de victoria.**

---

## Registro de cambios (actualizar en cada mejora)
| Fecha | Cambio | Efecto medido |
|---|---|---|
| 18-nov-2026 | Prueba de deriva pasiva, zonas habituales, simulador, validación | ver tabla de evidencia |
| 18-nov-2026 | **Corriente del agua más cercana en costa**, etiquetada «aproximada» + tolerancia mayor | Cobertura 60 % → 77 % en validación; 0 de 168 buques sin dato en vivo; amarrados→«deriva» sigue ≈ 0 % |
| 18-nov-2026 | **Fallo de la API ya no se recuerda como «sin dato»** (reintento a 60 s); celdas de tierra se consultan una vez al día | Se descubrió al exceder el límite de llamadas de Open-Meteo (429): la validación salió falsa y se descartó |
| 18-nov-2026 | **Recibo descargable por alerta** + verificador independiente | Hash del navegador = hash recalculado en Python (comprobado); recibo alterado detectado |
| 18-nov-2026 | **Tarea de precalentado** cada 15 s con cerrojo anti-apilamiento | Petición ~0,1 s; la tarea tarda ~7 s con 3 300 buques |
| 18-nov-2026 | Suite completa del backend tras estos cambios | 346 pruebas OK (409 antes de las podas; las 63 quitadas eran de funciones eliminadas). (el botón de recibo y el aviso de corriente aproximada se verificaron después en pantalla) |
| 18-nov-2026 | **Alertas selladas** (cadena de hashes horaria, API pública, verificador independiente, aparece en «Cómo se calcula») | Cadena verificada de punta a punta con la base de la demo (2 sellos; alteración detectada). **Sin resultados de validación todavía**; límite: la cadena solo prueba el orden en nuestra base, hay que publicar el último hash fuera |
| 18-nov-2026 | **Maury-valida:** corrientes de Copernicus vs 24 boyas-región de NOAA; panel público «Lo medido» (`/cables/validacion/`) | Báltico 95 % dentro de 0,4 kn; Mar del Norte 69–73 % → tolerancia regional 0,7 kn. Costo: amarrados «indeterminado» 87 %→96 %, motor «deriva» ~3 %→~6 % |
| 18-nov-2026 | **Revisión con tráfico real:** los primeros ALTO eran barcos amarrados en puerto. Regla «inmóvil ≥ 3 h en 250 m → máximo MEDIO» | ALTO 20→9 en una foto real; con prueba de pruebas (mutación detectada). **Sin saber cuántos de los 9 son reales** |
| 18-nov-2026 | Panel «Lo medido» verificado en pantalla (maquetación corregida); botón de recibo visto en la tarjeta | Verificado en el navegador; la descarga del archivo no se probó, el hash sí (cruce con Python) |
| 18-nov-2026 | Tareas periódicas heredadas pausadas; arreglo del `cierre` de sysmap | Sin cambios en pruebas del producto; `sysmap check` sin hallazgos nuevos |
| 18-nov-2026 | **Maury-valida a seis regiones** (72 boyas-región): Báltico 95 %, Perú 85 %, Mar del Norte 77 %, Mediterráneo 56 %, Taiwán 53 %, Mar Rojo 42 % dentro de 0,4 kn → tolerancia por región (0,4–1,0 kn) | Amarrados «deriva» 0,6 % (3 de 493); con motor «propulsión» 77 %→66 % (composición de buques distinta, no comparable punto a punto). En Mar Rojo/Taiwán la prueba casi no discrimina: se dice en pantalla |
| 18-nov-2026 | **Señal informativa «recorrido largo»** (en marcha ≥ 15 km seguidos en un corredor, huecos ≤ 25 min), lista en pantalla y sellada | En 8 h de AIS real: 11 de 12 062 buques ≥ 15 km; en vivo 4–5 de ~810 en corredor, todos tráfico normal (ferrys, rutas paralelas a cables). **Sin validar:** no hay incidentes. Una medición inicial salió inflada (unía posiciones separadas por horas) y se corrigió con prueba |
| 18-nov-2026 | **Rendimiento:** `cerca_de_amarre` usaba mal el índice espacial | 4,7 s → 0,02 s con resultado idéntico verificado (245 de 394); cálculo total 9–12 s → 4–6 s |
| 18-nov-2026 | Revisión de interfaz en navegador: la lista de alertas quedó comprimida al añadir secciones; corregido (altura mínima, notas a tooltip) | Verificado en pantalla |
| 18-nov-2026 | **Replay de 3 h** con deslizador (`/api/v1/cables/replay/`) | Verificado en pantalla; interpolación comprobada sin navegador (encontró un punto repetido en el rastro). Posiciones reales cada ~10 min; entre ellas es línea recta |
| 18-nov-2026 | **Modelo regional del Mediterráneo (4,2 km) vs global** con las mismas 12 boyas | Mediana 0,33 vs 0,36 kn; dentro de 0,4 kn 62 % vs 56 %. Mejora pequeña: no se integró; corrige mi propuesta anterior de «mejores corrientes regionales» |
| 18-nov-2026 | **Poda del backend heredado** (vigilancia, métricas, NAVTEX): 6 endpoints, 2 apps, 50 pruebas de funciones ya retiradas | 359 pruebas OK; el mapa SAR probado en navegador con sesión; sysmap 78→65 hallazgos. Producto más pequeño y honesto: no declara funciones que ya no existen |
| 18-nov-2026 | **Seguridad:** `backend/.env` estaba versionado y `.env.example` traía valores reales; ahora `.gitignore` los excluye y el ejemplo lleva marcadores | Obliga a **rotar** las claves que estuvieron en el repositorio (ver `DEPLOYMENT.md`) |
| 18-nov-2026 | **Auditoría de coherencia:** se retiraron `/deteccion` (texto desactualizado que prometía funciones ya eliminadas), `/boyas` y `/rutas-3d` (sin enlace de entrada); título de pestaña, login, API y README alineados con el tema | Rutas finales: `/`, `/login`, `/mapa`, `/incidentes/…`, `/i/…`. 346 pruebas OK. Mapa SAR y menú revisados en el navegador |
| 18-nov-2026 | **Pitch y README reescritos:** el problema desde cero con fuentes, a quién le duele y qué se resuelve, qué hace en 6 pasos, la pantalla elemento por elemento, reglas exactas, preguntas duras, guion y lista de demo, **cómo investigar más con Google o una IA** (frases de búsqueda, preguntas para asistentes, cómo verificar) y glosario | Solo documentación; las cifras reutilizan las ya medidas. El README ahora describe Vigía (antes describía el sistema SAR) |
| 18-nov-2026 | **Vigía queda como proyecto independiente:** se elimina por completo el módulo de rescate (usuarios, capitanías, incidentes, simulación, mapa SAR, login), se cambia el nombre a **Vigía**, se añaden ayudas emergentes a cada término de la pantalla, se vacía el repositorio de lo que no es de este producto y se mueven los documentos de rescate a un archivo fuera del repositorio | Backend: 3 apps (`cables`, `detection`, `core`); dependencias de 64 a 13; web: una sola ruta (`/`); API sin autenticación. 92 pruebas OK en un entorno creado solo con `requirements.txt`; web y API compilan; sysmap 59→24 hallazgos |
| 18-nov-2026 | **Investigar un cable** (`/api/v1/cables/<slug>/historial/`): qué barcos estuvieron sobre él en 6/24/72 h + informe descargable con hash | 4 pruebas nuevas (con mutación); 10–70 ms con datos reales (p. ej. IOEMA-1: 258 barcos en 24 h). Responde a «¿y si un cable falla?» sin pretender detectar el corte |
| 18-nov-2026 | **Defectos de pantalla corregidos:** (1) cables que no volvían a pedirse si la primera petición fallaba (el error lo borraba la siguiente consulta de barcos); (2) **las flechas de los barcos no se dibujaban nunca** en zoom cercano (la proyección de globo no soporta ese tipo de rotación; medido: 0 de 3 811); (3) puntos de barcos de 2 px; (4) nueva **Leyenda** | Verificado en el navegador; el aviso «vista 3D interrumpida» se probó y se descubrió un falso positivo propio (MapLibre pierde el contexto a propósito al destruir un mapa) |
