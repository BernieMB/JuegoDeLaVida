from __future__ import annotations

import pytest

from vida.rules import KNOWN_RULES, Rule, get_rule


def test_parse_basic_rulestring():
    rule = Rule.parse("B3/S23")
    assert rule.birth == frozenset({3})
    assert rule.survive == frozenset({2, 3})
    assert rule.rulestring == "B3/S23"


def test_parse_is_case_insensitive_and_trims_whitespace():
    rule = Rule.parse("  b3 / s23  ")
    assert rule.rulestring == "B3/S23"


def test_parse_swapped_order_s_before_b():
    rule = Rule.parse("S23/B3")
    assert rule.birth == frozenset({3})
    assert rule.survive == frozenset({2, 3})


def test_parse_empty_survive_set_seeds():
    rule = Rule.parse("B2/S")
    assert rule.birth == frozenset({2})
    assert rule.survive == frozenset()
    assert rule.rulestring == "B2/S"


def test_parse_invalid_raises():
    with pytest.raises(ValueError):
        Rule.parse("not a rule")
    with pytest.raises(ValueError):
        Rule.parse("B9/S23")  # 9 no es un conteo de vecinos valido (0-8)


def test_rulestring_roundtrip_sorts_digits():
    rule = Rule.parse("B63/S32")
    assert rule.rulestring == "B36/S23"


@pytest.mark.parametrize(
    "key, expected",
    [
        ("life", "B3/S23"),
        ("highlife", "B36/S23"),
        ("daynight", "B3678/S34678"),
        ("seeds", "B2/S"),
        ("diamoeba", "B35678/S5678"),
        ("2x2", "B36/S125"),
        ("morley", "B368/S245"),
        ("anneal", "B4678/S35678"),
        ("lifewithoutdeath", "B3/S012345678"),
        ("replicator", "B1357/S1357"),
    ],
)
def test_known_rules_catalog(key, expected):
    assert KNOWN_RULES[key].rulestring == expected


def test_get_rule_from_catalog_key():
    assert get_rule("life").rulestring == "B3/S23"
    assert get_rule("HighLife").rulestring == "B36/S23"


def test_get_rule_from_raw_rulestring_not_in_catalog():
    rule = get_rule("B36/S125")
    assert rule.rulestring == "B36/S125"


def test_build_lut_matches_conway_truth_table():
    lut = KNOWN_RULES["life"].build_lut()
    # Celda muerta (estado 0): nace solo con exactamente 3 vecinas.
    for n in range(9):
        assert lut[0 * 9 + n] == (1 if n == 3 else 0), f"muerta con {n} vecinas"
    # Celda viva (estado 1): sobrevive con 2 o 3 vecinas.
    for n in range(9):
        assert lut[1 * 9 + n] == (1 if n in (2, 3) else 0), f"viva con {n} vecinas"


def test_build_lut_highlife_adds_birth_on_six():
    lut = KNOWN_RULES["highlife"].build_lut()
    assert lut[0 * 9 + 6] == 1  # B36: tambien nace con 6 vecinas
    assert lut[0 * 9 + 3] == 1
    assert lut[1 * 9 + 2] == 1
    assert lut[1 * 9 + 3] == 1
    assert lut[1 * 9 + 6] == 0  # S23 no incluye 6
