from __future__ import annotations

import ast
import inspect
import threading

import pytest

from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    VisualizerClipPolicy,
    VisualizerShellPolicy,
    get_visualizer_mode_descriptor,
)
from widgets.spotify_visualizer.logical_runtime import LatestStateMailbox
from widgets.spotify_visualizer.runtime_adapter import (
    LegacyVisualizerRuntimeAdapterMixin,
)
from widgets.spotify_visualizer.runtime_controller import (
    VisualizerRuntimeController,
)


class _LegacyAdapterProbe(LegacyVisualizerRuntimeAdapterMixin):
    def __init__(self, controller: VisualizerRuntimeController) -> None:
        self._runtime_controller = controller
        self._bars_timer = None
        self._base_max_fps = 90.0
        self._target_timer_interval_ms = 0
        self._current_timer_interval_ms = 0


def _controller(*, generation: int = 0) -> VisualizerRuntimeController:
    return VisualizerRuntimeController(
        runtime_generation=generation,
        initial_mode="spectrum",
        engine_factory=lambda _bar_count: object(),
    )


def test_current_modes_resolve_their_proven_carded_presentation_policy() -> None:
    for mode_id in VISUALIZER_MODE_IDS:
        policy = get_visualizer_mode_descriptor(mode_id).presentation_policy
        assert policy.shell_policy is VisualizerShellPolicy.CARD
        assert policy.clip_policy is VisualizerClipPolicy.CARD_INTERIOR
        # All five modes (Bubble included after its logical reflow) are
        # viewport-resize-capable.
        assert policy.viewport_resize_capable is True


def test_controller_is_presentation_neutral_and_source_resolution_is_lazy() -> None:
    factory_calls: list[int] = []
    controller = VisualizerRuntimeController(
        runtime_generation=0,
        bar_count=24,
        initial_mode="bubble",
        engine_factory=lambda count: factory_calls.append(count) or object(),
    )

    assert controller.runtime_generation == 0
    assert controller.engine is None
    assert factory_calls == []
    assert controller.ensure_engine() is controller.engine
    assert factory_calls == [24]

    module = __import__(
        "widgets.spotify_visualizer.runtime_controller",
        fromlist=["VisualizerRuntimeController"],
    )
    tree = ast.parse(inspect.getsource(module))
    imports = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert not any(
        name.startswith(("PySide6.QtWidgets", "PySide6.QtQuick", "OpenGL"))
        for name in imports
    )
    assert not any(
        name.endswith(("spotify_bars_gl_overlay", "gl_compositor"))
        for name in imports
    )


def test_controller_owns_mode_settings_playback_and_activation_state() -> None:
    controller = _controller()
    settings = {"mode": "spectrum", "nested": {"value": 1}}
    activation = {"preset": 2, "resolved": {"gain": 0.75}}

    controller.settings_model = settings
    controller.record_resolved_activation(activation)
    controller.playing = True
    controller.enabled = True
    controller.set_mode("devcurve")

    settings["nested"]["value"] = 9
    activation["resolved"]["gain"] = 0.1
    assert controller.settings_model["nested"]["value"] == 1
    assert controller.resolved_activation["resolved"]["gain"] == 0.75
    assert controller.mode_id == "devcurve"
    assert controller.playing is True
    assert controller.enabled is True


def test_legacy_adapter_has_explicit_access_to_the_single_controller_state() -> None:
    controller = _controller()
    adapter = _LegacyAdapterProbe(controller)

    adapter._enabled = True
    adapter._spotify_playing = True
    adapter._vis_mode = "sine_wave"
    adapter._pending_engine_generation = 0
    adapter._pending_engine_activation_id = 0

    assert adapter.runtime_controller is controller
    assert controller.enabled is True
    assert controller.playing is True
    assert controller.mode_id == "sine_wave"
    assert adapter._pending_engine_generation == 0
    assert adapter._pending_engine_activation_id == 0


