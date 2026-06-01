from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VisualizerStartupState:
    """Single source of truth for staged visualizer startup state."""

    secondary_stage_registered: bool = False
    secondary_stage_pending: bool = False
    hot_start_started: bool = False
    reveal_pending: bool = False
    reveal_token: int = 0
    reveal_ready_token: int = -1
    wake_deferred: bool = False
    wake_deferred_reason: str = ""
    require_playing_before_reveal: bool = False
    idle_reveal_requires_authoritative_media: bool = False
    has_authoritative_media_update: bool = False
    min_reveal_delay_ms: int = 900
    reveal_watchdog_ms: int = 1900
    reveal_not_before_ts: float = 0.0

    @classmethod
    def from_shared_fade_duration(cls, fade_duration_ms: int) -> "VisualizerStartupState":
        fade_ms = max(0, int(fade_duration_ms))
        min_reveal_delay_ms = max(900, int(fade_ms * 0.8))
        return cls(
            min_reveal_delay_ms=min_reveal_delay_ms,
            reveal_watchdog_ms=min_reveal_delay_ms + 1000,
        )
