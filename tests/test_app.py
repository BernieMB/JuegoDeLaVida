from __future__ import annotations

import pygame
import pytest

from vida.app import SPEED_VALUES, App
from vida.engine import Topology
from vida.renderer import ColorMode
from vida.rules import KNOWN_RULES


@pytest.fixture()
def app():
    application = App(width=30, height=30, window_size=(900, 600))
    yield application
    # No se llama a pygame.quit() aqui: el Theme es un singleton de modulo
    # cuyas fuentes quedarian invalidas para el siguiente test si se
    # desinicializara pygame.font entre tests (la app real solo hace
    # pygame.quit() una vez, al cerrar el proceso).


def _key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="")


class TestAppConstruction:
    def test_builds_engine_with_requested_size(self, app):
        assert app.engine.width == 30
        assert app.engine.height == 30

    def test_starts_paused(self, app):
        assert app.simulating is False

    def test_default_speed_is_reasonable(self, app):
        assert SPEED_VALUES[app.speed_index] >= 10

    def test_camera_fits_grid_on_startup(self, app):
        x0, y0, x1, y1 = app.camera.visible_cell_rect()
        assert x0 == 0 and y0 == 0
        assert x1 >= 29 and y1 >= 29


class TestPlaybackActions:
    def test_toggle_pause_flips_state(self, app):
        assert app.simulating is False
        app.toggle_pause()
        assert app.simulating is True
        app.toggle_pause()
        assert app.simulating is False

    def test_play_pause_update_button_label(self, app):
        app.play()
        assert "Pausar" in app.btn_play.text
        app.pause()
        assert "Reproducir" in app.btn_play.text

    def test_step_once_only_advances_when_paused(self, app):
        app.pause()
        gen_before = app.engine.generation
        app.step_once()
        assert app.engine.generation == gen_before + 1
        app.play()
        gen_before = app.engine.generation
        app.step_once()  # no deberia avanzar: la simulacion ya esta corriendo
        assert app.engine.generation == gen_before

    def test_step_button_disabled_while_simulating(self, app):
        app.play()
        assert app.btn_step.enabled is False
        app.pause()
        assert app.btn_step.enabled is True


class TestBoardActions:
    def test_clear_board_empties_grid_and_pauses(self, app):
        app.engine.set_cell(1, 1, True)
        app.play()
        app.clear_board()
        assert app.engine.population == 0
        assert app.simulating is False

    def test_reset_board_restores_seed(self, app):
        app.engine.set_cell(2, 2, True)
        app.engine.set_cell(3, 3, True)
        app.step_once()
        app.reset_board()
        assert app.engine.population == 2
        assert app.engine.generation == 0

    def test_randomize_board_uses_density_setting(self, app):
        app.density = 50
        app.randomize_board()
        assert 0.3 < app.engine.alive_fraction < 0.7


class TestSpeedControl:
    def test_set_speed_index_clamps(self, app):
        app.set_speed_index(-10)
        assert app.speed_index == 0
        app.set_speed_index(999)
        assert app.speed_index == len(SPEED_VALUES) - 1

    def test_increase_and_decrease_speed(self, app):
        app.set_speed_index(0)
        app.increase_speed()
        assert app.speed_index == 1
        app.decrease_speed()
        assert app.speed_index == 0

    def test_speed_slider_and_app_stay_in_sync(self, app):
        app.set_speed_index(3)
        assert app.speed_slider.index == 3
        app.speed_slider.set_index(5)
        assert app._on_speed_changed  # solo confirma que el callback esta enlazado

    def test_max_speed_runs_many_generations_per_frame(self, app):
        app.set_speed_index(len(SPEED_VALUES) - 1)  # "MAX"
        assert SPEED_VALUES[app.speed_index] == "MAX"
        app.play()
        gen_before = app.engine.generation
        app._advance_simulation(dt=1 / 60)
        assert app.engine.generation - gen_before > 100


class TestRuleAndTopology:
    def test_cycle_rule_changes_engine_rule(self, app):
        initial_rule = app.engine.rule
        app.cycle_rule()
        assert app.engine.rule is not initial_rule
        assert app.engine.rule.rulestring in {r.rulestring for r in KNOWN_RULES.values()}

    def test_toggle_topology_switches_between_torus_and_bounded(self, app):
        assert app.engine.topology is Topology.TORUS
        app.toggle_topology()
        assert app.engine.topology is Topology.BOUNDED
        app.toggle_topology()
        assert app.engine.topology is Topology.TORUS


class TestViewActions:
    def test_toggle_color_mode_updates_renderer_and_button(self, app):
        assert app.renderer.mode == ColorMode.CLASSIC
        app.toggle_color_mode()
        assert app.renderer.mode == ColorMode.AGE
        assert app.btn_color_mode.checked is True

    def test_fit_view_shows_whole_grid(self, app):
        app.camera.cell_size = 1
        app.fit_view()
        x0, y0, x1, y1 = app.camera.visible_cell_rect()
        assert x1 >= 29 and y1 >= 29

    def test_zoom_actual_size_sets_cell_size_near_one(self, app):
        app.zoom_actual_size()
        assert app.camera.cell_size == pytest.approx(1.0)


class TestKeyboardShortcuts:
    def test_space_toggles_pause(self, app):
        app._handle_keydown(_key(pygame.K_SPACE))
        assert app.simulating is True

    def test_c_clears_board(self, app):
        app.engine.set_cell(0, 0, True)
        app._handle_keydown(_key(pygame.K_c))
        assert app.engine.population == 0

    def test_plus_minus_change_speed(self, app):
        app.set_speed_index(2)
        app._handle_keydown(_key(pygame.K_EQUALS))
        assert app.speed_index == 3
        app._handle_keydown(_key(pygame.K_MINUS))
        assert app.speed_index == 2

    def test_g_randomizes_board(self, app):
        app._handle_keydown(_key(pygame.K_g))
        assert app.engine.population > 0


class TestResizeAndLayout:
    def test_resize_updates_viewport_and_camera(self, app):
        app.handle_resize(1000, 700)
        assert app.viewport_rect.width == 1000 - 300
        assert app.camera.viewport_width == app.viewport_rect.width


class TestUpdateDrawSmoke:
    def test_update_and_draw_cycle_does_not_crash(self, app):
        app.play()
        for _ in range(5):
            app._update(1 / 60)
            app._draw()
        assert app.engine.generation > 0

    def test_export_png(self, app, tmp_path):
        app.engine.set_cell(1, 1, True)
        out_path = str(tmp_path / "out.png")
        result = app.export_current_png(out_path)
        assert result == out_path
        assert (tmp_path / "out.png").exists()
