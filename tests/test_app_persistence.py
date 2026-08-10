from __future__ import annotations

import pygame
import pytest

from vida.app import App


@pytest.fixture()
def app(tmp_path):
    application = App(width=40, height=40, window_size=(900, 600),
                       patterns_dir=tmp_path / "patterns")
    application.camera.cell_size = 10
    application.camera.offset_x = 0
    application.camera.offset_y = 0
    return application


def _mouse_down(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


def _key(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="")


class TestSaveBoard:
    def test_save_board_creates_file_and_sets_status(self, app):
        app.engine.set_cells([(1, 1), (2, 1), (1, 2)], True)
        app.save_board_to_file()
        files = list(app.patterns_dir.glob("*.rle"))
        assert len(files) == 1
        assert "guardado" in app._status_message.lower()

    def test_ctrl_s_saves_board(self, app):
        app.engine.set_cell(1, 1, True)
        app._handle_keydown(_key(pygame.K_s, mod=pygame.KMOD_CTRL))
        assert len(list(app.patterns_dir.glob("*.rle"))) == 1


class TestSaveSelection:
    def test_save_selection_creates_file_with_only_that_region(self, app):
        app.engine.set_cells([(5, 5), (20, 20)], True)
        app.selection.start(5, 5)
        app.selection.update(6, 6)
        app.save_selection_to_file()
        files = list(app.patterns_dir.glob("seleccion_*.rle"))
        assert len(files) == 1
        from vida.persistence import load_pattern_file
        pattern = load_pattern_file(files[0])
        assert pattern.population == 1

    def test_save_selection_without_selection_sets_warning_status(self, app):
        app.save_selection_to_file()
        assert len(list(app.patterns_dir.glob("*.rle"))) == 0
        assert "seleccion" in app._status_message.lower()

    def test_ctrl_shift_s_saves_selection(self, app):
        app.engine.set_cell(5, 5, True)
        app.selection.start(5, 5)
        app.selection.update(5, 5)
        app._handle_keydown(_key(pygame.K_s, mod=pygame.KMOD_CTRL | pygame.KMOD_SHIFT))
        assert len(list(app.patterns_dir.glob("seleccion_*.rle"))) == 1


class TestFileBrowser:
    def test_open_file_browser_lists_saved_files(self, app):
        app.engine.set_cell(1, 1, True)
        app.save_board_to_file()
        app.open_file_browser()
        assert app.file_browser_overlay.visible is True
        assert len(app.file_list.items) == 1

    def test_opening_file_browser_closes_pattern_browser(self, app):
        app.open_pattern_browser()
        app.open_file_browser()
        assert app.pattern_overlay.visible is False
        assert app.file_browser_overlay.visible is True

    def test_opening_pattern_browser_closes_file_browser(self, app):
        app.open_file_browser()
        app.open_pattern_browser()
        assert app.file_browser_overlay.visible is False
        assert app.pattern_overlay.visible is True

    def test_select_and_load_as_stamp(self, app):
        app.engine.set_cells([(1, 1), (2, 1)], True)
        app.save_board_to_file()
        app.clear_board()
        app.open_file_browser()
        app._on_file_selected(0, app.file_list.items[0])
        app.load_selected_as_stamp()
        assert app.stamp.active is True
        assert app.file_browser_overlay.visible is False

    def test_select_and_load_as_board_replaces_grid(self, app):
        app.engine.set_cells([(1, 1), (2, 1)], True)
        app.save_board_to_file()
        app.clear_board()
        app.open_file_browser()
        app._on_file_selected(0, app.file_list.items[0])
        app.load_selected_as_board()
        assert app.engine.population == 2
        assert app.file_browser_overlay.visible is False

    def test_load_as_board_switches_rule_if_specified(self, app, tmp_path):
        (app.patterns_dir).mkdir(parents=True, exist_ok=True)
        custom = app.patterns_dir / "highlife.rle"
        custom.write_text("x = 2, y = 1, rule = B36/S23\n2o!\n", encoding="utf-8")
        app.open_file_browser()
        app._on_file_selected(app.file_list.items.index("highlife.rle"), "highlife.rle")
        app.load_selected_as_board()
        assert app.engine.rule.rulestring == "B36/S23"

    def test_load_as_board_is_undoable(self, app):
        app.engine.set_cell(1, 1, True)
        app.save_board_to_file()
        app.clear_board()
        app.open_file_browser()
        app._on_file_selected(0, app.file_list.items[0])
        app.load_selected_as_board()
        assert app.engine.population == 1
        app.undo()
        assert app.engine.population == 0

    def test_refresh_updates_after_new_save(self, app):
        app.open_file_browser()
        assert len(app.file_list.items) == 0
        app.engine.set_cell(1, 1, True)
        app.save_board_to_file()
        app.refresh_file_list()
        assert len(app.file_list.items) == 1

    def test_click_outside_file_browser_closes_it(self, app):
        app.open_file_browser()
        pygame.event.post(_mouse_down((5, 5)))
        app._handle_events()
        assert app.file_browser_overlay.visible is False
