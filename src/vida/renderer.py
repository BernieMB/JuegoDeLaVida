"""Renderizado de la rejilla: paleta vectorizada (NumPy) + blit sobre pygame.

En vez de dibujar cada celda con ``pygame.draw.rect`` (inviable con decenas
de miles de celdas), se construye un array RGB con NumPy y se vuelca de una
vez sobre una superficie "logica" (1 pixel = 1 celda visible), que luego se
escala al tamano real del viewport. Solo se procesa la region visible segun
la camara, no la rejilla entera.
"""

from __future__ import annotations

import numpy as np
import pygame

from vida.camera import Camera
from vida.engine import LifeEngine

BACKGROUND = (16, 16, 22)
CLASSIC_ALIVE = (235, 235, 240)
AGE_YOUNG = (255, 244, 214)
AGE_OLD = (70, 130, 220)
TRAIL_COLOR = (180, 60, 50)
GRID_LINE_COLOR = (40, 40, 52)

AGE_COLOR_CAP = 40
TRAIL_DECAY = 0.90
TRAIL_CUTOFF = 200
TRAIL_VISIBLE_THRESHOLD = 0.004

_BACKGROUND_F = np.array(BACKGROUND, dtype=np.float32)
_CLASSIC_ALIVE_F = np.array(CLASSIC_ALIVE, dtype=np.float32)
_AGE_YOUNG_F = np.array(AGE_YOUNG, dtype=np.float32)
_AGE_OLD_F = np.array(AGE_OLD, dtype=np.float32)
_TRAIL_COLOR_F = np.array(TRAIL_COLOR, dtype=np.float32)


class ColorMode:
    CLASSIC = "classic"
    AGE = "age"

    ALL = (CLASSIC, AGE)


def compute_rgb(grid_sub: np.ndarray, mode: str, age_sub: np.ndarray | None = None,
                 trail_sub: np.ndarray | None = None) -> np.ndarray:
    """Convierte una sub-rejilla 0/1 (+ opcionalmente edad/estela) en un
    array RGB uint8 de forma (alto, ancho, 3)."""
    h, w = grid_sub.shape
    rgb = np.broadcast_to(_BACKGROUND_F, (h, w, 3)).copy()
    alive = (grid_sub == 1)[..., None]

    if mode == ColorMode.AGE and age_sub is not None and trail_sub is not None:
        strength = trail_sub[..., None]
        trail_rgb = _BACKGROUND_F * (1 - strength) + _TRAIL_COLOR_F * strength
        rgb = np.where(strength > TRAIL_VISIBLE_THRESHOLD, trail_rgb, rgb)

        t = np.clip(age_sub / AGE_COLOR_CAP, 0.0, 1.0)[..., None]
        age_rgb = _AGE_YOUNG_F * (1 - t) + _AGE_OLD_F * t
        rgb = np.where(alive, age_rgb, rgb)
    else:
        rgb = np.where(alive, _CLASSIC_ALIVE_F, rgb)

    return np.clip(rgb, 0, 255).astype(np.uint8)


def age_and_trail_for_region(engine: LifeEngine, x0: int, y0: int, x1: int, y1: int
                              ) -> tuple[np.ndarray, np.ndarray]:
    """Deriva edad y estela SOLO para la sub-region visible, a partir de las
    generaciones de nacimiento/muerte del motor (sin coste por generacion)."""
    grid_sub = engine.grid[y0:y1, x0:x1]
    age_sub = np.clip(engine.generation - engine.birth_gen[y0:y1, x0:x1], 0, None)
    age_sub = np.where(grid_sub == 1, age_sub, 0)
    death_delta = np.clip(engine.generation - engine.death_gen[y0:y1, x0:x1], 0, TRAIL_CUTOFF)
    trail_sub = np.where(grid_sub == 0,
                          np.power(np.float32(TRAIL_DECAY), death_delta.astype(np.float32)),
                          np.float32(0.0)).astype(np.float32)
    return age_sub, trail_sub


