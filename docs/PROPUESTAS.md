# Propuestas para el Vigía (18-nov-2026)

*Nada de esto está construido. Cada propuesta dice qué compra, cuánto cuesta y qué podría salir mal. Lo no verificado lleva **[sin verificar]**.*

## Fuentes abiertas encontradas hoy (búsqueda breve; confirmar condiciones antes de usarlas)
- **Drifters del Global Drifter Program (NOAA):** corrientes medidas por boyas a la deriva, horarias, en un bucket abierto de AWS sin cuenta, licencia CC BY 4.0. La serie horaria aparece hasta ~mediados de 2020 **[confirmar rango actual]**. Es el único dato independiente de corriente que tenemos a mano.
- **Digitraffic (Finlandia):** AIS del Báltico/Finlandia, CC BY 4.0, sin clave según terceros **[endpoints sin confirmar en la fuente oficial]**.
- **Kystverket (Noruega):** posiciones AIS de la zona de 12 millas como descarga abierta en CSV; no encontré API en tiempo real **[sin verificar]**.
- **AIS histórico de la DMA (Dinamarca):** se pide por formulario con base en la ley de reutilización de información pública; la DMA puede cobrar **[condiciones y precio sin confirmar]**.

## A. Resolver lo pendiente
| # | Pendiente | Propuesta | Costo | Riesgo |
|---|---|---|---|---|
| 1 | **HECHA (18-nov)** — Sin incidente real para validar | **Alertas selladas:** cada día se guarda la lista de alertas ALTO/MEDIO con hora, datos y un hash encadenado (cada sello incluye el hash del anterior) y se publica. Luego se comparan con fallos de cable reportados públicamente. Es validación *prospectiva*: no se puede ajustar después del resultado. En paralelo, pedir a la DMA el AIS de nov-2024 (*Yi Peng 3*). | ~1 día | Tarda semanas en acumular; puede que no ocurra ningún incidente y el resultado sea «sin eventos» (también se publica) |
| 2 | **HECHA (18-nov)** — Maury 2.0 era circular | Reformularla como **«Maury-valida»: medir cuánto se equivoca el modelo de corrientes contra drifters reales** en Mar del Norte y Báltico, y de ahí fijar con datos la tolerancia (hoy 0,4 kn por suposición) y el arrastre del viento (hoy 2,5 % por suposición). | 2–3 días | Los drifters y nuestro AIS no coinciden en el tiempo: se valida el *modelo*, no la flota. Necesita corrientes históricas (Copernicus, con cuenta gratuita) |
| 3 | AIS gratis solo cubre Europa del norte | No hay arreglo gratis para Mar Rojo/Golfo/Perú. **Reencuadrar:** *Yi Peng 3*, *Eagle S* y otros casos europeos ocurrieron en zona que SÍ vemos. Añadir Digitraffic y Kystverket como segunda fuente con licencia clara y para redundancia. | 1–2 días | No amplía regiones nuevas |
| 4 | Backend heredado | Podar GAP/NAVTEX/métricas/vigilancia con `sysmap cascada` antes de cada archivo. Quita además un ciclo de importaciones (`ais_gaps` ↔ `tasks`) que sysmap reporta. | 1 día | Tocar `MARESMap.tsx` (870 líneas) sin poder probar la sesión SAR |
| 5 | Licencias | Confirmar por escrito TeleGeography y Open-Meteo; plan B: Copernicus Marine para corrientes (licencia abierta, requiere cuenta). | el usuario | Ninguno técnico |
| 6 | `sysmap cierre` se cae | Reportarlo/arreglarlo en el repo de sysmap (busca `backend/openapi.json` en una copia de git donde el archivo no existe). | horas | — |

## B. Ideas para elevar el proyecto
1. **Replay de 3 horas con deslizador:** arrastrar el tiempo y ver cómo el buque llega, frena y se queda sobre el cable; las líneas observado/agua se dibujan en vivo. Es lo más visual para el jurado y usa datos que ya guardamos. ~2 días.
2. **Cuarta hipótesis, «retenido»:** además de deriva/fijo/propulsión, un buque con ancla arrastrando se mueve *en la dirección del agua pero a una fracción de su velocidad*. Es física razonable, pero **no hay datos reales para calibrarla**: sería una hipótesis marcada, no un resultado.
3. **Marcador público de la prueba:** una página con las cifras medidas (consistencia, cobertura, ruido), regenerada por el comando de validación, con fecha. Convierte «lo medimos» en algo auditable.
4. **Alertas con retiro automático:** una alerta se retira sola si su regla deja de cumplirse (principio del recibo de ALMA) y queda registrada en la cadena sellada.

## Orden que recomiendo
1 (alertas selladas, porque empieza a acumular tiempo desde hoy) → 2 (Maury-valida) → B1 (replay) → A4 (poda) → 3.

