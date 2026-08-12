# Planning de Mejoras — El Juego de la Vida

> Documento de planificación técnica. Versión 1.0 · Estado: **implementado**
> Adenda a [`Docs/Planning.md`](Planning.md) (fases 0-8, ya completadas y en producción).
> Alcance: 4 mejoras solicitadas sobre la aplicación ya funcional. Son **independientes entre
> sí** (ninguna depende de otra), por lo que se pueden implementar y aprobar en cualquier orden,
> o en paralelo.

---

## 0. Resumen ejecutivo

| # | Mejora | Módulos principales | Esfuerzo | Riesgo |
|---|---|---|---|---|
| A | Pantalla completa | `app.py`, `cli.py` | S/M | Medio (depende de plataforma; no verificable bajo el driver SDL *dummy* de los tests) |
| B | Información del tamaño de la matriz | `app.py` | XS | Ninguno |
| C | Más construcciones típicas | `patterns.py`, `app.py` | M/L | Bajo (7 patrones nuevos verificados uno a uno) |
| D | Zoom mínimo = ajuste exacto a pantalla | `camera.py` | S | Bajo (aislado, con tests deterministas) |

Ningún ítem toca el motor de simulación (`engine.py`, `rules.py`) ni el formato de persistencia
(`rle.py`, `persistence.py`).

---

## 1. Mejora A — Pantalla completa

### 1.1 Estado actual

`App.__init__` crea la ventana con un único flag (`app.py:83`):

```python
flags = pygame.RESIZABLE
self.screen = pygame.display.set_mode(window_size, flags)
```

No existe ningún atajo, botón ni bandera de CLI para pantalla completa. `handle_resize()`
(`app.py:552`) ya sabe reaccionar a un cambio de tamaño de ventana (recalcula `viewport_rect` y
avisa a la cámara), pero solo se dispara hoy desde el evento `pygame.VIDEORESIZE`.

### 1.2 Diseño propuesto

**Nuevo estado:** `self.fullscreen: bool = False` y `self._windowed_size: tuple[int, int]`
(para poder restaurar el tamaño de ventana exacto al salir de pantalla completa).

**Nuevo método** `toggle_fullscreen()`:

```python
def toggle_fullscreen(self) -> None:
    if not self.fullscreen:
        self._windowed_size = (self.window_width, self.window_height)
        info = pygame.display.Info()
        self.screen = pygame.display.set_mode((info.current_w, info.current_h), pygame.FULLSCREEN)
    else:
        self.screen = pygame.display.set_mode(self._windowed_size, pygame.RESIZABLE)
    self.fullscreen = not self.fullscreen
    self.handle_resize(*self.screen.get_size())
```

