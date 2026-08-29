"""Presentation-neutral visualizer runtime ownership.

The legacy QWidget remains the current production presentation adapter until
the Qt Quick cutover. This owner contains the state that must survive that
pixel-boundary change: mode/settings/playback identity, the shared source
handle, and the sole authored logical runtime/latest-state mailbox.

This module deliberately imports no QWidget, QQuickItem, QPainter, OpenGL, or
legacy compositor code. A future Quick presentation can own this controller
without constructing a hidden QWidget.
"""

from __future__ import annotations

import copy
import threading
from collections.abc import Callable
from typing import Any

from core.settings.visualizer_mode_registry import (
    VisualizerModePresentationPolicy,
    coerce_visualizer_mode_id,
    get_visualizer_presentation_policy,
)
from widgets.spotify_visualizer.logical_runtime import (
    LatestStateMailbox,
    VisualizerLogicalRuntime,
    coerce_identity,
)
from widgets.spotify_visualizer.render_bridge import (
    VisualizerRenderIdentity,
    VisualizerSnapshotBridge,
)
from widgets.spotify_visualizer.render_state import (
    CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
    ResolvedVisualizerPresentation,
    VisualizerLogicalFrame,
    compose_visualizer_render_snapshot,
)


EngineFactory = Callable[[int], Any]
LogicalStep = Callable[[float], None]
ModeStateFactory = Callable[[], Any]


