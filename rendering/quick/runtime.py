"""Generation-scoped Qt Quick runtime owner for one physical display."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QScreen

from .frame_pacer import QuickFramePacer
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

    def __init__(
        self,
        *,
        screen_index: int,
        runtime_generation: int,
        screen: QScreen,
        scene_factory: QuickSceneFactory,
        window_policy: QuickWindowPolicy,
        telemetry: RenderNodeTelemetry | None = None,
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

        self._window.display_identity_changed.connect(
            self._on_display_identity_changed
        )
        self._window.visibleChanged.connect(self._on_visibility_changed)
        self._window.destroyed.connect(self._on_window_destroyed)
        self._scene.readiness_changed.connect(self._on_scene_readiness_changed)

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

    def show_on_screen(self) -> None:
        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            raise RuntimeError("cannot show a retiring Quick display runtime")
        self.window.show_on_screen()

    def hide(self) -> None:
        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            return
        self.frame_pacer.stop()
        self.window.queue_hide()
        self._set_phase(QuickRuntimePhase.PAUSED)

    def quiesce_for_runtime_pause(self) -> None:
        self.hide()

    def close_runtime(self) -> bool:
        """Begin exact retirement without blocking Python on the render thread."""

        if self._phase in (QuickRuntimePhase.RETIRING, QuickRuntimePhase.RETIRED):
            return False

        self._set_phase(QuickRuntimePhase.RETIRING)
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
        return {
            "screen_index": self._screen_index,
            "runtime_generation": self._runtime_generation,
            "phase": self._phase.value,
            "display_identity": self._display_identity.as_dict(),
            "scene_readiness": self._scene_readiness.as_dict(),
            "window": window_state,
            "scene": scene_state,
            "frame_pacer": pacer_state,
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
        self._window_delete_queued = True
        window.deleteLater()

    def _on_window_destroyed(self, *_args: object) -> None:
        if self._phase is not QuickRuntimePhase.RETIRING:
            return
        self._window = None
        self._scene = None
        self._pacer = None
        self._set_phase(QuickRuntimePhase.RETIRED)
        if not self._retirement_emitted:
            self._retirement_emitted = True
            self.retirement_completed.emit(self._runtime_generation)

    def _set_phase(self, phase: QuickRuntimePhase) -> None:
        self._phase = phase
