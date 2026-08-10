from __future__ import annotations

import pygame
import pytest

from vida.ui.widgets import (
    Button,
    Checkbox,
    DiscreteSlider,
    Label,
    ListPanel,
    Panel,
    Slider,
    Sparkline,
    ToggleButton,
    Widget,
)


@pytest.fixture(scope="module")
def _pygame_init():
    # El ciclo de vida real de pygame lo gestiona el fixture de sesion en
    # conftest.py (ver tests/conftest.py); no hace falta repetirlo aqui.
    yield


def _mouse_down(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


def _mouse_up(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=button)


def _mouse_move(pos):
    return pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0))


def _wheel(y):
    return pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=y, flipped=False)


class TestButton:
    def test_click_inside_triggers_callback(self):
        calls = []
        btn = Button(pygame.Rect(0, 0, 100, 30), "Click", on_click=lambda: calls.append(1))
        btn.handle_event(_mouse_down((50, 15)))
        btn.handle_event(_mouse_up((50, 15)))
        assert calls == [1]

    def test_release_outside_does_not_trigger(self):
        calls = []
        btn = Button(pygame.Rect(0, 0, 100, 30), "Click", on_click=lambda: calls.append(1))
        btn.handle_event(_mouse_down((50, 15)))
        btn.handle_event(_mouse_up((500, 500)))
        assert calls == []

    def test_disabled_button_ignores_clicks(self):
        calls = []
        btn = Button(pygame.Rect(0, 0, 100, 30), "Click", on_click=lambda: calls.append(1))
        btn.enabled = False
        btn.handle_event(_mouse_down((50, 15)))
        btn.handle_event(_mouse_up((50, 15)))
        assert calls == []

    def test_hover_state_tracks_mouse_motion(self):
        btn = Button(pygame.Rect(0, 0, 100, 30), "Click")
        btn.handle_event(_mouse_move((50, 15)))
        assert btn.hovered is True
        btn.handle_event(_mouse_move((500, 500)))
        assert btn.hovered is False

    def test_set_text_changes_label(self):
        btn = Button(pygame.Rect(0, 0, 100, 30), "Antes")
        btn.set_text("Despues")
        assert btn.text == "Despues"

    def test_draw_does_not_crash(self):
        btn = Button(pygame.Rect(0, 0, 100, 30), "Click", accent=True)
        surface = pygame.Surface((200, 200))
        btn.draw(surface)
        btn.danger = True
        btn.draw(surface)
        btn.enabled = False
        btn.draw(surface)


class TestToggleButton:
    def test_click_toggles_checked_and_notifies(self):
        states = []
        btn = ToggleButton(pygame.Rect(0, 0, 100, 30), "Modo", checked=False,
                            on_toggle=lambda c: states.append(c))
        btn.handle_event(_mouse_down((10, 10)))
        btn.handle_event(_mouse_up((10, 10)))
        assert btn.checked is True
        assert states == [True]
        btn.handle_event(_mouse_down((10, 10)))
        btn.handle_event(_mouse_up((10, 10)))
        assert btn.checked is False
        assert states == [True, False]

    def test_set_checked_without_notify(self):
        states = []
        btn = ToggleButton(pygame.Rect(0, 0, 100, 30), "Modo", on_toggle=lambda c: states.append(c))
        btn.set_checked(True, notify=False)
        assert btn.checked is True
        assert states == []