class VisualizerRuntimeController:
    """Own non-pixel visualizer identity, source, and logical lifecycle.

    The controller is intentionally small. Mode-specific authored state stays
    in the existing logical modules while those modes move through Phase D;
    presentation geometry, fades, chrome, input, and GPU resources do not
    belong here.
    """

    def __init__(
        self,
        *,
        runtime_generation: int | None,
        bar_count: int = 32,
        initial_mode: str | None = None,
        engine_factory: EngineFactory | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._runtime_generation = coerce_identity(runtime_generation)
        self._bar_count = max(1, int(bar_count))
        self._mode_id = coerce_visualizer_mode_id(initial_mode)
        self._presentation_policy = get_visualizer_presentation_policy(
            self._mode_id
        )

        self._enabled = False
        self._playing = False
        self._settings_model: Any = None
        self._technical_config_cache: dict[str, dict[str, Any]] = {}
        self._resolved_activation: Any = None
        self._committed_activation_identity: tuple | None = None
        self._mode_activation_committed_for: Any = None

        self._engine_factory = engine_factory
        self._engine: Any = None
        self._thread_manager: Any = None
        self._process_supervisor: Any = None

        self._pending_engine_generation = -1
        self._last_engine_generation_seen = -1
        self._pending_engine_activation_id = -1
        self._last_engine_activation_seen = -1

        self._logical_mailbox = LatestStateMailbox()
        self._logical_runtime: VisualizerLogicalRuntime | None = None
        self._logical_present_pending = False
        self._logical_mode_states: dict[str, Any] = {}
        # Viewport extent has two distinct owners that must not fight over one
        # scalar: the ordinary committed presentation extent (set by the render
        # publication path) and an optional temporary CUSTOM working override
        # (set by the live edit seam). The effective extent consumed by the
        # authored logical step is the override while it is active, otherwise the
        # committed value. Retiring the override never manufactures canonical - it
        # simply falls back to whatever is actually committed.
        self._committed_viewport_extent = (
            CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
        )
        self._custom_viewport_override: tuple[float, float] | None = None
        self._render_bridge = VisualizerSnapshotBridge()
        # The presentation-neutral destination owner for this generation's
        # authored per-tick logical state. The authored logical step advances
        # against this host so no QWidget/legacy presenter is required. One per
        # controller; the shared engine/source/logical runtime stay singular here.
        from widgets.spotify_visualizer.logical_tick_state import (
            VisualizerLogicalTickState,
        )

        self._logical_tick_state = VisualizerLogicalTickState(self)

    @property
    def logical_tick_state(self) -> Any:
        """Return the controller-owned authored per-tick logical state host."""

        return self._logical_tick_state

    @property
    def runtime_generation(self) -> int:
        return self._runtime_generation

    @runtime_generation.setter
    def runtime_generation(self, value: int | None) -> None:
        generation = coerce_identity(value)
        with self._lock:
            runtime = self._logical_runtime
            if runtime is not None and generation != self._runtime_generation:
                raise RuntimeError(
                    "cannot retarget a generation-scoped visualizer runtime"
                )
            if generation != self._runtime_generation:
                self._render_bridge.close_admission()
                self._logical_mode_states.clear()
            self._runtime_generation = generation

    @property
    def bar_count(self) -> int:
        return self._bar_count

    @bar_count.setter
    def bar_count(self, value: int) -> None:
        self._bar_count = max(1, int(value))

    @property
    def mode_id(self) -> str:
        return self._mode_id

    @property
    def presentation_policy(self) -> VisualizerModePresentationPolicy:
        return self._presentation_policy

    def set_mode(self, mode: Any) -> str:
        raw = getattr(mode, "name", mode)
        mode_id = coerce_visualizer_mode_id(str(raw or "").lower())
        retired_states: tuple[Any, ...] = ()
        with self._lock:
            if mode_id != self._mode_id:
                # A render admission is generation + activation + mode scoped.
                # The target mode reopens it only when that activation commits.
                self._render_bridge.close_admission()
                retired_states = tuple(self._logical_mode_states.values())
                self._logical_mode_states.clear()
            self._mode_id = mode_id
            self._presentation_policy = get_visualizer_presentation_policy(
                mode_id
            )
        for state in retired_states:
            retire = getattr(state, "retire", None)
            if callable(retire):
                retire()
                continue
            reset = getattr(state, "reset", None)
            if callable(reset):
                reset()
        return mode_id

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = bool(value)

    @property
    def playing(self) -> bool:
        return self._playing

    @playing.setter
    def playing(self, value: bool) -> None:
        self._playing = bool(value)

    @property
    def settings_model(self) -> Any:
        return self._settings_model

    @settings_model.setter
    def settings_model(self, model: Any) -> None:
        try:
            self._settings_model = copy.deepcopy(model)
        except Exception:
            self._settings_model = model

    @property
    def technical_config_cache(self) -> dict[str, dict[str, Any]]:
        return self._technical_config_cache

    @technical_config_cache.setter
    def technical_config_cache(self, value: dict[str, dict[str, Any]]) -> None:
        self._technical_config_cache = value

    @property
    def resolved_activation(self) -> Any:
        return self._resolved_activation

    def record_resolved_activation(self, payload: Any) -> None:
        try:
            self._resolved_activation = copy.deepcopy(payload)
        except Exception:
            self._resolved_activation = payload

    @property
    def committed_activation_identity(self) -> tuple | None:
        return self._committed_activation_identity

    @committed_activation_identity.setter
    def committed_activation_identity(self, value: tuple | None) -> None:
        self._committed_activation_identity = value
        if value is None:
            self._render_bridge.close_admission()
            return
        try:
            _payload_identity, engine_stamp = value
            engine_generation, activation_id = engine_stamp
            self.begin_render_activation(
                engine_generation=engine_generation,
                activation_id=activation_id,
            )
        except (TypeError, ValueError):
            self._render_bridge.close_admission()

    @property
    def mode_activation_committed_for(self) -> Any:
        return self._mode_activation_committed_for

    @mode_activation_committed_for.setter
    def mode_activation_committed_for(self, value: Any) -> None:
        self._mode_activation_committed_for = value

    @property
    def engine(self) -> Any:
        return self._engine

    @engine.setter
    def engine(self, value: Any) -> None:
        self._engine = value

    def ensure_engine(self) -> Any:
        with self._lock:
            if self._engine is not None:
                return self._engine
            factory = self._engine_factory
            if factory is None:
                # Lazy so importing the controller does not import the
                # QObject-backed source implementation or presentation code.
                from widgets.spotify_visualizer.beat_engine import (
                    get_shared_spotify_beat_engine,
                )

                factory = get_shared_spotify_beat_engine
            engine = factory(self._bar_count)
            self._engine = engine
            return engine

    @property
    def thread_manager(self) -> Any:
        return self._thread_manager

    @thread_manager.setter
    def thread_manager(self, value: Any) -> None:
        self._thread_manager = value

    @property
    def process_supervisor(self) -> Any:
        return self._process_supervisor

    @process_supervisor.setter
    def process_supervisor(self, value: Any) -> None:
        self._process_supervisor = value

    @property
    def pending_engine_generation(self) -> int:
        return self._pending_engine_generation

    @pending_engine_generation.setter
    def pending_engine_generation(self, value: int) -> None:
        self._pending_engine_generation = int(value)

    @property
    def last_engine_generation_seen(self) -> int:
        return self._last_engine_generation_seen

    @last_engine_generation_seen.setter
    def last_engine_generation_seen(self, value: int) -> None:
        self._last_engine_generation_seen = int(value)

    @property
    def pending_engine_activation_id(self) -> int:
        return self._pending_engine_activation_id

    @pending_engine_activation_id.setter
    def pending_engine_activation_id(self, value: int) -> None:
        self._pending_engine_activation_id = int(value)

    @property
    def last_engine_activation_seen(self) -> int:
        return self._last_engine_activation_seen

    @last_engine_activation_seen.setter
    def last_engine_activation_seen(self, value: int) -> None:
        self._last_engine_activation_seen = int(value)

    @property
    def logical_mailbox(self) -> LatestStateMailbox:
        return self._logical_mailbox

    def replace_logical_mailbox(self, mailbox: LatestStateMailbox) -> None:
        """Install an empty mailbox for a legacy harness before runtime start."""

        with self._lock:
            runtime = self._logical_runtime
            if runtime is not None and runtime.is_running():
                raise RuntimeError("cannot replace a running visualizer mailbox")
            self._logical_mailbox = mailbox

    @property
    def render_bridge(self) -> VisualizerSnapshotBridge:
        return self._render_bridge

    @property
    def render_identity(self) -> VisualizerRenderIdentity | None:
        return self._render_bridge.identity

    @property
    def presentation_viewport_extent(self) -> tuple[float, float]:
        """Effective logical viewport extent for the next authored step.

        The temporary CUSTOM working override wins while it is active; otherwise
        the ordinary committed presentation extent applies.
        """

        with self._lock:
            if self._custom_viewport_override is not None:
                return self._custom_viewport_override
            return self._committed_viewport_extent

    @property
    def committed_viewport_extent(self) -> tuple[float, float]:
        """Ordinary committed presentation extent, ignoring any CUSTOM override."""

        with self._lock:
            return self._committed_viewport_extent

    @property
    def has_custom_viewport_override(self) -> bool:
        with self._lock:
            return self._custom_viewport_override is not None

    def set_custom_viewport_override(
        self,
        extent: tuple[float, float] | None,
    ) -> None:
        """Publish (or retire) the temporary CUSTOM working viewport extent.

        This is the presentation-neutral seam for the retained CUSTOM edge
        operation: while edit mode is active the GUI-owned session pushes its
        working logical world here, and the next authored logical step consumes
        it in preference to the committed extent. Viewport extent is state, not
        an authored temporal event, so the latest value coalesces freely - no
        queue, clock or acknowledgement. ``None`` retires the override, which
        falls back to the committed extent (never manufactured canonical). Only
        plain typed floats cross this boundary; no QQuickItem/QScreen/render
        object ever does.
        """

        if extent is None:
            resolved: tuple[float, float] | None = None
        else:
            width = float(extent[0])
            height = float(extent[1])
            if not (width > 0.0 and height > 0.0):
                raise ValueError("viewport extent must be positive")
            resolved = (width, height)
        with self._lock:
            self._custom_viewport_override = resolved

    def commit_presentation_metrics(
        self,
        presentation: ResolvedVisualizerPresentation,
    ) -> None:
        """Commit the ordinary presentation extent for the next authored tick.

        This is the ordinary (non-CUSTOM) publication path. It updates only the
        committed extent and never touches a live CUSTOM working override, so an
        ordinary presentation republish while edit mode is active cannot erase
        the working value. After Save this is the seam that promotes the newly
        committed extent so retiring the override lands on the correct value.
        """

        if not isinstance(presentation, ResolvedVisualizerPresentation):
            raise TypeError("visualizer presentation must already be resolved")
        policy = self._presentation_policy
        if (
            presentation.shell_policy is not policy.shell_policy
            or presentation.clip_policy is not policy.clip_policy
            or presentation.viewport_resize_capable
            != policy.viewport_resize_capable
        ):
            raise ValueError("visualizer presentation policy does not match mode")
        with self._lock:
            self._committed_viewport_extent = presentation.viewport_extent

    def resolve_logical_mode_state(
        self,
        mode_id: object,
        factory: ModeStateFactory,
    ) -> Any:
        """Lazily own plain authored state for only the current mode."""

        canonical = coerce_visualizer_mode_id(mode_id)
        if not callable(factory):
            raise TypeError("visualizer logical mode state requires a factory")
        with self._lock:
            if canonical != self._mode_id:
                raise ValueError(
                    "visualizer logical mode state does not match current mode"
                )
            state = self._logical_mode_states.get(canonical)
            if state is None:
                state = factory()
                self._logical_mode_states[canonical] = state
            return state

    def peek_logical_mode_state(self, mode_id: object) -> Any:
        """Inspect an already-active plain mode state without constructing it."""

        canonical = coerce_visualizer_mode_id(mode_id)
        with self._lock:
            if canonical != self._mode_id:
                return None
            return self._logical_mode_states.get(canonical)

    def begin_render_activation(
        self,
        *,
        engine_generation: int,
        activation_id: int,
    ) -> VisualizerRenderIdentity:
        """Open immutable render admission after activation commit."""

        return self._render_bridge.begin_activation(
            runtime_generation=self._runtime_generation,
            engine_generation=engine_generation,
            activation_id=activation_id,
            mode_id=self._mode_id,
        )

    def close_render_admission(self) -> None:
        self._render_bridge.close_admission()

    def publish_render_snapshot(
        self,
        logical: VisualizerLogicalFrame,
        presentation: ResolvedVisualizerPresentation,
        *,
        logical_revision: int,
    ) -> bool:
        """Compose and admit one GUI-resolved immutable Quick snapshot."""

        if logical.mode_id != self._mode_id:
            return False
        policy = self._presentation_policy
        if (
            presentation.shell_policy is not policy.shell_policy
            or presentation.clip_policy is not policy.clip_policy
            or presentation.viewport_resize_capable
            != policy.viewport_resize_capable
        ):
            return False
        self.commit_presentation_metrics(presentation)
        snapshot = compose_visualizer_render_snapshot(
            logical,
            presentation,
            logical_revision=logical_revision,
        )
        return self._render_bridge.publish(snapshot)

    @property
    def logical_runtime(self) -> VisualizerLogicalRuntime | None:
        return self._logical_runtime

    def adopt_logical_runtime(
        self,
        runtime: VisualizerLogicalRuntime | None,
    ) -> None:
        """Adopt a preconstructed runtime used by legacy diagnostics.

        Production starts through :meth:`start_logical_runtime`; this narrow
        seam keeps existing production-shaped diagnostic tools working without
        giving presentation code ownership of the runtime lifecycle.
        """

        with self._lock:
            current = self._logical_runtime
            if current is not None and current is not runtime and current.is_running():
                raise RuntimeError("cannot replace a running visualizer runtime")
            self._logical_runtime = runtime

    @property
    def logical_present_pending(self) -> bool:
        return self._logical_present_pending

    @logical_present_pending.setter
    def logical_present_pending(self, value: bool) -> None:
        self._logical_present_pending = bool(value)

    def reset_logical_handoff(self) -> None:
        """Reset the empty handoff before its owner starts.

        A running logical runtime is never replaced or orphaned merely to
        reset a mailbox.
        """

        with self._lock:
            runtime = self._logical_runtime
            if runtime is not None and runtime.is_running():
                raise RuntimeError("cannot reset a running visualizer runtime")
            self._logical_runtime = None
            self._logical_mailbox.clear()
            self._logical_present_pending = False
            self._logical_mode_states.clear()
            self._render_bridge.close_admission()

    def start_logical_runtime(
        self,
        *,
        step: LogicalStep,
        interval_s: float,
    ) -> VisualizerLogicalRuntime:
        """Start or return the sole authored logical runtime."""

        with self._lock:
            runtime = self._logical_runtime
            if runtime is not None:
                if runtime.is_running():
                    return runtime
                self._logical_runtime = None

            runtime = VisualizerLogicalRuntime(
                step=step,
                interval_s=interval_s,
                generation=self._runtime_generation,
            )
            # Publish the owner before the thread starts. A fast first step can
            # then observe that it is the thread-owned path and request the one
            # bounded presentation callback.
            self._logical_runtime = runtime
            try:
                runtime.start()
            except Exception:
                self._logical_runtime = None
                raise
            return runtime

    def stop_logical_runtime(self) -> bool:
        """Close and join logical ownership without orphaning a live thread."""

        self._render_bridge.close_admission()
        with self._lock:
            runtime = self._logical_runtime
        if runtime is None:
            self._logical_mailbox.clear()
            self._logical_present_pending = False
            self._logical_mode_states.clear()
            return True

        try:
            joined = bool(runtime.stop())
        except Exception:
            # A failed stop is still a closed publication boundary. Retain the
            # runtime object as the unresolved destruction owner, but never
            # leave a stale frame or GUI admission request live behind it.
            with self._lock:
                self._logical_mailbox.clear()
                self._logical_present_pending = False
            raise
        with self._lock:
            if joined and self._logical_runtime is runtime:
                self._logical_runtime = None
                self._logical_mode_states.clear()
            self._logical_mailbox.clear()
            self._logical_present_pending = False
        return joined

    def describe(self) -> dict[str, Any]:
        runtime = self._logical_runtime
        return {
            "runtime_generation": self._runtime_generation,
            "mode": self._mode_id,
            "enabled": self._enabled,
            "playing": self._playing,
            "logical_running": bool(runtime and runtime.is_running()),
            "logical_revision": self._logical_mailbox.revision,
            "render_admission_open": self._render_bridge.is_open,
        }


__all__ = ["VisualizerRuntimeController"]
