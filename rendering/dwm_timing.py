"""Passive DWM composition-timing snapshots for P4 presentation attribution.

Answers one question: does a severe 50-80 ms compositor paint gap span roughly
2-4 real DWM refresh/composition intervals while an ordinary gap spans about
one?

Strictly observational:

- ``DwmGetCompositionTimingInfo(NULL, ...)`` only. Windows 8.1+ requires
  ``hwnd = NULL``;
- **never** ``DwmFlush`` - that blocks until the next composition;
- no sleeps, waits or control-flow changes;
- sampled at paint boundaries that already hold the GIL, so no new Qt signal
  callback and no additional GIL entry is introduced;
- unsupported platforms and unavailable fields stay explicit and are never
  zero-invented.
"""
from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from typing import Any

from core.logging.logger import get_logger

logger = get_logger(__name__)

_UINT32 = ctypes.c_uint32
_UINT64 = ctypes.c_uint64


class UNSIGNED_RATIO(ctypes.Structure):
    _fields_ = [("uiNumerator", _UINT32), ("uiDenominator", _UINT32)]


class DWM_TIMING_INFO(ctypes.Structure):
    """Mirror of dwmapi.h DWM_TIMING_INFO under natural alignment."""

    _fields_ = [
        ("cbSize", _UINT32),
        ("rateRefresh", UNSIGNED_RATIO),
        ("qpcRefreshPeriod", _UINT64),
        ("rateCompose", UNSIGNED_RATIO),
        ("qpcVBlank", _UINT64),
        ("cRefresh", _UINT64),
        ("cDXRefresh", _UINT32),
        ("qpcCompose", _UINT64),
        ("cFrame", _UINT64),
        ("cDXPresent", _UINT32),
        ("cRefreshFrame", _UINT64),
        ("cFrameSubmitted", _UINT64),
        ("cDXPresentSubmitted", _UINT32),
        ("cFrameConfirmed", _UINT64),
        ("cDXPresentConfirmed", _UINT32),
        ("cRefreshConfirmed", _UINT64),
        ("cDXRefreshConfirmed", _UINT32),
        ("cFramesLate", _UINT64),
        ("cFramesOutstanding", _UINT32),
        ("cFrameDisplayed", _UINT64),
        ("qpcFrameDisplayed", _UINT64),
        ("cRefreshFrameDisplayed", _UINT64),
        ("cFrameComplete", _UINT64),
        ("qpcFrameComplete", _UINT64),
        ("cFramePending", _UINT64),
        ("qpcFramePending", _UINT64),
        ("cFramesDisplayed", _UINT64),
        ("cFramesComplete", _UINT64),
        ("cFramesPending", _UINT64),
        ("cFramesAvailable", _UINT64),
        ("cFramesDropped", _UINT64),
        ("cFramesMissed", _UINT64),
        ("cRefreshNextDisplayed", _UINT64),
        ("cRefreshNextPresented", _UINT64),
        ("cRefreshesDisplayed", _UINT64),
        ("cRefreshesPresented", _UINT64),
        ("cRefreshStarted", _UINT64),
        ("cPixelsReceived", _UINT64),
        ("cPixelsDrawn", _UINT64),
        ("cBuffersEmpty", _UINT64),
    ]


# Fields reported as N -> N+1 deltas.
DELTA_FIELDS = (
    "cRefresh",
    "cFrame",
    "cFrameSubmitted",
    "cFrameConfirmed",
    "cFrameDisplayed",
    "cFramesLate",
    "cFramesDropped",
    "cFramesMissed",
    "cRefreshesDisplayed",
    "cRefreshesPresented",
)

# QPC fields reported as millisecond deltas.
QPC_DELTA_FIELDS = ("qpcCompose", "qpcVBlank")


@dataclass(frozen=True)
class DwmSnapshot:
    """One captured DWM timing sample plus its owning frame identity."""

    scene_generation: int
    frame_index: int
    values: dict
    supported: bool
    reason: str


