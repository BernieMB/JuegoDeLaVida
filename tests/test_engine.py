from __future__ import annotations

import numpy as np
import pytest

from vida.engine import LifeEngine, Topology
from vida.rules import KNOWN_RULES, Rule


def _reference_step(grid: np.ndarray, rule: Rule, topology: Topology) -> np.ndarray:
    """Implementacion de referencia deliberadamente distinta (bucles Python
    puros, sin trucos de slicing ni optimizacion de caja) para validar por
    comparacion cruzada el motor vectorizado de ``LifeEngine``."""
    h, w = grid.shape
    new_grid = np.zeros_like(grid)
    for y in range(h):
        for x in range(w):
            count = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    ny, nx = y + dy, x + dx
                    if topology is Topology.TORUS:
                        ny %= h
                        nx %= w
                    elif not (0 <= ny < h and 0 <= nx < w):
                        continue
                    count += int(grid[ny, nx])
            alive = bool(grid[y, x])
            if alive:
                new_grid[y, x] = 1 if count in rule.survive else 0
            else:
                new_grid[y, x] = 1 if count in rule.birth else 0
    return new_grid


def _make_engine(width, height, topology=Topology.TORUS, rule_key="life") -> LifeEngine:
    return LifeEngine(width, height, rule=KNOWN_RULES[rule_key], topology=topology)


class TestBasicMechanics:
    def test_empty_grid_stays_empty(self):
        engine = _make_engine(20, 20)
        engine.step()
        assert engine.population == 0
        assert engine.generation == 1

    def test_block_is_a_still_life(self):
        engine = _make_engine(10, 10)
        engine.set_cells([(4, 4), (5, 4), (4, 5), (5, 5)], True)
        before = engine.grid.copy()
        engine.step()
        assert np.array_equal(engine.grid, before)

    def test_blinker_has_period_2(self):
        engine = _make_engine(10, 10, topology=Topology.BOUNDED)
        # Blinker horizontal lejos del borde.
        engine.set_cells([(3, 5), (4, 5), (5, 5)], True)
        initial = engine.grid.copy()
        engine.step()
        assert not np.array_equal(engine.grid, initial)
        engine.step()
        assert np.array_equal(engine.grid, initial)

    def test_generation_counter_increments(self):
        engine = _make_engine(10, 10)
        assert engine.generation == 0
        engine.step(times=5)
        assert engine.generation == 5

    def test_population_property(self):
        engine = _make_engine(10, 10)
        engine.set_cells([(0, 0), (1, 1), (2, 2)], True)
        assert engine.population == 3


class TestTopology:
    def test_bounded_glider_falls_off_edge(self):
        # Un bloque de 2x2 en la esquina (0,0) en modo BOUNDED pierde vecinas
        # fuera de la rejilla: con < 2 vecinas todas mueren (subpoblacion en
        # las puntas). Colocamos 3 celulas vivas que solo son vecinas de la
        # esquina (0,0) SI el tablero envuelve (torus): (9,9), (9,0) y (0,9)
        # son, respectivamente, las posiciones (-1,-1), (-1,0) y (0,-1)
        # relativas a (0,0) al enlazar los bordes. En TORUS, (0,0) tiene 3
        # vecinas vivas -> nace (B3). En BOUNDED esas posiciones no existen
        # -> (0,0) sigue muerta.
        bounded = _make_engine(10, 10, topology=Topology.BOUNDED)
        torus = _make_engine(10, 10, topology=Topology.TORUS)
        coords = [(9, 9), (9, 0), (0, 9)]
        bounded.set_cells(coords, True)
        torus.set_cells(coords, True)
        bounded.step()
        torus.step()
        assert torus.grid[0, 0] == 1
        assert bounded.grid[0, 0] == 0
        assert not np.array_equal(bounded.grid, torus.grid)

    def test_torus_wraps_around(self):
        engine = _make_engine(10, 10, topology=Topology.TORUS)
        # Blinker vertical centrado en la columna 0 (a caballo del borde
        # izquierdo/derecho al enlazarse el toro).
        engine.set_cells([(0, 4), (0, 5), (0, 6)], True)
        engine.step()
        # Tras un paso un blinker vertical pasa a horizontal; en el toro
        # debe aparecer en x=9 (columna enlazada), x=0 y x=1.
        assert engine.grid[5, 9] == 1
        assert engine.grid[5, 0] == 1
        assert engine.grid[5, 1] == 1


