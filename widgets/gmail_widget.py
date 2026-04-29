"""Gmail overlay widget for screensaver."""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QWidget

from core.gmail.gmail_backend import GmailBackend
from core.gmail.gmail_client import EmailMetadata, GmailLabel
from core.gmail.gmail_deeplinks import gmail_inbox_url
from core.logging.logger import get_logger
from core.settings.storage_paths import get_app_data_dir
from core.threading.manager import ThreadManager
from core.windows.secure_url_launcher import open_url
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition, WidgetLifecycleState
from widgets.gmail_components import (
    GmailPosition,
    _format_relative_time,
    clean_sender_name,
    deserialize_email_cache,
    shorten_subject,
    smart_title_case_subject,
    serialize_email_cache,
)
from widgets.overlay_timers import create_overlay_timer, OverlayTimerHandle
from widgets.shadow_utils import ShadowFadeProfile, draw_rounded_rect_with_shadow

logger = get_logger(__name__)

CACHE_MAX_AGE_HOURS = 72
CACHE_DIR = get_app_data_dir() / "cache"
CACHE_PATH = CACHE_DIR / "gmail_cache.json"


class GmailWidget(BaseOverlayWidget):
    """Gmail overlay widget showing recent emails."""

    email_clicked = Signal(str)
    unread_count_changed = Signal(int)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        position: GmailPosition = GmailPosition.TOP_LEFT,
        settings: Optional[Any] = None,
    ) -> None:
        overlay_pos = OverlayPosition.from_string(position.value)
        super().__init__(parent, position=overlay_pos, overlay_name="gmail")
        self._gmail_position = position

        self._backend: GmailBackend = GmailBackend.instance()
        self._gmail_client = None  # GmailClient or GmailImapClient
        self._emails: List[EmailMetadata] = []
        self._unread_count = 0
        self._has_displayed_valid_data = False
        self._last_error: Optional[str] = None

        self._limit = 5
        self._refresh_interval = timedelta(minutes=5)
        self._filter_label = GmailLabel.INBOX.value
        self._show_sender = True
        self._show_subject = True
        self._show_envelope_icon = True
        self._show_three_dot_menu = True
        self._show_timestamp = True
        self._show_separators = True
        self._auto_title_case = True
        self._clean_sender_names = True
        self._max_sender_words = 3
        self._sender_column_width = 180
        self._max_subject_words = 4
        self._max_subject_chars = 0
        self._show_unread_count_in_header = True
        self._desaturate_when_no_unread = True
        self._account_slot = "0"

        self._separator_color = QColor(200, 200, 200, 40)
        self._separator_thickness = 1
        self._boundary_separator_color = QColor(180, 180, 180, 80)
        self._boundary_separator_thickness = 2

        self._width = 600
        self._content_padding_left = 0
        self._content_padding_right = 0
        self._content_padding_top = 0
        self._show_header_border = True
        self._header_frame_pad_x = 9
        self._header_frame_pad_y = 5
        self._header_logo_gap = 8

        self._header_font_pt = max(10, int(self._font_size) + 2)
        self._header_logo_size = 28
        self._row_vertical_spacing = 2

        self._brand_pixmap: Optional[QPixmap] = None
        self._brand_pixmap_desaturated: Optional[QPixmap] = None
        self._envelope_pixmap: Optional[QPixmap] = None
        self._envelope_pixmap_dim: Optional[QPixmap] = None
        self._action_icons: Dict[str, Optional[QPixmap]] = {}

        self._header_hit_rect: Optional[QRect] = None
        self._row_hit_rects: List[Tuple[QRect, str, str]] = []
        self._action_hit_rects: List[Tuple[QRect, str]] = []

        self._update_timer_handle: Optional[OverlayTimerHandle] = None
        self._update_timer: Optional[QTimer] = None
        self._fetch_in_progress = False
        self._fetch_lock = threading.Lock()
        self._fetch_generation = 0
        self._cancelled = False

        # New-mail detection: only fire sound for messages that arrive after
        # the first fetch of this session. Pre-existing unread on first fetch
        # is silently absorbed.
        self._seen_message_ids: Set[str] = set()
        self._seen_initialised: bool = False
        self._play_sound_on_new_mail: bool = False
        self._sound_file_path: str = "resources/tutuogg.ogg"
        self._sound_volume_percent: int = 50

        if settings is not None:
            self.apply_settings(settings)
        self._setup_ui()
        self._load_brand_pixmap()
        self._load_envelope_pixmap()
        self._load_action_icons()

    def _setup_ui(self) -> None:
        self._apply_base_styling()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(False)
        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)
        self.setFont(font)
        self.setContentsMargins(29, 12, 12, 12)
        self._apply_width()
        self.setMinimumHeight(120)

    def _apply_width(self) -> None:
        width = max(200, min(1200, int(self._width)))
        self._width = width
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)
        if self.width() != width:
            self.resize(width, self.height())
        self._update_position()

    def sizeHint(self) -> QSize:  # type: ignore[override]
        hint = super().sizeHint()
        width = self._width
        height = max(self.minimumHeight(), hint.height())
        return QSize(width, height)

    def _load_brand_pixmap(self) -> None:
        path = Path("images/google-gmail.png")
        if path.exists():
            pm = QPixmap(str(path))
            if not pm.isNull():
                self._brand_pixmap = pm.scaled(
                    self._header_logo_size, self._header_logo_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._brand_pixmap_desaturated = None
                return
        logger.warning("[GMAIL] Brand PNG missing: %s", path)
        self._brand_pixmap = None
        self._brand_pixmap_desaturated = None

    def _load_envelope_pixmap(self) -> None:
        path = Path("images/gmail-envelope.png")
        if path.exists():
            pm = QPixmap(str(path))
            if not pm.isNull():
                target = 16
                self._envelope_pixmap = pm.scaled(
                    target, target,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                dim_img = pm.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
                self._envelope_pixmap_dim = QPixmap.fromImage(dim_img).scaled(
                    target, target,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                return
        logger.warning("[GMAIL] Envelope PNG missing: %s", path)
        self._envelope_pixmap = None
        self._envelope_pixmap_dim = None

    def _ensure_desaturated_brand(self) -> Optional[QPixmap]:
        if self._brand_pixmap is None:
            return None
        if self._brand_pixmap_desaturated is not None:
            return self._brand_pixmap_desaturated
        img = self._brand_pixmap.toImage()
        grayscale = img.convertToFormat(QImage.Format.Format_Grayscale8)
        pm = QPixmap.fromImage(grayscale)
        self._brand_pixmap_desaturated = pm
        return pm

    def _load_action_icons(self) -> None:
        names = {"read": "images/gmail-read.png", "spam": "images/gmail-spam.png", "trash": "images/gmail-trash.png"}
        for key, path_str in names.items():
            path = Path(path_str)
            if path.exists():
                pm = QPixmap(str(path))
                if not pm.isNull():
                    self._action_icons[key] = pm.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    continue
            self._action_icons[key] = None

    def _initialize_impl(self) -> None:
        logger.debug("[LIFECYCLE] GmailWidget initialized")

    def _activate_impl(self) -> None:
        self._cancelled = False
        if self._backend.is_authenticated:
            self._gmail_client = self._backend.client
        cached = self._load_email_cache()
        if cached:
            self._emails = cached
            self._unread_count = sum(1 for e in self._emails if e.is_unread)
            self._has_displayed_valid_data = True
            self._update_card_height_from_content(len(self._emails))
            self.update()
        else:
            self._update_card_height_from_content(1)
            self.update()
        self._schedule_timer()
        self._fetch_emails()

        # Register for coordinated fade-in (must happen before compositor_ready fires)
        self._request_fade_in()
        logger.debug("[LIFECYCLE] GmailWidget activated")

    def _deactivate_impl(self) -> None:
        if self._update_timer_handle is not None:
            try:
                self._update_timer_handle.stop()
            except Exception:
                pass
            self._update_timer_handle = None
        if self._update_timer is not None:
            try:
                self._update_timer.stop()
                self._update_timer.deleteLater()
            except Exception:
                pass
            self._update_timer = None
        self._cancelled = True
        self._fetch_generation += 1
        self._emails.clear()
        self._row_hit_rects.clear()
        self._action_hit_rects.clear()
        logger.debug("[LIFECYCLE] GmailWidget deactivated")

    def _cleanup_impl(self) -> None:
        self._deactivate_impl()
        logger.debug("[LIFECYCLE] GmailWidget cleaned up")

    def start(self) -> None:
        if self._lifecycle_state == WidgetLifecycleState.INACTIVE:
            self.activate()

    def stop(self) -> None:
        if self._lifecycle_state == WidgetLifecycleState.ACTIVE:
            self.deactivate()

    def cleanup(self) -> None:
        # Reset new-mail detection state so a subsequent start() re-absorbs
        # the existing inbox without firing the sound for old messages.
        self._seen_message_ids = set()
        self._seen_initialised = False
        self._cancelled = True
        self._fetch_generation += 1
        # Explicit timer cleanup for safety (also covered by _cleanup_impl → _deactivate_impl)
        if self._update_timer_handle is not None:
            try:
                self._update_timer_handle.stop()
            except Exception:
                pass
            self._update_timer_handle = None
        if self._update_timer is not None:
            try:
                self._update_timer.stop()
                self._update_timer.deleteLater()
            except Exception:
                pass
            self._update_timer = None
        self._emails.clear()
        self._row_hit_rects.clear()
        self._action_hit_rects.clear()
        super().cleanup()

    # ------------------------------------------------------------------
    # Timer & Fetch
    # ------------------------------------------------------------------

    def _schedule_timer(self) -> None:
        interval_ms = int(self._refresh_interval.total_seconds() * 1000)
        try:
            self._update_timer_handle = create_overlay_timer(
                self, interval_ms, self._fetch_emails,
                description="gmail_refresh",
            )
        except Exception:
            self._update_timer = QTimer(self)
            self._update_timer.timeout.connect(self._fetch_emails)
            self._update_timer.start(interval_ms)

    def _fetch_emails(self) -> None:
        with self._fetch_lock:
            if self._fetch_in_progress:
                logger.debug("[GMAIL] Fetch already in progress, skipping")
                return
            self._fetch_in_progress = True
        # Re-acquire client from backend each fetch in case mode/credentials changed
        self._gmail_client = self._backend.client if self._backend.is_authenticated else None
        if self._gmail_client is None:
            with self._fetch_lock:
                self._fetch_in_progress = False
            logger.debug("[GMAIL] Not authenticated, skipping fetch")
            self._last_error = "auth"
            self.update()
            return
        try:
            if self._ensure_thread_manager("GmailWidget._fetch_emails"):
                generation = self._fetch_generation
                self._thread_manager.submit_io_task(self._fetch_emails_async, generation)
            else:
                self._fetch_emails_sync()
        except Exception:
            self._fetch_emails_sync()

    def _fetch_emails_async(self, generation: int) -> None:
        try:
            if self._cancelled or generation != self._fetch_generation:
                return
            label_ids = [self._filter_label]
            emails = self._gmail_client.list_messages(
                max_results=self._limit, label_ids=label_ids
            )
            unread = sum(1 for e in emails if e.is_unread)
            try:
                ThreadManager.run_on_ui_thread(
                    self._on_emails_fetched, emails, unread, generation
                )
            except Exception:
                logger.critical("[GMAIL] run_on_ui_thread failed, dropping fetch result")
        except Exception as exc:
            logger.error("[GMAIL] Fetch failed: %s", exc)
            try:
                ThreadManager.run_on_ui_thread(
                    self._on_fetch_error, str(exc), generation
                )
            except Exception:
                logger.critical("[GMAIL] run_on_ui_thread failed, dropping error")
        finally:
            with self._fetch_lock:
                self._fetch_in_progress = False

    def _fetch_emails_sync(self) -> None:
        try:
            label_ids = [self._filter_label]
            emails = self._gmail_client.list_messages(
                max_results=self._limit, label_ids=label_ids
            )
            unread = sum(1 for e in emails if e.is_unread)
            self._on_emails_fetched(emails, unread)
        except Exception as e:
            logger.error("[GMAIL] Sync fetch failed: %s", e)
            self._on_fetch_error(str(e))
        finally:
            with self._fetch_lock:
                self._fetch_in_progress = False

    def _on_emails_fetched(
        self, emails: List[EmailMetadata], unread_count: int, generation: Optional[int] = None
    ) -> None:
        if self._cancelled:
            return
        if generation is not None and generation != self._fetch_generation:
            return
        self._emails = sorted(emails, key=lambda e: (not e.is_unread, -e.date.timestamp()))
        self._last_error = None
        self._detect_new_mail(emails)
        if unread_count != self._unread_count:
            self._unread_count = unread_count
            self.unread_count_changed.emit(unread_count)
        if emails:
            self._has_displayed_valid_data = True
            self._write_email_cache(emails)
            self._update_card_height_from_content(len(emails))
            self.update()
            if not self.isVisible():
                self._request_fade_in()
        else:
            self._update_card_height_from_content(1)
            self.update()
            if not self.isVisible():
                self._request_fade_in()

    def _detect_new_mail(self, emails: List[EmailMetadata]) -> None:
        """Detect newly-arrived unread messages and play notification sound.

        First fetch of the session populates the seen set without playing
        sound (suppresses startup blast for pre-existing unread).
        """
        try:
            current_unread_ids = {e.id for e in emails if getattr(e, "is_unread", False)}
        except Exception as exc:
            logger.debug("[GMAIL] _detect_new_mail id collection failed: %s", exc)
            return

        if not self._seen_initialised:
            # Absorb the existing inbox quietly.
            self._seen_message_ids = current_unread_ids
            self._seen_initialised = True
            return

        new_ids = current_unread_ids - self._seen_message_ids
        # Always update the seen set so messages don't re-trigger.
        self._seen_message_ids = current_unread_ids

        if not new_ids:
            return
        if not self._play_sound_on_new_mail:
            return

        try:
            from core.audio.notification_sound import NotificationSoundPlayer
            player = NotificationSoundPlayer.instance()
            # Push current settings on every play in case the user changed
            # path/volume mid-session.
            if player.file_path != self._sound_file_path:
                player.set_file_path(self._sound_file_path)
            if player.volume_percent != self._sound_volume_percent:
                player.set_volume(self._sound_volume_percent)
            player.play()
            logger.info("[GMAIL] New mail detected (%d new) — sound played", len(new_ids))
        except Exception as exc:
            logger.warning("[GMAIL] Notification sound failed: %s", exc)

    def _on_fetch_error(self, error_msg: str, generation: Optional[int] = None) -> None:
        if self._cancelled:
            return
        if generation is not None and generation != self._fetch_generation:
            return
        self._last_error = error_msg
        logger.warning("[GMAIL] Displaying error state: %s", error_msg)
        self._update_card_height_from_content(1)
        self.update()

    # ------------------------------------------------------------------
    # Email Cache
    # ------------------------------------------------------------------

    def _load_email_cache(self) -> Optional[List[EmailMetadata]]:
        if not CACHE_PATH.exists():
            return None
        mtime = datetime.fromtimestamp(CACHE_PATH.stat().st_mtime)
        if datetime.now() - mtime > timedelta(hours=CACHE_MAX_AGE_HOURS):
            logger.debug("[GMAIL] Cache stale (>24h), ignoring")
            return None
        try:
            data = CACHE_PATH.read_text(encoding="utf-8")
            emails = deserialize_email_cache(data)
            logger.info("[GMAIL] Loaded %d cached emails", len(emails))
            return emails
        except Exception as e:
            logger.warning("[GMAIL] Failed to load cache: %s", e)
            return None

    def _write_email_cache(self, emails: List[EmailMetadata]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = CACHE_PATH.with_suffix(".tmp")
            tmp.write_text(serialize_email_cache(emails), encoding="utf-8")
            tmp.replace(CACHE_PATH)
        except Exception as e:
            logger.warning("[GMAIL] Failed to write cache: %s", e)

    # ------------------------------------------------------------------
    # Card Height
    # ------------------------------------------------------------------

    def _update_card_height_from_content(
        self, visible_rows: Optional[int] = None
    ) -> None:
        rows = max(1, int(visible_rows)) if visible_rows is not None else 0
        if rows <= 0:
            rows = len(self._emails) or self._limit or 1
        rows = max(1, min(rows, max(1, self._limit)))
        base_font_pt = max(8, int(self._font_size))
        header_font_pt = int(self._header_font_pt or base_font_pt)
        header_font = QFont(self._font_family, header_font_pt, QFont.Weight.Bold)
        header_layout = self._calculate_header_layout(
            header_font,
            self._header_text(),
            self._brand_pixmap,
        )
        header_height = int(header_layout["height"]) + self._content_padding_top + 8
        row_font = QFont(self._font_family, base_font_pt, QFont.Weight.Normal)
        row_metrics = QFontMetrics(row_font)
        line_height = row_metrics.height() + 6
        card_padding = 22
        try:
            margins = self.contentsMargins()
            margin_top = margins.top()
            margin_bottom = margins.bottom()
        except Exception:
            margin_top = 0
            margin_bottom = 0
        content_height = (
            header_height
            + (rows * line_height)
            + (max(0, rows - 1) * self._row_vertical_spacing)
            + card_padding
        )
        target = content_height + margin_top + margin_bottom + 4
        try:
            self.setMinimumHeight(target)
            self.setMaximumHeight(target)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Fade In
    # ------------------------------------------------------------------

    def _request_fade_in(self) -> None:
        try:
            parent = self.parent()
            if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
                def starter():
                    self.show()
                    self.raise_()
                    ShadowFadeProfile.start_fade_in(
                        self,
                        self._shadow_config,
                        has_background_frame=self._show_background,
                    )
                parent.request_overlay_fade_sync("gmail", starter)
            else:
                self.show()
                self.raise_()
        except Exception:
            self.show()

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        try:
            self._paint_header(painter)
            if self._last_error:
                self._paint_error_state(painter)
            elif not self._emails:
                self._paint_empty_state(painter)
            else:
                self._paint_emails(painter)
        finally:
            painter.end()

    def _paint_header(self, painter: QPainter) -> None:
        header_font_pt = int(self._header_font_pt) if self._header_font_pt > 0 else self._font_size
        font = QFont(self._font_family, header_font_pt, QFont.Weight.Bold)
        painter.setFont(font)
        header_text = self._header_text()
        pixmap = self._brand_pixmap
        if self._desaturate_when_no_unread and self._unread_count == 0:
            desat = self._ensure_desaturated_brand()
            if desat is not None:
                pixmap = desat
        layout = self._calculate_header_layout(font, header_text, pixmap)
        self._paint_header_frame(painter, layout["frame_rect"])
        if pixmap is not None:
            painter.drawPixmap(layout["logo_rect"], pixmap)
        painter.setPen(self._text_color)
        painter.drawText(layout["text_x"], layout["text_baseline_y"], header_text)
        self._header_hit_rect = QRect(layout["frame_rect"])

    def _header_text(self) -> str:
        if self._show_unread_count_in_header and self._unread_count > 0:
            return f"Gmail ({self._unread_count})"
        return "Gmail"

    def _calculate_header_layout(
        self,
        font: QFont,
        header_text: str,
        pixmap: Optional[QPixmap],
    ) -> Dict[str, Any]:
        margins = self.contentsMargins()
        left = margins.left() + self._content_padding_left
        top = margins.top() + self._content_padding_top
        fm = QFontMetrics(font)
        logo_width = pixmap.width() if pixmap is not None else max(1, int(self._header_logo_size))
        logo_height = pixmap.height() if pixmap is not None else max(1, int(self._header_logo_size))
        text_width = fm.horizontalAdvance(header_text)
        text_height = fm.height()
        content_width = logo_width + self._header_logo_gap + text_width
        content_height = max(logo_height, text_height)
        frame_width = content_width + (self._header_frame_pad_x * 2)
        frame_height = content_height + (self._header_frame_pad_y * 2)
        max_width = max(1, self.width() - left - margins.right() - self._content_padding_right)
        frame_width = max(1, min(frame_width, max_width))
        frame_rect = QRect(left, top, frame_width, frame_height)
        center_y = frame_rect.top() + self._header_frame_pad_y + (content_height / 2)
        logo_x = frame_rect.left() + self._header_frame_pad_x
        logo_y = int(center_y - (logo_height / 2))
        text_x = logo_x + logo_width + self._header_logo_gap
        text_baseline_y = int(center_y - (text_height / 2) + fm.ascent())
        return {
            "frame_rect": frame_rect,
            "logo_rect": QRect(logo_x, logo_y, logo_width, logo_height),
            "text_x": text_x,
            "text_baseline_y": text_baseline_y,
            "height": frame_height,
            "bottom": frame_rect.bottom(),
        }

    def _paint_header_frame(self, painter: QPainter, frame_rect: QRect) -> None:
        if not self._show_header_border:
            return
        if self._bg_border_width <= 0 or self._bg_border_color.alpha() <= 0:
            return
        if frame_rect.width() <= 0 or frame_rect.height() <= 0:
            return
        radius = min(self._bg_corner_radius + 1, min(frame_rect.width(), frame_rect.height()) / 2)
        border_width = max(1, self._bg_border_width)
        draw_rounded_rect_with_shadow(
            painter,
            frame_rect,
            radius,
            self._bg_border_color,
            border_width,
        )

    def _header_bottom_y(self) -> int:
        header_font_pt = int(self._header_font_pt) if self._header_font_pt > 0 else self._font_size
        font = QFont(self._font_family, header_font_pt, QFont.Weight.Bold)
        pixmap = self._brand_pixmap
        layout = self._calculate_header_layout(font, self._header_text(), pixmap)
        return int(layout["bottom"]) + 8

    def _paint_empty_state(self, painter: QPainter) -> None:
        margins = self.contentsMargins()
        rect = self.rect().adjusted(
            margins.left() + self._content_padding_left,
            0,
            -(margins.right() + self._content_padding_right),
            0,
        )
        msg = "No unread emails"
        painter.setPen(self._text_color.darker(120))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, msg)

    def _paint_error_state(self, painter: QPainter) -> None:
        margins = self.contentsMargins()
        rect = self.rect().adjusted(
            margins.left() + self._content_padding_left,
            0,
            -(margins.right() + self._content_padding_right),
            0,
        )
        is_auth = self._last_error and "auth" in self._last_error.lower()
        msg = (
            "Gmail not connected. Tap to authenticate."
            if is_auth
            else "Gmail unavailable. Tap to retry."
        )
        painter.setPen(self._text_color.darker(120))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, msg)

    def _paint_emails(self, painter: QPainter) -> None:
        margins = self.contentsMargins()
        left = margins.left() + self._content_padding_left
        base_font_pt = max(8, int(self._font_size))
        row_y = self._header_bottom_y()
        self._row_hit_rects.clear()
        self._action_hit_rects.clear()
        available_width = max(
            1,
            self.width() - left - margins.right() - self._content_padding_right,
        )
        visible_emails = self._emails[: self._limit]
        action_width = 24 if self._show_three_dot_menu else 0
        env_slot_width = (
            self._envelope_pixmap.width() + 6
            if self._show_envelope_icon and self._envelope_pixmap is not None
            else 0
        )
        time_slot_width = 0
        if self._show_timestamp:
            time_font = QFont(self._font_family, base_font_pt - 2, QFont.Weight.Normal)
            time_fm = QFontMetrics(time_font)
            time_slot_width = max(
                (time_fm.horizontalAdvance(_format_relative_time(email.date)) + 8 for email in visible_emails),
                default=0,
            )
        text_area_width = max(1, available_width - env_slot_width - time_slot_width - action_width - 18)
        sender_slot_width = 0
        if self._show_sender:
            max_sender_width = max(40, text_area_width - 20)
            configured_sender_width = max(40, int(self._sender_column_width))
            sender_slot_width = min(configured_sender_width, max_sender_width)
        prev_unread = None
        for i, email in enumerate(visible_emails):
            if prev_unread is not None and prev_unread != email.is_unread and self._show_separators:
                sep_y = row_y - 1
                painter.setPen(QPen(self._boundary_separator_color, self._boundary_separator_thickness))
                painter.drawLine(left, sep_y, left + available_width, sep_y)
                row_y += 2
            weight = QFont.Weight.Bold if email.is_unread else QFont.Weight.Normal
            time_width = time_slot_width
            time_text = ""
            if self._show_timestamp:
                time_font = QFont(self._font_family, base_font_pt - 2, QFont.Weight.Normal)
                painter.setFont(time_font)
                time_text = _format_relative_time(email.date)
            env_x = left
            env_width = env_slot_width
            # Pre-compute line height so we can vertically centre the envelope
            subject_font = QFont(self._font_family, base_font_pt, weight)
            subject_fm = QFontMetrics(subject_font)
            line_height = subject_fm.height() + 6
            if self._show_envelope_icon and self._envelope_pixmap is not None:
                env_pm = self._envelope_pixmap if email.is_unread else self._envelope_pixmap_dim
                if env_pm is not None:
                    line_centre = row_y + (line_height * 0.5)
                    icon_half = float(env_pm.height()) / 2.0
                    env_y = int(line_centre - icon_half)
                    # Clamp so icon never sits above row or below row bottom
                    env_y = max(row_y, min(env_y, row_y + line_height - env_pm.height()))
                    painter.drawPixmap(env_x, env_y, env_pm)
            sender_width = 0
            if self._show_sender:
                sender_font = QFont(self._font_family, base_font_pt, weight)
                painter.setFont(sender_font)
                sender_fm = QFontMetrics(sender_font)
                sender_text = clean_sender_name(
                    email.sender,
                    enabled=self._clean_sender_names,
                    max_words=self._max_sender_words,
                )
                sender_text = sender_fm.elidedText(
                    sender_text, Qt.TextElideMode.ElideRight, sender_slot_width
                )
                sender_width = sender_slot_width + 12
            subject_font = QFont(self._font_family, base_font_pt, weight)
            painter.setFont(subject_font)
            subject_fm = QFontMetrics(subject_font)
            subject_text = email.subject
            if self._auto_title_case:
                subject_text = smart_title_case_subject(subject_text)
            subject_text = shorten_subject(
                subject_text,
                max_words=self._max_subject_words,
                max_chars=self._max_subject_chars,
            )
            subject_max_width = max(20, available_width - time_width - sender_width - env_width - action_width - 18)
            subject_text = subject_fm.elidedText(
                subject_text, Qt.TextElideMode.ElideRight, subject_max_width
            )
            text_y = row_y + subject_fm.ascent() + 2
            if self._show_timestamp:
                painter.setFont(QFont(self._font_family, base_font_pt - 2, QFont.Weight.Normal))
                painter.setPen(QColor(180, 180, 180, 200))
                time_x = env_x + env_width
                painter.drawText(time_x, text_y, time_text)
            if self._show_sender:
                painter.setFont(QFont(self._font_family, base_font_pt, weight))
                painter.setPen(
                    QColor(200, 200, 200, 255)
                    if email.is_unread
                    else QColor(180, 180, 180, 220)
                )
                sender_x = env_x + env_width + time_width
                painter.drawText(sender_x, text_y, sender_text)
            if self._show_subject:
                painter.setFont(subject_font)
                painter.setPen(
                    QColor(255, 255, 255, 255)
                    if email.is_unread
                    else QColor(220, 220, 220, 230)
                )
                subject_x = env_x + env_width + time_width + sender_width
                painter.drawText(subject_x, text_y, subject_text)
            if self._show_separators and i < len(visible_emails) - 1:
                sep_y = row_y + line_height
                painter.setPen(QPen(self._separator_color, self._separator_thickness))
                painter.drawLine(left, sep_y, left + available_width, sep_y)
            row_rect = QRect(left, row_y, available_width, line_height)
            self._row_hit_rects.append((row_rect, email.id, email.subject))
            if self._show_three_dot_menu:
                action_x = self.width() - margins.right() - self._content_padding_right - 24
                action_rect = QRect(action_x, row_y, 24, line_height)
                self._action_hit_rects.append((action_rect, email.id))
                painter.setPen(QColor(150, 150, 150, 180))
                dot_x = action_x + action_rect.width() // 2
                dot_y = row_y + line_height // 2 - 6
                for j in range(3):
                    painter.drawEllipse(QPoint(dot_x, dot_y + j * 6), 2, 2)
            prev_unread = email.is_unread
            row_y += line_height + self._row_vertical_spacing

    # ------------------------------------------------------------------
    # Click Handling
    # ------------------------------------------------------------------

    def handle_click(self, local_pos: QPoint) -> bool:
        if self._last_error:
            is_auth = "auth" in self._last_error.lower()
            if is_auth:
                self._trigger_auth_flow()
            else:
                self._fetch_emails()
            return True

        if self._header_hit_rect is not None and self._header_hit_rect.contains(local_pos):
            open_url(gmail_inbox_url(self._account_slot))
            return True

        for rect, message_id in self._action_hit_rects:
            if rect.contains(local_pos):
                self._show_action_menu(message_id, local_pos)
                return True

        for rect, message_id, _subject in self._row_hit_rects:
            if rect.contains(local_pos):
                email = next((e for e in self._emails if e.id == message_id), None)
                if email is not None and email.open_url:
                    open_url(email.open_url)
                elif self._gmail_client:
                    self._gmail_client.open_message_in_browser(message_id)
                else:
                    open_url(gmail_inbox_url(self._account_slot))
                return True

        return False

    def resolve_click_target(self, local_pos: QPoint) -> Optional[str]:
        """Return a Gmail URL for central MC/SCR click routing, without opening it."""
        if self._last_error:
            return None

        if self._header_hit_rect is not None and self._header_hit_rect.contains(local_pos):
            return gmail_inbox_url(self._account_slot)

        for rect, _message_id in self._action_hit_rects:
            if rect.contains(local_pos):
                return None

        for rect, message_id, _subject in self._row_hit_rects:
            if not rect.contains(local_pos):
                continue
            email = next((e for e in self._emails if e.id == message_id), None)
            if email is not None and email.open_url:
                return email.open_url
            return gmail_inbox_url(self._account_slot)

        return None

    def _trigger_auth_flow(self) -> None:
        logger.info("[GMAIL] Requesting authentication")
        try:
            self._backend.start_oauth_flow()
        except Exception as e:
            logger.error("[GMAIL] Auth flow failed: %s", e)

    def _show_action_menu(self, message_id: str, local_pos: QPoint) -> None:
        menu = QMenu(self)
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        menu.setStyleSheet(
            "QMenu { background-color: rgba(43,43,43,255); border: 2px solid rgba(154,154,154,200); border-radius: 6px; padding: 4px 2px; }"
            "QMenu::item { background-color: transparent; color: #ffffff; padding: 6px 20px 6px 12px; margin: 1px 3px; border-radius: 3px; font-size: 12px; }"
            "QMenu::item:selected { background-color: rgba(62,62,62,220); }"
        )
        email = next((e for e in self._emails if e.id == message_id), None)
        if not email:
            return

        widget_ref = self
        action_message_id = self._action_message_id(email)

        if email.is_unread:
            action_read = menu.addAction("Mark as Read")
            icon_read = self._action_icons.get("read")
            if icon_read:
                action_read.setIcon(QIcon(icon_read))
            action_read.triggered.connect(
                lambda _checked=False, mid=action_message_id: self._dispatch_action(widget_ref, self._do_mark_as_read, mid)
            )

        action_archive = menu.addAction("Archive")
        action_archive.triggered.connect(
            lambda _checked=False, mid=action_message_id: self._dispatch_action(widget_ref, self._do_archive, mid)
        )

        action_spam = menu.addAction("Mark as Spam")
        icon_spam = self._action_icons.get("spam")
        if icon_spam:
            action_spam.setIcon(QIcon(icon_spam))
        action_spam.triggered.connect(
            lambda _checked=False, mid=action_message_id: self._dispatch_action(widget_ref, self._do_spam, mid)
        )

        action_trash = menu.addAction("Delete")
        icon_trash = self._action_icons.get("trash")
        if icon_trash:
            action_trash.setIcon(QIcon(icon_trash))
        action_trash.triggered.connect(
            lambda _checked=False, mid=action_message_id: self._dispatch_action(widget_ref, self._do_trash, mid)
        )

        global_pos = self.mapToGlobal(local_pos)
        menu.popup(global_pos)

    @staticmethod
    def _action_message_id(email: EmailMetadata) -> str:
        if email.provider in {"gmail", "imap"} and email.imap_uid:
            return email.imap_uid
        return email.id

    @staticmethod
    def _dispatch_action(widget_ref, action_fn, message_id: str) -> None:
        try:
            from shiboken6 import isValid
            if not isValid(widget_ref):
                logger.warning("[GMAIL] Widget destroyed before action dispatch")
                return
        except ImportError:
            pass
        try:
            if widget_ref._ensure_thread_manager("GmailWidget._dispatch_action"):
                widget_ref._thread_manager.submit_io_task(lambda: action_fn(message_id))
            else:
                action_fn(message_id)
        except Exception:
            action_fn(message_id)

    def _do_mark_as_read(self, message_id: str) -> None:
        if self._gmail_client and self._gmail_client.mark_as_read(message_id):
            logger.info("[GMAIL] Marked %s as read", message_id)
            try:
                ThreadManager.run_on_ui_thread(self._fetch_emails)
            except Exception:
                pass

    def _do_archive(self, message_id: str) -> None:
        if self._gmail_client and self._gmail_client.archive_message(message_id):
            logger.info("[GMAIL] Archived %s", message_id)
            try:
                ThreadManager.run_on_ui_thread(self._fetch_emails)
            except Exception:
                pass

    def _do_spam(self, message_id: str) -> None:
        if self._gmail_client and self._gmail_client.spam_message(message_id):
            logger.info("[GMAIL] Marked %s as spam", message_id)
            try:
                ThreadManager.run_on_ui_thread(self._fetch_emails)
            except Exception:
                pass

    def _do_trash(self, message_id: str) -> None:
        if self._gmail_client and self._gmail_client.trash_message(message_id):
            logger.info("[GMAIL] Trashed %s", message_id)
            try:
                ThreadManager.run_on_ui_thread(self._fetch_emails)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def apply_settings(self, settings: Any) -> None:
        self._fetch_generation += 1
        if isinstance(settings, dict):
            self._apply_settings_dict(settings)
            return
        self.set_gmail_position(getattr(settings, "position", self._gmail_position.value))
        self.set_width(self._settings_width_value(settings))
        self.set_show_header_border(getattr(settings, "show_header_border", self._show_header_border))
        self.set_account_slot(getattr(settings, "account_slot", self._account_slot))
        self.set_limit(getattr(settings, "limit", self._limit))
        self.set_refresh_interval(getattr(settings, "refresh_minutes", 5))
        self.set_show_sender(getattr(settings, "show_sender", self._show_sender))
        self.set_show_subject(getattr(settings, "show_subject", self._show_subject))
        self.set_show_envelope_icon(getattr(settings, "show_envelope_icon", self._show_envelope_icon))
        self.set_show_three_dot_menu(getattr(settings, "show_three_dot_menu", self._show_three_dot_menu))
        self.set_show_timestamp(getattr(settings, "show_timestamp", self._show_timestamp))
        self.set_show_separators(getattr(settings, "show_separators", self._show_separators))
        self.set_separator_color(getattr(settings, "separator_color", self._separator_color))
        self.set_separator_thickness(getattr(settings, "separator_thickness", self._separator_thickness))
        self.set_boundary_separator_color(getattr(settings, "boundary_separator_color", self._boundary_separator_color))
        self.set_boundary_separator_thickness(getattr(settings, "boundary_separator_thickness", self._boundary_separator_thickness))
        self.set_auto_title_case(getattr(settings, "auto_title_case", self._auto_title_case))
        self.set_clean_sender_names(getattr(settings, "clean_sender_names", self._clean_sender_names))
        self.set_max_sender_words(getattr(settings, "max_sender_words", self._max_sender_words))
        self.set_sender_column_width(getattr(settings, "sender_column_width", self._sender_column_width))
        self.set_max_subject_words(getattr(settings, "max_subject_words", self._max_subject_words))
        self.set_max_subject_chars(getattr(settings, "max_subject_chars", self._max_subject_chars))
        self.set_show_unread_count_in_header(getattr(settings, "show_unread_count_in_header", self._show_unread_count_in_header))
        self.set_desaturate_when_no_unread(getattr(settings, "desaturate_when_no_unread", self._desaturate_when_no_unread))
        self.set_play_sound_on_new_mail(getattr(settings, "play_sound_on_new_mail", self._play_sound_on_new_mail))
        self.set_sound_file_path(getattr(settings, "sound_file_path", self._sound_file_path))
        self.set_sound_volume_percent(getattr(settings, "sound_volume_percent", self._sound_volume_percent))

    def _apply_settings_dict(self, d: Dict[str, Any]) -> None:
        if any(str(key).startswith("gmail.") for key in d):
            d = {
                str(key).split(".", 1)[1] if str(key).startswith("gmail.") else str(key): value
                for key, value in d.items()
            }
        self.set_gmail_position(d.get("position", self._gmail_position.value))
        self.set_width(d.get("width", d.get("min_width", d.get("max_width", self._width))))
        self.set_show_header_border(d.get("show_header_border", self._show_header_border))
        self.set_account_slot(d.get("account_slot", self._account_slot))
        self.set_limit(d.get("limit", self._limit))
        self.set_refresh_interval(d.get("refresh_minutes", 5))
        self.set_show_sender(d.get("show_sender", self._show_sender))
        self.set_show_subject(d.get("show_subject", self._show_subject))
        self.set_show_envelope_icon(d.get("show_envelope_icon", self._show_envelope_icon))
        self.set_show_three_dot_menu(d.get("show_three_dot_menu", self._show_three_dot_menu))
        self.set_show_timestamp(d.get("show_timestamp", self._show_timestamp))
        self.set_show_separators(d.get("show_separators", self._show_separators))
        self.set_separator_color(d.get("separator_color", self._separator_color))
        self.set_separator_thickness(d.get("separator_thickness", self._separator_thickness))
        self.set_boundary_separator_color(d.get("boundary_separator_color", self._boundary_separator_color))
        self.set_boundary_separator_thickness(d.get("boundary_separator_thickness", self._boundary_separator_thickness))
        self.set_auto_title_case(d.get("auto_title_case", self._auto_title_case))
        self.set_clean_sender_names(d.get("clean_sender_names", self._clean_sender_names))
        self.set_max_sender_words(d.get("max_sender_words", self._max_sender_words))
        self.set_sender_column_width(d.get("sender_column_width", self._sender_column_width))
        self.set_max_subject_words(d.get("max_subject_words", self._max_subject_words))
        self.set_max_subject_chars(d.get("max_subject_chars", self._max_subject_chars))
        self.set_show_unread_count_in_header(d.get("show_unread_count_in_header", self._show_unread_count_in_header))
        self.set_desaturate_when_no_unread(d.get("desaturate_when_no_unread", self._desaturate_when_no_unread))
        self.set_play_sound_on_new_mail(d.get("play_sound_on_new_mail", self._play_sound_on_new_mail))
        self.set_sound_file_path(d.get("sound_file_path", self._sound_file_path))
        self.set_sound_volume_percent(d.get("sound_volume_percent", self._sound_volume_percent))

    def set_gmail_position(self, position: Any) -> None:
        if isinstance(position, GmailPosition):
            gmail_position = position
        else:
            gmail_position = GmailPosition.from_string(str(position))
        self._gmail_position = gmail_position
        self.set_position(OverlayPosition.from_string(gmail_position.value))

    def _settings_width_value(self, settings: Any) -> Any:
        if hasattr(settings, "width"):
            return getattr(settings, "width")
        if hasattr(settings, "min_width"):
            return getattr(settings, "min_width")
        if hasattr(settings, "max_width"):
            return getattr(settings, "max_width")
        return self._width

    def set_width(self, width: Any) -> None:
        try:
            self._width = int(width)
        except (TypeError, ValueError):
            self._width = 600
        self._apply_width()

    def set_min_width(self, width: int) -> None:
        self.set_width(width)

    def set_max_width(self, width: int) -> None:
        self.set_width(width)

    def set_content_padding(self, left: int, right: int, top: int) -> None:
        self._content_padding_left = 0
        self._content_padding_right = 0
        self._content_padding_top = 0
        self._update_card_height_from_content(len(self._emails) or self._limit)
        self.update()
        self._update_position()

    def set_show_header_border(self, show: bool) -> None:
        self._show_header_border = bool(show)
        self._update_card_height_from_content(len(self._emails) or self._limit)
        self.update()

    def set_account_slot(self, slot: Any) -> None:
        text = str(slot or "0").strip()
        self._account_slot = text if text.isdigit() else "0"

    def set_limit(self, limit: int) -> None:
        self._limit = max(5, min(10, limit))
        self._update_card_height_from_content(self._limit)

    def set_refresh_interval(self, minutes: int) -> None:
        self._refresh_interval = timedelta(minutes=max(1, minutes))

    def set_show_sender(self, show: bool) -> None:
        self._show_sender = bool(show)
        self.update()

    def set_show_subject(self, show: bool) -> None:
        self._show_subject = bool(show)
        self.update()

    def set_show_envelope_icon(self, show: bool) -> None:
        self._show_envelope_icon = bool(show)
        self.update()

    def set_show_three_dot_menu(self, show: bool) -> None:
        self._show_three_dot_menu = bool(show)
        self.update()

    def set_show_timestamp(self, show: bool) -> None:
        self._show_timestamp = bool(show)
        self.update()

    def set_show_separators(self, show: bool) -> None:
        self._show_separators = bool(show)
        self.update()

    def set_separator_color(self, color: Any) -> None:
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            self._separator_color = QColor(*color)
        elif isinstance(color, QColor):
            self._separator_color = color
        self.update()

    def set_separator_thickness(self, thickness: int) -> None:
        self._separator_thickness = max(1, min(4, thickness))
        self.update()

    def set_boundary_separator_color(self, color: Any) -> None:
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            self._boundary_separator_color = QColor(*color)
        elif isinstance(color, QColor):
            self._boundary_separator_color = color
        self.update()

    def set_boundary_separator_thickness(self, thickness: int) -> None:
        self._boundary_separator_thickness = max(1, min(6, thickness))
        self.update()

    def set_auto_title_case(self, enable: bool) -> None:
        self._auto_title_case = bool(enable)
        self.update()

    def set_clean_sender_names(self, enable: bool) -> None:
        self._clean_sender_names = bool(enable)
        self.update()

    def set_max_sender_words(self, value: Any) -> None:
        self._max_sender_words = self._coerce_non_negative_int(value, 3)
        self.update()

    def set_sender_column_width(self, value: Any) -> None:
        try:
            self._sender_column_width = max(40, min(360, int(value)))
        except (TypeError, ValueError):
            self._sender_column_width = 180
        self.update()

    def set_max_subject_words(self, value: Any) -> None:
        self._max_subject_words = self._coerce_non_negative_int(value, 4)
        self.update()

    def set_max_subject_chars(self, value: Any) -> None:
        self._max_subject_chars = self._coerce_non_negative_int(value, 0)
        self.update()

    @staticmethod
    def _coerce_non_negative_int(value: Any, default: int) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return default

    def set_show_unread_count_in_header(self, show: bool) -> None:
        self._show_unread_count_in_header = bool(show)
        self.update()

    def set_desaturate_when_no_unread(self, desaturate: bool) -> None:
        self._desaturate_when_no_unread = bool(desaturate)
        self.update()

    # ------------------------------------------------------------------
    # Notification sound
    # ------------------------------------------------------------------

    def set_play_sound_on_new_mail(self, enabled: bool) -> None:
        self._play_sound_on_new_mail = bool(enabled)

    def set_sound_file_path(self, path: str) -> None:
        path = str(path or "")
        if path == self._sound_file_path:
            return
        self._sound_file_path = path
        # Push to singleton so the next play() picks up the change.
        try:
            from core.audio.notification_sound import NotificationSoundPlayer
            NotificationSoundPlayer.instance().set_file_path(path)
        except Exception as exc:
            logger.debug("[GMAIL] sound set_file_path defer failed: %s", exc)

    def set_sound_volume_percent(self, percent: int) -> None:
        try:
            value = max(0, min(100, int(percent)))
        except (TypeError, ValueError):
            value = 50
        if value == self._sound_volume_percent:
            return
        self._sound_volume_percent = value
        try:
            from core.audio.notification_sound import NotificationSoundPlayer
            NotificationSoundPlayer.instance().set_volume(value)
        except Exception as exc:
            logger.debug("[GMAIL] sound set_volume defer failed: %s", exc)
