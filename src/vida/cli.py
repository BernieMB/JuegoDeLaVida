"""Interfaz de linea de comandos (``uv run vida`` / ``python -m vida``)."""

from __future__ import annotations

import argparse
import sys

from vida import __version__
from vida.engine import Topology
from vida.rules import KNOWN_RULES, get_rule


def _parse_size(value: str) -> tuple[int, int]:
    text = value.lower().strip()
    if "x" in text:
        w_str, h_str = text.split("x", 1)
        return int(w_str), int(h_str)
    n = int(text)
    return n, n


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vida",
        description="El Juego de la Vida de Conway: simulacion interactiva con pygame-ce y NumPy.",
    )
    parser.add_argument("--version", action="version", version=f"vida {__version__}")
    parser.add_argument(
        "--size", type=_parse_size, default=(200, 200),
        help="Tamano de la rejilla: 'N' o 'ANCHOxALTO' (por defecto 200x200, el minimo pedido).",
    )
    parser.add_argument(
        "--rule", default="life",
        help=f"Regla inicial: clave del catalogo ({', '.join(KNOWN_RULES)}) o un rulestring 'B../S..'.",
    )
    parser.add_argument(
        "--topology", choices=["torus", "bounded"], default="torus",
        help="Topologia de la rejilla: 'torus' (bordes enlazados, por defecto) o 'bounded' (exterior muerto).",
    )
    parser.add_argument(
        "--window", type=_parse_size, default=(1300, 860),
        help="Tamano inicial de la ventana 'ANCHOxALTO' (por defecto 1300x860).",
    )
    parser.add_argument(
        "--random", action="store_true",
        help="Arranca con el tablero relleno aleatoriamente en vez de vacio.",
    )
    parser.add_argument(
        "--density", type=float, default=0.3,
        help="Densidad (0-1) usada con --random (por defecto 0.3).",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Semilla del generador aleatorio, para reproducibilidad.",
    )
    parser.add_argument(
        "--benchmark", action="store_true",
        help="Ejecuta un benchmark de generaciones/segundo (sin ventana) y sale.",
    )
    parser.add_argument(
        "--benchmark-generations", type=int, default=300,
        help="Numero de generaciones a medir con --benchmark (por defecto 300).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    width, height = args.size
    rule = get_rule(args.rule)
    topology = Topology.TORUS if args.topology == "torus" else Topology.BOUNDED

    if args.benchmark:
        from vida.benchmark import run_benchmark
        run_benchmark(width, height, rule=rule, topology=topology,
                       generations=args.benchmark_generations, density=args.density,
                       seed=args.seed if args.seed is not None else 42)
        return 0

    from vida.app import App
    window_w, window_h = args.window
    app = App(width=width, height=height, rule=rule, topology=topology,
              window_size=(window_w, window_h))
    if args.random:
        app.engine.randomize(density=args.density, seed=args.seed)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
