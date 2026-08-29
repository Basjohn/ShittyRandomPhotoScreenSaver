"""Thin Quick per-display visualizer ownership edge (H).

This is the small destination-side assembly that owns one
``VisualizerRuntimeController`` per display/generation and binds it into a
``QuickDisplayRuntime``. It invents no visualizer subsystem: the controller
already owns mode/settings, the shared BeatEngine/source, the authored
``VisualizerLogicalRuntime`` and controller-owned logical tick state, viewport
configuration and render-bridge publication. This edge only:

- constructs one controller for the display generation;
- configures it from canonical (already-resolved) settings through the neutral
  logical-configuration authority and the shared engine;
- starts the authored logical runtime with the widget-free step;
- binds the controller's render source + viewport-config seam into the runtime;
- retires it (stop the sole logical runtime, close render admission).

No ``SpotifyVisualizerWidget`` is constructed. The shared BeatEngine is reused
(``ensure_engine``), so no duplicate engine/logical owner is created; exactly one
authored logical runtime exists per active owner/generation.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from core.logging.logger import get_logger

logger = get_logger(__name__)

# Authored default logical cadence ceiling (Hz); matches the widget path's
# authored_logical_interval_s default when no explicit interval is supplied.
_DEFAULT_MAX_FPS = 90.0


def _mode_runtime_factory(mode_id: str) -> Callable[[], Any]:
    """Return the authored per-mode logical runtime factory (lazy import)."""

    normalized = str(mode_id or "").lower()
    if normalized == "bubble":
        from widgets.spotify_visualizer.bubble_frame_runtime import BubbleFrameRuntime

        return BubbleFrameRuntime
    if normalized == "devcurve":
        from widgets.spotify_visualizer.devcurve_frame_runtime import (
            DevCurveFrameRuntime,
        )

        return DevCurveFrameRuntime
    if normalized == "oscilloscope":
        from widgets.spotify_visualizer.oscilloscope_frame_runtime import (
            OscilloscopeFrameRuntime,
        )

        return OscilloscopeFrameRuntime
    if normalized == "sine_wave":
        from widgets.spotify_visualizer.sine_frame_runtime import SineFrameRuntime

        return SineFrameRuntime
    from widgets.spotify_visualizer.spectrum_frame_runtime import SpectrumFrameRuntime

    return SpectrumFrameRuntime


class QuickDisplayVisualizerOwner:
    """Own + bind one visualizer controller for one Quick display generation."""

    def __init__(
        self,
        runtime: Any,
        *,
        bar_count: int,
        initial_mode: str,
        engine_factory: Callable[[int], Any] | None = None,
    ) -> None:
        from widgets.spotify_visualizer.runtime_controller import (
            VisualizerRuntimeController,
        )

        self._runtime = runtime
        self._controller = VisualizerRuntimeController(
            runtime_generation=runtime.runtime_generation,
            bar_count=int(bar_count),
            initial_mode=str(initial_mode),
            engine_factory=engine_factory,
        )
        self._configured = False
        self._started = False
        self._bound = False
        self._retired = False
        self._render_identity: Any = None

    @property
    def controller(self) -> Any:
        return self._controller

    @property
    def render_identity(self) -> Any:
        return self._render_identity

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def is_retired(self) -> bool:
        return self._retired

    def configure(
        self,
        *,
        logical_kwargs: Mapping[str, Any] | None = None,
        thread_manager: Any | None = None,
        process_supervisor: Any | None = None,
        playing: bool = False,
    ) -> None:
        """Configure the controller from already-resolved canonical settings."""

        if self._retired:
            raise RuntimeError("cannot configure a retired visualizer owner")
        from widgets.spotify_visualizer.config_applier import (
            apply_logical_vis_mode_kwargs,
        )
        from widgets.spotify_visualizer.logical_tick_state import (
            install_default_logical_tick_state,
        )

        controller = self._controller
        state = controller.logical_tick_state
        install_default_logical_tick_state(state, bar_count=controller.bar_count)
        if logical_kwargs:
            apply_logical_vis_mode_kwargs(state, logical_kwargs)
        controller.enabled = True
        controller.playing = bool(playing)
        if thread_manager is not None:
            controller.thread_manager = thread_manager
        if process_supervisor is not None:
            controller.process_supervisor = process_supervisor
        controller.ensure_engine()
        # Resolve the sole authored logical runtime for the current mode. The
        # shared engine is reused; no duplicate engine/logical owner is created.
        controller.resolve_logical_mode_state(
            controller.mode_id, _mode_runtime_factory(controller.mode_id)
        )
        # A fresh destination owner is source-ready to advance.
        state._mode_teardown_block_until_ready = False
        state._mode_transition_ready = True
        state._waiting_for_fresh_engine_frame = False
        self._configured = True

    def bind(self, *, engine_generation: int, activation_id: int) -> Any:
        """Bind the controller's render source + viewport-config seam into the runtime."""

        if self._retired:
            raise RuntimeError("cannot bind a retired visualizer owner")
        self._render_identity = self._runtime.bind_visualizer_render_source(
            self._controller,
            engine_generation=int(engine_generation),
            activation_id=int(activation_id),
        )
        self._runtime.bind_visualizer_viewport_config(
            self._controller.set_custom_viewport_override
        )
        self._bound = True
        return self._render_identity

    def start(self, *, interval_s: float | None = None) -> None:
        """Start the sole authored logical runtime with the widget-free step."""

        if self._retired:
            raise RuntimeError("cannot start a retired visualizer owner")
        from widgets.spotify_visualizer.tick_pipeline import logical_tick

        controller = self._controller
        interval = (
            float(interval_s)
            if interval_s is not None
            else 1.0 / max(15.0, _DEFAULT_MAX_FPS)
        )
        controller.start_logical_runtime(
            step=lambda _deadline_ts, _s=controller.logical_tick_state: logical_tick(_s),
            interval_s=interval,
        )
        self._started = True

    def retire(self) -> bool:
        """Retire exactly once: stop the sole logical runtime, close admission."""

        if self._retired:
            return False
        self._retired = True
        try:
            self._controller.stop_logical_runtime()
        except Exception:
            logger.error(
                "[VIS_OWNER] Logical runtime stop raised during retirement",
                exc_info=True,
            )
        self._controller.close_render_admission()
        return True


__all__ = ["QuickDisplayVisualizerOwner"]
