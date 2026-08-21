"""Phase C2 gates for Quick transition lifecycle and completion fencing."""

from __future__ import annotations

from pathlib import Path

import pytest

from rendering.quick.image_state import PresentationImage
from rendering.quick.transitions import (
    QuickTransitionController,
    TransitionOutcome,
    TransitionRequest,
)


ROOT = Path(__file__).resolve().parents[1]


class _Signal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback

    def emit(self) -> None:
        assert self.callback is not None
        self.callback()


class _Timer:
    def __init__(self) -> None:
        self.timeout = _Signal()
        self.single_shot = False
        self.timer_type = None
        self.started_delays: list[int] = []
        self.stop_count = 0

    def setSingleShot(self, value: bool) -> None:
        self.single_shot = bool(value)

    def setTimerType(self, timer_type) -> None:
        self.timer_type = timer_type

    def start(self, delay_ms: int) -> None:
        self.started_delays.append(int(delay_ms))

    def stop(self) -> None:
        self.stop_count += 1

    def fire(self) -> None:
        self.timeout.emit()


class _Pacer:
    def __init__(self) -> None:
        self.transition_demands: list[bool] = []

    def set_transition_active(self, active: bool) -> None:
        self.transition_demands.append(bool(active))


class _Clock:
    def __init__(self, now_ns: int = 1_000_000_000) -> None:
        self.now_ns = int(now_ns)

    def __call__(self) -> int:
        return self.now_ns


def _image(identity: str) -> PresentationImage:
    return PresentationImage(
        identity=identity,
        source_path="synthetic",
        logical_size=(1, 1),
        device_pixel_ratio=1,
        pixel_size=(1, 1),
        row_stride=4,
        rgba8=b"\x00\x00\x00\xff",
    )


def _request(*, generation: int = 7, duration_ms: int = 100) -> TransitionRequest:
    return TransitionRequest(
        runtime_generation=generation,
        transition_id="crossfade",
        requested_name="Crossfade",
        selected_from_random=False,
        duration_ms=duration_ms,
        direction=None,
        parameters={},
        source_image=_image("old"),
        destination_image=_image("new"),
    )


def _controller(qt_app):
    timer = _Timer()
    pacer = _Pacer()
    clock = _Clock()
    controller = QuickTransitionController(
        runtime_generation=7,
        frame_pacer=pacer,  # type: ignore[arg-type]
        clock_ns=clock,
        timer=timer,  # type: ignore[arg-type]
    )
    return controller, timer, pacer, clock


def test_deadline_completion_is_timer_owned_and_exactly_once(qt_app):
    controller, timer, pacer, clock = _controller(qt_app)
    completions = []
    run = controller.start(_request(), on_finalized=completions.append)

    assert controller.is_active is True
    assert pacer.transition_demands == [True]
    assert timer.single_shot is True
    assert timer.started_delays == [100]

    clock.now_ns += 40_000_000
    timer.fire()
    assert controller.is_active is True
    assert timer.started_delays[-1] == 60
    assert completions == []

    clock.now_ns = run.end_ns
    timer.fire()
    timer.fire()
    assert controller.is_active is False
    assert pacer.transition_demands == [True, False]
    assert len(completions) == 1
    assert completions[0].outcome is TransitionOutcome.COMPLETED
    assert completions[0].destination_image_identity == "new"
    assert controller.describe()["completion_count"] == 1


def test_cancel_snaps_destination_once_and_stale_completion_is_rejected(qt_app):
    controller, _timer, pacer, clock = _controller(qt_app)
    completions = []
    run = controller.start(_request(), on_finalized=completions.append)

    clock.now_ns += 25_000_000
    assert controller.cancel_current(reason="image-replaced") is True
    assert controller.cancel_current(reason="duplicate") is False
    assert controller.finish_if_current(
        run_id=run.run_id,
        runtime_generation=run.request.runtime_generation,
        now_ns=run.end_ns,
    ) is False

    assert len(completions) == 1
    assert completions[0].outcome is TransitionOutcome.CANCELLED_TO_DESTINATION
    assert completions[0].reason == "image-replaced"
    assert completions[0].destination_image_identity == "new"
    assert pacer.transition_demands == [True, False]


def test_runs_require_explicit_interruption_and_are_generation_fenced(qt_app):
    controller, _timer, _pacer, _clock = _controller(qt_app)
    first = controller.start(_request())

    with pytest.raises(RuntimeError, match="already active"):
        controller.start(_request())
    assert controller.finish_if_current(
        run_id=first.run_id,
        runtime_generation=99,
        now_ns=first.end_ns,
    ) is False

    assert controller.cancel_current(reason="explicit-replacement") is True
    second = controller.start(_request())
    assert second.run_id == first.run_id + 1
    assert controller.finish_if_current(
        run_id=first.run_id,
        runtime_generation=7,
        now_ns=first.end_ns,
    ) is False

    # The cancellation must execute and be asserted on its own so a premature
    # exception cannot let the generation-fence check falsely pass. Only the
    # generation-mismatched start is expected to raise.
    assert controller.cancel_current(reason="test-cleanup") is True
    assert controller.is_active is False
    with pytest.raises(ValueError, match="generation"):
        controller.start(_request(generation=8))
    assert controller.is_active is False


def test_close_finalizes_active_destination_and_closes_admission(qt_app):
    controller, _timer, pacer, _clock = _controller(qt_app)
    completions = []
    controller.start(_request(), on_finalized=completions.append)

    controller.close()
    controller.close()

    assert len(completions) == 1
    assert completions[0].outcome is TransitionOutcome.CANCELLED_TO_DESTINATION
    assert completions[0].reason == "runtime-retirement"
    assert pacer.transition_demands == [True, False]
    assert controller.describe()["closed"] is True
    with pytest.raises(RuntimeError, match="closed"):
        controller.start(_request())


def test_quick_transition_lifecycle_has_no_widget_compositor_or_paint_ack_dependency():
    paths = [
        ROOT / "rendering" / "quick" / "transitions" / "state.py",
        ROOT / "rendering" / "quick" / "transitions" / "controller.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    for forbidden in (
        "QWidget",
        "QPixmap",
        "DisplayWidget",
        "GLCompositorWidget",
        "_gl_compositor",
        "AnimationManager",
        "frameSwapped",
        "afterRendering",
        "afterFrameEnd",
    ):
        assert forbidden not in source
    assert "time.monotonic_ns" in source
    assert "QTimer" in source


def test_runtime_owns_transition_lifecycle_without_renderer_dispatch():
    runtime_source = (
        ROOT / "rendering" / "quick" / "runtime.py"
    ).read_text(encoding="utf-8")
    scene_source = (
        ROOT / "rendering" / "quick" / "scene_controller.py"
    ).read_text(encoding="utf-8")
    node_source = (
        ROOT / "rendering" / "quick" / "render" / "background_node.py"
    ).read_text(encoding="utf-8")

    assert "QuickTransitionController(" in runtime_source
    assert "run_changed.connect(self._scene.set_transition_run)" in runtime_source
    assert runtime_source.index("self.transition_controller.close()") < (
        runtime_source.index("self.frame_pacer.close()")
    )
    assert "scene.set_presentation_image(request.destination_image)" in runtime_source
    assert "run.sample(time.monotonic_ns())" in node_source
    assert "last_transition_run_id" in scene_source
    for source in (runtime_source, scene_source):
        assert "transition_id ==" not in source
        assert "transition_id in" not in source
