"""Studios under ``--frame-trace`` (the operator's diagnostic runs).

7 Nov: with ``--frame-trace`` admitted, every engine-answer Studio (Spectrum, Oscilloscope, DevCurve, Neon Lake, Sphere,
Extruded Spectrum) failed to render: "Step state holds an uncopyable WindowsPath", then, once paths were shared,
"... uncopyable bytearray (in VisualizerRuntimeController._logical_mailbox)". The production mailbox caches the
process-wide trace sink and the preview's step-state snapshot tried to deep-copy it. A failed capture also left the
evaluator half-started ("'NoneType' object has no attribute 'restore'" on every later frame). Default-profile tests
never admit a trace, so none of this was caught.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from tests.test_studio_exit_every_mode import (  # noqa: F401  (fixtures)
    MODES, _no_open_studio, _open, mode_dialog, no_gl_checks, settings_manager)

def _engine_answer_modes() -> list:
    """Every registered Studio whose preview replays through the engine-answer evaluator (the step-state path)."""
    from ui.studio.engine_answers import EngineAnswerEvaluator
    from ui.studio.registry import create_adapter
    modes = []
    for mode in MODES:
        probe = create_adapter(mode).create_evaluator()
        if isinstance(probe, EngineAnswerEvaluator):
            modes.append(mode)
        probe.release()
    return modes


ENGINE_ANSWER_MODES = _engine_answer_modes()


@pytest.fixture
def admitted_frame_trace(tmp_path, monkeypatch):
    """A real sink installed exactly where ``--frame-trace`` admission puts it."""
    from core.performance import frame_trace
    from core.performance.gui_stall_sampler import GuiStallSampler
    sink = frame_trace.FrameTraceSink(Path(tmp_path) / "screensaver_frame_trace.bin")
    sampler = GuiStallSampler(Path(tmp_path) / "gui_stall_stacks.log")     # --gui-stall-stacks, also cached by objects
    monkeypatch.setattr(frame_trace, "_active_sink", sink)
    monkeypatch.setattr(frame_trace, "_active_stall_sampler", sampler)
    yield sink
    monkeypatch.setattr(frame_trace, "_active_sink", None)
    monkeypatch.setattr(frame_trace, "_active_stall_sampler", None)
    sampler.close()
    sink.close()


def _frames(controller, surface, count=12):
    for _ in range(count):
        surface.pump()
    return controller.bridge.viewportStatus, controller.bridge.viewportError


@pytest.mark.parametrize("mode", ENGINE_ANSWER_MODES)
def test_an_engine_answer_studio_renders_under_frame_trace_and_writes_nothing_to_it(
        qt_app, mode_dialog, no_gl_checks, admitted_frame_trace, caplog, mode):
    _dialog, tab = mode_dialog(mode)
    with caplog.at_level(logging.ERROR):
        controller, surface = _open(tab, mode)
        status, error = _frames(controller, surface)
        evaluator = controller.evaluator
        snapshot_ran = getattr(evaluator, "_pristine", None) is not None
    failures = [r.getMessage() for r in caplog.records if "Preview evaluation failed" in r.getMessage()]
    assert not failures and status not in ("failed", "error"), (mode, status, error, failures)
    assert snapshot_ran, f"{mode}: the preview never took its step-state snapshot (the test would prove nothing)"
    # The offline replay is not a presentation: nothing of it reaches the live trace.
    assert evaluator._controller.logical_mailbox._frame_trace is None
    assert admitted_frame_trace._written == 0 and admitted_frame_trace._count == 0


def test_a_failed_start_leaves_nothing_half_started_and_retries(qt_app, mode_dialog, no_gl_checks, monkeypatch):
    """A capture that raises leaves no controller behind, so the next frame starts again (and reports the real error)
    instead of calling ``restore`` on a missing snapshot."""
    import ui.studio.replay_engine as replay_engine
    _dialog, tab = mode_dialog("spectrum")
    controller, _surface = _open(tab, "spectrum")
    evaluator = controller.evaluator
    calls = []

    def failing(self, *args, **kwargs):
        calls.append(1)
        raise TypeError("Step state holds an uncopyable Probe")
    monkeypatch.setattr(replay_engine.StepState, "__init__", failing)
    evaluator._controller = None                                       # force a fresh start
    with pytest.raises(TypeError, match="uncopyable Probe"):
        evaluator.evaluate(0.5, controller.evaluation_values())
    assert evaluator._controller is None, "a failed capture must not leave a half-started controller"
    with pytest.raises(TypeError, match="uncopyable Probe"):                  # retried: the same real error, not
        evaluator.evaluate(0.5, controller.evaluation_values())               # "'NoneType' ... 'restore'"
    assert len(calls) == 2
