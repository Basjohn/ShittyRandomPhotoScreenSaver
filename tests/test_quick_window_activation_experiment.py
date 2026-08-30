"""Operator-gated Display-1 flash activation A/B must be inert by default.

Physical `[QUICK_SURFACE]` telemetry ties every recurring Display-1 black flash
to a native `window_active_changed` on the secondary window while the scene
graph and frame swaps stay healthy. `SRPSS_QUICK_ACTIVATION` lets the operator
A/B the window activation policy against `tools/black_flash_capture.py`. These
bars pin that the default behaviour is unchanged and that each experiment value
maps to the exact policy fields, so nothing silently ships a focus change.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from rendering.quick.state import QuickWindowPolicy


def test_default_policy_still_forces_activation_and_accepts_focus() -> None:
    policy = QuickWindowPolicy()
    assert policy.accepts_focus is True
    assert policy.proactively_activate is True
    # Default flags must not carry the no-activate bit.
    assert not (policy.flags() & Qt.WindowType.WindowDoesNotAcceptFocus)


def test_no_focus_policy_sets_the_no_activate_window_bit() -> None:
    policy = QuickWindowPolicy(accepts_focus=False, proactively_activate=False)
    assert bool(policy.flags() & Qt.WindowType.WindowDoesNotAcceptFocus)


def test_activation_experiment_env_maps_to_policy_fields(monkeypatch) -> None:
    from engine.display_manager import DisplayManager

    monkeypatch.delenv("SRPSS_QUICK_ACTIVATION", raising=False)
    assert DisplayManager._quick_activation_experiment() == {
        "accepts_focus": True,
        "proactively_activate": True,
    }

    monkeypatch.setenv("SRPSS_QUICK_ACTIVATION", "no-activate")
    assert DisplayManager._quick_activation_experiment() == {
        "accepts_focus": True,
        "proactively_activate": False,
    }

    monkeypatch.setenv("SRPSS_QUICK_ACTIVATION", "no-focus")
    assert DisplayManager._quick_activation_experiment() == {
        "accepts_focus": False,
        "proactively_activate": False,
    }

    # Unknown values are inert (fail safe to current behaviour).
    monkeypatch.setenv("SRPSS_QUICK_ACTIVATION", "banana")
    assert DisplayManager._quick_activation_experiment() == {
        "accepts_focus": True,
        "proactively_activate": True,
    }
