"""One compositor-owned fade authority for the visualizer scene.

Why this exists
---------------

``ShadowFadeProfile`` is QWidget-oriented: it installs a
``QGraphicsOpacityEffect`` on the widget, animates it, and exposes the
instantaneous progress on a ``_shadowfade_progress`` side-channel that GPU
clients read. That was correct while ``SpotifyVisualizerWidget`` painted the
card itself.

After the single-surface migration the card and the visualizer shader are both
drawn by the display compositor, so a QWidget opacity effect cannot fade those
pixels at all. The installed result was a fade whose first half had no pixel
owner and whose second half slammed in: the effect faded a widget that painted
nothing, while the compositor's own fade input was a side-channel that could
also jump to 1.0 the moment the effect was torn down.

This module owns the replacement: **one** animation, **one** progress scalar,
consumed by every compositor-drawn visualizer layer.

Authored profile
----------------

Duration and easing are still taken from ``ShadowFadeProfile`` so the authored
1800 ms InOutCubic startup profile has exactly one definition. The authored
bars stagger - bars arrive after the card/shadow are established - is preserved
as a pure function of that same progress rather than a second animation, so the
card and the bars can never be driven by two clocks that disagree.
"""

from __future__ import annotations

import weakref
from typing import Any, Callable, Optional

from PySide6.QtCore import QEasingCurve, QVariantAnimation

from core.logging.logger import get_logger

logger = get_logger(__name__)


# Authored stagger: the bars begin only once the card/shadow have established
# themselves. Historically this lived inline in ``get_gpu_fade_factor`` and was
# applied to the QWidget effect's progress side-channel.
BARS_FADE_DELAY = 0.65


def bars_fade_from_progress(progress: float) -> float:
    """Authored bars stagger applied to the one scene fade progress.

    Pure function: no state, no second animation, no separate clock. Passing the
    same progress always yields the same bars fade, which is what makes the two
    layers provably consistent.
    """
    try:
        p = float(progress)
    except Exception:
        return 0.0
    if p <= BARS_FADE_DELAY:
        return 0.0
    if p >= 1.0:
        return 1.0
    t = (p - BARS_FADE_DELAY) / (1.0 - BARS_FADE_DELAY)
    # Slower cubic ease-in, exactly as authored.
    t = t * t * t
    return max(0.0, min(1.0, t))


def _shared_profile() -> tuple[int, Any]:
    """Return the authored (duration_ms, easing) without duplicating it."""
    from widgets.shadow_utils import ShadowFadeProfile

    try:
        duration_ms = int(ShadowFadeProfile.default_duration_ms())
    except Exception:
        duration_ms = 1800
    try:
        easing = ShadowFadeProfile.EASING
    except Exception:
        easing = QEasingCurve.Type.InOutCubic
    return max(0, duration_ms), easing


