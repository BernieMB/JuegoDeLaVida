# Informe: Coste de usar modelos de visión grandes para testing automático de aplicaciones (capturas 4K)

**Fecha del informe:** 11 de agosto de 2026
**Motivo:** Evaluar el impacto económico de que agentes basados en modelos "frontier" costosos (Claude Opus 5, Claude Sonnet 5, GPT-5.6 Sol) tomen capturas de pantalla de un monitor 4K para verificar visualmente el comportamiento de una aplicación durante pruebas automatizadas/agénticas.
**Caso de referencia:** aplicación Python + SDL (por ejemplo, un juego o herramienta gráfica en tiempo real con `pygame`/`PySDL2`).

> Todos los precios y fórmulas de tokenización se han verificado contra la documentación oficial vigente en la fecha de este informe (Anthropic `docs.claude.com`, OpenAI `developers.openai.com` / `openai.com/api/pricing`). Los proveedores pueden cambiar precios y comportamientos sin previo aviso — revisar antes de presupuestar a largo plazo.

---

## 1. Resumen ejecutivo

- Una única captura 4K (3840×2160 px) **no** es gratis ni trivial en tokens: cuesta entre **~1.560 y ~8.160 "tokens de imagen"** dependiendo del modelo, solo para que el modelo la "vea".
- El modelo más caro de los tres analizados (**GPT-5.6 Sol**) es, además, el que **por defecto** ("detail": "auto"/"original") procesa la imagen a **resolución completa sin límite de tokens**, lo cual puede disparar el coste **3-4 veces** por encima de lo necesario si no se configura explícitamente.
- En un escenario realista de regresión automática de una app Python+SDL (40 casos de prueba, 15 capturas por caso, 3 ejecuciones/día), el coste mensual **solo por la parte de visión** puede oscilar entre:
  - **~28 $/mes** con un modelo barato bien configurado (GPT-5.6 Luna), y
  - **~1.700-3.100 $/mes** con los modelos "frontier" (Opus 5 / GPT-5.6 Sol) sin optimizar.
- El mayor riesgo oculto no es el precio por imagen, sino la **acumulación de contexto en conversaciones multi-turno**: si el agente mantiene todas las capturas anteriores en el mismo hilo de conversación, el coste crece de forma **cuadrática**, no lineal (hasta 8× más en una secuencia de 15 pasos).
- Recomendación central: **no** enviar capturas 4K completas del escritorio. Reducir resolución, recortar a la ventana de la app, fijar explícitamente el nivel de detalle, y reservar el modelo caro solo para los pasos que realmente lo necesiten.

---

## 2. El problema

Cuando un agente de codificación (Claude Code, Codex/GPT, u OpenCode con estos modelos) prueba una aplicación gráfica, una técnica común es:

1. Ejecutar una acción (clic, tecla, movimiento).
2. Tomar una captura de pantalla completa.
3. Enviar esa captura al modelo para que "vea" el resultado y decida si el test pasa o falla, o cuál es el siguiente paso.

En un monitor **4K (3840×2160 px)**, cada una de esas capturas es una imagen considerablemente más grande que las resoluciones típicas de entrenamiento/documentación (1024-2048 px). Los modelos de visión no procesan "píxeles" directamente: los trocean en **parches** y cada parche se convierte en uno o más tokens. Cuantos más parches, más tokens de entrada — y los tokens de entrada (y sobre todo de salida) son lo que se factura.

Para un flujo de testing agéntico que repite este ciclo decenas o cientos de veces por sesión, el coste de "solo mirar la pantalla" puede convertirse en la partida dominante del presupuesto de la sesión.

---

## 3. Cómo tokenizan las imágenes los modelos de visión

### 3.1 Claude (Anthropic) — Opus 5 / Sonnet 5 / Haiku 4.5

Claude ve las imágenes como una cuadrícula de parches de **28×28 píxeles**. El coste en tokens es:

```
tokens_imagen = ceil(ancho / 28) × ceil(alto / 28)
```

Cada modelo tiene un límite de resolución nativa según su "tier":

| Tier | Modelos | Lado largo máx. | Tokens visuales máx. |
|---|---|---|---|
| Alta resolución | Claude 4.7 y posteriores (incluye **Opus 5** y **Sonnet 5**) | 2576 px | 4.784 |
| Estándar | Resto de modelos (incluye **Haiku 4.5**) | 1568 px | 1.568 |

Si la imagen excede el límite, Claude la reescala manteniendo la proporción **antes** de tokenizar, lo cual limita el coste máximo por imagen, pase lo que pase con la resolución original.

**Para una captura 4K (3840×2160 px):**

| Tier | Reescalado a | Tokens |
|---|---|---|
| Alta resolución (Opus 5 / Sonnet 5) | 2576×1449 px | **4.784** |
| Estándar (Haiku 4.5) | 1456×819 px | **1.560** |

Es decir: **una imagen 4K completa nunca cuesta más de 4.784 tokens en Claude**, sin importar si el monitor es 4K, 8K o más — el tope está fijado por el modelo, no por la resolución de origen. Esto es una protección natural contra el problema que motivó este informe.

### 3.2 GPT-5.6 (OpenAI) — Sol / Terra / Luna

La familia GPT-5.6 tokeniza imágenes con parches de **32×32 píxeles**:

