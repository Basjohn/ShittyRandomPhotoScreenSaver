"""Linux display power: GNOME Mutter's PowerSaveMode when the session bus has it, else the explicit inert backend.

Runs only on Linux (Docs/Guardrails/Linux_Compatibility.md §7). Unvalidated on a real desktop: see Linux_Plan.md §3.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core import display_power
from core.display_power import InertDisplayPowerBackend, LinuxMutterDisplayPowerWatcher


def test_mutter_is_selected_only_when_it_answers(monkeypatch):
    pytest.importorskip("jeepney")
    monkeypatch.setattr(LinuxMutterDisplayPowerWatcher, "available", lambda self: True)
    backend = display_power.create_display_power_backend(lambda _s: None, lambda _o: None,
                                                         thread_manager=SimpleNamespace())
    assert isinstance(backend, LinuxMutterDisplayPowerWatcher)
    monkeypatch.setattr(LinuxMutterDisplayPowerWatcher, "available", lambda self: False)
    backend = display_power.create_display_power_backend(lambda _s: None, lambda _o: None,
                                                         thread_manager=SimpleNamespace())
    assert isinstance(backend, InertDisplayPowerBackend)


def test_without_a_listener_lane_linux_is_explicitly_inert(monkeypatch):
    monkeypatch.setattr(LinuxMutterDisplayPowerWatcher, "available", lambda self: pytest.fail("bus probed"))
    backend = display_power.create_display_power_backend(lambda _s: None, lambda _o: None, thread_manager=None)
    assert isinstance(backend, InertDisplayPowerBackend) and backend.start() is True


def test_the_authority_stays_on_with_the_inert_backend(qt_app):
    authority = display_power.DisplayPowerAuthority(
        backend_factory=lambda *_a, **_k: InertDisplayPowerBackend("test"))
    authority.start()
    qt_app.processEvents()
    assert authority.is_on and authority.generation == 0 and authority.backend_name == "inert"
    authority.retire()
