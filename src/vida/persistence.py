"""Persistencia de patrones: guardar el tablero (o una seleccion) y cargar
ficheros RLE/plaintext desde la carpeta ``patterns/``."""

from __future__ import annotations

import datetime
from pathlib import Path

import numpy as np

from vida.engine import LifeEngine
from vida.rle import Pattern, parse_auto, serialize_rle

DEFAULT_PATTERNS_DIR = Path("patterns")


def ensure_patterns_dir(directory: Path | str = DEFAULT_PATTERNS_DIR) -> Path:
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_filename(prefix: str = "tablero", extension: str = "rle") -> str:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.{extension}"


def bounding_box_of_alive_cells(grid: np.ndarray) -> tuple[int, int, int, int] | None:
    """(x0, y0, x1, y1) semiabierto que envuelve todas las celulas vivas, o
    ``None`` si la rejilla esta completamente vacia."""
    rows = np.any(grid, axis=1)
    if not rows.any():
        return None
    cols = np.any(grid, axis=0)
    y0 = int(np.argmax(rows))
    y1 = grid.shape[0] - int(np.argmax(rows[::-1]))
    x0 = int(np.argmax(cols))
    x1 = grid.shape[1] - int(np.argmax(cols[::-1]))
    return x0, y0, x1, y1


def save_board(engine: LifeEngine, path: Path | str, *, name: str = "",
               comment: str = "", author: str = "",
               crop_to_content: bool = True) -> Path:
    """Guarda el tablero completo en RLE. Por defecto se recorta al
    bounding box de celulas vivas (anotando la posicion original en un
    comentario, para poder restaurarlo exactamente con la misma posicion)."""
    path = Path(path)
    grid = engine.grid
    notes = [comment] if comment else []

    if crop_to_content:
        bbox = bounding_box_of_alive_cells(grid)
        if bbox is not None:
            x0, y0, x1, y1 = bbox
            grid = grid[y0:y1, x0:x1]
            notes.append(f"Posicion original en el tablero: ({x0}, {y0})")

    text = serialize_rle(grid, name=name or path.stem, comment="\n".join(notes),
                          author=author, rule=engine.rule.rulestring)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def save_selection(engine: LifeEngine, x0: int, y0: int, x1: int, y1: int,
                    path: Path | str, *, name: str = "", comment: str = "",
                    author: str = "") -> Path:
    """Guarda solo la region [x0,x1) x [y0,y1) del tablero (una seleccion)."""
    path = Path(path)
    grid = engine.extract(x0, y0, x1, y1)
    notes = [comment] if comment else []
    notes.append(f"Posicion original en el tablero: ({x0}, {y0})")
    text = serialize_rle(grid, name=name or path.stem, comment="\n".join(notes),
                          author=author, rule=engine.rule.rulestring)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def load_pattern_file(path: Path | str) -> Pattern:
    """Interpreta un fichero ``.rle`` o ``.cells`` (formato detectado
    automaticamente) y devuelve su ``Pattern``."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    return parse_auto(text)


def list_pattern_files(directory: Path | str = DEFAULT_PATTERNS_DIR) -> list[Path]:
    """Ficheros ``.rle``/``.cells`` disponibles, ordenados por fecha de
    modificacion descendente (los mas recientes primero)."""
    path = ensure_patterns_dir(directory)
    files = list(path.glob("*.rle")) + list(path.glob("*.cells"))
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files