```
patches_originales = ceil(ancho / 32) × ceil(alto / 32)
```

El comportamiento crítico y **diferente a Claude** está en el parámetro `detail`:

| `detail` | Comportamiento en GPT-5.6 |
|---|---|
| `low` | Resolución baja fija (512×512), coste mínimo constante |
| `high` | Se reescala para caber en un presupuesto de parches finito (barato, controlado) |
| `original` | **Preserva la resolución de entrada. No hay límite de parches ni de píxeles.** |
| `auto` (u omitido) | **En GPT-5.6, `auto` equivale a `original`** — es decir, es el comportamiento sin límite. |

> Este es el hallazgo más importante del informe: **en GPT-5.6, si no se especifica `detail` explícitamente (o se deja en `auto`), el sistema usa `original`, que procesa la imagen a su resolución completa sin ningún techo de tokens.** En generaciones anteriores (GPT-4o, GPT-4.1, gpt-5.4/5.5) `auto` se comportaba como `high` (acotado). Este cambio de comportamiento por defecto es fácil de pasar por alto y puede multiplicar el coste sin que el equipo lo note hasta ver la factura.

**Para una captura 4K (3840×2160 px) en GPT-5.6 Sol:**

| `detail` | Parches resultantes | Nota |
|---|---|---|
| `original` / `auto` (por defecto) | **8.160** | Sin reescalado — imagen a resolución completa |
| `high` (estimado por analogía con el presupuesto de `gpt-5.5`, ~2.500 parches)* | **~2.442** | Reescalada a ~2105×1184 px |

\* *OpenAI no publica un número exacto de presupuesto de parches para el nivel `high` de GPT-5.6 en la documentación consultada (sí lo hace para 5.4/5.5: 2.500 parches). Se usa ese valor como estimación razonable por continuidad de familia; conviene verificarlo empíricamente contra la API antes de presupuestar con precisión.*

Esto significa que, a resolución 4K, **GPT-5.6 Sol en su modo por defecto usa ~1,7× más tokens que Claude Opus 5** para "ver" la misma imagen (8.160 vs 4.784), y unas **5,2× más** que el propio GPT-5.6 Sol configurado correctamente con `detail: high` (8.160 vs ~2.442).

---

## 4. Precios vigentes de los modelos (input corto contexto / output), por millón de tokens

| Modelo | Input | Output | Input en caché (lectura) |
|---|---|---|---|
| **Claude Opus 5** | $5.00 | $25.00 | $0.50 (10%) |
| **Claude Sonnet 5** | $2.00 | $10.00 | $0.20 (10%) |
| Claude Haiku 4.5 (referencia barata) | $1.00 | $5.00 | $0.10 (10%) |
| **GPT-5.6 Sol** | $5.00 | $30.00 | $0.50 (10%) |
| GPT-5.6 Luna (referencia barata) | $0.20 | $1.20 | $0.02 (10%) |

Fuente: `claude.com/pricing` y `platform.openai.com/docs/pricing`, consultados el 11/08/2026.

---

## 5. Coste de una única captura 4K

Combinando la fórmula de tokenización con el precio de cada modelo, el coste de que el modelo **reciba y "vea"** una sola captura 4K (sin contar aún la respuesta de texto que genera) es:

| Modelo | Tokens de imagen | Coste por captura | Coste por 1.000 capturas |
|---|---:|---:|---:|
| Claude Opus 5 | 4.784 | $0.0239 | **$23.92** |
| Claude Sonnet 5 | 4.784 | $0.0096 | **$9.57** |
| Claude Haiku 4.5 | 1.560 | $0.0016 | **$1.56** |
| GPT-5.6 Sol (`auto`/`original`, por defecto) | 8.160 | $0.0408 | **$40.80** |
| GPT-5.6 Sol (`detail: high`, estimado) | ~2.442 | $0.0122 | **$12.21** |
| GPT-5.6 Luna (`detail: high`, estimado) | ~2.442 | $0.0005 | **$0.49** |

Si además se contabiliza la respuesta del modelo (el texto que describe lo que ve o el veredicto del test), el coste sube. Aquí es importante un matiz: los modelos de razonamiento (Opus 5, GPT-5.6 Sol en modo agéntico) suelen generar tokens de "pensamiento" internos que se facturan como *output* aunque el usuario no los vea directamente. Se presentan dos escenarios:

- **Escenario A — respuesta concisa** (~250 tokens de salida: veredicto + breve justificación)
- **Escenario B — con razonamiento extendido** (~1.500 tokens de salida: típico si el modelo "piensa" antes de responder en un flujo agéntico)

| Modelo | Coste/captura (Escenario A) | Coste/captura (Escenario B) |
|---|---:|---:|
| Claude Opus 5 | $0.0302 | $0.0614 |
| Claude Sonnet 5 | $0.0121 | $0.0246 |
| Claude Haiku 4.5 | $0.0028 | $0.0091 |
| GPT-5.6 Sol (`auto`, por defecto) | $0.0483 | $0.0858 |
| GPT-5.6 Sol (`detail: high`) | $0.0197 | $0.0572 |
| GPT-5.6 Luna (`detail: high`) | $0.0008 | $0.0023 |

---

## 6. Escenario de prueba: aplicación Python + SDL

