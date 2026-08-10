"""Motor de simulacion del automata celular.

Representa la rejilla como un ``numpy.ndarray`` de ``uint8`` y aplica la regla
mediante una tabla de consulta (LUT) vectorizada — ver ``rules.py``.

Puntos de diseno:

- **Doble buffer implicito**: cada generacion se calcula entera antes de
  sustituir la rejilla, tal y como exigen las reglas (los nacimientos y
  muertes son simultaneos).
- **Topologia conmutable**: ``TORUS`` (bordes que se enlazan, recomendado por
  la literatura para evitar efectos de borde) o ``BOUNDED`` (exterior muerto).
- **Optimizacion por caja envolvente**: si las celulas vivas ocupan una
  fraccion pequena de la rejilla y no tocan el borde, solo se recalcula esa
  region (mas 1 celda de margen, ya que la informacion viaja como maximo 1
  celda por generacion). Si toca el borde en modo TORUS se recurre al calculo
  completo para no romper el enlace con el lado opuesto.
- **Edad/estela sin coste por generacion**: en vez de incrementar un contador
  de edad en cada paso (lo que obligaria a recorrer toda la rejilla aunque se
  use la optimizacion por caja), se guarda la generacion de nacimiento y de
  muerte de cada celda. La edad y la intensidad de la estela se derivan de
  esos dos arrays *unicamente cuando el renderer los necesita* (una vez por
  fotograma, no una vez por generacion).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from vida.rules import KNOWN_RULES, Rule


class Topology(Enum):
    TORUS = "torus"
    BOUNDED = "bounded"


# Generacion "en el infinito": las celdas que nunca han nacido/muerto llevan
# esta marca de modo que edad/estela salgan naturalmente a 0 sin casos
# especiales en el renderer.
_SENTINEL = -1_000_000

# Umbral de densidad de celulas vivas por debajo del cual compensa usar la
# optimizacion de caja envolvente en vez de recalcular toda la rejilla.
_BBOX_DENSITY_THRESHOLD = 0.40

_UNDO_LIMIT = 100


@dataclass
class StepStats:
    """Resultado de aplicar una generacion."""

    births: int = 0
    deaths: int = 0
    used_bbox: bool = False


class LifeEngine:
    """Estado y logica de un tablero del Juego de la Vida."""

    def __init__(
        self,
        width: int,
        height: int,
        rule: Rule | None = None,
        topology: Topology = Topology.TORUS,
    ) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("width y height deben ser positivos")
        self.width = width
        self.height = height
        self.topology = topology
        self.rule = rule or KNOWN_RULES["life"]
        self._lut = self.rule.build_lut()

        self.grid = np.zeros((height, width), dtype=np.uint8)
        self.birth_gen = np.full((height, width), _SENTINEL, dtype=np.int64)
        self.death_gen = np.full((height, width), _SENTINEL, dtype=np.int64)

        self.generation = 0
        self.last_stats = StepStats()

        self._seed = self.grid.copy()
        self._undo_stack: deque[tuple[bytes, int]] = deque(maxlen=_UNDO_LIMIT)
        self._redo_stack: deque[tuple[bytes, int]] = deque(maxlen=_UNDO_LIMIT)

    # ------------------------------------------------------------------
    # Propiedades derivadas
    # ------------------------------------------------------------------
    @property
    def population(self) -> int:
        return int(np.count_nonzero(self.grid))

    @property
    def alive_fraction(self) -> float:
        return self.population / (self.width * self.height)

    def age_array(self) -> np.ndarray:
        """Generaciones que lleva viva cada celda (0 en las celdas muertas)."""
        age = self.generation - self.birth_gen
        age = np.where(self.grid == 1, np.clip(age, 0, None), 0)
        return age

    def trail_intensity(self, decay: float = 0.90, cutoff: int = 200) -> np.ndarray:
        """Intensidad 0..1 de la 'estela' de celdas recien muertas."""
        age_since_death = np.clip(self.generation - self.death_gen, 0, cutoff)
        intensity = np.power(decay, age_since_death, dtype=np.float32)
        return np.where(self.grid == 0, intensity, 0.0).astype(np.float32)

    # ------------------------------------------------------------------
    # Simulacion
    # ------------------------------------------------------------------
    def step(self, times: int = 1) -> StepStats:
        """Avanza ``times`` generaciones. Devuelve las estadisticas del ultimo paso."""
        stats = StepStats()
        for _ in range(max(1, times)):
            stats = self._step_once()
        self.last_stats = stats
        return stats

    def _step_once(self) -> StepStats:
        bbox = self._alive_bbox()
        new_generation = self.generation + 1

        if bbox is None:
            # Rejilla completamente vacia: nada que hacer.
            self.generation = new_generation
            return StepStats(0, 0, used_bbox=False)

        r0, r1, c0, c1 = bbox
        alive_area = (r1 - r0 + 1) * (c1 - c0 + 1)
        total_area = self.height * self.width
        touches_edge = r0 == 0 or c0 == 0 or r1 == self.height - 1 or c1 == self.width - 1
        safe_for_torus = self.topology is Topology.BOUNDED or not touches_edge
        use_bbox = safe_for_torus and alive_area < _BBOX_DENSITY_THRESHOLD * total_area

        if use_bbox:
            births, deaths = self._step_region(r0, r1, c0, c1, new_generation)
        else:
            births, deaths = self._step_full(new_generation)

        self.generation = new_generation
        return StepStats(births, deaths, used_bbox=use_bbox)

    def _alive_bbox(self) -> tuple[int, int, int, int] | None:
        rows = np.any(self.grid, axis=1)
        if not rows.any():
            return None
        cols = np.any(self.grid, axis=0)
        r0 = int(np.argmax(rows))
        r1 = self.height - 1 - int(np.argmax(rows[::-1]))
        c0 = int(np.argmax(cols))
        c1 = self.width - 1 - int(np.argmax(cols[::-1]))
        return r0, r1, c0, c1

    @staticmethod
    def _count_neighbors(padded: np.ndarray) -> np.ndarray:
        return (
            padded[:-2, :-2] + padded[:-2, 1:-1] + padded[:-2, 2:]
            + padded[1:-1, :-2] + padded[1:-1, 2:]
            + padded[2:, :-2] + padded[2:, 1:-1] + padded[2:, 2:]
        )

    def _step_full(self, new_generation: int) -> tuple[int, int]:
        mode = "wrap" if self.topology is Topology.TORUS else "constant"
        padded = np.pad(self.grid, 1, mode=mode)
        neighbors = self._count_neighbors(padded)
        idx = self.grid * 9 + neighbors
        new_grid = self._lut[idx]
        births, deaths = self._apply_transition(
            0, self.height - 1, 0, self.width - 1, self.grid, new_grid, new_generation
        )
        self.grid = new_grid
        return births, deaths

    def _step_region(
        self, r0: int, r1: int, c0: int, c1: int, new_generation: int
    ) -> tuple[int, int]:
        pr0, pr1 = max(r0 - 1, 0), min(r1 + 1, self.height - 1)
        pc0, pc1 = max(c0 - 1, 0), min(c1 + 1, self.width - 1)
        region = self.grid[pr0 : pr1 + 1, pc0 : pc1 + 1]
        padded = np.pad(region, 1, mode="constant", constant_values=0)
        neighbors = self._count_neighbors(padded)
        idx = region * 9 + neighbors
        new_region = self._lut[idx]
        births, deaths = self._apply_transition(
            pr0, pr1, pc0, pc1, region, new_region, new_generation
        )
        self.grid[pr0 : pr1 + 1, pc0 : pc1 + 1] = new_region
        return births, deaths

    def _apply_transition(
        self,
        r0: int,
        r1: int,
        c0: int,
        c1: int,
        old_region: np.ndarray,
        new_region: np.ndarray,
        new_generation: int,
    ) -> tuple[int, int]:
        newly_alive = (new_region == 1) & (old_region == 0)
        newly_dead = (new_region == 0) & (old_region == 1)

        bg_slice = self.birth_gen[r0 : r1 + 1, c0 : c1 + 1]
        dg_slice = self.death_gen[r0 : r1 + 1, c0 : c1 + 1]
        bg_slice[newly_alive] = new_generation
        dg_slice[newly_dead] = new_generation
        # (las slices de arrays 2D de numpy son vistas: la asignacion booleana
        # ya modifica el array original in-place, no hace falta reasignar)

        return int(np.count_nonzero(newly_alive)), int(np.count_nonzero(newly_dead))

    # ------------------------------------------------------------------
    # Edicion
    # ------------------------------------------------------------------
    def _mark_edit(self) -> None:
        """Si aun no ha arrancado la simulacion, la edicion pasa a formar
        parte de la semilla (lo que 'Resetear' restaurara)."""
        if self.generation == 0:
            self._seed = self.grid.copy()

    def set_cell(self, x: int, y: int, alive: bool) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            new_val = np.uint8(1 if alive else 0)
            if self.grid[y, x] != new_val:
                self.grid[y, x] = new_val
                if alive:
                    self.birth_gen[y, x] = self.generation
                else:
                    self.death_gen[y, x] = self.generation
            self._mark_edit()

    def set_cells(self, coords: list[tuple[int, int]], alive: bool) -> None:
        """Pinta/borra varias celdas a la vez (p.ej. un trazo de arrastre)."""
        if not coords:
            return
        xs = np.array([c[0] for c in coords])
        ys = np.array([c[1] for c in coords])
        mask = (xs >= 0) & (xs < self.width) & (ys >= 0) & (ys < self.height)
        xs, ys = xs[mask], ys[mask]
        if xs.size == 0:
            return
        new_val = np.uint8(1 if alive else 0)
        changed = self.grid[ys, xs] != new_val
        self.grid[ys, xs] = new_val
        if alive:
            self.birth_gen[ys[changed], xs[changed]] = self.generation
        else:
            self.death_gen[ys[changed], xs[changed]] = self.generation
        self._mark_edit()

    def toggle_cell(self, x: int, y: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.set_cell(x, y, not bool(self.grid[y, x]))

    def clear(self) -> None:
        self.push_undo()
        self.grid.fill(0)
        self.birth_gen.fill(_SENTINEL)
        self.death_gen.fill(_SENTINEL)
        self.generation = 0
        self.last_stats = StepStats()
        self._seed = self.grid.copy()

    def reset(self) -> None:
        """Restaura la semilla (estado guardado al iniciar/cargar la simulacion)."""
        self.push_undo()
        self.grid = self._seed.copy()
        self.birth_gen.fill(_SENTINEL)
        self.death_gen.fill(_SENTINEL)
        self.birth_gen[self.grid == 1] = 0
        self.generation = 0
        self.last_stats = StepStats()

    def randomize(self, density: float = 0.3, seed: int | None = None) -> None:
        self.push_undo()
        rng = np.random.default_rng(seed)
        self.grid = (rng.random((self.height, self.width)) < density).astype(np.uint8)
        self.birth_gen.fill(_SENTINEL)
        self.death_gen.fill(_SENTINEL)
        self.birth_gen[self.grid == 1] = 0
        self.generation = 0
        self.last_stats = StepStats()
        self._seed = self.grid.copy()

    def stamp(self, pattern: np.ndarray, x: int, y: int, mode: str = "or") -> None:
        """Coloca un patron (array 2D de 0/1) con su esquina superior
        izquierda en (x, y). Se recorta silenciosamente si sale de la
        rejilla. ``mode``: 'or' (superpone vivas) o 'replace' (sustituye
        tambien con celdas muertas, borrando lo que hubiera debajo)."""
        ph, pw = pattern.shape
        gx0, gy0 = max(x, 0), max(y, 0)
        gx1, gy1 = min(x + pw, self.width), min(y + ph, self.height)
        if gx0 >= gx1 or gy0 >= gy1:
            return
        px0, py0 = gx0 - x, gy0 - y
        px1, py1 = px0 + (gx1 - gx0), py0 + (gy1 - gy0)
        sub_pattern = pattern[py0:py1, px0:px1].astype(np.uint8)

        target = self.grid[gy0:gy1, gx0:gx1]
        if mode == "replace":
            new_val = sub_pattern
        else:
            new_val = np.maximum(target, sub_pattern)
        changed_alive = (new_val == 1) & (target == 0)
        changed_dead = (new_val == 0) & (target == 1)
        self.birth_gen[gy0:gy1, gx0:gx1][changed_alive] = self.generation
        self.death_gen[gy0:gy1, gx0:gx1][changed_dead] = self.generation
        self.grid[gy0:gy1, gx0:gx1] = new_val
        self._mark_edit()

    def extract(self, x0: int, y0: int, x1: int, y1: int) -> np.ndarray:
        """Devuelve una copia (0/1 uint8) de la region [x0,x1) x [y0,y1)."""
        x0c, y0c = max(x0, 0), max(y0, 0)
        x1c, y1c = min(x1, self.width), min(y1, self.height)
        if x0c >= x1c or y0c >= y1c:
            return np.zeros((0, 0), dtype=np.uint8)
        return self.grid[y0c:y1c, x0c:x1c].copy()

    def clear_region(self, x0: int, y0: int, x1: int, y1: int) -> None:
        x0c, y0c = max(x0, 0), max(y0, 0)
        x1c, y1c = min(x1, self.width), min(y1, self.height)
        if x0c >= x1c or y0c >= y1c:
            return
        self.push_undo()
        region = self.grid[y0c:y1c, x0c:x1c]
        self.death_gen[y0c:y1c, x0c:x1c][region == 1] = self.generation
        region.fill(0)
        self._mark_edit()

    # ------------------------------------------------------------------
    # Configuracion
    # ------------------------------------------------------------------
    def set_rule(self, rule: Rule) -> None:
        self.rule = rule
        self._lut = rule.build_lut()

    def set_topology(self, topology: Topology) -> None:
        self.topology = topology

    def load_grid(self, new_grid: np.ndarray, at_x: int = 0, at_y: int = 0) -> None:
        """Reemplaza el tablero entero (recorta si el patron es mayor que la
        rejilla) y lo marca como nueva semilla."""
        self.push_undo()
        self.grid.fill(0)
        h, w = new_grid.shape
        gx1, gy1 = min(at_x + w, self.width), min(at_y + h, self.height)
        gx0, gy0 = max(at_x, 0), max(at_y, 0)
        if gx0 < gx1 and gy0 < gy1:
            self.grid[gy0:gy1, gx0:gx1] = new_grid[
                gy0 - at_y : gy1 - at_y, gx0 - at_x : gx1 - at_x
            ]
        self.birth_gen.fill(_SENTINEL)
        self.death_gen.fill(_SENTINEL)
        self.birth_gen[self.grid == 1] = 0
        self.generation = 0
        self.last_stats = StepStats()
        self._seed = self.grid.copy()

    # ------------------------------------------------------------------
    # Deshacer / rehacer (solo para ediciones, no para pasos de simulacion)
    # ------------------------------------------------------------------
    def push_undo(self) -> None:
        self._undo_stack.append((np.packbits(self.grid).tobytes(), self.generation))
        self._redo_stack.clear()

    def _unpack(self, data: bytes) -> np.ndarray:
        bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
        return bits[: self.width * self.height].reshape(self.height, self.width).astype(np.uint8)

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self._redo_stack.append((np.packbits(self.grid).tobytes(), self.generation))
        data, generation = self._undo_stack.pop()
        self.grid = self._unpack(data)
        self.generation = generation
        self.birth_gen.fill(_SENTINEL)
        self.death_gen.fill(_SENTINEL)
        self.birth_gen[self.grid == 1] = max(generation - 1, 0)
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        self._undo_stack.append((np.packbits(self.grid).tobytes(), self.generation))
        data, generation = self._redo_stack.pop()
        self.grid = self._unpack(data)
        self.generation = generation
        self.birth_gen.fill(_SENTINEL)
        self.death_gen.fill(_SENTINEL)
        self.birth_gen[self.grid == 1] = max(generation - 1, 0)
        return True

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)
