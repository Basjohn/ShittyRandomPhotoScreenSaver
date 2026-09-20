"""Pure, event-only reveal policy for the optional system-volume OSD.

The shared Core Audio owner supplies complete snapshots. This policy does not
create a source, timer or publication authority. The Qt presenter owns a single
restartable inactivity deadline, armed only when ``accept`` requests a reveal.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class OSDDecision:
    accepted: bool
    reveal: bool
    available: bool
    volume: float | None
    muted: bool
    endpoint_token: int
    revision: int


class SystemAudioOSDPolicy:
    def __init__(self) -> None:
        self._last: tuple[bool, float | None, bool, int] | None = None
        self._revision = -1
        self._endpoint_token = -1
        self._retired = False

    def accept(self, snapshot: object) -> OSDDecision:
        if self._retired:
            return OSDDecision(False, False, False, None, False,
                               self._endpoint_token, self._revision)
        revision = int(getattr(snapshot, "revision"))
        token = int(getattr(snapshot, "endpoint_token"))
        available = bool(getattr(snapshot, "available"))
        raw_volume = getattr(snapshot, "volume", None) if available else None
        if raw_volume is None:
            available = False
            volume = None
        else:
            volume = float(raw_volume)
            if not isfinite(volume) or not 0.0 <= volume <= 1.0:
                raise ValueError("invalid system-audio volume snapshot")
            volume = round(volume, 6)
        muted = bool(getattr(snapshot, "muted")) if available else False
        if token < self._endpoint_token or (
            token == self._endpoint_token and revision <= self._revision
        ):
            return OSDDecision(False, False, available, volume, muted, token, revision)
        state = (available, volume, muted, token)
        previous = self._last
        self._last = state
        self._revision = revision
        self._endpoint_token = token
        # Initial subscription is a silent state seed. A newly reconnected
        # device never displays a stale predecessor's value as an OSD event.
        reveal = bool(
            previous is not None and previous[0] and available and state != previous
            and token == previous[3]
        )
        return OSDDecision(True, reveal, available, volume, muted, token, revision)

    def retire(self) -> None:
        self._retired = True
        self._last = None