### 6.1 Supuestos del escenario

Para dar cifras concretas y accionables, se define un escenario de referencia razonable para una aplicación "importante" (por ejemplo, un juego o herramienta gráfica en tiempo real hecha con `pygame`/`PySDL2`) bajo un proceso de QA agéntico:

| Parámetro | Valor asumido |
|---|---|
| Casos de prueba en la suite de regresión | 40 |
| Capturas necesarias por caso (navegar menús, ejecutar acciones, verificar estado) | 15 |
| Capturas por regresión completa | **600** |
| Ejecuciones de la suite por día (CI + validaciones manuales) | 3 |
| Días laborables por mes | 20 |
| Capturas totales por mes | **36.000** |

*(Estos números son ajustables — el informe da el coste por captura para que cualquier equipo recalcule con sus propios volúmenes.)*

### 6.2 Proyección de costes (solo la parte de visión del agente)

| Modelo | Por regresión (600 capturas) A/B | Por día (1.800) A/B | Por mes (36.000) A/B |
|---|---:|---:|---:|
| Claude Opus 5 | $18.10 / $36.85 | $54.31 / $110.56 | **$1.086 / $2.211** |
| Claude Sonnet 5 | $7.24 / $14.74 | $21.72 / $44.22 | **$434 / $884** |
| Claude Haiku 4.5 | $1.69 / $5.44 | $5.06 / $16.31 | **$101 / $326** |
| GPT-5.6 Sol (`auto`, por defecto) | $28.98 / $51.48 | $86.94 / $154.44 | **$1.739 / $3.089** |
| GPT-5.6 Sol (`detail: high`) | $11.83 / $34.33 | $35.48 / $102.98 | **$710 / $2.060** |
| GPT-5.6 Luna (`detail: high`) | $0.47 / $1.37 | $1.42 / $4.12 | **$28 / $82** |

**Lecturas clave de la tabla:**

- Usar **GPT-5.6 Sol sin configurar `detail`** (su comportamiento por defecto) cuesta **~2,4× más al mes** que usarlo correctamente configurado con `detail: high` ($1.739-3.089 vs $710-2.060).
- La diferencia entre el modelo más caro bien usado (Opus 5) y un modelo barato bien elegido (GPT-5.6 Luna) es de **~26-38×**.
- Estas cifras son **solo la parte de "visión"** del agente. El coste real de un agente de testing incluye además el razonamiento textual para decidir la siguiente acción, herramientas, historial de conversación, etc. — esta es una cota inferior del gasto total, no el gasto total.

---

## 7. El riesgo oculto: acumulación de contexto en conversaciones multi-turno

Los cálculos anteriores asumen que cada captura se factura **una sola vez**. En la práctica, si el agente mantiene **una sola conversación continua** durante todo un caso de prueba (15 pasos, 15 capturas) y no gestiona el contexto, **cada nueva petición reenvía el historial completo**, incluyendo todas las imágenes anteriores.

Esto convierte el coste de lineal a **cuadrático**:

```
tokens_imagen_totales = tokens_por_imagen × (1 + 2 + 3 + ... + n) = tokens_por_imagen × n(n+1)/2
```

Para `n = 15` pasos en un mismo hilo:

- Coste ingenuo esperado: 15 capturas → **15 unidades**.
- Coste real sin gestión de contexto: **120 unidades** (factor **8×**).

### Mitigación: caché de prompts

Tanto Anthropic como OpenAI ofrecen **caché de prompts**: si el prefijo de la conversación (incluidas imágenes previas) no cambia, las relecturas se facturan a **~10% del precio de entrada normal** en vez de precio completo, siempre que:

- El proveedor soporte cachear bloques de imagen (Claude lo permite).
- No pase más tiempo que el TTL de la caché (5 min por defecto, hasta 1 hora en modo extendido).
- El prefijo sea exactamente igual (cualquier cambio antes del punto cacheado invalida la caché desde ahí).

Con caché activa, el mismo caso de 15 pasos pasa de **120 unidades** a aproximadamente **25,5 unidades equivalentes** (15 imágenes nuevas + 105 relecturas al 10%) — un sobrecoste de solo **1,7×** en vez de 8×, pero **todavía por encima del ideal de 1×**.

**Conclusión práctica:** si el agente de testing usa un único hilo largo por sesión de pruebas en vez de resetear el contexto entre casos, el coste real puede ser entre **1,7× y 8×** superior a las cifras de la sección 6, dependiendo de si hay caché activa y de si su TTL sobrevive entre pasos.

---

## 8. Recomendaciones para reducir el coste

En orden de impacto:

1. **No capturar el escritorio 4K completo.** Capturar únicamente la ventana/región de la aplicación bajo prueba (con `pygame.Surface` recortado, `pyautogui.screenshot(region=...)`, o el handle de ventana de SDL). Si la ventana de la app es, por ejemplo, 1280×720 en vez de todo el escritorio 4K, el ahorro de tokens es inmediato y no requiere reescalar nada.

2. **Fijar explícitamente el nivel de detalle en GPT-5.6.** Nunca dejar `detail` en `auto` (equivale a `original`, sin techo). Usar `"detail": "high"` explícitamente para reducir el coste ~3-4× frente al comportamiento por defecto, verificando antes contra la API real cuál es el presupuesto de parches vigente para el modelo concreto que se use.

