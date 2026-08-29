"""Controller-owned presentation-neutral visualizer logical tick state (H).

The authored per-tick logical computation historically ran against a large set
of live ``SpotifyVisualizerWidget`` fields. This object is the destination owner
for that per-tick logical state so ``VisualizerLogicalRuntime`` can advance
without a ``QWidget``/legacy presenter argument, per the H visualizer runtime
ownership correction.

Design:

- The presentation-neutral ``VisualizerRuntimeController`` owns exactly one of
  these per generation; it does **not** duplicate the BeatEngine, source, logical
  runtime, mailbox or render bridge - those stay singular on the controller.
- Fields the controller already owns (engine/playback/mode identity, mailbox,
  engine generation/activation fencing, thread/process/settings seams) are
  exposed here as delegating properties to the controller, so this object is a
  single complete logical host.
- The remaining authored per-tick logical fields (heartbeat, perf-tick,
  devcurve, bubble, mode-transition-readiness, source freshness, smoothing) live
  here as plain attributes, populated by the existing initialization/tick code.
- The five logical hooks the tick pipeline invokes are thin delegators to the
  existing presentation-neutral module functions, passing this host.

No QML/QQuickItem/QScreen/render-thread object ever enters this state. This is an
ownership migration; authored algorithms, timing and semantics are unchanged.
"""

from __future__ import annotations

from typing import Any


# The controller-owned fields the logical host exposes by delegation. Mirrors the
# legacy widget adapter so a state-owned host and a widget host are interchangeable.
_CONTROLLER_DELEGATED: tuple[str, ...] = (
    "_engine",
    "_spotify_playing",
    "_enabled",
    "_bar_count",
    "_settings_model",
    "_technical_config_cache",
    "_thread_manager",
    "_process_supervisor",
    "_logical_mailbox",
    "_logical_present_pending",
    "_committed_activation_identity",
    "_mode_activation_committed_for",
    "_pending_engine_generation",
    "_last_engine_generation_seen",
    "_pending_engine_activation_id",
    "_last_engine_activation_seen",
)


