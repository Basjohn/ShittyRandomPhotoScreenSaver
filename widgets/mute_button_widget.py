"""System-wide mute toggle button widget.

A small rounded button positioned near the media widget that toggles
the system master mute on/off. Styled to match the transport control bar.

The widget is non-interactive in Qt hit-testing terms
(``WA_TransparentForMouseEvents``); DisplayWidget routes clicks
when interaction mode is active.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QPainterPath
from PySide6.QtWidgets import QWidget

from core.logging.logger import get_logger
from core.media import system_mute
from core.threading.manager import ThreadManager
from widgets.shadow_utils import configure_overlay_widget_attributes

logger = get_logger(__name__)


class MuteButtonWidget(QWidget):
    """Small rounded mute toggle button anchored to the media widget."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._muted: bool = False
        self._available: bool = system_mute.is_available()
        self._enabled: bool = False
        self._anchor_media: Optional[QWidget] = None
        self._thread_manager: Optional[ThreadManager] = None
        self._has_faded_in: bool = False
        self._mute_poll_active: bool = False

        # Visual feedback on click
        self._feedback_alpha: float = 0.0

        # Styling (configured from media widget)
        self._bg_color: QColor = QColor(35, 35, 35, 200)
        self._border_color: QColor = QColor(255, 255, 255, 65)
        self._icon_color: QColor = QColor(255, 255, 255, 230)
        self._icon_muted_color: QColor = QColor(200, 200, 200, 180)

        # Match control bar border radius
        self._border_radius: float = 12.0
        self._outline_alpha: int = 65
        self._shadow_alpha: int = 60

        self._btn_width: int = 40
        self._btn_height: int = 36

        configure_overlay_widget_attributes(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFixedSize(self._btn_width, self._btn_height)
        self.hide()

    # ------------------------------------------------------------------
    # Public configuration
    # ------------------------------------------------------------------

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the mute button."""
        self._enabled = bool(enabled) and self._available
        if not self._enabled:
            self.hide()

    def set_thread_manager(self, tm: ThreadManager) -> None:
        """Inject the ThreadManager for async mute operations."""
        self._thread_manager = tm
        self._start_mute_poll()

    def set_anchor(self, media_widget: Optional[QWidget]) -> None:
        """Set the media widget this button anchors to."""
        self._anchor_media = media_widget

    def set_colors(
        self,
        bg: QColor,
        border: QColor,
        icon: QColor,
    ) -> None:
        """Configure visual styling to match the media card."""
        self._bg_color = QColor(bg)
        self._border_color = QColor(border)
        self._icon_color = QColor(icon)
        self.update()

    def sync_visibility_with_anchor(self) -> None:
        """Show/hide based on anchor media widget visibility and enabled state."""
        if not self._enabled or not self._available:
            self.hide()
            return
        anchor = self._anchor_media
        if anchor is None or not anchor.isVisible():
            self.hide()
            return
        if not self._has_faded_in:
            self._start_widget_fade_in(1200)
        else:
            self.show()
            self.raise_()
        self.update_position()
        self.poll_mute_state()

    def _start_widget_fade_in(self, duration_ms: int = 1200) -> None:
        """Fade the widget in using ShadowFadeProfile, matching other overlays."""
        if duration_ms <= 0:
            self.show()
            self.raise_()
            self._has_faded_in = True
            return
        try:
            from widgets.shadow_utils import ShadowFadeProfile
            ShadowFadeProfile.start_fade_in(
                self,
                None,
                has_background_frame=False,
                on_finished=lambda: setattr(self, '_has_faded_in', True),
            )
        except Exception:
            logger.debug("[MUTE_BTN] _start_widget_fade_in fallback", exc_info=True)
            self.show()
            self.raise_()
            self._has_faded_in = True

    def update_position(self) -> None:
        """Position the button relative to the anchored media widget.

        Y-axis: aligned with the control bar row inside the media card.
        X-axis: centered horizontally under the artwork panel.
        Falls back to bottom-right if layout info is unavailable.
        """
        anchor = self._anchor_media
        if anchor is None or not anchor.isVisible():
            return

        anchor_geo = anchor.geometry()

        # Try to get the control bar Y and artwork rect from the media widget
        controls_layout = None
        artwork_rect = None
        try:
            if hasattr(anchor, '_compute_controls_layout'):
                controls_layout = anchor._compute_controls_layout()
            if hasattr(anchor, '_last_artwork_rect'):
                artwork_rect = getattr(anchor, '_last_artwork_rect', None)
        except Exception:
            logger.debug("[MUTE_BTN] Layout probe failed", exc_info=True)

        if controls_layout is not None and artwork_rect is not None:
            row_rect = controls_layout.get("row_rect")
            if row_rect is not None:
                # Y: same as control bar top, in parent coordinates
                y = anchor_geo.top() + row_rect.top() + (row_rect.height() - self._btn_height) // 2
                # X: centered under artwork panel, in parent coordinates
                art_center_x = anchor_geo.left() + artwork_rect.left() + artwork_rect.width() // 2
                x = art_center_x - self._btn_width // 2
            else:
                x, y = self._fallback_position(anchor_geo)
        else:
            x, y = self._fallback_position(anchor_geo)

        parent = self.parent()
        if parent is not None:
            max_y = parent.height() - self._btn_height - 4
            y = min(y, max_y)
            x = max(0, min(x, parent.width() - self._btn_width))
        self.move(x, y)

    def _fallback_position(self, anchor_geo):
        """Fallback: position below the media card, right-aligned."""
        margins = self._anchor_media.contentsMargins() if hasattr(self._anchor_media, 'contentsMargins') else None
        right_margin = margins.right() if margins else 8
        x = anchor_geo.right() - right_margin - self._btn_width
        y = anchor_geo.bottom() + 6
        return x, y

    # ------------------------------------------------------------------
    # Periodic system mute polling (30s interval)
    # ------------------------------------------------------------------

    _MUTE_POLL_INTERVAL_S: float = 30.0

    def _start_mute_poll(self) -> None:
        """Start periodic mute state polling via ThreadManager."""
        if self._mute_poll_active or not self._available:
            return
        tm = self._thread_manager
        if tm is None:
            return
        self._mute_poll_active = True
        self._schedule_next_poll()

    def _stop_mute_poll(self) -> None:
        """Cancel periodic mute polling."""
        self._mute_poll_active = False

    def _schedule_next_poll(self) -> None:
        """Schedule the next poll using ThreadManager.single_shot (non-blocking)."""
        if not self._mute_poll_active:
            return
        try:
            delay_ms = int(self._MUTE_POLL_INTERVAL_S * 1000)
            ThreadManager.single_shot(delay_ms, self._poll_mute_tick)
        except Exception:
            logger.debug("[MUTE_BTN] Failed to schedule mute poll", exc_info=True)
            self._mute_poll_active = False

    def _poll_mute_tick(self) -> None:
        """Called on UI thread via single_shot: read mute state and reschedule."""
        if not self._mute_poll_active:
            return
        state = system_mute.get_mute()
        if state is not None:
            self._apply_mute_state(state)
        self._schedule_next_poll()

    def cleanup(self) -> None:
        """Stop polling and clean up resources."""
        self._stop_mute_poll()

    # ------------------------------------------------------------------
    # Interaction (called by DisplayWidget)
    # ------------------------------------------------------------------

    def handle_click(self) -> bool:
        """Toggle system mute. Returns True if handled.

        Runs synchronously on the UI thread because pycaw COM objects
        are apartment-threaded — they must be called from the same
        thread that acquired them (the main/UI thread).
        """
        if not self._enabled or not self._available:
            logger.debug("[MUTE_BTN] handle_click blocked: enabled=%s available=%s",
                         self._enabled, self._available)
            return False

        logger.debug("[MUTE_BTN] handle_click: toggling mute (current=%s)", self._muted)
        result = system_mute.toggle_mute()
        if result is not None:
            self._muted = result
            logger.debug("[MUTE_BTN] mute toggled to %s", result)
        else:
            logger.debug("[MUTE_BTN] toggle_mute returned None")

        self._trigger_feedback()
        self.update()
        return True

    def _trigger_feedback(self) -> None:
        """Start a visual click-flash feedback animation using QVariantAnimation."""
        # Stop any running feedback animation
        old_anim = getattr(self, '_feedback_anim', None)
        if old_anim is not None:
            try:
                old_anim.stop()
                old_anim.deleteLater()
            except Exception:
                logger.debug("[MUTE_BTN] Old animation cleanup failed", exc_info=True)
            self._feedback_anim = None

        self._feedback_alpha = 1.0
        self.update()
        try:
            from PySide6.QtCore import QVariantAnimation, QEasingCurve
            anim = QVariantAnimation(self)
            anim.setDuration(350)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.valueChanged.connect(lambda val: self._on_feedback_tick(val))
            anim.finished.connect(lambda: self._on_feedback_done())
            self._feedback_anim = anim
            anim.start()
        except Exception:
            logger.debug("[MUTE_BTN] Feedback animation failed", exc_info=True)
            self._feedback_alpha = 0.0

    def _on_feedback_tick(self, val: float) -> None:
        self._feedback_alpha = max(0.0, float(val))
        self.update()

    def _on_feedback_done(self) -> None:
        self._feedback_alpha = 0.0
        self.update()

    def _apply_mute_state(self, new_state: bool) -> None:
        """Apply mute state on UI thread."""
        changed = (new_state != self._muted)
        self._muted = new_state
        if changed:
            self._trigger_feedback()
        self.update()

    def poll_mute_state(self) -> None:
        """Poll the current system mute state (call periodically)."""
        if not self._enabled or not self._available:
            return
        state = system_mute.get_mute()
        if state is not None and state != self._muted:
            self._muted = state
            self._trigger_feedback()
            self.update()

    def hit_test(self, global_pos) -> bool:
        """Return True if the global position is within this button."""
        if not self.isVisible():
            return False
        local = self.mapFromGlobal(global_pos)
        return self.rect().contains(local)

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        if not self._enabled or not self._available:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        radius = self._border_radius

        # Background with gradient matching control bar
        from PySide6.QtGui import QLinearGradient
        base = QColor(self._bg_color)
        top_c = QColor(base)
        bot_c = QColor(base)
        top_c.setAlpha(min(255, int(base.alpha() * 0.95) + 30))
        bot_c.setAlpha(min(255, int(base.alpha() * 0.85)))
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0.0, top_c)
        gradient.setColorAt(1.0, bot_c)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(gradient)
        p.drawRoundedRect(rect, radius, radius)

        # Inner shadow (matches control bar)
        p.setPen(QColor(0, 0, 0, self._shadow_alpha))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect.adjusted(2, 2, -2, -2), radius - 1, radius - 1)

        # Outer outline (matches control bar)
        outline_pen = QPen(QColor(255, 255, 255, self._outline_alpha), 1.25)
        p.setPen(outline_pen)
        p.drawRoundedRect(rect, radius, radius)

        # Draw monochrome speaker + sound wave icon
        self._paint_speaker_icon(p, rect)

        # Click feedback flash overlay
        if self._feedback_alpha > 0.01:
            flash_alpha = int(min(255, self._feedback_alpha * 120))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, flash_alpha))
            p.drawRoundedRect(rect, radius, radius)

        p.end()

    def _paint_speaker_icon(self, p: QPainter, rect: QRectF) -> None:
        """Draw a monochrome speaker icon with sound waves (or crossed out if muted)."""
        icon_color = self._icon_muted_color if self._muted else self._icon_color
        cx = rect.center().x()
        cy = rect.center().y()
        scale = min(rect.width(), rect.height()) * 0.32

        p.save()
        p.translate(cx, cy)

        # Speaker body (left-pointing trapezoid + rectangle)
        speaker_path = QPainterPath()
        # Small rectangle (speaker grille)
        sx = -scale * 0.55
        speaker_path.moveTo(sx, -scale * 0.18)
        speaker_path.lineTo(sx + scale * 0.22, -scale * 0.18)
        # Cone flare
        speaker_path.lineTo(sx + scale * 0.55, -scale * 0.45)
        speaker_path.lineTo(sx + scale * 0.55, scale * 0.45)
        speaker_path.lineTo(sx + scale * 0.22, scale * 0.18)
        speaker_path.lineTo(sx, scale * 0.18)
        speaker_path.closeSubpath()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(icon_color)
        p.drawPath(speaker_path)

        if not self._muted:
            # Sound waves (arcs going right)
            wave_pen = QPen(icon_color, max(1.2, scale * 0.14))
            wave_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(wave_pen)
            p.setBrush(Qt.BrushStyle.NoBrush)

            wave_cx = sx + scale * 0.65
            for i, r in enumerate([scale * 0.35, scale * 0.6]):
                arc_rect = QRectF(wave_cx - r, -r, r * 2, r * 2)
                alpha = 225 - (i * 10) if self._icon_color.alpha() > 100 else 180
                wave_color = QColor(icon_color)
                wave_color.setAlpha(max(80, alpha - i * 40))
                wave_pen_i = QPen(wave_color, max(1.2, scale * 0.14))
                wave_pen_i.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(wave_pen_i)
                # Draw arc: angles in 1/16th degree, -40 to +40 degrees
                p.drawArc(arc_rect, -40 * 16, 80 * 16)
        else:
            # Muted: draw diagonal cross-out line
            cross_pen = QPen(icon_color, max(1.5, scale * 0.16))
            cross_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(cross_pen)
            p.drawLine(
                QPointF(-scale * 0.15, -scale * 0.5),
                QPointF(scale * 0.55, scale * 0.5),
            )

        p.restore()
