from __future__ import annotations

import numpy as np
import pytest

from vida.engine import LifeEngine, Topology
from vida.patterns import CATALOG, categories, get_pattern, list_patterns


def _bbox(grid: np.ndarray):
    rows = np.any(grid, axis=1)
    if not rows.any():
        return None
    cols = np.any(grid, axis=0)
    r0 = int(np.argmax(rows))
    r1 = grid.shape[0] - 1 - int(np.argmax(rows[::-1]))
    c0 = int(np.argmax(cols))
    c1 = grid.shape[1] - 1 - int(np.argmax(cols[::-1]))
    return r0, r1, c0, c1


def _normalized_shape(grid: np.ndarray) -> np.ndarray | None:
    b = _bbox(grid)
    if b is None:
        return None
    r0, r1, c0, c1 = b
    return grid[r0 : r1 + 1, c0 : c1 + 1].copy()


def _place_centered(engine: LifeEngine, grid: np.ndarray) -> None:
    gh, gw = grid.shape
    ox = (engine.width - gw) // 2
    oy = (engine.height - gh) // 2
    engine.stamp(grid, ox, oy)


class TestCatalogStructure:
    def test_no_duplicate_keys(self):
        keys = [p.key for p in CATALOG.values()]
        assert len(keys) == len(set(keys))

    def test_covers_all_expected_categories(self):
        assert set(categories()) == {
            "still_life", "oscillator", "spaceship", "methuselah", "gun",
        }

    def test_has_a_healthy_number_of_patterns(self):
        assert len(CATALOG) == 30

    def test_every_pattern_grid_matches_its_population(self):
        for pattern in CATALOG.values():
            grid = pattern.to_grid()
            assert grid.size > 0
            assert int(grid.sum()) == pattern.population


class TestStillLives:
    """Una still life debe ser identica a si misma tras 1 generacion."""

    @pytest.mark.parametrize("key", [p.key for p in list_patterns("still_life")])
    def test_unchanged_after_one_generation(self, key):
        pattern = get_pattern(key)
        engine = LifeEngine(40, 40, topology=Topology.BOUNDED)
        _place_centered(engine, pattern.to_grid())
        before = engine.grid.copy()
        engine.step()
        assert np.array_equal(engine.grid, before), (
            f"{pattern.name} deberia ser una forma estable (still life)"
        )


class TestOscillators:
    """El periodo declarado debe ser exacto (minimo), no solo un multiplo
    que coincida por casualidad."""

    @pytest.mark.parametrize("key", [p.key for p in list_patterns("oscillator")])
    def test_period_is_exact(self, key):
        pattern = get_pattern(key)
        size = 70
        engine = LifeEngine(size, size, topology=Topology.BOUNDED)
        _place_centered(engine, pattern.to_grid())
        initial_shape = _normalized_shape(engine.grid)
        initial_pop = engine.population

        for gen in range(1, pattern.period):
            engine.step()
            shape = _normalized_shape(engine.grid)
            same = (
                shape is not None
                and shape.shape == initial_shape.shape
                and np.array_equal(shape, initial_shape)
            )
            assert not same, (
                f"{pattern.name}: repite su forma en la generacion {gen}, "
                f"antes del periodo declarado ({pattern.period})"
            )

        engine.step()  # llegamos a la generacion == pattern.period
        final_shape = _normalized_shape(engine.grid)
        assert final_shape is not None
        assert final_shape.shape == initial_shape.shape
        assert np.array_equal(final_shape, initial_shape), (
            f"{pattern.name}: no vuelve a su forma inicial tras "
            f"{pattern.period} generaciones"
        )
        assert engine.population == initial_pop