Reutiliza `handle_resize()` tal cual (mismo camino que un *resize* manual): la cámara conserva
`cell_size`/*offset* y simplemente revela más o menos rejilla, igual que ya ocurre hoy al
arrastrar el borde de la ventana. **Decisión explícita:** no se re-centra ni se hace *fit* al
entrar/salir de pantalla completa, para no introducir un comportamiento distinto al que ya existe
en un *resize* normal.

**Dos formas de pedirle a SDL2 la pantalla completa** (ambas viables con pygame-ce 2.5.8, ya
verificado en `Planning.md §2.1`); se elige la primera por ser más explícita y predecible:

| Opción | Cómo | Pros / Contras |
|---|---|---|
| **`set_mode(desktop_size, FULLSCREEN)`** (elegida) | Recrear la ventana con la resolución de escritorio actual (`pygame.display.Info()`) | Explícita, tamaño resultante conocido de antemano, fácil de testear el flujo de estado. Riesgo menor de *flicker* al coincidir con la resolución nativa. |
| `pygame.display.toggle_fullscreen()` | Alternar sin recrear la ventana | Una sola llamada, pero su comportamiento exacto (tamaño de superficie resultante, si dispara o no un evento de resize) varía según SDL/plataforma y tiene historial de *bugs* en versiones antiguas de SDL2 en Windows. |

**Entrada de usuario:**
- Tecla **`F11`** (convención universal en navegadores y editores; no está en uso — se revisó
  `_handle_keydown` y `HELP_LINES` para confirmarlo).
- Botón en la sección "Vista" del panel lateral, junto a "Ajustar a la ventana" / "Tamaño real":
  `ToggleButton(..., "Pantalla completa (F11)", checked=self.fullscreen, on_toggle=...)` — mismo
  patrón ya usado para "Coloreado por edad" (`app.py:237`), de modo que el botón refleje el
  estado (pulsado/despulsado) sin lógica nueva de *widget*.
- **Se descarta** reutilizar `Escape` para salir de pantalla completa: hoy `Escape` ya cancela el
  sello activo o vacía la selección (`app.py:806`); solaparlo rompería ese atajo documentado.
- CLI: nuevo flag `--fullscreen` en `cli.py` (arranca ya en pantalla completa), análogo a
  `--window`.

### 1.3 Riesgos y verificación

El driver de vídeo usado en los tests es `SDL_VIDEODRIVER=dummy` (`tests/conftest.py`), que no
representa una pantalla real: `pygame.display.Info()` y el propio cambio de modo pueden
comportarse de forma degenerada (p. ej. `current_w/h` a 0). Por tanto:

- Los **tests automáticos** solo pueden cubrir la lógica de estado (`fullscreen` alterna,
  `_windowed_size` se recuerda y se restaura, se llama a `handle_resize` con el tamaño nuevo),
  simulando el tamaño "de escritorio" en vez de depender de `pygame.display.Info()` real.
- La **verificación del comportamiento visual real** (¿se ve realmente a pantalla completa en
  Windows? ¿el panel lateral y el viewport se redistribuyen bien? ¿hay parpadeo al alternar?)
  solo se puede hacer con inspección visual manual (capturas), **igual que se hizo en la Fase 7**
  para los bugs de UI — no es automatizable de forma fiable bajo el driver *dummy*.

### 1.4 Documentación a actualizar

`README.md` (características + tabla de opciones de CLI), `Docs/Controles.md` (sección "Vista"),
`HELP_LINES` en `app.py` (overlay F1/H).

---

## 2. Mejora B — Información del tamaño de la matriz actual

### 2.1 Estado actual

La barra de estado (`_draw_status_bar`, `app.py:1001`) ya construye una línea de texto por
fotograma:

```python
text = (f"Gen {self.engine.generation}   "
        f"Pob {self.engine.population} ({self.engine.alive_fraction:.1%})   "
        f"{self.speed_meter.value:,.0f} gen/s   "
        f"FPS {self.clock.get_fps():.0f}")
```

No incluye el tamaño de la rejilla (`engine.width` × `engine.height`), que hoy solo se puede
saber mirando los argumentos de `--size` con los que se arrancó, o contando a ojo.

**Dato clave:** el tamaño de la rejilla es **fijo durante toda la ejecución** — no hay ninguna
función para redimensionarla en caliente, se crea una vez en `App.__init__` (`app.py:88`). Es
información estática de la sesión, no una métrica que cambie por fotograma.

### 2.2 Diseño propuesto

Al ser un dato estático, tiene sentido mostrarlo en **dos sitios** con propósitos distintos (coste
de implementación trivial en ambos, no hay razón para elegir solo uno):

1. **Panel lateral** (siempre visible, no se tapa nunca): una línea nueva justo debajo del
   subtítulo "Conway · B3/S23 y variantes" (`app.py:172-174`), como referencia permanente:

   ```python
   add_label(f"Rejilla {width} × {height} · {width * height:,} celdas",
             font=theme.font_small, color=theme.text_dim, height=18)
   ```

2. **Barra de estado**, al principio de la línea ya existente (visible mientras se mira el
   tablero, sin tener que apartar la vista al panel):

   ```python
   text = (f"{self.engine.width}×{self.engine.height}   "
           f"Gen {self.engine.generation}   "
           ...)
   ```

   Nota: cuando hay un mensaje de estado temporal ("Tablero guardado: …", 3 s de duración) la
   línea de estadísticas al completo se sustituye por ese mensaje — comportamiento **ya existente
   y aceptado hoy** para Gen/Pob/velocidad/FPS; el tamaño de rejilla hereda la misma restricción,
   sin regresión nueva porque el panel lateral (punto 1) lo sigue mostrando siempre.

### 2.3 Tests

Ampliar el test que cubra `_draw_status_bar`/panel (si existe uno que inspeccione el texto
generado) para incluir el nuevo formato; si no existe ninguno hoy, añadir uno mínimo en
`test_app.py` que arranque con un tamaño conocido (p. ej. 64x48) y compruebe que el texto de la
etiqueta del panel contiene `"64 x 48"`.

---

## 3. Mejora C — Más construcciones típicas

### 3.1 Estado actual

30 patrones verificados en 5 categorías (`patterns.py`): 11 formas estables, 7 osciladores, 6
naves, 4 matusalenes, 2 cañones (Gosper y Simkin).

**Hallazgo importante:** el propio `Planning.md` original (§1.3) ya preveía una lista más amplia
que la finalmente implementada. Lo no implementado de esa lista original es el candidato natural
y ya "pre-aprobado en espíritu" para esta mejora, en vez de proponer patrones nuevos sin
precedente:

| Categoría | Ya implementado | Fuera de alcance confirmado |
|---|---|---|
| Formas estables | Block, Beehive, Loaf, Boat, Tub, Ship, Pond, Barge, Canoe, Long barge, Eater 1 | — |
| Osciladores | Blinker, Toad, Beacon, Clock, Figure eight, Pulsar, Pentadecathlon | — |
| Naves | Glider, LWSS, MWSS, HWSS, Copperhead, Loafer | — |
| Matusalenes | R-pentomino, Diehard, Acorn, Thunderbird | — |
| Cañones | Gosper glider gun, Simkin glider gun | — |
| Puffers *(categoría no añadida)* | — | Puffer train, Block-laying switch engine |

### 3.2 Adición propuesta fuera del plan original: Eater 1 (Fishhook)

No estaba en la lista original, pero se propone añadirlo por ser una de las formas estables **más
típicas** que existen (usada para "comer" planeadores y otras naves pequeñas sin destruirse) y
porque el propio plan original mencionaba como construcción de interés una *"demostración de
interacción cañón + eater"* (`Planning.md:73`). En vez de construir un mecanismo especial de
"escena combinada", basta con añadir el patrón **Eater 1** al catálogo: el usuario ya puede
recrear esa demostración por su cuenta colocando dos sellos (cañón + eater) uno cerca del otro,
sin necesidad de una función nueva.

### 3.3 Explícitamente fuera de alcance (y por qué)

- **Patrones de "crecimiento infinito"** (los tres mínimos de Wikipedia: 10 células, 5×5, y el de
  una fila) — mencionados en el plan original, pero son curiosidades de investigación más que
  "construcciones típicas" (lo que el usuario ha pedido explícitamente). Se dejan fuera de esta
  ronda; son fáciles de añadir después como categoría separada si se quieren.
- **Demo combinada "cañón + eater"** — como se explica en 3.2, queda cubierta por tener ambos
  patrones por separado en la biblioteca, no requiere trabajo adicional.

### 3.4 Metodología de verificación (igual que la ya usada, sin inventar una nueva)

Cada patrón nuevo se verifica **por simulación real** contra una propiedad documentada, replicando
exactamente el patrón de `tests/test_patterns.py`:

- Osciladores nuevos (Clock, Figure eight): periodo exacto, tablero acotado (`Topology.BOUNDED`),
  igual que `test_period_is_exact`.
- Naves nuevas (Copperhead, Loafer): periodo **y** desplazamiento exactos sobre toro
  (`Topology.TORUS`), igual que `test_period_and_displacement`.
- Thunderbird (matusalén): al no ser periódico, se documentará y verificará población o
  generación de estabilización concreta (metodología de `test_r_pentomino_stabilizes_at_documented_population` /
  `test_acorn_reaches_documented_population`), con rejilla lo bastante grande para que ningún
  planeador escapado choque contra el borde antes de esa generación (se usaron hasta 3200×3200
  para Acorn; Thunderbird necesitará su propio dimensionado según cuántas generaciones tarde).
- Simkin glider gun: mismo patrón que `test_gosper_gun_emits_a_new_glider_every_period` (la
  población total debe crecer en +población_del_planeador cada P generaciones una vez
  estabilizado el mecanismo).
- **Puffers (categoría nueva, requiere un test nuevo, no una plantilla ya existente):** verificar
  que tras N generaciones (i) la "cabeza" del puffer se ha desplazado la distancia documentada, y
  (ii) ha dejado detrás el número esperado de copias de su resto/estela (still life de desecho).
  Requiere rejilla grande y acotada (`BOUNDED`, para que el puffer no le muerda la cola al
  envolver en un toro) en la dirección de avance, con margen suficiente para varios periodos.
- Eater 1: verificación de forma estable tras 1 generación (`test_unchanged_after_one_generation`,
  ya genérico por categoría) — y, si se quiere ir más allá, un test adicional específico que
  compruebe que efectivamente "absorbe" un planeador entrante sin regenerarse (demostración de su
  propiedad característica, no solo que es estable).

> **Nota de honestidad:** los periodos/velocidades citados arriba (Clock p2, Figure eight p8,
> Copperhead c/10, Loafer c/7, Simkin p120) son los que ya constaban en `Planning.md` original.
> Las coordenadas exactas de cada patrón y la confirmación empírica de esos valores son trabajo
> de la fase de implementación (como se hizo para los 23 patrones iniciales). Ya quedaron
> verificados por los tests de esta iteración.

### 3.5 Cambios de infraestructura realizados

- `patterns.py`: añadidas las siete entradas aprobadas (Eater 1, Clock, Figure eight, Copperhead,
  Loafer, Thunderbird y Simkin glider gun).
- No se añade una categoría `puffer` ni se modifica `PATTERN_CATEGORIES_ORDER`: los *puffers* y
  los patrones de crecimiento infinito quedaron fuera del alcance confirmado.
- `README.md`: actualizado el contador a **30 construcciones conocidas**.
- `tests/test_patterns.py`: catálogo fijado en 30 y ampliado con las verificaciones específicas
  de Thunderbird y Simkin, además de los tests parametrizados de las categorías existentes.

---

## 4. Mejora D — Zoom mínimo ajustado exactamente a la pantalla

### 4.1 Estado actual y bug relacionado descubierto

`Camera.MIN_CELL_SIZE = 0.5` (`camera.py:20`) es una **constante fija**, ajena al tamaño de la
rejilla o del viewport. La usan dos sitios:

1. `zoom_at()` (`camera.py:44-51`): límite inferior al hacer zoom con la rueda del ratón.
2. `fit_to_grid()` (`camera.py:61-66`): `self.cell_size = max(self.MIN_CELL_SIZE, min(size_x, size_y) * margin)`.

El punto 2 es un **bug latente** que afecta directamente a lo que se pide arreglar: si la rejilla
es mucho más grande que el viewport (p. ej. 3000×3000 en una ventana de 800×600), el tamaño de
celda necesario para que quepa entera es `min(800/3000, 600/3000) ≈ 0,20`, **por debajo** de la
constante 0.5 — por lo que hoy, tanto "Ajustar a la ventana" (botón/tecla `F`) como el zoom mínimo
de la rueda **se quedan cortos** y no llegan a mostrar la rejilla entera. Arreglar esto de forma
consistente en los dos sitios a la vez es más correcto que parchear solo uno.

### 4.2 Diseño propuesto

Sustituir la constante fija por un cálculo dinámico, dependiente de `grid_width/height` y
`viewport_width/height` (que ya son atributos de `Camera`):

```python
ABSOLUTE_MIN_CELL_SIZE = 0.01  # solo red de seguridad ante entradas degeneradas (viewport 0)

def _fit_cell_size(self, margin: float = 1.0) -> float:
    """Tamano de celda para que la rejilla ocupe 'margin' veces el viewport
    en su dimension limitante. margin=1.0 -> ajuste EXACTO (toca los bordes)."""
    if self.viewport_width <= 0 or self.viewport_height <= 0:
        return self.ABSOLUTE_MIN_CELL_SIZE
    size_x = self.viewport_width / self.grid_width
    size_y = self.viewport_height / self.grid_height
    return max(self.ABSOLUTE_MIN_CELL_SIZE, min(size_x, size_y) * margin)

@property
def min_cell_size(self) -> float:
    """Zoom minimo dinamico: el necesario para que la rejilla completa
    ocupe EXACTAMENTE el viewport (lo pedido). Se recalcula solo, siempre
    fresco frente al tamano de ventana actual."""
    return self._fit_cell_size(margin=1.0)

def zoom_at(self, screen_x: float, screen_y: float, factor: float) -> None:
    wx, wy = self.screen_to_world(screen_x, screen_y)
    new_size = min(self.MAX_CELL_SIZE, max(self.min_cell_size, self.cell_size * factor))
    self.cell_size = new_size
    self.offset_x = wx - screen_x / self.cell_size
    self.offset_y = wy - screen_y / self.cell_size

def fit_to_grid(self, margin: float = 0.96) -> None:
    self.cell_size = self._fit_cell_size(margin)
    self._center_on_grid()

def resize_viewport(self, width: int, height: int) -> None:
    self.viewport_width = width
    self.viewport_height = height
    self.cell_size = max(self.cell_size, self.min_cell_size)  # mantiene el invariante tras un resize
```

**Decisiones de alcance, explícitas para evitar sorpresas:**

- El margen cosmético `0.96` de `fit_to_grid()` (pequeño respiro visual alrededor del borde,
  usado por "Ajustar a la ventana"/`F`) **se mantiene sin cambios** — lo único que cambia es que
  ya no queda artificialmente limitado por la vieja constante de 0.5, así que ahora sí funciona
  correctamente también en rejillas enormes. Si se prefiriese que "Ajustar a la ventana" también
  fuera a ajuste exacto (`margin=1.0`, sin respiro), es un cambio de una palabra — se deja fuera
  por ahora para no alterar más comportamiento del estrictamente pedido.
- `zoom_to_actual_size()` (zoom real 1:1) **no** se acota con el nuevo `min_cell_size`: es una
  acción explícita del usuario, no el límite de la rueda interactiva, y debe poder mostrar una
  rejilla pequeña en una ventana grande sin forzarla a un tamaño artificialmente mayor.
- El re-acotado en `resize_viewport()` cierra un caso borde: si la ventana se hace más pequeña (o
  se sale de pantalla completa — ver Mejora A) después de haber llegado al zoom mínimo, el
  `cell_size` vigente podría quedar por debajo del nuevo mínimo; sin este ajuste, quedaría zoom
  "más alejado que exacto" hasta el siguiente scroll de rueda.

### 4.3 Tests afectados

| Test | Cambio |
|---|---|
| `test_zoom_clamped_to_bounds` (`test_camera.py:59`) | Cambia el `assert cam.cell_size == Camera.MIN_CELL_SIZE` final por `== pytest.approx(cam.min_cell_size)`, ya que la constante de clase desaparece. |
| *(nuevo)* `test_min_cell_size_matches_exact_fit` | Cámara con relación viewport/rejilla conocida; comprueba `cam.min_cell_size == pytest.approx(min(vw/gw, vh/gh))`. |
| *(nuevo)* `test_zoom_out_shows_whole_grid_at_min` | Zoom a factor extremo hacia fuera; comprueba que `visible_cell_rect()` cubre la rejilla entera (`x0==0, y0==0, x1>=grid_width-1, y1>=grid_height-1`) — el requisito pedido, probado directamente. |
| *(nuevo)* `test_fit_to_grid_not_capped_for_huge_grid` | Rejilla mucho mayor que el viewport (p. ej. 5000×5000 en 800×600); comprueba que `fit_to_grid(margin=1.0)` ya no queda clampado en 0.5 — prueba explícita del bug corregido. |
| *(nuevo)* `test_resize_viewport_reclamps_cell_size` | Cámara en su mínimo; `resize_viewport()` a un viewport mayor que eleva el mínimo dinámico; comprueba `cell_size >= min_cell_size` tras el resize. |

---

## 5. Impacto conjunto en tests existentes

| Archivo | Afectado por | Tipo de cambio |
|---|---|---|
| `tests/test_camera.py` | D | 1 test modificado, 4 nuevos |
| `tests/test_app.py` | A, B | Tests nuevos para `toggle_fullscreen` (estado) y para el texto de tamaño de rejilla |
| `tests/test_cli.py` | A | Test nuevo para `--fullscreen` |
| `tests/test_patterns.py` | C | `test_covers_all_expected_categories` y `test_has_a_healthy_number_of_patterns` ampliados; nuevos tests parametrizados por patrón nuevo |
| `tests/test_renderer.py` | — | Sin cambios (el renderizado ya recorta a `visible_cell_rect()`, independiente de cómo se llegó a ese `cell_size`) |

No se toca `engine.py`, `rules.py`, `rle.py`, `persistence.py`, `selection.py`, `stats.py` ni
`ui/widgets.py` en ninguna de las 4 mejoras.

---

## 6. Orden de implementación propuesto

Al ser independientes, el orden es una recomendación de eficiencia, no una dependencia real:

1. **D (zoom mínimo)** — la más aislada y con tests deterministas; corrige además un bug real.
2. **B (tamaño de matriz)** — trivial, alta visibilidad, buen "quick win".
3. **A (pantalla completa)** — requiere una pasada de verificación visual manual en Windows real
   al final (no ejecutable por CI/tests).
4. **C (más construcciones)** — la de mayor volumen (7 patrones nuevos, cada uno con su propio
   test de verificación).

## 7. Documentación a sincronizar

| Documento | A | B | C | D |
|---|---|---|---|---|
| `README.md` (características + CLI) | ✅ | — | ✅ (contador de patrones) | — |
| `Docs/Controles.md` | ✅ (sección Vista) | — | — | — |
| `HELP_LINES` en `app.py` | ✅ | — | — | — |
| `Docs/Planning.md` | — | — | ✅ anotado como completado lo implementado de §1.3 | — |

## 8. Decisiones adoptadas

- **A:** Se implementan `F11`, el botón del panel y `--fullscreen`; no se persiste el estado entre
  ejecuciones.
- **C:** Se dejan fuera crecimiento infinito y *puffers*. Se implementan Clock, Figure eight,
  Copperhead, Loafer, Thunderbird, Simkin gun y Eater 1.
- **D:** "Ajustar a la ventana" (`F`) conserva el margen cosmético del 4 %; el límite mínimo
  interactivo de la rueda es el que ajusta exactamente la matriz al viewport.