3. **Reescalar la captura antes de enviarla.** Redimensionar con Pillow/OpenCV a ~1024-1568 px de lado largo antes de mandarla (siempre por debajo del tope nativo del modelo, p. ej. 1568 px para Claude estándar). Para verificación de UI (botones, textos, estados), esta resolución suele ser más que suficiente; para necesitar más detalle real (leer texto pequeño, contar píxeles) hay que sopesarlo caso por caso.

4. **Usar un modelo barato para el "primer filtro" y reservar el caro para casos difíciles.** Un patrón eficaz: que un modelo económico (Haiku 4.5, GPT-5.6 Luna) haga la verificación rutinaria "¿la pantalla cambió como se esperaba? sí/no", y solo escalar al modelo caro (Opus 5, GPT-5.6 Sol) cuando hay una discrepancia real que requiere análisis más profundo (fallo, comportamiento inesperado).

5. **Verificación por comparación de imágenes en local antes de llamar al modelo.** Un diff de píxeles o SSIM (`scikit-image`, `opencv`) entre la captura actual y la esperada/anterior, calculado localmente en Python sin coste de API, puede filtrar el 90%+ de los pasos donde "no ha pasado nada visualmente relevante" y evitar llamar al LLM en absoluto en esos casos.

6. **Verificar estado interno en vez de solo píxeles cuando sea posible.** Si la app expone hooks de test (estado del juego, valores de widgets, logs estructurados), usar aserciones de texto/datos en vez de visión siempre que baste — la visión debería reservarse para lo que *solo* se puede verificar mirando el render (composición visual, efectos, layout).

7. **Acotar o resetear el contexto de conversación entre pasos/casos de prueba.** Evitar un único hilo gigante para toda la sesión de QA. Iniciar conversaciones nuevas y cortas por caso de prueba (o por aserción) limita el efecto de acumulación cuadrática descrito en la sección 7 a, como mucho, el tamaño de un caso individual.

8. **Usar la API de Files / referencias por ID en vez de reenviar base64 en cada turno**, cuando el flujo lo permita, para reducir el tamaño del payload y la latencia (aunque esto no elimina el coste de tokens de visión en sí, si mejora la eficiencia general del pipeline).

9. **Considerar procesamiento por lotes (Batch API)** para análisis de test no interactivo/offline: tanto Anthropic como OpenAI ofrecen ~50% de descuento en modo batch, adecuado para regresiones nocturnas donde no se necesita respuesta inmediata.

---

## 9. Conclusiones

- Un monitor 4K no es intrínsecamente "más caro" en Claude gracias a su tope de tokens por tier de resolución (máx. 4.784 tokens/imagen pase lo que pase), pero **sí lo es en GPT-5.6 si se usa el comportamiento por defecto**, que no tiene techo.
- El coste de la parte "visión" de un pipeline de testing agéntico sobre una app real puede ir de **~30 $/mes** (bien optimizado, modelo barato) a **más de 3.000 $/mes** (modelo frontier, mal configurado, sin gestión de contexto) — un rango de más de 100×.
- El mayor multiplicador de coste no es la elección de modelo sino **la disciplina de ingeniería**: resolución de captura, nivel de detalle explícito, gestión de contexto y filtrado previo con métodos no-LLM.
- Antes de escalar cualquier suite de testing agéntico basada en visión a producción, se recomienda instrumentar el conteo real de tokens (las respuestas de la API de ambos proveedores incluyen el desglose exacto de tokens usados) para validar estas estimaciones contra el uso real, en vez de fiarse solo de cálculos teóricos.

---

## 10. Fuentes

- Anthropic — Vision (tokenización y costes de imagen): `docs.claude.com/en/docs/build-with-claude/vision`
- Anthropic — Pricing (Opus 5, Sonnet 5, Haiku 4.5): `claude.com/pricing`
- OpenAI — Images and vision (tokenización por parches, niveles de detalle): `platform.openai.com/docs/guides/images-vision`
- OpenAI — Pricing (GPT-5.6 Sol/Terra/Luna): `platform.openai.com/docs/pricing`

*Todas las fuentes consultadas y verificadas el 11 de agosto de 2026. Los precios y comportamientos de tokenización pueden cambiar; revisar la documentación oficial antes de tomar decisiones de presupuesto a largo plazo.*

---

## Anexo A — Aplicación al caso real: "El Juego de la Vida" (Claude Sonnet 5)

**Fecha del anexo:** 11 de agosto de 2026 (revisado el mismo día tras detectar un error de método)

> **⚠️ Corrección de la versión anterior de este anexo.** La primera versión de este
> anexo estimaba el coste de la sesión en **≈$0,85**, calculado a partir del tamaño
> del código/tests/capturas *finales*. El usuario señaló que el coste real que
> reporta OpenCode para esta sesión ronda los **35 $** — casi **43 veces más**. Se
> investigó la causa consultando los datos reales que OpenCode guarda localmente
> (no estimaciones: el coste y el desglose de tokens **exactos**, por mensaje, tal y
> como los devuelve la API). El resultado confirma que la estimación anterior era
> **conceptualmente incompleta**, no solo imprecisa en la cifra: media el coste de
> "producir el contenido final" pero ignoraba casi por completo el coste de
> **operar la sesión agéntica que lo produjo**. Las secciones A.2 y A.3 explican
> el porqué; el resto del anexo usa ya los datos reales.

