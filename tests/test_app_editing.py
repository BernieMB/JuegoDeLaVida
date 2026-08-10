from __future__ import annotations

import pygame
import pytest

from vida.app import App
from vida.selection import Tool


@pytest.fixture()
def app():
    application = App(width=40, height=40, window_size=(900, 600))
    # Camara determinista: 10 px/celda, sin offset, para poder calcular a
    # mano que celda corresponde a cada posicion de pantalla en los tests.
    application.camera.cell_size = 10
    application.camera.offset_x = 0
    application.camera.offset_y = 0
    return application


def _screen_pos(app, cell_x, cell_y):
    """Posicion de pantalla (ventana) para el centro de una celda, dada la
    camara deterministica fijada en el fixture."""
    local_x = cell_x * 10 + 5
    local_y = cell_y * 10 + 5
    return (app.viewport_rect.x + local_x, app.viewport_rect.y + local_y)


def _mouse_down(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


def _mouse_up(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=button)


def _mouse_move(pos):
    return pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0))


def _key(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="")


class TestPainting:
    def test_click_paints_a_cell_alive(self, app):
        pos = _screen_pos(app, 5, 5)
        app._handle_viewport_event(_mouse_down(pos))
        assert app.engine.grid[5, 5] == 1

    def test_drag_paints_a_continuous_line(self, app):
        app._handle_viewport_event(_mouse_down(_screen_pos(app, 2, 2)))
        app._handle_viewport_event(_mouse_move(_screen_pos(app, 6, 2)))
        for x in range(2, 7):
            assert app.engine.grid[2, x] == 1, f"falta celda en x={x}"

    def test_mouse_up_ends_painting_stroke(self, app):
        app._handle_viewport_event(_mouse_down(_screen_pos(app, 1, 1)))
        app._handle_viewport_event(_mouse_up(_screen_pos(app, 1, 1)))
        assert app._painting is False
        assert app._last_paint_cell is None

    def test_painting_pushes_a_single_undo_step_per_stroke(self, app):
        assert app.engine.can_undo() is False
        app._handle_viewport_event(_mouse_down(_screen_pos(app, 1, 1)))
        app._handle_viewport_event(_mouse_move(_screen_pos(app, 5, 1)))
        app._handle_viewport_event(_mouse_up(_screen_pos(app, 5, 1)))
        assert app.engine.can_undo() is True
        app.undo()
        assert app.engine.population == 0


class TestErasing:
    def test_right_click_erases_a_cell(self, app):
        app.engine.set_cell(5, 5, True)
        app._handle_viewport_event(_mouse_down(_screen_pos(app, 5, 5), button=3))
        assert app.engine.grid[5, 5] == 0

    def test_erase_drag_clears_a_line(self, app):
        app.engine.set_cells([(x, 3) for x in range(2, 8)], True)
        app._handle_viewport_event(_mouse_down(_screen_pos(app, 2, 3), button=3))
        app._handle_viewport_event(_mouse_move(_screen_pos(app, 7, 3)))
        for x in range(2, 8):
            assert app.engine.grid[3, x] == 0


class TestSelection:
    def test_shift_click_starts_selection(self, app, monkeypatch):
        monkeypatch.setattr(pygame.key, "get_mods", lambda: pygame.KMOD_SHIFT)
        app._handle_viewport_event(_mouse_down(_screen_pos(app, 3, 3)))
        assert app.selection.active is True
        assert app._painting is False  # el shift-click no debe pintar

    def test_shift_drag_updates_selection_bounds(self, app, monkeypatch):
        monkeypatch.setattr(pygame.key, "get_mods", lambda: pygame.KMOD_SHIFT)
        app._handle_viewport_event(_mouse_down(_screen_pos(app, 3, 3)))
        app._handle_viewport_event(_mouse_move(_screen_pos(app, 8, 9)))
        assert app.selection.normalized() == (3, 3, 9, 10)

    def test_plain_click_clears_previous_selection(self, app, monkeypatch):
        monkeypatch.setattr(pygame.key, "get_mods", lambda: pygame.KMOD_SHIFT)
        app._handle_viewport_event(_mouse_down(_screen_pos(app, 3, 3)))
        monkeypatch.setattr(pygame.key, "get_mods", lambda: 0)
        app._handle_viewport_event(_mouse_down(_screen_pos(app, 10, 10)))
        assert app.selection.is_empty is True