class Renderer:
    """Mantiene una superficie 'logica' reutilizable (1 px/celda) para
    evitar reasignar memoria en cada fotograma."""

    def __init__(self, mode: str = ColorMode.CLASSIC) -> None:
        self.mode = mode
        self._logical_surface: pygame.Surface | None = None
        self._logical_size: tuple[int, int] = (0, 0)

    def toggle_mode(self) -> str:
        self.mode = ColorMode.AGE if self.mode == ColorMode.CLASSIC else ColorMode.CLASSIC
        return self.mode

    def set_mode(self, mode: str) -> None:
        if mode not in ColorMode.ALL:
            raise ValueError(f"Modo de color desconocido: {mode!r}")
        self.mode = mode

    def _logical(self, w: int, h: int) -> pygame.Surface:
        if self._logical_surface is None or self._logical_size != (w, h):
            self._logical_surface = pygame.Surface((w, h))
            self._logical_size = (w, h)
        return self._logical_surface

    def render(self, target: pygame.Surface, viewport: pygame.Rect,
               engine: LifeEngine, camera: Camera) -> None:
        target.fill(BACKGROUND, viewport)
        x0, y0, x1, y1 = camera.visible_cell_rect()
        if x1 <= x0 or y1 <= y0:
            return

        grid_sub = engine.grid[y0:y1, x0:x1]
        if self.mode == ColorMode.AGE:
            age_sub, trail_sub = age_and_trail_for_region(engine, x0, y0, x1, y1)
        else:
            age_sub = trail_sub = None
        rgb = compute_rgb(grid_sub, self.mode, age_sub, trail_sub)

        w, h = x1 - x0, y1 - y0
        logical = self._logical(w, h)
        pygame.surfarray.blit_array(logical, rgb.transpose(1, 0, 2))

        screen_x, screen_y = camera.world_to_screen(x0, y0)
        dest_w = max(1, round(w * camera.cell_size))
        dest_h = max(1, round(h * camera.cell_size))
        scaled = pygame.transform.scale(logical, (dest_w, dest_h))
        target.blit(scaled, (viewport.x + round(screen_x), viewport.y + round(screen_y)))

        if camera.show_grid_lines:
            self._draw_grid_lines(target, viewport, camera, x0, y0, x1, y1)

    @staticmethod
    def _draw_grid_lines(target: pygame.Surface, viewport: pygame.Rect,
                          camera: Camera, x0: int, y0: int, x1: int, y1: int) -> None:
        top, bottom = viewport.y, viewport.y + viewport.height
        left, right = viewport.x, viewport.x + viewport.width
        for gx in range(x0, x1 + 1):
            sx, _ = camera.world_to_screen(gx, 0)
            px = viewport.x + round(sx)
            if left <= px <= right:
                pygame.draw.line(target, GRID_LINE_COLOR, (px, top), (px, bottom))
        for gy in range(y0, y1 + 1):
            _, sy = camera.world_to_screen(0, gy)
            py = viewport.y + round(sy)
            if top <= py <= bottom:
                pygame.draw.line(target, GRID_LINE_COLOR, (left, py), (right, py))


# ---------------------------------------------------------------------------
# Overlays (seleccion, previsualizacion de sellos, resaltado de celda)
# ---------------------------------------------------------------------------

def draw_world_rect_outline(target: pygame.Surface, viewport: pygame.Rect, camera: Camera,
                             x0: int, y0: int, x1: int, y1: int,
                             color: tuple[int, int, int], width: int = 2) -> None:
    sx0, sy0 = camera.world_to_screen(x0, y0)
    sx1, sy1 = camera.world_to_screen(x1, y1)
    rect = pygame.Rect(
        viewport.x + round(sx0), viewport.y + round(sy0),
        max(1, round(sx1 - sx0)), max(1, round(sy1 - sy0)),
    )
    pygame.draw.rect(target, color, rect, width)


def draw_stamp_preview(target: pygame.Surface, viewport: pygame.Rect, camera: Camera,
                        pattern_grid: np.ndarray, x0: int, y0: int,
                        color: tuple[int, int, int] = (120, 200, 255)) -> None:
    ph, pw = pattern_grid.shape
    cell_px = max(1, round(camera.cell_size))
    overlay = pygame.Surface((cell_px, cell_px), pygame.SRCALPHA)
    overlay.fill((*color, 130))
    for ry, rx in np.argwhere(pattern_grid == 1):
        sx, sy = camera.world_to_screen(x0 + int(rx), y0 + int(ry))
        target.blit(overlay, (viewport.x + round(sx), viewport.y + round(sy)))
    draw_world_rect_outline(target, viewport, camera, x0, y0, x0 + pw, y0 + ph, color, width=1)


def draw_cell_highlight(target: pygame.Surface, viewport: pygame.Rect, camera: Camera,
                         x: int, y: int, color: tuple[int, int, int] = (255, 255, 255)) -> None:
    draw_world_rect_outline(target, viewport, camera, x, y, x + 1, y + 1, color, width=1)


def render_full_rgb(engine: LifeEngine, mode: str = ColorMode.CLASSIC) -> np.ndarray:
    """RGB de la rejilla ENTERA (para exportar a PNG), independiente de camara."""
    if mode == ColorMode.AGE:
        age_sub, trail_sub = age_and_trail_for_region(engine, 0, 0, engine.width, engine.height)
    else:
        age_sub = trail_sub = None
    return compute_rgb(engine.grid, mode, age_sub, trail_sub)


def export_png(engine: LifeEngine, path: str, cell_px: int = 4, mode: str = ColorMode.CLASSIC) -> None:
    """Exporta el estado actual de la rejilla como imagen PNG."""
    rgb = render_full_rgb(engine, mode)
    surface = pygame.Surface((engine.width, engine.height))
    pygame.surfarray.blit_array(surface, rgb.transpose(1, 0, 2))
    if cell_px != 1:
        surface = pygame.transform.scale(
            surface, (engine.width * cell_px, engine.height * cell_px)
        )
    pygame.image.save(surface, path)