def test_tick_source_uses_controller_as_the_sole_logical_runtime_owner(
    monkeypatch,
) -> None:
    from widgets.spotify_visualizer import tick_helpers, tick_pipeline

    stepped = threading.Event()
    controller = _controller()
    controller.enabled = True
    controller.thread_manager = object()
    adapter = _LegacyAdapterProbe(controller)
    monkeypatch.setattr(
        tick_pipeline,
        "logical_tick",
        lambda _owner: stepped.set(),
    )

    tick_helpers.ensure_tick_source(adapter)
    runtime = controller.logical_runtime
    assert runtime is not None
    assert adapter._logical_runtime is runtime
    assert stepped.wait(0.5)

    # Pause/Play changes state, not authored-clock identity.
    adapter._spotify_playing = False
    tick_helpers.ensure_tick_source(adapter)
    assert controller.logical_runtime is runtime
    adapter._spotify_playing = True
    assert controller.logical_runtime is runtime

    tick_helpers.stop_tick_source(adapter)
    assert controller.logical_runtime is None


def test_failed_logical_join_retains_runtime_ownership_and_clears_admission() -> None:
    class _UnjoinedRuntime:
        def is_running(self) -> bool:
            return True

        def stop(self) -> bool:
            return False

    controller = _controller()
    runtime = _UnjoinedRuntime()
    controller.adopt_logical_runtime(runtime)  # type: ignore[arg-type]
    controller.logical_mailbox.publish("stale", generation=0)
    controller.logical_present_pending = True

    assert controller.stop_logical_runtime() is False
    assert controller.logical_runtime is runtime
    assert controller.logical_mailbox.take() is None
    assert controller.logical_present_pending is False


def test_exception_during_logical_stop_closes_admission_and_retains_owner() -> None:
    class _ExplodingRuntime:
        def is_running(self) -> bool:
            return True

        def stop(self) -> bool:
            raise OSError("join failed")

    controller = _controller()
    runtime = _ExplodingRuntime()
    controller.adopt_logical_runtime(runtime)  # type: ignore[arg-type]
    controller.logical_mailbox.publish("stale", generation=0)
    controller.logical_present_pending = True

    with pytest.raises(OSError, match="join failed"):
        controller.stop_logical_runtime()

    assert controller.logical_runtime is runtime
    assert controller.logical_mailbox.take() is None
    assert controller.logical_present_pending is False


def test_production_stop_helper_propagates_an_unresolved_stop_exception() -> None:
    from widgets.spotify_visualizer import tick_helpers

    class _ExplodingRuntime:
        def is_running(self) -> bool:
            return True

        def stop(self) -> bool:
            raise OSError("join failed")

    controller = _controller()
    runtime = _ExplodingRuntime()
    controller.adopt_logical_runtime(runtime)  # type: ignore[arg-type]
    adapter = _LegacyAdapterProbe(controller)

    with pytest.raises(OSError, match="join failed"):
        tick_helpers.stop_tick_source(adapter)

    assert controller.logical_runtime is runtime
    assert controller.logical_present_pending is False


def test_production_stop_helper_blocks_teardown_after_join_timeout() -> None:
    from widgets.spotify_visualizer import tick_helpers

    class _UnjoinedRuntime:
        def is_running(self) -> bool:
            return True

        def stop(self) -> bool:
            return False

    controller = _controller()
    runtime = _UnjoinedRuntime()
    controller.adopt_logical_runtime(runtime)  # type: ignore[arg-type]
    adapter = _LegacyAdapterProbe(controller)

    with pytest.raises(RuntimeError, match="join barrier"):
        tick_helpers.stop_tick_source(adapter)

    assert controller.logical_runtime is runtime
    assert controller.logical_present_pending is False


def test_running_generation_scoped_runtime_cannot_be_retargeted() -> None:
    class _LiveRuntime:
        def is_running(self) -> bool:
            return True

    controller = _controller(generation=0)
    runtime = _LiveRuntime()
    controller.adopt_logical_runtime(runtime)  # type: ignore[arg-type]

    controller.runtime_generation = 0
    with pytest.raises(RuntimeError, match="generation-scoped"):
        controller.runtime_generation = 1

    assert controller.runtime_generation == 0
    assert controller.logical_runtime is runtime


def test_controller_mailbox_remains_single_slot_and_generation_fenced() -> None:
    controller = _controller(generation=0)
    mailbox = controller.logical_mailbox
    assert isinstance(mailbox, LatestStateMailbox)

    mailbox.publish("old", generation=0, activation_id=0)
    mailbox.publish("latest", generation=0, activation_id=1)
    publication = mailbox.take_for_generation(0)

    assert publication is not None
    assert publication.state == "latest"
    assert publication.activation_id == 1
    assert mailbox.take() is None
