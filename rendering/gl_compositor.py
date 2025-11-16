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

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from core.logging.logger import get_logger
from core.animation.types import EasingCurve
from core.animation.animator import AnimationManager
from rendering.gl_format import apply_widget_surface_format


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

        # Slide and crossfade are mutually exclusive; clear any active crossfade.
        self._crossfade = None
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
        self.update()

    def _on_slide_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        # Snap to final state: base pixmap becomes the new image, transition ends.
        if self._slide is not None:
            try:
                self._base_pixmap = self._slide.new_pixmap
            except Exception:
                pass
        self._slide = None
        self._current_anim_id = None
        self.update()
        if on_finished:
            try:
                on_finished()
            except Exception:
                logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)

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
            except Exception:
                pass
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

        if snap_to_new and new_pm is not None:
            self._base_pixmap = new_pm

        self._crossfade = None
        self._slide = None
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

            # If a slide is active, draw both images at interpolated positions.
            if self._slide is not None:
                st = self._slide
                w = target.width()
                h = target.height()

                t = max(0.0, min(1.0, st.progress))

                def lerp(a: QPoint, b: QPoint, t: float) -> QPoint:
                    return QPoint(
                        int(a.x() + (b.x() - a.x()) * t),
                        int(a.y() + (b.y() - a.y()) * t),
                    )

                old_pos = lerp(st.old_start, st.old_end, t)
                new_pos = lerp(st.new_start, st.new_end, t)

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
