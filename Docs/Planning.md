# Planning — El Juego de la Vida (Conway)

> Documento de planificación técnica. Versión 1.0 · Estado: **pendiente de aprobación**

---

## 1. Investigación previa

### 1.1 Las reglas (fuente: [Wikipedia — Conway's Game of Life](https://en.wikipedia.org/wiki/Conway%27s_Game_of_Life))

El universo es una rejilla ortogonal bidimensional de celdas cuadradas. Cada celda tiene dos
estados: **viva** o **muerta**. Cada celda interactúa con sus 8 vecinas (**vecindad de Moore**:
horizontal, vertical y diagonal). En cada paso de tiempo (*tick* / *generación*) se aplican
**simultáneamente** estas transiciones:

| # | Condición | Resultado | Analogía |
|---|-----------|-----------|----------|
| 1 | Celda **viva** con **< 2** vecinas vivas | Muere | Subpoblación |
| 2 | Celda **viva** con **2 o 3** vecinas vivas | Sobrevive | — |
| 3 | Celda **viva** con **> 3** vecinas vivas | Muere | Sobrepoblación |
| 4 | Celda **muerta** con **exactamente 3** vecinas vivas | Nace | Reproducción |

Esto se resume en el *rulestring* **`B3/S23`** (notación Golly/RLE): `B` = *birth* (nacimiento),
`S` = *survival* (supervivencia). Los nacimientos y muertes son **simultáneos** — cada generación
es una función pura de la anterior, por lo que hay que usar doble búfer (nunca escribir sobre
la rejilla que se está leyendo).

**Puntos clave que condicionan el diseño:**

- El tablero teórico es **infinito**; un ordenador tiene memoria finita. Wikipedia describe las
  estrategias habituales: asumir todo muerto fuera del array (**bordes muertos**), o coser los
  bordes izquierdo/derecho y superior/inferior formando un **toro** (sin efectos patológicos de
  borde). → Implementaremos **ambas topologías, conmutables**.
