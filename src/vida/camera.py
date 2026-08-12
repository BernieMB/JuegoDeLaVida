"""Camara: transforma entre coordenadas del mundo (celda de la rejilla) y
coordenadas de pantalla (pixeles), con zoom centrado en el cursor y paneo."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Camera:
    grid_width: int
    grid_height: int
    viewport_width: int
    viewport_height: int
    cell_size: float = 8.0
    offset_x: float = 0.0  # coordenada de mundo mostrada en el borde izquierdo
    offset_y: float = 0.0  # coordenada de mundo mostrada en el borde superior

    # Lower bound used only as a safety net.  The interactive minimum is
    # calculated from the grid and viewport dimensions by min_cell_size.
    ABSOLUTE_MIN_CELL_SIZE = 0.01
    MIN_CELL_SIZE = ABSOLUTE_MIN_CELL_SIZE  # compatibility alias
    MAX_CELL_SIZE = 80.0
    GRID_LINES_MIN_CELL_SIZE = 5.0

    def resize_viewport(self, width: int, height: int) -> None:
        was_at_min = self.cell_size <= self.min_cell_size + 1e-9
        self.viewport_width = width
        self.viewport_height = height
        if was_at_min or self.cell_size < self.min_cell_size:
            self.cell_size = self.min_cell_size
            self._center_on_grid()

    # ------------------------------------------------------------------
    # Transformaciones
    # ------------------------------------------------------------------
    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        return (wx - self.offset_x) * self.cell_size, (wy - self.offset_y) * self.cell_size

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return sx / self.cell_size + self.offset_x, sy / self.cell_size + self.offset_y

    def screen_to_cell(self, sx: float, sy: float) -> tuple[int, int]:
        wx, wy = self.screen_to_world(sx, sy)
        return int(math.floor(wx)), int(math.floor(wy))

    # ------------------------------------------------------------------
    # Zoom / paneo
    # ------------------------------------------------------------------
    def zoom_at(self, screen_x: float, screen_y: float, factor: float) -> None:
        """Aplica un factor de zoom manteniendo fijo el punto del mundo bajo
        el cursor (zoom centrado en el raton, no en la esquina)."""
        wx, wy = self.screen_to_world(screen_x, screen_y)
        upper_bound = max(self.MAX_CELL_SIZE, self.min_cell_size)
        requested_size = self.cell_size * factor
        if requested_size <= self.min_cell_size:
            self.cell_size = self.min_cell_size
            self._center_on_grid()
            return
        new_size = min(upper_bound, requested_size)
        self.cell_size = new_size
        self.offset_x = wx - screen_x / self.cell_size
        self.offset_y = wy - screen_y / self.cell_size

    def pan_pixels(self, dx: float, dy: float) -> None:
        self.offset_x -= dx / self.cell_size
        self.offset_y -= dy / self.cell_size

    def pan_cells(self, dx: float, dy: float) -> None:
        self.offset_x += dx
        self.offset_y += dy

    def fit_to_grid(self, margin: float = 0.96) -> None:
        """Ajusta el zoom para que la rejilla entera quepa en el viewport."""
        self.cell_size = self._fit_cell_size(margin)
        self._center_on_grid()

    def zoom_to_actual_size(self) -> None:
        """Un pixel de pantalla por celda (zoom 1:1)."""
        self.cell_size = max(self.ABSOLUTE_MIN_CELL_SIZE, min(1.0, self.MAX_CELL_SIZE))
        self._center_on_grid()

    def _fit_cell_size(self, margin: float = 1.0) -> float:
        if self.grid_width <= 0 or self.grid_height <= 0:
            return self.ABSOLUTE_MIN_CELL_SIZE
        size_x = self.viewport_width / self.grid_width
        size_y = self.viewport_height / self.grid_height
        return max(self.ABSOLUTE_MIN_CELL_SIZE, min(size_x, size_y) * margin)

    @property
    def min_cell_size(self) -> float:
        """Zoom minimo que hace que la rejilla completa toque el viewport."""
        return self._fit_cell_size()

    def _center_on_grid(self) -> None:
        self.offset_x = (self.grid_width - self.viewport_width / self.cell_size) / 2
        self.offset_y = (self.grid_height - self.viewport_height / self.cell_size) / 2

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def visible_cell_rect(self) -> tuple[int, int, int, int]:
        """Rango de celdas (x0, y0, x1, y1) visible, recortado a la rejilla."""
        x0 = max(0, int(math.floor(self.offset_x)))
        y0 = max(0, int(math.floor(self.offset_y)))
        x1 = min(self.grid_width, int(math.ceil(self.offset_x + self.viewport_width / self.cell_size)) + 1)
        y1 = min(self.grid_height, int(math.ceil(self.offset_y + self.viewport_height / self.cell_size)) + 1)
        x1 = max(x1, x0)
        y1 = max(y1, y0)
        return x0, y0, x1, y1

    @property
    def show_grid_lines(self) -> bool:
        return self.cell_size >= self.GRID_LINES_MIN_CELL_SIZE
