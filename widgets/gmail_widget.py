"""Gmail overlay widget for screensaver."""
from __future__ import annotations

import threading
import math
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QMenu, QWidget

from core.gmail.gmail_backend import GmailBackend, GmailBackendMode
from core.gmail.gmail_client import EmailMetadata, GmailLabel
from core.gmail.gmail_deeplinks import gmail_inbox_url
from core.logging.logger import get_logger
from core.performance import record_widget_timer_result, widget_paint_sample, widget_timer_sample
from core.audio.sound_paths import default_notification_sound_path
from core.settings.storage_paths import get_app_data_dir
from core.threading.manager import ThreadManager
from core.windows.secure_url_launcher import open_url
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition, WidgetLifecycleState
from widgets.gmail_components import (
    GmailPosition,
    clean_sender_name,
    deserialize_email_cache,
    format_email_date,
    shorten_subject,
    smart_title_case_subject,
    serialize_email_cache,
)
from widgets.overlay_timers import create_overlay_timer, OverlayTimerHandle
from widgets.shadow_utils import (
    ShadowFadeProfile,
    draw_rounded_rect_with_shadow,
    draw_text_with_shadow,
    header_shadows_enabled,
    text_shadows_enabled,
)

logger = get_logger(__name__)


CACHE_MAX_AGE_HOURS = 72
CACHE_DIR = get_app_data_dir() / "cache"
CACHE_PATH = CACHE_DIR / "gmail_cache.json"
GMAIL_IMAGE_ASSETS = (
    "images/google-gmail.png",
    "images/gmail-envelope.png",
    "images/gmail-read.png",
    "images/gmail-archive.svg",
    "images/gmail-spam.png",
    "images/gmail-trash.png",
)
GMAIL_ACTION_ICON_PATHS = {
    "read": ("images/gmail-read.png",),
    "unread": ("images/gmail-envelope.png",),
    "archive": ("images/gmail-archive.svg",),
    "spam": ("images/gmail-spam.png",),
    "trash": ("images/gmail-trash.png",),
}


def _gmail_asset_path(relative_path: str) -> Path:
    """Resolve Gmail widget assets in script, onedir, and onefile builds."""
    rel = Path(relative_path)
    candidates = [
        Path.cwd() / rel,
        Path(getattr(sys, "argv", [""])[0]).resolve().parent / rel,
        Path(__file__).resolve().parents[1] / rel,
    ]
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except Exception:
            continue
    return candidates[-1]


