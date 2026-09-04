"""Pre-V5/V6 deepest request-admission gate at the DisplayManager seam.

``_request_quick_visualizer_mode`` must itself refuse a canonical, dev-active but
*disabled* (not in ``enabled_modes``) mode for a normal runtime/UI request,
without routing to it or re-enabling it. An enabled mode must pass the guard into
activation. Startup/stale-persisted substitution is handled separately by the
startup resolver, not here.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import core.settings.visualizer_presets as visualizer_presets
from engine.display_manager import DisplayManager


class _Owner:
    def __init__(self) -> None:
        self.is_retired = False
        self.request_calls: list[tuple[str, dict]] = []

    def request_mode_change(self, target, **kwargs):  # noqa: D401 - test double
        self.request_calls.append((target, kwargs))
        return True


def _make_manager(section: dict, owner: _Owner) -> DisplayManager:
    mgr = DisplayManager.__new__(DisplayManager)
    mgr._quick_visualizer_owner = owner
    mgr.settings_manager = SimpleNamespace(
        get=lambda key, default=None: (
            section if key == "widgets.spotify_visualizer" else default
        )
    )
    return mgr


def test_request_rejects_disabled_mode_without_activation():
    owner = _Owner()
    section = {"mode": "spectrum", "enabled_modes": ["spectrum", "bubble"]}
    mgr = _make_manager(section, owner)

    # oscilloscope is dev-active and canonical but NOT enabled -> rejected before
    # any activation/model build, and the owner is never asked to change mode.
    assert mgr._request_quick_visualizer_mode("oscilloscope") is False
    assert owner.request_calls == []


def test_request_admits_enabled_mode_into_activation(monkeypatch):
    owner = _Owner()
    section = {"mode": "spectrum", "enabled_modes": ["spectrum", "bubble"]}
    mgr = _make_manager(section, owner)

    class _ReachedActivation(RuntimeError):
        pass

    def _boom(_section):
        raise _ReachedActivation

    # Short-circuit the heavy activation build: reaching it proves the enabled
    # target passed the admission guard (we assert admission, not the full build).
    monkeypatch.setattr(
        visualizer_presets, "resolve_visualizer_activation_payload", _boom
    )

    with pytest.raises(_ReachedActivation):
        mgr._request_quick_visualizer_mode("bubble")


def test_request_all_modes_enabled_default_admits_any_active_mode(monkeypatch):
    # Absent enabled_modes -> every mode enabled (today's default): no gate
    # rejection for any dev-active mode.
    owner = _Owner()
    section = {"mode": "spectrum"}
    mgr = _make_manager(section, owner)

    class _ReachedActivation(RuntimeError):
        pass

    monkeypatch.setattr(
        visualizer_presets,
        "resolve_visualizer_activation_payload",
        lambda _section: (_ for _ in ()).throw(_ReachedActivation()),
    )

    for mode in ("spectrum", "oscilloscope", "sine_wave", "bubble", "devcurve"):
        with pytest.raises(_ReachedActivation):
            mgr._request_quick_visualizer_mode(mode)
