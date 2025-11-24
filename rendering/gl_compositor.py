"""Single OpenGL compositor widget for DisplayWidget.

This module introduces a single per-display GL compositor that is responsible
for drawing the base image and GL-backed transitions. The intent is to replace
per-transition QOpenGLWidget overlays with a single GL surface that owns the
composition, reducing DWM/stacking complexity and flicker on Windows.

Initial implementation focuses on a GPU-backed Crossfade equivalent. Other
transitions (Slide, Wipe, Block Puzzle Flip, Blinds) can be ported onto this
compositor over time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Callable
import time

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QPainter, QPixmap, QRegion
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from core.logging.logger import get_logger
from core.animation.types import EasingCurve
from core.animation.animator import AnimationManager
from rendering.gl_format import apply_widget_surface_format
from transitions.wipe_transition import WipeDirection, _compute_wipe_region


logger = get_logger(__name__)


@dataclass
class CrossfadeState:
    """State for a compositor-driven crossfade transition."""

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    progress: float = 0.0  # 0..1


@dataclass
class SlideState:
    """State for a compositor-driven slide transition."""

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    old_start: QPoint
    old_end: QPoint
    new_start: QPoint
    new_end: QPoint
    progress: float = 0.0  # 0..1


@dataclass
class WipeState:
    """State for a compositor-driven wipe transition."""

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    direction: WipeDirection
    progress: float = 0.0  # 0..1


@dataclass
class BlockFlipState:
    """State for a compositor-driven block puzzle flip transition.

    The detailed per-block progression is managed by the controller; the
    compositor only needs the reveal region to clip the new pixmap.
    """

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    region: Optional[QRegion] = None
    progress: float = 0.0  # 0..1


@dataclass
class BlindsState:
    """State for a compositor-driven blinds transition.

    Like BlockFlip, the controller owns per-slat progression and provides an
    aggregate reveal region; the compositor only clips the new pixmap.
    """

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    region: Optional[QRegion] = None
    progress: float = 0.0  # 0..1


@dataclass
class DiffuseState:
    """State for a compositor-driven diffuse transition.

    The controller owns per-cell progression and provides an aggregate reveal
    region; the compositor only clips the new pixmap.
    """

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    region: Optional[QRegion] = None
    progress: float = 0.0  # 0..1


class GLCompositorWidget(QOpenGLWidget):
    """Single GL compositor that renders the base image and transitions.

    This widget is intended to be created as a single child of DisplayWidget,
    covering its full client area in borderless fullscreen mode. Transitions
    are driven externally (via AnimationManager); the compositor simply
    renders according to the current state.
    """

    def __init__(self, parent) -> None:
        super().__init__(parent)
        prefs = apply_widget_surface_format(self, reason="gl_compositor")
        self._surface_prefs = prefs

        # Avoid system background clears and rely entirely on our paintGL.
        try:
            self.setAutoFillBackground(False)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception:
            pass
        try:
            self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.NoPartialUpdate)
        except Exception:
            pass

        self._base_pixmap: Optional[QPixmap] = None
        self._crossfade: Optional[CrossfadeState] = None
        self._slide: Optional[SlideState] = None
        self._wipe: Optional[WipeState] = None
        self._blockflip: Optional[BlockFlipState] = None
        self._blinds: Optional[BlindsState] = None
        self._diffuse: Optional[DiffuseState] = None

        # Profiling for compositor-driven slide transitions (Route3 §6.4).
        # Metrics are logged with the "[PERF] [GL COMPOSITOR]" tag so
        # production builds can grep and gate/strip this telemetry if needed.
        self._slide_profile_start_ts: Optional[float] = None
        self._slide_profile_last_ts: Optional[float] = None
        self._slide_profile_frame_count: int = 0
        self._slide_profile_min_dt: float = 0.0
        self._slide_profile_max_dt: float = 0.0
        self._wipe_profile_start_ts: Optional[float] = None
        self._wipe_profile_last_ts: Optional[float] = None
        self._wipe_profile_frame_count: int = 0
        self._wipe_profile_min_dt: float = 0.0
        self._wipe_profile_max_dt: float = 0.0

        # Animation plumbing: compositor does not own AnimationManager, but we
        # keep the current animation id so the caller can cancel if needed.
        self._animation_manager: Optional[AnimationManager] = None
        self._current_anim_id: Optional[str] = None
        # Default easing is QUAD_IN_OUT; callers can override per-transition.
        self._current_easing: EasingCurve = EasingCurve.QUAD_IN_OUT

    # ------------------------------------------------------------------
    # Public API used by DisplayWidget / transitions
    # ------------------------------------------------------------------

    def set_base_pixmap(self, pixmap: Optional[QPixmap]) -> None:
        """Set the base image when no transition is active."""
        self._base_pixmap = pixmap
        # If no crossfade is active, repaint immediately.
        if self._crossfade is None:
            self.update()

    def start_crossfade(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a crossfade between two pixmaps using the compositor.

        This replaces the old per-transition `_GLFadeWidget`. The caller is
        responsible for ensuring that `animation_manager` lives at least as
        long as the transition.
        """
        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for crossfade")
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately")
            self._crossfade = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Crossfade and slide are mutually exclusive; clear any active slide.
        self._slide = None
        self._crossfade = CrossfadeState(old_pixmap=old_pixmap, new_pixmap=new_pixmap, progress=0.0)
        self._animation_manager = animation_manager
        self._current_easing = easing

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_crossfade_update,
            on_complete=lambda: self._on_crossfade_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_wipe(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        direction: WipeDirection,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a wipe between two pixmaps using the compositor.

        The caller is responsible for providing the wipe direction; geometry is
        derived from the widget rect and kept in sync with the CPU Wipe
        transition via the shared `_compute_wipe_region` helper.
        """

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for wipe")
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (wipe)")
            self._crossfade = None
            self._slide = None
            self._wipe = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Wipe is mutually exclusive with crossfade and slide.
        self._crossfade = None
        self._slide = None
        self._wipe = WipeState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            direction=direction,
            progress=0.0,
        )
        self._animation_manager = animation_manager
        self._current_easing = easing

        self._wipe_profile_start_ts = time.time()
        self._wipe_profile_last_ts = None
        self._wipe_profile_frame_count = 0
        self._wipe_profile_min_dt = 0.0
        self._wipe_profile_max_dt = 0.0

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_wipe_update,
            on_complete=lambda: self._on_wipe_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_slide(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        old_start: QPoint,
        old_end: QPoint,
        new_start: QPoint,
        new_end: QPoint,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a slide between two pixmaps using the compositor.

        The caller is responsible for providing start/end positions that
        correspond to the desired slide direction and widget geometry.
        """

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for slide")
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (slide)")
            self._crossfade = None
            self._slide = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Slide and crossfade/wipe are mutually exclusive; clear any active crossfade/wipe.
        self._crossfade = None
        self._wipe = None
        self._slide = SlideState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            old_start=old_start,
            old_end=old_end,
            new_start=new_start,
            new_end=new_end,
            progress=0.0,
        )
        self._animation_manager = animation_manager
        self._current_easing = easing

        # Reset slide profiling state for this transition.
        self._slide_profile_start_ts = time.time()
        self._slide_profile_last_ts = None
        self._slide_profile_frame_count = 0
        self._slide_profile_min_dt = 0.0
        self._slide_profile_max_dt = 0.0

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_slide_update,
            on_complete=lambda: self._on_slide_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_block_flip(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        update_callback: Callable[[float], None],
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a block puzzle flip using the compositor.

        The caller owns per-block timing and progression and must update the
        reveal region via :meth:`set_blockflip_region` from the provided
        ``update_callback``.
        """

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for block flip")
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (block flip)")
            self._crossfade = None
            self._slide = None
            self._wipe = None
            self._blockflip = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Block flip is mutually exclusive with other transitions.
        self._crossfade = None
        self._slide = None
        self._wipe = None
        self._blockflip = BlockFlipState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            region=None,
        )
        self._animation_manager = animation_manager
        self._current_easing = easing

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=update_callback,
            on_complete=lambda: self._on_blockflip_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_diffuse(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        update_callback: Callable[[float], None],
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a diffuse reveal using the compositor.

        The caller owns per-cell timing/geometry and must update the reveal
        region via :meth:`set_diffuse_region` from the provided
        ``update_callback``.
        """

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for diffuse")
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (diffuse)")
            self._crossfade = None
            self._slide = None
            self._wipe = None
            self._blockflip = None
            self._blinds = None
            self._diffuse = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Diffuse is mutually exclusive with other transitions.
        self._crossfade = None
        self._slide = None
        self._wipe = None
        self._blockflip = None
        self._blinds = None
        self._diffuse = DiffuseState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            region=None,
        )
        self._animation_manager = animation_manager
        self._current_easing = easing

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=update_callback,
            on_complete=lambda: self._on_diffuse_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_blinds(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        update_callback: Callable[[float], None],
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a blinds reveal using the compositor.

        The caller owns per-slat timing/geometry and must update the reveal
        region via :meth:`set_blinds_region` from the provided
        ``update_callback``.
        """

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for blinds")
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (blinds)")
            self._crossfade = None
            self._slide = None
            self._wipe = None
            self._blockflip = None
            self._blinds = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Blinds is mutually exclusive with other transitions.
        self._crossfade = None
        self._slide = None
        self._wipe = None
        self._blockflip = None
        self._blinds = BlindsState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            region=None,
        )
        self._animation_manager = animation_manager
        self._current_easing = easing

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=update_callback,
            on_complete=lambda: self._on_blinds_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    # ------------------------------------------------------------------
    # Animation callbacks
    # ------------------------------------------------------------------

    def _on_crossfade_update(self, progress: float) -> None:
        if self._crossfade is None:
            return
        # Clamp and store progress
        p = max(0.0, min(1.0, float(progress)))
        self._crossfade.progress = p
        self.update()

    def _on_crossfade_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        # Snap to final state: base pixmap becomes the new image, transition ends.
        if self._crossfade is not None:
            try:
                self._base_pixmap = self._crossfade.new_pixmap
            except Exception:
                pass
        self._crossfade = None
        self._current_anim_id = None
        self.update()
        if on_finished:
            try:
                on_finished()
            except Exception:
                logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)

    def _on_slide_update(self, progress: float) -> None:
        if self._slide is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._slide.progress = p

        # Profiling: track frame timing for compositor-driven slide.
        now = time.time()
        if self._slide_profile_start_ts is None:
            self._slide_profile_start_ts = now
        if self._slide_profile_last_ts is not None:
            dt = now - self._slide_profile_last_ts
            if dt > 0.0:
                if self._slide_profile_min_dt == 0.0 or dt < self._slide_profile_min_dt:
                    self._slide_profile_min_dt = dt
                if dt > self._slide_profile_max_dt:
                    self._slide_profile_max_dt = dt
        self._slide_profile_last_ts = now
        self._slide_profile_frame_count += 1

        self.update()

    def _on_slide_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Handle completion of compositor-driven slide transitions.

        This callback may fire after the underlying QOpenGLWidget has been
        deleted (e.g. during test teardown). All QWidget/QObject calls are
        therefore wrapped defensively to avoid RuntimeError bubbling out of
        the Qt event loop.
        """

        try:
            # Emit a concise profiling summary for slide transitions.
            # The log line is tagged with "[PERF] [GL COMPOSITOR]" for easy
            # discovery/disablement when preparing production builds.
            try:
                if (
                    self._slide_profile_start_ts is not None
                    and self._slide_profile_last_ts is not None
                    and self._slide_profile_frame_count > 0
                ):
                    elapsed = max(0.0, self._slide_profile_last_ts - self._slide_profile_start_ts)
                    if elapsed > 0.0:
                        duration_ms = elapsed * 1000.0
                        avg_fps = self._slide_profile_frame_count / elapsed
                        min_dt_ms = self._slide_profile_min_dt * 1000.0 if self._slide_profile_min_dt > 0.0 else 0.0
                        max_dt_ms = self._slide_profile_max_dt * 1000.0 if self._slide_profile_max_dt > 0.0 else 0.0
                        logger.info(
                            "[PERF] [GL COMPOSITOR] Slide metrics: duration=%.1fms, frames=%d, "
                            "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, size=%dx%d",
                            duration_ms,
                            self._slide_profile_frame_count,
                            avg_fps,
                            min_dt_ms,
                            max_dt_ms,
                            self.width(),
                            self.height(),
                        )
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Slide metrics logging failed: %s", e, exc_info=True)

            # Reset profiling state.
            self._slide_profile_start_ts = None
            self._slide_profile_last_ts = None
            self._slide_profile_frame_count = 0
            self._slide_profile_min_dt = 0.0
            self._slide_profile_max_dt = 0.0

            # Snap to final state: base pixmap becomes the new image, transition ends.
            if self._slide is not None:
                try:
                    self._base_pixmap = self._slide.new_pixmap
                except Exception:
                    pass
            self._slide = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Slide complete update failed (likely after deletion): %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            # Final safeguard so no exception escapes the Qt event loop.
            logger.debug("[GL COMPOSITOR] Slide complete handler failed: %s", e, exc_info=True)

    def _on_wipe_update(self, progress: float) -> None:
        if self._wipe is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._wipe.progress = p

        now = time.time()
        if self._wipe_profile_start_ts is None:
            self._wipe_profile_start_ts = now
        if self._wipe_profile_last_ts is not None:
            dt = now - self._wipe_profile_last_ts
            if dt > 0.0:
                if self._wipe_profile_min_dt == 0.0 or dt < self._wipe_profile_min_dt:
                    self._wipe_profile_min_dt = dt
                if dt > self._wipe_profile_max_dt:
                    self._wipe_profile_max_dt = dt
        self._wipe_profile_last_ts = now
        self._wipe_profile_frame_count += 1
        self.update()

    def _on_wipe_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Handle completion of compositor-driven wipe transitions."""

        try:
            try:
                if (
                    self._wipe_profile_start_ts is not None
                    and self._wipe_profile_last_ts is not None
                    and self._wipe_profile_frame_count > 0
                ):
                    elapsed = max(0.0, self._wipe_profile_last_ts - self._wipe_profile_start_ts)
                    if elapsed > 0.0:
                        duration_ms = elapsed * 1000.0
                        avg_fps = self._wipe_profile_frame_count / elapsed
                        min_dt_ms = self._wipe_profile_min_dt * 1000.0 if self._wipe_profile_min_dt > 0.0 else 0.0
                        max_dt_ms = self._wipe_profile_max_dt * 1000.0 if self._wipe_profile_max_dt > 0.0 else 0.0
                        logger.info(
                            "[PERF] [GL COMPOSITOR] Wipe metrics: duration=%.1fms, frames=%d, "
                            "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, size=%dx%d",
                            duration_ms,
                            self._wipe_profile_frame_count,
                            avg_fps,
                            min_dt_ms,
                            max_dt_ms,
                            self.width(),
                            self.height(),
                        )
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Wipe metrics logging failed: %s", e, exc_info=True)

            self._wipe_profile_start_ts = None
            self._wipe_profile_last_ts = None
            self._wipe_profile_frame_count = 0
            self._wipe_profile_min_dt = 0.0
            self._wipe_profile_max_dt = 0.0

            # Snap to final state: base pixmap becomes the new image, transition ends.
            if self._wipe is not None:
                try:
                    self._base_pixmap = self._wipe.new_pixmap
                except Exception:
                    pass
            self._wipe = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Wipe complete update failed (likely after deletion): %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Wipe complete handler failed: %s", e, exc_info=True)

    def _on_blockflip_update(self, progress: float) -> None:
        if self._blockflip is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._blockflip.progress = p
        self.update()

    def _on_blockflip_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven block flip transitions."""

        try:
            # Snap to final state: base pixmap becomes the new image, transition ends.
            if self._blockflip is not None:
                try:
                    self._base_pixmap = self._blockflip.new_pixmap
                except Exception:
                    pass
            self._blockflip = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Blockflip complete update failed (likely after deletion): %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Blockflip complete handler failed: %s", e, exc_info=True)

    def _on_diffuse_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven diffuse transitions."""

        try:
            if self._diffuse is not None:
                try:
                    self._base_pixmap = self._diffuse.new_pixmap
                except Exception:
                    pass
            self._diffuse = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Diffuse complete update failed (likely after deletion): %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Diffuse complete handler failed: %s", e, exc_info=True)

    def _on_blinds_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven blinds transitions."""

        try:
            if self._blinds is not None:
                try:
                    self._base_pixmap = self._blinds.new_pixmap
                except Exception:
                    pass
            self._blinds = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Blinds complete update failed (likely after deletion): %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Blinds complete handler failed: %s", e, exc_info=True)

    def set_blockflip_region(self, region: Optional[QRegion]) -> None:
        """Update the reveal region for an in-flight block flip transition."""

        if self._blockflip is None:
            return
        self._blockflip.region = region
        self.update()

    def set_blinds_region(self, region: Optional[QRegion]) -> None:
        """Update the reveal region for an in-flight blinds transition."""

        if self._blinds is None:
            return
        self._blinds.region = region
        self.update()

    def set_diffuse_region(self, region: Optional[QRegion]) -> None:
        """Update the reveal region for an in-flight diffuse transition."""

        if self._diffuse is None:
            return
        self._diffuse.region = region
        self.update()

    def cancel_current_transition(self, snap_to_new: bool = True) -> None:
        """Cancel any active compositor-driven transition.

        If ``snap_to_new`` is True, the compositor's base pixmap is updated to
        the new image of the in-flight transition (if any) before clearing
        state. This is used by transitions that want to avoid visual pops when
        interrupted.
        """

        if self._animation_manager and self._current_anim_id:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Failed to cancel current animation: %s", e, exc_info=True)
        self._current_anim_id = None

        new_pm: Optional[QPixmap] = None
        if self._crossfade is not None:
            try:
                new_pm = self._crossfade.new_pixmap
            except Exception:
                new_pm = None
        elif self._slide is not None:
            try:
                new_pm = self._slide.new_pixmap
            except Exception:
                new_pm = None
        elif self._wipe is not None:
            try:
                new_pm = self._wipe.new_pixmap
            except Exception:
                new_pm = None
        elif self._blockflip is not None:
            try:
                new_pm = self._blockflip.new_pixmap
            except Exception:
                new_pm = None
        elif self._blinds is not None:
            try:
                new_pm = self._blinds.new_pixmap
            except Exception:
                new_pm = None
        elif self._diffuse is not None:
            try:
                new_pm = self._diffuse.new_pixmap
            except Exception:
                new_pm = None

        if snap_to_new and new_pm is not None:
            self._base_pixmap = new_pm

        self._crossfade = None
        self._slide = None
        self._wipe = None
        self._blockflip = None
        self._blinds = None
        self._diffuse = None
        self.update()

    # ------------------------------------------------------------------
    # QOpenGLWidget hooks
    # ------------------------------------------------------------------

    def initializeGL(self) -> None:  # type: ignore[override]
        try:
            ctx = self.context()
            if ctx is not None:
                fmt = ctx.format()
                logger.info(
                    "[GL COMPOSITOR] Context initialized: version=%s.%s, swap=%s, interval=%s",
                    fmt.majorVersion(),
                    fmt.minorVersion(),
                    fmt.swapBehavior(),
                    fmt.swapInterval(),
                )
        except Exception:
            logger.debug("[GL COMPOSITOR] initializeGL failed", exc_info=True)

    def paintGL(self) -> None:  # type: ignore[override]
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            target = self.rect()

            # If a block flip is active, draw old fully and new clipped to the
            # aggregated reveal region.
            if self._blockflip is not None:
                st = self._blockflip
                # Draw old image fully.
                if st.old_pixmap and not st.old_pixmap.isNull():
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.old_pixmap)

                # Clip and draw new image inside the reveal region.
                if st.new_pixmap and not st.new_pixmap.isNull() and st.region is not None and not st.region.isEmpty():
                    painter.save()
                    painter.setClipRegion(st.region)
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.new_pixmap)
                    painter.restore()
                return

            # If a blinds transition is active, draw old fully and new clipped
            # to the blinds reveal region.
            if self._blinds is not None:
                st = self._blinds
                if st.old_pixmap and not st.old_pixmap.isNull():
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.old_pixmap)

                if st.new_pixmap and not st.new_pixmap.isNull() and st.region is not None and not st.region.isEmpty():
                    painter.save()
                    painter.setClipRegion(st.region)
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.new_pixmap)
                    painter.restore()
                return

            if self._diffuse is not None:
                st = self._diffuse
                if st.old_pixmap and not st.old_pixmap.isNull():
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.old_pixmap)

                if st.new_pixmap and not st.new_pixmap.isNull() and st.region is not None and not st.region.isEmpty():
                    painter.save()
                    painter.setClipRegion(st.region)
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.new_pixmap)
                    painter.restore()
                return

            # If a wipe is active, draw old fully and new clipped to the wipe region.
            if self._wipe is not None:
                st = self._wipe
                w = target.width()
                h = target.height()
                t = max(0.0, min(1.0, st.progress))

                # Draw old image fully.
                if st.old_pixmap and not st.old_pixmap.isNull():
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.old_pixmap)

                # Clip and draw new according to wipe direction.
                if st.new_pixmap and not st.new_pixmap.isNull():
                    region = _compute_wipe_region(st.direction, w, h, t)
                    if not region.isEmpty():
                        painter.save()
                        painter.setClipRegion(region)
                        painter.setOpacity(1.0)
                        painter.drawPixmap(target, st.new_pixmap)
                        painter.restore()
                return

            # If a slide is active, draw both images at interpolated positions.
            if self._slide is not None:
                st = self._slide
                w = target.width()
                h = target.height()

                t = max(0.0, min(1.0, st.progress))
                old_pos = QPoint(
                    int(st.old_start.x() + (st.old_end.x() - st.old_start.x()) * t),
                    int(st.old_start.y() + (st.old_end.y() - st.old_start.y()) * t),
                )
                new_pos = QPoint(
                    int(st.new_start.x() + (st.new_end.x() - st.new_start.x()) * t),
                    int(st.new_start.y() + (st.new_end.y() - st.new_start.y()) * t),
                )

                if st.old_pixmap and not st.old_pixmap.isNull():
                    painter.setOpacity(1.0)
                    old_rect = QRect(old_pos.x(), old_pos.y(), w, h)
                    painter.drawPixmap(old_rect, st.old_pixmap)
                if st.new_pixmap and not st.new_pixmap.isNull():
                    painter.setOpacity(1.0)
                    new_rect = QRect(new_pos.x(), new_pos.y(), w, h)
                    painter.drawPixmap(new_rect, st.new_pixmap)
                return

            # If a crossfade is active, draw old + new with interpolated opacity.
            if self._crossfade is not None:
                cf = self._crossfade
                if cf.old_pixmap and not cf.old_pixmap.isNull():
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, cf.old_pixmap)
                if cf.new_pixmap and not cf.new_pixmap.isNull():
                    painter.setOpacity(cf.progress)
                    painter.drawPixmap(target, cf.new_pixmap)
                return

            # No active transition -> draw base pixmap if present.
            if self._base_pixmap is not None and not self._base_pixmap.isNull():
                painter.setOpacity(1.0)
                painter.drawPixmap(target, self._base_pixmap)
            else:
                # As a last resort, fill black.
                painter.fillRect(target, Qt.GlobalColor.black)
        finally:
            painter.end()
