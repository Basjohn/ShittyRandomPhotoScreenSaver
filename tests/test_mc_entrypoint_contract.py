from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_main_mc_forces_hard_exit_default() -> None:
    src = (ROOT / "main_mc.py").read_text(encoding="utf-8")
    assert 'mgr.set("input.hard_exit", True)' in src
