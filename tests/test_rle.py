from __future__ import annotations

import numpy as np
import pytest

from vida.rle import (
    Pattern,
    RLEParseError,
    coords_to_grid,
    parse_auto,
    parse_plaintext,
    parse_rle,
    serialize_plaintext,
    serialize_rle,
)


GLIDER_RLE = """#N Glider
#C El planeador mas pequeno y comun, se desplaza en diagonal.
#O Richard K. Guy, 1970
x = 3, y = 3, rule = B3/S23
bob$2bo$3o!
"""


class TestParseRLE:
    def test_parses_header_metadata(self):
        pattern = parse_rle(GLIDER_RLE)
        assert pattern.name == "Glider"
        assert "planeador" in pattern.comment
        assert pattern.author == "Richard K. Guy, 1970"
        assert pattern.rule == "B3/S23"
        assert pattern.width == 3
        assert pattern.height == 3

    def test_parses_cells_correctly(self):
        pattern = parse_rle(GLIDER_RLE)
        expected = np.array(
            [[0, 1, 0], [0, 0, 1], [1, 1, 1]], dtype=np.uint8
        )
        assert np.array_equal(pattern.cells, expected)

    def test_population_matches_glider(self):
        pattern = parse_rle(GLIDER_RLE)
        assert pattern.population == 5

    def test_missing_header_raises(self):
        with pytest.raises(RLEParseError):
            parse_rle("bob$2bo$3o!")

    def test_rule_defaults_to_conway_when_absent(self):
        text = "x = 1, y = 1\no!"
        pattern = parse_rle(text)
        assert pattern.rule == "B3/S23"

    def test_repeated_dollar_produces_blank_rows(self):
        # row0 = "obo"; luego "3$" avanza 3 filas (0 -> 3), dejando en blanco
        # las filas 1 y 2; row3 = "obo" de nuevo; row4 nunca se toca (blanco).
        text = "x = 3, y = 5, rule = B3/S23\nobo3$obo!"
        pattern = parse_rle(text)
        assert pattern.height == 5
        assert pattern.cells[0].tolist() == [1, 0, 1]
        assert pattern.cells[1].sum() == 0
        assert pattern.cells[2].sum() == 0
        assert pattern.cells[3].tolist() == [1, 0, 1]
        assert pattern.cells[4].sum() == 0

    def test_run_length_counts_are_applied(self):
        text = "x = 6, y = 1, rule = B3/S23\n3o3b!"
        pattern = parse_rle(text)
        assert pattern.cells[0].tolist() == [1, 1, 1, 0, 0, 0]

    def test_ignores_whitespace_and_newlines_inside_data(self):
        text = "x = 3, y = 3, rule = B3/S23\nbo b $ \n 2bo $ 3o !"
        pattern = parse_rle(text)
        expected = np.array(
            [[0, 1, 0], [0, 0, 1], [1, 1, 1]], dtype=np.uint8
        )
        assert np.array_equal(pattern.cells, expected)

    def test_swapped_bs_order_header_rule_still_parsed(self):
        text = "x = 3, y = 1, rule = B36/S23\n3o!"
        pattern = parse_rle(text)
        assert pattern.rule == "B36/S23"


class TestSerializeRLE:
    def test_roundtrip_preserves_grid_for_random_patterns(self):
        rng = np.random.default_rng(0)
        for trial in range(10):
            h, w = rng.integers(1, 20), rng.integers(1, 20)
            grid = (rng.random((h, w)) < 0.4).astype(np.uint8)
            text = serialize_rle(grid, rule="B3/S23")
            parsed = parse_rle(text)
            assert np.array_equal(parsed.cells, grid), f"fallo en trial {trial}"

    def test_roundtrip_preserves_metadata(self):
        grid = np.array([[0, 1, 0], [0, 0, 1], [1, 1, 1]], dtype=np.uint8)
        text = serialize_rle(grid, name="Glider", author="R. Guy",
                              comment="linea 1\nlinea 2", rule="B3/S23")
        parsed = parse_rle(text)
        assert parsed.name == "Glider"
        assert parsed.author == "R. Guy"
        assert "linea 1" in parsed.comment and "linea 2" in parsed.comment
        assert np.array_equal(parsed.cells, grid)

    def test_roundtrip_pattern_object(self):
        grid = np.array([[1, 1], [1, 1]], dtype=np.uint8)
        pattern = Pattern(cells=grid, name="Block", rule="B3/S23")
        text = serialize_rle(pattern)
        parsed = parse_rle(text)
        assert parsed.name == "Block"
        assert np.array_equal(parsed.cells, grid)

    def test_all_dead_grid_serializes_and_parses(self):
        grid = np.zeros((4, 4), dtype=np.uint8)
        text = serialize_rle(grid)
        parsed = parse_rle(text)
        assert np.array_equal(parsed.cells, grid)

    def test_long_rows_are_wrapped_but_still_parse(self):
        grid = np.ones((2, 200), dtype=np.uint8)
        text = serialize_rle(grid, line_width=70)
        assert any(len(line) <= 72 for line in text.splitlines())
        parsed = parse_rle(text)
        assert np.array_equal(parsed.cells, grid)

    def test_custom_rule_is_preserved(self):
        grid = np.array([[1, 0], [0, 1]], dtype=np.uint8)
        text = serialize_rle(grid, rule="B36/S23")
        assert "rule = B36/S23" in text
        assert parse_rle(text).rule == "B36/S23"


class TestPlaintext:
    def test_parse_plaintext_basic(self):
        text = "!Name: Glider\n!Comentario\n.O.\n..O\nOOO\n"
        pattern = parse_plaintext(text)
        assert pattern.name == "Glider"
        expected = np.array([[0, 1, 0], [0, 0, 1], [1, 1, 1]], dtype=np.uint8)
        assert np.array_equal(pattern.cells, expected)

    def test_serialize_plaintext_roundtrip(self):
        grid = np.array([[0, 1, 0], [0, 0, 1], [1, 1, 1]], dtype=np.uint8)
        text = serialize_plaintext(grid, name="Glider")
        parsed = parse_plaintext(text)
        assert np.array_equal(parsed.cells, grid)
        assert parsed.name == "Glider"

    def test_plaintext_pads_ragged_rows(self):
        text = ".O\nOOO\n.O\n"
        pattern = parse_plaintext(text)
        assert pattern.width == 3
        assert pattern.height == 3


class TestParseAuto:
    def test_detects_rle(self):
        pattern = parse_auto(GLIDER_RLE)
        assert pattern.name == "Glider"

    def test_detects_plaintext(self):
        text = "!Name: Block\n.OO.\n.OO.\n"
        pattern = parse_auto(text)
        assert pattern.name == "Block"
        assert pattern.width == 4


class TestCoordsToGrid:
    def test_basic_bounding_box(self):
        coords = [(2, 2), (3, 2), (2, 3)]
        grid = coords_to_grid(coords)
        assert grid.shape == (2, 2)
        assert grid.tolist() == [[1, 1], [1, 0]]

    def test_empty_coords_returns_empty_grid(self):
        grid = coords_to_grid([])
        assert grid.shape == (0, 0)

    def test_single_cell(self):
        grid = coords_to_grid([(5, 5)])
        assert grid.shape == (1, 1)
        assert grid[0, 0] == 1