class TestSlider:
    def test_set_value_clamps_to_range(self):
        slider = Slider(pygame.Rect(0, 0, 200, 30), 0, 10, 5)
        slider.set_value(999)
        assert slider.value == 10
        slider.set_value(-999)
        assert slider.value == 0

    def test_integer_mode_rounds(self):
        slider = Slider(pygame.Rect(0, 0, 200, 30), 0, 10, 0, integer=True)
        slider.set_value(4.6)
        assert slider.value == 5
        assert isinstance(slider.value, int)

    def test_click_on_track_updates_value(self):
        slider = Slider(pygame.Rect(0, 0, 200, 30), 0, 100, 0)
        # El track tiene padding de 4px por cada lado: ancho util ~= 192.
        slider.handle_event(_mouse_down((100, 25)))
        assert 40 < slider.value < 60  # aprox mitad del recorrido

    def test_on_change_called_only_when_value_changes(self):
        calls = []
        slider = Slider(pygame.Rect(0, 0, 200, 30), 0, 10, 5, on_change=lambda v: calls.append(v))
        slider.set_value(5)  # mismo valor -> no deberia notificar
        assert calls == []
        slider.set_value(7)
        assert calls == [7]

    def test_dragging_updates_continuously(self):
        slider = Slider(pygame.Rect(0, 0, 200, 30), 0, 100, 0)
        slider.handle_event(_mouse_down((4, 25)))
        first_value = slider.value
        slider.handle_event(_mouse_move((196, 25)))
        assert slider.value > first_value
        slider.handle_event(_mouse_up((196, 25)))
        assert slider.dragging is False

    def test_draw_does_not_crash(self):
        slider = Slider(pygame.Rect(0, 0, 200, 30), 0, 10, 5, label="Densidad")
        pygame.Surface((300, 100)).blit  # noqa: B018 (solo para asegurar contexto pygame listo)
        slider.draw(pygame.Surface((300, 100)))


class TestDiscreteSlider:
    SPEEDS = [1, 2, 5, 10, 20, 30, 60, 120, 250, 500, 1000]

    def test_set_index_clamps(self):
        slider = DiscreteSlider(pygame.Rect(0, 0, 200, 30), self.SPEEDS, index=0)
        slider.set_index(-5)
        assert slider.index == 0
        slider.set_index(999)
        assert slider.index == len(self.SPEEDS) - 1

    def test_step_moves_by_delta(self):
        slider = DiscreteSlider(pygame.Rect(0, 0, 200, 30), self.SPEEDS, index=2)
        slider.step(1)
        assert slider.index == 3
        assert slider.value == 10
        slider.step(-2)
        assert slider.index == 1

    def test_value_property_matches_index(self):
        slider = DiscreteSlider(pygame.Rect(0, 0, 200, 30), self.SPEEDS, index=5)
        assert slider.value == 30

    def test_on_change_receives_actual_value_not_index(self):
        seen = []
        slider = DiscreteSlider(pygame.Rect(0, 0, 200, 30), self.SPEEDS, index=0,
                                 on_change=lambda v: seen.append(v))
        slider.set_index(4)
        assert seen == [20]

    def test_click_near_right_edge_selects_last_value(self):
        slider = DiscreteSlider(pygame.Rect(0, 0, 200, 30), self.SPEEDS, index=0)
        slider.handle_event(_mouse_down((199, 25)))
        assert slider.value == self.SPEEDS[-1]


class TestCheckbox:
    def test_click_toggles_and_notifies(self):
        states = []
        cb = Checkbox(pygame.Rect(0, 0, 150, 20), "Auto-pausa", on_toggle=lambda c: states.append(c))
        cb.handle_event(_mouse_down((5, 10)))
        assert cb.checked is True
        assert states == [True]

    def test_click_outside_does_nothing(self):
        cb = Checkbox(pygame.Rect(0, 0, 150, 20), "Auto-pausa")
        cb.handle_event(_mouse_down((500, 500)))
        assert cb.checked is False


class TestLabel:
    def test_set_text_updates_and_draw_does_not_crash(self):
        label = Label(pygame.Rect(0, 0, 100, 20), "Hola")
        label.set_text("Adios")
        assert label.text == "Adios"
        label.draw(pygame.Surface((200, 100)))

    def test_alignment_variants_do_not_crash(self):
        surface = pygame.Surface((200, 100))
        for align in ("left", "center", "right"):
            Label(pygame.Rect(0, 0, 100, 20), "X", align=align).draw(surface)