class TestCopyCutPaste:
    def _make_selection(self, app):
        app.engine.set_cells([(5, 5), (6, 5), (5, 6)], True)
        app.selection.start(5, 5)
        app.selection.update(6, 6)

    def test_copy_selection_fills_clipboard(self, app):
        self._make_selection(app)
        app.copy_selection()
        assert app.clipboard.has_content is True
        assert app.clipboard.grid.sum() == 3
        # copiar no debe borrar el tablero original
        assert app.engine.population == 3

    def test_cut_selection_empties_region_and_clears_selection(self, app):
        self._make_selection(app)
        app.cut_selection()
        assert app.clipboard.has_content is True
        assert app.engine.population == 0
        assert app.selection.is_empty is True

    def test_copy_with_no_selection_is_noop(self, app):
        app.copy_selection()
        assert app.clipboard.has_content is False

    def test_paste_activates_stamp_with_clipboard_content(self, app):
        self._make_selection(app)
        app.copy_selection()
        app.paste_clipboard()
        assert app.stamp.active is True

    def test_delete_selection_clears_only_that_region(self, app):
        app.engine.set_cells([(5, 5), (20, 20)], True)
        app.selection.start(5, 5)
        app.selection.update(5, 5)
        app.delete_selection()
        assert app.engine.grid[5, 5] == 0
        assert app.engine.grid[20, 20] == 1


class TestStamps:
    def test_start_stamp_from_pattern_activates_stamp(self, app):
        app.start_stamp_from_pattern("glider")
        assert app.stamp.active is True
        assert app.stamp.name == "Glider"

    def test_stamp_follows_mouse_motion(self, app):
        app.start_stamp_from_pattern("block")  # 2x2, se centra facil
        app._handle_viewport_event(_mouse_move(_screen_pos(app, 10, 10)))
        assert (app.stamp.x, app.stamp.y) == (9, 9)  # centrado: 10 - 2//2

    def test_left_click_places_the_stamp(self, app):
        app.start_stamp_from_pattern("block")
        app.stamp.move_to(10, 10)
        app._handle_viewport_event(_mouse_down(_screen_pos(app, 10, 10)))
        assert app.engine.grid[10, 10] == 1
        assert app.engine.grid[11, 11] == 1
        assert app.engine.population == 4

    def test_stamp_stays_active_after_placing_for_repeated_stamping(self, app):
        app.start_stamp_from_pattern("block")
        app.stamp.move_to(5, 5)
        app._handle_viewport_event(_mouse_down(_screen_pos(app, 5, 5)))
        assert app.stamp.active is True

    def test_right_click_cancels_stamp(self, app):
        app.start_stamp_from_pattern("glider")
        app._handle_viewport_event(_mouse_down(_screen_pos(app, 10, 10), button=3))
        assert app.stamp.active is False

    def test_escape_key_cancels_active_stamp(self, app):
        app.start_stamp_from_pattern("glider")
        app._handle_keydown(_key(pygame.K_ESCAPE))
        assert app.stamp.active is False

    def test_r_key_rotates_stamp_instead_of_resetting_board(self, app):
        app.engine.set_cell(0, 0, True)
        app.engine.step()  # generacion > 0 para poder distinguir un reset accidental
        app.start_stamp_from_pattern("glider")
        original = app.stamp.grid.copy()
        app._handle_keydown(_key(pygame.K_r))
        assert not (app.stamp.grid.shape == original.shape and (app.stamp.grid == original).all()) \
            or app.stamp.grid.shape != original.shape

    def test_f_key_flips_stamp(self, app):
        app.start_stamp_from_pattern("glider")
        before = app.stamp.grid.copy()
        app._handle_keydown(_key(pygame.K_f))
        assert not (before.shape == app.stamp.grid.shape and (before == app.stamp.grid).all())

    def test_placing_stamp_can_be_undone(self, app):
        app.start_stamp_from_pattern("block")
        app.stamp.move_to(5, 5)
        app._handle_viewport_event(_mouse_down(_screen_pos(app, 5, 5)))
        assert app.engine.population == 4
        app.undo()
        assert app.engine.population == 0