class VisualizerLogicalTickState:
    """Single presentation-neutral host for one generation's logical tick state."""

    def __init__(self, controller: Any) -> None:
        object.__setattr__(self, "_controller", controller)

    # ------------------------------------------------------------------ #
    # Controller-delegated identity/lifecycle fields                      #
    # ------------------------------------------------------------------ #
    @property
    def runtime_controller(self) -> Any:
        return self._controller

    @property
    def _runtime_generation(self) -> int:
        return self._controller.runtime_generation

    @_runtime_generation.setter
    def _runtime_generation(self, value: int | None) -> None:
        self._controller.runtime_generation = value

    @property
    def _engine(self) -> Any:
        return self._controller.engine

    @_engine.setter
    def _engine(self, value: Any) -> None:
        self._controller.engine = value

    @property
    def _spotify_playing(self) -> bool:
        return self._controller.playing

    @_spotify_playing.setter
    def _spotify_playing(self, value: bool) -> None:
        self._controller.playing = value

    @property
    def _enabled(self) -> bool:
        return self._controller.enabled

    @_enabled.setter
    def _enabled(self, value: bool) -> None:
        self._controller.enabled = value

    @property
    def _bar_count(self) -> int:
        return self._controller.bar_count

    @_bar_count.setter
    def _bar_count(self, value: int) -> None:
        self._controller.bar_count = value

    @property
    def _settings_model(self) -> Any:
        return self._controller.settings_model

    @_settings_model.setter
    def _settings_model(self, value: Any) -> None:
        self._controller.settings_model = value

    @property
    def _technical_config_cache(self) -> dict[str, dict[str, Any]]:
        return self._controller.technical_config_cache

    @_technical_config_cache.setter
    def _technical_config_cache(self, value: dict[str, dict[str, Any]]) -> None:
        self._controller.technical_config_cache = value

    @property
    def _thread_manager(self) -> Any:
        return self._controller.thread_manager

    @_thread_manager.setter
    def _thread_manager(self, value: Any) -> None:
        self._controller.thread_manager = value

    @property
    def _process_supervisor(self) -> Any:
        return self._controller.process_supervisor

    @_process_supervisor.setter
    def _process_supervisor(self, value: Any) -> None:
        self._controller.process_supervisor = value

    @property
    def _logical_mailbox(self) -> Any:
        return self._controller.logical_mailbox

    @_logical_mailbox.setter
    def _logical_mailbox(self, value: Any) -> None:
        self._controller.replace_logical_mailbox(value)

    @property
    def _logical_present_pending(self) -> bool:
        return self._controller.logical_present_pending

    @_logical_present_pending.setter
    def _logical_present_pending(self, value: bool) -> None:
        self._controller.logical_present_pending = value

    @property
    def _committed_activation_identity(self) -> tuple | None:
        return self._controller.committed_activation_identity

    @_committed_activation_identity.setter
    def _committed_activation_identity(self, value: tuple | None) -> None:
        self._controller.committed_activation_identity = value

    @property
    def _mode_activation_committed_for(self) -> Any:
        return self._controller.mode_activation_committed_for

    @_mode_activation_committed_for.setter
    def _mode_activation_committed_for(self, value: Any) -> None:
        self._controller.mode_activation_committed_for = value

    @property
    def _pending_engine_generation(self) -> int:
        return self._controller.pending_engine_generation

    @_pending_engine_generation.setter
    def _pending_engine_generation(self, value: int) -> None:
        self._controller.pending_engine_generation = value

    @property
    def _last_engine_generation_seen(self) -> int:
        return self._controller.last_engine_generation_seen

    @_last_engine_generation_seen.setter
    def _last_engine_generation_seen(self, value: int) -> None:
        self._controller.last_engine_generation_seen = value

    @property
    def _pending_engine_activation_id(self) -> int:
        return self._controller.pending_engine_activation_id

    @_pending_engine_activation_id.setter
    def _pending_engine_activation_id(self, value: int) -> None:
        self._controller.pending_engine_activation_id = value

    @property
    def _last_engine_activation_seen(self) -> int:
        return self._controller.last_engine_activation_seen

    @_last_engine_activation_seen.setter
    def _last_engine_activation_seen(self, value: int) -> None:
        self._controller.last_engine_activation_seen = value

    # ------------------------------------------------------------------ #
    # Logical hooks: thin delegators to existing neutral module functions #
    # ------------------------------------------------------------------ #
    def _check_mode_teardown_ready(self, engine: Any, now_ts: float) -> bool:
        from widgets.spotify_visualizer.mode_transition import (
            evaluate_mode_teardown_ready,
        )

        return evaluate_mode_teardown_ready(self, engine, now_ts)

    def _on_first_frame_after_cold_start(self) -> None:
        from widgets.spotify_visualizer.mode_transition import (
            on_first_frame_after_cold_start,
        )

        on_first_frame_after_cold_start(self)

    def _log_tick_spike(self, dt: float, transition_ctx: dict[str, Any]) -> None:
        from widgets.spotify_visualizer.tick_helpers import log_tick_spike

        log_tick_spike(self, dt, transition_ctx)

    def _log_perf_snapshot(self, reset: bool = False) -> None:
        from widgets.spotify_visualizer.tick_helpers import log_perf_snapshot

        log_perf_snapshot(self, reset=reset)

    def _log_audio_latency_metrics(
        self,
        engine: Any,
        now_ts: float,
        force_reason: str | None = None,
    ) -> None:
        from widgets.spotify_visualizer.tick_pipeline import log_audio_latency_metrics

        log_audio_latency_metrics(self, engine, now_ts, force_reason=force_reason)


__all__ = ["VisualizerLogicalTickState", "_CONTROLLER_DELEGATED"]
