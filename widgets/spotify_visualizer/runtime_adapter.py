"""Explicit legacy QWidget adapter properties for runtime-controller state.

This is intentionally not a generic ``__getattr__`` facade. It lists the
temporary old-presenter seams that still need controller-owned state while the
QWidget remains production presentation before Phase H.
"""

from __future__ import annotations

from typing import Any

from widgets.spotify_visualizer.audio_worker import VisualizerMode


_VISUALIZER_MODE_BY_ID = {
    "spectrum": VisualizerMode.SPECTRUM,
    "oscilloscope": VisualizerMode.OSCILLOSCOPE,
    "sine_wave": VisualizerMode.SINE_WAVE,
    "bubble": VisualizerMode.BUBBLE,
    "devcurve": VisualizerMode.DEVCURVE,
}


class LegacyVisualizerRuntimeAdapterMixin:
    """Named old-presenter accessors backed by one runtime controller."""

    @property
    def runtime_controller(self):
        return self._runtime_controller

    @property
    def _runtime_generation(self) -> int:
        return self._runtime_controller.runtime_generation

    @_runtime_generation.setter
    def _runtime_generation(self, value: int | None) -> None:
        self._runtime_controller.runtime_generation = value

    @property
    def _bar_count(self) -> int:
        return self._runtime_controller.bar_count

    @_bar_count.setter
    def _bar_count(self, value: int) -> None:
        self._runtime_controller.bar_count = value

    @property
    def _vis_mode(self) -> VisualizerMode:
        return _VISUALIZER_MODE_BY_ID.get(
            self._runtime_controller.mode_id,
            VisualizerMode.SPECTRUM,
        )

    @_vis_mode.setter
    def _vis_mode(self, value: VisualizerMode | str) -> None:
        self._runtime_controller.set_mode(value)

    @property
    def _enabled(self) -> bool:
        return self._runtime_controller.enabled

    @_enabled.setter
    def _enabled(self, value: bool) -> None:
        self._runtime_controller.enabled = value

    @property
    def _spotify_playing(self) -> bool:
        return self._runtime_controller.playing

    @_spotify_playing.setter
    def _spotify_playing(self, value: bool) -> None:
        self._runtime_controller.playing = value

    @property
    def _settings_model(self) -> Any:
        return self._runtime_controller.settings_model

    @_settings_model.setter
    def _settings_model(self, value: Any) -> None:
        self._runtime_controller.settings_model = value

    @property
    def _technical_config_cache(self) -> dict[str, dict[str, Any]]:
        return self._runtime_controller.technical_config_cache

    @_technical_config_cache.setter
    def _technical_config_cache(self, value: dict[str, dict[str, Any]]) -> None:
        self._runtime_controller.technical_config_cache = value

    @property
    def _engine(self) -> Any:
        return self._runtime_controller.engine

    @_engine.setter
    def _engine(self, value: Any) -> None:
        self._runtime_controller.engine = value

    @property
    def _thread_manager(self) -> Any:
        return self._runtime_controller.thread_manager

    @_thread_manager.setter
    def _thread_manager(self, value: Any) -> None:
        self._runtime_controller.thread_manager = value

    @property
    def _process_supervisor(self) -> Any:
        return self._runtime_controller.process_supervisor

    @_process_supervisor.setter
    def _process_supervisor(self, value: Any) -> None:
        self._runtime_controller.process_supervisor = value

    @property
    def _logical_runtime(self):
        return self._runtime_controller.logical_runtime

    @_logical_runtime.setter
    def _logical_runtime(self, value) -> None:
        self._runtime_controller.adopt_logical_runtime(value)

    @property
    def _logical_mailbox(self):
        return self._runtime_controller.logical_mailbox

    @_logical_mailbox.setter
    def _logical_mailbox(self, value) -> None:
        self._runtime_controller.replace_logical_mailbox(value)

    @property
    def _logical_present_pending(self) -> bool:
        return self._runtime_controller.logical_present_pending

    @_logical_present_pending.setter
    def _logical_present_pending(self, value: bool) -> None:
        self._runtime_controller.logical_present_pending = value

    @property
    def _committed_activation_identity(self) -> tuple | None:
        return self._runtime_controller.committed_activation_identity

    @_committed_activation_identity.setter
    def _committed_activation_identity(self, value: tuple | None) -> None:
        self._runtime_controller.committed_activation_identity = value

    @property
    def _mode_activation_committed_for(self):
        return self._runtime_controller.mode_activation_committed_for

    @_mode_activation_committed_for.setter
    def _mode_activation_committed_for(self, value) -> None:
        self._runtime_controller.mode_activation_committed_for = value

    @property
    def _pending_engine_generation(self) -> int:
        return self._runtime_controller.pending_engine_generation

    @_pending_engine_generation.setter
    def _pending_engine_generation(self, value: int) -> None:
        self._runtime_controller.pending_engine_generation = value

    @property
    def _last_engine_generation_seen(self) -> int:
        return self._runtime_controller.last_engine_generation_seen

    @_last_engine_generation_seen.setter
    def _last_engine_generation_seen(self, value: int) -> None:
        self._runtime_controller.last_engine_generation_seen = value

    @property
    def _pending_engine_activation_id(self) -> int:
        return self._runtime_controller.pending_engine_activation_id

    @_pending_engine_activation_id.setter
    def _pending_engine_activation_id(self, value: int) -> None:
        self._runtime_controller.pending_engine_activation_id = value

    @property
    def _last_engine_activation_seen(self) -> int:
        return self._runtime_controller.last_engine_activation_seen

    @_last_engine_activation_seen.setter
    def _last_engine_activation_seen(self, value: int) -> None:
        self._runtime_controller.last_engine_activation_seen = value


__all__ = ["LegacyVisualizerRuntimeAdapterMixin"]
