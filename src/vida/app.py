"""Aplicacion principal: ventana, bucle de eventos, panel de control y
sincronizacion entre la simulacion (generaciones/segundo) y el renderizado
(fotogramas/segundo), que se ejecutan a ritmos independientes."""

from __future__ import annotations

import time
from pathlib import Path

import pygame

from vida import persistence
from vida.camera import Camera
from vida.engine import LifeEngine, Topology
from vida.patterns import CATEGORY_LABELS, get_pattern, list_patterns
from vida.renderer import (
    ColorMode,
    Renderer,
    draw_stamp_preview,
    draw_world_rect_outline,
    export_png,
)
from vida.rules import KNOWN_RULES, Rule, get_rule
from vida.selection import Clipboard, Selection, StampState, bresenham_line
from vida.stats import CycleDetector, PopulationHistory, RealSpeedMeter
from vida.ui.theme import get_default_theme
from vida.ui.widgets import (
    Button,
    Checkbox,
    DiscreteSlider,
    Label,
    ListPanel,
    Panel,
    ScrollableSidebar,
    Slider,
    Sparkline,
    ToggleButton,
)

SIDEBAR_WIDTH = 300
STATUS_HEIGHT = 30
DEFAULT_WINDOW_SIZE = (1300, 860)

SPEED_VALUES = [1, 2, 5, 10, 20, 30, 60, 120, 250, 500, 1000, "MAX"]
DEFAULT_SPEED_INDEX = 6  # 60 gen/s de partida: fluido y muy por encima del minimo pedido
MAX_STEPS_PER_FRAME_FINITE = 20_000  # valvula de seguridad ante picos de dt
MAX_FRAME_BUDGET_FOR_MAX_SPEED = 1 / 60 * 0.6  # deja margen para el resto del frame

RULE_CYCLE_KEYS = list(KNOWN_RULES.keys())
SELECTION_COLOR = (250, 210, 90)
STAMP_PREVIEW_COLOR = (120, 200, 255)
PATTERN_CATEGORIES_ORDER = ("still_life", "oscillator", "spaceship", "methuselah", "gun")


