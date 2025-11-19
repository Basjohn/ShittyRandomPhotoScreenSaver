"""Media/Now Playing widget for screensaver overlay.

This widget displays the current media playback state (track title,
artist, album) using the centralized media controller abstraction.

It is intentionally read-only and non-interactive in this first
iteration; transport controls will be layered on later and gated
behind explicit user intent (hard-exit/Ctrl-hold).
"""
from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QLabel, QWidget, QGraphicsOpacityEffect
from PySide6.QtCore import QTimer, Qt, Signal, QVariantAnimation, QEasingCurve, QRect
from PySide6.QtGui import QFont, QColor, QPixmap, QPainter, QPainterPath, QFontMetrics

from core.logging.logger import get_logger
from core.media.media_controller import (
    BaseMediaController,
    MediaPlaybackState,
    MediaTrackInfo,
    create_media_controller,
)
from core.threading.manager import ThreadManager

logger = get_logger(__name__)


class MediaPosition(Enum):
    """Media widget position on screen (corner positions)."""

    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


class MediaWidget(QLabel):
    """Media widget for displaying current playback information.

    Features:
    - Polls a centralized media controller for current track info
    - Shows playback state (playing/paused), title, artist, album
    - Configurable position, font, colors, and background frame
    - Non-interactive (transparent to mouse) for screensaver safety
    """

    media_updated = Signal(dict)  # Emits dict(MediaTrackInfo) when refreshed

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        position: MediaPosition = MediaPosition.BOTTOM_LEFT,
        controller: Optional[BaseMediaController] = None,
    ) -> None:
        super().__init__(parent)

        self._position = position
        self._controller: BaseMediaController = controller or create_media_controller()

        self._update_timer: Optional[QTimer] = None
        self._enabled = False
        self._thread_manager = None
        self._refresh_in_flight = False

        # Styling defaults (mirrors general widget style)
        self._font_family = "Segoe UI"
        self._font_size = 20
        self._text_color = QColor(255, 255, 255, 230)
        self._margin = 20

        # Background frame settings
        self._show_background = False
        self._bg_opacity = 0.9
        self._bg_color = QColor(64, 64, 64, int(255 * self._bg_opacity))
        self._bg_border_width = 2
        self._bg_border_color = QColor(128, 128, 128, 200)

        # Album artwork state (optional)
        self._artwork_pixmap: Optional[QPixmap] = None
        # Default artwork size (logical pixels); overridable via settings.
        self._artwork_size: int = 200
        self._artwork_opacity: float = 1.0
        self._artwork_anim: Optional[QVariantAnimation] = None

        # Artwork border behaviour
        self._rounded_artwork_border: bool = True

        # Layout/controls behaviour
        self._show_controls: bool = True

        # Widget-level fade effect for startup and track changes
        self._widget_opacity_effect: Optional[QGraphicsOpacityEffect] = None
        self._widget_fade_anim: Optional[QVariantAnimation] = None

        # Optional Spotify-style brand logo used when album artwork is absent.
        self._brand_pixmap: Optional[QPixmap] = self._load_brand_pixmap()

        # Cached header logo metrics so paintEvent can align the Spotify glyph
        # with the rich-text SPOTIFY header.
        self._header_logo_size: int = 0
        self._header_logo_margin: int = 0
        self._header_font_pt: int = self._font_size

        # Cache of last track for diagnostics / interaction
        self._last_info: Optional[MediaTrackInfo] = None

        # One-shot flag so we only log the first paintEvent geometry.
        self._paint_debug_logged = False

        self._setup_ui()

        logger.debug("MediaWidget created (position=%s)", position.value)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        # Align content to the top-left so the header/logo sit close to the
        # top edge rather than vertically centered in the card.
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        try:
            # Non-interactive by default; screensaver interaction is gated elsewhere.
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception:
            pass

        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)
        self.setFont(font)
        self.setWordWrap(True)

        # Base contents margins; _update_display() will tighten these once we
        # know the artwork size, but start with a modest frame.
        self.setContentsMargins(24, 12, 12, 12)

        # Ensure a reasonable default footprint before artwork/metadata arrive.
        self.setMinimumWidth(600)
        self.setMinimumHeight(220)

        self._update_stylesheet()

        # Install a graphics opacity effect so we can fade the entire widget
        # in on startup / track changes without affecting siblings.
        try:
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(0.0)
            self.setGraphicsEffect(effect)
            self._widget_opacity_effect = effect
        except Exception:
            self._widget_opacity_effect = None
        self.hide()

    def start(self) -> None:
        """Begin polling media controller and showing widget."""

        if self._enabled:
            logger.warning("[FALLBACK] Media widget already running")
            return

        self._enabled = True
        # Start the polling timer and trigger an immediate refresh. When a
        # ThreadManager is available we go straight to the async path so
        # WinRT/GSMTC calls never block the UI thread on startup.
        self._ensure_timer()
        if self._thread_manager is not None:
            self._refresh_async()
        else:
            self._refresh()
        logger.info("Media widget started")

    def stop(self) -> None:
        """Stop polling and hide widget."""

        if not self._enabled:
            return

        self._enabled = False
        if self._update_timer is not None:
            try:
                self._update_timer.stop()
                self._update_timer.deleteLater()
            except RuntimeError:
                pass
            self._update_timer = None

        self.hide()
        logger.debug("Media widget stopped")

    def is_running(self) -> bool:
        return self._enabled

    def cleanup(self) -> None:
        """Clean up resources (called from DisplayWidget)."""

        logger.debug("Cleaning up media widget")
        self.stop()

    def set_thread_manager(self, thread_manager) -> None:
        self._thread_manager = thread_manager

    # ------------------------------------------------------------------
    # Position & layout
    # ------------------------------------------------------------------
    def _ensure_timer(self) -> None:
        if self._update_timer is not None:
            return
        timer = QTimer(self)
        timer.setSingleShot(False)
        timer.setInterval(1500)  # 1.5s poll
        timer.timeout.connect(self._refresh)
        self._update_timer = timer
        self._update_timer.start()

    def _update_position(self) -> None:
        if not self.parent():
            return

        parent_width = self.parent().width()
        parent_height = self.parent().height()
        widget_width = self.width()
        widget_height = self.height()

        edge_margin = max(0, int(self._margin))

        if self._position == MediaPosition.TOP_LEFT:
            x = edge_margin
            y = edge_margin
        elif self._position == MediaPosition.TOP_RIGHT:
            x = parent_width - widget_width - edge_margin
            y = edge_margin
        elif self._position == MediaPosition.BOTTOM_LEFT:
            x = edge_margin
            y = parent_height - widget_height - edge_margin
        elif self._position == MediaPosition.BOTTOM_RIGHT:
            x = parent_width - widget_width - edge_margin
            y = parent_height - widget_height - edge_margin
        else:
            x = edge_margin
            y = parent_height - widget_height - edge_margin

        self.move(x, y)

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def _update_stylesheet(self) -> None:
        if self._show_background:
            self.setStyleSheet(
                f"""
                QLabel {{
                    color: rgba({self._text_color.red()}, {self._text_color.green()},
                               {self._text_color.blue()}, {self._text_color.alpha()});
                    background-color: rgba({self._bg_color.red()}, {self._bg_color.green()},
                                          {self._bg_color.blue()}, {self._bg_color.alpha()});
                    border: {self._bg_border_width}px solid rgba({self._bg_border_color.red()},
                                                                 {self._bg_border_color.green()},
                                                                 {self._bg_border_color.blue()},
                                                                 {self._bg_border_color.alpha()});
                    border-radius: 8px;
                }}
                """
            )
        else:
            self.setStyleSheet(
                f"""
                QLabel {{
                    color: rgba({self._text_color.red()}, {self._text_color.green()},
                               {self._text_color.blue()}, {self._text_color.alpha()});
                    background-color: transparent;
                }}
                """
            )

    def set_font_family(self, family: str) -> None:
        self._font_family = family
        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)
        self.setFont(font)

    def set_font_size(self, size: int) -> None:
        if size <= 0:
            logger.warning("[FALLBACK] Invalid media widget font size %s, using 20", size)
            size = 20
        self._font_size = size
        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)
        self.setFont(font)

    def set_text_color(self, color: QColor) -> None:
        self._text_color = color
        self._update_stylesheet()

    def set_show_background(self, show: bool) -> None:
        self._show_background = bool(show)
        self._update_stylesheet()

    def set_background_color(self, color: QColor) -> None:
        self._bg_color = color
        if self._show_background:
            self._update_stylesheet()

    def set_background_opacity(self, opacity: float) -> None:
        self._bg_opacity = max(0.0, min(1.0, opacity))
        self._bg_color.setAlpha(int(255 * self._bg_opacity))
        if self._show_background:
            self._update_stylesheet()

    def set_background_border(self, width: int, color: QColor) -> None:
        self._bg_border_width = max(0, int(width))
        self._bg_border_color = color
        if self._show_background:
            self._update_stylesheet()

    def set_margin(self, margin: int) -> None:
        if margin < 0:
            logger.warning("[FALLBACK] Invalid media widget margin %s, using 20", margin)
            margin = 20
        self._margin = margin
        if self._enabled:
            self._update_position()

    def set_position(self, position: MediaPosition) -> None:
        self._position = position
        if self._enabled:
            self._update_position()

    def set_artwork_size(self, size: int) -> None:
        """Set preferred artwork size in pixels and refresh layout."""

        if size <= 0:
            return
        self._artwork_size = int(size)
        if self._last_info is not None:
            try:
                self._update_display(self._last_info)
            except Exception:
                self.update()

    def set_rounded_artwork_border(self, rounded: bool) -> None:
        """Enable or disable rounded borders around the album artwork."""

        self._rounded_artwork_border = bool(rounded)
        self.update()

    def set_show_controls(self, show: bool) -> None:
        """Show or hide the transport controls row."""

        self._show_controls = bool(show)
        if self._last_info is not None:
            try:
                self._update_display(self._last_info)
            except Exception:
                self.update()

    # ------------------------------------------------------------------
    # Transport controls (delegated to controller)
    # ------------------------------------------------------------------
    def play_pause(self) -> None:
        """Toggle play/pause when supported.

        This is best-effort and never raises; failures are logged by the
        underlying controller. It is safe to call even when no media is
        currently playing.
        """

        try:
            self._controller.play_pause()
        except Exception:
            logger.debug("[MEDIA] play_pause delegation failed", exc_info=True)

    def next_track(self) -> None:
        """Skip to next track when supported (best-effort)."""

        try:
            self._controller.next()
        except Exception:
            logger.debug("[MEDIA] next delegation failed", exc_info=True)

    def previous_track(self) -> None:
        """Skip to previous track when supported (best-effort)."""

        try:
            self._controller.previous()
        except Exception:
            logger.debug("[MEDIA] previous delegation failed", exc_info=True)

    # ------------------------------------------------------------------
    # Polling and display
    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        if not self._enabled:
            return
        if self._thread_manager is not None:
            logger.debug("[MEDIA_WIDGET] Scheduling async refresh via ThreadManager")
            self._refresh_async()
            return

        info: Optional[MediaTrackInfo]
        try:
            info = self._controller.get_current_track()
        except Exception:
            logger.debug("[MEDIA] get_current_track failed", exc_info=True)
            info = None

        self._update_display(info)

    def _refresh_async(self) -> None:
        if self._refresh_in_flight:
            return
        tm = self._thread_manager
        if tm is None:
            return

        self._refresh_in_flight = True
        logger.debug("[MEDIA_WIDGET] Async refresh started")

        def _do_query():
            try:
                return self._controller.get_current_track()
            except Exception:
                logger.debug("[MEDIA] get_current_track failed", exc_info=True)
                return None

        def _on_result(task_result) -> None:
            def _apply(info) -> None:
                self._refresh_in_flight = False
                try:
                    if info is None:
                        logger.debug("[MEDIA_WIDGET] No track info in async result; hiding")
                    else:
                        try:
                            state = getattr(info, "state", None)
                            state_val = state.value if hasattr(state, "value") else str(state)
                        except Exception:
                            state_val = "?"
                        logger.debug(
                            "[MEDIA_WIDGET] Applying track: state=%s, title=%r, artist=%r, album=%r",
                            state_val,
                            getattr(info, "title", None),
                            getattr(info, "artist", None),
                            getattr(info, "album", None),
                        )
                except Exception:
                    logger.debug("[MEDIA_WIDGET] Failed to log async apply", exc_info=True)
                self._update_display(info)

            info = None
            if getattr(task_result, "success", False):
                info = getattr(task_result, "result", None)
            ThreadManager.run_on_ui_thread(_apply, info)

        try:
            tm.submit_io_task(_do_query, callback=_on_result)
        except Exception:
            self._refresh_in_flight = False

    def _update_display(self, info: Optional[MediaTrackInfo]) -> None:
        # Cache last track snapshot for diagnostics/interaction
        prev_info = self._last_info
        self._last_info = info

        if info is None:
            # No active media session (e.g. Spotify not playing) – hide widget
            logger.debug("[MEDIA_WIDGET] _update_display called with None; hiding widget")
            self._artwork_pixmap = None
            try:
                self.hide()
            except Exception:
                pass
            return

        try:
            state = info.state
        except Exception:
            state = MediaPlaybackState.UNKNOWN

        # Metadata: title and artist on separate lines; album is intentionally
        # omitted to keep the block compact.
        title = (info.title or "").strip()
        artist = (info.artist or "").strip()

        # Typography: header is slightly larger than the base font, the song
        # title is emphasised, and the artist is a touch smaller but still
        # strong enough to read at a glance.
        base_font = max(6, self._font_size)
        header_font = max(6, int(base_font * 1.2))
        title_font = max(6, base_font + 3)
        artist_font = max(6, base_font - 2)

        header_weight = 750  # a bit heavier than standard bold
        title_weight = 700
        artist_weight = 600

        # Store logo metrics so paintEvent can size/position the glyph
        # relative to the SPOTIFY text. The logo is kept slightly larger than
        # the SPOTIFY word and the header text is indented accordingly.
        self._header_font_pt = header_font
        self._header_logo_size = max(12, int(header_font * 1.3))
        self._header_logo_margin = self._header_logo_size + 10

        # Build metadata lines with per-line font sizes/weights.
        if not title and not artist:
            body_html = (
                f"<div style='font-size:{base_font}pt; font-weight:500;'>(no metadata)</div>"
            )
        else:
            body_lines_html = []
            if title:
                body_lines_html.append(
                    f"<div style='font-size:{title_font}pt; font-weight:{title_weight};'>{title}</div>"
                )
            if artist:
                body_lines_html.append(
                    f"<div style='margin-top:4px; font-size:{artist_font}pt; font-weight:{artist_weight}; opacity:0.95;'>{artist}</div>"
                )
            body_html = "".join(body_lines_html)

        controls_html = ""
        if self._show_controls:
            # Slightly smaller than the main body text to keep controls
            # visually subtle and avoid cartoonish glyph sizing.
            controls_font = max(6, self._font_size - 3)
            inactive_color = "rgba(200,200,200,230)"
            active_color = "rgba(255,255,255,255)"

            def _control_span(symbol: str, is_active: bool, scale: float = 1.0) -> str:
                size = max(4.0, float(controls_font) * max(0.5, float(scale)))
                color = active_color if is_active else inactive_color
                weight = "700" if is_active else "500"
                return (
                    f"<span style='font-size:{size}pt; font-weight:{weight}; color:{color};'>{symbol}</span>"
                )

            # Structured, minimal controls: left/right arrows and a single
            # centre play/pause toggle. The play glyph is slightly upsized so
            # it visually matches the pause bars it toggles into.
            prev_sym = "\u2190"  # LEFTWARDS ARROW
            next_sym = "\u2192"  # RIGHTWARDS ARROW
            if state == MediaPlaybackState.PLAYING:
                centre_sym = "||"  # pause
                centre_scale = 1.0
            else:
                centre_sym = "\u25b6"  # play
                centre_scale = 1.25

            prev_html = _control_span(prev_sym, False)
            centre_html = _control_span(centre_sym, True, centre_scale)
            next_html = _control_span(next_sym, False)

            controls_html = (
                f"{prev_html}&nbsp;&nbsp;{centre_html}&nbsp;&nbsp;{next_html}"
            )

        header_html = (
            f"<div style='font-size:{header_font}pt; font-weight:{header_weight}; "
            f"opacity:0.9; letter-spacing:1px; margin-left:{self._header_logo_margin}px;'>SPOTIFY</div>"
        )
        # Outer wrapper just establishes spacing; individual lines carry
        # their own font sizes/weights.
        body_wrapper = f"<div style='margin-top:8px;'>{body_html}</div>"

        html_parts = ["<div style='line-height:1.25'>", header_html, body_wrapper]
        if controls_html:
            html_parts.append(f"<div style='margin-top:8px;'>{controls_html}</div>")
        html_parts.append("</div>")
        html = "".join(html_parts)

        self.setTextFormat(Qt.TextFormat.RichText)
        self.setText(html)
        self.adjustSize()
        if self.parent():
            self._update_position()

        try:
            payload = asdict(info)
            payload["state"] = info.state.value
            self.media_updated.emit(payload)
        except Exception:
            # Failing to emit rich diagnostics should not break the widget.
            pass

        # Decode optional artwork bytes
        prev_pm = self._artwork_pixmap
        had_artwork_before = prev_pm is not None and not prev_pm.isNull()
        self._artwork_pixmap = None
        artwork_bytes = getattr(info, "artwork", None)
        if isinstance(artwork_bytes, (bytes, bytearray)) and artwork_bytes:
            try:
                pm = QPixmap()
                if pm.loadFromData(bytes(artwork_bytes)) and not pm.isNull():
                    self._artwork_pixmap = pm
                    if not had_artwork_before:
                        self._start_artwork_fade_in()
            except Exception:
                logger.debug("[MEDIA] Failed to decode artwork pixmap", exc_info=True)

        # Reserve space for artwork plus breathing room on the right even
        # when artwork is missing so the widget size stays stable. Text stays
        # anchored on the left side.
        right_margin = max(self._artwork_size + 40, 60)
        self.setContentsMargins(24, 12, right_margin, 12)

        # Let the card height track the configured artwork size so large
        # artwork (e.g. 300px) does not clip and always has comfortable
        # padding to the top/bottom edges.
        self.setMinimumHeight(max(220, self._artwork_size + 60))

        # After adjusting margins and height, recompute the widget's anchored
        # position so we do not "jump" after the fade completes.
        if self.parent():
            self._update_position()

        # Fade in the widget when the track changes (including the first
        # time we see media); otherwise just ensure it is visible.
        track_changed = (
            prev_info is None
            or getattr(prev_info, "title", "").strip() != title
            or getattr(prev_info, "artist", "").strip() != artist
        )
        if track_changed:
            self._start_widget_fade_in(800)
        else:
            try:
                self.show()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def paintEvent(self, event):  # type: ignore[override]
        """Paint text via QLabel then overlay optional artwork icon.

        Artwork is drawn to the right side inside the widget's margins so
        that the text content remains legible. All failures are ignored so
        that paint never raises.
        """

        super().paintEvent(event)

        try:
            painter = QPainter(self)
            try:
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            except Exception:
                pass

            pm = self._artwork_pixmap
            if pm is not None and not pm.isNull():
                # Artwork should be the dominant visual element but must
                # respect padding so it never clips. We clamp by height and
                # the requested logical size, avoiding overly conservative
                # width-based caps.
                max_by_height = max(24, self.height() - 60)  # 30px top/bottom padding
                size = max(48, min(self._artwork_size, max_by_height))
                if size > 0:
                    # Scale in device pixels but compute the border in logical
                    # coordinates so the frame fits tightly even on high-DPI
                    # displays.
                    try:
                        dpr = float(self.devicePixelRatioF())
                    except Exception:
                        dpr = 1.0
                    scale_dpr = max(1.0, dpr)
                    target_px = int(size * scale_dpr)
                    scaled = pm.scaled(
                        target_px,
                        target_px,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    try:
                        scaled.setDevicePixelRatio(scale_dpr)
                    except Exception:
                        pass

                    logical_w = int(round(scaled.width() / scale_dpr)) or size
                    logical_h = int(round(scaled.height() / scale_dpr)) or size

                    # Keep a fixed inset from the top/right card borders so the
                    # artwork and its border never touch the outer frame.
                    pad = 20
                    x = max(pad, self.width() - pad - logical_w)
                    y = pad
                    painter.save()
                    try:
                        if self._artwork_opacity != 1.0:
                            painter.setOpacity(max(0.0, min(1.0, float(self._artwork_opacity))))

                        border_rect = QRect(x, y, logical_w, logical_h).adjusted(-1, -1, 1, 1)

                        # Clip the artwork to the same rounded/square frame so
                        # pixels never bleed out past the border corners.
                        path = QPainterPath()
                        if self._rounded_artwork_border:
                            radius = min(border_rect.width(), border_rect.height()) / 8.0
                            path.addRoundedRect(border_rect, radius, radius)
                        else:
                            path.addRect(border_rect)
                        painter.setClipPath(path)

                        painter.drawPixmap(x, y, scaled)

                        # Artwork border matching the widget frame colour/opacity.
                        if self._bg_border_width > 0 and self._bg_border_color.alpha() > 0:
                            pen = painter.pen()
                            pen.setColor(self._bg_border_color)
                            pen.setWidth(max(1, self._bg_border_width))
                            painter.setPen(pen)
                            painter.setBrush(Qt.BrushStyle.NoBrush)
                            if self._rounded_artwork_border:
                                painter.drawPath(path)
                            else:
                                painter.drawRect(border_rect)
                    finally:
                        painter.restore()
            # Paint the Spotify logo for the header using high-DPI aware
            # scaling so it stays crisp and properly aligned with the SPOTIFY
            # word rendered by QLabel's rich text.
            self._paint_header_logo(painter)
        except Exception:
            logger.debug("[MEDIA] Failed to paint artwork pixmap", exc_info=True)

    def _load_brand_pixmap(self) -> Optional[QPixmap]:
        """Best-effort load of a Spotify logo from the shared images folder.

        We prefer the high-resolution primary logo asset when present so that
        the glyph remains sharp even when scaled up on high-DPI displays.
        """

        try:
            images_dir = Path(__file__).resolve().parent.parent / "images"
            candidates = [
                "Spotify_Primary_Logo_RGB_Black.png",
                "spotify_logo.png",
                "SpotifyLogo.png",
                "spotify.png",
            ]
            for name in candidates:
                candidate = images_dir / name
                if candidate.exists() and candidate.is_file():
                    pm = QPixmap(str(candidate))
                    if not pm.isNull():
                        return pm
        except Exception:
            logger.debug("[MEDIA] Failed to load Spotify logo", exc_info=True)
        return None

    def _paint_header_logo(self, painter: QPainter) -> None:
        """Paint the Spotify logo glyph next to the SPOTIFY header text.

        This is drawn separately from the rich-text header so that we can
        control DPI scaling and alignment precisely while keeping the
        markup simple on the QLabel side.
        """

        pm = self._brand_pixmap
        size = self._header_logo_size
        if pm is None or pm.isNull() or size <= 0:
            return

        try:
            dpr = float(self.devicePixelRatioF())
        except Exception:
            dpr = 1.0

        target_px = int(size * max(1.0, dpr))
        if target_px <= 0:
            return

        scaled = pm.scaled(
            target_px,
            target_px,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        try:
            scaled.setDevicePixelRatio(max(1.0, dpr))
        except Exception:
            pass

        margins = self.contentsMargins()
        x = margins.left()

        # Align the logo vertically with the SPOTIFY text by centring the
        # glyph within the first header line's text metrics instead of
        # simply pinning it to the top margin.
        try:
            header_font_pt = int(self._header_font_pt) if self._header_font_pt > 0 else self._font_size
        except Exception:
            header_font_pt = self._font_size

        font = QFont(self._font_family, header_font_pt, QFont.Weight.Bold)
        fm = QFontMetrics(font)
        line_height = fm.height()
        line_centre = margins.top() + (line_height / 2.0)
        icon_half = float(self._header_logo_size) / 2.0
        y = int(line_centre - icon_half)
        if y < margins.top():
            y = margins.top()

        painter.save()
        try:
            painter.drawPixmap(x, y, scaled)
        finally:
            painter.restore()

    def _start_widget_fade_in(self, duration_ms: int = 800) -> None:
        """Fade the entire widget in using a graphics opacity effect."""

        effect = self._widget_opacity_effect
        if effect is None:
            # No effect installed; fall back to an immediate show.
            try:
                self.show()
            except Exception:
                pass
            return

        # Stop any in-flight animation.
        if self._widget_fade_anim is not None:
            try:
                self._widget_fade_anim.stop()
            except Exception:
                pass
            self._widget_fade_anim = None

        try:
            self.show()
        except Exception:
            pass

        try:
            effect.setOpacity(0.0)
        except Exception:
            return

        anim = QVariantAnimation(self)
        anim.setDuration(max(0, int(duration_ms)))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutQuad)

        def _on_value_changed(value):
            try:
                effect.setOpacity(float(value))
            except Exception:
                pass

        anim.valueChanged.connect(_on_value_changed)

        def _on_finished() -> None:
            self._widget_fade_anim = None
            try:
                effect.setOpacity(1.0)
            except Exception:
                pass

        anim.finished.connect(_on_finished)
        self._widget_fade_anim = anim
        anim.start()

    def _start_artwork_fade_in(self) -> None:
        if self._artwork_anim is not None:
            try:
                self._artwork_anim.stop()
            except Exception:
                pass
            self._artwork_anim = None

        self._artwork_opacity = 0.0

        anim = QVariantAnimation(self)
        anim.setDuration(350)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutQuad)

        def _on_value_changed(value):
            try:
                self._artwork_opacity = float(value)
            except (TypeError, ValueError):
                self._artwork_opacity = 1.0
            self.update()

        anim.valueChanged.connect(_on_value_changed)

        def _on_finished() -> None:
            self._artwork_anim = None
            self._artwork_opacity = 1.0

        anim.finished.connect(_on_finished)
        self._artwork_anim = anim
        anim.start()
