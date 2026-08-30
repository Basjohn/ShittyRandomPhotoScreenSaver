"""One coordinated retained-Quick startup reveal for ordinary widget families.

The pre-Quick product had a single manager-owned startup fade authority.  The
Qt Quick migration already retained a presentation-neutral root opacity seam on
every ordinary family (`OverlayWidget.fadeOpacity`), but the orchestration that
actually drove it was missing while lifecycle telemetry still reported a reveal
completion.

This owner restores the *one shared scalar* contract without resurrecting
QWidget/QGraphicsOpacityEffect choreography, per-widget timers, or a second
presentation surface.  Exact visual timing remains a Parity+ tuning concern;
the important runtime contract is that all admitted ordinary families start at
zero opacity, reveal together once the generation is genuinely reveal-ready,
and publish completion only after the animation has finished.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QObject, QVariantAnimation, Signal


# Historical accepted product timing used one soft shared overlay fade rather
# than the old 300 ms generic UI fade constant.  Keep this destination-owned so
# later J Parity+ tuning never needs to import the retired QWidget fade helper.
QUICK_STARTUP_REVEAL_DURATION_MS = 1800


class QuickStartupRevealCoordinator(QObject):
    """Drive one generation-scoped opacity scalar across ordinary families."""

    completed = Signal(int)

    def __init__(
        self,
        *,
        runtime_generation: int,
        opacity_sink: Callable[[float], int],
        duration_ms: int = QUICK_STARTUP_REVEAL_DURATION_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        if not callable(opacity_sink):
            raise TypeError("startup reveal opacity_sink must be callable")
        self._runtime_generation = int(runtime_generation)
        self._opacity_sink = opacity_sink
        self._duration_ms = max(0, int(duration_ms))
        self._target_count = 0
        self._primed = False
        self._started = False
        self._completed = False
        self._cancelled = False

        animation = QVariantAnimation(self)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(self._duration_ms)
        animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        animation.valueChanged.connect(self._on_value_changed)
        animation.finished.connect(self._on_finished)
        self._animation = animation

    @property
    def runtime_generation(self) -> int:
        return self._runtime_generation

    @property
    def target_count(self) -> int:
        return self._target_count

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def is_completed(self) -> bool:
        return self._completed

    def prime(self) -> int:
        """Hide every currently admitted ordinary family before window reveal."""

        if self._cancelled or self._completed:
            return 0
        if self._primed:
            return self._target_count
        self._target_count = max(0, int(self._opacity_sink(0.0) or 0))
        self._primed = True
        return self._target_count

    def start(self) -> bool:
        """Begin the one shared reveal, exactly once."""

        if self._cancelled or self._completed or self._started:
            return False
        if not self._primed:
            self.prime()
        self._started = True

        # No ordinary targets must not hold startup accounting hostage.  The
        # visualizer retains its independent authored startup/fade authority.
        if self._target_count <= 0 or self._duration_ms <= 0:
            self._opacity_sink(1.0)
            self._finish_once()
            return True

        self._animation.start()
        return True

    def cancel(self) -> bool:
        """Cancel a retiring generation without publishing false completion."""

        if self._cancelled or self._completed:
            return False
        self._cancelled = True
        self._animation.stop()
        return True

    def _on_value_changed(self, value: object) -> None:
        if self._cancelled or self._completed:
            return
        try:
            opacity = float(value)
        except (TypeError, ValueError):
            return
        self._opacity_sink(max(0.0, min(1.0, opacity)))

    def _on_finished(self) -> None:
        if self._cancelled:
            return
        self._opacity_sink(1.0)
        self._finish_once()

    def _finish_once(self) -> None:
        if self._cancelled or self._completed:
            return
        self._completed = True
        self.completed.emit(self._runtime_generation)


__all__ = [
    "QUICK_STARTUP_REVEAL_DURATION_MS",
    "QuickStartupRevealCoordinator",
]
