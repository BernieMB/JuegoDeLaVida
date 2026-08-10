"""Parseo y catalogo de reglas *life-like* (notacion ``B{nacen}/S{sobreviven}``).

Cualquier automata celular "life-like" queda definido por dos conjuntos de
enteros 0-8:

- ``birth``: numero de vecinas vivas que hace *nacer* a una celda muerta.
- ``survive``: numero de vecinas vivas que hace *sobrevivir* a una celda viva.

Con esos dos conjuntos se construye una tabla de consulta (LUT) de 18
entradas (2 estados x 9 posibles conteos de vecinos) que permite aplicar la
regla con una simple indexacion vectorizada de NumPy, sin importar cual de
las 2**9 * 2**9 = 262144 reglas posibles se use.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

_RULE_RE = re.compile(r"^\s*B(?P<b>[0-8]*)\s*/\s*S(?P<s>[0-8]*)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Rule:
    """Una regla life-like inmutable, identificada por su rulestring canonico."""

    name: str
    birth: frozenset[int]
    survive: frozenset[int]

    @property
    def rulestring(self) -> str:
        b = "".join(str(n) for n in sorted(self.birth))
        s = "".join(str(n) for n in sorted(self.survive))
        return f"B{b}/S{s}"

    @classmethod
    def parse(cls, text: str, name: str | None = None) -> "Rule":
        """Interpreta un rulestring tipo ``B3/S23`` (orden B/S o S/B, case-insensitive)."""
        text = text.strip()
        match = _RULE_RE.match(text)
        if match is None:
            # Tambien se acepta el orden inverso S23/B3, poco comun pero valido.
            swapped = re.sub(r"^\s*S(?P<s>[0-8]*)\s*/\s*B(?P<b>[0-8]*)\s*$",
                              r"B\g<b>/S\g<s>", text, flags=re.IGNORECASE)
            match = _RULE_RE.match(swapped)
        if match is None:
            raise ValueError(
                f"Regla invalida: {text!r}. Formato esperado 'B<digitos>/S<digitos>', "
                "p.ej. 'B3/S23'."
            )
        birth = frozenset(int(c) for c in match.group("b"))
        survive = frozenset(int(c) for c in match.group("s"))
        return cls(name=name or f"B{match.group('b')}/S{match.group('s')}",
                    birth=birth, survive=survive)

    def build_lut(self) -> np.ndarray:
        """Construye la tabla de 18 entradas: indice = estado*9 + n_vecinos."""
        lut = np.zeros(18, dtype=np.uint8)
        for neighbors in range(9):
            lut[0 * 9 + neighbors] = 1 if neighbors in self.birth else 0
            lut[1 * 9 + neighbors] = 1 if neighbors in self.survive else 0
        return lut

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.name} ({self.rulestring})"


# Catalogo de reglas life-like notables (fuente: Wikipedia, "Life-like cellular
# automaton"). Todas comparten motor: solo cambia la LUT.
KNOWN_RULES: dict[str, Rule] = {
    "life": Rule.parse("B3/S23", "Life (Conway)"),
    "highlife": Rule.parse("B36/S23", "HighLife"),
    "daynight": Rule.parse("B3678/S34678", "Day & Night"),
    "seeds": Rule.parse("B2/S", "Seeds"),
    "diamoeba": Rule.parse("B35678/S5678", "Diamoeba"),
    "2x2": Rule.parse("B36/S125", "2x2"),
    "morley": Rule.parse("B368/S245", "Morley (Move)"),
    "anneal": Rule.parse("B4678/S35678", "Anneal"),
    "lifewithoutdeath": Rule.parse("B3/S012345678", "Life without Death"),
    "replicator": Rule.parse("B1357/S1357", "Replicator"),
}

DEFAULT_RULE_KEY = "life"


def get_rule(key: str) -> Rule:
    """Devuelve una regla del catalogo por clave, o la parsea si es un rulestring."""
    key_norm = key.strip().lower()
    if key_norm in KNOWN_RULES:
        return KNOWN_RULES[key_norm]
    return Rule.parse(key)
