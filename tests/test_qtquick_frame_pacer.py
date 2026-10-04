"""Contracts for Qt-owned retained-scene transition frame demand."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest
from PySide6.QtCore import QObject

from rendering.quick.frame_pacer import QuickFrameDemand, QuickFramePacer, QuickPacerState

ROOT = Path(__file__).resolve().parents[1]


class _Window(QObject):
    def __init__(self, *, visible: bool = True) -> None:
        super().__init__()
        self._visible = bool(visible)

    def isVisible(self) -> bool:  # noqa: N802 - mirrors QWindow API
        return self._visible


class _NativeDriver:
    def __init__(self) -> None:
        self.calls: list[tuple[bool, float]] = []
        self.animation_ticks = 0
        self.update_requests = 0

    def publish(self, active: bool, target_hz: float) -> None:
        self.calls.append((bool(active), float(target_hz)))

    def describe(self) -> dict[str, object]:
        active, target_hz = self.calls[-1] if self.calls else (False, 0.0)
        return {
            "animation_running": active,
            "target_hz": target_hz,
            "animation_ticks": self.animation_ticks,
            "update_requests": self.update_requests,
        }


def _pacer(target_hz: float = 100.0, *, visible: bool = True):
    window = _Window(visible=visible)
    native = _NativeDriver()
    pacer = QuickFramePacer(
        window,  # type: ignore[arg-type]
        target_hz,
        driver_state_setter=native.publish,
        driver_state_provider=native.describe,
    )
    return pacer, window, native


@pytest.mark.parametrize("rate", (0.0, -1.0, math.inf, -math.inf, math.nan))
def test_target_rate_must_be_finite_and_positive(rate):
    with pytest.raises(ValueError):
        QuickPacerState(rate)


def test_pacer_has_no_python_timer_frame_swap_feedback_or_visualizer_demand() -> None:
    source = (ROOT / "rendering" / "quick" / "frame_pacer.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_names: set[str] = set()
    referenced_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported_names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.Name):
            referenced_names.add(node.id)
    assert "QTimer" not in imported_names
    assert "QTimer" not in referenced_names
    assert "PreciseTimer" not in referenced_names
    assert "frameSwapped.connect" not in source
    assert "requestUpdate()" not in source
    for forbidden in ("set_visualizer_active", "set_visualizer_sync"):
        assert forbidden not in source
    assert not hasattr(QuickFrameDemand, "VISUALIZER")


def test_qml_frame_driver_uses_native_animation_and_per_display_gate() -> None:
    qml = (ROOT / "rendering" / "quick" / "qml" / "DisplayScene.qml").read_text(encoding="utf-8")
    assert "FrameAnimation {" in qml
    assert "running: displayScene.transitionFrameDriverActive" in qml
    assert "transitionFrameTargetHz" in qml
    assert "const intervalS = 1.0 / Math.max(1.0, targetHz)" in qml
    assert "intervalsPassed" in qml
    assert "transitionRenderItem.update()" in qml
    assert "onTransitionFrameTargetHzChanged" in qml
    assert "transitionFrameNextDueS = 0.0" in qml
    assert "if (running)" in qml
    assert "reset()" in qml
    assert "Timer {" not in qml



def test_qml_native_driver_discards_old_deadline_on_restart_and_display_retarget() -> None:
    qml = (ROOT / "rendering" / "quick" / "qml" / "DisplayScene.qml").read_text(encoding="utf-8")

    retarget = qml.split("onTransitionFrameTargetHzChanged", 1)[1].split("FrameAnimation {", 1)[0]
    assert "transitionFrameNextDueS = 0.0" in retarget

    running_changed = qml.split("onRunningChanged:", 1)[1].split("onTriggered:", 1)[0]
    assert "transitionFrameNextDueS = 0.0" in running_changed
    assert "if (running)" in running_changed
    assert "reset()" in running_changed

    triggered = qml.split("onTriggered:", 1)[1].split("}", 1)[0]
    # No while/catch-up loop may repay elapsed time after a stall. The gate
    # computes how many intervals were missed and still issues one update only.
    assert "while" not in triggered


def test_hidden_window_keeps_native_driver_stopped_until_resume() -> None:
    pacer, window, native = _pacer(60.0, visible=False)
    pacer.set_transition_active(True)

    assert pacer.describe()["paused"] is True
    assert native.calls == [(False, 60.0)]

    window._visible = True
    assert pacer.resume() is True
    assert native.calls[-1] == (True, 60.0)


def test_transition_demand_publishes_native_state_only_on_control_edges() -> None:
    pacer, _window, native = _pacer(165.0)
    assert pacer.is_active() is False
    pacer.set_transition_active(True)
    pacer.set_transition_active(True)
    assert pacer.is_active() is True
    assert native.calls == [(True, 165.0)]

    pacer.set_transition_active(False)
    assert native.calls[-1] == (False, 165.0)
    assert len(native.calls) == 2


def test_pause_resume_stop_preserve_demand_without_per_frame_python_work() -> None:
    pacer, _window, native = _pacer(60.0)
    pacer.set_transition_active(True)
    assert native.calls[-1] == (True, 60.0)

    assert pacer.pause() is True
    assert pacer.pause() is False
    assert pacer.demands == QuickFrameDemand.TRANSITION
    assert native.calls[-1] == (False, 60.0)

    assert pacer.resume() is True
    assert pacer.resume() is False
    assert native.calls[-1] == (True, 60.0)

    pacer.stop()
    assert pacer.is_active() is False
    assert native.calls[-1] == (False, 60.0)


def test_stop_does_not_clear_hidden_window_pause_ownership() -> None:
    pacer, window, native = _pacer(60.0, visible=False)
    pacer.set_transition_active(True)
    assert pacer.describe()["paused"] is True
    assert native.calls[-1] == (False, 60.0)

    pacer.stop()
    assert pacer.demands == QuickFrameDemand.NONE
    assert pacer.describe()["paused"] is True
    assert native.calls[-1] == (False, 60.0)

    # Re-admission while the window is still hidden remains inactive. Only the
    # visibility owner may clear the pause via resume().
    pacer.set_transition_active(True)
    assert pacer.is_active() is False
    assert native.calls[-1] == (False, 60.0)
    window._visible = True
    assert pacer.resume() is True
    assert native.calls[-1] == (True, 60.0)


def test_target_retarget_updates_native_per_display_gate() -> None:
    pacer, _window, native = _pacer(60.0)
    pacer.set_transition_active(True)
    pacer.set_target_hz(120.0)
    assert pacer.target_hz == 120.0
    assert native.calls[-1] == (True, 120.0)
    assert pacer.describe()["interval_ns"] == pytest.approx(round(1_000_000_000 / 120), abs=1)


def test_describe_samples_native_counters_without_per_frame_callback() -> None:
    pacer, _window, native = _pacer(165.0)
    pacer.set_transition_active(True)
    native.animation_ticks = 17
    native.update_requests = 11

    described = pacer.describe()
    assert described["driver"] == "qml_frame_animation"
    assert described["requested_opportunities"] == 17
    assert described["issued_update_requests"] == 11
    assert "skipped_deadlines" not in described
    assert "frame_swaps" not in described
    assert "update_pending" not in described
    assert described["animation_running"] is True


def test_close_stops_native_driver_and_rejects_new_admission() -> None:
    pacer, _window, native = _pacer()
    pacer.set_transition_active(True)
    pacer.close()
    assert native.calls[-1] == (False, 100.0)
    assert pacer.describe()["closed"] is True
    with pytest.raises(RuntimeError, match="closed"):
        pacer.set_transition_active(True)


def test_only_supported_nonzero_demand_bits_are_accepted() -> None:
    pacer, _window, _native = _pacer()
    with pytest.raises(ValueError, match="unsupported"):
        pacer.set_demand(QuickFrameDemand.NONE, True)
    with pytest.raises(ValueError, match="unsupported"):
        pacer.set_demand(QuickFrameDemand(8), True)


def test_describe_names_only_actual_custom_quick_demands() -> None:
    pacer, _window, _native = _pacer()
    pacer.set_transition_active(True)
    assert pacer.describe()["demands"] == ["transition"]


_GATE_ENGINE = []


def _qml_transition_gate():
    """DisplayScene.qml's pure per-tick gate, evaluated by a real JS engine (one engine for the
    module; only JSON text crosses it, so no JS value outlives it)."""
    import json

    from PySide6.QtCore import QCoreApplication
    from PySide6.QtQml import QJSEngine

    QCoreApplication.instance() or QCoreApplication([])
    if not _GATE_ENGINE:
        qml = (ROOT / "rendering" / "quick" / "qml" / "DisplayScene.qml").read_text(encoding="utf-8")
        start = qml.index("function transitionFrameGate(")
        end = qml.index("\n    }\n", start) + len("\n    }\n")
        body = qml[start:end]
        engine = QJSEngine()
        engine.evaluate(body)
        _GATE_ENGINE.append(engine)
    engine = _GATE_ENGINE[0]

    def tick(gate, elapsed_s, target_hz, visualizer_frames, fill_s=0.025):
        text = engine.evaluate(
            f"JSON.stringify(transitionFrameGate({json.dumps(gate)}, {elapsed_s!r}, {target_hz!r}, "
            f"{visualizer_frames!r}, {fill_s!r}))"
        ).toString()
        result = json.loads(text)
        return result, {"nextDueS": result["nextDueS"], "lastVisualizerS": result["lastVisualizerS"],
                        "seenVisualizerFrames": result["seenVisualizerFrames"]}

    return engine, tick


def test_transition_rides_visualizer_frames_and_fills_in_when_they_stop() -> None:
    """Bubble micro-flicker (2026-10-03): on a 165 Hz display the transition's own ~115 Hz ticks,
    unaligned with the Visualizer's 90 Hz frames, drew ~210 frames a second, ~120 of them an
    unchanged Visualizer state. While Visualizer frames arrive the transition requests none of
    its own (it samples wall time on every frame); once they stop it fills in at its own rate."""
    _engine, tick = _qml_transition_gate()
    gate = {"nextDueS": 0.0, "lastVisualizerS": -1.0, "seenVisualizerFrames": 0}
    requests, t, frames = 0, 0.0, 0
    for i in range(115):                         # one second of ~115 Hz ticks
        t = i / 115.0
        frames = int(t * 90.0) + 1               # Visualizer frames requested so far (90 Hz)
        result, gate = tick(gate, t, 165.0, frames)
        requests += bool(result["request"])
    assert requests == 0
    # The Visualizer stops (pause, mode change): within the fill gap the transition resumes on
    # its own ticks and never stalls.
    stopped_at = t
    own = []
    for i in range(1, 40):
        now = stopped_at + i / 115.0
        result, gate = tick(gate, now, 165.0, frames)
        if result["request"]:
            own.append(now)
    assert own and own[0] - stopped_at <= 0.025 + 1 / 115.0
    assert len(own) >= 30


def test_transition_gate_without_a_visualizer_keeps_its_display_rate() -> None:
    _engine, tick = _qml_transition_gate()
    gate = {"nextDueS": 0.0, "lastVisualizerS": -1.0, "seenVisualizerFrames": 0}
    requests = 0
    for i in range(1000):                         # 1 kHz ticks for one second, 60 Hz display
        result, gate = tick(gate, i / 1000.0, 60.0, 0)
        requests += bool(result["request"])
    assert 59 <= requests <= 61


def test_scene_counts_visualizer_frames_into_the_gate_only_while_a_transition_runs() -> None:
    """Dormant cost is zero: Visualizer frames touch the QML gate only while this display's
    transition driver runs."""
    from PySide6.QtCore import QCoreApplication

    from rendering.quick.scene_controller import QuickSceneController

    QCoreApplication.instance() or QCoreApplication([])

    class _Item:
        updates = 0

        def update(self) -> None:
            _Item.updates += 1

    root = QObject()
    root.setProperty("transitionVisualizerFrames", 0.0)
    from types import SimpleNamespace

    scene = SimpleNamespace(_visualizer_item=_Item(), _scene_root=root,
                            _transition_frames_active=False, _transition_visualizer_frames=0)

    assert QuickSceneController.request_visualizer_present(scene)
    assert root.property("transitionVisualizerFrames") == 0.0
    scene._transition_frames_active = True
    for _ in range(3):
        assert QuickSceneController.request_visualizer_present(scene)
    assert root.property("transitionVisualizerFrames") == 3.0
    scene._transition_frames_active = False
    QuickSceneController.request_visualizer_present(scene)
    assert root.property("transitionVisualizerFrames") == 3.0
    assert _Item.updates == 5