### A.1 Ficha del caso (datos reales)

| Dato | Valor |
|---|---|
| Modelo | **Claude Sonnet 5** (`claude-sonnet-5`, variante `max`, proveedor `github-copilot`) |
| Modalidad | Sesión única y continua (planificación + 8 fases de implementación + pulido visual + este mismo anexo) |
| **Coste real de la sesión** (tabla `session` de la base de datos local de OpenCode) | **$36,55** |
| Mensajes de asistente / llamadas a herramientas | 338 mensajes · 340 llamadas a herramientas (131 `bash`, 65 `read`, 59 `edit`, 46 `write`, 17 de memoria/`engram`, 12 `todowrite`, 9 `webfetch`) |
| Tokens reales (input / output / *cache read* / *cache write*) | 660 / 472.753 / **126.893.454** / 2.274.874 |
| Código de producción entregado | 2.986 líneas / 137.204 caracteres, 14 módulos |
| Tests entregados | 2.362 líneas / 108.741 caracteres, 371 tests |

La fila que importa es la de los tokens: **660 de entrada "fresca" frente a casi 127 millones releídos de caché.** Ahí está toda la explicación.

### A.2 Cómo se obtuvieron estos datos (no son una estimación)

A diferencia del resto del informe (y de la versión anterior de este anexo), estas cifras **no están calculadas** a partir de heurísticas de caracteres/tokens: se leyeron directamente de `opencode.db` (SQLite), que OpenCode mantiene en el equipo local (`~/.local/share/opencode/`). Dos tablas relevantes:

- `session`: una fila por sesión, con columnas `cost`, `tokens_input`, `tokens_output`, `tokens_reasoning`, `tokens_cache_read`, `tokens_cache_write` — el agregado de toda la sesión.
- `message`: una fila por paso del agente, cuyo campo `data` (JSON) incluye, para cada mensaje de asistente, su **propio** `cost` y `tokens` — exactamente el mismo desglose, pero por mensaje individual.

Esto permitió, además del total, **atribuir el coste de cada mensaje a la actividad concreta que realizó** (mirando qué herramienta invocó y sobre qué fichero: escribir en `src/`, escribir en `tests/`, leer una captura `.png`, ejecutar `pytest`, etc. — ver metodología completa en §A.5). Sumando el coste de los 338 mensajes de asistente se obtiene $37,52, un 2,7 % por encima del $36,55 registrado a nivel de sesión — diferencia asumible, atribuible a redondeos y a un puñado de mensajes sin coste asociado.

### A.3 Por qué la estimación anterior fallaba por un factor de ~43×

La versión anterior de este anexo calculaba, en esencia, *"¿cuánto costaría generar, de una sola vez y sin contexto previo, el texto final de estos ficheros?"* Esa pregunta **no es la que hay que responder**, porque así no es como trabaja un agente de codificación: la API de los modelos es *stateless* — cada turno reenvía **toda la conversación anterior** (system prompt, cada fichero leído, cada salida de `bash`, cada línea de código ya escrita, cada razonamiento previo) para que el modelo tenga contexto. Con **338 pasos** en una única conversación que fue creciendo todo el tiempo, el volumen de "recontexto" reenviado turno a turno es enorme.

La caché de prompts (mecanismo de mitigación descrito en la sección 7 del informe principal, no una de las recomendaciones numeradas de la §8) evita que ese recontexto se cobre a precio de entrada completo: se cobra como *cache read*, a **~10 % del precio de entrada** para Sonnet 5. Pero un descuento del 90 % sobre una cantidad suficientemente descomunal sigue siendo una cantidad grande:

| Concepto | Tokens | Precio | Coste |
|---|---:|---:|---:|
| Input "fresco" (no cacheado) | 660 | $2,00 /M | $0,00 |
| Output (código, texto, parámetros de herramientas) | 472.753 | $10,00 /M | $4,73 |
| **Cache *read*** (recontexto reenviado y releído en cada turno) | **126.893.454** | $0,20 /M | **$25,38** |
| Cache *write* (contexto nuevo que se cachea por primera vez) | 2.274.874 | ~$2,50 /M* | $5,69 |
| **TOTAL** | | | **$35,79** (≈ el $36,55 real) |

*\* Estimado como 1,25× el precio de entrada (TTL de caché de 5 minutos, el valor por defecto de Anthropic); no publicado explícitamente para esta combinación proveedor/variante, pero el total resultante casa con el coste real dentro de un ~2 %.*

**El 87 % del coste de esta sesión ($31,07 de $36,55) es relectura/escritura de contexto acumulado, no generación de contenido nuevo.** Solo el 13 % es el output real (código, tests, comentarios, llamadas a herramientas). Esto es, exactamente, el **"riesgo oculto" de la sección 7 del informe principal** — acumulación de contexto en conversaciones multi-turno — pero mucho más severo de lo que aquella sección proyectaba, porque allí se modelaba únicamente la repetición de **imágenes** en un caso de 15 pasos; aquí se repite **toda la conversación de una sesión de desarrollo completa de 338 pasos**, incluyendo código, salidas de comandos y razonamiento. La versión anterior de este anexo, en su §A.6, llegó a concluir que "el riesgo... es mucho menos relevante aquí" — **esa conclusión era incorrecta**, y esta revisión la corrige explícitamente.