def format_speed(value) -> str:
    return "MAX" if value == "MAX" else f"{value} gen/s"


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.size(candidate)[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class App:
    def __init__(self, *, width: int = 200, height: int = 200,
                 rule: Rule | None = None, topology: Topology = Topology.TORUS,
                 window_size: tuple[int, int] = DEFAULT_WINDOW_SIZE,
                 caption: str = "El Juego de la Vida",
                 patterns_dir: Path | str = "patterns") -> None:
        pygame.init()
        pygame.display.set_caption(caption)
        flags = pygame.RESIZABLE
        self.screen = pygame.display.set_mode(window_size, flags)
        self.clock = pygame.time.Clock()
        self.patterns_dir = Path(patterns_dir)

        self.engine = LifeEngine(width, height, rule=rule, topology=topology)
        self.renderer = Renderer(mode=ColorMode.CLASSIC)

        self.window_width, self.window_height = window_size
        self._recompute_layout()
        self.camera = Camera(grid_width=width, grid_height=height,
                              viewport_width=self.viewport_rect.width,
                              viewport_height=self.viewport_rect.height)
        self.camera.fit_to_grid()

        self.running = True
        self.simulating = False
        self.speed_index = DEFAULT_SPEED_INDEX
        self._sim_accumulator = 0.0
        self._panning = False
        self._painting = False
        self._erasing = False
        self._selecting = False
        self._last_paint_cell: tuple[int, int] | None = None
        self._rule_cycle_pos = RULE_CYCLE_KEYS.index("life")
        self.density = 30  # porcentaje, para el boton Aleatorio

        self.selection = Selection()
        self.clipboard = Clipboard()
        self.stamp = StampState()
        self._selected_pattern_key: str | None = None
        self._status_message: str = ""
        self._status_message_expiry: float = 0.0

        self.cycle_detector = CycleDetector()
        self.population_history = PopulationHistory()
        self.speed_meter = RealSpeedMeter()
        self.auto_pause_on_stability = False

        self.theme = get_default_theme()
        self.panel = self._build_panel()
        self.pattern_overlay = self._build_pattern_overlay()
        self.file_browser_overlay = self._build_file_browser()
        self.help_overlay = self._build_help_overlay()
        self._sync_panel_labels()
        self._sync_edit_buttons()

    # ------------------------------------------------------------------
    # Construccion del panel lateral
    # ------------------------------------------------------------------
    def _build_panel(self) -> ScrollableSidebar:
        theme = self.theme
        panel = ScrollableSidebar(pygame.Rect(0, 0, SIDEBAR_WIDTH, self.window_height),
                                   background=theme.bg_panel)
        pad = 16
        w = SIDEBAR_WIDTH - pad * 2
        y = 16

        def add_label(text, *, font=None, color=None, height=22):
            nonlocal y
            lbl = panel.add(Label(pygame.Rect(pad, y, w, height), text,
                                   font=font or theme.font_heading, color=color))
            y += height
            return lbl

        def add_gap(h=10):
            nonlocal y
            y += h

        def add_button(text, on_click, *, height=36, **kwargs):
            nonlocal y
            btn = panel.add(Button(pygame.Rect(pad, y, w, height), text, on_click=on_click, **kwargs))
            y += height + 8
            return btn

        def add_button_row(specs, *, height=36, gap=8):
            nonlocal y
            n = len(specs)
            item_w = (w - gap * (n - 1)) // n
            buttons = []
            x = pad
            for text, callback, kwargs in specs:
                btn = panel.add(Button(pygame.Rect(x, y, item_w, height), text,
                                        on_click=callback, **kwargs))
                buttons.append(btn)
                x += item_w + gap
            y += height + 8
            return buttons

        add_label("El Juego de la Vida")
        add_label("Conway · B3/S23 y variantes", font=theme.font_small, color=theme.text_dim, height=18)
        add_gap(12)

        # --- Simulacion --------------------------------------------------
        add_label("Simulacion", font=theme.font_normal, color=theme.text_dim, height=20)
        self.btn_play = add_button("Reproducir", self.toggle_pause, accent=True)
        self.btn_step = add_button("Paso a paso", self.step_once)
        self.speed_slider = panel.add(DiscreteSlider(
            pygame.Rect(pad, y, w, 40), SPEED_VALUES, index=self.speed_index,
            on_change=self._on_speed_changed, label="Velocidad", formatter=format_speed,
        ))
        y += 48
        add_gap(6)

        # --- Tablero -------------------------------------------------------
        add_label("Tablero", font=theme.font_normal, color=theme.text_dim, height=20)
        add_button("Limpiar", self.clear_board, danger=True)
        add_button("Resetear", self.reset_board)
        self.density_slider = panel.add(Slider(
            pygame.Rect(pad, y, w, 40), 1, 90, self.density, integer=True,
            label="Densidad aleatorio (%)", on_change=self._on_density_changed,
            value_formatter=lambda v: f"{v:.0f}%",
        ))
        y += 48
        add_button("Aleatorio", self.randomize_board)
        add_gap(6)

        # --- Edicion -------------------------------------------------------
        add_label("Edicion", font=theme.font_normal, color=theme.text_dim, height=20)
        add_label("Clic: pintar · Clic der.: borrar · Mayus+arrastrar: seleccionar",
                   font=theme.font_small, color=theme.text_dim, height=32)
        self.btn_undo, self.btn_redo = add_button_row([
            ("Deshacer", self.undo, {}), ("Rehacer", self.redo, {}),
        ])
        self.btn_copy, self.btn_cut = add_button_row([
            ("Copiar", self.copy_selection, {}), ("Cortar", self.cut_selection, {}),
        ])
        self.btn_paste = add_button("Pegar", self.paste_clipboard)
        self.btn_delete_selection = add_button("Borrar seleccion", self.delete_selection, danger=True)
        add_gap(6)

        # --- Patrones --------------------------------------------------
        add_label("Patrones conocidos", font=theme.font_normal, color=theme.text_dim, height=20)
        add_button("Elegir patron…", self.open_pattern_browser, accent=True)
        self.btn_cancel_stamp = add_button("Cancelar sello", self.cancel_stamp)
        add_gap(6)

        # --- Archivos --------------------------------------------------
        add_label("Archivos", font=theme.font_normal, color=theme.text_dim, height=20)
        add_button("Guardar tablero (Ctrl+S)", self.save_board_to_file)
        self.btn_save_selection = add_button("Guardar seleccion (Ctrl+Mayus+S)", self.save_selection_to_file)
        add_button("Abrir biblioteca de archivos…", self.open_file_browser)
        add_gap(6)

        # --- Reglas y topologia -------------------------------------------
        add_label("Reglas", font=theme.font_normal, color=theme.text_dim, height=20)
        self.btn_rule = add_button("Regla: …", self.cycle_rule)
        self.btn_topology = add_button("Topologia: …", self.toggle_topology)
        add_gap(6)

        # --- Vista -----------------------------------------------------
        add_label("Vista", font=theme.font_normal, color=theme.text_dim, height=20)
        add_button("Ajustar a la ventana", self.fit_view)
        add_button("Tamano real (1:1)", self.zoom_actual_size)
        self.btn_color_mode = panel.add(ToggleButton(
            pygame.Rect(pad, y, w, 36), "Coloreado por edad", checked=False,
            on_toggle=self._on_color_mode_toggled,
        ))
        y += 44
        add_gap(6)
        add_button("Exportar PNG (P)", lambda: self.export_current_png())

        # --- Estadisticas ------------------------------------------------
        add_label("Estadisticas", font=theme.font_normal, color=theme.text_dim, height=20)
        self.lbl_cycle_status = add_label("", font=theme.font_small, color=theme.success, height=18)
        self.population_sparkline = panel.add(Sparkline(
            pygame.Rect(pad, y, w, 64), get_values=self.population_history.values,
            label="Poblacion",
        ))
        y += 72
        self.chk_auto_pause = panel.add(Checkbox(
            pygame.Rect(pad, y, w, 22), "Auto-pausar al estabilizar",
            checked=False, on_toggle=self._on_auto_pause_toggled,
        ))
        y += 30
        add_gap(6)
        add_button("Ayuda (F1)", self.toggle_help)

        panel.content_height = y + 16
        return panel

    def _sync_panel_labels(self) -> None:
        self.btn_play.set_text("Pausar" if self.simulating else "Reproducir")
        self.btn_step.enabled = not self.simulating
        self.btn_rule.set_text(f"Regla: {self.engine.rule.name}")
        self.btn_topology.set_text(
            "Topologia: Toroidal" if self.engine.topology is Topology.TORUS
            else "Topologia: Acotada"
        )

    def _sync_edit_buttons(self) -> None:
        self.btn_undo.enabled = self.engine.can_undo()
        self.btn_redo.enabled = self.engine.can_redo()
        has_selection = not self.selection.is_empty
        self.btn_copy.enabled = has_selection
        self.btn_cut.enabled = has_selection
        self.btn_delete_selection.enabled = has_selection
        self.btn_save_selection.enabled = has_selection
        self.btn_paste.enabled = self.clipboard.has_content
        self.btn_cancel_stamp.enabled = self.stamp.active

    # ------------------------------------------------------------------
    # Overlay: biblioteca de patrones
    # ------------------------------------------------------------------
    def _build_pattern_overlay(self) -> Panel:
        theme = self.theme
        overlay_w = 380
        pad = 14
        inner_w = overlay_w - pad * 2
        title_h, list_h, desc_lines, desc_line_h = 26, 240, 4, 16
        gap, btn_h, btn2_h = 8, 36, 32
        overlay_h = (pad + title_h + gap + list_h + gap
                     + desc_lines * desc_line_h + gap + btn_h + gap + btn2_h + pad)

        overlay = Panel(pygame.Rect(0, 0, overlay_w, overlay_h), background=theme.bg_panel_alt)
        overlay.visible = False

        y = pad
        overlay.add(Label(pygame.Rect(pad, y, inner_w, title_h), "Biblioteca de patrones",
                           font=theme.font_heading))
        y += title_h + gap

        items: list[str] = []
        self._pattern_keys_by_item_index: list[str] = []
        for category in PATTERN_CATEGORIES_ORDER:
            label = CATEGORY_LABELS.get(category, category)
            for pattern in list_patterns(category):
                items.append(f"[{label}] {pattern.name}")
                self._pattern_keys_by_item_index.append(pattern.key)

        list_rect = pygame.Rect(pad, y, inner_w, list_h)
        self.pattern_list = overlay.add(ListPanel(
            list_rect, items=items, on_select=self._on_pattern_selected, item_height=24,
        ))
        y += list_h + gap

        self._pattern_desc_width = inner_w
        self.pattern_desc_labels = [
            overlay.add(Label(pygame.Rect(pad, y + i * desc_line_h, inner_w, desc_line_h), "",
                               font=theme.font_small, color=theme.text_dim))
            for i in range(desc_lines)
        ]
        y += desc_lines * desc_line_h + gap

        self.btn_place_pattern = overlay.add(Button(
            pygame.Rect(pad, y, inner_w, btn_h), "Colocar", on_click=self._place_selected_pattern,
            accent=True,
        ))
        y += btn_h + gap
        overlay.add(Button(pygame.Rect(pad, y, inner_w, btn2_h), "Cerrar",
                            on_click=self.close_pattern_browser))
        self.btn_place_pattern.enabled = False
        return overlay

    def _on_pattern_selected(self, index: int, _item_text: str) -> None:
        key = self._pattern_keys_by_item_index[index]
        pattern = get_pattern(key)
        lines = wrap_text(pattern.description, self.theme.font_small, self._pattern_desc_width)
        for i, label in enumerate(self.pattern_desc_labels):
            label.set_text(lines[i] if i < len(lines) else "")
        self._selected_pattern_key = key
        self.btn_place_pattern.enabled = True

    def _place_selected_pattern(self) -> None:
        if self._selected_pattern_key is not None:
            self.start_stamp_from_pattern(self._selected_pattern_key)
            self.close_pattern_browser()

    def open_pattern_browser(self) -> None:
        self.file_browser_overlay.visible = False
        self.pattern_overlay.rect.x = (self.window_width - self.pattern_overlay.rect.width) // 2
        self.pattern_overlay.rect.y = (self.window_height - self.pattern_overlay.rect.height) // 2
        self.pattern_overlay.visible = True

    def close_pattern_browser(self) -> None:
        self.pattern_overlay.visible = False

    # ------------------------------------------------------------------
    # Overlay: biblioteca de archivos guardados (patterns/)
    # ------------------------------------------------------------------
    @staticmethod
    def _add_overlay_button_row(panel: Panel, x: int, y: int, width: int,
                                 specs: list[tuple[str, object, dict]], *,
                                 height: int = 36, gap: int = 8) -> list[Button]:
        n = len(specs)
        item_w = (width - gap * (n - 1)) // n
        buttons = []
        cur_x = x
        for text, callback, kwargs in specs:
            btn = panel.add(Button(pygame.Rect(cur_x, y, item_w, height), text,
                                    on_click=callback, **kwargs))
            buttons.append(btn)
            cur_x += item_w + gap
        return buttons

    def _build_file_browser(self) -> Panel:
        theme = self.theme
        overlay_w = 380
        pad = 14
        inner_w = overlay_w - pad * 2
        title_h, list_h = 26, 240
        gap, row_h, btn_h = 10, 36, 32
        overlay_h = pad + title_h + gap + list_h + gap + row_h + gap + btn_h + gap + btn_h + pad

        overlay = Panel(pygame.Rect(0, 0, overlay_w, overlay_h), background=theme.bg_panel_alt)
        overlay.visible = False

        y = pad
        overlay.add(Label(pygame.Rect(pad, y, inner_w, title_h), "Archivos guardados (patterns/)",
                           font=theme.font_heading))
        y += title_h + gap

        list_rect = pygame.Rect(pad, y, inner_w, list_h)
        self.file_list = overlay.add(ListPanel(
            list_rect, items=[], on_select=self._on_file_selected, item_height=24,
        ))
        y += list_h + gap

        self.btn_load_as_stamp, self.btn_load_as_board = self._add_overlay_button_row(
            overlay, pad, y, inner_w,
            [("Cargar como sello", self.load_selected_as_stamp, {}),
             ("Reemplazar tablero", self.load_selected_as_board, {"danger": True})],
            height=row_h,
        )
        y += row_h + gap
        overlay.add(Button(pygame.Rect(pad, y, inner_w, btn_h), "Actualizar lista",
                            on_click=self.refresh_file_list))
        y += btn_h + gap
        overlay.add(Button(pygame.Rect(pad, y, inner_w, btn_h), "Cerrar",
                            on_click=self.close_file_browser))
        self.btn_load_as_stamp.enabled = False
        self.btn_load_as_board.enabled = False
        self._file_paths: list[Path] = []
        self._selected_file_index: int | None = None
        return overlay

    def refresh_file_list(self) -> None:
        self._file_paths = persistence.list_pattern_files(self.patterns_dir)
        self.file_list.set_items([p.name for p in self._file_paths])
        self._selected_file_index = None
        self.btn_load_as_stamp.enabled = False
        self.btn_load_as_board.enabled = False

    def _on_file_selected(self, index: int, _name: str) -> None:
        self._selected_file_index = index
        self.btn_load_as_stamp.enabled = True
        self.btn_load_as_board.enabled = True

    def open_file_browser(self) -> None:
        self.pattern_overlay.visible = False
        self.refresh_file_list()
        self.file_browser_overlay.rect.x = (self.window_width - self.file_browser_overlay.rect.width) // 2
        self.file_browser_overlay.rect.y = (self.window_height - self.file_browser_overlay.rect.height) // 2
        self.file_browser_overlay.visible = True

    def close_file_browser(self) -> None:
        self.file_browser_overlay.visible = False

    def load_selected_as_stamp(self) -> None:
        if self._selected_file_index is None:
            return
        path = self._file_paths[self._selected_file_index]
        pattern = persistence.load_pattern_file(path)
        self.stamp.set_pattern(pattern.cells, pattern.name or path.stem)
        self._center_stamp_on_cursor()
        self.close_file_browser()
        self._set_status(f"Cargado como sello: {path.name}")

    def load_selected_as_board(self) -> None:
        if self._selected_file_index is None:
            return
        path = self._file_paths[self._selected_file_index]
        pattern = persistence.load_pattern_file(path)
        self.engine.load_grid(pattern.cells)
        if pattern.rule:
            try:
                self.engine.set_rule(get_rule(pattern.rule))
            except ValueError:
                pass
        self._reset_stats_tracking()
        self._sync_panel_labels()
        self.close_file_browser()
        self._set_status(f"Tablero reemplazado: {path.name}")

    # ------------------------------------------------------------------
    # Ayuda
    # ------------------------------------------------------------------
    HELP_LINES = [
        ("Espacio", "Pausar / continuar"),
        ("-> o N", "Paso a paso (con la simulacion en pausa)"),
        ("+ / -", "Subir / bajar la velocidad"),
        ("C", "Limpiar el tablero"),
        ("R", "Resetear (o rotar el sello activo, si hay uno)"),
        ("F", "Ajustar vista (o voltear el sello activo, si hay uno)"),
        ("G", "Rellenar aleatoriamente"),
        ("1", "Zoom real (1 celda = 1 pixel)"),
        ("P", "Exportar la vista actual como PNG"),
        ("Clic izq. (arrastrar)", "Pintar celdas vivas"),
        ("Clic der. (arrastrar)", "Borrar celdas"),
        ("Mayus + arrastrar", "Seleccionar una region rectangular"),
        ("Rueda del raton", "Zoom centrado en el cursor"),
        ("Boton central + arrastrar", "Desplazar la vista (paneo)"),
        ("Ctrl+Z / Ctrl+Y", "Deshacer / rehacer"),
        ("Ctrl+C / Ctrl+X / Ctrl+V", "Copiar / cortar / pegar seleccion"),
        ("Supr / Retroceso", "Borrar la seleccion"),
        ("Escape", "Cancelar el sello activo o deseleccionar"),
        ("Ctrl+S", "Guardar el tablero completo"),
        ("Ctrl+Mayus+S", "Guardar solo la seleccion"),
        ("F1 o H", "Mostrar/ocultar esta ayuda"),
    ]

    def _build_help_overlay(self) -> Panel:
        theme = self.theme
        overlay_w = 620
        line_h = 22
        overlay_h = 60 + line_h * len(self.HELP_LINES) + 50
        overlay = Panel(pygame.Rect(0, 0, overlay_w, overlay_h), background=theme.bg_panel_alt)
        overlay.visible = False
        pad = 16
        inner_w = overlay_w - pad * 2

        overlay.add(Label(pygame.Rect(pad, pad, inner_w, 26), "Ayuda — Atajos de teclado y raton",
                           font=theme.font_heading))
        key_w = 190
        y = pad + 34
        for key_text, description in self.HELP_LINES:
            overlay.add(Label(pygame.Rect(pad, y, key_w, line_h), key_text,
                               font=theme.font_small, color=theme.accent_hover))
            overlay.add(Label(pygame.Rect(pad + key_w, y, inner_w - key_w, line_h), description,
                               font=theme.font_small, color=theme.text))
            y += line_h
        overlay.add(Button(pygame.Rect(pad, y + 12, inner_w, 32), "Cerrar", on_click=self.toggle_help))
        return overlay

    # ------------------------------------------------------------------
    # Guardar tablero / seleccion
    # ------------------------------------------------------------------
    def save_board_to_file(self) -> None:
        path = self.patterns_dir / persistence.default_filename("tablero")
        persistence.save_board(self.engine, path)
        self._set_status(f"Tablero guardado: {path.name}")

    def save_selection_to_file(self) -> None:
        if self.selection.is_empty:
            self._set_status("No hay seleccion activa para guardar")
            return
        x0, y0, x1, y1 = self.selection.normalized()
        path = self.patterns_dir / persistence.default_filename("seleccion")
        persistence.save_selection(self.engine, x0, y0, x1, y1, path)
        self._set_status(f"Seleccion guardada: {path.name}")

    def _set_status(self, message: str, duration: float = 3.0) -> None:
        self._status_message = message
        self._status_message_expiry = time.time() + duration

    # ------------------------------------------------------------------
    # Layout / ventana
    # ------------------------------------------------------------------
    def _recompute_layout(self) -> None:
        self.viewport_rect = pygame.Rect(
            SIDEBAR_WIDTH, 0,
            max(1, self.window_width - SIDEBAR_WIDTH),
            max(1, self.window_height - STATUS_HEIGHT),
        )
        self.status_rect = pygame.Rect(
            SIDEBAR_WIDTH, self.viewport_rect.bottom,
            max(1, self.window_width - SIDEBAR_WIDTH), STATUS_HEIGHT,
        )

    def handle_resize(self, width: int, height: int) -> None:
        self.window_width, self.window_height = width, height
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        self._recompute_layout()
        self.camera.resize_viewport(self.viewport_rect.width, self.viewport_rect.height)
        self.panel.rect.height = height

    # ------------------------------------------------------------------
    # Acciones de simulacion (testeables sin pasar por el bucle de eventos)
    # ------------------------------------------------------------------
    def play(self) -> None:
        self.simulating = True
        self._sim_accumulator = 0.0
        self._sync_panel_labels()

    def pause(self) -> None:
        self.simulating = False
        self._sync_panel_labels()

    def toggle_pause(self) -> None:
        self.pause() if self.simulating else self.play()

    def step_once(self) -> None:
        if not self.simulating:
            self.engine.step()

    def clear_board(self) -> None:
        self.pause()
        self.engine.clear()
        self.selection.clear()
        self._reset_stats_tracking()

    def reset_board(self) -> None:
        self.engine.reset()
        self._reset_stats_tracking()

    def randomize_board(self) -> None:
        self.engine.randomize(density=self.density / 100.0)
        self._reset_stats_tracking()

    def _reset_stats_tracking(self) -> None:
        self.cycle_detector.reset()
        self.population_history.reset()
        self.speed_meter.reset(self.engine.generation)

    def set_speed_index(self, index: int) -> None:
        self.speed_index = max(0, min(len(SPEED_VALUES) - 1, index))
        self.speed_slider.set_index(self.speed_index, notify=False)
        self._sim_accumulator = 0.0

    def increase_speed(self) -> None:
        self.set_speed_index(self.speed_index + 1)

    def decrease_speed(self) -> None:
        self.set_speed_index(self.speed_index - 1)

    def _on_speed_changed(self, value) -> None:
        self.speed_index = SPEED_VALUES.index(value)
        self._sim_accumulator = 0.0

    def _on_density_changed(self, value) -> None:
        self.density = int(value)

    def cycle_rule(self) -> None:
        self._rule_cycle_pos = (self._rule_cycle_pos + 1) % len(RULE_CYCLE_KEYS)
        rule_key = RULE_CYCLE_KEYS[self._rule_cycle_pos]
        self.engine.set_rule(KNOWN_RULES[rule_key])
        self._sync_panel_labels()

    def toggle_topology(self) -> None:
        new_topology = Topology.BOUNDED if self.engine.topology is Topology.TORUS else Topology.TORUS
        self.engine.set_topology(new_topology)
        self._sync_panel_labels()

    def toggle_color_mode(self) -> None:
        new_mode = self.renderer.toggle_mode()
        self.btn_color_mode.set_checked(new_mode == ColorMode.AGE)

    def _on_color_mode_toggled(self, checked: bool) -> None:
        self.renderer.set_mode(ColorMode.AGE if checked else ColorMode.CLASSIC)

    def _on_auto_pause_toggled(self, checked: bool) -> None:
        self.auto_pause_on_stability = checked

    def toggle_help(self) -> None:
        if self.help_overlay.visible:
            self.help_overlay.visible = False
            return
        self.pattern_overlay.visible = False
        self.file_browser_overlay.visible = False
        self.help_overlay.rect.x = (self.window_width - self.help_overlay.rect.width) // 2
        self.help_overlay.rect.y = (self.window_height - self.help_overlay.rect.height) // 2
        self.help_overlay.visible = True

    def fit_view(self) -> None:
        self.camera.fit_to_grid()

    def zoom_actual_size(self) -> None:
        self.camera.zoom_to_actual_size()

    def export_current_png(self, path: str | None = None) -> str:
        path = path or f"vida_{int(time.time())}.png"
        export_png(self.engine, path, cell_px=4, mode=self.renderer.mode)
        return path

    # ------------------------------------------------------------------
    # Deshacer / rehacer
    # ------------------------------------------------------------------
    def undo(self) -> bool:
        result = self.engine.undo()
        self._sync_panel_labels()
        return result

    def redo(self) -> bool:
        result = self.engine.redo()
        self._sync_panel_labels()
        return result

    # ------------------------------------------------------------------
    # Seleccion / portapapeles
    # ------------------------------------------------------------------
    def clear_selection(self) -> None:
        self.selection.clear()

    def copy_selection(self) -> None:
        if self.selection.is_empty:
            return
        x0, y0, x1, y1 = self.selection.normalized()
        self.clipboard.set(self.engine.extract(x0, y0, x1, y1))

    def cut_selection(self) -> None:
        if self.selection.is_empty:
            return
        x0, y0, x1, y1 = self.selection.normalized()
        self.clipboard.set(self.engine.extract(x0, y0, x1, y1))
        self.engine.clear_region(x0, y0, x1, y1)
        self.selection.clear()

    def delete_selection(self) -> None:
        if self.selection.is_empty:
            return
        x0, y0, x1, y1 = self.selection.normalized()
        self.engine.clear_region(x0, y0, x1, y1)
        self.selection.clear()

    def paste_clipboard(self) -> None:
        if self.clipboard.has_content:
            self.stamp.set_pattern(self.clipboard.grid, "Portapapeles")
            self._center_stamp_on_cursor()

    # ------------------------------------------------------------------
    # Sellos (stamps)
    # ------------------------------------------------------------------
    def start_stamp_from_pattern(self, key: str) -> None:
        pattern = get_pattern(key)
        self.stamp.set_pattern(pattern.to_grid(), pattern.name)
        self._center_stamp_on_cursor()

    def cancel_stamp(self) -> None:
        self.stamp.clear()

    def rotate_stamp(self) -> None:
        self.stamp.rotate()

    def flip_stamp(self) -> None:
        self.stamp.flip_horizontal()

    def _center_stamp_on_cursor(self) -> None:
        if not self.stamp.active:
            return
        pos = pygame.mouse.get_pos()
        cx, cy = self._event_to_cell(pos)
        ph, pw = self.stamp.grid.shape
        self.stamp.move_to(cx - pw // 2, cy - ph // 2)

    # ------------------------------------------------------------------
    # Bucle principal
    # ------------------------------------------------------------------
    def run(self) -> None:
        try:
            while self.running:
                dt = min(self.clock.tick(60) / 1000.0, 0.25)
                self._handle_events()
                self._update(dt)
                self._draw()
        finally:
            pygame.quit()

    def _active_modal(self) -> Panel | None:
        for overlay in (self.pattern_overlay, self.file_browser_overlay, self.help_overlay):
            if overlay.visible:
                return overlay
        return None

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if event.type == pygame.VIDEORESIZE:
                self.handle_resize(event.w, event.h)
                continue

            modal = self._active_modal()

            if event.type == pygame.KEYDOWN:
                if modal is not None:
                    if event.key == pygame.K_ESCAPE:
                        modal.visible = False
                    continue
                if self._handle_keydown(event):
                    continue

            if modal is not None:
                if modal.handle_event(event):
                    continue
                if event.type == pygame.MOUSEBUTTONDOWN and not modal.rect.collidepoint(event.pos):
                    modal.visible = False
                continue

            if self.panel.handle_event(event):
                continue
            self._handle_viewport_event(event)

    def _handle_keydown(self, event: pygame.event.Event) -> bool:
        key = event.key
        mods = event.mod
        ctrl = bool(mods & pygame.KMOD_CTRL)
        shift = bool(mods & pygame.KMOD_SHIFT)

        if self.stamp.active:
            if key == pygame.K_ESCAPE:
                self.cancel_stamp(); return True
            if key == pygame.K_r:
                self.rotate_stamp(); return True
            if key == pygame.K_f:
                self.flip_stamp(); return True

        if ctrl and shift and key == pygame.K_s:
            self.save_selection_to_file(); return True
        if ctrl and key == pygame.K_s:
            self.save_board_to_file(); return True
        if ctrl and key == pygame.K_z and not shift:
            self.undo(); return True
        if (ctrl and key == pygame.K_y) or (ctrl and shift and key == pygame.K_z):
            self.redo(); return True
        if ctrl and key == pygame.K_c:
            self.copy_selection(); return True
        if ctrl and key == pygame.K_x:
            self.cut_selection(); return True
        if ctrl and key == pygame.K_v:
            self.paste_clipboard(); return True
        if key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            self.delete_selection(); return True
        if key == pygame.K_ESCAPE:
            self.clear_selection(); return True

        if key == pygame.K_SPACE:
            self.toggle_pause(); return True
        if key in (pygame.K_RIGHT, pygame.K_n):
            self.step_once(); return True
        if key == pygame.K_c:
            self.clear_board(); return True
        if key == pygame.K_r:
            self.reset_board(); return True
        if key == pygame.K_g:
            self.randomize_board(); return True
        if key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.increase_speed(); return True
        if key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.decrease_speed(); return True
        if key == pygame.K_f:
            self.fit_view(); return True
        if key == pygame.K_1:
            self.zoom_actual_size(); return True
        if key == pygame.K_p:
            self.export_current_png(); return True
        if key in (pygame.K_F1, pygame.K_h):
            self.toggle_help(); return True
        return False

    def _to_viewport_local(self, pos: tuple[int, int]) -> tuple[int, int]:
        return (pos[0] - self.viewport_rect.x, pos[1] - self.viewport_rect.y)

    def _event_to_cell(self, pos: tuple[int, int]) -> tuple[int, int]:
        return self.camera.screen_to_cell(*self._to_viewport_local(pos))

    def _handle_viewport_event(self, event: pygame.event.Event) -> None:
        # Zoom y paneo funcionan siempre, sea cual sea la herramienta activa.
        if event.type == pygame.MOUSEWHEEL:
            pos = pygame.mouse.get_pos()
            if self.viewport_rect.collidepoint(pos):
                local = self._to_viewport_local(pos)
                factor = 1.15 if event.y > 0 else (1 / 1.15 if event.y < 0 else 1.0)
                if factor != 1.0:
                    self.camera.zoom_at(*local, factor)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
            if self.viewport_rect.collidepoint(event.pos):
                self._panning = True
            return
        if event.type == pygame.MOUSEBUTTONUP and event.button == 2:
            self._panning = False
            return
        if event.type == pygame.MOUSEMOTION and self._panning:
            dx, dy = event.rel
            self.camera.pan_pixels(dx, dy)
            return

        if self.stamp.active:
            self._handle_stamp_event(event)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.viewport_rect.collidepoint(event.pos):
                return
            cx, cy = self._event_to_cell(event.pos)
            if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                self.selection.start(cx, cy)
                self._selecting = True
            else:
                self.selection.clear()
                self.engine.push_undo()
                self.engine.set_cell(cx, cy, True)
                self._painting = True
                self._last_paint_cell = (cx, cy)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if not self.viewport_rect.collidepoint(event.pos):
                return
            cx, cy = self._event_to_cell(event.pos)
            self.engine.push_undo()
            self.engine.set_cell(cx, cy, False)
            self._erasing = True
            self._last_paint_cell = (cx, cy)
            return

        if event.type == pygame.MOUSEBUTTONUP and event.button in (1, 3):
            self._painting = False
            self._erasing = False
            self._selecting = False
            self._last_paint_cell = None
            return

        if event.type == pygame.MOUSEMOTION:
            cx, cy = self._event_to_cell(event.pos)
            if self._selecting:
                self.selection.update(cx, cy)
            elif self._painting or self._erasing:
                if self._last_paint_cell is not None:
                    line = bresenham_line(self._last_paint_cell[0], self._last_paint_cell[1], cx, cy)
                else:
                    line = [(cx, cy)]
                self.engine.set_cells(line, alive=self._painting)
                self._last_paint_cell = (cx, cy)
            return

    def _handle_stamp_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            cx, cy = self._event_to_cell(event.pos)
            ph, pw = self.stamp.grid.shape
            self.stamp.move_to(cx - pw // 2, cy - ph // 2)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.viewport_rect.collidepoint(event.pos):
                self.engine.push_undo()
                self.engine.stamp(self.stamp.grid, self.stamp.x, self.stamp.y)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self.cancel_stamp()
            return

    def _update(self, dt: float) -> None:
        if self.simulating:
            self._advance_simulation(dt)
        self.panel.update(dt)
        self._sync_edit_buttons()
        self.speed_meter.update(self.engine.generation)
        self.population_history.sample(self.engine)
        self.lbl_cycle_status.set_text(self.cycle_detector.message or "")

    def _advance_simulation(self, dt: float) -> None:
        speed = SPEED_VALUES[self.speed_index]
        if speed == "MAX":
            budget = MAX_FRAME_BUDGET_FOR_MAX_SPEED
            start = time.perf_counter()
            steps = 0
            while time.perf_counter() - start < budget:
                self.engine.step()
                steps += 1
                if self._observe_cycle_and_maybe_pause():
                    break
                if steps >= MAX_STEPS_PER_FRAME_FINITE:
                    break
            return

        step_dt = 1.0 / speed
        self._sim_accumulator += dt
        steps_done = 0
        while self._sim_accumulator >= step_dt and steps_done < MAX_STEPS_PER_FRAME_FINITE:
            self.engine.step()
            self._sim_accumulator -= step_dt
            steps_done += 1
            if self._observe_cycle_and_maybe_pause():
                break

    def _observe_cycle_and_maybe_pause(self) -> bool:
        just_detected = self.cycle_detector.observe(self.engine)
        if just_detected and self.auto_pause_on_stability:
            self.pause()
            self._set_status(self.cycle_detector.message or "Ciclo detectado", duration=4.0)
            return True
        return False

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------
    def _draw(self) -> None:
        self.screen.fill(self.theme.bg_panel)
        self.renderer.render(self.screen, self.viewport_rect, self.engine, self.camera)
        self._draw_selection_overlay()
        self._draw_stamp_overlay()
        self._draw_status_bar()
        self.panel.draw(self.screen)
        self.pattern_overlay.draw(self.screen)
        self.file_browser_overlay.draw(self.screen)
        self.help_overlay.draw(self.screen)
        pygame.display.flip()

    def _draw_selection_overlay(self) -> None:
        if self.selection.is_empty:
            return
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(self.viewport_rect)
        x0, y0, x1, y1 = self.selection.normalized()
        draw_world_rect_outline(self.screen, self.viewport_rect, self.camera, x0, y0, x1, y1,
                                 color=SELECTION_COLOR, width=2)
        self.screen.set_clip(prev_clip)

    def _draw_stamp_overlay(self) -> None:
        if not self.stamp.active:
            return
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(self.viewport_rect)
        draw_stamp_preview(self.screen, self.viewport_rect, self.camera, self.stamp.grid,
                            self.stamp.x, self.stamp.y, color=STAMP_PREVIEW_COLOR)
        self.screen.set_clip(prev_clip)

    def _draw_status_bar(self) -> None:
        theme = self.theme
        pygame.draw.rect(self.screen, theme.bg_panel_alt, self.status_rect)
        if self._status_message and time.time() < self._status_message_expiry:
            text = self._status_message
            color = theme.success
        else:
            text = (f"Gen {self.engine.generation}   "
                    f"Pob {self.engine.population} ({self.engine.alive_fraction:.1%})   "
                    f"{self.speed_meter.value:,.0f} gen/s   "
                    f"FPS {self.clock.get_fps():.0f}")
            color = theme.text_dim
        surf = theme.font_small.render(text, True, color)
        self.screen.blit(surf, (self.status_rect.x + 10,
                                 self.status_rect.y + (self.status_rect.height - surf.get_height()) // 2))