class VisualizerPresentationFade:
    """The single fade authority for compositor-owned visualizer pixels.

    Contract:

    * exactly one animation drives ``progress``;
    * ``progress`` only ever moves along the running animation or by an
      explicit ``jump_to``/``reset``; it never becomes 1.0 as a side effect of
      some other object being torn down;
    * a stale animation callback from a superseded fade is rejected by
      generation, so an interrupted fade cannot finish the new one;
    * the card fade is the progress itself and the bars fade is the authored
      stagger of that same progress.
    """

    __slots__ = (
        "__weakref__",
        "_owner_ref",
        "_anim",
        "_progress",
        "_target",
        "_generation",
        "_started",
    )

    def __init__(self, owner: Any = None) -> None:
        # ``owner`` only parents the QVariantAnimation so Qt owns its lifetime.
        # It is deliberately NOT a pixel owner and its visibility/effects are
        # never consulted here.
        #
        # The reference is weak on purpose: this object is stored ON the widget,
        # so a strong back-reference would create a Python cycle that outlives
        # the widget's C++ object and leaves a dangling wrapper behind.
        self._owner_ref = None
        if owner is not None:
            try:
                self._owner_ref = weakref.ref(owner)
            except TypeError:
                self._owner_ref = None
        self._anim: Optional[QVariantAnimation] = None
        self._progress: float = 0.0
        self._target: float = 0.0
        self._generation: int = 0
        self._started: bool = False

    # -- observation ----------------------------------------------------

    def _owner(self) -> Any:
        ref = self._owner_ref
        return ref() if ref is not None else None

    @property
    def progress(self) -> float:
        """Current authoritative fade progress in ``0.0..1.0``."""
        return self._progress

    def card_fade(self) -> float:
        """Fade for the authored card/background/border/shadow pixels."""
        return self._progress

    def bars_fade(self) -> float:
        """Fade for the visualizer shader pixels."""
        return bars_fade_from_progress(self._progress)

    def has_started(self) -> bool:
        """Whether a visible fade has been started at least once."""
        return self._started

    def is_running(self) -> bool:
        anim = self._anim
        if anim is None:
            return False
        try:
            return anim.state() == QVariantAnimation.State.Running
        except Exception:
            return False

    def is_complete(self) -> bool:
        """Whether the last requested fade has fully arrived at its target."""
        if not self._started:
            return False
        if self.is_running():
            return False
        return abs(self._progress - self._target) <= 1e-6

    # -- control --------------------------------------------------------

    def reset(self) -> None:
        """Cancel any running fade and return to fully invisible.

        Used by teardown, mode reset and generation replacement. It bumps the
        generation so an in-flight animation callback cannot resurrect the old
        fade.
        """
        self._generation += 1
        self._stop_animation()
        self._progress = 0.0
        self._target = 0.0
        self._started = False

    def jump_to(self, value: float) -> None:
        """Set progress directly (zero-duration fade paths only)."""
        self._generation += 1
        self._stop_animation()
        try:
            resolved = max(0.0, min(1.0, float(value)))
        except Exception:
            resolved = 0.0
        self._progress = resolved
        self._target = resolved
        self._started = True

    def begin_fade_in(
        self,
        *,
        duration_ms: Optional[int] = None,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> None:
        """Start the authored 0 -> 1 reveal from the current progress."""
        self._begin(1.0, duration_ms=duration_ms, on_finished=on_finished)

    def begin_fade_out(
        self,
        *,
        duration_ms: Optional[int] = None,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> None:
        """Start a 1 -> 0 hide from the current progress."""
        self._begin(0.0, duration_ms=duration_ms, on_finished=on_finished)

    # -- internals ------------------------------------------------------

    def _begin(
        self,
        target: float,
        *,
        duration_ms: Optional[int],
        on_finished: Optional[Callable[[], None]],
    ) -> None:
        shared_duration_ms, easing = _shared_profile()
        resolved_ms = shared_duration_ms if duration_ms is None else max(0, int(duration_ms))
        target = max(0.0, min(1.0, float(target)))

        # Supersede any in-flight fade before anything else, so its callbacks
        # cannot write progress after this point.
        self._generation += 1
        generation = self._generation
        self._stop_animation()
        self._target = target
        self._started = True

        if resolved_ms <= 0:
            self._progress = target
            if on_finished is not None:
                self._safe_call(on_finished)
            return

        start = self._progress
        anim = QVariantAnimation(self._owner())
        anim.setDuration(resolved_ms)
        anim.setStartValue(float(start))
        anim.setEndValue(float(target))
        try:
            anim.setEasingCurve(easing)
        except Exception:
            # Easing failure must not break the fade; the linear ramp still
            # completes at the authored duration.
            logger.debug("[SPOTIFY_VIS][FADE] Easing curve rejected", exc_info=True)

        def _on_value_changed(value: object) -> None:
            if generation != self._generation:
                return
            try:
                self._progress = max(0.0, min(1.0, float(value)))  # type: ignore[arg-type]
            except Exception:
                return

        def _on_finished() -> None:
            if generation != self._generation:
                return
            # Land exactly on the target once. There is no other route to 1.0.
            self._progress = self._target
            self._anim = None
            if on_finished is not None:
                self._safe_call(on_finished)

        anim.valueChanged.connect(_on_value_changed)
        anim.finished.connect(_on_finished)
        self._anim = anim
        anim.start()

    def _stop_animation(self) -> None:
        anim = self._anim
        self._anim = None
        if anim is None:
            return
        try:
            anim.stop()
        except Exception:
            logger.debug("[SPOTIFY_VIS][FADE] Failed to stop fade animation", exc_info=True)

    @staticmethod
    def _safe_call(callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception:
            logger.debug("[SPOTIFY_VIS][FADE] Fade completion callback failed", exc_info=True)


def ensure_presentation_fade(widget: Any) -> VisualizerPresentationFade:
    """Return the widget's fade authority, creating it on first use."""
    fade = getattr(widget, "_presentation_fade", None)
    if not isinstance(fade, VisualizerPresentationFade):
        fade = VisualizerPresentationFade(widget)
        try:
            widget._presentation_fade = fade
        except Exception:
            logger.debug("[SPOTIFY_VIS][FADE] Could not attach fade authority", exc_info=True)
    return fade
