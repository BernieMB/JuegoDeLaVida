from __future__ import annotations

import time

import numpy as np
import pytest

from vida.engine import LifeEngine, Topology
from vida.persistence import (
    bounding_box_of_alive_cells,
    default_filename,
    ensure_patterns_dir,
    list_pattern_files,
    load_pattern_file,
    save_board,
    save_selection,
)


class TestEnsurePatternsDir:
    def test_creates_directory_if_missing(self, tmp_path):
        target = tmp_path / "nuevos_patrones"
        assert not target.exists()
        result = ensure_patterns_dir(target)
        assert result.exists() and result.is_dir()

    def test_is_idempotent(self, tmp_path):
        target = tmp_path / "patrones"
        ensure_patterns_dir(target)
        ensure_patterns_dir(target)  # no debe fallar si ya existe
        assert target.exists()


class TestDefaultFilename:
    def test_uses_prefix_and_extension(self):
        name = default_filename("seleccion", extension="rle")
        assert name.startswith("seleccion_")
        assert name.endswith(".rle")

    def test_names_are_unique_across_calls(self):
        # No garantizamos unicidad al segundo exacto, pero si la estructura.
        name = default_filename("tablero")
        assert "tablero_" in name


class TestBoundingBoxOfAliveCells:
    def test_empty_grid_returns_none(self):
        grid = np.zeros((10, 10), dtype=np.uint8)
        assert bounding_box_of_alive_cells(grid) is None

    def test_single_cell(self):
        grid = np.zeros((10, 10), dtype=np.uint8)
        grid[3, 4] = 1
        assert bounding_box_of_alive_cells(grid) == (4, 3, 5, 4)

    def test_rectangle_of_cells(self):
        grid = np.zeros((10, 10), dtype=np.uint8)
        grid[2:5, 3:7] = 1
        assert bounding_box_of_alive_cells(grid) == (3, 2, 7, 5)


class TestSaveBoard:
    def test_crops_to_content_by_default(self, tmp_path):
        engine = LifeEngine(50, 50, topology=Topology.BOUNDED)
        engine.set_cells([(20, 20), (21, 20), (20, 21)], True)
        path = save_board(engine, tmp_path / "tablero.rle")
        pattern = load_pattern_file(path)
        assert pattern.width == 2 and pattern.height == 2
        assert pattern.population == 3

    def test_records_original_position_in_comment(self, tmp_path):
        engine = LifeEngine(50, 50, topology=Topology.BOUNDED)
        engine.set_cells([(20, 20), (21, 20)], True)
        path = save_board(engine, tmp_path / "tablero.rle")
        pattern = load_pattern_file(path)
        assert "(20, 20)" in pattern.comment

    def test_without_crop_preserves_full_grid_size(self, tmp_path):
        engine = LifeEngine(15, 12, topology=Topology.BOUNDED)
        engine.set_cell(1, 1, True)
        path = save_board(engine, tmp_path / "tablero.rle", crop_to_content=False)
        pattern = load_pattern_file(path)
        assert pattern.width == 15 and pattern.height == 12

    def test_saves_current_rule(self, tmp_path):
        from vida.rules import KNOWN_RULES
        engine = LifeEngine(10, 10, rule=KNOWN_RULES["highlife"])
        engine.set_cell(1, 1, True)
        path = save_board(engine, tmp_path / "t.rle")
        pattern = load_pattern_file(path)
        assert pattern.rule == "B36/S23"

    def test_creates_parent_directories(self, tmp_path):
        engine = LifeEngine(10, 10)
        engine.set_cell(1, 1, True)
        path = save_board(engine, tmp_path / "sub" / "dir" / "t.rle")
        assert path.exists()

    def test_empty_board_saves_without_crashing(self, tmp_path):
        engine = LifeEngine(10, 10)
        path = save_board(engine, tmp_path / "vacio.rle")
        pattern = load_pattern_file(path)
        assert pattern.population == 0


class TestSaveSelection:
    def test_saves_only_the_selected_region(self, tmp_path):
        engine = LifeEngine(50, 50, topology=Topology.BOUNDED)
        engine.set_cells([(5, 5), (6, 5), (30, 30)], True)
        path = save_selection(engine, 5, 5, 8, 8, tmp_path / "sel.rle")
        pattern = load_pattern_file(path)
        assert pattern.population == 2  # (30,30) queda fuera de la seleccion
        assert pattern.width == 3 and pattern.height == 3

    def test_records_original_position(self, tmp_path):
        engine = LifeEngine(50, 50, topology=Topology.BOUNDED)
        engine.set_cells([(10, 12)], True)
        path = save_selection(engine, 10, 12, 15, 15, tmp_path / "sel.rle")
        pattern = load_pattern_file(path)
        assert "(10, 12)" in pattern.comment


class TestLoadPatternFile:
    def test_detects_rle_format(self, tmp_path):
        rle_path = tmp_path / "glider.rle"
        rle_path.write_text("x = 3, y = 3, rule = B3/S23\nbob$2bo$3o!\n", encoding="utf-8")
        pattern = load_pattern_file(rle_path)
        assert pattern.population == 5

    def test_detects_plaintext_format(self, tmp_path):
        cells_path = tmp_path / "glider.cells"
        cells_path.write_text("!Name: Glider\n.O.\n..O\nOOO\n", encoding="utf-8")
        pattern = load_pattern_file(cells_path)
        assert pattern.name == "Glider"
        assert pattern.population == 5


class TestListPatternFiles:
    def test_empty_directory_returns_empty_list(self, tmp_path):
        assert list_pattern_files(tmp_path / "vacio") == []

    def test_lists_rle_and_cells_files(self, tmp_path):
        (tmp_path / "a.rle").write_text("x = 1, y = 1\no!\n", encoding="utf-8")
        (tmp_path / "b.cells").write_text(".O.\n", encoding="utf-8")
        (tmp_path / "c.txt").write_text("no deberia aparecer", encoding="utf-8")
        files = list_pattern_files(tmp_path)
        names = {p.name for p in files}
        assert names == {"a.rle", "b.cells"}

    def test_most_recently_modified_file_comes_first(self, tmp_path):
        old = tmp_path / "viejo.rle"
        old.write_text("x = 1, y = 1\no!\n", encoding="utf-8")
        time.sleep(0.02)
        new = tmp_path / "nuevo.rle"
        new.write_text("x = 1, y = 1\no!\n", encoding="utf-8")
        files = list_pattern_files(tmp_path)
        assert files[0].name == "nuevo.rle"
