from __future__ import annotations

import numpy as np
import pygame
import pytest

from vida.camera import Camera
from vida.engine import LifeEngine, Topology
from vida.renderer import (
    BACKGROUND,
    CLASSIC_ALIVE,
    TRAIL_COLOR,
    ColorMode,
    Renderer,
    age_and_trail_for_region,
    compute_rgb,
    export_png,
    render_full_rgb,
)


@pytest.fixture(scope="module")
def _pygame_init():
    # El ciclo de vida real de pygame lo gestiona el fixture de sesion en
    # conftest.py (ver tests/conftest.py); no hace falta repetirlo aqui.
    yield


class TestComputeRGB:
    def test_dead_cell_is_background_in_classic_mode(self):
        grid = np.zeros((3, 3), dtype=np.uint8)
        rgb = compute_rgb(grid, ColorMode.CLASSIC)
        assert tuple(rgb[1, 1]) == BACKGROUND

    def test_alive_cell_is_classic_color(self):
        grid = np.array([[0, 0], [0, 1]], dtype=np.uint8)
        rgb = compute_rgb(grid, ColorMode.CLASSIC)
        assert tuple(rgb[1, 1]) == CLASSIC_ALIVE
        assert tuple(rgb[0, 0]) == BACKGROUND

    def test_age_mode_newborn_cell_is_young_color(self):
        grid = np.array([[1]], dtype=np.uint8)
        age = np.array([[0]], dtype=np.int64)
        trail = np.array([[0.0]], dtype=np.float32)
        rgb = compute_rgb(grid, ColorMode.AGE, age, trail)
        from vida.renderer import AGE_YOUNG
        assert tuple(int(v) for v in rgb[0, 0]) == AGE_YOUNG

    def test_age_mode_old_cell_tends_towards_old_color(self):
        grid = np.array([[1]], dtype=np.uint8)
        age = np.array([[10_000]], dtype=np.int64)  # muy por encima del cap
        trail = np.array([[0.0]], dtype=np.float32)
        rgb = compute_rgb(grid, ColorMode.AGE, age, trail)
        from vida.renderer import AGE_OLD
        assert tuple(int(v) for v in rgb[0, 0]) == AGE_OLD

    def test_age_mode_dead_cell_with_full_trail_is_trail_color(self):
        grid = np.array([[0]], dtype=np.uint8)
        age = np.array([[0]], dtype=np.int64)
        trail = np.array([[1.0]], dtype=np.float32)
        rgb = compute_rgb(grid, ColorMode.AGE, age, trail)
        assert tuple(int(v) for v in rgb[0, 0]) == TRAIL_COLOR

    def test_age_mode_dead_cell_with_no_trail_is_background(self):
        grid = np.array([[0]], dtype=np.uint8)
        age = np.array([[0]], dtype=np.int64)
        trail = np.array([[0.0]], dtype=np.float32)
        rgb = compute_rgb(grid, ColorMode.AGE, age, trail)
        assert tuple(int(v) for v in rgb[0, 0]) == BACKGROUND

    def test_classic_mode_ignores_age_and_trail_args(self):
        grid = np.array([[1]], dtype=np.uint8)
        rgb_with = compute_rgb(grid, ColorMode.CLASSIC,
                                np.array([[999]]), np.array([[1.0]]))
        rgb_without = compute_rgb(grid, ColorMode.CLASSIC)
        assert np.array_equal(rgb_with, rgb_without)