class TestSpaceships:
    """Tras 'period' generaciones deben reproducir su forma exacta pero
    desplazada, con la misma poblacion 'de reposo' que al iniciar."""

    @pytest.mark.parametrize("key", [p.key for p in list_patterns("spaceship")])
    def test_period_and_displacement(self, key):
        pattern = get_pattern(key)
        size = 90
        engine = LifeEngine(size, size, topology=Topology.TORUS)
        _place_centered(engine, pattern.to_grid())
        initial_shape = _normalized_shape(engine.grid)
        initial_bbox = _bbox(engine.grid)
        initial_pop = engine.population

        for _ in range(pattern.period):
            engine.step()

        final_shape = _normalized_shape(engine.grid)
        final_bbox = _bbox(engine.grid)
        assert final_shape is not None
        assert final_shape.shape == initial_shape.shape
        assert np.array_equal(final_shape, initial_shape), (
            f"{pattern.name}: no reproduce su forma tras {pattern.period} generaciones"
        )
        assert engine.population == initial_pop, (
            f"{pattern.name}: la poblacion deberia volver a su valor de reposo "
            f"({initial_pop}) tras un periodo completo"
        )
        moved = (
            final_bbox[0] != initial_bbox[0] or final_bbox[2] != initial_bbox[2]
        )
        assert moved, f"{pattern.name}: no se ha desplazado tras su periodo"


class TestMethuselahs:
    """Los matusalenes no son periodicos: se comprueba poblacion/extincion
    EXACTA en la generacion documentada por Wikipedia."""

    def test_r_pentomino_stabilizes_at_documented_population(self):
        pattern = get_pattern("r_pentomino")
        size = 900  # margen suficiente: 6 planeadores escapan a c/4 en 1103 gens
        engine = LifeEngine(size, size, topology=Topology.BOUNDED)
        c = size // 2
        engine.stamp(pattern.to_grid(), c, c)
        engine.step(times=1103)
        assert engine.population == 116

    def test_diehard_dies_at_exact_generation(self):
        pattern = get_pattern("diehard")
        size = 200
        engine = LifeEngine(size, size, topology=Topology.BOUNDED)
        c = size // 2
        engine.stamp(pattern.to_grid(), c, c)
        engine.step(times=129)
        assert engine.population > 0, "Diehard no deberia extinguirse antes de tiempo"
        engine.step()
        assert engine.population == 0, "Diehard deberia extinguirse en la generacion 130"

    @pytest.mark.slow
    def test_acorn_reaches_documented_population(self):
        pattern = get_pattern("acorn")
        size = 3200  # margen amplio: 13 planeadores escapan a c/4 en 5206 gens
        engine = LifeEngine(size, size, topology=Topology.BOUNDED)
        c = size // 2
        engine.stamp(pattern.to_grid(), c, c)
        engine.step(times=5206)
        assert engine.population == 633

    def test_thunderbird_reaches_documented_lifespan(self):
        pattern = get_pattern("thunderbird")
        engine = LifeEngine(500, 500, topology=Topology.BOUNDED)
        engine.stamp(pattern.to_grid(), 250, 250)
        engine.step(times=243)
        assert engine.population == 46
        for _ in range(3):
            engine.step()
            assert engine.population == 46


class TestGuns:
    def test_gosper_gun_emits_a_new_glider_every_period(self):
        gun = get_pattern("gosper_gun")
        glider_population = get_pattern("glider").population
        size = 220
        engine = LifeEngine(size, size, topology=Topology.BOUNDED)
        engine.stamp(gun.to_grid(), 15, 15)
        engine.step(times=90)  # dejar pasar el transitorio inicial
        pop_before = engine.population
        engine.step(times=gun.period)
        pop_after = engine.population
        assert pop_after - pop_before == glider_population

    def test_simkin_gun_emits_a_new_glider_every_period(self):
        gun = get_pattern("simkin_gun")
        glider_population = get_pattern("glider").population
        engine = LifeEngine(500, 500, topology=Topology.BOUNDED)
        engine.stamp(gun.to_grid(), 100, 100)
        engine.step(times=240)
        pop_before = engine.population
        engine.step(times=gun.period)
        pop_after = engine.population
        assert pop_after - pop_before == glider_population
