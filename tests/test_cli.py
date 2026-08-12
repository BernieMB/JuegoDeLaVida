from __future__ import annotations

from vida.cli import build_arg_parser


def test_fullscreen_flag_is_available():
    args = build_arg_parser().parse_args(["--fullscreen"])
    assert args.fullscreen is True
