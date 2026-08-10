from __future__ import annotations

import numpy as np
import pytest

from vida.engine import LifeEngine, Topology
from vida.stats import CycleDetector, CycleStatus, PopulationHistory, RealSpeedMeter


class TestCycleDetectorStillLife:
    def test_detects_still_life_as_period_one(self):
        engine = LifeEngine(20, 20, topology=Topology.BOUNDED)
        engine.set_cells([(4, 4), (5, 4), (4, 5), (5, 5)], True)  # block
        detector = CycleDetector()
        detector.observe(engine)
        engine.step()
        just_detected = detector.observe(engine)
        assert just_detected is True
        assert detector.status == CycleStatus.STILL
        assert detector.period == 1
        assert detector.message == "Estable (still life)"

    def test_does_not_redetect_on_subsequent_observations(self):
        engine = LifeEngine(20, 20, topology=Topology.BOUNDED)
        engine.set_cells([(4, 4), (5, 4), (4, 5), (5, 5)], True)
        detector = CycleDetector()
        detector.observe(engine)
        engine.step()
        first = detector.observe(engine)
        engine.step()
        second = detector.observe(engine)
        assert first is True
        assert second is False  # ya estaba en ciclo, no es una nueva deteccion


class TestCycleDetectorOscillator:
    def test_detects_blinker_period_two(self):
        engine = LifeEngine(20, 20, topology=Topology.BOUNDED)
        engine.set_cells([(3, 5), (4, 5), (5, 5)], True)
        detector = CycleDetector()
        detector.observe(engine)
        engine.step()
        detector.observe(engine)
        engine.step()
        just_detected = detector.observe(engine)
        assert just_detected is True
        assert detector.status == CycleStatus.OSCILLATING
        assert detector.period == 2
        assert detector.message == "Oscilador de periodo 2"

    def test_detects_pulsar_period_three(self):
        coords = []
        for row in (0, 5, 7, 12):
            for col in (2, 3, 4, 8, 9, 10):
                coords.append((col + 5, row + 5))
        for row in (2, 3, 4, 8, 9, 10):
            for col in (0, 5, 7, 12):
                coords.append((col + 5, row + 5))
        engine = LifeEngine(30, 30, topology=Topology.BOUNDED)
        engine.set_cells(coords, True)
        detector = CycleDetector()
        detector.observe(engine)
        for _ in range(3):
            engine.step()
            result = detector.observe(engine)
        assert detector.status == CycleStatus.OSCILLATING
        assert detector.period == 3


class TestCycleDetectorNoCycle:
    def test_growing_chaotic_pattern_reports_no_cycle(self):
        engine = LifeEngine(200, 200, topology=Topology.BOUNDED)
        cx = 100
        engine.set_cells([(cx + 1, cx), (cx + 2, cx), (cx, cx + 1), (cx + 1, cx + 1),
                           (cx + 1, cx + 2)], True)  # R-pentomino: caotico durante mucho tiempo
        detector = CycleDetector(window=64)
        detector.observe(engine)
        for _ in range(60):
            engine.step()
            detector.observe(engine)
        assert detector.status == CycleStatus.NONE
        assert detector.message is None

    def test_empty_grid_is_a_still_life(self):
        engine = LifeEngine(10, 10)
        detector = CycleDetector()
        detector.observe(engine)
        engine.step()
        detector.observe(engine)
        assert detector.status == CycleStatus.STILL


class TestCycleDetectorReset:
    def test_reset_clears_status_and_history(self):
        engine = LifeEngine(20, 20, topology=Topology.BOUNDED)
        engine.set_cells([(4, 4), (5, 4), (4, 5), (5, 5)], True)
        detector = CycleDetector()
        detector.observe(engine)
        engine.step()
        detector.observe(engine)
        assert detector.status != CycleStatus.NONE
        detector.reset()
        assert detector.status == CycleStatus.NONE
        assert detector.period is None


class TestPopulationHistory:
    def test_sample_appends_current_population(self):
        engine = LifeEngine(10, 10)
        engine.set_cells([(1, 1), (2, 2)], True)
        history = PopulationHistory()
        history.sample(engine)
        assert history.values() == [2]

    def test_max_samples_truncates_oldest(self):
        engine = LifeEngine(10, 10)
        history = PopulationHistory(max_samples=3)
        for i in range(5):
            engine.clear()
            engine.set_cells([(x, 0) for x in range(i)], True)
            history.sample(engine)
        assert len(history.values()) == 3
        assert history.values() == [2, 3, 4]

    def test_min_max_value(self):
        history = PopulationHistory()
        history.samples.extend([5, 2, 9, 1])
        assert history.min_value == 1
        assert history.max_value == 9

    def test_empty_history_min_max_are_zero(self):
        history = PopulationHistory()
        assert history.min_value == 0
        assert history.max_value == 0

    def test_reset_clears_samples(self):
        history = PopulationHistory()
        history.samples.extend([1, 2, 3])
        history.reset()
        assert history.values() == []


class TestRealSpeedMeter:
    def test_value_unchanged_before_window_elapses(self, monkeypatch):
        times = iter([100.0, 100.1])  # 0.1s < window_seconds por defecto (0.5)
        monkeypatch.setattr("vida.stats.time.perf_counter", lambda: next(times))
        meter = RealSpeedMeter(window_seconds=0.5)
        meter.update(10)
        assert meter.value == 0.0

    def test_value_updates_after_window_elapses(self, monkeypatch):
        current_time = [100.0]
        monkeypatch.setattr("vida.stats.time.perf_counter", lambda: current_time[0])
        meter = RealSpeedMeter(window_seconds=0.5)
        meter.reset(generation=0)
        current_time[0] = 100.6  # avanza 0.6s >= window_seconds (0.5)
        meter.update(300)  # 300 generaciones en 0.6s -> 500 gen/s
        assert meter.value == pytest.approx(500.0, rel=0.01)

    def test_reset_sets_baseline_generation(self, monkeypatch):
        monkeypatch.setattr("vida.stats.time.perf_counter", lambda: 50.0)
        meter = RealSpeedMeter()
        meter.reset(generation=1000)
        assert meter._window_start_generation == 1000
        assert meter.value == 0.0