class TestAgeAndTrailForRegion:
    def test_matches_engine_full_grid_computation(self):
        engine = LifeEngine(20, 20, topology=Topology.BOUNDED)
        engine.set_cells([(5, 5), (6, 5), (5, 6)], True)
        engine.step(times=3)
        age_sub, trail_sub = age_and_trail_for_region(engine, 0, 0, 20, 20)
        assert np.array_equal(age_sub, engine.age_array())
        assert np.allclose(trail_sub, engine.trail_intensity())

    def test_region_slicing_matches_subarray_of_full(self):
        engine = LifeEngine(30, 30, topology=Topology.BOUNDED)
        engine.set_cells([(10, 10), (11, 10), (10, 11), (20, 20)], True)
        engine.step(times=2)
        age_full = engine.age_array()
        trail_full = engine.trail_intensity()
        age_sub, trail_sub = age_and_trail_for_region(engine, 5, 5, 15, 15)
        assert np.array_equal(age_sub, age_full[5:15, 5:15])
        assert np.allclose(trail_sub, trail_full[5:15, 5:15])


class TestRendererIntegration:
    def test_render_does_not_crash_and_fills_viewport(self):
        engine = LifeEngine(20, 20, topology=Topology.BOUNDED)
        engine.set_cells([(5, 5), (6, 5), (7, 5)], True)
        camera = Camera(grid_width=20, grid_height=20, viewport_width=200,
                         viewport_height=200, cell_size=10, offset_x=0, offset_y=0)
        renderer = Renderer(mode=ColorMode.CLASSIC)
        target = pygame.Surface((200, 200))
        viewport = pygame.Rect(0, 0, 200, 200)
        renderer.render(target, viewport, engine, camera)
        # La celda (5,5) esta viva -> el pixel central de su bloque de 10x10
        # deberia tener el color 'vivo', no el de fondo.
        px = target.get_at((55, 55))[:3]
        assert tuple(px) == CLASSIC_ALIVE

    def test_render_dead_area_is_background(self):
        engine = LifeEngine(20, 20, topology=Topology.BOUNDED)
        camera = Camera(grid_width=20, grid_height=20, viewport_width=200,
                         viewport_height=200, cell_size=10, offset_x=0, offset_y=0)
        renderer = Renderer(mode=ColorMode.CLASSIC)
        target = pygame.Surface((200, 200))
        viewport = pygame.Rect(0, 0, 200, 200)
        renderer.render(target, viewport, engine, camera)
        px = target.get_at((55, 55))[:3]
        assert tuple(px) == BACKGROUND

    def test_toggle_mode_switches_between_classic_and_age(self):
        renderer = Renderer(mode=ColorMode.CLASSIC)
        assert renderer.toggle_mode() == ColorMode.AGE
        assert renderer.toggle_mode() == ColorMode.CLASSIC

    def test_set_mode_rejects_unknown_mode(self):
        renderer = Renderer()
        with pytest.raises(ValueError):
            renderer.set_mode("no-existe")

    def test_render_reuses_logical_surface_when_size_unchanged(self):
        engine = LifeEngine(20, 20, topology=Topology.BOUNDED)
        camera = Camera(grid_width=20, grid_height=20, viewport_width=200,
                         viewport_height=200, cell_size=10, offset_x=0, offset_y=0)
        renderer = Renderer()
        target = pygame.Surface((200, 200))
        viewport = pygame.Rect(0, 0, 200, 200)
        renderer.render(target, viewport, engine, camera)
        surf_1 = renderer._logical_surface
        renderer.render(target, viewport, engine, camera)
        surf_2 = renderer._logical_surface
        assert surf_1 is surf_2


class TestExportPNG:
    def test_export_png_creates_readable_file(self, tmp_path):
        engine = LifeEngine(10, 10, topology=Topology.BOUNDED)
        engine.set_cells([(2, 2), (3, 2), (4, 2)], True)
        out = tmp_path / "estado.png"
        export_png(engine, str(out), cell_px=4, mode=ColorMode.CLASSIC)
        assert out.exists()
        loaded = pygame.image.load(str(out))
        assert loaded.get_size() == (40, 40)

    def test_render_full_rgb_matches_full_grid_shape(self):
        engine = LifeEngine(15, 12, topology=Topology.BOUNDED)
        rgb = render_full_rgb(engine)
        assert rgb.shape == (12, 15, 3)