### A.4 Capturas de pantalla realmente utilizadas

Esto no cambia respecto a la versión anterior — son datos observables directamente, no estimaciones de coste:

| Captura | Resolución | Veces vista | Qué reveló |
|---|---:|---:|---|
| `smoke_test.png` | 1300×860 | 3 | Símbolos Unicode rotos (▶⏸↺↻) → luego texto "Coplar" por el bug de fuente |
| `overlay_patterns.png` | 1300×860 | 2 | Bug de coordenadas en `Panel` (widgets hijos mal posicionados) |
| `overlay_help.png` | 1300×860 | 3 | Texto cortado por altura/anchura del overlay mal calculada |
| `overlay_files.png` | 1300×860 | 1 | Confirmación de que el navegador de archivos ya cabía bien |
| `smoke_classic.png` | 1300×860 | 1 | Confirmación visual de que el cañón de Gosper dispara planeadores correctamente |
| `smoke_polish.png` | 1300×860 | 1 | Confirmación de selección y previsualización de sello |
| `smoke_scrolled.png` | 1300×860 | 1 | Confirmación del scroll del panel y la gráfica de población (sparkline) |
| `copiar_test.png` / `copiar_test_big.png` | 42×15 / 336×120 | 1 + 1 | Confirmación del bug "Copiar"→"Coplar" |
| 4× `font_*-20.png` | ~1056×100 | 1 c/u | Comparativa de fuentes para el fix del bug de la "i" |

**13 capturas distintas, 18 lecturas**, todas de la ventana de la app (1300×860), nunca del escritorio — y encontraron los 3 bugs de interfaz reales descritos en la Fase 7 del proyecto.

### A.5 Desglose real del gasto por actividad (atribuido mensaje a mensaje)

Cada uno de los 338 mensajes de asistente se clasificó según la herramienta que invocó y, cuando aplica, la ruta del fichero (`src/` → código, `tests/` → tests, `.png` → visual, `pytest`/scripts de verificación → tests, llamadas a `engram`/gestión de tareas/`bash` genérico → *overhead* de la sesión). Cuando un mensaje mezclaba categorías, su coste se repartió a partes iguales entre ellas.

| Categoría | Coste real | % del total |
|---|---:|---:|
| **Código** (escribir/editar `src/`, `Docs/`, `README.md`, leer ficheros de código, investigación web) | $13,96 | **37,4 %** |
| **Tests, en sentido amplio** (subtotal ↓) | $14,08 | **37,7 %** |
| &nbsp;&nbsp;↳ Scripts de verificación puntuales (benchmarks, validación empírica de patrones) | $4,20 | 29,8 % *(de "tests")* |
| &nbsp;&nbsp;↳ Ejecuciones de `pytest` | $3,91 | 27,8 % *(de "tests")* |
| &nbsp;&nbsp;↳ Escribir/editar la suite `tests/*.py` | $3,27 | 23,2 % *(de "tests")* |
| &nbsp;&nbsp;↳ **Análisis visual de capturas de pantalla** | **$2,01** | **14,3 % *(de "tests")*** |
| &nbsp;&nbsp;↳ Releer ficheros de test ya existentes | $0,69 | 4,9 % *(de "tests")* |
| *Overhead* de la sesión (`bash` genérico, memoria `engram`, gestión de tareas, llamada inválida) | $9,31 | **24,9 %** |
| **TOTAL clasificado** | **$37,34** | 100 % *(≈ $36,55 real, dif. ~2 %)* |

**Lo que esto responde, literalmente, a la pregunta original:**

- **Código ≈ 37 %**, **tests (en sentido amplio) ≈ 38 %** — mucho más parejos entre sí de lo que sugería la estimación anterior (43 %/57 %). La razón: las tareas de test/verificación tienden a ocurrir **más tarde** en la sesión (cuando ya hay más contexto acumulado que releer) y se **repiten** muchas veces (cada ejecución de `pytest` vuelve a pagar el recontexto completo acumulado hasta ese punto), así que cuestan más por unidad de contenido nuevo que escribir código una vez.
- **Dentro de "tests", el análisis de capturas de pantalla representó ≈14 %** — bastante menos de lo que sugería la estimación anterior (≈38 %). La mayor parte del gasto de testing no fue mirar imágenes: fue ejecutar `pytest` una y otra vez y escribir los propios ficheros de test.
- En términos del **coste total de la sesión, el análisis visual fue ≈5,4 %** ($2,01 de $37,34) — una cifra que, curiosamente, **sí** queda cerca de lo que la estimación (defectuosa) anterior había dicho por casualidad (≈8 %), aunque llegó ahí por un camino equivocado (ignoraba tanto el numerador real de "tests" como el denominador real del total).
- Hay una categoría que la versión anterior **ni siquiera contemplaba**: el **25 % de "overhead"** — comandos `bash` genéricos (listados de directorio, `uv sync`, limpieza de ficheros), llamadas a la memoria persistente (`engram`) y gestión de la lista de tareas. Es coste real de la sesión que no es ni "escribir código" ni "testear", sino simplemente **operar el agente**.