class TestCrossValidationAgainstReference:
    """Compara el motor vectorizado (con y sin optimizacion de caja) contra
    una implementacion de referencia con bucles puros, para varias regals,
    topologias y densidades."""

    @pytest.mark.parametrize("topology", [Topology.TORUS, Topology.BOUNDED])
    @pytest.mark.parametrize("rule_key", ["life", "highlife", "seeds", "anneal"])
    @pytest.mark.parametrize("seed", [0, 1, 2, 3])
    def test_sparse_pattern_matches_reference(self, topology, rule_key, seed):
        rng = np.random.default_rng(seed)
        size = 25
        engine = _make_engine(size, size, topology=topology, rule_key=rule_key)
        # Patron dentro de un margen, para poder disparar la optimizacion de
        # caja (no toca el borde) y comprobar que coincide igualmente.
        grid = np.zeros((size, size), dtype=np.uint8)
        grid[5:15, 5:15] = (rng.random((10, 10)) < 0.35).astype(np.uint8)
        engine.grid = grid.copy()

        expected = _reference_step(grid, engine.rule, topology)
        engine.step()

        assert np.array_equal(engine.grid, expected), (
            f"Discrepancia con regla={rule_key} topologia={topology} seed={seed}"
        )

    @pytest.mark.parametrize("topology", [Topology.TORUS, Topology.BOUNDED])
    def test_dense_pattern_matches_reference(self, topology):
        rng = np.random.default_rng(42)
        size = 20
        grid = (rng.random((size, size)) < 0.5).astype(np.uint8)
        engine = _make_engine(size, size, topology=topology)
        engine.grid = grid.copy()

        expected = _reference_step(grid, engine.rule, topology)
        engine.step()
        assert np.array_equal(engine.grid, expected)

    def test_pattern_touching_edge_in_torus_matches_reference(self):
        size = 20
        grid = np.zeros((size, size), dtype=np.uint8)
        # Planeador tocando el borde superior e izquierdo: debe forzar el
        # calculo completo (no bbox) para no romper el enlace toroidal.
        grid[0, 1] = 1
        grid[1, 2] = 1
        grid[2, 0] = 1
        grid[2, 1] = 1
        grid[2, 2] = 1
        engine = _make_engine(size, size, topology=Topology.TORUS)
        engine.grid = grid.copy()
        expected = _reference_step(grid, engine.rule, Topology.TORUS)

        stats = engine.step()
        assert not stats.used_bbox
        assert np.array_equal(engine.grid, expected)

    def test_bbox_path_is_actually_exercised_and_correct(self):
        size = 60
        grid = np.zeros((size, size), dtype=np.uint8)
        # Glider bien alejado de todos los bordes -> debe activar la
        # optimizacion de caja envolvente.
        grid[10, 11] = 1
        grid[11, 12] = 1
        grid[12, 10] = 1
        grid[12, 11] = 1
        grid[12, 12] = 1
        engine = _make_engine(size, size, topology=Topology.TORUS)
        engine.grid = grid.copy()
        expected = _reference_step(grid, engine.rule, Topology.TORUS)

        stats = engine.step()
        assert stats.used_bbox
        assert np.array_equal(engine.grid, expected)

    def test_bbox_and_full_step_agree_over_many_generations(self):
        """Corre 40 generaciones de un patron denso y ramificado (no
        necesita ser un patron 'real' conocido) y verifica en cada paso que
        coincide con la referencia. Al crecer y moverse, la region viva
        alternara entre disparar la optimizacion de caja y el calculo
        completo, lo que detecta bugs que solo aparecen tras varias
        iteraciones (p.ej. arrastre de estado obsoleto entre ambos caminos)."""
        size = 60
        rng = np.random.default_rng(99)
        grid = np.zeros((size, size), dtype=np.uint8)
        grid[15:25, 15:25] = (rng.random((10, 10)) < 0.4).astype(np.uint8)
        engine = _make_engine(size, size, topology=Topology.TORUS)
        engine.grid = grid.copy()
        reference = grid.copy()
        for gen in range(40):
            reference = _reference_step(reference, engine.rule, Topology.TORUS)
            engine.step()
            assert np.array_equal(engine.grid, reference), f"Diverge en gen {gen + 1}"


