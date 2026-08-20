"""Generation-scoped Qt Quick runtime owner for one physical display."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QPoint, Signal
from PySide6.QtGui import QScreen

from .frame_pacer import QuickFramePacer
from .input_controller import QuickInputController
from .render import RenderNodeTelemetry
from .scene_controller import QuickSceneController, QuickSceneFactory
from .state import (
    QuickDisplayIdentity,
    QuickRuntimePhase,
    QuickSceneReadiness,
    QuickWindowPolicy,
)
from .window import QuickDisplayWindow


class QuickDisplayRuntime(QObject):
    """Own one window/scene/pacer generation with only explicit runtime APIs."""

    readiness_changed = Signal(object)
    display_identity_changed = Signal(object)
    visibility_changed = Signal(bool)
    retirement_completed = Signal(int)
    input_state_changed = Signal(object)
    exit_requested = Signal()
    previous_requested = Signal()
    next_requested = Signal()
    cycle_transition_requested = Signal()
    settings_requested = Signal()
    play_pause_requested = Signal()
    home_play_pause_requested = Signal()
    previous_track_requested = Signal()
    next_track_requested = Signal()
    slider_volume_up_requested = Signal()
    slider_volume_down_requested = Signal()
    global_volume_up_requested = Signal()
    global_volume_down_requested = Signal()
    global_mute_toggle_requested = Signal()
    context_menu_requested = Signal(QPoint)
    layout_slot_load_requested = Signal(str)
    layout_slot_save_requested = Signal(str)

    def __init__(
        self,
        *,
        screen_index: int,
        runtime_generation: int,
        screen: QScreen,
        scene_factory: QuickSceneFactory,
        window_policy: QuickWindowPolicy,
        telemetry: RenderNodeTelemetry | None = None,
        interaction_mode_provider: Callable[[], bool] | None = None,
        global_ctrl_held_provider: Callable[[], bool] | None = None,
        ctrl_state_publisher: Callable[[bool], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._screen_index = int(screen_index)
        self._runtime_generation = int(runtime_generation)
        self._phase = QuickRuntimePhase.CONSTRUCTED
        self._telemetry = telemetry or RenderNodeTelemetry()
        self._window: QuickDisplayWindow | None = QuickDisplayWindow(
            screen_index=self._screen_index,
            runtime_generation=self._runtime_generation,
            screen=screen,
            policy=window_policy,
        )
        self._display_identity = self._window.display_identity
        self._input: QuickInputController | None = QuickInputController(
            screen_index=self._screen_index,
            runtime_generation=self._runtime_generation,
            interaction_mode_provider=interaction_mode_provider,
            global_ctrl_held_provider=global_ctrl_held_provider,
            ctrl_state_publisher=ctrl_state_publisher,
            parent=self,
        )
        self._window.bind_input_controller(self._input)
        refresh_rate = float(self._display_identity.refresh_rate_hz)
        if refresh_rate <= 0.0:
            raise RuntimeError(
                f"screen {self._screen_index} has invalid refresh rate: {refresh_rate}"
            )
        self._scene: QuickSceneController | None = QuickSceneController(
            window=self._window,
            factory=scene_factory,
            telemetry=self._telemetry,
        )
        self._scene_readiness = self._scene.readiness
        self._pacer: QuickFramePacer | None = QuickFramePacer(
            self._window,
            refresh_rate,
        )
        self._close_meta_calls_queued = False
        self._window_delete_queued = False
        self._retirement_emitted = False
        self._retired_window_state: dict[str, Any] | None = None
        self._retired_scene_state: dict[str, Any] | None = None
        self._retired_pacer_state: dict[str, Any] | None = None
        self._retired_input_state: dict[str, Any] | None = None

        self._window.display_identity_changed.connect(
            self._on_display_identity_changed
        )
        self._window.visibleChanged.connect(self._on_visibility_changed)
        self._window.destroyed.connect(self._on_window_destroyed)
        self._scene.readiness_changed.connect(self._on_scene_readiness_changed)
        self._input.input_state_changed.connect(self.input_state_changed.emit)
        self._input.exit_requested.connect(self.exit_requested.emit)
        self._input.previous_image_requested.connect(self.previous_requested.emit)
        self._input.next_image_requested.connect(self.next_requested.emit)
        self._input.cycle_transition_requested.connect(
            self.cycle_transition_requested.emit
        )
        self._input.settings_requested.connect(self.settings_requested.emit)
        self._input.play_pause_requested.connect(self.play_pause_requested.emit)
        self._input.home_play_pause_requested.connect(
            self.home_play_pause_requested.emit
        )
        self._input.previous_track_requested.connect(
            self.previous_track_requested.emit
        )
        self._input.next_track_requested.connect(self.next_track_requested.emit)
        self._input.slider_volume_up_requested.connect(
            self.slider_volume_up_requested.emit
        )
        self._input.slider_volume_down_requested.connect(
            self.slider_volume_down_requested.emit
        )
        self._input.global_volume_up_requested.connect(
            self.global_volume_up_requested.emit
        )
        self._input.global_volume_down_requested.connect(
            self.global_volume_down_requested.emit
        )
        self._input.global_mute_toggle_requested.connect(
            self.global_mute_toggle_requested.emit
        )
        self._input.context_menu_requested.connect(self.context_menu_requested.emit)
        self._input.layout_slot_load_requested.connect(
            self.layout_slot_load_requested.emit
        )
        self._input.layout_slot_save_requested.connect(
            self.layout_slot_save_requested.emit
        )

    @property
    def screen_index(self) -> int:
        return self._screen_index

    @property
    def runtime_generation(self) -> int:
        return self._runtime_generation

    @property
    def phase(self) -> QuickRuntimePhase:
        return self._phase

    @property
    def display_identity(self) -> QuickDisplayIdentity:
        return self._display_identity

    @property
    def scene_readiness(self) -> QuickSceneReadiness:
        return self._scene_readiness

    @property
    def telemetry(self) -> RenderNodeTelemetry:
        return self._telemetry

    @property
    def window(self) -> QuickDisplayWindow:
        window = self._window
        if window is None:
            raise RuntimeError("Quick display window has retired")
        return window

    @property
    def scene_controller(self) -> QuickSceneController:
        scene = self._scene
        if scene is None:
            raise RuntimeError("Quick scene controller has retired")
        return scene

    @property
    def frame_pacer(self) -> QuickFramePacer:
        pacer = self._pacer
        if pacer is None:
            raise RuntimeError("Quick frame pacer has retired")
        return pacer

    @property
    def input_controller(self) -> QuickInputController:
        controller = self._input
        if controller is None:
            raise RuntimeError("Quick input controller has retired")
        return controller

    def show_on_screen(self) -> None:
        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            raise RuntimeError("cannot show a retiring Quick display runtime")
        self.input_controller.reset_initial_position()
        self.window.show_on_screen()

    def hide(self) -> None:
        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            return
        was_visible = self.window.isVisible()
        self.frame_pacer.pause()
        self.input_controller.reset_initial_position()
        self.window.queue_hide()
        if not was_visible:
            self._set_phase(QuickRuntimePhase.PAUSED)

    def quiesce_for_runtime_pause(self) -> None:
        self.hide()

    def close_runtime(self) -> bool:
        """Begin exact retirement without blocking Python on the render thread."""

        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            return False

        self._set_phase(QuickRuntimePhase.RETIRING)
        self.input_controller.close_input()
        self.frame_pacer.close()
        self.scene_controller.quiesce_for_retirement()
        # This is the only legal window retirement entry: QuickDisplayWindow
        # queues C++ meta-calls so Python does not hold the GIL while Qt waits
        # for the threaded scene graph.
        self.window.queue_close()
        self._close_meta_calls_queued = True
        self._maybe_queue_window_deletion()
        return True

    def describe_runtime_state(self) -> dict[str, Any]:
        window_state = self._retired_window_state
        if window_state is None and self._window is not None:
            window_state = self._window.describe_window_state()
        scene_state = self._retired_scene_state
        if scene_state is None and self._scene is not None:
            scene_state = self._scene.describe_scene_state()
        pacer_state = self._retired_pacer_state
        if pacer_state is None and self._pacer is not None:
            pacer_state = self._pacer.describe()
        input_state = self._retired_input_state
        if input_state is None and self._input is not None:
            input_state = self._input.describe_input_state()
        return {
            "screen_index": self._screen_index,
            "runtime_generation": self._runtime_generation,
            "phase": self._phase.value,
            "display_identity": self._display_identity.as_dict(),
            "scene_readiness": self._scene_readiness.as_dict(),
            "window": window_state,
            "scene": scene_state,
            "frame_pacer": pacer_state,
            "input": input_state,
            "close_meta_calls_queued": self._close_meta_calls_queued,
            "window_delete_queued": self._window_delete_queued,
            "retirement_completed": self._retirement_emitted,
        }

    def _on_display_identity_changed(self, identity: QuickDisplayIdentity) -> None:
        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            return
        self._display_identity = identity
        if self._pacer is not None:
            self._pacer.set_target_hz(identity.refresh_rate_hz)
        self.display_identity_changed.emit(identity)

    def _on_visibility_changed(self, visible: bool) -> None:
        if self._phase not in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            if visible:
                self.frame_pacer.resume()
            else:
                self.frame_pacer.pause()
                self.input_controller.reset_initial_position()
            self._set_phase(
                QuickRuntimePhase.VISIBLE if visible else QuickRuntimePhase.PAUSED
            )
        self.visibility_changed.emit(bool(visible))

    def _on_scene_readiness_changed(self, readiness: QuickSceneReadiness) -> None:
        self._scene_readiness = readiness
        self.readiness_changed.emit(readiness)
        self._maybe_queue_window_deletion()

    def _maybe_queue_window_deletion(self) -> None:
        if (
            self._phase is not QuickRuntimePhase.RETIRING
            or not self._close_meta_calls_queued
            or self._window_delete_queued
            or not self._scene_readiness.qml_objects_retired
        ):
            return
        window = self._window
        scene = self._scene
        if window is None or scene is None:
            return
        if window.isSceneGraphInitialized():
            return
        scene.finalize_retirement()
        self._retired_scene_state = scene.describe_scene_state()
        self._retired_window_state = window.describe_window_state()
        if self._pacer is not None:
            self._retired_pacer_state = self._pacer.describe()
        if self._input is not None:
            self._retired_input_state = self._input.describe_input_state()
        self._window_delete_queued = True
        window.deleteLater()

    def _on_window_destroyed(self, *_args: object) -> None:
        if self._phase is not QuickRuntimePhase.RETIRING:
            return
        self._window = None
        self._scene = None
        self._pacer = None
        if self._input is not None:
            self._retired_input_state = self._input.describe_input_state()
            self._input.deleteLater()
            self._input = None
        self._set_phase(QuickRuntimePhase.RETIRED)
        if not self._retirement_emitted:
            self._retirement_emitted = True
            self.retirement_completed.emit(self._runtime_generation)

    def _set_phase(self, phase: QuickRuntimePhase) -> None:
        self._phase = phase