class GmailWidget(BaseOverlayWidget):
    """Gmail overlay widget showing recent emails."""

    email_clicked = Signal(str)
    unread_count_changed = Signal(int)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        position: GmailPosition = GmailPosition.TOP_CENTER,
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
        self._group_threads = False
        self._show_sender = True
        self._show_subject = True
        self._show_envelope_icon = True
        self._show_three_dot_menu = True
        self._show_refresh_spiral = True
        self._show_timestamp = True
        self._date_display_mode = "relative"
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
        self._header_frame_pad_x = 10
        self._header_frame_pad_y = 6
        self._header_logo_gap = 8
        self._header_logo_y_offset = 2
        self._header_content_y_offset = -1

        self._header_logo_px_adjust = 0
        self._header_font_pt = max(6, int(self._font_size * 1.2))
        self._header_logo_size = max(12, int(self._header_font_pt * 1.3))
        self._row_vertical_spacing = 2

        self._brand_pixmap: Optional[QPixmap] = None
        self._brand_pixmap_desaturated: Optional[QPixmap] = None
        self._envelope_pixmap: Optional[QPixmap] = None
        self._envelope_pixmap_dim: Optional[QPixmap] = None
        self._envelope_read_pixmap: Optional[QPixmap] = None
        self._action_icons: Dict[str, Optional[QPixmap]] = {}
        self._cached_content_pixmap: Optional[QPixmap] = None
        self._cache_invalidated = True

        self._header_hit_rect: Optional[QRect] = None
        self._refresh_hit_rect: Optional[QRect] = None
        self._row_hit_rects: List[Tuple[QRect, str, str]] = []
        self._action_hit_rects: List[Tuple[QRect, str]] = []
        self._active_action_menu: Optional[QMenu] = None

        self._update_timer_handle: Optional[OverlayTimerHandle] = None
        self._update_timer: Optional[QTimer] = None
        self._fetch_in_progress = False
        self._fetch_lock = threading.Lock()
        self._fetch_generation = 0
        self._cancelled = False
        self._refreshing = False
        self._refresh_spin_angle = 0
        self._refresh_spin_timer: Optional[QTimer] = None
        self._refresh_spinner_suspended_for_transition = False
        self._deferred_fetch_timer: Optional[QTimer] = None
        self._deferred_refresh_timer: Optional[QTimer] = None
        self._pending_refresh_after_transition = False
        self._deferred_fetch_result: Optional[Tuple[List[EmailMetadata], int, Optional[int]]] = None
        self._deferred_fetch_error: Optional[Tuple[str, Optional[int]]] = None

        # New-mail detection: only fire sound for messages that arrive after
        # the first fetch of this session. Pre-existing unread on first fetch
        # is silently absorbed.
        self._seen_message_ids: Set[str] = set()
        self._seen_initialised: bool = False
        self._play_sound_on_new_mail: bool = False
        self._sound_file_path: str = default_notification_sound_path()
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
        self.setContentsMargins(20, 12, 20, 12)
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

    def _update_stylesheet(self) -> None:
        super()._update_stylesheet()

    def sizeHint(self) -> QSize:  # type: ignore[override]
        hint = super().sizeHint()
        width = self._width
        height = max(self.minimumHeight(), hint.height())
        return QSize(width, height)

    def _load_brand_pixmap(self) -> None:
        path = _gmail_asset_path("images/google-gmail.png")
        if path.exists():
            pm = QPixmap(str(path))
            if not pm.isNull():
                self._brand_pixmap = pm.scaled(
                    self._header_logo_size, self._header_logo_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._brand_pixmap_desaturated = self._desaturate_pixmap(self._brand_pixmap)
                return
        logger.warning("[GMAIL] Brand PNG missing: %s", path)
        self._brand_pixmap = None
        self._brand_pixmap_desaturated = None

    @staticmethod
    def _desaturate_pixmap(pixmap: QPixmap) -> Optional[QPixmap]:
        if pixmap.isNull():
            return None
        grayscale = pixmap.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
        return QPixmap.fromImage(grayscale)

    def _sync_header_metrics(self) -> None:
        base_font = max(6, int(self._font_size))
        media_header_font = max(6, int(base_font * 1.2))
        header_font = max(6, media_header_font + int(round(int(self._header_logo_px_adjust) / 1.3)))
        logo_size = max(12, int(header_font * 1.3))
        self._header_logo_size = logo_size
        self._header_font_pt = header_font

    def _load_envelope_pixmap(self) -> None:
        unread_path = _gmail_asset_path("images/gmail-envelope.png")
        read_path = _gmail_asset_path("images/gmail-read.png")
        target = 16

        if unread_path.exists():
            pm = QPixmap(str(unread_path))
            if not pm.isNull():
                self._envelope_pixmap = pm.scaled(
                    target, target,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

        if read_path.exists():
            read_pm = QPixmap(str(read_path))
            if not read_pm.isNull():
                self._envelope_read_pixmap = read_pm.scaled(
                    target, target,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

        if self._envelope_read_pixmap is None and unread_path.exists():
            pm = QPixmap(str(unread_path))
            if not pm.isNull():
                dim_img = pm.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
                self._envelope_pixmap_dim = QPixmap.fromImage(dim_img).scaled(
                    target, target,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._envelope_read_pixmap = self._envelope_pixmap_dim
        else:
            self._envelope_pixmap_dim = self._envelope_read_pixmap

        if self._envelope_pixmap is None:
            logger.warning("[GMAIL] Envelope PNG missing: %s", unread_path)
        if self._envelope_read_pixmap is None:
            logger.warning("[GMAIL] Read envelope PNG missing: %s", read_path)

    def _envelope_for_email(self, email: EmailMetadata) -> Optional[QPixmap]:
        return self._envelope_pixmap if email.is_unread else self._envelope_read_pixmap

    def _ensure_desaturated_brand(self) -> Optional[QPixmap]:
        if self._brand_pixmap is None:
            return None
        return self._brand_pixmap_desaturated

    def _load_action_icons(self) -> None:
        for key, path_options in GMAIL_ACTION_ICON_PATHS.items():
            loaded: Optional[QPixmap] = None
            for path_str in path_options:
                path = _gmail_asset_path(path_str)
                if path.exists():
                    pm = QPixmap(str(path))
                    if not pm.isNull():
                        loaded = pm.scaled(
                            16,
                            16,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        break
            if loaded is None:
                logger.warning("[GMAIL] Action icon missing or unreadable: %s", path_options)
            self._action_icons[key] = loaded

    def _action_icon(self, key: str) -> QIcon:
        pm = self._action_icons.get(key)
        if pm is None or pm.isNull():
            pm = self._fallback_action_pixmap(key)
            self._action_icons[key] = pm
        return QIcon(pm)

    @staticmethod
    def _fallback_action_pixmap(key: str) -> QPixmap:
        pm = QPixmap(16, 16)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor(235, 235, 235, 220), 1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            if key == "archive":
                painter.drawLine(3, 5, 13, 5)
                painter.drawLine(4, 5, 5, 3)
                painter.drawLine(5, 3, 11, 3)
                painter.drawLine(11, 3, 12, 5)
                painter.drawRect(3, 5, 10, 8)
                painter.drawLine(6, 8, 10, 8)
            elif key == "unread":
                painter.drawRect(2, 4, 12, 8)
                painter.drawLine(2, 4, 8, 9)
                painter.drawLine(14, 4, 8, 9)
            else:
                painter.drawEllipse(3, 3, 10, 10)
        finally:
            painter.end()
        return pm

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
            self._invalidate_content_cache_and_update()
            self._request_fade_in()
        else:
            self._update_card_height_from_content(1)
        self._schedule_timer()
        self._fetch_emails()
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
        if self._deferred_fetch_timer is not None:
            try:
                self._deferred_fetch_timer.stop()
            except Exception:
                pass
        if self._deferred_refresh_timer is not None:
            try:
                self._deferred_refresh_timer.stop()
            except Exception:
                pass
        self._pending_refresh_after_transition = False
        self._deferred_fetch_result = None
        self._deferred_fetch_error = None
        self._set_refreshing(False)
        self._cancelled = True
        self._fetch_generation += 1
        self._emails.clear()
        self._row_hit_rects.clear()
        self._action_hit_rects.clear()
        self._clear_content_cache()
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
        if self._deferred_fetch_timer is not None:
            try:
                self._deferred_fetch_timer.stop()
                self._deferred_fetch_timer.deleteLater()
            except Exception:
                pass
            self._deferred_fetch_timer = None
        if self._deferred_refresh_timer is not None:
            try:
                self._deferred_refresh_timer.stop()
                self._deferred_refresh_timer.deleteLater()
            except Exception:
                pass
            self._deferred_refresh_timer = None
        self._pending_refresh_after_transition = False
        self._deferred_fetch_result = None
        self._deferred_fetch_error = None
        self._set_refreshing(False)
        self._emails.clear()
        self._row_hit_rects.clear()
        self._action_hit_rects.clear()
        self._refresh_hit_rect = None
        self._clear_content_cache()
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

    def _fetch_emails(self, *, defer_for_transition: bool = True) -> bool:
        start_time = time.perf_counter()
        if defer_for_transition and self._defer_refresh_if_transition():
            record_widget_timer_result(
                self._perf_widget_name(),
                "gmail.refresh.dispatch",
                (time.perf_counter() - start_time) * 1000.0,
                None,
            )
            return True
        try:
            with self._fetch_lock:
                if self._fetch_in_progress:
                    logger.debug("[GMAIL] Fetch already in progress, skipping")
                    return False
                self._fetch_in_progress = True
            self._set_refreshing(True)
            # Re-acquire client from backend each fetch in case mode/credentials changed
            self._gmail_client = self._backend.client if self._backend.is_authenticated else None
            if self._gmail_client is None:
                with self._fetch_lock:
                    self._fetch_in_progress = False
                self._set_refreshing(False)
                logger.debug("[GMAIL] Not authenticated, skipping fetch")
                self._last_error = "auth"
                self._invalidate_content_cache_and_update()
                return False
            try:
                if self._ensure_thread_manager("GmailWidget._fetch_emails"):
                    generation = self._fetch_generation
                    self._thread_manager.submit_io_task(self._fetch_emails_async, generation)
                else:
                    self._fetch_emails_sync()
            except Exception:
                self._fetch_emails_sync()
            return True
        finally:
            record_widget_timer_result(
                self._perf_widget_name(),
                "gmail.refresh.dispatch",
                (time.perf_counter() - start_time) * 1000.0,
                None,
            )

    def _perf_widget_name(self) -> str:
        try:
            overlay_name = getattr(self, "_overlay_name", None)
            if overlay_name:
                return str(overlay_name)
        except Exception:
            pass
        return "GmailWidget"

    def _set_refreshing(self, refreshing: bool) -> None:
        refreshing = bool(refreshing)
        if refreshing == self._refreshing:
            return
        self._refreshing = refreshing
        if refreshing:
            self._refresh_spinner_suspended_for_transition = self._parent_transition_running()
            if self._refresh_spin_timer is None:
                self._refresh_spin_timer = QTimer(self)
                self._refresh_spin_timer.timeout.connect(self._advance_refresh_spinner)
            if not self._refresh_spinner_suspended_for_transition:
                self._refresh_spin_timer.start(80)
        else:
            self._refresh_spinner_suspended_for_transition = False
            if self._refresh_spin_timer is not None:
                self._refresh_spin_timer.stop()
            self._refresh_spin_angle = 0
        self._update_refresh_button_region()

    def _advance_refresh_spinner(self) -> None:
        if not self._refreshing or self._refresh_spinner_suspended_for_transition or self._parent_transition_running():
            if self._refresh_spin_timer is not None:
                self._refresh_spin_timer.stop()
            self._refresh_spinner_suspended_for_transition = bool(self._refreshing)
            return
        self._refresh_spin_angle = (self._refresh_spin_angle + 30) % 360
        self._update_refresh_button_region()

    def _update_refresh_button_region(self) -> None:
        if self._refresh_hit_rect is not None:
            self.update(self._refresh_hit_rect.adjusted(-2, -2, 2, 2))
        else:
            self.update()

    def _parent_transition_running(self) -> bool:
        parent = self.parent()
        while parent is not None:
            try:
                has_pending = getattr(parent, "has_transition_work_pending", None)
                if callable(has_pending) and bool(has_pending()):
                    return True
                has_running = getattr(parent, "has_running_transition", None)
                if callable(has_running) and bool(has_running()):
                    return True
            except Exception:
                return False
            parent = parent.parent() if hasattr(parent, "parent") else None
        return False

    def on_parent_transition_work_pending(self, pending: bool) -> None:
        """Pause live refresh animation as soon as a transition is requested."""
        if not self._refreshing:
            return
        transition_busy = bool(pending) or self._parent_transition_running()
        if transition_busy:
            self._refresh_spinner_suspended_for_transition = True
            if self._refresh_spin_timer is not None and self._refresh_spin_timer.isActive():
                self._refresh_spin_timer.stop()
            self._update_refresh_button_region()
            return
        if self._refresh_spinner_suspended_for_transition:
            self._refresh_spinner_suspended_for_transition = False
            if self._refresh_spin_timer is not None and not self._refresh_spin_timer.isActive():
                self._refresh_spin_timer.start(80)
            self._update_refresh_button_region()

    def _defer_refresh_if_transition(self) -> bool:
        if not self._parent_transition_running():
            return False
        self._pending_refresh_after_transition = True
        self._schedule_deferred_refresh()
        logger.debug("[GMAIL] Deferred email refresh until active transition finishes")
        return True

    def _schedule_deferred_refresh(self) -> None:
        if self._deferred_refresh_timer is None:
            self._deferred_refresh_timer = QTimer(self)
            self._deferred_refresh_timer.setSingleShot(True)
            self._deferred_refresh_timer.timeout.connect(self._flush_deferred_refresh)
        if not self._deferred_refresh_timer.isActive():
            self._deferred_refresh_timer.start(250)

    def _flush_deferred_refresh(self) -> None:
        if self._cancelled:
            self._pending_refresh_after_transition = False
            return
        if not self._pending_refresh_after_transition:
            return
        if self._parent_transition_running():
            self._schedule_deferred_refresh()
            return
        self._pending_refresh_after_transition = False
        self._fetch_emails(defer_for_transition=False)

    def _defer_fetch_result_if_transition(
        self,
        emails: List[EmailMetadata],
        unread_count: int,
        generation: Optional[int],
    ) -> bool:
        if not self._parent_transition_running():
            return False
        self._deferred_fetch_result = (list(emails), int(unread_count), generation)
        self._deferred_fetch_error = None
        self._schedule_deferred_fetch_flush()
        logger.debug("[GMAIL] Deferred fetched mail apply until active transition finishes")
        return True

    def _defer_fetch_error_if_transition(
        self,
        error_msg: str,
        generation: Optional[int],
    ) -> bool:
        if not self._parent_transition_running():
            return False
        self._deferred_fetch_error = (str(error_msg), generation)
        self._deferred_fetch_result = None
        self._schedule_deferred_fetch_flush()
        logger.debug("[GMAIL] Deferred fetch error display until active transition finishes")
        return True

    def _schedule_deferred_fetch_flush(self) -> None:
        if self._deferred_fetch_timer is None:
            self._deferred_fetch_timer = QTimer(self)
            self._deferred_fetch_timer.setSingleShot(True)
            self._deferred_fetch_timer.timeout.connect(self._flush_deferred_fetch_result)
        if not self._deferred_fetch_timer.isActive():
            self._deferred_fetch_timer.start(250)

    def _flush_deferred_fetch_result(self) -> None:
        if self._cancelled:
            self._deferred_fetch_result = None
            self._deferred_fetch_error = None
            return
        if self._parent_transition_running():
            self._schedule_deferred_fetch_flush()
            return
        if self._deferred_fetch_error is not None:
            error_msg, generation = self._deferred_fetch_error
            self._deferred_fetch_error = None
            self._on_fetch_error(error_msg, generation, defer_for_transition=False)
            return
        if self._deferred_fetch_result is not None:
            emails, unread_count, generation = self._deferred_fetch_result
            self._deferred_fetch_result = None
            self._on_emails_fetched(emails, unread_count, generation, defer_for_transition=False)

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
        self,
        emails: List[EmailMetadata],
        unread_count: int,
        generation: Optional[int] = None,
        *,
        defer_for_transition: bool = True,
    ) -> None:
        with widget_timer_sample(self, "gmail.fetch.apply"):
            self._on_emails_fetched_impl(
                emails,
                unread_count,
                generation,
                defer_for_transition=defer_for_transition,
            )

    def _on_emails_fetched_impl(
        self,
        emails: List[EmailMetadata],
        unread_count: int,
        generation: Optional[int] = None,
        *,
        defer_for_transition: bool = True,
    ) -> None:
        if self._cancelled:
            return
        if generation is not None and generation != self._fetch_generation:
            return
        self._set_refreshing(False)
        if defer_for_transition and self._defer_fetch_result_if_transition(emails, unread_count, generation):
            return
        display_emails = list(emails)
        if (
            self._has_displayed_valid_data
            and self._last_error is None
            and display_emails == self._emails
            and unread_count == self._unread_count
        ):
            logger.debug("[GMAIL] Fetched mail unchanged; skipping cache write and repaint")
            return
        self._emails = display_emails
        self._last_error = None
        self._detect_new_mail(emails)
        if unread_count != self._unread_count:
            self._unread_count = unread_count
            self.unread_count_changed.emit(unread_count)
        if display_emails:
            self._has_displayed_valid_data = True
            self._write_email_cache_deferred(display_emails)
            self._update_card_height_from_content(len(display_emails))
            self._invalidate_content_cache_and_update()
            if not self.isVisible():
                self._request_fade_in()
        else:
            self._update_card_height_from_content(1)
            self._invalidate_content_cache_and_update()
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

    def _on_fetch_error(
        self,
        error_msg: str,
        generation: Optional[int] = None,
        *,
        defer_for_transition: bool = True,
    ) -> None:
        with widget_timer_sample(self, "gmail.fetch.error_apply"):
            self._on_fetch_error_impl(
                error_msg,
                generation,
                defer_for_transition=defer_for_transition,
            )

    def _on_fetch_error_impl(
        self,
        error_msg: str,
        generation: Optional[int] = None,
        *,
        defer_for_transition: bool = True,
    ) -> None:
        if self._cancelled:
            return
        if generation is not None and generation != self._fetch_generation:
            return
        self._set_refreshing(False)
        if defer_for_transition and self._defer_fetch_error_if_transition(error_msg, generation):
            return
        self._last_error = error_msg
        logger.warning("[GMAIL] Displaying error state: %s", error_msg)
        self._update_card_height_from_content(1)
        self._invalidate_content_cache_and_update()

    # ------------------------------------------------------------------
    # Email Cache
    # ------------------------------------------------------------------

    def _load_email_cache(self) -> Optional[List[EmailMetadata]]:
        if not CACHE_PATH.exists():
            return None
        mtime = datetime.fromtimestamp(CACHE_PATH.stat().st_mtime)
        if datetime.now() - mtime > timedelta(hours=CACHE_MAX_AGE_HOURS):
            logger.debug("[GMAIL] Cache stale (>%dh), ignoring", CACHE_MAX_AGE_HOURS)
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
        with widget_timer_sample(self, "gmail.cache.write"):
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                tmp = CACHE_PATH.with_suffix(".tmp")
                tmp.write_text(serialize_email_cache(emails), encoding="utf-8")
                tmp.replace(CACHE_PATH)
            except Exception as e:
                logger.warning("[GMAIL] Failed to write cache: %s", e)

    def _write_email_cache_deferred(self, emails: List[EmailMetadata]) -> None:
        cache_emails = list(emails)
        try:
            if self._ensure_thread_manager("GmailWidget._write_email_cache"):
                self._thread_manager.submit_io_task(self._write_email_cache, cache_emails)
                return
        except Exception as exc:
            logger.debug("[GMAIL] Cache write IO dispatch failed: %s", exc)
        self._write_email_cache(cache_emails)

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
        with widget_paint_sample(self, "gmail.paint"):
            super().paintEvent(event)
            self._paint_cached_content()

    def _paint_cached_content(self) -> None:
        widget_size = self.size()
        cache_valid = False
        if self._cached_content_pixmap is not None and not self._cached_content_pixmap.isNull():
            try:
                cached_dpr = self._cached_content_pixmap.devicePixelRatio()
                cached_w = int(self._cached_content_pixmap.width() / cached_dpr)
                cached_h = int(self._cached_content_pixmap.height() / cached_dpr)
                cache_valid = (
                    abs(cached_w - widget_size.width()) <= 2
                    and abs(cached_h - widget_size.height()) <= 2
                )
            except Exception:
                cache_valid = False

        if self._cache_invalidated or not cache_valid:
            self._regenerate_content_cache(widget_size)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        try:
            if self._cached_content_pixmap is not None and not self._cached_content_pixmap.isNull():
                painter.drawPixmap(0, 0, self._cached_content_pixmap)
            if self._show_refresh_spiral:
                self._paint_refresh_button(painter)
            else:
                self._refresh_hit_rect = None
        finally:
            painter.end()

    def _regenerate_content_cache(self, size: QSize) -> None:
        """Regenerate stable Gmail content without touching widget effects."""
        if size.width() <= 0 or size.height() <= 0:
            self._clear_content_cache()
            return
        with widget_timer_sample(self, "gmail.cache.regen"):
            try:
                dpr = self.devicePixelRatioF()
            except Exception:
                dpr = 1.0
            pixmap = QPixmap(max(1, int(size.width() * dpr)), max(1, int(size.height() * dpr)))
            pixmap.setDevicePixelRatio(dpr)
            pixmap.fill(Qt.GlobalColor.transparent)

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            try:
                self._paint_stable_content(painter)
            finally:
                painter.end()
            self._cached_content_pixmap = pixmap
            self._cache_invalidated = False

    def _paint_stable_content(self, painter: QPainter) -> None:
        self._row_hit_rects.clear()
        self._action_hit_rects.clear()
        self._paint_header(painter)
        if self._last_error:
            self._paint_error_state(painter)
        elif not self._emails:
            self._paint_empty_state(painter)
        else:
            self._paint_emails(painter)

    def _invalidate_content_cache(self) -> None:
        self._cache_invalidated = True

    def _invalidate_content_cache_and_update(self) -> None:
        self._invalidate_content_cache()
        self.update()

    def _clear_content_cache(self) -> None:
        self._cached_content_pixmap = None
        self._cache_invalidated = True

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._invalidate_content_cache()

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
        draw_text_with_shadow(
            painter,
            layout["text_x"],
            layout["text_baseline_y"],
            header_text,
            font_size=header_font_pt,
            enabled=text_shadows_enabled(self._shadow_config),
        )
        self._header_hit_rect = QRect(layout["frame_rect"])

    def _paint_refresh_button(self, painter: QPainter) -> None:
        margins = self.contentsMargins()
        size = 22
        right = self.width() - margins.right() - self._content_padding_right
        top = margins.top() + self._content_padding_top
        rect = QRect(max(0, right - size), top, size, size)
        self._refresh_hit_rect = rect

        painter.save()
        try:
            color = QColor(170, 170, 170, 190)
            if self._refreshing:
                color = QColor(210, 210, 210, 230)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(color, 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            center = rect.center()
            max_radius = max(4.0, (min(rect.width(), rect.height()) / 2.0) - 3.0)
            path = QPainterPath()
            steps = 44
            for index in range(steps):
                progress = index / float(steps - 1)
                radius = 1.1 + progress * (max_radius - 1.1)
                angle = math.radians(self._refresh_spin_angle + 30 + progress * 620)
                x = center.x() + math.cos(angle) * radius
                y = center.y() + math.sin(angle) * radius
                if index == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            painter.drawPath(path)
        finally:
            painter.restore()

    def _header_text(self) -> str:
        if self._show_unread_count_in_header and self._unread_count > 0:
            return f"Gmail ( {self._unread_count} )"
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
        content_y_offset = int(self._header_content_y_offset)
        logo_y = int(center_y - (logo_height / 2)) + int(self._header_logo_y_offset) + content_y_offset
        text_x = logo_x + logo_width + self._header_logo_gap
        text_baseline_y = int(center_y - (text_height / 2) + fm.ascent()) + content_y_offset + 1
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
        border_width = max(2, max(1, self._bg_border_width) - 3)
        draw_rounded_rect_with_shadow(
            painter,
            frame_rect,
            radius,
            self._bg_border_color,
            border_width,
            shadow_enabled=header_shadows_enabled(self._shadow_config),
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
            time_font = QFont(self._font_family, base_font_pt - 5, QFont.Weight.Normal)
            time_fm = QFontMetrics(time_font)
            time_slot_width = max(
                (time_fm.horizontalAdvance(self._format_email_date(email.date)) + 8 for email in visible_emails),
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
            subject_weight = QFont.Weight(600) if email.is_unread else QFont.Weight(400)
            sender_weight = QFont.Weight(680) if email.is_unread else QFont.Weight(550)
            time_width = time_slot_width
            time_text = ""
            if self._show_timestamp:
                time_font = QFont(self._font_family, base_font_pt - 5, QFont.Weight.Normal)
                painter.setFont(time_font)
                time_text = self._format_email_date(email.date)
            env_x = left
            env_width = env_slot_width
            # Pre-compute line height so we can vertically centre the envelope
            subject_font = QFont(self._font_family, base_font_pt, subject_weight)
            subject_fm = QFontMetrics(subject_font)
            line_height = subject_fm.height() + 6
            if self._show_envelope_icon and self._envelope_pixmap is not None:
                env_pm = self._envelope_for_email(email)
                if env_pm is not None:
                    line_centre = row_y + (line_height * 0.5)
                    icon_half = float(env_pm.height()) / 2.0
                    env_y = int(line_centre - icon_half)
                    # Clamp so icon never sits above row or below row bottom
                    env_y = max(row_y, min(env_y, row_y + line_height - env_pm.height()))
                    painter.drawPixmap(env_x, env_y, env_pm)
            sender_width = 0
            if self._show_sender:
                sender_font = QFont(self._font_family, base_font_pt, sender_weight)
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
            subject_font = QFont(self._font_family, base_font_pt, subject_weight)
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
                painter.setFont(QFont(self._font_family, base_font_pt - 5, QFont.Weight.Normal))
                painter.setPen(QColor(180, 180, 180, 200))
                time_x = env_x + env_width
                draw_text_with_shadow(
                    painter,
                    time_x,
                    text_y - 2,
                    time_text,
                    font_size=base_font_pt,
                    enabled=text_shadows_enabled(self._shadow_config),
                )
            if self._show_sender:
                painter.setFont(QFont(self._font_family, base_font_pt, sender_weight))
                painter.setPen(
                    QColor(200, 200, 200, 255)
                    if email.is_unread
                    else QColor(180, 180, 180, 220)
                )
                sender_x = env_x + env_width + time_width
                draw_text_with_shadow(
                    painter,
                    sender_x,
                    text_y,
                    sender_text,
                    font_size=base_font_pt,
                    enabled=text_shadows_enabled(self._shadow_config),
                )
            if self._show_subject:
                painter.setFont(subject_font)
                painter.setPen(
                    QColor(255, 255, 255, 255)
                    if email.is_unread
                    else QColor(220, 220, 220, 230)
                )
                subject_x = env_x + env_width + time_width + sender_width
                draw_text_with_shadow(
                    painter,
                    subject_x,
                    text_y,
                    subject_text,
                    font_size=base_font_pt,
                    enabled=text_shadows_enabled(self._shadow_config),
                )
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

    def _is_interactive_point(self, local_pos: QPoint) -> bool:
        if self._show_refresh_spiral and self._refresh_hit_rect is not None and self._refresh_hit_rect.contains(local_pos):
            return True
        if self._header_hit_rect is not None and self._header_hit_rect.contains(local_pos):
            return True
        if self.is_action_menu_point(local_pos):
            return True
        if any(rect.contains(local_pos) for rect, _message_id, _subject in self._row_hit_rects):
            return True
        return False

    def is_action_menu_point(self, local_pos: QPoint) -> bool:
        return any(rect.contains(local_pos) for rect, _message_id in self._action_hit_rects)

    def is_action_menu_visible(self) -> bool:
        menu = self._active_action_menu
        return bool(menu is not None and menu.isVisible())

    def handle_click(self, local_pos: QPoint) -> bool:
        if self._show_refresh_spiral and self._refresh_hit_rect is not None and self._refresh_hit_rect.contains(local_pos):
            self._fetch_emails()
            return True

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

    def handle_double_click(self, local_pos: QPoint) -> bool:
        if not self._enabled:
            return False
        if self._is_interactive_point(local_pos):
            return False
        try:
            started = self._fetch_emails()
            if started:
                logger.debug("[GMAIL] Blank-space double-click triggered email refresh")
            return True
        except Exception:
            logger.debug("[GMAIL] Double-click refresh failed", exc_info=True)
            return False

    def resolve_click_target(self, local_pos: QPoint) -> Optional[str]:
        """Return a Gmail URL for central MC/SCR click routing, without opening it."""
        if self._last_error:
            return None

        if self._show_refresh_spiral and self._refresh_hit_rect is not None and self._refresh_hit_rect.contains(local_pos):
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
        if self._active_action_menu is not None:
            try:
                self._active_action_menu.close()
            except Exception:
                pass
            self._active_action_menu = None

        menu = QMenu(self)
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        menu.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
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
            action_read.setIcon(self._action_icon("read"))
            action_read.triggered.connect(
                lambda _checked=False, mid=action_message_id: self._dispatch_action(widget_ref, self._do_mark_as_read, mid)
            )
        else:
            action_unread = menu.addAction("Mark as Unread")
            action_unread.setIcon(self._action_icon("unread"))
            action_unread.triggered.connect(
                lambda _checked=False, mid=action_message_id: self._dispatch_action(widget_ref, self._do_mark_as_unread, mid)
            )

        if self._should_show_archive_action(email):
            action_archive = menu.addAction("Archive")
            action_archive.setIcon(self._action_icon("archive"))
            action_archive.triggered.connect(
                lambda _checked=False, mid=action_message_id: self._dispatch_action(widget_ref, self._do_archive, mid)
            )

        action_spam = menu.addAction("Mark as Spam")
        action_spam.setIcon(self._action_icon("spam"))
        action_spam.triggered.connect(
            lambda _checked=False, mid=action_message_id: self._dispatch_action(widget_ref, self._do_spam, mid)
        )

        action_trash = menu.addAction("Delete")
        action_trash.setIcon(self._action_icon("trash"))
        action_trash.triggered.connect(
            lambda _checked=False, mid=action_message_id: self._dispatch_action(widget_ref, self._do_trash, mid)
        )

        global_pos = self.mapToGlobal(local_pos)
        self._active_action_menu = menu
        menu.aboutToHide.connect(lambda: setattr(self, "_active_action_menu", None))
        menu.popup(global_pos)

    @staticmethod
    def _action_message_id(email: EmailMetadata) -> str:
        if email.provider in {"gmail", "imap"} and email.imap_uid:
            return email.imap_uid
        return email.id

    def _should_show_archive_action(self, email: EmailMetadata) -> bool:
        """Hide Archive for IMAP; keep the action code for future OAuth/diagnostic work."""
        try:
            if self._backend.mode == GmailBackendMode.IMAP:
                return False
        except Exception:
            pass
        try:
            client_name = type(self._gmail_client).__name__.lower()
            if "imap" in client_name:
                return False
        except Exception:
            pass
        return email.provider != "imap"

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
        else:
            logger.warning("[GMAIL] Mark as read failed for %s", message_id)

    def _do_mark_as_unread(self, message_id: str) -> None:
        if self._gmail_client and self._gmail_client.mark_as_unread(message_id):
            logger.info("[GMAIL] Marked %s as unread", message_id)
            try:
                ThreadManager.run_on_ui_thread(self._fetch_emails)
            except Exception:
                pass
        else:
            logger.warning("[GMAIL] Mark as unread failed for %s", message_id)

    def _do_archive(self, message_id: str) -> None:
        """Archive action code is retained for OAuth/future diagnostics, but hidden for IMAP."""
        if self._gmail_client and self._gmail_client.archive_message(message_id):
            logger.info("[GMAIL] Archived %s", message_id)
            try:
                ThreadManager.run_on_ui_thread(self._fetch_emails)
            except Exception:
                pass
        else:
            logger.warning("[GMAIL] Archive failed for %s", message_id)

    def _do_spam(self, message_id: str) -> None:
        if self._gmail_client and self._gmail_client.spam_message(message_id):
            logger.info("[GMAIL] Marked %s as spam", message_id)
            try:
                ThreadManager.run_on_ui_thread(self._fetch_emails)
            except Exception:
                pass
        else:
            logger.warning("[GMAIL] Spam failed for %s", message_id)

    def _do_trash(self, message_id: str) -> None:
        if self._gmail_client and self._gmail_client.trash_message(message_id):
            logger.info("[GMAIL] Trashed %s", message_id)
            try:
                ThreadManager.run_on_ui_thread(self._fetch_emails)
            except Exception:
                pass
        else:
            logger.warning("[GMAIL] Trash failed for %s", message_id)

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
        self.set_header_logo_px_adjust(getattr(settings, "header_logo_px_adjust", self._header_logo_px_adjust))
        self.set_account_slot(getattr(settings, "account_slot", self._account_slot))
        self.set_limit(getattr(settings, "limit", self._limit))
        self.set_refresh_interval(getattr(settings, "refresh_minutes", 5))
        self.set_group_threads(getattr(settings, "group_threads", self._group_threads))
        self.set_show_sender(getattr(settings, "show_sender", self._show_sender))
        self.set_show_subject(getattr(settings, "show_subject", self._show_subject))
        self.set_show_envelope_icon(getattr(settings, "show_envelope_icon", self._show_envelope_icon))
        self.set_show_three_dot_menu(getattr(settings, "show_three_dot_menu", self._show_three_dot_menu))
        self.set_show_refresh_spiral(getattr(settings, "show_refresh_spiral", self._show_refresh_spiral))
        self.set_show_timestamp(getattr(settings, "show_timestamp", self._show_timestamp))
        self.set_date_display_mode(getattr(settings, "date_display_mode", self._date_display_mode))
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
        self.set_header_logo_px_adjust(d.get("header_logo_px_adjust", self._header_logo_px_adjust))
        self.set_account_slot(d.get("account_slot", self._account_slot))
        self.set_limit(d.get("limit", self._limit))
        self.set_refresh_interval(d.get("refresh_minutes", 5))
        self.set_group_threads(d.get("group_threads", self._group_threads))
        self.set_show_sender(d.get("show_sender", self._show_sender))
        self.set_show_subject(d.get("show_subject", self._show_subject))
        self.set_show_envelope_icon(d.get("show_envelope_icon", self._show_envelope_icon))
        self.set_show_three_dot_menu(d.get("show_three_dot_menu", self._show_three_dot_menu))
        self.set_show_refresh_spiral(d.get("show_refresh_spiral", self._show_refresh_spiral))
        self.set_show_timestamp(d.get("show_timestamp", self._show_timestamp))
        self.set_date_display_mode(d.get("date_display_mode", self._date_display_mode))
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
            next_width = int(width)
        except (TypeError, ValueError):
            next_width = 600
        if self._width == max(200, min(1200, next_width)):
            return
        self._width = next_width
        self._apply_width()
        self._invalidate_content_cache_and_update()

    def set_min_width(self, width: int) -> None:
        self.set_width(width)

    def set_max_width(self, width: int) -> None:
        self.set_width(width)

    def _set_attr_and_update(self, attr: str, value: Any) -> bool:
        if getattr(self, attr) == value:
            return False
        setattr(self, attr, value)
        self._invalidate_content_cache_and_update()
        return True

    def set_show_background(self, show: bool) -> None:
        super().set_show_background(show)

    def set_background_color(self, color: QColor) -> None:
        super().set_background_color(color)

    def set_background_opacity(self, opacity: float) -> None:
        super().set_background_opacity(opacity)

    def set_background_border(self, width: int, color: QColor) -> None:
        super().set_background_border(width, color)

    def set_background_corner_radius(self, radius: int) -> None:
        super().set_background_corner_radius(radius)

    def set_shadow_config(self, config: Optional[Dict[str, Any]]) -> None:
        super().set_shadow_config(config)

    def on_fade_complete(self) -> None:
        super().on_fade_complete()

    def set_content_padding(self, left: int, right: int, top: int) -> None:
        if (
            self._content_padding_left == 0
            and self._content_padding_right == 0
            and self._content_padding_top == 0
        ):
            return
        self._content_padding_left = 0
        self._content_padding_right = 0
        self._content_padding_top = 0
        self._update_card_height_from_content(len(self._emails) or self._limit)
        self._invalidate_content_cache_and_update()
        self._update_position()

    def set_show_header_border(self, show: bool) -> None:
        show = bool(show)
        if self._show_header_border == show:
            return
        self._show_header_border = show
        self._update_card_height_from_content(len(self._emails) or self._limit)
        self._invalidate_content_cache_and_update()

    def set_font_size(self, size: int) -> None:
        super().set_font_size(size)
        self._sync_header_metrics()
        self._load_brand_pixmap()
        self._update_card_height_from_content(len(self._emails) or self._limit)
        self._invalidate_content_cache_and_update()

    def set_header_logo_px_adjust(self, value: Any) -> None:
        try:
            adjust = int(value)
        except (TypeError, ValueError):
            adjust = 0
        adjust = max(-12, min(24, adjust))
        if self._header_logo_px_adjust == adjust:
            return
        self._header_logo_px_adjust = adjust
        self._sync_header_metrics()
        self._load_brand_pixmap()
        self._update_card_height_from_content(len(self._emails) or self._limit)
        self._invalidate_content_cache_and_update()

    def set_account_slot(self, slot: Any) -> None:
        text = str(slot or "0").strip()
        next_slot = text if text.isdigit() else "0"
        if self._account_slot == next_slot:
            return
        self._account_slot = next_slot

    def set_limit(self, limit: int) -> None:
        next_limit = max(5, min(10, limit))
        if self._limit == next_limit:
            return
        self._limit = next_limit
        self._update_card_height_from_content(self._limit)
        self._invalidate_content_cache_and_update()

    def set_refresh_interval(self, minutes: int) -> None:
        next_interval = timedelta(minutes=max(1, minutes))
        if self._refresh_interval == next_interval:
            return
        self._refresh_interval = next_interval

    def set_group_threads(self, enabled: bool) -> None:
        self._set_attr_and_update("_group_threads", bool(enabled))

    def set_show_sender(self, show: bool) -> None:
        self._set_attr_and_update("_show_sender", bool(show))

    def set_show_subject(self, show: bool) -> None:
        self._set_attr_and_update("_show_subject", bool(show))

    def set_show_envelope_icon(self, show: bool) -> None:
        self._set_attr_and_update("_show_envelope_icon", bool(show))

    def set_show_three_dot_menu(self, show: bool) -> None:
        self._set_attr_and_update("_show_three_dot_menu", bool(show))

    def set_show_refresh_spiral(self, show: bool) -> None:
        show = bool(show)
        if self._show_refresh_spiral == show:
            return
        self._show_refresh_spiral = show
        self._update_refresh_button_region()

    def set_show_timestamp(self, show: bool) -> None:
        self._set_attr_and_update("_show_timestamp", bool(show))

    def set_date_display_mode(self, mode: Any) -> None:
        normalized = str(mode or "relative").strip().lower()
        if normalized not in {"relative", "numeric", "words"}:
            normalized = "relative"
        self._set_attr_and_update("_date_display_mode", normalized)

    def _format_email_date(self, dt: datetime) -> str:
        return format_email_date(dt, self._date_display_mode)

    def set_show_separators(self, show: bool) -> None:
        self._set_attr_and_update("_show_separators", bool(show))

    def set_separator_color(self, color: Any) -> None:
        next_color = self._separator_color
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            next_color = QColor(*color)
        elif isinstance(color, QColor):
            next_color = color
        self._set_attr_and_update("_separator_color", next_color)

    def set_separator_thickness(self, thickness: int) -> None:
        self._set_attr_and_update("_separator_thickness", max(1, min(4, thickness)))

    def set_boundary_separator_color(self, color: Any) -> None:
        next_color = self._boundary_separator_color
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            next_color = QColor(*color)
        elif isinstance(color, QColor):
            next_color = color
        self._set_attr_and_update("_boundary_separator_color", next_color)

    def set_boundary_separator_thickness(self, thickness: int) -> None:
        self._set_attr_and_update("_boundary_separator_thickness", max(1, min(6, thickness)))

    def set_auto_title_case(self, enable: bool) -> None:
        self._set_attr_and_update("_auto_title_case", bool(enable))

    def set_clean_sender_names(self, enable: bool) -> None:
        self._set_attr_and_update("_clean_sender_names", bool(enable))

    def set_max_sender_words(self, value: Any) -> None:
        self._set_attr_and_update("_max_sender_words", self._coerce_non_negative_int(value, 3))

    def set_sender_column_width(self, value: Any) -> None:
        try:
            next_width = max(40, min(360, int(value)))
        except (TypeError, ValueError):
            next_width = 180
        self._set_attr_and_update("_sender_column_width", next_width)

    def set_max_subject_words(self, value: Any) -> None:
        self._set_attr_and_update("_max_subject_words", self._coerce_non_negative_int(value, 4))

    def set_max_subject_chars(self, value: Any) -> None:
        self._set_attr_and_update("_max_subject_chars", self._coerce_non_negative_int(value, 0))

    @staticmethod
    def _coerce_non_negative_int(value: Any, default: int) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return default

    def set_show_unread_count_in_header(self, show: bool) -> None:
        self._set_attr_and_update("_show_unread_count_in_header", bool(show))

    def set_desaturate_when_no_unread(self, desaturate: bool) -> None:
        self._set_attr_and_update("_desaturate_when_no_unread", bool(desaturate))

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
