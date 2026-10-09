"""One coordinated retained-Quick startup reveal for all widget presentation.

The pre-Quick product had a single manager-owned startup fade authority. The Qt
Quick destination now gives ordinary roots and the Visualizer an independent
``startupRevealOpacity`` gate that multiplies, rather than replaces, each
family's authored lifecycle/scene fade.

This owner drives that *one shared scalar* without resurrecting
QWidget/QGraphicsOpacityEffect choreography, per-widget timers, or a second
presentation surface. Exact visual timing remains a Parity+ tuning concern; the
important runtime contract is that all admitted roots start behind the closed
gate, reveal together once the generation is genuinely reveal-ready, and
publish completion only after the animation has finished.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    QEasingCurve, QObject, QPauseAnimation, QSequentialAnimationGroup,
    QVariantAnimation, Signal,
)


# Historical accepted product timing used one soft shared overlay fade rather
# than the old 300 ms generic UI fade constant.  Keep this destination-owned so
# later J Parity+ tuning never needs to import the retired QWidget fade helper.
# The startup gate remains closed 300 ms *after* the same readiness milestone
# as before. This is a one-shot Qt animation pause, not a second timer or
# another presentation clock; ordinary lifecycle/scene fades are untouched.
QUICK_STARTUP_REVEAL_DELAY_MS = 300
# Previously 1,800 ms; lengthen the easing by 700 ms, not to 700 ms.
QUICK_STARTUP_REVEAL_DURATION_MS = 2500
# The initial desktop snapshot is a one-session staging source, not authored
# wallpaper state. Crossfade into the first processed wallpaper on the authored
# startup-staging timing, then release the coordinated widget reveal. This is a
# presentation constant, not the persisted Transitions duration default.
QUICK_STARTUP_DESKTOP_CROSSFADE_DURATION_MS = 1300


class QuickStartupRevealCoordinator(QObject):
    """Drive one generation-scoped opacity scalar across retained widgets."""

    completed = Signal(int)

    def __init__(
        self,
        *,
        runtime_generation: int,
        opacity_sink: Callable[[float], int],
        duration_ms: int = QUICK_STARTUP_REVEAL_DURATION_MS,
        delay_ms: int = QUICK_STARTUP_REVEAL_DELAY_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        if not callable(opacity_sink):
            raise TypeError("startup reveal opacity_sink must be callable")
        self._runtime_generation = int(runtime_generation)
        self._opacity_sink = opacity_sink
        self._duration_ms = max(0, int(duration_ms))
        self._delay_ms = max(0, int(delay_ms))
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
        # Reuse Qt's single unified animation driver for both the held gate and
        # the original opacity animation. QPauseAnimation does not write opacity
        # or create a timer/poller; the same generation owner controls both.
        timeline = QSequentialAnimationGroup(self)
        if self._delay_ms:
            timeline.addAnimation(QPauseAnimation(self._delay_ms))
        timeline.addAnimation(animation)
        self._animation = animation
        self._timeline = timeline

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
        """Hide every currently admitted widget behind the startup gate."""

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
        else:
            # Families may finish retained construction while the desktop ->
            # first-wallpaper crossfade is running. Re-project the closed gate
            # immediately before reveal and refresh the target count so a root
            # that did not exist at prime time still participates in the same
            # synchronized fade instead of appearing at full opacity.
            self._target_count = max(
                self._target_count,
                max(0, int(self._opacity_sink(0.0) or 0)),
            )
        self._started = True

        # The reveal scalar is generation-owned, not target-count-owned. Even an
        # empty initial target set runs the bounded startup animation so a late
        # Visualizer/family root admitted during the reveal inherits the current
        # scalar rather than appearing at full opacity. Only explicitly zero
        # delay AND zero duration bypass the timeline.
        if self._duration_ms <= 0 and self._delay_ms <= 0:
            self._opacity_sink(1.0)
            self._finish_once()
            return True

        # The held gate must also apply to zero-duration overrides. The
        # animation group's pause is the sole delay and is retired with us.
        self._timeline.start()
        return True

    def cancel(self) -> bool:
        """Cancel a retiring generation without publishing false completion."""

        if self._cancelled or self._completed:
            return False
        self._cancelled = True
        self._timeline.stop()
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
    "QUICK_STARTUP_DESKTOP_CROSSFADE_DURATION_MS",
    "QUICK_STARTUP_REVEAL_DELAY_MS",
    "QUICK_STARTUP_REVEAL_DURATION_MS",
    "QuickStartupRevealCoordinator",
]
