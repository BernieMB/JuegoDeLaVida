from __future__ import annotations

import pytest

from vida.camera import Camera


def _make_camera(**kwargs) -> Camera:
    defaults = dict(grid_width=200, grid_height=200, viewport_width=800, viewport_height=600)
    defaults.update(kwargs)
    return Camera(**defaults)


class TestTransforms:
    def test_world_to_screen_basic(self):
        cam = _make_camera(cell_size=10, offset_x=0, offset_y=0)
        assert cam.world_to_screen(0, 0) == (0, 0)
        assert cam.world_to_screen(5, 3) == (50, 30)

    def test_world_to_screen_respects_offset(self):
        cam = _make_camera(cell_size=10, offset_x=2, offset_y=1)
        assert cam.world_to_screen(2, 1) == (0, 0)
        assert cam.world_to_screen(3, 1) == (10, 0)

    def test_screen_to_world_is_inverse_of_world_to_screen(self):
        cam = _make_camera(cell_size=7, offset_x=3.5, offset_y=-2)
        sx, sy = cam.world_to_screen(12.3, 8.1)
        wx, wy = cam.screen_to_world(sx, sy)
        assert wx == pytest.approx(12.3)
        assert wy == pytest.approx(8.1)

    def test_screen_to_cell_floors(self):
        cam = _make_camera(cell_size=10, offset_x=0, offset_y=0)
        assert cam.screen_to_cell(25, 35) == (2, 3)
        assert cam.screen_to_cell(0, 0) == (0, 0)
        assert cam.screen_to_cell(-5, -5) == (-1, -1)


class TestZoom:
    def test_zoom_keeps_cursor_point_fixed(self):
        cam = _make_camera(cell_size=8, offset_x=10, offset_y=10)
        cursor = (300, 200)
        wx_before, wy_before = cam.screen_to_world(*cursor)
        cam.zoom_at(*cursor, factor=2.0)
        wx_after, wy_after = cam.screen_to_world(*cursor)
        assert wx_after == pytest.approx(wx_before, abs=1e-9)
        assert wy_after == pytest.approx(wy_before, abs=1e-9)
        assert cam.cell_size == pytest.approx(16.0)

    def test_zoom_out_keeps_cursor_point_fixed(self):
        cam = _make_camera(cell_size=8, offset_x=10, offset_y=10)
        cursor = (150, 90)
        wx_before, wy_before = cam.screen_to_world(*cursor)
        cam.zoom_at(*cursor, factor=0.5)
        wx_after, wy_after = cam.screen_to_world(*cursor)
        assert wx_after == pytest.approx(wx_before, abs=1e-9)
        assert wy_after == pytest.approx(wy_before, abs=1e-9)

    def test_zoom_clamped_to_bounds(self):
        cam = _make_camera(cell_size=8)
        cam.zoom_at(0, 0, factor=1000)
        assert cam.cell_size == Camera.MAX_CELL_SIZE
        cam.zoom_at(0, 0, factor=0.0001)
        assert cam.cell_size == pytest.approx(cam.min_cell_size)


class TestPan:
    def test_pan_pixels_moves_offset(self):
        cam = _make_camera(cell_size=10, offset_x=0, offset_y=0)
        cam.pan_pixels(50, 20)
        assert cam.offset_x == pytest.approx(-5.0)
        assert cam.offset_y == pytest.approx(-2.0)

    def test_pan_cells_moves_offset_directly(self):
        cam = _make_camera(cell_size=10, offset_x=5, offset_y=5)
        cam.pan_cells(2, -3)
        assert cam.offset_x == pytest.approx(7.0)
        assert cam.offset_y == pytest.approx(2.0)


class TestFitAndVisibleRect:
    def test_min_cell_size_is_exact_fit(self):
        cam = _make_camera(grid_width=200, grid_height=100,
                           viewport_width=800, viewport_height=600)
        assert cam.min_cell_size == pytest.approx(4.0)

    def test_zoom_out_at_minimum_centers_and_shows_whole_grid(self):
        cam = _make_camera(cell_size=8)
        cam.pan_cells(50, 25)
        cam.zoom_at(400, 300, factor=0.0001)
        assert cam.cell_size == pytest.approx(cam.min_cell_size)
        x0, y0, x1, y1 = cam.visible_cell_rect()
        assert x0 == 0 and y0 == 0
        assert x1 == cam.grid_width and y1 == cam.grid_height

    def test_fit_to_grid_is_not_capped_for_huge_grid(self):
        cam = _make_camera(grid_width=5000, grid_height=5000,
                           viewport_width=800, viewport_height=600)
        cam.fit_to_grid(margin=1.0)
        assert cam.cell_size == pytest.approx(0.12)
        assert cam.cell_size < 0.5
        x0, y0, x1, y1 = cam.visible_cell_rect()
        assert x0 == 0 and y0 == 0
        assert x1 == cam.grid_width and y1 == cam.grid_height

    def test_resize_viewport_reclamps_cell_size(self):
        cam = _make_camera(cell_size=3.0)
        cam.resize_viewport(1600, 1200)
        assert cam.cell_size == pytest.approx(cam.min_cell_size)

    def test_fit_to_grid_shows_whole_grid(self):
        cam = _make_camera(grid_width=200, grid_height=200,
                            viewport_width=800, viewport_height=600)
        cam.fit_to_grid(margin=1.0)
        x0, y0, x1, y1 = cam.visible_cell_rect()
        assert x0 == 0 and y0 == 0
        assert x1 >= 199 and y1 >= 199

    def test_visible_cell_rect_clips_to_grid_bounds(self):
        cam = _make_camera(grid_width=50, grid_height=50, cell_size=8,
                            offset_x=-10, offset_y=-10)
        x0, y0, x1, y1 = cam.visible_cell_rect()
        assert x0 >= 0 and y0 >= 0
        assert x1 <= 50 and y1 <= 50

    def test_show_grid_lines_threshold(self):
        cam = _make_camera(cell_size=Camera.GRID_LINES_MIN_CELL_SIZE - 0.1)
        assert cam.show_grid_lines is False
        cam.cell_size = Camera.GRID_LINES_MIN_CELL_SIZE + 0.1
        assert cam.show_grid_lines is True

    def test_resize_viewport_updates_dimensions(self):
        cam = _make_camera()
        cam.resize_viewport(1024, 768)
        assert cam.viewport_width == 1024
        assert cam.viewport_height == 768
