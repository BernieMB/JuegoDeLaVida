"""Tema visual: colores y fuentes compartidos por los widgets."""

from __future__ import annotations

import pygame

# Cadena de fuentes de sistema con buena cobertura multiplataforma (Windows,
# macOS, Linux). Se probo empiricamente que la fuente interna de pygame
# (``pygame.font.Font(None, size)``) NO dibuja el punto de la 'i' minuscula
# a tamanos pequenos (p.ej. "Copiar" se lee "Coplar", "Edicion" se lee
# "Edlclon") -- un problema serio para un proyecto en castellano. Usar una
# fuente de sistema real evita ese defecto.
_UI_FONT_CANDIDATES = "arial,helvetica,dejavusans,verdana,liberationsans,freesans,sans"


def _load_ui_font(size: int) -> pygame.font.Font:
    return pygame.font.SysFont(_UI_FONT_CANDIDATES, size)


class Theme:
    def __init__(self) -> None:
        pygame.font.init()
        self.font_small = _load_ui_font(16)
        self.font_normal = _load_ui_font(20)
        self.font_heading = _load_ui_font(24)
        try:
            self.font_mono = pygame.font.SysFont("consolas,couriernew,monospace", 15)
        except Exception:  # pragma: no cover - fallback muy improbable
            self.font_mono = pygame.font.Font(None, 16)

        # Paleta de la interfaz (independiente de la paleta de la rejilla).
        self.bg_panel = (24, 24, 32)
        self.bg_panel_alt = (30, 30, 40)
        self.bg_widget = (42, 42, 54)
        self.bg_widget_hover = (56, 56, 72)
        self.bg_widget_pressed = (72, 72, 92)
        self.bg_widget_disabled = (32, 32, 40)
        self.accent = (90, 160, 250)
        self.accent_hover = (120, 180, 255)
        self.accent_text = (18, 18, 24)
        self.text = (230, 230, 235)
        self.text_dim = (155, 155, 165)
        self.text_disabled = (100, 100, 112)
        self.border = (60, 60, 76)
        self.danger = (214, 90, 90)
        self.danger_hover = (230, 110, 110)
        self.success = (90, 200, 130)


_default_theme: Theme | None = None


def get_default_theme() -> Theme:
    global _default_theme
    if _default_theme is None:
        _default_theme = Theme()
    return _default_theme
