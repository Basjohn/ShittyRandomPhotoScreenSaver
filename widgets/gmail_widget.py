"""Gmail overlay widget for screensaver."""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QWidget

from core.gmail.gmail_client import EmailMetadata, GmailClient, GmailLabel
from core.gmail.gmail_oauth import GmailOAuthManager
from core.logging.logger import get_logger
from core.settings.storage_paths import get_app_data_dir
from core.threading.manager import ThreadManager
from core.windows.secure_url_launcher import open_url
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition, WidgetLifecycleState
from widgets.gmail_components import (
    GmailPosition,
    _format_relative_time,
    _smart_title_case,
    deserialize_email_cache,
    serialize_email_cache,
)
from widgets.overlay_timers import create_overlay_timer, OverlayTimerHandle
from widgets.shadow_utils import ShadowFadeProfile

logger = get_logger(__name__)

CACHE_MAX_AGE_HOURS = 24
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
        overlay_pos = OverlayPosition(position.value)
        super().__init__(parent, position=overlay_pos, overlay_name="gmail")
        self._gmail_position = position

        self._oauth_manager: GmailOAuthManager = GmailOAuthManager.instance()
        self._gmail_client: Optional[GmailClient] = None
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
        self._show_unread_count_in_header = True
        self._desaturate_when_no_unread = True

        self._header_font_pt = max(10, int(self._font_size) + 2)
        self._header_logo_size = 24
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
        self.setMinimumWidth(400)
        self.setMinimumHeight(120)

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
        if self._oauth_manager.is_authenticated:
            self._gmail_client = GmailClient(self._oauth_manager)
        cached = self._load_email_cache()
        if cached:
            self._emails = cached
            self._unread_count = sum(1 for e in self._emails if e.is_unread)
            self._has_displayed_valid_data = True
            self._update_card_height_from_content(len(self._emails))
            self.update()
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
        if self._gmail_client is None or not self._oauth_manager.is_authenticated:
            with self._fetch_lock:
                self._fetch_in_progress = False
            logger.debug("[GMAIL] Not authenticated, skipping fetch")
            self._last_error = "auth"
            self.update()
            return
        try:
            ThreadManager().submit_io_task(self._fetch_emails_async)
        except Exception:
            self._fetch_emails_sync()

    def _fetch_emails_async(self) -> None:
        try:
            label_ids = [self._filter_label]
            emails = self._gmail_client.list_messages(
                max_results=self._limit, label_ids=label_ids
            )
            unread = sum(1 for e in emails if e.is_unread)
            try:
                ThreadManager().invoke_in_ui_thread(
                    lambda: self._on_emails_fetched(emails, unread)
                )
            except Exception:
                logger.critical("[GMAIL] invoke_in_ui_thread failed, dropping fetch result")
        except Exception as exc:
            logger.error("[GMAIL] Fetch failed: %s", exc)
            try:
                ThreadManager().invoke_in_ui_thread(
                    lambda err=str(exc): self._on_fetch_error(err)
                )
            except Exception:
                logger.critical("[GMAIL] invoke_in_ui_thread failed, dropping error")
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
        self, emails: List[EmailMetadata], unread_count: int
    ) -> None:
        self._emails = sorted(emails, key=lambda e: (not e.is_unread, -e.date.timestamp()))
        self._last_error = None
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

    def _on_fetch_error(self, error_msg: str) -> None:
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
        header_metrics = QFontMetrics(header_font)
        header_height = header_metrics.height() + 8
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
        margins = self.contentsMargins()
        left = margins.left()
        top = margins.top() + 4
        header_font_pt = int(self._header_font_pt) if self._header_font_pt > 0 else self._font_size
        font = QFont(self._font_family, header_font_pt, QFont.Weight.Bold)
        painter.setFont(font)
        fm = QFontMetrics(font)
        logo_size = max(1, int(self._header_logo_size))
        logo_x = left
        logo_y = top
        pixmap = self._brand_pixmap
        if self._desaturate_when_no_unread and self._unread_count == 0:
            desat = self._ensure_desaturated_brand()
            if desat is not None:
                pixmap = desat
        if pixmap is not None:
            painter.drawPixmap(logo_x, logo_y, pixmap)
        text_x = logo_x + logo_size + 8
        text_y = logo_y + fm.ascent() + (logo_size - fm.height()) // 2
        painter.setPen(self._text_color)
        header_text = "Gmail"
        if self._show_unread_count_in_header and self._unread_count > 0:
            header_text = f"Gmail ({self._unread_count})"
        painter.drawText(text_x, text_y, header_text)
        header_width = logo_size + 8 + fm.horizontalAdvance(header_text)
        self._header_hit_rect = QRect(left, top, header_width, logo_size)

    def _paint_empty_state(self, painter: QPainter) -> None:
        margins = self.contentsMargins()
        rect = self.rect().adjusted(margins.left(), 0, -margins.right(), 0)
        msg = "No unread emails"
        painter.setPen(self._text_color.darker(120))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, msg)

    def _paint_error_state(self, painter: QPainter) -> None:
        margins = self.contentsMargins()
        rect = self.rect().adjusted(margins.left(), 0, -margins.right(), 0)
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
        left = margins.left()
        top = margins.top()
        header_font_pt = int(self._header_font_pt) if self._header_font_pt > 0 else self._font_size
        header_font = QFont(self._font_family, header_font_pt, QFont.Weight.Bold)
        header_fm = QFontMetrics(header_font)
        header_height = header_fm.height() + 12
        base_font_pt = max(8, int(self._font_size))
        row_y = top + header_height
        self._row_hit_rects.clear()
        self._action_hit_rects.clear()
        available_width = self.width() - left - margins.right() - 10
        prev_unread = None
        for i, email in enumerate(self._emails[: self._limit]):
            if prev_unread is not None and prev_unread != email.is_unread and self._show_separators:
                sep_y = row_y - 1
                painter.setPen(QColor(180, 180, 180, 60))
                painter.drawLine(left, sep_y, left + available_width, sep_y)
                row_y += 2
            weight = QFont.Weight.Bold if email.is_unread else QFont.Weight.Normal
            time_width = 0
            time_text = ""
            if self._show_timestamp:
                time_font = QFont(self._font_family, base_font_pt - 2, QFont.Weight.Normal)
                painter.setFont(time_font)
                time_fm = QFontMetrics(time_font)
                time_text = _format_relative_time(email.date)
                time_width = time_fm.horizontalAdvance(time_text) + 8
            env_x = left
            env_width = 0
            if self._show_envelope_icon and self._envelope_pixmap is not None:
                env_width = self._envelope_pixmap.width() + 6
                env_pm = self._envelope_pixmap if email.is_unread else self._envelope_pixmap_dim
                if env_pm is not None:
                    painter.drawPixmap(env_x, row_y + 2, env_pm)
            sender_width = 0
            if self._show_sender:
                sender_font = QFont(self._font_family, base_font_pt, weight)
                painter.setFont(sender_font)
                sender_fm = QFontMetrics(sender_font)
                sender_text = email.sender
                max_sender_width = min(150, available_width // 3)
                sender_text = sender_fm.elidedText(
                    sender_text, Qt.TextElideMode.ElideRight, max_sender_width
                )
                sender_width = sender_fm.horizontalAdvance(sender_text) + 12
            subject_font = QFont(self._font_family, base_font_pt, weight)
            painter.setFont(subject_font)
            subject_fm = QFontMetrics(subject_font)
            subject_text = email.subject
            if self._auto_title_case:
                subject_text = _smart_title_case(subject_text)
            subject_max_width = available_width - time_width - sender_width - env_width - 30
            subject_text = subject_fm.elidedText(
                subject_text, Qt.TextElideMode.ElideRight, subject_max_width
            )
            line_height = subject_fm.height() + 6
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
            if self._show_separators and i < len(self._emails[: self._limit]) - 1:
                sep_y = row_y + line_height
                painter.setPen(QColor(200, 200, 200, 30))
                painter.drawLine(left, sep_y, left + available_width, sep_y)
            row_rect = QRect(left, row_y, available_width, line_height)
            self._row_hit_rects.append((row_rect, email.id, email.subject))
            if self._show_three_dot_menu:
                action_x = self.width() - margins.right() - 24
                action_rect = QRect(action_x, row_y, 24, line_height)
                self._action_hit_rects.append((action_rect, email.id))
                painter.setPen(QColor(150, 150, 150, 180))
                dot_y = row_y + line_height // 2
                for j in range(3):
                    painter.drawEllipse(QPoint(action_x + 4 + j * 6, dot_y), 2, 2)
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
            open_url("https://mail.google.com")
            return True

        for rect, message_id in self._action_hit_rects:
            if rect.contains(local_pos):
                self._show_action_menu(message_id, local_pos)
                return True

        for rect, message_id, _subject in self._row_hit_rects:
            if rect.contains(local_pos):
                if self._gmail_client:
                    self._gmail_client.open_message_in_browser(message_id)
                return True

        return False

    def _trigger_auth_flow(self) -> None:
        logger.info("[GMAIL] Requesting OAuth authentication")
        try:
            self._oauth_manager.start_auth_flow()
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

        if email.is_unread:
            action_read = menu.addAction("Mark as Read")
            icon_read = self._action_icons.get("read")
            if icon_read:
                action_read.setIcon(QIcon(icon_read))
            action_read.triggered.connect(
                lambda _checked=False, mid=message_id: self._dispatch_action(widget_ref, self._do_mark_as_read, mid)
            )

        action_archive = menu.addAction("Archive")
        action_archive.triggered.connect(
            lambda _checked=False, mid=message_id: self._dispatch_action(widget_ref, self._do_archive, mid)
        )

        action_spam = menu.addAction("Mark as Spam")
        icon_spam = self._action_icons.get("spam")
        if icon_spam:
            action_spam.setIcon(QIcon(icon_spam))
        action_spam.triggered.connect(
            lambda _checked=False, mid=message_id: self._dispatch_action(widget_ref, self._do_spam, mid)
        )

        action_trash = menu.addAction("Delete")
        icon_trash = self._action_icons.get("trash")
        if icon_trash:
            action_trash.setIcon(QIcon(icon_trash))
        action_trash.triggered.connect(
            lambda _checked=False, mid=message_id: self._dispatch_action(widget_ref, self._do_trash, mid)
        )

        global_pos = self.mapToGlobal(local_pos)
        menu.popup(global_pos)

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
            ThreadManager().submit_io_task(lambda: action_fn(message_id))
        except Exception:
            action_fn(message_id)

    def _do_mark_as_read(self, message_id: str) -> None:
        if self._gmail_client and self._gmail_client.mark_as_read(message_id):
            logger.info("[GMAIL] Marked %s as read", message_id)
            try:
                ThreadManager().invoke_in_ui_thread(self._fetch_emails)
            except Exception:
                pass

    def _do_archive(self, message_id: str) -> None:
        if self._gmail_client and self._gmail_client.archive_message(message_id):
            logger.info("[GMAIL] Archived %s", message_id)
            try:
                ThreadManager().invoke_in_ui_thread(self._fetch_emails)
            except Exception:
                pass

    def _do_spam(self, message_id: str) -> None:
        if self._gmail_client and self._gmail_client.spam_message(message_id):
            logger.info("[GMAIL] Marked %s as spam", message_id)
            try:
                ThreadManager().invoke_in_ui_thread(self._fetch_emails)
            except Exception:
                pass

    def _do_trash(self, message_id: str) -> None:
        if self._gmail_client and self._gmail_client.trash_message(message_id):
            logger.info("[GMAIL] Trashed %s", message_id)
            try:
                ThreadManager().invoke_in_ui_thread(self._fetch_emails)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def apply_settings(self, settings: Any) -> None:
        if isinstance(settings, dict):
            self._apply_settings_dict(settings)
            return
        self.set_limit(getattr(settings, "limit", self._limit))
        self.set_refresh_interval(getattr(settings, "refresh_minutes", 5))
        self.set_show_sender(getattr(settings, "show_sender", self._show_sender))
        self.set_show_subject(getattr(settings, "show_subject", self._show_subject))
        self.set_show_envelope_icon(getattr(settings, "show_envelope_icon", self._show_envelope_icon))
        self.set_show_three_dot_menu(getattr(settings, "show_three_dot_menu", self._show_three_dot_menu))
        self.set_show_timestamp(getattr(settings, "show_timestamp", self._show_timestamp))
        self.set_show_separators(getattr(settings, "show_separators", self._show_separators))
        self.set_auto_title_case(getattr(settings, "auto_title_case", self._auto_title_case))
        self.set_show_unread_count_in_header(getattr(settings, "show_unread_count_in_header", self._show_unread_count_in_header))
        self.set_desaturate_when_no_unread(getattr(settings, "desaturate_when_no_unread", self._desaturate_when_no_unread))

    def _apply_settings_dict(self, d: Dict[str, Any]) -> None:
        self.set_limit(d.get("limit", self._limit))
        self.set_refresh_interval(d.get("refresh_minutes", 5))
        self.set_show_sender(d.get("show_sender", self._show_sender))
        self.set_show_subject(d.get("show_subject", self._show_subject))
        self.set_show_envelope_icon(d.get("show_envelope_icon", self._show_envelope_icon))
        self.set_show_three_dot_menu(d.get("show_three_dot_menu", self._show_three_dot_menu))
        self.set_show_timestamp(d.get("show_timestamp", self._show_timestamp))
        self.set_show_separators(d.get("show_separators", self._show_separators))
        self.set_auto_title_case(d.get("auto_title_case", self._auto_title_case))
        self.set_show_unread_count_in_header(d.get("show_unread_count_in_header", self._show_unread_count_in_header))
        self.set_desaturate_when_no_unread(d.get("desaturate_when_no_unread", self._desaturate_when_no_unread))

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

    def set_auto_title_case(self, enable: bool) -> None:
        self._auto_title_case = bool(enable)
        self.update()

    def set_show_unread_count_in_header(self, show: bool) -> None:
        self._show_unread_count_in_header = bool(show)
        self.update()

    def set_desaturate_when_no_unread(self, desaturate: bool) -> None:
        self._desaturate_when_no_unread = bool(desaturate)
        self.update()

