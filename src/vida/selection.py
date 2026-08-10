"""Estado de edicion interactiva: herramienta activa, seleccion rectangular,
portapapeles y sello (patron 'en la mano' listo para colocar)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

import numpy as np


class Tool(Enum):
    PAINT = auto()
    ERASE = auto()
    SELECT = auto()


@dataclass
class Selection:
    """Seleccion rectangular activa, en coordenadas de celda."""

    x0: int = 0
    y0: int = 0
    x1: int = 0
    y1: int = 0
    active: bool = False

    def start(self, x: int, y: int) -> None:
        self.x0 = self.x1 = x
        self.y0 = self.y1 = y
        self.active = True

    def update(self, x: int, y: int) -> None:
        self.x1 = x
        self.y1 = y

    def clear(self) -> None:
        self.active = False

    def normalized(self) -> tuple[int, int, int, int]:
        """(x0, y0, x1, y1) con x0<=x1, y0<=y1 y extremo final EXCLUSIVO
        (compatible con LifeEngine.extract/clear_region)."""
        x0, x1 = sorted((self.x0, self.x1))
        y0, y1 = sorted((self.y0, self.y1))
        return x0, y0, x1 + 1, y1 + 1

    @property
    def is_empty(self) -> bool:
        if not self.active:
            return True
        x0, y0, x1, y1 = self.normalized()
        return x1 <= x0 or y1 <= y0


@dataclass
class StampState:
    """Patron actualmente 'en la mano', listo para colocar con un clic."""

    grid: np.ndarray | None = None
    name: str = ""
    x: int = 0
    y: int = 0

    @property
    def active(self) -> bool:
        return self.grid is not None

    def set_pattern(self, grid: np.ndarray, name: str = "") -> None:
        self.grid = grid.astype(np.uint8).copy()
        self.name = name

    def clear(self) -> None:
        self.grid = None
        self.name = ""

    def move_to(self, x: int, y: int) -> None:
        self.x, self.y = x, y

    def rotate(self) -> None:
        if self.grid is not None:
            self.grid = np.ascontiguousarray(np.rot90(self.grid, k=-1))

    def flip_horizontal(self) -> None:
        if self.grid is not None:
            self.grid = np.ascontiguousarray(np.fliplr(self.grid))

    def flip_vertical(self) -> None:
        if self.grid is not None:
            self.grid = np.ascontiguousarray(np.flipud(self.grid))


@dataclass
class Clipboard:
    grid: np.ndarray | None = None

    def set(self, grid: np.ndarray) -> None:
        self.grid = grid.astype(np.uint8).copy()

    def clear(self) -> None:
        self.grid = None

    @property
    def has_content(self) -> bool:
        return self.grid is not None and self.grid.size > 0 and bool(self.grid.any())


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """Celdas que atraviesa el segmento (x0,y0)-(x1,y1), sin huecos. Se usa
    para rellenar el trazo cuando el raton se arrastra rapido entre dos
    eventos MOUSEMOTION consecutivos."""
    points: list[tuple[int, int]] = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy
    return points