class TestListPanel:
    def test_click_selects_item_and_notifies(self):
        selected = []
        panel = ListPanel(pygame.Rect(0, 0, 150, 100), items=["a", "b", "c"],
                           on_select=lambda i, v: selected.append((i, v)),
                           item_height=25)
        panel.handle_event(_mouse_down((10, 30)))  # segunda fila (indice 1)
        assert selected == [(1, "b")]
        assert panel.selected_index == 1

    def test_scroll_clamped_within_bounds(self):
        panel = ListPanel(pygame.Rect(0, 0, 150, 60), items=[f"item{i}" for i in range(20)],
                           item_height=20)
        for _ in range(50):
            panel.handle_event(_wheel(-1))
        assert panel.scroll == panel._max_scroll()
        for _ in range(50):
            panel.handle_event(_wheel(1))
        assert panel.scroll == 0

    def test_set_items_resets_selection(self):
        panel = ListPanel(pygame.Rect(0, 0, 150, 100), items=["a", "b"], item_height=25)
        panel.handle_event(_mouse_down((10, 5)))
        assert panel.selected_index == 0
        panel.set_items(["x", "y", "z"])
        assert panel.selected_index is None

    def test_draw_does_not_crash_with_scrolled_offscreen_items(self):
        panel = ListPanel(pygame.Rect(0, 0, 150, 60), items=[f"item{i}" for i in range(50)],
                           item_height=20)
        panel.scroll = 400
        panel.draw(pygame.Surface((300, 300)))


class TestPanelContainer:
    def test_add_appends_widget(self):
        panel = Panel(pygame.Rect(0, 0, 300, 300))
        btn = panel.add(Button(pygame.Rect(0, 0, 50, 20), "X"))
        assert btn in panel.children

    def test_event_stops_at_first_consuming_child(self):
        calls = []
        panel = Panel(pygame.Rect(0, 0, 300, 300))
        panel.add(Button(pygame.Rect(0, 0, 100, 30), "A", on_click=lambda: calls.append("A")))
        panel.add(Button(pygame.Rect(0, 0, 100, 30), "B", on_click=lambda: calls.append("B")))
        panel.handle_event(_mouse_down((10, 10)))
        panel.handle_event(_mouse_up((10, 10)))
        # Los botones se solapan; el ultimo anadido (B) se procesa primero.
        assert calls == ["B"]

    def test_invisible_panel_ignores_events(self):
        calls = []
        panel = Panel(pygame.Rect(0, 0, 300, 300))
        panel.add(Button(pygame.Rect(0, 0, 100, 30), "A", on_click=lambda: calls.append("A")))
        panel.visible = False
        panel.handle_event(_mouse_down((10, 10)))
        panel.handle_event(_mouse_up((10, 10)))
        assert calls == []

    def test_draw_renders_all_visible_children_without_crash(self):
        panel = Panel(pygame.Rect(0, 0, 300, 300), background=(10, 10, 10))
        panel.add(Label(pygame.Rect(10, 10, 100, 20), "Titulo"))
        panel.add(Button(pygame.Rect(10, 40, 100, 30), "Boton"))
        panel.draw(pygame.Surface((300, 300)))