### A.6 Contraste con las recomendaciones del informe principal (revisado)

| Recomendación del informe (§8) | ¿Se siguió en este caso? |
|---|---|
| 1. No capturar el escritorio 4K completo | ✅ Sí — todas las capturas son de la ventana de la app (1300×860) |
| 3. Reescalar antes de enviar | ✅ De facto — 1300 px ya está por debajo del tope de Sonnet 5 |
| 7. **Acotar o resetear el contexto entre pasos** | ❌ **No, y esto es lo que ha costado ~$31 de los $36,55** — una única conversación continua de 338 pasos, sin reinicios, es precisamente el escenario que la sección 7 del informe advierte que hay que evitar |
| 9. Batch API (procesamiento offline) | N/A — sesión interactiva, no aplica |
| *(§7)* Caché de prompts, como mitigación del riesgo de acumulación de contexto | ✅ Parcialmente — sí estaba activa (de ahí que el input "fresco" fuera solo 660 tokens, no 127 millones a precio completo) y ahorró aproximadamente un 90 % sobre lo que habría costado sin ella — pero ni siquiera con ese descuento el volumen deja de dominar la factura |

La lectura correcta, ya con datos reales: **la recomendación más importante de las nueve del informe principal para este tipo de sesión no es ninguna de las relativas a imágenes — es la número 7.** Trocear una sesión de desarrollo larga en sub-sesiones más cortas (por fase, o al terminar cada bloque de trabajo estable) habría evitado que el recontexto creciera de forma acumulativa durante 338 pasos seguidos, y es previsiblemente la palanca de ahorro más grande disponible, muy por encima de cualquier optimización sobre las capturas de pantalla.

### A.7 Conclusión del anexo (revisada)

El coste real de construir "El Juego de la Vida" con Claude Sonnet 5 en una sesión continua fue **$36,55** — no los $0,85 que estimaba la primera versión de este anexo, y consistente con los ~35 $ que el propio usuario observó en OpenCode. El error de la primera versión no fue de precisión aritmética sino de **alcance**: medía el coste de *escribir* el producto final, no el coste de *operar la sesión agéntica* que lo escribió, y esa segunda cifra está dominada (≈87 %) por la relectura de contexto acumulado (*cache read*), no por la generación de contenido nuevo. Dentro del gasto que sí es atribuible a actividad reconocible, código y tests quedan casi empatados (≈37 % / ≈38 %), y el análisis de capturas de pantalla —el tema del cuerpo principal del informe— resulta ser una porción modesta tanto del gasto de testing (≈14 %) como del gasto total (≈5,4 %). La lección que deja este caso, más allá de las cifras concretas, es que **en agentes de codificación de sesión larga, la gestión del contexto de la conversación (acotarlo, resetearlo entre fases, o confiar en un buen mecanismo de caché) importa más para el coste final que cualquier decisión sobre cómo o cuánto se usa la visión** — el propio informe principal ya lo advertía en su sección 7, y este caso real es la confirmación empírica de que el riesgo no era teórico.

---

## Anexo B — Patrón práctico en OpenCode para evitar la acumulación de contexto (recomendación nº 7 aplicada)

**Fecha del anexo:** 11 de agosto de 2026

El Anexo A confirmó que la recomendación nº 7 del informe principal (*"acotar o resetear el contexto entre pasos/casos de prueba"*) es, con diferencia, la palanca de ahorro más importante para sesiones agénticas largas — muy por encima de cualquier optimización sobre capturas de pantalla. Esta sección traduce esa recomendación a **mecanismos concretos disponibles en OpenCode**, que es la herramienta que se está usando en este proyecto.

### B.1 Por qué ocurre: el modelo es *stateless*, la conversación no

La API de los modelos no tiene memoria entre llamadas: cada turno reenvía el system prompt, todo el historial de mensajes, cada fichero leído y cada salida de herramienta anterior. Si todo ese historial vive en **una única conversación** que crece paso a paso, el coste de recontexto crece de forma triangular/cuadrática con el número de pasos (sección 7). La caché de prompts amortigua el precio (~90 % de descuento) pero no elimina el volumen — como demostró el Anexo A, ni con caché activa deja de dominar la factura.

La única forma de romper ese crecimiento es **no dejar que el historial de una única conversación crezca sin límite**. OpenCode ofrece varios mecanismos para esto, de más a menos aislamiento:

### B.2 Mecanismos disponibles en OpenCode, de mayor a menor impacto