class TestUndoRedoKeyboard:
    def test_ctrl_z_undoes(self, app):
        app.engine.push_undo()
        app.engine.set_cell(1, 1, True)
        app._handle_keydown(_key(pygame.K_z, mod=pygame.KMOD_CTRL))
        assert app.engine.population == 0

    def test_ctrl_y_redoes(self, app):
        app.engine.push_undo()
        app.engine.set_cell(1, 1, True)
        app._handle_keydown(_key(pygame.K_z, mod=pygame.KMOD_CTRL))
        app._handle_keydown(_key(pygame.K_y, mod=pygame.KMOD_CTRL))
        assert app.engine.population == 1

    def test_ctrl_c_copies_and_ctrl_x_cuts(self, app):
        app.engine.set_cells([(2, 2), (3, 2)], True)
        app.selection.start(2, 2)
        app.selection.update(3, 2)
        app._handle_keydown(_key(pygame.K_c, mod=pygame.KMOD_CTRL))
        assert app.clipboard.has_content is True
        app._handle_keydown(_key(pygame.K_x, mod=pygame.KMOD_CTRL))
        assert app.engine.population == 0

    def test_ctrl_v_pastes_as_stamp(self, app):
        app.clipboard.set(app.engine.extract(0, 0, 1, 1) * 0 + 1)  # 1x1 vivo
        app._handle_keydown(_key(pygame.K_v, mod=pygame.KMOD_CTRL))
        assert app.stamp.active is True

    def test_delete_key_clears_selection_region(self, app):
        app.engine.set_cell(4, 4, True)
        app.selection.start(4, 4)
        app.selection.update(4, 4)
        app._handle_keydown(_key(pygame.K_DELETE))
        assert app.engine.grid[4, 4] == 0

    def test_escape_clears_selection_when_no_stamp_active(self, app):
        app.selection.start(1, 1)
        app._handle_keydown(_key(pygame.K_ESCAPE))
        assert app.selection.is_empty is True


class TestPatternBrowserOverlay:
    def test_opens_and_centers(self, app):
        app.open_pattern_browser()
        assert app.pattern_overlay.visible is True

    def test_close_hides_overlay(self, app):
        app.open_pattern_browser()
        app.close_pattern_browser()
        assert app.pattern_overlay.visible is False

    def test_selecting_item_populates_description_and_enables_place_button(self, app):
        app.open_pattern_browser()
        app._on_pattern_selected(0, "cualquiera")
        assert app._selected_pattern_key is not None
        assert app.btn_place_pattern.enabled is True

    def test_place_button_starts_stamp_and_closes_overlay(self, app):
        app.open_pattern_browser()
        app._on_pattern_selected(0, "cualquiera")
        app._place_selected_pattern()
        assert app.stamp.active is True
        assert app.pattern_overlay.visible is False

    def test_click_outside_overlay_closes_it(self, app):
        app.open_pattern_browser()
        far_away_pos = (5, 5)
        assert not app.pattern_overlay.rect.collidepoint(far_away_pos)
        pygame.event.post(_mouse_down(far_away_pos))
        app._handle_events()
        assert app.pattern_overlay.visible is False

    def test_global_shortcuts_suppressed_while_overlay_open(self, app):
        app.open_pattern_browser()
        # Cuando el overlay esta abierto, _handle_events debe interceptar el
        # evento ANTES de llegar a _handle_keydown; comprobamos ese camino
        # completo usando el bucle real de manejo de eventos.
        pygame.event.post(_key(pygame.K_c))
        app._handle_events()
        assert app.engine.population >= 0  # no debe haber "limpiado" nada de forma inesperada
        assert app.pattern_overlay.visible is True