class TestPanelChildCoordinatesAreLocalToPanelPosition:
    """Regresion: si el panel se reposiciona (p.ej. para centrar un dialogo
    emergente en la ventana), sus widgets hijos -definidos en coordenadas
    LOCALES- deben seguir respondiendo en la posicion de PANTALLA correcta,
    no en sus coordenadas locales crudas."""

    def test_click_on_child_uses_screen_coordinates_when_panel_is_offset(self):
        calls = []
        # Panel desplazado a (500, 300), como un dialogo centrado en pantalla.
        panel = Panel(pygame.Rect(500, 300, 300, 200))
        # Boton en coordenadas LOCALES (10,10)-(110,40) dentro del panel.
        panel.add(Button(pygame.Rect(10, 10, 100, 30), "Boton", on_click=lambda: calls.append(1)))

        # Un clic en la coordenada LOCAL (sin sumar el offset del panel) NO
        # deberia activar el boton: en pantalla esa posicion cae fuera del panel.
        panel.handle_event(_mouse_down((50, 20)))
        panel.handle_event(_mouse_up((50, 20)))
        assert calls == []

        # El clic en la posicion de PANTALLA correcta (offset del panel +
        # coordenada local) si debe activarlo.
        panel.handle_event(_mouse_down((500 + 50, 300 + 20)))
        panel.handle_event(_mouse_up((500 + 50, 300 + 20)))
        assert calls == [1]

    def test_draw_positions_children_at_panel_offset(self):
        panel = Panel(pygame.Rect(100, 50, 200, 150), background=(0, 0, 0))
        panel.add(Button(pygame.Rect(10, 10, 80, 20), "Boton"))
        surface = pygame.Surface((400, 300))
        surface.fill((0, 0, 0))
        panel.draw(surface)
        # El boton se dibuja en la region de pantalla (110..190, 60..80)
        # (offset del panel (100,50) + rect local (10,10,80,20)), no en su
        # rect local crudo (10..90, 10..30).
        button_screen_region = [
            tuple(surface.get_at((x, y)))[:3]
            for x in range(111, 190, 4) for y in range(61, 80, 4)
        ]
        assert any(px != (0, 0, 0) for px in button_screen_region), (
            "el boton no se dibujo en su posicion de pantalla esperada"
        )
        local_region = [
            tuple(surface.get_at((x, y)))[:3]
            for x in range(11, 90, 4) for y in range(11, 30, 4)
        ]
        assert all(px == (0, 0, 0) for px in local_region), (
            "el boton se dibujo en sus coordenadas locales crudas, sin aplicar el offset del panel"
        )

    def test_moving_panel_after_construction_still_routes_events_correctly(self):
        calls = []
        panel = Panel(pygame.Rect(0, 0, 300, 200))
        panel.add(Button(pygame.Rect(20, 20, 100, 30), "Boton", on_click=lambda: calls.append(1)))
        # Se reposiciona el panel DESPUES de anadir los hijos (como hace
        # open_pattern_browser al centrar el dialogo en la ventana).
        panel.rect.x = 400
        panel.rect.y = 250
        panel.handle_event(_mouse_down((400 + 50, 250 + 30)))
        panel.handle_event(_mouse_up((400 + 50, 250 + 30)))
        assert calls == [1]


class TestSparkline:
    def test_draw_does_not_crash_with_no_values(self):
        spark = Sparkline(pygame.Rect(0, 0, 200, 60), get_values=lambda: [])
        spark.draw(pygame.Surface((300, 300)))

    def test_draw_does_not_crash_with_a_single_value(self):
        spark = Sparkline(pygame.Rect(0, 0, 200, 60), get_values=lambda: [5])
        spark.draw(pygame.Surface((300, 300)))

    def test_draw_does_not_crash_with_constant_values(self):
        # span == 0: no debe dividir por cero.
        spark = Sparkline(pygame.Rect(0, 0, 200, 60), get_values=lambda: [3, 3, 3, 3])
        spark.draw(pygame.Surface((300, 300)))

    def test_draw_with_label_shows_latest_value(self):
        spark = Sparkline(pygame.Rect(0, 0, 200, 60), get_values=lambda: [1, 2, 3], label="Poblacion")
        surface = pygame.Surface((300, 300))
        spark.draw(surface)  # solo verificamos que no lance excepcion

    def test_calls_get_values_callable_each_draw(self):
        calls = []

        def provider():
            calls.append(1)
            return [1, 2, 3]

        spark = Sparkline(pygame.Rect(0, 0, 200, 60), get_values=provider)
        spark.draw(pygame.Surface((300, 300)))
        spark.draw(pygame.Surface((300, 300)))
        assert len(calls) == 2
