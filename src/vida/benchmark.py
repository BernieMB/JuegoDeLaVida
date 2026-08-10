"""Modo benchmark: mide generaciones/segundo reales sin abrir ventana."""

from __future__ import annotations

import time

from vida.engine import LifeEngine, Topology
from vida.rules import Rule


def run_benchmark(width: int, height: int, *, rule: Rule, topology: Topology,
                   generations: int = 300, density: float = 0.3,
                   seed: int | None = 42, warmup: int = 10) -> dict:
    """Mide el rendimiento de ``LifeEngine.step()`` con una sopa aleatoria de
    densidad ``density`` (caso desfavorable: la optimizacion de caja
    envolvente no se activa con tanta densidad, por lo que el numero
    resultante es conservador, no optimista)."""
    engine = LifeEngine(width, height, rule=rule, topology=topology)
    engine.randomize(density=density, seed=seed)

    for _ in range(warmup):
        engine.step()

    start = time.perf_counter()
    for _ in range(generations):
        engine.step()
    elapsed = time.perf_counter() - start

    gens_per_second = generations / elapsed if elapsed > 0 else float("inf")
    ms_per_gen = (elapsed / generations) * 1000 if generations else 0.0

    result = {
        "width": width,
        "height": height,
        "rule": engine.rule.rulestring,
        "topology": topology.value,
        "generations": generations,
        "elapsed_seconds": elapsed,
        "generations_per_second": gens_per_second,
        "ms_per_generation": ms_per_gen,
    }

    print("Vida -- benchmark de simulacion (sin ventana, sopa aleatoria densidad "
          f"{density:.0%}, caso desfavorable para la optimizacion de caja)")
    print(f"  Rejilla:        {width}x{height}  (topologia: {topology.value})")
    print(f"  Regla:          {engine.rule.rulestring}")
    print(f"  Generaciones:   {generations}")
    print(f"  Tiempo total:   {elapsed * 1000:.2f} ms")
    print(f"  Por generacion: {ms_per_gen:.4f} ms")
    print(f"  Velocidad:      {gens_per_second:,.0f} generaciones/segundo")
    print("  (requisito minimo del proyecto: 2-3 gen/s en la velocidad mas rapida)")
    return result