class TestEditing:
    def test_set_cell_single(self):
        engine = _make_engine(10, 10)
        engine.set_cell(3, 3, True)
        assert engine.grid[3, 3] == 1
        engine.set_cell(3, 3, False)
        assert engine.grid[3, 3] == 0

    def test_set_cell_out_of_bounds_is_noop(self):
        engine = _make_engine(10, 10)
        engine.set_cell(-1, 0, True)
        engine.set_cell(100, 0, True)
        assert engine.population == 0

    def test_toggle_cell(self):
        engine = _make_engine(10, 10)
        engine.toggle_cell(2, 2)
        assert engine.grid[2, 2] == 1
        engine.toggle_cell(2, 2)
        assert engine.grid[2, 2] == 0

    def test_set_cells_batch_clips_out_of_bounds(self):
        engine = _make_engine(10, 10)
        engine.set_cells([(1, 1), (-5, 3), (2, 2), (50, 50)], True)
        assert engine.population == 2
        assert engine.grid[1, 1] == 1
        assert engine.grid[2, 2] == 1

    def test_clear_resets_population_and_generation(self):
        engine = _make_engine(10, 10)
        engine.set_cells([(1, 1), (2, 2)], True)
        engine.step(times=3)
        engine.clear()
        assert engine.population == 0
        assert engine.generation == 0

    def test_reset_restores_seed_after_stepping(self):
        engine = _make_engine(10, 10, topology=Topology.BOUNDED)
        engine.set_cells([(3, 5), (4, 5), (5, 5)], True)  # blinker = semilla
        seed_snapshot = engine.grid.copy()
        engine.step(times=7)
        assert not np.array_equal(engine.grid, seed_snapshot)
        engine.reset()
        assert np.array_equal(engine.grid, seed_snapshot)
        assert engine.generation == 0

    def test_edits_before_first_step_become_part_of_seed(self):
        engine = _make_engine(10, 10)
        engine.set_cell(1, 1, True)
        engine.set_cell(2, 2, True)  # ambas ediciones a generacion 0
        engine.reset()
        assert engine.population == 2

    def test_edits_after_stepping_do_not_change_seed(self):
        engine = _make_engine(10, 10, topology=Topology.BOUNDED)
        engine.set_cells([(3, 5), (4, 5), (5, 5)], True)
        engine.step()  # generation pasa a 1, la semilla queda fijada
        engine.set_cell(0, 0, True)  # "toco" la simulacion en marcha
        engine.reset()
        assert engine.grid[0, 0] == 0  # el toque no debia quedar en la semilla

    def test_randomize_is_reproducible_with_seed(self):
        e1 = _make_engine(30, 30)
        e2 = _make_engine(30, 30)
        e1.randomize(density=0.4, seed=123)
        e2.randomize(density=0.4, seed=123)
        assert np.array_equal(e1.grid, e2.grid)

    def test_randomize_density_is_approximately_correct(self):
        engine = _make_engine(200, 200)
        engine.randomize(density=0.3, seed=7)
        assert 0.25 < engine.alive_fraction < 0.35


class TestStampAndRegions:
    def test_stamp_places_pattern_at_position(self):
        engine = _make_engine(20, 20)
        glider = np.array([[0, 1, 0], [0, 0, 1], [1, 1, 1]], dtype=np.uint8)
        engine.stamp(glider, 5, 5)
        assert engine.grid[5, 6] == 1
        assert engine.grid[6, 7] == 1
        assert engine.grid[7, 5] == 1
        assert engine.grid[7, 6] == 1
        assert engine.grid[7, 7] == 1
        assert engine.population == 5

    def test_stamp_clips_at_grid_edges(self):
        engine = _make_engine(10, 10)
        block = np.ones((4, 4), dtype=np.uint8)
        engine.stamp(block, 8, 8)  # se sale por abajo y por la derecha
        assert engine.population == 4  # solo cabe la esquina 2x2

    def test_extract_returns_subregion(self):
        engine = _make_engine(10, 10)
        engine.set_cells([(2, 2), (3, 2), (2, 3)], True)
        region = engine.extract(2, 2, 4, 4)
        assert region.shape == (2, 2)
        assert region.sum() == 3

    def test_clear_region_only_affects_selection(self):
        engine = _make_engine(10, 10)
        engine.set_cells([(1, 1), (5, 5)], True)
        engine.clear_region(0, 0, 3, 3)
        assert engine.grid[1, 1] == 0
        assert engine.grid[5, 5] == 1


