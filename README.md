# El Juego de la Vida

Una implementación interactiva del **Juego de la Vida** de Conway (y varias
reglas *life-like* emparentadas), escrita en Python con [uv](https://docs.astral.sh/uv/),
[NumPy](https://numpy.org/) y [pygame-ce](https://pyga.me/).

> Ver [`Docs/Planning.md`](Docs/Planning.md) para la investigación de las
> reglas, la justificación del stack técnico y el plan de fases seguido.
> Ver [`Docs/Controles.md`](Docs/Controles.md) para la chuleta completa de
> atajos de teclado y ratón.

## Características

- **Rejilla configurable**, 200×200 por defecto (el mínimo pedido) y hasta
  1024×1024 o más, con topología **toroidal** (bordes enlazados) o
  **acotada** (exterior muerto), conmutable en caliente.
- **Motor vectorizado con NumPy**: más de 6.000 generaciones/segundo a
  200×200 (medido), muy por encima del requisito de 2-3 gen/s. Incluye una
  optimización automática por caja envolvente para patrones dispersos en
  rejillas grandes.
- **11 reglas *life-like*** además de la Conway clásica (B3/S23): HighLife,
  Day & Night, Seeds, Diamoeba, 2x2, Morley, Anneal, Life without Death,
  Replicator — conmutables desde la interfaz.
- **Controles completos de simulación**: pausar/continuar, paso a paso,
  control de velocidad (12 niveles, de 1 gen/s hasta *MAX*, miles de gen/s),
  limpiar, resetear a la semilla, y relleno aleatorio con densidad ajustable.
- **Edición interactiva**: pintar y borrar celdas arrastrando el ratón (sin
  huecos, incluso con la simulación en marcha), selección rectangular,
  copiar/cortar/pegar, deshacer/rehacer.
- **Biblioteca de 30 construcciones conocidas**, verificadas por simulación
  real (no solo copiadas de memoria): formas estables, osciladores, naves,
  matusalenes y cañones de planeadores de Gosper y Simkin. Se colocan como
  "sello" con rotación y volteo.
- **Persistencia en formato RLE estándar** (compatible con Golly/LifeWiki):
  guardar el tablero completo o solo una selección, cargar patrones propios
  o externos, navegador de archivos integrado.
- **Coloreado por edad** (opcional, conmutable): las celdas nuevas brillan
  en cálido, las estables se enfrían, y las recién muertas dejan una estela
  que se desvanece — o el modo **clásico** blanco/negro de toda la vida.
- **Detección automática de ciclos**: la aplicación reconoce cuándo el
  tablero se ha vuelto una forma estable o un oscilador (y de qué periodo),
  con opción de auto-pausar.
- **Zoom y paneo** fluidos, gráfica de tendencia de población, exportación a
  PNG, pantalla completa con `F11`, información permanente del tamaño de la
  matriz, y un modo `--benchmark` que mide el rendimiento real sin abrir
  ventana. El zoom mínimo ajusta la matriz completa al viewport.

## Requisitos

- [uv](https://docs.astral.sh/uv/) instalado (gestiona Python y las
  dependencias automáticamente; no hace falta instalar Python ni paquetes
  manualmente).

## Cómo ejecutarlo

```powershell
uv run vida
```

Este único comando resuelve el intérprete de Python y las dependencias
(NumPy, pygame-ce) e inicia la aplicación con una rejilla vacía de 200×200.

### Opciones de línea de comandos

```powershell
uv run vida --size 512x512          # rejilla de otro tamano (o "N" para NxN)
uv run vida --rule highlife         # empezar con otra regla del catalogo
uv run vida --topology bounded      # exterior muerto en vez de toroidal
uv run vida --random --density 0.35 --seed 42   # arrancar con una sopa aleatoria reproducible
uv run vida --window 1600x1000      # tamano inicial de ventana distinto
uv run vida --fullscreen             # arrancar a pantalla completa (F11 para alternar)
uv run vida --version
uv run vida --help
```

### Modo benchmark (sin ventana)

Mide objetivamente las generaciones por segundo reales en esta máquina:

```powershell
uv run vida --benchmark --size 200x200 --benchmark-generations 300
```

## Controles básicos

| Acción | Cómo |
|---|---|
| Pausar / continuar | `Espacio` o botón "Reproducir/Pausar" |
| Paso a paso | `→` / `N` (con la simulación en pausa) |
| Cambiar velocidad | `+` / `-` o el deslizador "Velocidad" |
| Pintar / borrar celdas | Clic izquierdo / derecho, arrastrando |
| Seleccionar una región | `Mayús` + arrastrar |
| Copiar / cortar / pegar | `Ctrl+C` / `Ctrl+X` / `Ctrl+V` |
| Deshacer / rehacer | `Ctrl+Z` / `Ctrl+Y` |
| Zoom / paneo | Rueda del ratón / botón central + arrastrar |
| Pantalla completa | `F11` o botón de Vista |
| Guardar tablero / selección | `Ctrl+S` / `Ctrl+Mayús+S` |
| Ayuda completa (en la app) | `F1` o `H` |

Ver [`Docs/Controles.md`](Docs/Controles.md) para la lista completa.

## Estructura del proyecto

```
src/vida/
├── engine.py       # motor de simulacion (NumPy, LUT de reglas, undo)
├── rules.py        # parseo de rulestrings B../S.. y catalogo de reglas
├── rle.py          # lectura/escritura de patrones RLE y plaintext
├── patterns.py      # biblioteca de 30 construcciones conocidas y verificadas
├── camera.py        # transformaciones mundo<->pantalla, zoom, paneo
├── renderer.py       # paleta NumPy -> pygame, modos clasico/edad
├── selection.py     # seleccion, portapapeles, sellos, rasterizado de linea
├── persistence.py   # guardar/cargar tableros y selecciones
├── stats.py         # deteccion de ciclos, historial de poblacion
├── app.py           # bucle principal, panel de control, edicion
├── cli.py           # interfaz de linea de comandos
├── benchmark.py      # modo --benchmark headless
└── ui/
    ├── theme.py      # colores y fuentes
    └── widgets.py    # Button, Slider, ListPanel, Sparkline, Panel...

tests/                # 385 tests (pytest, 1 marcado slow)
patterns/             # patrones guardados por el usuario (.rle)
Docs/
├── Planning.md       # investigacion, arquitectura y plan de fases
└── Controles.md      # chuleta de atajos
```

## Tests

```powershell
uv run pytest              # suite rapida (385 tests, ~3 segundos)
uv run pytest -m slow       # incluye la validacion de Acorn (5206 generaciones, ~2.5 min)
```

La biblioteca de patrones (`patterns.py`) no se limita a copiar coordenadas:
cada construcción se valida por simulación real contra sus propiedades
documentadas (periodo, velocidad, generación de extinción o población
exacta en una generación concreta), incluyendo una implementación de
referencia independiente (bucles Python puros) para contrastar el motor
vectorizado.
