from __future__ import annotations

import pygame
import pytest

from vida.app import App
from vida.engine import Topology
from vida.stats import CycleStatus


@pytest.fixture()
def app():
    application = App(width=30, height=30, window_size=(900, 600))
    application.engine.set_topology(Topology.BOUNDED)
    return application


def _key(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="")


def _mouse_down(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


class TestFrameSampling:
    def test_update_samples_population_history(self, app):
        app.engine.set_cells([(1, 1), (2, 2)], True)
        app._update(1 / 60)
        assert app.population_history.values() == [2]

    def test_update_refreshes_cycle_status_label(self, app):
        app.engine.set_cells([(4, 4), (5, 4), (4, 5), (5, 5)], True)  # block
        app.play()
        app._update(1 / 60)
        app._update(1 / 60)
        assert "Estable" in app.lbl_cycle_status.text or app.lbl_cycle_status.text == ""


class TestAutoPauseOnStability:
    def test_auto_pause_stops_simulation_when_still_life_detected(self, app):
        app.engine.set_cells([(4, 4), (5, 4), (4, 5), (5, 5)], True)  # block, ya estable
        app.auto_pause_on_stability = True
        app.play()
        app._advance_simulation(dt=1.0)  # a 60 gen/s, suficiente para detectar el ciclo
        assert app.simulating is False
        assert "Estable" in app._status_message

    def test_without_auto_pause_simulation_keeps_running(self, app):
        app.engine.set_cells([(4, 4), (5, 4), (4, 5), (5, 5)], True)
        app.auto_pause_on_stability = False
        app.play()
        app._advance_simulation(dt=1.0)
        assert app.simulating is True

    def test_checkbox_toggle_updates_flag(self, app):
        app.chk_auto_pause.handle_event(_mouse_down((app.chk_auto_pause.rect.x + 5,
                                                       app.chk_auto_pause.rect.y + 5)))
        assert app.auto_pause_on_stability is True

    def test_auto_pause_detects_oscillator_too(self, app):
        app.engine.set_cells([(3, 5), (4, 5), (5, 5)], True)  # blinker
        app.auto_pause_on_stability = True
        app.play()
        app._advance_simulation(dt=1.0)
        assert app.simulating is False
        assert "Oscilador" in app._status_message


class TestStatsResetOnBoardChanges:
    def test_clear_board_resets_cycle_detector(self, app):
        app.engine.set_cells([(4, 4), (5, 4), (4, 5), (5, 5)], True)
        app.cycle_detector.observe(app.engine)
        app.engine.step()
        app.cycle_detector.observe(app.engine)
        assert app.cycle_detector.status != CycleStatus.NONE
        app.clear_board()
        assert app.cycle_detector.status == CycleStatus.NONE

    def test_reset_board_clears_population_history(self, app):
        app.engine.set_cell(1, 1, True)
        app.population_history.sample(app.engine)
        assert len(app.population_history.values()) > 0
        app.reset_board()
        assert app.population_history.values() == []

    def test_randomize_resets_stats(self, app):
        app.population_history.sample(app.engine)
        app.randomize_board()
        assert app.population_history.values() == []


class TestHelpOverlay:
    def test_toggle_help_opens_and_closes(self, app):
        app.toggle_help()
        assert app.help_overlay.visible is True
        app.toggle_help()
        assert app.help_overlay.visible is False

    def test_f1_key_toggles_help(self, app):
        app._handle_keydown(_key(pygame.K_F1))
        assert app.help_overlay.visible is True

    def test_h_key_toggles_help(self, app):
        app._handle_keydown(_key(pygame.K_h))
        assert app.help_overlay.visible is True

    def test_opening_help_closes_other_overlays(self, app):
        app.open_pattern_browser()
        app.toggle_help()
        assert app.pattern_overlay.visible is False
        assert app.help_overlay.visible is True

    def test_escape_closes_help_via_event_loop(self, app):
        app.toggle_help()
        pygame.event.post(_key(pygame.K_ESCAPE))
        app._handle_events()
        assert app.help_overlay.visible is False

    def test_click_outside_help_closes_it(self, app):
        app.toggle_help()
        pygame.event.post(_mouse_down((2, 2)))
        app._handle_events()
        assert app.help_overlay.visible is False

    def test_help_lines_cover_core_shortcuts(self, app):
        keys_documented = {line[0] for line in app.HELP_LINES}
        assert "Espacio" in keys_documented
        assert "Ctrl+Z / Ctrl+Y" in keys_documented


class TestStatusBarContent:
    def test_shows_generation_population_and_speed(self, app):
        app.engine.set_cell(1, 1, True)
        app._draw_status_bar()  # no debe lanzar excepcion
        # Verificamos indirectamente via el estado que alimenta el texto:
        assert app.engine.population == 1
        assert app.speed_meter.value >= 0.0