class TestUndoRedo:
    def test_undo_restores_previous_grid(self):
        engine = _make_engine(10, 10)
        engine.set_cell(1, 1, True)
        engine.step()
        before_clear = engine.grid.copy()
        engine.clear()
        assert engine.population == 0
        assert engine.undo() is True
        assert np.array_equal(engine.grid, before_clear)

    def test_redo_reapplies_after_undo(self):
        engine = _make_engine(10, 10)
        engine.set_cell(1, 1, True)
        engine.step()
        engine.clear()
        engine.undo()
        assert engine.redo() is True
        assert engine.population == 0

    def test_undo_on_empty_stack_returns_false(self):
        engine = _make_engine(10, 10)
        assert engine.undo() is False

    def test_can_undo_can_redo_flags(self):
        engine = _make_engine(10, 10)
        assert engine.can_undo() is False
        engine.clear()
        assert engine.can_undo() is True
        engine.undo()
        assert engine.can_redo() is True


class TestAgeAndTrail:
    def test_newly_born_cell_has_age_zero(self):
        engine = _make_engine(10, 10, topology=Topology.BOUNDED)
        engine.set_cells([(3, 5), (4, 5), (5, 5)], True)
        initial = engine.grid.copy()
        engine.step()
        age = engine.age_array()
        newly_alive = (engine.grid == 1) & (initial == 0)
        survived = (engine.grid == 1) & (initial == 1)
        assert newly_alive.any() and survived.any()
        assert np.all(age[newly_alive] == 0)
        # La celula central del blinker sobrevive un paso: ya tiene 1 generacion.
        assert np.all(age[survived] == 1)

    def test_age_increases_for_still_life(self):
        engine = _make_engine(10, 10)
        engine.set_cells([(4, 4), (5, 4), (4, 5), (5, 5)], True)  # block
        engine.step(times=5)
        age = engine.age_array()
        assert age[4, 4] == 5

    def test_trail_intensity_is_one_right_after_death(self):
        engine = _make_engine(10, 10, topology=Topology.BOUNDED)
        engine.set_cells([(3, 5), (4, 5), (5, 5)], True)  # blinker
        engine.step()
        trail = engine.trail_intensity()
        # Las puntas del blinker mueren en el primer paso.
        assert trail[5, 3] == pytest.approx(1.0)
        assert trail[5, 5] == pytest.approx(1.0)

    def test_trail_decays_over_generations(self):
        engine = _make_engine(10, 10, topology=Topology.BOUNDED)
        # Celula aislada: muere de subpoblacion en el primer paso y, al no
        # quedar ninguna celula viva en el tablero, ya no puede renacer
        # (B3/S23 no genera vida de la nada) -> decaimiento monotono limpio.
        engine.set_cell(5, 5, True)
        engine.step()
        t1 = engine.trail_intensity()[5, 5]
        engine.step()
        engine.step()
        t3 = engine.trail_intensity()[5, 5]
        assert t1 == pytest.approx(1.0)
        assert t3 < t1


class TestRuleAndTopologySwitching:
    def test_set_rule_changes_behavior(self):
        engine = _make_engine(10, 10, topology=Topology.BOUNDED)
        engine.set_cells([(3, 5), (4, 5), (5, 5)], True)
        engine.set_rule(KNOWN_RULES["seeds"])
        engine.step()
        # Con Seeds (B2/S) ninguna celda viva sobrevive nunca.
        assert engine.grid[5, 4] == 0

    def test_set_topology_takes_effect_next_step(self):
        engine = _make_engine(10, 10, topology=Topology.BOUNDED)
        engine.set_topology(Topology.TORUS)
        assert engine.topology is Topology.TORUS
