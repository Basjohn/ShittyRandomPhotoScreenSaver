"""Render-thread failure logging that cannot become a per-frame traceback storm."""

from __future__ import annotations

import logging


class RenderFailureLog:
    """Log each distinct render failure once with its traceback, then count repeats.

    A render node that fails persistently fails on every frame (90-330 per second).
    Formatting a traceback per frame on the render thread adds GIL-held work on
    top of the failure itself. This gate keeps the first occurrence of each
    failure signature with its full traceback, reports sparse repeat milestones
    while the same failure persists, and reports the repeat total when the
    failure changes or the node recovers. It never suppresses a new signature
    and never reclassifies the error; telemetry recording stays with the caller.
    """

    __slots__ = ("_logger", "_label", "_signature", "_repeats", "_next_milestone")

    _FIRST_MILESTONE = 100

    def __init__(self, logger: logging.Logger, label: str) -> None:
        self._logger = logger
        self._label = label
        self._signature: str | None = None
        self._repeats = 0
        self._next_milestone = self._FIRST_MILESTONE

    @property
    def failing(self) -> bool:
        return self._signature is not None

    def note_failure(self, signature: str, exc: BaseException) -> None:
        """Record one failed frame; must be called from inside the ``except`` block."""

        if signature == self._signature:
            self._repeats += 1
            if self._repeats >= self._next_milestone:
                self._next_milestone *= 10
                self._logger.error(
                    "[QUICK] %s still failing after %d repeat(s): %s",
                    self._label,
                    self._repeats,
                    signature,
                )
            return
        self._close_signature()
        self._signature = signature
        self._logger.exception("[QUICK] %s failed: %s", self._label, exc)

    def note_success(self) -> None:
        """Report recovery after a failure run; callers gate on ``failing``."""

        self._close_signature(recovered=True)

    def _close_signature(self, *, recovered: bool = False) -> None:
        signature = self._signature
        if signature is None:
            return
        if recovered:
            self._logger.warning(
                "[QUICK] %s recovered after %d repeat(s) of: %s",
                self._label,
                self._repeats,
                signature,
            )
        elif self._repeats:
            self._logger.error(
                "[QUICK] %s failure superseded after %d repeat(s): %s",
                self._label,
                self._repeats,
                signature,
            )
        self._signature = None
        self._repeats = 0
        self._next_milestone = self._FIRST_MILESTONE
