"""Estadisticas de la simulacion: deteccion de ciclos (osciladores/still
lifes), historial de poblacion para la grafica de tendencia (sparkline) y
medicion de la velocidad REAL (generaciones/segundo efectivas)."""

from __future__ import annotations

import hashlib
import time
from collections import deque

from vida.engine import LifeEngine


class CycleStatus:
    NONE = "none"
    STILL = "still"
    OSCILLATING = "oscillating"


def _hash_grid(engine: LifeEngine) -> bytes:
    return hashlib.blake2b(engine.grid.tobytes(), digest_size=8).digest()


class CycleDetector:
    """Detecta si el tablero ha entrado en un ciclo (still life u
    oscilador) comparando el hash del estado actual contra una ventana
    reciente de estados anteriores.

    Debe alimentarse con ``observe()`` tras CADA generacion simulada (no
    una vez por fotograma): si se simula mas de una generacion por frame
    (velocidades altas) y solo se muestreara la ultima, un oscilador de
    periodo corto podria pasar desapercibido."""

    def __init__(self, window: int = 256):
        self.window = window
        self._history: deque[tuple[int, bytes]] = deque(maxlen=window)
        self.status = CycleStatus.NONE
        self.period: int | None = None

    def reset(self) -> None:
        self._history.clear()
        self.status = CycleStatus.NONE
        self.period = None

    def observe(self, engine: LifeEngine) -> bool:
        """Registra el estado actual. Devuelve True solo en el momento en
        que se detecta la transicion de 'sin ciclo' a 'ciclo' (util para
        disparar un auto-pausado o un aviso una unica vez)."""
        state_hash = _hash_grid(engine)
        generation = engine.generation
        was_cyclic = self.status != CycleStatus.NONE

        for past_gen, past_hash in reversed(self._history):
            if past_hash == state_hash:
                period = generation - past_gen
                if period > 0:
                    self.period = period
                    self.status = CycleStatus.STILL if period == 1 else CycleStatus.OSCILLATING
                    self._history.append((generation, state_hash))
                    return not was_cyclic
                break

        self.status = CycleStatus.NONE
        self.period = None
        self._history.append((generation, state_hash))
        return False

    @property
    def message(self) -> str | None:
        if self.status == CycleStatus.STILL:
            return "Estable (still life)"
        if self.status == CycleStatus.OSCILLATING:
            return f"Oscilador de periodo {self.period}"
        return None


class PopulationHistory:
    """Historial de poblacion muestreado una vez por FOTOGRAMA (no por
    generacion), para que la grafica de tendencia cubra una ventana de
    tiempo razonable sin importar la velocidad de simulacion."""

    def __init__(self, max_samples: int = 300):
        self.max_samples = max_samples
        self.samples: deque[int] = deque(maxlen=max_samples)

    def reset(self) -> None:
        self.samples.clear()

    def sample(self, engine: LifeEngine) -> None:
        self.samples.append(engine.population)

    @property
    def min_value(self) -> int:
        return min(self.samples) if self.samples else 0

    @property
    def max_value(self) -> int:
        return max(self.samples) if self.samples else 0

    def values(self) -> list[int]:
        return list(self.samples)


class RealSpeedMeter:
    """Mide las generaciones/segundo REALES (no el objetivo de velocidad
    configurado), promediando sobre una ventana deslizante."""

    def __init__(self, window_seconds: float = 0.5):
        self.window_seconds = window_seconds
        self.value = 0.0
        self._window_start_time = time.perf_counter()
        self._window_start_generation = 0

    def reset(self, generation: int = 0) -> None:
        self._window_start_time = time.perf_counter()
        self._window_start_generation = generation
        self.value = 0.0

    def update(self, generation: int) -> None:
        now = time.perf_counter()
        elapsed = now - self._window_start_time
        if elapsed >= self.window_seconds:
            delta = generation - self._window_start_generation
            self.value = delta / elapsed if elapsed > 0 else 0.0
            self._window_start_time = now
            self._window_start_generation = generation