## Estado al cierre del 18-nov
- Hechas: alertas selladas, Maury-valida (tolerancia regional), marcador «Lo medido», recibo, precalentado, corriente en costa, regla de inmóvil, tareas heredadas pausadas, arreglo del cierre de sysmap.
- **Hecha:** poda del backend heredado (ver `ESTADO_TECNICO.md`).
- **Necesitan decisión tuya:** (a) publicar el último hash de los sellos en un commit; (b) **rotar las claves** que estuvieron en `backend/.env` (estaba versionado); (c) commit del arreglo en `~/Documentos/sysmap`; (d) si quieres, borrar a mano las tablas huérfanas `surveillance_*` y `reports_*` de tus bases (no lo hice).
- **Hechas después:** tolerancia medida en seis regiones; señal informativa de «recorrido largo» (sellada); corrección de rendimiento del cruce con amarres.
- **Hecha:** replay de 3 h con deslizador.
- **Propuestas nuevas sin construir:** **mejores corrientes donde el modelo falla** (Mar Rojo, Taiwán, Mediterráneo). *Probado en el Mediterráneo: el modelo regional de 4,2 km mejora poco (62 % frente a 56 % dentro de 0,4 kn), así que más resolución no basta*; queda por separar la causa (¿remolinos?, ¿arrastre del viento sobre la boya?, ¿profundidad?) o recurrir a radar HF. Hoy la prueba casi no discrimina allí; **validar el «recorrido largo» con un incidente real** (*Yi Peng 3* / *Eagle S*) cuando haya AIS histórico.

## Propuestas nuevas (19-nov)
*Las fuentes externas son de prensa del sector o documentación de terceros; verificar antes de comprometerse.*
1. **Ver algo en zonas ciegas (Mar Rojo, Golfo, Ormuz).** Capa de *presencia de buques* de Global Fishing Watch (API 4Wings: satélite, una posición por barco y hora, retraso ~72–96 h, CC BY-NC, clave gratuita; [docs](https://globalfishingwatch.org/our-apis/documentation)). No sirve para alertas en vivo, sí para investigar. Ya hay `GFW_API_KEY` en tu `.env`. **[Límites de uso sin confirmar.]**
2. **Marcar posiciones dudosas (interferencia de GPS/AIS).** En esas zonas hay reportes de posiciones falsas ([Inside GNSS](https://insidegnss.com/gnss-interference-complicates-navigation-as-hormuz-shipping-disruption-deepens/)). Se puede detectar en nuestros propios datos: saltos de posición imposibles para la velocidad, barcos «en tierra», posiciones en círculos. Un aviso «posible interferencia» evitaría falsas alertas y enseñaría un hallazgo propio.
3. **Detectar el corte, no solo el entorno.** Cruzar la investigación de un cable con señales externas de caídas de internet (Cloudflare Radar publica un Outage Center y resúmenes trimestrales de cortes de cables; [ejemplo](https://blog.cloudflare.com/q1-2024-internet-disruption-summary)). **[Acceso por API sin verificar.]** Con eso Vigía podría decir «este cable parece haberse cortado; estos barcos estuvieron cerca».
4. **Informe de incidente de un clic.** Ya existe la lista y el informe sellado; falta añadir los cables vecinos, el estado de la corriente y el viento en el punto, y las alertas selladas de esa hora.
5. **Tramos terrestres.** Marcar en el mapa qué parte del cable es marítima y cuál terrestre (hoy se dibuja el trazado completo).
6. **Alertas por correo o webhook** a quien vigila un cable concreto (suscripción por cable). Sin cuentas de usuario sería por enlace firmado; decisión de producto.

## Probar si alguien pagaría (2–3 semanas, solo internet)
*No hay evidencia de demanda; esto es un plan para obtenerla. Los umbrales son mi juicio y se pueden ajustar.*
1. **Dejar la demo abierta y medible** (semana 1): publicar Vigía en una dirección pública y añadir un botón «Quiero alertas de un cable» con un correo de contacto. Medir visitas, cables que se investigan y correos.
2. **Escribir a quien vigila cables** (semana 1–2): 30 mensajes cortos a operadores y consorcios pequeños o regionales, autoridades marítimas, aseguradoras marítimas y centros de operaciones de red. Una sola pregunta: *«Cuando un barco queda parado sobre uno de sus cables, ¿cómo lo sabe hoy y qué le costaría no saberlo?»*. Guardar las respuestas literales.
3. **Ofrecer un piloto gratis** (semana 2–3): vigilar UN cable que elija el interesado durante 30 días y entregar un informe sellado. Es la prueba más honesta de interés.
4. **Mirar a los competidores** (continuo): precios, clientes y casos publicados de Windward y Gatehouse; qué hueco dejan.

**Decisión:** seguir si ≥ 5 respuestas dicen que hoy lo hacen a mano o sin datos **y** ≥ 2 aceptan un piloto; ajustar el enfoque si responden pero no ven el dolor; descartar el ángulo comercial si < 3 responden tras 30 mensajes bien escritos. Aunque sea «descartar», Vigía conserva su valor como demostración y como método (ver el pitch).
