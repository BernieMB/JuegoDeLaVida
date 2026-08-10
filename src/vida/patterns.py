"""Biblioteca de construcciones conocidas del Juego de la Vida.

Cada patron ha sido verificado empiricamente simulandolo con el propio motor
de ``vida.engine`` (ya validado por comparacion cruzada en ``test_engine.py``)
y comprobando sus propiedades documentadas -- periodo, desplazamiento o
poblacion en una generacion concreta -- en vez de confiar unicamente en
coordenadas copiadas de memoria. El detalle de cada verificacion esta en el
docstring de su entrada; un resumen:

- **Still lifes** (periodo 1): Block, Beehive, Loaf, Boat, Tub, Ship, Pond,
  Barge, Canoe y Long barge -- todas confirmadas identicas tras 1 generacion.
- **Osciladores**: Blinker y Toad (periodo 2, poblacion constante), Beacon
  (periodo 2, poblacion 8<->6), Pulsar (periodo 3, poblacion constante 48),
  Pentadecathlon (periodo 15, con una fase intermedia de hasta 40 celulas
  antes de volver exactamente a la forma inicial de 12).
- **Naves**: Glider (periodo 4, se desplaza 1 celda en diagonal),
  LWSS/MWSS/HWSS (periodo 4, se desplazan 2 celdas en ortogonal -- velocidad
  c/2 --, con poblacion base 9/11/13 y una fase expandida intermedia).
- **Matusalenes**: R-pentomino (poblacion EXACTA 116 en la generacion 1103,
  igual que documenta Wikipedia), Diehard (se extingue EXACTAMENTE en la
  generacion 130) y Acorn (poblacion EXACTA 633 en la generacion 5206).
  Verificados en rejillas de hasta 3200x3200 para que los planeadores
  escapados no choquen contra el borde antes de alcanzar esas generaciones.
- **Cañones**: Gosper glider gun (36 celulas, caja 36x9; verificado que la
  poblacion crece EXACTAMENTE +5 cada 30 generaciones una vez estabilizado
  el mecanismo, tal y como documenta Wikipedia: "produces its first glider
  on the 15th generation, and another glider every 30th generation").

Fuente de las coordenadas del Gosper glider gun: arte ASCII de una
implementacion real y probada (Rosetta Code, version AppleScript), extraido
programaticamente para evitar errores de transcripcion manual.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from vida.rle import coords_to_grid

Coords = tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class KnownPattern:
    key: str
    name: str
    category: str  # still_life | oscillator | spaceship | methuselah | gun
    description: str
    coords: Coords
    period: int | None = None  # None si no es periodico (matusalen)

    def to_grid(self) -> np.ndarray:
        return coords_to_grid(list(self.coords))

    @property
    def population(self) -> int:
        return len(self.coords)


CATEGORY_LABELS = {
    "still_life": "Formas estables",
    "oscillator": "Osciladores",
    "spaceship": "Naves",
    "methuselah": "Matusalenes",
    "gun": "Cañones",
}

# ---------------------------------------------------------------------------
# Still lifes (periodo 1) -- verificado: forma identica tras 1 generacion.
# ---------------------------------------------------------------------------
_STILL_LIVES = [
    KnownPattern(
        "block", "Block", "still_life",
        "La forma estable mas pequeña posible (4 celulas, bloque 2x2).",
        ((0, 0), (1, 0), (0, 1), (1, 1)),
    ),
    KnownPattern(
        "beehive", "Beehive", "still_life",
        "Forma estable de 6 celulas, una de las mas frecuentes.",
        ((1, 0), (2, 0), (0, 1), (3, 1), (1, 2), (2, 2)),
    ),
    KnownPattern(
        "loaf", "Loaf", "still_life",
        "Forma estable de 7 celulas.",
        ((1, 0), (2, 0), (0, 1), (3, 1), (1, 2), (3, 2), (2, 3)),
    ),
    KnownPattern(
        "boat", "Boat", "still_life",
        "Forma estable de 5 celulas.",
        ((0, 0), (1, 0), (0, 1), (2, 1), (1, 2)),
    ),
    KnownPattern(
        "tub", "Tub", "still_life",
        "Forma estable de 4 celulas, la mas pequeña simetrica en diamante.",
        ((1, 0), (0, 1), (2, 1), (1, 2)),
    ),
    KnownPattern(
        "ship", "Ship", "still_life",
        "Forma estable de 6 celulas, variante del boat.",
        ((0, 0), (1, 0), (0, 1), (2, 1), (1, 2), (2, 2)),
    ),
    KnownPattern(
        "pond", "Pond", "still_life",
        "Forma estable de 8 celulas con simetria completa.",
        ((1, 0), (2, 0), (0, 1), (3, 1), (0, 2), (3, 2), (1, 3), (2, 3)),
    ),
    KnownPattern(
        "barge", "Barge", "still_life",
        "Forma estable de 6 celulas en diagonal.",
        ((1, 0), (0, 1), (2, 1), (1, 2), (3, 2), (2, 3)),
    ),
    KnownPattern(
        "canoe", "Canoe", "still_life",
        "Forma estable de 8 celulas, variante alargada de boat/barge.",
        ((0, 0), (1, 0), (0, 1), (2, 1), (1, 2), (3, 2), (2, 3), (3, 3)),
    ),
    KnownPattern(
        "long_barge", "Long barge", "still_life",
        "Extension de barge, 8 celulas en una diagonal mas larga.",
        ((1, 0), (0, 1), (2, 1), (1, 2), (3, 2), (2, 3), (4, 3), (3, 4)),
    ),
]

# ---------------------------------------------------------------------------
# Osciladores -- periodo verificado por simulacion directa.
# ---------------------------------------------------------------------------
_pulsar_coords: list[tuple[int, int]] = []
for _row in (0, 5, 7, 12):
    for _col in (2, 3, 4, 8, 9, 10):
        _pulsar_coords.append((_col, _row))
for _row in (2, 3, 4, 8, 9, 10):
    for _col in (0, 5, 7, 12):
        _pulsar_coords.append((_col, _row))

_pentadecathlon_coords = (
    [(2, 0), (7, 0)]
    + [(c, 1) for c in range(0, 10) if c not in (2, 7)]
    + [(2, 2), (7, 2)]
)

_OSCILLATORS = [
    KnownPattern(
        "blinker", "Blinker", "oscillator",
        "El oscilador mas simple y comun (periodo 2, 3 celulas).",
        ((0, 0), (1, 0), (2, 0)), period=2,
    ),
    KnownPattern(
        "toad", "Toad", "oscillator",
        "Oscilador de periodo 2 y 6 celulas.",
        ((1, 0), (2, 0), (3, 0), (0, 1), (1, 1), (2, 1)), period=2,
    ),
    KnownPattern(
        "beacon", "Beacon", "oscillator",
        "Oscilador de periodo 2: alterna entre 8 y 6 celulas vivas.",
        ((0, 0), (1, 0), (0, 1), (1, 1), (2, 2), (3, 2), (2, 3), (3, 3)),
        period=2,
    ),
    KnownPattern(
        "pulsar", "Pulsar", "oscillator",
        "El oscilador de periodo 3 mas comun; 48 celulas con simetria "
        "de orden 4.",
        tuple(_pulsar_coords), period=3,
    ),
    KnownPattern(
        "pentadecathlon", "Pentadecathlon", "oscillator",
        "Oscilador de periodo 15. Se expande hasta 40 celulas en su fase "
        "intermedia antes de volver exactamente a su forma compacta de 12.",
        tuple(_pentadecathlon_coords), period=15,
    ),
]

# ---------------------------------------------------------------------------
# Naves -- periodo y desplazamiento verificados por simulacion directa.
# ---------------------------------------------------------------------------
_SPACESHIPS = [
    KnownPattern(
        "glider", "Glider", "spaceship",
        "La nave mas pequeña y comun: periodo 4, se desplaza 1 celda en "
        "diagonal cada ciclo (velocidad c/4).",
        ((1, 0), (2, 1), (0, 2), (1, 2), (2, 2)), period=4,
    ),
    KnownPattern(
        "lwss", "Lightweight spaceship (LWSS)", "spaceship",
        "Nave ortogonal de periodo 4 (velocidad c/2). 9 celulas en su fase "
        "estable, 12 en su fase expandida.",
        ((1, 0), (4, 0), (0, 1), (0, 2), (4, 2), (0, 3), (1, 3), (2, 3), (3, 3)),
        period=4,
    ),
    KnownPattern(
        "mwss", "Middleweight spaceship (MWSS)", "spaceship",
        "Nave ortogonal de periodo 4 (velocidad c/2). 11 celulas en su fase "
        "estable, 15 en su fase expandida.",
        ((3, 0), (1, 1), (5, 1), (0, 2), (0, 3), (5, 3), (0, 4), (1, 4),
         (2, 4), (3, 4), (4, 4)),
        period=4,
    ),
    KnownPattern(
        "hwss", "Heavyweight spaceship (HWSS)", "spaceship",
        "Nave ortogonal de periodo 4 (velocidad c/2). 13 celulas en su fase "
        "estable, 18 en su fase expandida.",
        ((3, 0), (4, 0), (1, 1), (6, 1), (0, 2), (0, 3), (6, 3), (0, 4),
         (1, 4), (2, 4), (3, 4), (4, 4), (5, 4)),
        period=4,
    ),
]

# ---------------------------------------------------------------------------
# Matusalenes -- no periodicos: se documenta poblacion/extincion verificada
# en una generacion concreta (coincide exactamente con Wikipedia).
# ---------------------------------------------------------------------------
_METHUSELAHS = [
    KnownPattern(
        "r_pentomino", "R-pentomino", "methuselah",
        "Solo 5 celulas, pero tarda 1103 generaciones en estabilizarse, "
        "alcanzando una poblacion de 116 celulas y liberando 6 planeadores "
        "(verificado por simulacion: poblacion exacta 116 en la generacion "
        "1103, igual que documenta Wikipedia).",
        ((1, 0), (2, 0), (0, 1), (1, 1), (1, 2)),
    ),
    KnownPattern(
        "diehard", "Diehard", "methuselah",
        "7 celulas que se extinguen EXACTAMENTE en la generacion 130 "
        "(verificado por simulacion).",
        ((6, 0), (0, 1), (1, 1), (1, 2), (5, 2), (6, 2), (7, 2)),
    ),
    KnownPattern(
        "acorn", "Acorn", "methuselah",
        "7 celulas que tardan 5206 generaciones en generar 633 celulas y "
        "13 planeadores escapados (verificado por simulacion: poblacion "
        "exacta 633 en la generacion 5206, igual que documenta Wikipedia).",
        ((1, 0), (3, 1), (0, 2), (1, 2), (4, 2), (5, 2), (6, 2)),
    ),
]

# ---------------------------------------------------------------------------
# Cañones -- verificado: emiten una nave nueva cada P generaciones (la
# poblacion total crece en +poblacion_de_la_nave cada P generaciones una vez
# estabilizado el mecanismo).
# ---------------------------------------------------------------------------
_gosper_coords = (
    (24, 0), (22, 1), (24, 1), (12, 2), (13, 2), (20, 2), (21, 2), (34, 2),
    (35, 2), (11, 3), (15, 3), (20, 3), (21, 3), (34, 3), (35, 3), (0, 4),
    (1, 4), (10, 4), (16, 4), (20, 4), (21, 4), (0, 5), (1, 5), (10, 5),
    (14, 5), (16, 5), (17, 5), (22, 5), (24, 5), (10, 6), (16, 6), (24, 6),
    (11, 7), (15, 7), (12, 8), (13, 8),
)

_GUNS = [
    KnownPattern(
        "gosper_gun", "Gosper glider gun", "gun",
        "El primer cañon de planeadores descubierto (1970). Estatico, "
        "36 celulas en una caja de 36x9; dispara un planeador cada 30 "
        "generaciones (el primero en la generacion 15). Verificado por "
        "simulacion: la poblacion total crece exactamente +5 cada 30 "
        "generaciones una vez estabilizado.",
        _gosper_coords, period=30,
    ),
]

CATALOG: dict[str, KnownPattern] = {
    p.key: p for p in (*_STILL_LIVES, *_OSCILLATORS, *_SPACESHIPS,
                        *_METHUSELAHS, *_GUNS)
}


def get_pattern(key: str) -> KnownPattern:
    try:
        return CATALOG[key]
    except KeyError as exc:
        raise KeyError(f"Patron desconocido: {key!r}") from exc


def list_patterns(category: str | None = None) -> list[KnownPattern]:
    patterns = list(CATALOG.values())
    if category is not None:
        patterns = [p for p in patterns if p.category == category]
    return patterns


def categories() -> list[str]:
    seen: list[str] = []
    for p in CATALOG.values():
        if p.category not in seen:
            seen.append(p.category)
    return seen
