"""Zero-burden admission coverage for the opt-in P1 switch/resource telemetry.

The switch/resource render-host lifecycle telemetry is a diagnostic experiment,
not runtime behaviour. These tests pin the hard requirement: an ordinary
Standard/MC runtime (no flag) allocates no lifecycle telemetry object, keeps no
new bookkeeping, and surfaces no new snapshot; ``--viz-switch-telemetry`` admits
the boundary telemetry without the A/B/C driver; and ``--abc-drive`` implicitly
admits the same telemetry alongside the driver. The pre-existing per-node
``VisualizerRenderNodeTelemetry`` (with its cheaper P5 ``note_*`` path) is
unaffected either way.
"""

from __future__ import annotations

import pytest

from core.diagnostics import experiment_flags as ef
from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
from rendering.quick.visualizer.telemetry import (
    VisualizerRenderHostLifecycleTelemetry,
    VisualizerRenderNodeTelemetry,
)


@pytest.fixture(autouse=True)
def _reset_active_flags():
    ef.override_active_flags_for_testing(None)
    yield
    ef.override_active_flags_for_testing(None)


def _activate(argv: list[str]) -> None:
    ef.activate_experiment_flags(ef.parse_experiment_flags(argv))


# --- NO FLAG: ordinary Standard/MC runtime ---------------------------------


def test_no_flag_host_allocates_no_lifecycle_telemetry():
    _activate(["main.py", "/s"])  # ordinary RUN launch, no diagnostic admission
    host = QuickVisualizerRenderHost()
    # No allocation, no snapshot, no new bookkeeping surfaced.
    assert host.lifecycle_telemetry_enabled is False
    assert host._lifecycle is None
    assert host.lifecycle_snapshot() is None


def test_no_flag_host_switch_path_is_a_noop_for_telemetry(monkeypatch):
    """Driving mode changes on a disabled host records nothing and never raises."""
    from types import SimpleNamespace

    from rendering.quick.visualizer import render_host as render_host_module

    _activate(["main.py", "/s"])
    host = QuickVisualizerRenderHost()
    host._quad_vao = 7
    host._quad_vbo = 7
    monkeypatch.setattr(
        render_host_module,
        "QOpenGLContext",
        SimpleNamespace(currentContext=staticmethod(object)),
    )
    monkeypatch.setattr(
        render_host_module,
        "resolve_quick_visualizer_renderer",
        lambda mode_id: SimpleNamespace(
            has_resources=True,
            render=lambda _frame: None,
            release_resources=lambda: None,
        ),
    )
    monkeypatch.setattr(
        render_host_module._InheritedGlState,
        "capture",
        lambda: SimpleNamespace(restore=lambda: None),
    )
    for name in (
        "glEnable",
        "glBlendEquationSeparate",
        "glBlendFuncSeparate",
        "glDisable",
        "glDepthMask",
        "glViewport",
    ):
        monkeypatch.setattr(render_host_module.gl, name, lambda *_args: None)

    for mode in ("bubble", "spectrum", "bubble"):
        snapshot = SimpleNamespace(logical=SimpleNamespace(mode_id=mode))
        assert host.render(
            snapshot=snapshot,
            viewport=(0, 0, 10, 10),
            logical_size=(10.0, 10.0),
            matrix_values=(1.0,) * 16,
        ) == mode
    # Still nothing allocated or recorded.
    assert host.lifecycle_telemetry_enabled is False
    assert host.lifecycle_snapshot() is None


# --- --viz-switch-telemetry: telemetry, no driver --------------------------


def test_viz_switch_telemetry_flag_admits_boundary_telemetry():
    _activate(["main.py", "/s", "--viz-switch-telemetry"])
    assert ef.visualizer_switch_telemetry_admitted() is True
    assert ef.abc_drive_condition() is None  # no A/B/C driver admitted
    host = QuickVisualizerRenderHost()
    assert host.lifecycle_telemetry_enabled is True
    assert host.lifecycle_snapshot() is not None


# --- --abc-drive: telemetry implicitly enabled + driver admitted -----------


def test_abc_drive_flag_implicitly_admits_boundary_telemetry():
    _activate(["main.py", "/s", "--abc-drive=B"])
    assert ef.abc_drive_condition() == "B"  # driver admitted
    assert ef.visualizer_switch_telemetry_admitted() is True  # telemetry too
    host = QuickVisualizerRenderHost()
    assert host.lifecycle_telemetry_enabled is True
    assert host.lifecycle_snapshot() is not None


# --- injection seam independent of process argv ----------------------------


def test_injected_telemetry_overrides_disabled_admission():
    _activate(["main.py", "/s"])  # admission disabled
    host = QuickVisualizerRenderHost(
        lifecycle_telemetry=VisualizerRenderHostLifecycleTelemetry()
    )
    assert host.lifecycle_telemetry_enabled is True
    assert host.lifecycle_snapshot() is not None


# --- pre-existing node telemetry unaffected --------------------------------


def test_node_telemetry_note_path_remains_cheap_and_present():
    """The pre-existing per-node telemetry is unrelated to the opt-in admission."""
    _activate(["main.py", "/s"])  # no lifecycle telemetry admitted
    telemetry = VisualizerRenderNodeTelemetry()
    before = telemetry.snapshot()
    telemetry.note_sync()
    telemetry.note_draw("bubble", logical_revision=3, logical_timestamp=1.0)
    after = telemetry.snapshot()
    assert after.sync_count == before.sync_count + 1
    assert after.drawn_mode_id == "bubble"
