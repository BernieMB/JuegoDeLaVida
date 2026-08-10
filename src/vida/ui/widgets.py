"""Widgets de interfaz en modo retenido para pygame: Button, ToggleButton,
Slider, DiscreteSlider, Label, Checkbox, ListPanel, Sparkline y Panel
(contenedor)."""

from __future__ import annotations

from typing import Callable

import pygame

from vida.ui.theme import Theme, get_default_theme


class Widget:
    def __init__(self, rect: pygame.Rect) -> None:
        self.rect = rect
        self.visible = True
        self.enabled = True

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Devuelve True si el evento fue consumido (para no propagarlo)."""
        return False

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        pass


class Button(Widget):
    def __init__(self, rect: pygame.Rect, text: str,
                 on_click: Callable[[], None] | None = None, *,
                 theme: Theme | None = None, danger: bool = False,
                 accent: bool = False) -> None:
        super().__init__(rect)
        self.text = text
        self.on_click = on_click
        self.theme = theme or get_default_theme()
        self.danger = danger
        self.accent = accent
        self.hovered = False
        self._pressed_inside = False

    def set_text(self, text: str) -> None:
        self.text = text

    def _is_accent_like(self) -> bool:
        return self.accent or getattr(self, "checked", False)

    def _colors_for_state(self):
        theme = self.theme
        if not self.enabled:
            return theme.bg_widget_disabled, theme.text_disabled, theme.border
        accent_like = self._is_accent_like()
        if self.danger:
            base, hover = theme.danger, theme.danger_hover
        elif accent_like:
            base, hover = theme.accent, theme.accent_hover
        else:
            base, hover = theme.bg_widget, theme.bg_widget_hover
        text_color = theme.accent_text if accent_like else theme.text
        active = self.hovered or self._pressed_inside
        border = theme.accent if (active or accent_like) else theme.border
        bg = hover if active else base
        return bg, text_color, border

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._pressed_inside = True
                return True
            return False
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_pressed = self._pressed_inside
            self._pressed_inside = False
            if was_pressed and self.rect.collidepoint(event.pos):
                if self.on_click is not None:
                    self.on_click()
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.theme
        bg, text_color, border = self._colors_for_state()
        pygame.draw.rect(surface, bg, self.rect, border_radius=6)
        pygame.draw.rect(surface, border, self.rect, width=1, border_radius=6)
        text_surf = theme.font_normal.render(self.text, True, text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)


class ToggleButton(Button):
    def __init__(self, rect: pygame.Rect, text: str, checked: bool = False,
                 on_toggle: Callable[[bool], None] | None = None, **kwargs) -> None:
        super().__init__(rect, text, on_click=self._handle_click, **kwargs)
        self.checked = checked
        self.on_toggle = on_toggle

    def _handle_click(self) -> None:
        self.checked = not self.checked
        if self.on_toggle is not None:
            self.on_toggle(self.checked)

    def set_checked(self, checked: bool, notify: bool = False) -> None:
        self.checked = checked
        if notify and self.on_toggle is not None:
            self.on_toggle(self.checked)


class Slider(Widget):
    """Control deslizante continuo (o entero) para un rango [min, max]."""

    def __init__(self, rect: pygame.Rect, min_value: float, max_value: float,
                 value: float, on_change: Callable[[float], None] | None = None, *,
                 integer: bool = False, label: str = "", theme: Theme | None = None,
                 value_formatter: Callable[[float], str] | None = None) -> None:
        super().__init__(rect)
        self.min_value = min_value
        self.max_value = max_value
        self.value = value
        self.on_change = on_change
        self.integer = integer
        self.label = label
        self.theme = theme or get_default_theme()
        self.value_formatter = value_formatter or (
            (lambda v: f"{v:.0f}") if integer else (lambda v: f"{v:.2f}")
        )
        self.dragging = False

    def set_value(self, value: float, notify: bool = True) -> None:
        value = max(self.min_value, min(self.max_value, value))
        if self.integer:
            value = round(value)
        changed = value != self.value
        self.value = value
        if changed and notify and self.on_change is not None:
            self.on_change(self.value)

    def _track_rect(self) -> pygame.Rect:
        pad = 4
        return pygame.Rect(self.rect.x + pad, self.rect.bottom - 10,
                            max(1, self.rect.width - 2 * pad), 6)

    def _update_from_mouse_x(self, mx: int) -> None:
        track = self._track_rect()
        t = 0.0 if track.width <= 0 else (mx - track.x) / track.width
        t = max(0.0, min(1.0, t))
        self.set_value(self.min_value + t * (self.max_value - self.min_value))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            self.dragging = True
            self._update_from_mouse_x(event.pos[0])
            return True
        if event.type == pygame.MOUSEMOTION and self.dragging:
            self._update_from_mouse_x(event.pos[0])
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging:
            self.dragging = False
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.theme
        if self.label:
            label_surf = theme.font_small.render(
                f"{self.label}: {self.value_formatter(self.value)}", True, theme.text_dim
            )
            surface.blit(label_surf, (self.rect.x, self.rect.y))
        track = self._track_rect()
        pygame.draw.rect(surface, theme.bg_widget, track, border_radius=3)
        span = self.max_value - self.min_value
        t = 0.0 if span == 0 else (self.value - self.min_value) / span
        fill_w = round(track.width * t)
        if fill_w > 0:
            pygame.draw.rect(surface, theme.accent, pygame.Rect(track.x, track.y, fill_w, track.height),
                              border_radius=3)
        handle_center = (track.x + fill_w, track.y + track.height // 2)
        pygame.draw.circle(surface, theme.accent_hover if self.dragging else theme.accent, handle_center, 7)
        pygame.draw.circle(surface, theme.text, handle_center, 7, width=1)


class DiscreteSlider(Widget):
    """Control deslizante sobre una lista fija de valores (p.ej. la escala
    de velocidad 1,2,5,10,...,MAX)."""

    def __init__(self, rect: pygame.Rect, values: list, index: int = 0,
                 on_change: Callable[[object], None] | None = None, *,
                 label: str = "", theme: Theme | None = None,
                 formatter: Callable[[object], str] = str) -> None:
        super().__init__(rect)
        self.values = list(values)
        self.index = max(0, min(len(self.values) - 1, index))
        self.on_change = on_change
        self.label = label
        self.theme = theme or get_default_theme()
        self.formatter = formatter
        self.dragging = False

    @property
    def value(self):
        return self.values[self.index]

    def set_index(self, index: int, notify: bool = True) -> None:
        index = max(0, min(len(self.values) - 1, index))
        changed = index != self.index
        self.index = index
        if changed and notify and self.on_change is not None:
            self.on_change(self.value)

    def step(self, delta: int) -> None:
        self.set_index(self.index + delta)

    def _track_rect(self) -> pygame.Rect:
        pad = 4
        return pygame.Rect(self.rect.x + pad, self.rect.bottom - 10,
                            max(1, self.rect.width - 2 * pad), 6)

    def _update_from_mouse_x(self, mx: int) -> None:
        track = self._track_rect()
        n = len(self.values)
        if n <= 1 or track.width <= 0:
            return
        t = max(0.0, min(1.0, (mx - track.x) / track.width))
        self.set_index(round(t * (n - 1)))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            self.dragging = True
            self._update_from_mouse_x(event.pos[0])
            return True
        if event.type == pygame.MOUSEMOTION and self.dragging:
            self._update_from_mouse_x(event.pos[0])
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging:
            self.dragging = False
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.theme
        if self.label:
            label_surf = theme.font_small.render(
                f"{self.label}: {self.formatter(self.value)}", True, theme.text_dim
            )
            surface.blit(label_surf, (self.rect.x, self.rect.y))
        track = self._track_rect()
        pygame.draw.rect(surface, theme.bg_widget, track, border_radius=3)
        n = len(self.values)
        for i in range(n):
            ti = 0.0 if n <= 1 else i / (n - 1)
            x = track.x + round(track.width * ti)
            pygame.draw.line(surface, theme.border, (x, track.y - 2), (x, track.y + track.height + 2))
        t = 0.0 if n <= 1 else self.index / (n - 1)
        fill_w = round(track.width * t)
        if fill_w > 0:
            pygame.draw.rect(surface, theme.accent, pygame.Rect(track.x, track.y, fill_w, track.height),
                              border_radius=3)
        handle_center = (track.x + fill_w, track.y + track.height // 2)
        pygame.draw.circle(surface, theme.accent_hover if self.dragging else theme.accent, handle_center, 7)
        pygame.draw.circle(surface, theme.text, handle_center, 7, width=1)


class Checkbox(Widget):
    def __init__(self, rect: pygame.Rect, text: str, checked: bool = False,
                 on_toggle: Callable[[bool], None] | None = None, *,
                 theme: Theme | None = None) -> None:
        super().__init__(rect)
        self.text = text
        self.checked = checked
        self.on_toggle = on_toggle
        self.theme = theme or get_default_theme()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            self.checked = not self.checked
            if self.on_toggle is not None:
                self.on_toggle(self.checked)
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.theme
        box_size = min(18, self.rect.height)
        box_rect = pygame.Rect(self.rect.x, self.rect.y + (self.rect.height - box_size) // 2,
                                box_size, box_size)
        pygame.draw.rect(surface, theme.accent if self.checked else theme.bg_widget, box_rect, border_radius=3)
        pygame.draw.rect(surface, theme.border, box_rect, width=1, border_radius=3)
        if self.checked:
            inner = box_rect.inflate(-6, -6)
            pygame.draw.rect(surface, theme.accent_text, inner, border_radius=2)
        text_surf = theme.font_small.render(self.text, True, theme.text)
        surface.blit(text_surf, (box_rect.right + 8, self.rect.y + (self.rect.height - text_surf.get_height()) // 2))


class Label(Widget):
    def __init__(self, rect: pygame.Rect, text: str = "", *, theme: Theme | None = None,
                 color: tuple[int, int, int] | None = None, font: pygame.font.Font | None = None,
                 align: str = "left") -> None:
        super().__init__(rect)
        self.text = text
        self.theme = theme or get_default_theme()
        self.color = color
        self.font = font
        self.align = align

    def set_text(self, text: str) -> None:
        self.text = text

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.theme
        font = self.font or theme.font_normal
        color = self.color or theme.text
        text_surf = font.render(self.text, True, color)
        if self.align == "center":
            rect = text_surf.get_rect(center=self.rect.center)
        elif self.align == "right":
            rect = text_surf.get_rect(midright=(self.rect.right, self.rect.centery))
        else:
            rect = text_surf.get_rect(midleft=(self.rect.x, self.rect.centery))
        surface.blit(text_surf, rect)


class ListPanel(Widget):
    """Lista desplazable de elementos seleccionables (patrones, ficheros...)."""

    def __init__(self, rect: pygame.Rect, items: list | None = None,
                 on_select: Callable[[int, object], None] | None = None, *,
                 theme: Theme | None = None, item_height: int = 26) -> None:
        super().__init__(rect)
        self.items = list(items or [])
        self.on_select = on_select
        self.theme = theme or get_default_theme()
        self.item_height = item_height
        self.scroll = 0
        self.selected_index: int | None = None
        self.hovered_index: int | None = None

    def set_items(self, items: list, keep_selection: bool = False) -> None:
        self.items = list(items)
        if not keep_selection:
            self.selected_index = None
        self.scroll = 0
        self.hovered_index = None

    def _max_scroll(self) -> int:
        content_h = len(self.items) * self.item_height
        return max(0, content_h - self.rect.height)

    def _index_at(self, pos: tuple[int, int]) -> int | None:
        if not self.rect.collidepoint(pos):
            return None
        local_y = pos[1] - self.rect.y + self.scroll
        idx = local_y // self.item_height
        if 0 <= idx < len(self.items):
            return int(idx)
        return None

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                self.scroll = max(0, min(self._max_scroll(), self.scroll - event.y * self.item_height * 2))
                return True
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hovered_index = self._index_at(event.pos)
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            idx = self._index_at(event.pos)
            if idx is not None:
                self.selected_index = idx
                if self.on_select is not None:
                    self.on_select(idx, self.items[idx])
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.theme
        pygame.draw.rect(surface, theme.bg_panel_alt, self.rect)
        prev_clip = surface.get_clip()
        surface.set_clip(self.rect)
        for i, item in enumerate(self.items):
            y = self.rect.y - self.scroll + i * self.item_height
            if y + self.item_height < self.rect.y or y > self.rect.bottom:
                continue
            item_rect = pygame.Rect(self.rect.x, y, self.rect.width, self.item_height - 1)
            if i == self.selected_index:
                bg, text_color = theme.accent, theme.accent_text
            elif i == self.hovered_index:
                bg, text_color = theme.bg_widget_hover, theme.text
            else:
                bg, text_color = theme.bg_panel_alt, theme.text_dim
            pygame.draw.rect(surface, bg, item_rect)
            text_surf = theme.font_small.render(str(item), True, text_color)
            surface.blit(text_surf, (item_rect.x + 8, item_rect.y + (item_rect.height - text_surf.get_height()) // 2))
        surface.set_clip(prev_clip)
        pygame.draw.rect(surface, theme.border, self.rect, width=1)


class Sparkline(Widget):
    """Grafica de tendencia sencilla (linea) para una serie de valores,
    p.ej. el historial de poblacion."""

    def __init__(self, rect: pygame.Rect, get_values: Callable[[], list[float]], *,
                 theme: Theme | None = None, label: str = "") -> None:
        super().__init__(rect)
        self.get_values = get_values
        self.theme = theme or get_default_theme()
        self.label = label

    def draw(self, surface: pygame.Surface) -> None:
        theme = self.theme
        pygame.draw.rect(surface, theme.bg_widget, self.rect, border_radius=4)
        values = list(self.get_values())

        label_h = 16 if self.label else 0
        if self.label:
            current = f" ({values[-1]:.0f})" if values else ""
            label_surf = theme.font_small.render(f"{self.label}{current}", True, theme.text_dim)
            surface.blit(label_surf, (self.rect.x + 6, self.rect.y + 2))

        graph_top = self.rect.y + label_h + 3
        graph_h = max(1, self.rect.height - label_h - 6)
        if len(values) >= 2:
            lo, hi = min(values), max(values)
            span = max(1e-9, hi - lo)
            n = len(values)
            usable_w = max(1, self.rect.width - 8)
            points = []
            for i, v in enumerate(values):
                x = self.rect.x + 4 + usable_w * (i / (n - 1))
                t = (v - lo) / span
                y = graph_top + graph_h * (1 - t)
                points.append((x, y))
            pygame.draw.lines(surface, theme.accent, False, points, 2)
        pygame.draw.rect(surface, theme.border, self.rect, width=1, border_radius=4)


class Panel(Widget):
    """Contenedor: agrupa widgets hijos y les reenvia eventos/dibujo.

    Los widgets hijos se definen con coordenadas LOCALES (relativas a la
    esquina superior izquierda del panel, como si este estuviera en
    (0, 0)). El panel traduce automaticamente esas coordenadas al dibujar
    (mediante una subsuperficie desplazada) y al manejar eventos (restando
    la posicion del panel a ``event.pos``), de modo que reposicionar el
    panel entero (p.ej. para centrar un dialogo emergente en la ventana)
    no requiere recalcular la posicion de cada widget hijo."""

    def __init__(self, rect: pygame.Rect, *, theme: Theme | None = None,
                 background: tuple[int, int, int] | None = None) -> None:
        super().__init__(rect)
        self.theme = theme or get_default_theme()
        self.background = background
        self.children: list[Widget] = []

    def add(self, widget: Widget) -> Widget:
        self.children.append(widget)
        return widget

    def _shift_event(self, event: pygame.event.Event) -> pygame.event.Event:
        if not hasattr(event, "pos"):
            return event
        data = event.dict.copy()
        data["pos"] = (event.pos[0] - self.rect.x, event.pos[1] - self.rect.y)
        return pygame.event.Event(event.type, data)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False
        shifted = self._shift_event(event)
        for child in reversed(self.children):
            if child.handle_event(shifted):
                return True
        return False

    def update(self, dt: float) -> None:
        for child in self.children:
            child.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        if self.background:
            pygame.draw.rect(surface, self.background, self.rect)
        target = surface
        if self.rect.x or self.rect.y:
            clipped = self.rect.clip(surface.get_rect())
            if clipped.width > 0 and clipped.height > 0:
                target = surface.subsurface(clipped)
        for child in self.children:
            if child.visible:
                child.draw(target)


class ScrollableSidebar(Panel):
    """Panel que permite que su contenido (los widgets hijos, colocados en
    coordenadas 'de contenido' a partir de y=0) supere la altura visible del
    panel, desplazandose con la rueda del raton. Util para el panel lateral
    de controles cuando tiene mas secciones de las que caben en pantalla."""

    SCROLL_STEP = 32

    def __init__(self, rect: pygame.Rect, *, theme: Theme | None = None,
                 background: tuple[int, int, int] | None = None) -> None:
        super().__init__(rect, theme=theme, background=background)
        self.scroll = 0
        self.content_height = rect.height

    def _max_scroll(self) -> int:
        return max(0, self.content_height - self.rect.height)

    def clamp_scroll(self) -> None:
        self.scroll = max(0, min(self._max_scroll(), self.scroll))

    def _shift_event(self, event: pygame.event.Event) -> pygame.event.Event:
        if not hasattr(event, "pos"):
            return event
        data = event.dict.copy()
        data["pos"] = (event.pos[0] - self.rect.x, event.pos[1] - self.rect.y + self.scroll)
        return pygame.event.Event(event.type, data)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                self.scroll -= event.y * self.SCROLL_STEP
                self.clamp_scroll()
                return True
            return False
        if hasattr(event, "pos"):
            shifted = self._shift_event(event)
            for child in reversed(self.children):
                if child.handle_event(shifted):
                    return True
            return False
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        canvas_height = max(self.content_height, self.rect.height)
        content = pygame.Surface((max(1, self.rect.width), canvas_height))
        if self.background:
            content.fill(self.background)
        for child in self.children:
            if child.visible:
                child.draw(content)
        self.clamp_scroll()
        visible_h = min(self.rect.height, canvas_height - self.scroll)
        visible_slice = content.subsurface(pygame.Rect(0, self.scroll, self.rect.width, max(1, visible_h)))
        surface.blit(visible_slice, self.rect.topleft)

        if self._max_scroll() > 0:
            theme = self.theme
            track_h = self.rect.height
            thumb_h = max(24, int(track_h * self.rect.height / canvas_height))
            thumb_y = self.rect.y + int((track_h - thumb_h) * (self.scroll / self._max_scroll()))
            pygame.draw.rect(surface, theme.border,
                              pygame.Rect(self.rect.right - 4, thumb_y, 3, thumb_h), border_radius=2)