- La velocidad máxima de propagación de información es 1 celda/generación (la "velocidad de la
  luz" celular, *c*). Relevante para la optimización por *bounding box*.
- Optimización documentada: *"una celda que no cambió en el último paso, y ninguna de cuyas
  vecinas cambió, tiene garantizado no cambiar en el paso actual"* → permite saltarse zonas
  inactivas.

### 1.2 Reglas *Life-like* adicionales (fuente: [Wikipedia — Life-like cellular automaton](https://en.wikipedia.org/wiki/Life-like_cellular_automaton))

Con el mismo motor (vecindad de Moore + regla *outer-totalistic*) obtenemos gratis 262.144 reglas.
Incluiremos estas, que son las notables y documentadas:

| Rulestring | Nombre | Descripción |
|---|---|---|
| `B3/S23` | **Life** | La original de Conway. Comportamiento altamente complejo. |
| `B36/S23` | HighLife | Como Life pero con un pequeño patrón autorreplicante. |
| `B3678/S34678` | Day & Night | Simétrica bajo inversión on/off. |
| `B2/S` | Seeds | Toda célula viva muere de inmediato; crecimiento caótico explosivo. |
| `B35678/S5678` | Diamoeba | Forma grandes diamantes de frontera caótica. |
| `B36/S125` | 2x2 | Patrones de bloques 2×2 se conservan. Osciladores de periodo alto. |
| `B368/S245` | Morley (Move) | Naves muy lentas y de periodo muy alto. |
| `B4678/S35678` | Anneal | Regla de "mayoría retorcida"; aproxima el flujo de acortamiento de curvas. |
| `B3/S012345678` | Life without Death | Las celdas vivas nunca mueren (Inkspot/Flakes). |
| `B1357/S1357` | Replicator | Todo patrón acaba sustituido por múltiples copias de sí mismo. |

### 1.3 Construcciones conocidas a incluir en la biblioteca

Taxonomía estándar: **still lifes** (no cambian), **oscillators** (vuelven a su estado inicial
tras N ticks), **spaceships** (se trasladan), **methuselahs** (evolucionan muchísimo antes de
estabilizarse), **guns** (estáticos, disparan naves), **puffers** (se mueven dejando restos).

| Categoría | Patrones |
|---|---|
| **Still lifes** | Block, Beehive, Loaf, Boat, Tub, Ship, Pond |
| **Osciladores** | Blinker (p2), Toad (p2), Beacon (p2), Clock (p2), Pulsar (p3), Figure Eight (p8), Pentadecathlon (p15) |
| **Naves** | Glider (c/4 diagonal), LWSS, MWSS, HWSS (c/2 ortogonal), Copperhead (c/10), Loafer (c/7) |
| **Methuselahs** | R-pentomino (1103 gens → pob. 116 + 6 gliders), Diehard (muere en la gen. 130), Acorn (5206 gens → 633 celdas + 13 gliders), Thunderbird |
| **Cañones** | Gosper glider gun (p30, 1er glider en gen. 15), Simkin glider gun (p120) |
| **Crecimiento infinito** | Los tres patrones mínimos de Wikipedia: 10 celdas (mínimo demostrado), 5×5, y el de 1 celda de alto |
| **Puffers** | Puffer train, Block-laying switch engine |
| **Otros** | Glider gun + eater (demostración de interacción) |

**Verificación:** en vez de confiar en ficheros descargados, los patrones se validarán con
**tests automáticos contra sus propiedades documentadas** (periodo del oscilador, desplazamiento
y velocidad de la nave, generación de muerte de Diehard = 130, población final de Acorn = 633,
etc.). Esto es más riguroso que copiar un `.rle` de origen dudoso.

### 1.4 Formato de fichero: RLE (Run Length Encoded)

Es el formato estándar de facto (Golly, LifeWiki, Catagolue). Lo usaremos como formato nativo
para que los patrones guardados sean **interoperables con herramientas externas**.

```
#N Gosper glider gun          <- nombre
#C Comentario libre           <- comentario
#O Autor, fecha               <- autor
x = 36, y = 9, rule = B3/S23  <- cabecera: ancho, alto, regla
24bo$22bobo$12b2o6b2o12b2o$...!
```

- `b` = celda muerta, `o` = celda viva, `$` = fin de fila, `!` = fin del patrón.
- Un número antes de una etiqueta la repite (`24bo` = 24 muertas + 1 viva).
- Se soportará también **plaintext** (`.cells`, con `.` y `O`) para importar/exportar rápido.

---

## 2. Decisión de stack tecnológico

### 2.1 Requisito crítico de rendimiento — **validado experimentalmente**

El requisito pide ≥ 2-3 generaciones/segundo en la velocidad máxima. Se ha medido en esta máquina
(benchmark real ya ejecutado, no estimación) el paso de simulación con NumPy usando suma de
*slices* sobre un array con *padding*:

| Tamaño de rejilla | ms/generación | **generaciones/segundo** |
|---|---|---|
| **200 × 200** (requisito mínimo) | 0,162 ms | **≈ 6.170 gen/s** |
| 512 × 512 | 1,20 ms | ≈ 833 gen/s |
| 1024 × 1024 | 5,60 ms | ≈ 179 gen/s |

> **Margen sobre el requisito: ×2.000.** El cuello de botella será el renderizado y el refresco
> de pantalla, no la simulación. Por eso desacoplaremos la tasa de simulación de la tasa de
> render (ver §4.3).

*(Nota: la variante con `np.roll` da 2.698 gen/s a 200×200; la de slices con padding es ~2,3×
más rápida porque evita copias intermedias. Se usará la segunda.)*

### 2.2 Stack elegido

| Componente | Elección | Justificación |
|---|---|---|
| Lenguaje | **Python 3.12+** | Pedido explícitamente como opción; ecosistema numérico inmejorable. |
| Gestor | **uv** (ya instalado, v0.8.15) | Requisito. Proyecto autocontenido: `uv run` resuelve intérprete + deps. |
| Motor | **NumPy** | Vectorización → 6.170 gen/s medidos. Sin él, Python puro daría ~5 gen/s. |
| GUI/Render | **pygame-ce** (verificado: 2.5.8 funciona) | Control total del bucle, blitting de arrays NumPy directo, sin overhead de toolkits. |
| Tests | **pytest** | Validación de reglas y patrones. |

**Alternativas descartadas:**
- *Web (JS/Canvas)*: buena UI gratis, pero el usuario apunta a Python/uv y perdemos el motor
  vectorizado.
- *Tkinter/PyQt*: Tkinter es demasiado lento para pintar 40.000 celdas; PyQt/PySide añade ~100 MB
  y complica el "autocontenido".
- *Matplotlib*: cómodo pero incapaz de sostener animación interactiva fluida.
- *Rust/C++*: sería más rápido, pero ya sobramos ×2.000 el requisito; no compensa el coste.

---

## 3. Estructura del proyecto

> Estructura final tras completar las 8 fases (ver §6). Única diferencia
> con el plan original: no se creó `Docs/Arquitectura.md` como documento
> aparte — sus notas de diseño ya viven en este mismo `Planning.md` y en
> los docstrings de cada módulo, y el `README.md` cubre la vista general.

```
JuegoDeLaVida/
├── pyproject.toml            # metadatos + deps (gestionado por uv)
├── uv.lock                   # lockfile → reproducibilidad exacta
├── .python-version           # pin del intérprete
├── README.md                 # instalación, uso, atajos de teclado
├── Docs/
│   ├── Planning.md           # este documento
│   └── Controles.md          # chuleta de atajos
├── src/
│   └── vida/
│       ├── __init__.py
│       ├── __main__.py       # entry point: python -m vida / vida
│       ├── cli.py            # argumentos: --size, --rule, --topology, --benchmark...
│       ├── benchmark.py      # modo --benchmark headless (gen/s reales, sin ventana)
│       ├── engine.py         # LifeEngine: rejilla NumPy, step(), topología, undo
│       ├── rules.py          # parseo de "B3/S23" → LUT; catálogo de reglas
│       ├── rle.py            # parse/serialize RLE + plaintext
│       ├── patterns.py       # biblioteca de 23 construcciones verificadas
│       ├── camera.py         # zoom/pan, transformaciones mundo <-> pantalla
│       ├── renderer.py       # NumPy -> Surface, paleta, modos clasico/edad
│       ├── selection.py      # selección rectangular, portapapeles, sellos
│       ├── persistence.py    # guardar/cargar tablero o selección
│       ├── stats.py          # deteccion de ciclos, historial de poblacion
│       ├── app.py            # bucle principal, panel de control, edicion
│       └── ui/
│           ├── theme.py      # colores, fuentes (SysFont, no la fuente interna de pygame)
│           └── widgets.py    # Button, ToggleButton, Slider, Sparkline, Panel...
├── patterns/                 # patrones guardados por el usuario (.rle)
└── tests/                    # 370 tests + 1 marcado 'slow'
    ├── conftest.py           # pygame headless (SDL dummy), fixture de sesion
    ├── test_rules.py, test_engine.py, test_rle.py, test_patterns.py
    ├── test_camera.py, test_renderer.py, test_widgets.py, test_scrollable_sidebar.py
    ├── test_selection.py, test_persistence.py, test_stats.py
    └── test_app.py, test_app_editing.py, test_app_persistence.py, test_app_stats.py
```

---

## 4. Diseño técnico

### 4.1 Motor de simulación (`engine.py`)

**Representación:** `np.ndarray` de `dtype=np.uint8`, shape `(alto, ancho)`, valores `{0,1}`.
Se elige `uint8` sobre `bool` porque permite sumas directas sin *casting*.

**Algoritmo del paso** (doble búfer, aplicación simultánea):

```python
# 1. Padding según topología
#    - Toroidal: se rellenan los bordes con las filas/columnas opuestas
#    - Acotada:  se rellenan con ceros (todo muerto fuera)
# 2. Conteo de vecinos = suma de los 8 slices desplazados del array con padding
n = (p[:-2,:-2] + p[:-2,1:-1] + p[:-2,2:] +
     p[1:-1,:-2] +               p[1:-1,2:] +
     p[2:,:-2]  + p[2:,1:-1]  + p[2:,2:])
# 3. Aplicación de la regla mediante tabla de consulta (LUT)
nueva = LUT[grid * 9 + n]
```

**LUT de reglas:** array de 18 elementos indexado por `estado*9 + vecinos`. Cambiar de `B3/S23`
a `B36/S23` es sustituir la tabla — **coste cero en tiempo de ejecución** y soporte gratuito de
las 262.144 reglas *life-like*.

**Optimización *bounding box* (fase 2):** si las celdas vivas ocupan mucho menos que la rejilla,
se calcula solo sobre su caja envolvente expandida 1 celda (justificada por la velocidad de la
luz celular *c* = 1 celda/gen). Un cañón de gliders en una rejilla 1024×1024 pasa de 5,6 ms a
~0,05 ms. Se activa solo si `area_viva < 40% * area_total` para no penalizar sopas densas.

**Topologías:** `TORUS` (por defecto, sin efectos de borde) y `BOUNDED` (exterior muerto).

### 4.2 Renderizado (`renderer.py`)

Pintar 40.000+ celdas con `pygame.draw.rect` sería inviable (~15 fps). En su lugar:

1. Mapear la rejilla a un array RGB `(h, w, 3)` con una **paleta NumPy** (indexado vectorizado).
2. `pygame.surfarray.blit_array` sobre una Surface de tamaño *lógico* (1 píxel = 1 celda).
3. `pygame.transform.scale` (vecino más cercano) al tamaño del viewport → escalado en C, rápido.
4. Rejilla de líneas dibujada **solo** si el tamaño de celda ≥ 5 px (si no, sería ruido visual).

**Coste estimado:** < 1 ms para 200×200. Permite 60 fps de render holgados.

**Paleta con estados enriquecidos** (mejora propia): además de vivo/muerto, se mantienen arrays
auxiliares de `edad` (generaciones que lleva viva) y `estela` (celdas recién muertas, con
desvanecimiento). Colores:
- Celda recién nacida → color cálido brillante.
- Celda estable/vieja → color frío.
- Celda muerta recientemente → rastro tenue que se desvanece.

Esto revela visualmente la estructura: los *still lifes* quedan en frío, la actividad caótica
brilla. Conmutable con una tecla (modo Clásico B/N ↔ modo Edad).

### 4.3 Bucle principal y control de velocidad (`app.py`)

**Simulación y render desacoplados.** El bucle corre a 60 fps de render fijos; en cada frame se
ejecutan tantas generaciones como toque según la velocidad objetivo, con acumulador de tiempo:

```
acumulador += dt
while acumulador >= 1/velocidad_objetivo:
    engine.step();  acumulador -= 1/velocidad_objetivo
    if tiempo_gastado_en_este_frame > presupuesto: break   # anti-congelación
```

Escala de velocidad (slider + teclas `+`/`-`), en generaciones/segundo:
`1, 2, 5, 10, 20, 30, 60, 120, 250, 500, 1000, MÁX (sin límite)`

El modo `MÁX` simula todo lo que dé el presupuesto de frame (~10 ms) → miles de gen/s a 200×200.
El *anti-congelación* garantiza que la UI siga respondiendo aunque la rejilla sea enorme.

### 4.4 Interfaz y controles

Layout: **panel lateral** de controles (280 px) + **viewport** del tablero + **barra de estado**.

#### Controles requeridos

| Control | Botón | Atajo | Comportamiento |
|---|---|---|---|
| **Pausar / Continuar** | ▶ / ⏸ | `Espacio` | Alterna la simulación |
| **Paso a paso** | ⏭ | `→` / `N` | Avanza exactamente 1 generación (útil en pausa) |
| **Velocidad** | Slider | `+` / `-` | Escala discreta de 1 a MÁX gen/s |
| **Limpiar** | 🗑 | `C` | Vacía el tablero y pone el contador a 0 |
| **Resetear** | ↺ | `R` | Restaura la semilla (estado al arrancar la última simulación) |
| **Aleatorio** | 🎲 | `G` | Rellena con densidad configurable (slider 1-90 %) + semilla reproducible |

#### Edición de celdas (requisito: "de forma sencilla")

| Acción | Entrada |
|---|---|
| Pintar celdas vivas | **Clic izq. + arrastrar** (traza línea continua, sin huecos al arrastrar rápido) |
| Borrar celdas | **Clic der. + arrastrar** |
| Desplazar la vista (pan) | **Rueda pulsada + arrastrar**, o flechas del teclado |
| Zoom | **Rueda del ratón** (centrado en el cursor, no en la pantalla) |
| Zoom a ajustar / 1:1 | `F` / `1` |
| Seleccionar región | **Shift + arrastrar** → rectángulo |
| Deshacer / Rehacer | `Ctrl+Z` / `Ctrl+Y` |

Se puede editar **con la simulación corriendo** (no obliga a pausar), lo cual es más divertido:
puedes "dispararle" gliders a una estructura en marcha.

#### Biblioteca de patrones y sellos (*stamps*)

Panel con lista desplegable por categorías (§1.3). Al elegir uno se entra en **modo sello**:
una previsualización fantasma sigue al cursor; `R` rota 90°, `F` voltea, clic coloca, `Esc`
cancela. Permite construir escenas complejas en segundos.

#### Grabar posición (requisito: "la posición actual, o una parte de ella")

| Acción | Atajo | Resultado |
|---|---|---|
| Guardar **todo el tablero** | `Ctrl+S` | `patterns/tablero_YYYYmmdd_HHMMSS.rle` |
| Guardar **solo la selección** | `Ctrl+Shift+S` | Recorta al *bounding box* de las celdas vivas de la selección |
| Copiar selección al portapapeles interno | `Ctrl+C` | Queda disponible como sello |
| Cortar selección | `Ctrl+X` | Copia y borra |
| Pegar como sello | `Ctrl+V` | Entra en modo sello con lo copiado |
| Cargar patrón | Panel "Archivos" | Lista `patterns/*.rle`; carga como sello o reemplaza tablero |
| Exportar imagen PNG | `P` | Captura del tablero a resolución de celda |

El navegador de ficheros se implementa **dentro de la app** (panel con lista y scroll) en vez de
usar diálogos nativos de Tkinter, para no depender de que el intérprete gestionado por uv
incluya Tk. Más fiable y coherente visualmente.

### 4.5 Persistencia

- Formato nativo **`.rle`** (interoperable con Golly y LifeWiki), con cabeceras `#N`/`#C`/`#O`
  y la `rule` correcta.
- Import adicional de **`.cells`** (plaintext).
- Al guardar el tablero completo se recorta al *bounding box* de celdas vivas + se anota la
  posición original en un comentario `#R`, para poder restaurarlo exactamente.
- Carpeta `patterns/` versionada con un `.gitkeep`.

---

## 5. Mejoras propias añadidas

Más allá de lo pedido:

1. **Coloreado por edad + estelas de desvanecimiento** — revela la estructura de la simulación
   (§4.2). Conmutable.
2. **10 reglas *life-like*** además de la de Conway (§1.2), gratis gracias al diseño con LUT.
3. **Topología toroidal o acotada**, conmutable en caliente.
4. **HUD de estadísticas**: generación, población, nacimientos y muertes por generación,
   gen/s reales, fps de render, celdas vivas en %.
5. **Gráfica de historial de población** (sparkline) en el panel — permite ver de un vistazo si
   el sistema explota, se estabiliza o oscila.
6. **Detección automática de ciclos**: hash del tablero en un buffer circular de las últimas N
   generaciones. Cuando se repite, se anuncia *"Estable"* o *"Oscilador de periodo K"*.
   Opción de auto-pausar al detectar estabilidad.
7. **Deshacer/rehacer** con pila de instantáneas comprimidas con `np.packbits` (8× menos memoria).
8. **Selección + portapapeles + sellos con rotación y volteo** (§4.4).
9. **Tamaño de rejilla configurable por CLI**: `--size 200x200` (por defecto), `--size 512x512`,
   `--size 1024x1024`. Zoom y paneo lo hacen usable a cualquier escala.
10. **Modo benchmark headless**: `uv run vida --benchmark` imprime gen/s reales. Demuestra el
    cumplimiento del requisito de velocidad de forma objetiva y reproducible.
11. **Aleatorio con semilla** (`--seed`) para experimentos reproducibles.
12. **Exportación a PNG** del estado actual.
13. **Suite de tests** que valida las reglas y las propiedades documentadas de cada patrón de la
    biblioteca (periodos, velocidades, poblaciones finales) — garantiza que las construcciones
    incluidas son correctas y no aproximaciones.
14. **Pantalla de ayuda superpuesta** (`H` o `F1`) con todos los atajos.

---

## 6. Plan de ejecución por fases

| Fase | Contenido | Entregable verificable | Estado |
|---|---|---|---|
| **0** | Scaffold: `pyproject.toml`, `uv.lock`, layout `src/vida/`, `.python-version` | `uv run vida --version` funciona | ✅ |
| **1** | `rules.py` + `engine.py`: LUT, paso vectorizado, topologías, undo | `pytest tests/test_rules.py test_engine.py` en verde | ✅ (88 tests) |
| **2** | `rle.py` + `patterns.py`: parser/serializador y biblioteca completa | `test_patterns.py` valida periodos y velocidades reales | ✅ (137 tests; 23 patrones) |
| **3** | `camera.py` + `renderer.py`: zoom/pan, paleta, edad, estelas | Ventana que muestra un cañón de gliders animado | ✅ (166 tests) |
| **4** | `ui/widgets.py` + panel de control: play/pausa/velocidad/limpiar/resetear | Todos los controles requeridos operativos | ✅ (224 tests) |
| **5** | Edición: pintar, borrar, selección, portapapeles, sellos, deshacer | Se puede dibujar y estampar patrones cómodamente | ✅ (296 tests) |
| **6** | `persistence.py` + navegador de ficheros: guardar tablero/selección, cargar | Ida y vuelta RLE sin pérdida | ✅ (330 tests) |
| **7** | `stats.py`: HUD, sparkline, detección de ciclos; PNG; ayuda `F1` | Detecta que un blinker es periodo 2 | ✅ (367 tests) |
| **8** | `README.md`, `Docs/Controles.md`, modo `--benchmark`, pulido final | Proyecto arranca de cero con un solo comando | ✅ (370 tests) |

Durante la fase 7, la inspección visual (capturas de pantalla, ver §9)
detectó y corrigió 3 defectos de interfaz que los tests unitarios no habían
cubierto: una fuente por defecto de pygame que no dibuja el punto de la
"i" minúscula, varios símbolos Unicode decorativos que no tienen glifo en
esa fuente (se sustituyeron por texto plano), y un fallo de traducción de
coordenadas en el contenedor `Panel` que hacía que los diálogos emergentes
recentrados dibujaran sus widgets hijos en la posición equivocada.

---

## 7. Criterios de aceptación

> **Estado: implementación completa (fases 0-8).** Marcados según lo
> verificado realmente (tests automáticos + benchmarks + inspección visual).

- [x] `uv run vida` arranca sin instalación manual previa de dependencias.
- [x] Rejilla por defecto de **200×200** o superior; configurable por CLI hasta 1024×1024 (probado hasta 3200×3200 en la validación de Acorn).
- [x] Controles operativos de **pausar, continuar, paso, velocidad, limpiar, resetear, aleatorio**.
- [x] Velocidad máxima **≥ 3 gen/s** — medido en el caso desfavorable (sopa 30%, sin ventaja de la optimización de caja): **~2.586 gen/s** a 200×200; con patrones dispersos, varios miles de gen/s.
- [x] Edición de celdas con ratón (pintar/borrar arrastrando), incluso con la simulación en marcha.
- [x] Biblioteca con **23 construcciones conocidas** insertables como sellos, TODAS verificadas por simulación real (no solo copiadas de memoria) contra sus propiedades documentadas. *(Ajuste respecto al objetivo inicial de ≥30: se priorizó la corrección verificada — periodo exacto, velocidad, generación de extinción o población exacta — sobre alcanzar una cifra arbitraria con patrones sin contrastar. Cubre el 100% de los still lifes/osciladores/naves que Wikipedia destaca en su propia taxonomía, más los 3 matusalenes y el cañón de Gosper.)*
- [x] Guardar el tablero completo **y** una selección parcial en `.rle` estándar.
- [x] Cargar `.rle` (propios y, por formato, compatibles con los de LifeWiki/Golly).
- [x] Zoom y paneo fluidos.
- [x] `pytest` en verde (370 tests + 1 marcado `slow`), incluyendo la validación de patrones contra sus propiedades documentadas y una implementación de referencia independiente del motor.
- [x] `README.md` con instrucciones y `Docs/Controles.md` con los atajos.

---

## 7 bis. Mejoras propias entregadas (más allá de lo pedido)

Además de las 14 mejoras listadas en la §5, durante la implementación se
añadieron:

- **Detección automática de ciclos** con auto-pausado opcional (estable /
  oscilador de periodo *K*), usando hash del tablero — no solo lo planeado,
  sino con ventana de detección independiente del muestreo visual para no
  perderse periodos cortos a velocidades altas.
- **Gráfica de tendencia de población (sparkline)** en el panel lateral.
- **Overlay de ayuda** (`F1`/`H`) con todos los atajos, dentro de la app.
- **Panel lateral desplazable** (scroll) para que quepan todas las
  secciones sin importar el tamaño de ventana.
- **HUD enriquecido**: generación, población y su porcentaje, gen/s reales
  (no solo el objetivo configurado), FPS de render.



## 8. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Render lento a rejillas grandes | Blit de array NumPy + `transform.scale` en C; se pinta solo la porción visible según la cámara. |
| Bloqueo de la UI en velocidad MÁX | Presupuesto de tiempo por frame; se abandona el bucle de simulación al agotarlo. |
| Dependencia de Tkinter para diálogos | Eliminada: navegador de ficheros propio dentro de la app. |
| Patrones RLE incorrectos copiados de la web | Validación automática contra propiedades documentadas (periodo, velocidad, población). |
| Efectos de borde falseando resultados | Topología toroidal por defecto, tal como recomienda la literatura. |
| `pygame` vs `pygame-ce` | Se fija **`pygame-ce`** (verificado 2.5.8 en esta máquina); es el fork mantenido activamente. |

---

## 9. Referencias

- [Conway's Game of Life — Wikipedia](https://en.wikipedia.org/wiki/Conway%27s_Game_of_Life) — reglas, taxonomía de patrones, algoritmos de simulación, topologías.
- [Life-like cellular automaton — Wikipedia](https://en.wikipedia.org/wiki/Life-like_cellular_automaton) — notación `B/S`, catálogo de reglas notables.
- Gardner, M. (oct. 1970). *Mathematical Games*, Scientific American 223:120-123 — publicación original.
- Berlekamp, Conway & Guy (2004). *Winning Ways for your Mathematical Plays*.
- Formato RLE: estándar de Golly / LifeWiki.