| Mecanismo | Qué hace | Por qué ataca el problema |
|---|---|---|
| **Subagentes vía Task tool** (`general`, `explore`, `scout`, o agentes personalizados) | Cada invocación de `task` crea una **child session con contexto fresco** — no hereda el historial completo de la sesión padre. El subagente hace su trabajo (potencialmente muchos pasos propios) y devuelve **un único mensaje-resumen** al padre. | Es la mitigación más potente: el coste cuadrático de recontexto ocurre *dentro* del subagente, sobre una base mucho menor de pasos, y el padre solo paga el resumen final (unos pocos cientos/miles de tokens), no el detalle interno. |
| **`/compact`** (alias `/summarize`, keybind `ctrl+x c`) | Resume la sesión actual en un contexto más pequeño. Hay un agente oculto de compactación que además se dispara **automáticamente** cuando hace falta (desactivable con `OPENCODE_DISABLE_AUTOCOMPACT`). | Poda el historial acumulado antes de que siga creciendo. Conviene invocarlo **proactivamente al cerrar cada fase estable**, no esperar a que salte solo. |
| **`/new`** (alias `/clear`, keybind `ctrl+x n`) | Empieza una sesión completamente nueva. Más agresivo que `/compact`: no hay resumen, pero el estado del proyecto en disco (código, tests, `AGENTS.md`) persiste igualmente. | Ideal entre fases **totalmente independientes** de una tarea grande (terminado y verificado el motor de reglas → sesión nueva para el overlay de ayuda). |
| **`steps` / max steps por agente** (config `opencode.json` o frontmatter del agente) | Límite de iteraciones agénticas; al alcanzarlo, el agente se ve forzado a resumir su trabajo y parar. | Salvaguarda contra que una tarea se descontrole a cientos de pasos en un único hilo sin que nadie lo note hasta la factura. |
| **Persistencia externa al chat** (`AGENTS.md`, `todowrite`, memoria Engram MCP) | Guarda decisiones/estado en disco o en memoria estructurada consultable bajo demanda, en vez de depender de que "esté en el historial" para que el modelo lo recuerde. | Una consulta corta a memoria persistente cuesta un puñado de tokens; releer todo el historial de chat para encontrar la misma información cuesta el recontexto completo acumulado hasta ese punto. |
| **Navegación de child sessions** (`session_child_first`, `session_child_cycle`, `session_parent`) | Permite inspeccionar el trabajo de un subagente sin fusionar su contexto en el hilo principal. | Se puede auditar/revisar una fase delegada sin pagar por traer su historial completo a la sesión padre. |

### B.3 Patrón recomendado para crear de forma agéntica una tarea grande

1. **Planificar primero** (modo `Plan`, o pidiendo explícitamente un plan antes de ejecutar) para descomponer la tarea en **fases acotadas e independientes** — por módulo, por capa, o por bug/feature concreta. El propio Anexo A lo ilustra: el proyecto tuvo fases naturalmente separables (motor de reglas → UI del overlay → fix de fuente → pulido visual) que en su lugar se ejecutaron todas en el mismo hilo.
2. **Registrar el plan fuera de la conversación** — con `todowrite` (que ya persiste de forma estructurada, no como texto de chat) y/o en un fichero del repo. Esto sirve de "memoria externa" barata de releer, en vez de depender de que quede en el historial.
3. **Delegar cada fase autocontenida a un subagente vía Task**, con un prompt **muy detallado y autosuficiente** — el subagente no ve el historial del padre, así que hay que darle todo el contexto que necesita en el propio prompt de invocación (qué archivos tocar, qué convenciones seguir, cómo verificar su propio trabajo).
4. **Verificar cada fase dentro de su propio subagente** (incluyendo, si aplica, el análisis de capturas de pantalla de la sección 3-8 de este informe) en vez de acumular ejecuciones de test en el hilo principal.
5. **Compactar o iniciar sesión nueva entre fases estables** — al terminar y dar por buena una fase, `/compact` si se quiere conservar un resumen navegable, o `/new` si la siguiente fase es independiente y no necesita nada del detalle anterior (el código ya está en disco).
6. **Fijar un `steps` máximo razonable** en los agentes usados para fases individuales, como red de seguridad ante descontroles.

### B.4 Impacto ilustrativo de aplicar este patrón al caso del Anexo A

Como ilustración conceptual del **orden de magnitud** del ahorro (no una reconstrucción exacta — los 338 pasos reales no tienen tamaño uniforme, así que esto es una simplificación pedagógica con el mismo modelo triangular ya usado en la sección 7):

| Estructura | Cálculo | Recontexto acumulado (unidades relativas) |
|---|---|---:|
| 1 sesión continua de 338 pasos (lo que ocurrió realmente) | `338×339/2` | **57.291** |
| 10 subagentes de ~34 pasos cada uno, delegados desde un padre orquestador | `10 × (34×35/2)` | **5.610** |

**Reducción teórica: ~90 %** (10× menos recontexto acumulado) simplemente por trocear la misma cantidad total de trabajo en unidades más pequeñas y aisladas, en vez de cambiar nada sobre el uso de visión. Esto es coherente con la conclusión del Anexo A: la partida dominante del coste real ($31 de $36,55) es estructural — cómo se organiza la sesión — no el modelo ni las capturas de pantalla en sí.

### B.5 Conclusión del anexo

OpenCode ya trae las piezas necesarias para aplicar la recomendación nº 7 sin herramientas externas: subagentes con contexto fresco por defecto (Task tool), compactación manual y automática (`/compact`), reinicio limpio de sesión (`/new`), límites de pasos por agente, y un mecanismo de memoria persistente (Engram u otro MCP equivalente) para que el conocimiento sobreviva entre sesiones sin tener que arrastrarlo en el historial de chat. El patrón concreto es: **planificar por fases, delegar cada fase a un subagente autocontenido, verificar dentro de esa delegación, y cortar el hilo (compact o new) entre fases** — en vez de dejar crecer una única conversación de principio a fin de la tarea grande.