class DwmTimingProbe:
    """Bounded, availability-checked DWM timing sampler."""

    def __init__(self, *, capacity: int = 256) -> None:
        from collections import deque

        self._snapshots: deque[DwmSnapshot] = deque(maxlen=capacity)
        self._dwmapi: Any | None = None
        self._qpc_frequency: int | None = None
        self._supported: bool | None = None
        self._reason = "uninitialized"

    # ------------------------------------------------------------- support
    @property
    def supported(self) -> bool:
        if self._supported is None:
            self._probe_support()
        return bool(self._supported)

    @property
    def reason(self) -> str:
        if self._supported is None:
            self._probe_support()
        return self._reason

    def _probe_support(self) -> None:
        if not sys.platform.startswith("win"):
            self._supported = False
            self._reason = "not_windows"
            return
        try:
            self._dwmapi = ctypes.WinDLL("dwmapi")
        except Exception as exc:
            self._supported = False
            self._reason = f"dwmapi_unavailable:{type(exc).__name__}"
            return
        if not hasattr(self._dwmapi, "DwmGetCompositionTimingInfo"):
            self._supported = False
            self._reason = "no_timing_api"
            return
        try:
            frequency = ctypes.c_int64()
            ctypes.windll.kernel32.QueryPerformanceFrequency(ctypes.byref(frequency))
            self._qpc_frequency = int(frequency.value) or None
        except Exception:
            self._qpc_frequency = None
        self._supported = True
        self._reason = "supported"

    # -------------------------------------------------------------- sample
    def capture(self, *, scene_generation: int, frame_index: int) -> bool:
        """Take one snapshot at an existing paint boundary. Never blocks."""
        if not self.supported:
            self._snapshots.append(
                DwmSnapshot(
                    scene_generation=int(scene_generation),
                    frame_index=int(frame_index),
                    values={},
                    supported=False,
                    reason=self._reason,
                )
            )
            return False
        info = DWM_TIMING_INFO()
        info.cbSize = ctypes.sizeof(DWM_TIMING_INFO)
        try:
            # hwnd must be NULL on Windows 8.1+.
            result = self._dwmapi.DwmGetCompositionTimingInfo(None, ctypes.byref(info))
        except Exception as exc:
            self._snapshots.append(
                DwmSnapshot(
                    scene_generation=int(scene_generation),
                    frame_index=int(frame_index),
                    values={},
                    supported=False,
                    reason=f"call_error:{type(exc).__name__}",
                )
            )
            return False
        if result != 0:
            self._snapshots.append(
                DwmSnapshot(
                    scene_generation=int(scene_generation),
                    frame_index=int(frame_index),
                    values={},
                    supported=False,
                    reason=f"hresult:{result:#010x}",
                )
            )
            return False

        values = {name: int(getattr(info, name)) for name in DELTA_FIELDS}
        values.update({name: int(getattr(info, name)) for name in QPC_DELTA_FIELDS})
        values["qpcRefreshPeriod"] = int(info.qpcRefreshPeriod)
        values["rateRefreshNumerator"] = int(info.rateRefresh.uiNumerator)
        values["rateRefreshDenominator"] = int(info.rateRefresh.uiDenominator)
        self._snapshots.append(
            DwmSnapshot(
                scene_generation=int(scene_generation),
                frame_index=int(frame_index),
                values=values,
                supported=True,
                reason="supported",
            )
        )
        return True

    def take_snapshots(self) -> list[DwmSnapshot]:
        drained = list(self._snapshots)
        self._snapshots.clear()
        return drained

    @property
    def qpc_frequency(self) -> int | None:
        if self._supported is None:
            self._probe_support()
        return self._qpc_frequency


def qpc_delta_ms(earlier: int, later: int, frequency: int | None) -> float | None:
    """Convert a QPC tick delta to milliseconds, or None when unconvertible."""
    if not frequency:
        return None
    if later < earlier:
        return None
    return (later - earlier) * 1000.0 / float(frequency)


def associate_dwm(snapshots, frequency: int | None = None) -> dict:
    """Join snapshots N -> N+1 by identity and report deltas.

    Missing or unsupported fields remain explicit rather than zero-invented.
    """
    by_identity = {}
    for snapshot in snapshots:
        by_identity[(snapshot.scene_generation, snapshot.frame_index)] = snapshot

    rows = []
    unsupported = 0
    unmatched = 0
    for snapshot in snapshots:
        if not snapshot.supported:
            unsupported += 1
            continue
        successor = by_identity.get(
            (snapshot.scene_generation, snapshot.frame_index + 1)
        )
        if successor is None or not successor.supported:
            unmatched += 1
            continue
        row = {
            "scene_generation": snapshot.scene_generation,
            "frame_index": snapshot.frame_index,
        }
        for name in DELTA_FIELDS:
            a = snapshot.values.get(name)
            b = successor.values.get(name)
            row[name] = None if (a is None or b is None) else int(b) - int(a)
        for name in QPC_DELTA_FIELDS:
            a = snapshot.values.get(name)
            b = successor.values.get(name)
            row[f"{name}_ms"] = (
                None if (a is None or b is None) else qpc_delta_ms(a, b, frequency)
            )
        row["qpcRefreshPeriod"] = snapshot.values.get("qpcRefreshPeriod")
        row["rateRefreshNumerator"] = snapshot.values.get("rateRefreshNumerator")
        row["rateRefreshDenominator"] = snapshot.values.get("rateRefreshDenominator")
        rows.append(row)

    return {"rows": rows, "unsupported": unsupported, "unmatched": unmatched}
