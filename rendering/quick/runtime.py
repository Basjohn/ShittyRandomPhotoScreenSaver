"""Generation-scoped Qt Quick runtime owner for one physical display."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QPoint, QSize, Signal
from PySide6.QtGui import QScreen

from rendering.widget_runtime_manager import WidgetRuntimeManager

from .auxiliary import QuickAuxiliaryController
from .context_menu import QuickContextMenuModel
from .cursor_controller import QuickCursorController
from .frame_pacer import QuickFramePacer
from .image_state import PresentationImage
from .input_controller import QuickInputController
from .render import RenderNodeTelemetry
from .scene_controller import QuickSceneController, QuickSceneFactory
from .state import (
    QuickDisplayBindingLoss,
    QuickDisplayIdentity,
    QuickRuntimePhase,
    QuickSceneReadiness,
    QuickWindowPolicy,
)
from .transitions import (
    QuickTransitionController,
    TransitionCompletion,
    TransitionRequest,
    TransitionRun,
)
from .window import QuickDisplayWindow


class QuickDisplayRuntime(QObject):
    """Own one window/scene/pacer generation with only explicit runtime APIs."""

    readiness_changed = Signal(object)
    display_identity_changed = Signal(object)
    topology_loss_detected = Signal(object)
    transition_started = Signal(object)
    transition_finalized = Signal(object)
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
    custom_layout_save_requested = Signal()
    custom_layout_cancel_requested = Signal()

    def __init__(
        self,
        *,
        screen_index: int,
        runtime_generation: int,
        screen: QScreen,
        scene_factory: QuickSceneFactory,
        window_policy: QuickWindowPolicy,
        telemetry: RenderNodeTelemetry | None = None,
        interaction_mode_enabled: bool = False,
        ctrl_state_publisher: Callable[[bool], None] | None = None,
        custom_layout_active_provider: Callable[[], bool] | None = None,
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
        self._binding_loss: QuickDisplayBindingLoss | None = None
        self._input: QuickInputController | None = QuickInputController(
            screen_index=self._screen_index,
            runtime_generation=self._runtime_generation,
            interaction_mode_enabled=interaction_mode_enabled,
            ctrl_state_publisher=ctrl_state_publisher,
            custom_layout_active_provider=custom_layout_active_provider,
            parent=self,
        )
        self._window.bind_input_controller(self._input)
        self._cursor: QuickCursorController | None = QuickCursorController(
            window=self._window,
            screen_index=self._screen_index,
            runtime_generation=self._runtime_generation,
            parent=self,
        )
        self._window.bind_cursor_controller(self._cursor)
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
        self._auxiliary: QuickAuxiliaryController | None = QuickAuxiliaryController(
            screen_index=self._screen_index,
            runtime_generation=self._runtime_generation,
            parent=self,
        )
        self._context_menu: QuickContextMenuModel | None = QuickContextMenuModel(
            screen_index=self._screen_index,
            runtime_generation=self._runtime_generation,
            parent=self,
        )
        self._scene.bind_context_menu_model(self._context_menu)
        self._pacer: QuickFramePacer | None = QuickFramePacer(
            self._window,
            refresh_rate,
        )
        self._transition: QuickTransitionController | None = (
            QuickTransitionController(
                runtime_generation=self._runtime_generation,
                frame_pacer=self._pacer,
                parent=self,
            )
        )
        self._scene.bind_perf_pacer_state_provider(self._pacer.describe)
        # Event-driven continuous-frame demand for running widget QML animations
        # (Media artwork/metadata, Steam content rotations, lifecycle fades). Set
        # before any family widget QML is instantiated so its animations can raise
        # the demand from onRunningChanged and fade smoothly instead of flashing.
        from rendering.quick.widget_frame_demand import QuickWidgetFrameDemand

        self._widget_frame_demand: QuickWidgetFrameDemand | None = (
            QuickWidgetFrameDemand(self._pacer, parent=self)
        )
        self._scene.bind_widget_frame_demand(self._widget_frame_demand)
        self._auxiliary.set_pixel_shift_defer_check(
            lambda: self._transition is not None and self._transition.is_active
        )
        # Exactly one presentation-neutral runtime capability/lifecycle/service
        # owner per display generation (H §7 cardinality). It is constructed
        # hostless; the per-display family presentation binder binds a registry
        # host and drives admission/service lifetimes through it. Never run a
        # second neutral manager in parallel for this display.
        self._widget_runtime_manager: WidgetRuntimeManager | None = (
            WidgetRuntimeManager()
        )
        self._close_meta_calls_queued = False
        self._window_delete_queued = False
        self._retirement_emitted = False
        self._retired_window_state: dict[str, Any] | None = None
        self._retired_scene_state: dict[str, Any] | None = None
        self._retired_pacer_state: dict[str, Any] | None = None
        self._retired_input_state: dict[str, Any] | None = None
        self._retired_auxiliary_state: dict[str, Any] | None = None
        self._retired_cursor_state: dict[str, Any] | None = None
        self._retired_context_menu_state: dict[str, Any] | None = None
        self._retired_transition_state: dict[str, Any] | None = None

        self._window.display_identity_changed.connect(
            self._on_display_identity_changed
        )
        self._window.binding_lost.connect(self._on_window_binding_lost)
        self._window.visibleChanged.connect(self._on_visibility_changed)
        self._window.destroyed.connect(self._on_window_destroyed)
        self._scene.readiness_changed.connect(self._on_scene_readiness_changed)
        self._auxiliary.state_changed.connect(self._scene.apply_auxiliary_state)
        self._scene.apply_auxiliary_state(self._auxiliary.state)
        self._auxiliary.state_changed.connect(self._cursor.apply_auxiliary_state)
        self._cursor.apply_auxiliary_state(self._auxiliary.state)
        self._input.input_state_changed.connect(self._auxiliary.apply_input_state)
        self._auxiliary.apply_input_state(self._input.input_state)
        self._context_menu.visibilityChanged.connect(
            self._input.set_context_menu_active
        )
        self._input.input_state_changed.connect(self._scene.apply_input_state)
        self._input.widget_glow_pressed.connect(self._scene.apply_widget_glow_press)
        self._scene.apply_input_state(self._input.input_state)
        self._transition.run_changed.connect(self._scene.set_transition_run)
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
        self._input.context_menu_requested.connect(
            self._on_context_menu_requested
        )
        self._input.context_menu_requested.connect(self.context_menu_requested.emit)
        self._input.layout_slot_load_requested.connect(
            self.layout_slot_load_requested.emit
        )
        self._input.layout_slot_save_requested.connect(
            self.layout_slot_save_requested.emit
        )
        self._input.custom_layout_save_requested.connect(
            self.custom_layout_save_requested.emit
        )
        self._input.custom_layout_cancel_requested.connect(
            self.custom_layout_cancel_requested.emit
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
    def binding_loss(self) -> QuickDisplayBindingLoss | None:
        return self._binding_loss

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

    @property
    def auxiliary_controller(self) -> QuickAuxiliaryController:
        controller = self._auxiliary
        if controller is None:
            raise RuntimeError("Quick auxiliary controller has retired")
        return controller

    @property
    def context_menu_model(self) -> QuickContextMenuModel:
        model = self._context_menu
        if model is None:
            raise RuntimeError("Quick context menu model has retired")
        return model

    @property
    def transition_controller(self) -> QuickTransitionController:
        controller = self._transition
        if controller is None:
            raise RuntimeError("Quick transition controller has retired")
        return controller

    @property
    def cursor_controller(self) -> QuickCursorController:
        controller = self._cursor
        if controller is None:
            raise RuntimeError("Quick cursor controller has retired")
        return controller

    @property
    def widget_runtime_manager(self) -> WidgetRuntimeManager:
        manager = self._widget_runtime_manager
        if manager is None:
            raise RuntimeError("Quick widget runtime manager has retired")
        return manager

    def show_on_screen(self) -> None:
        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            raise RuntimeError("cannot show a retiring Quick display runtime")
        if self._binding_loss is not None:
            raise RuntimeError("cannot show a topology-displaced Quick display runtime")
        self.auxiliary_controller.resume()
        self.input_controller.reset_initial_position()
        self.window.show_on_screen()

    def hide(self) -> None:
        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            return
        was_visible = self.window.isVisible()
        self.context_menu_model.dismiss()
        self.frame_pacer.pause()
        self.auxiliary_controller.pause()
        self.input_controller.reset_initial_position()
        self.window.queue_hide()
        if not was_visible:
            self._set_phase(QuickRuntimePhase.PAUSED)

    def quiesce_for_runtime_pause(self) -> None:
        self.hide()

    def bind_visualizer_render_source(
        self,
        controller: Any,
        *,
        engine_generation: int,
        activation_id: int,
    ) -> Any:
        """Bind one exact visualizer activation's render bridge into this scene.

        The display owner opens render admission on the presentation-neutral
        runtime controller and hands its latest-state snapshot bridge to the
        retained scene item for the current runtime generation. Logical ownership
        stays with the controller; only the bounded immutable bridge crosses into
        render. Returns the exact ``VisualizerRenderIdentity`` for caller proof.
        """

        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            raise RuntimeError("cannot bind a visualizer source on a retiring runtime")
        identity = controller.begin_render_activation(
            engine_generation=int(engine_generation),
            activation_id=int(activation_id),
        )
        self.scene_controller.set_visualizer_render_source(
            controller.render_bridge,
            identity,
        )
        return identity

    def bind_visualizer_viewport_config(
        self,
        override_sink: Callable[[tuple[float, float] | None], None],
    ) -> None:
        """Bind the corrected-G4 visualizer viewport-config ownership once.

        The display owner wires the retained CUSTOM viewport-config sink to the
        visualizer runtime controller's ``set_custom_viewport_override`` so a live
        edge drag drives only the temporary working override, while the ordinary
        committed extent stays the controller's own commit path. Retiring the
        override (CUSTOM inactive) falls back to the committed extent - never a
        manufactured canonical. Only plain typed floats cross this seam; no
        QQuickItem/QScreen/render-thread object enters Bubble logical state, and
        no second config map/queue/timer/clock is introduced.
        """

        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            raise RuntimeError("cannot bind viewport config on a retiring runtime")
        if not callable(override_sink):
            raise TypeError("visualizer viewport override sink must be callable")
        self.scene_controller.set_visualizer_viewport_config_sink(override_sink)

    def get_target_size(self) -> QSize:
        """Return this display's target image pixel size (logical size x DPR).

        This is the physical pixel extent the image pipeline should process to for
        this display, derived from the bound display identity - no legacy widget
        or compositor surface is consulted.
        """

        _x, _y, width, height = self._display_identity.geometry
        dpr = float(self._display_identity.device_pixel_ratio)
        if dpr <= 0.0:
            dpr = 1.0
        return QSize(
            max(1, int(round(float(width) * dpr))),
            max(1, int(round(float(height) * dpr))),
        )

    def set_presentation_image(self, image: PresentationImage | None) -> None:
        """Publish immutable base-image state into this display generation."""

        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            raise RuntimeError("cannot update a retiring Quick display runtime")
        if self.transition_controller.is_active:
            raise RuntimeError("cannot replace the base image during a transition run")
        self.scene_controller.set_presentation_image(image)

    def clear(self) -> None:
        """Clear the base image while keeping the window/scene generation live.

        A running transition is cancelled first so the cleared state is coherent.
        A retiring/retired generation ignores the request.
        """

        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            return
        if self.transition_controller.is_active:
            self.transition_controller.cancel_current(reason="clear")
        self.scene_controller.set_presentation_image(None)

    def start_transition(
        self,
        request: TransitionRequest,
        *,
        on_finalized: Callable[[TransitionCompletion], None] | None = None,
    ) -> TransitionRun:
        """Start one presentation-neutral run against the current base image."""

        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            raise RuntimeError("cannot transition a retiring Quick display runtime")
        if self._binding_loss is not None:
            raise RuntimeError("cannot transition a topology-displaced Quick runtime")
        current = self.scene_controller.presentation_image
        if current != request.source_image:
            raise ValueError("transition source does not match the current base image")

        def _finalize_destination(completion: TransitionCompletion) -> None:
            try:
                scene = self._scene
                if scene is not None and scene.readiness.admission_open:
                    scene.set_presentation_image(request.destination_image)
            finally:
                self.transition_finalized.emit(completion)
                if on_finalized is not None:
                    on_finalized(completion)

        run = self.transition_controller.start(
            request,
            on_finalized=_finalize_destination,
        )
        self.transition_started.emit(run)
        return run

    def cancel_transition(self, *, reason: str) -> bool:
        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            return False
        return self.transition_controller.cancel_current(reason=reason)

    def close_runtime(self) -> bool:
        """Begin exact retirement without blocking Python on the render thread."""

        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            return False

        self._set_phase(QuickRuntimePhase.RETIRING)
        self.input_controller.close_input()
        self.context_menu_model.close()
        self.auxiliary_controller.close()
        self.cursor_controller.close()
        self.transition_controller.close()
        # Retire the neutral capability/service owner's generation-owned provider
        # and model lifetimes exactly once before scene/render teardown, so no
        # generation-owned runtime service outlives its display generation.
        if self._widget_runtime_manager is not None:
            self._widget_runtime_manager.cleanup()
        if self._widget_frame_demand is not None:
            self._widget_frame_demand.clear()
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
        transition_state = self._retired_transition_state
        if transition_state is None and self._transition is not None:
            transition_state = self._transition.describe()
        auxiliary_state = self._retired_auxiliary_state
        if auxiliary_state is None and self._auxiliary is not None:
            auxiliary_state = self._auxiliary.describe()
        cursor_state = self._retired_cursor_state
        if cursor_state is None and self._cursor is not None:
            cursor_state = self._cursor.describe()
        context_menu_state = self._retired_context_menu_state
        if context_menu_state is None and self._context_menu is not None:
            context_menu_state = self._context_menu.describe()
        return {
            "screen_index": self._screen_index,
            "runtime_generation": self._runtime_generation,
            "phase": self._phase.value,
            "display_identity": self._display_identity.as_dict(),
            "binding_loss": (
                None if self._binding_loss is None else self._binding_loss.as_dict()
            ),
            "scene_readiness": self._scene_readiness.as_dict(),
            "window": window_state,
            "scene": scene_state,
            "frame_pacer": pacer_state,
            "input": input_state,
            "auxiliary": auxiliary_state,
            "cursor": cursor_state,
            "context_menu": context_menu_state,
            "transition": transition_state,
            "close_meta_calls_queued": self._close_meta_calls_queued,
            "window_delete_queued": self._window_delete_queued,
            "retirement_completed": self._retirement_emitted,
            "widget_runtime_manager": {
                "present": self._widget_runtime_manager is not None,
                "retired": (
                    self._widget_runtime_manager is None
                    or self._widget_runtime_manager.is_retired
                ),
                "has_bound_host": (
                    self._widget_runtime_manager is not None
                    and self._widget_runtime_manager.has_bound_host
                ),
            },
        }

    def _on_display_identity_changed(self, identity: QuickDisplayIdentity) -> None:
        if (
            self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED)
            or self._binding_loss is not None
        ):
            return
        self._display_identity = identity
        if self._pacer is not None:
            self._pacer.set_target_hz(identity.refresh_rate_hz)
        if self._cursor is not None:
            self._cursor.refresh_display_metrics()
        self.display_identity_changed.emit(identity)

    def _on_window_binding_lost(self, loss: QuickDisplayBindingLoss) -> None:
        if (
            self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED)
            or self._binding_loss is not None
        ):
            return
        if (
            loss.screen_index != self._screen_index
            or loss.runtime_generation != self._runtime_generation
            or loss.expected_screen_key != self._display_identity.screen_key
        ):
            raise RuntimeError("Quick display binding-loss identity mismatch")

        self._binding_loss = loss
        self.transition_controller.cancel_current(reason="topology-loss")
        self.frame_pacer.pause()
        self.context_menu_model.close()
        self.auxiliary_controller.close()
        self.cursor_controller.close()
        self.input_controller.close_input()
        self._set_phase(QuickRuntimePhase.PAUSED)
        self.topology_loss_detected.emit(loss)

    def _on_visibility_changed(self, visible: bool) -> None:
        if self._phase not in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            if self._binding_loss is not None:
                self.frame_pacer.pause()
                self._set_phase(QuickRuntimePhase.PAUSED)
                if visible:
                    self.window.queue_hide()
            elif visible:
                self.frame_pacer.resume()
            else:
                self.frame_pacer.pause()
                self.input_controller.reset_initial_position()
            if self._binding_loss is None:
                self._set_phase(
                    QuickRuntimePhase.VISIBLE if visible else QuickRuntimePhase.PAUSED
                )
        self.visibility_changed.emit(bool(visible))

    def _on_context_menu_requested(self, global_pos: QPoint) -> None:
        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            return
        local_pos = self.window.mapFromGlobal(global_pos)
        self.context_menu_model.open_at(local_pos.x(), local_pos.y())

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
        if self._auxiliary is not None:
            self._retired_auxiliary_state = self._auxiliary.describe()
        if self._cursor is not None:
            self._retired_cursor_state = self._cursor.describe()
        if self._context_menu is not None:
            self._retired_context_menu_state = self._context_menu.describe()
        if self._transition is not None:
            self._retired_transition_state = self._transition.describe()
        self._window_delete_queued = True
        window.deleteLater()

    def _on_window_destroyed(self, *_args: object) -> None:
        if self._phase is not QuickRuntimePhase.RETIRING:
            return
        self._window = None
        self._scene = None
        self._pacer = None
        self._transition = None
        if self._widget_runtime_manager is not None:
            self._widget_runtime_manager.cleanup()
            self._widget_runtime_manager = None
        if self._auxiliary is not None:
            self._retired_auxiliary_state = self._auxiliary.describe()
            self._auxiliary.deleteLater()
            self._auxiliary = None
        if self._cursor is not None:
            self._retired_cursor_state = self._cursor.describe()
            self._cursor.deleteLater()
            self._cursor = None
        if self._context_menu is not None:
            self._retired_context_menu_state = self._context_menu.describe()
            self._context_menu.deleteLater()
            self._context_menu = None
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
