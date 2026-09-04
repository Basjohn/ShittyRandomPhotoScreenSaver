"""V5 Settings-body dormancy contract (pre-V5/V6 gate item 4).

Proves the canonical lazy Settings-body ownership mechanism: opening Settings
constructs no disabled/unselected mode bodies; selecting an enabled mode builds
only that body; disabling a mode retires its body without losing state; and
reselecting a re-enabled mode reconstructs it from the preserved state authority.
No timers/pollers/workers; no second state authority; save/load never constructs
a body; and importing the registry imports no mode builder.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from core.settings.visualizer_mode_body_host import (
    SETUP_PILL_ID,
    VisualizerModeBodyHost,
    visualizer_pill_model,
)

_DISABLED = ("oscilloscope", "sine_wave", "devcurve")


class _Authority:
    """Stand-in for the sole settings/model state authority.

    Holds each mode's authored local state. The host reads through the factory
    but never mutates or copies this into a second owner.
    """

    def __init__(self, state: dict[str, dict]) -> None:
        self.state = {mode: dict(values) for mode, values in state.items()}


class _Body:
    def __init__(self, mode_id: str, snapshot: dict) -> None:
        self.mode_id = mode_id
        self.snapshot = snapshot  # captured from the authority at construction
        self.retired = False


def _make_host(authority: _Authority, enabled, *, constructions, retirements):
    def factory(mode_id: str) -> _Body:
        constructions.append(mode_id)
        # Reconstruct from the PRESERVED authority state (never a default reset).
        return _Body(mode_id, dict(authority.state.get(mode_id, {})))

    def retire(mode_id: str, body: _Body) -> None:
        body.retired = True
        retirements.append(mode_id)

    return VisualizerModeBodyHost(
        body_factory=factory, retire_body=retire, enabled_modes=enabled
    )


def _authority() -> _Authority:
    return _Authority(
        {
            "spectrum": {"drop_speed": 1.85, "fill": [31, 32, 33, 34]},
            "bubble": {"manual_floor": 0.27},
            # Disabled modes still carry authored state that must survive.
            "devcurve": {"active_layer": "mids", "manual_floor": 0.19},
        }
    )


def test_opening_settings_constructs_no_disabled_bodies():
    constructions: list[str] = []
    host = _make_host(
        _authority(), ["spectrum", "bubble"],
        constructions=constructions, retirements=[],
    )
    # Host creation alone constructs nothing.
    assert constructions == []
    assert host.constructed_modes() == frozenset()
    # Even after selecting the active enabled mode, no disabled body appears.
    host.select("spectrum")
    assert constructions == ["spectrum"]
    assert host.constructed_modes() == frozenset({"spectrum"})
    for disabled in _DISABLED:
        assert not host.is_constructed(disabled)


def test_selecting_enabled_mode_constructs_only_that_body():
    constructions: list[str] = []
    host = _make_host(
        _authority(), ["spectrum", "bubble"],
        constructions=constructions, retirements=[],
    )
    host.select("bubble")
    assert constructions == ["bubble"]
    assert host.constructed_modes() == frozenset({"bubble"})
    assert host.selected_mode == "bubble"


def test_switching_between_enabled_modes_never_constructs_disabled():
    constructions: list[str] = []
    host = _make_host(
        _authority(), ["spectrum", "bubble"],
        constructions=constructions, retirements=[],
    )
    host.select("spectrum")
    host.select("bubble")
    host.select("spectrum")  # cached, no re-construction
    assert constructions == ["spectrum", "bubble"]
    assert all(mode not in constructions for mode in _DISABLED)
    assert host.constructed_modes() == frozenset({"spectrum", "bubble"})


def test_selecting_a_disabled_mode_is_rejected():
    host = _make_host(_authority(), ["spectrum", "bubble"], constructions=[], retirements=[])
    with pytest.raises(ValueError):
        host.select("oscilloscope")


def test_disabling_mode_retires_body_without_losing_state():
    authority = _authority()
    constructions: list[str] = []
    retirements: list[str] = []
    host = _make_host(
        authority, ["spectrum", "bubble"],
        constructions=constructions, retirements=retirements,
    )
    host.select("spectrum")
    original_state = dict(authority.state["spectrum"])

    retired = host.set_enabled_modes(["bubble"])

    assert retired == ("spectrum",)
    assert retirements == ["spectrum"]
    assert not host.is_constructed("spectrum")
    assert host.selected_mode is None  # selected mode was disabled -> cleared
    # Persisted state is untouched: the host never owned it.
    assert authority.state["spectrum"] == original_state


def test_reenable_reselect_reconstructs_from_preserved_state():
    authority = _authority()
    constructions: list[str] = []
    host = _make_host(
        authority, ["spectrum", "bubble"],
        constructions=constructions, retirements=[],
    )
    first_body = host.select("spectrum")
    host.set_enabled_modes(["bubble"])            # spectrum disabled + retired
    host.set_enabled_modes(["spectrum", "bubble"])  # spectrum re-enabled

    second_body = host.select("spectrum")

    # A fresh body was reconstructed (not the retired instance)...
    assert second_body is not first_body
    assert constructions == ["spectrum", "spectrum"]
    # ...from the exact preserved authority state — no default reset.
    assert second_body.snapshot == {"drop_speed": 1.85, "fill": [31, 32, 33, 34]}
    assert second_body.snapshot == authority.state["spectrum"]


def test_settings_recreation_preserves_enabled_and_disabled_state():
    authority = _authority()
    constructions: list[str] = []
    # Simulate Settings-dialog recreation: a brand-new host from the same
    # authority. It must construct nothing and derive the enabled set correctly,
    # while the disabled mode's authored state remains intact in the authority.
    host = _make_host(
        authority, ["spectrum", "bubble"],
        constructions=constructions, retirements=[],
    )
    assert constructions == []
    assert host.enabled_modes == ("spectrum", "bubble")
    assert authority.state["devcurve"] == {"active_layer": "mids", "manual_floor": 0.19}


def test_save_load_serialization_constructs_no_body():
    from core.settings.models import SpotifyVisualizerSettings

    constructions: list[str] = []
    _make_host(_authority(), ["spectrum", "bubble"], constructions=constructions, retirements=[])

    # A full settings round trip must not touch the body host at all.
    payload = {"mode": "bubble", "enabled_modes": ["spectrum", "bubble"]}
    model = SpotifyVisualizerSettings.from_mapping(payload, apply_preset_overlay=False)
    persisted = model.to_dict()

    class _Dummy:
        def get(self, key, default=None):
            return persisted.get(key, default)

    SpotifyVisualizerSettings.from_settings(_Dummy())
    assert constructions == []


def test_pill_model_is_setup_plus_enabled_in_canonical_order():
    pills = visualizer_pill_model(["bubble", "spectrum"])
    assert pills[0] == (SETUP_PILL_ID, "Setup")
    # Canonical order (spectrum before bubble), disabled modes absent.
    assert [pid for pid, _label in pills[1:]] == ["spectrum", "bubble"]
    assert dict(pills)["spectrum"] == "Spectrum"
    assert dict(pills)["bubble"] == "Bubble"
    # Absent selection -> every mode enabled (migration default).
    assert [pid for pid, _ in visualizer_pill_model(None)[1:]] == [
        "spectrum", "oscilloscope", "sine_wave", "bubble", "devcurve",
    ]


def test_importing_registry_imports_no_mode_settings_builder():
    """Fresh-process proof that the Settings-builder wiring stays lazy."""
    probe = (
        "import sys\n"
        "import core.settings.visualizer_mode_body_host  # noqa: F401\n"
        "import core.settings.visualizer_mode_registry as r\n"
        "builders = [m for m in sys.modules if m.endswith('_builder') "
        "and m.startswith('ui.tabs.media.')]\n"
        "d = r.get_visualizer_mode_descriptor('spectrum')\n"
        "assert d.settings_builder_module == 'ui.tabs.media.spectrum_builder', d\n"
        "assert d.settings_builder_factory == 'build_spectrum_ui', d\n"
        "print('BUILDERS=' + ','.join(sorted(builders)))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path.cwd(), capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines()[-1] == "BUILDERS="
