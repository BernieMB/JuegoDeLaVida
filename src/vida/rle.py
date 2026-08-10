"""Lectura y escritura del formato RLE (Run Length Encoded) y del formato
plaintext (``.cells``), los dos formatos estandar de facto para patrones del
Juego de la Vida (Golly, LifeWiki, Catagolue).

Formato RLE, ejemplo (planeador):

    #N Glider
    #C El planeador mas pequeno y comun.
    #O Richard K. Guy, 1970
    x = 3, y = 3, rule = B3/S23
    bob$2bo$3o!

- ``b`` = celda muerta, ``o`` = celda viva, ``$`` = fin de fila, ``!`` = fin.
- Un numero antes de una letra la repite (``3o`` = 3 celdas vivas seguidas).
- Un numero antes de ``$`` repite el salto de linea (filas en blanco).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from vida.rules import DEFAULT_RULE_KEY, KNOWN_RULES


@dataclass
class Pattern:
    """Un patron cargado o listo para guardar: metadatos + rejilla 0/1."""

    cells: np.ndarray  # uint8, shape (height, width)
    name: str = ""
    comment: str = ""
    author: str = ""
    rule: str = "B3/S23"

    @property
    def width(self) -> int:
        return int(self.cells.shape[1]) if self.cells.size else 0

    @property
    def height(self) -> int:
        return int(self.cells.shape[0]) if self.cells.size else 0

    @property
    def population(self) -> int:
        return int(np.count_nonzero(self.cells))


class RLEParseError(ValueError):
    """El texto no es un RLE valido."""


_HEADER_RE = re.compile(
    r"x\s*=\s*(?P<x>\d+)\s*,\s*y\s*=\s*(?P<y>\d+)\s*(?:,\s*rule\s*=\s*(?P<rule>[^,\s]+))?",
    re.IGNORECASE,
)


def parse_rle(text: str) -> Pattern:
    """Interpreta un patron en formato RLE (cabeceras ``#N``/``#C``/``#O`` +
    linea ``x = .., y = .., rule = ..`` + datos terminados en ``!``)."""
    name = ""
    comments: list[str] = []
    author = ""
    header_line: str | None = None
    data_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            tag = line[1:2]
            rest = line[2:].strip()
            if tag in ("N", "n"):
                name = rest
            elif tag in ("C", "c"):
                comments.append(rest)
            elif tag in ("O", "o"):
                author = rest
            # Se ignoran otras cabeceras (#R, #P, #r...): no aportan a la
            # rejilla y no son necesarias para nuestro caso de uso.
            continue
        if header_line is None and "=" in line:
            header_line = line
            continue
        data_lines.append(line)

    if header_line is None:
        raise RLEParseError("El RLE no tiene cabecera 'x = .., y = .., rule = ..'")

    match = _HEADER_RE.search(header_line)
    if match is None:
        raise RLEParseError(f"Cabecera RLE invalida: {header_line!r}")
    width = int(match.group("x"))
    height = int(match.group("y"))
    rule = match.group("rule") or "B3/S23"

    grid = np.zeros((height, width), dtype=np.uint8)
    x = y = 0
    count_str = ""
    for ch in "".join(data_lines):
        if ch.isdigit():
            count_str += ch
            continue
        count = int(count_str) if count_str else 1
        count_str = ""
        if ch in "bB":
            x += count
        elif ch in "oO":
            x_end = min(x + count, width)
            if 0 <= y < height and x < width:
                grid[y, x:x_end] = 1
            x += count
        elif ch == "$":
            y += count
            x = 0
        elif ch == "!":
            break
        # Cualquier otro caracter (espacios ya recortados, saltos de linea)
        # se ignora silenciosamente.

    return Pattern(cells=grid, name=name, comment="\n".join(comments),
                    author=author, rule=rule)


def serialize_rle(
    pattern: Pattern | np.ndarray,
    *,
    name: str = "",
    comment: str = "",
    author: str = "",
    rule: str = "B3/S23",
    line_width: int = 70,
) -> str:
    """Serializa una rejilla (o un ``Pattern``) a texto RLE."""
    if isinstance(pattern, Pattern):
        grid = pattern.cells
        name = name or pattern.name
        comment = comment or pattern.comment
        author = author or pattern.author
        rule = rule if rule != "B3/S23" else pattern.rule
    else:
        grid = pattern

    height, width = grid.shape
    header_lines: list[str] = []
    if name:
        header_lines.append(f"#N {name}")
    if author:
        header_lines.append(f"#O {author}")
    if comment:
        for c in comment.splitlines():
            header_lines.append(f"#C {c}")
    header_lines.append(f"x = {width}, y = {height}, rule = {rule}")

    row_tokens: list[str] = []
    for y in range(height):
        row = grid[y]
        runs: list[tuple[int, int]] = []
        if width > 0:
            current = int(row[0])
            count = 1
            for val in row[1:]:
                val = int(val)
                if val == current:
                    count += 1
                else:
                    runs.append((current, count))
                    current = val
                    count = 1
            runs.append((current, count))
        if runs and runs[-1][0] == 0:
            runs.pop()  # el final de fila ($ o !) ya implica muertas al final
        row_tokens.append(
            "".join(f"{c if c > 1 else ''}{'o' if v else 'b'}" for v, c in runs)
        )

    body_parts: list[str] = []
    i, n = 0, len(row_tokens)
    while i < n:
        if row_tokens[i] == "":
            j = i
            while j < n and row_tokens[j] == "":
                j += 1
            blank_count = j - i
            if j < n:  # no hace falta emitir "$" final tras la ultima fila
                body_parts.append(f"{blank_count if blank_count > 1 else ''}$")
            i = j
        else:
            body_parts.append(row_tokens[i])
            if i < n - 1:
                body_parts.append("$")
            i += 1
    body = "".join(body_parts) + "!"

    wrapped_lines: list[str] = []
    cur = ""
    for ch in body:
        cur += ch
        if len(cur) >= line_width:
            wrapped_lines.append(cur)
            cur = ""
    if cur:
        wrapped_lines.append(cur)

    return "\n".join(header_lines + wrapped_lines) + "\n"


def parse_plaintext(text: str) -> Pattern:
    """Interpreta el formato plaintext ``.cells`` (``!`` comentario, ``.``
    muerta, ``O``/``o``/``*`` viva)."""
    name = ""
    comments: list[str] = []
    rows: list[str] = []
    for line in text.splitlines():
        if line.startswith("!"):
            content = line[1:].strip()
            if content.lower().startswith("name:"):
                name = content.split(":", 1)[1].strip()
            elif content:
                comments.append(content)
            continue
        rows.append(line.rstrip("\n\r"))
    while rows and rows[-1].strip() == "":
        rows.pop()
    width = max((len(r) for r in rows), default=0)
    height = len(rows)
    grid = np.zeros((height, width), dtype=np.uint8)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in "oO*":
                grid[y, x] = 1
    return Pattern(cells=grid, name=name, comment="\n".join(comments),
                    rule="B3/S23")


def serialize_plaintext(pattern: Pattern | np.ndarray, *, name: str = "",
                         comment: str = "") -> str:
    if isinstance(pattern, Pattern):
        grid = pattern.cells
        name = name or pattern.name
        comment = comment or pattern.comment
    else:
        grid = pattern
    lines: list[str] = []
    if name:
        lines.append(f"!Name: {name}")
    if comment:
        for c in comment.splitlines():
            lines.append(f"!{c}")
    for row in grid:
        lines.append("".join("O" if v else "." for v in row))
    return "\n".join(lines) + "\n"


def parse_auto(text: str) -> Pattern:
    """Detecta el formato (RLE o plaintext) y lo interpreta."""
    stripped = text.strip()
    for line in stripped.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        if _HEADER_RE.search(line):
            return parse_rle(text)
        break
    return parse_plaintext(text)


def coords_to_grid(coords: list[tuple[int, int]]) -> np.ndarray:
    """Convierte una lista de coordenadas (x, y) vivas en la rejilla minima
    (bounding box) que las contiene, en formato uint8."""
    if not coords:
        return np.zeros((0, 0), dtype=np.uint8)
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    grid = np.zeros((max_y - min_y + 1, max_x - min_x + 1), dtype=np.uint8)
    for x, y in coords:
        grid[y - min_y, x - min_x] = 1
    return grid
