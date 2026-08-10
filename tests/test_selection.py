from __future__ import annotations

import numpy as np
import pytest

from vida.selection import Clipboard, Selection, StampState, bresenham_line


class TestSelection:
    def test_start_sets_both_corners_to_same_point(self):
        sel = Selection()
        sel.start(5, 5)
        assert sel.x0 == sel.x1 == 5
        assert sel.y0 == sel.y1 == 5
        assert sel.active is True

    def test_update_moves_second_corner(self):
        sel = Selection()
        sel.start(2, 2)
        sel.update(8, 6)
        assert (sel.x0, sel.y0, sel.x1, sel.y1) == (2, 2, 8, 6)

    def test_normalized_sorts_and_makes_end_exclusive(self):
        sel = Selection()
        sel.start(8, 6)
        sel.update(2, 2)
        assert sel.normalized() == (2, 2, 9, 7)

    def test_normalized_single_cell_selection(self):
        sel = Selection()
        sel.start(3, 3)
        assert sel.normalized() == (3, 3, 4, 4)

    def test_clear_deactivates(self):
        sel = Selection()
        sel.start(1, 1)
        sel.clear()
        assert sel.active is False
        assert sel.is_empty is True

    def test_is_empty_when_never_started(self):
        sel = Selection()
        assert sel.is_empty is True


class TestStampState:
    def test_inactive_without_pattern(self):
        stamp = StampState()
        assert stamp.active is False

    def test_set_pattern_activates(self):
        stamp = StampState()
        stamp.set_pattern(np.array([[1, 0], [0, 1]]), name="Prueba")
        assert stamp.active is True
        assert stamp.name == "Prueba"

    def test_clear_deactivates(self):
        stamp = StampState()
        stamp.set_pattern(np.array([[1]]))
        stamp.clear()
        assert stamp.active is False
        assert stamp.grid is None

    def test_move_to_updates_position(self):
        stamp = StampState()
        stamp.move_to(10, 20)
        assert (stamp.x, stamp.y) == (10, 20)

    def test_rotate_glider_matches_manual_rotation(self):
        glider = np.array([[0, 1, 0], [0, 0, 1], [1, 1, 1]], dtype=np.uint8)
        stamp = StampState()
        stamp.set_pattern(glider)
        stamp.rotate()
        expected = np.rot90(glider, k=-1)
        assert np.array_equal(stamp.grid, expected)

    def test_rotate_four_times_returns_to_original(self):
        pattern = np.array([[1, 0, 0], [1, 1, 0]], dtype=np.uint8)
        stamp = StampState()
        stamp.set_pattern(pattern)
        for _ in range(4):
            stamp.rotate()
        assert np.array_equal(stamp.grid, pattern)

    def test_flip_horizontal(self):
        pattern = np.array([[1, 0], [0, 0]], dtype=np.uint8)
        stamp = StampState()
        stamp.set_pattern(pattern)
        stamp.flip_horizontal()
        assert np.array_equal(stamp.grid, np.array([[0, 1], [0, 0]]))

    def test_flip_vertical(self):
        pattern = np.array([[1, 0], [0, 0]], dtype=np.uint8)
        stamp = StampState()
        stamp.set_pattern(pattern)
        stamp.flip_vertical()
        assert np.array_equal(stamp.grid, np.array([[0, 0], [1, 0]]))

    def test_flip_twice_returns_to_original(self):
        pattern = np.array([[1, 0, 1], [0, 1, 0]], dtype=np.uint8)
        stamp = StampState()
        stamp.set_pattern(pattern)
        stamp.flip_horizontal()
        stamp.flip_horizontal()
        assert np.array_equal(stamp.grid, pattern)


class TestClipboard:
    def test_empty_by_default(self):
        cb = Clipboard()
        assert cb.has_content is False

    def test_set_with_all_dead_cells_has_no_content(self):
        cb = Clipboard()
        cb.set(np.zeros((3, 3), dtype=np.uint8))
        assert cb.has_content is False

    def test_set_with_alive_cells_has_content(self):
        cb = Clipboard()
        cb.set(np.array([[0, 1], [0, 0]], dtype=np.uint8))
        assert cb.has_content is True

    def test_clear_empties_clipboard(self):
        cb = Clipboard()
        cb.set(np.array([[1]], dtype=np.uint8))
        cb.clear()
        assert cb.has_content is False
        assert cb.grid is None

    def test_set_copies_array_defensively(self):
        original = np.array([[1, 0]], dtype=np.uint8)
        cb = Clipboard()
        cb.set(original)
        original[0, 0] = 0
        assert cb.grid[0, 0] == 1


class TestBresenhamLine:
    def test_horizontal_line_includes_all_points(self):
        assert bresenham_line(0, 0, 4, 0) == [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]

    def test_vertical_line_includes_all_points(self):
        assert bresenham_line(0, 0, 0, 3) == [(0, 0), (0, 1), (0, 2), (0, 3)]

    def test_single_point_when_start_equals_end(self):
        assert bresenham_line(5, 5, 5, 5) == [(5, 5)]

    def test_diagonal_line(self):
        assert bresenham_line(0, 0, 3, 3) == [(0, 0), (1, 1), (2, 2), (3, 3)]

    def test_line_has_no_gaps_steep_slope(self):
        points = bresenham_line(0, 0, 2, 10)
        ys = [p[1] for p in points]
        assert ys == list(range(11))  # todas las filas 0..10 presentes, sin huecos

    def test_line_is_symmetric_regardless_of_direction(self):
        forward = bresenham_line(1, 1, 8, 5)
        backward = bresenham_line(8, 5, 1, 1)
        assert set(forward) == set(backward)

    def test_negative_coordinates_supported(self):
        points = bresenham_line(-3, -3, 2, 2)
        assert (-3, -3) in points and (2, 2) in points
        assert len(points) == 6
