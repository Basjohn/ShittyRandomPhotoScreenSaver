"""Gmail overlay widget for screensaver.

Displays recent emails from the user's Gmail inbox with sender, subject, and time.
Follows the same card styling as Reddit/Spotify widgets.

Privacy:
- Only accesses email metadata (sender, subject, labels, timestamps)
- NEVER downloads message content, attachments, or body text
- Uses gmail.metadata and gmail.modify scopes only

The widget is interactive in Ctrl-held / hard-exit modes:
- Click subject → opens email in browser
- 3-dot menu → Mark Read / Archive / Spam / Delete
"""
from __future__ import annotations

from enum import Enum
from typing import Optional, List
from datetime import timedelta
import os

from PySide6.QtCore import Qt, QTimer, QRect, QPoint, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QFontMetrics, QPixmap
from PySide6.QtWidgets import QWidget, QMenu, QToolTip

from core.logging.logger import get_logger
from core.threading.manager import ThreadManager
from core.gmail.gmail_client import GmailClient, EmailMetadata
from core.auth.gmail_oauth import GmailOAuthManager
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.shadow_utils import ShadowFadeProfile
from widgets.overlay_timers import create_overlay_timer, OverlayTimerHandle

logger = get_logger(__name__)


class GmailPosition(Enum):
    """Gmail widget position on screen (corner positions)."""
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


class GmailWidget(BaseOverlayWidget):
    """
    Gmail overlay widget displaying recent emails.
    
    Extends BaseOverlayWidget for common styling/positioning functionality.
    
    Features:
    - Displays 5 or 10 most recent emails from configured label/filter
    - Shows sender, subject, and time for each email
    - Unread emails displayed in bold
    - Header row with Gmail logo + "Gmail" text
    - Click-to-open in browser
    - Action menu for Mark Read/Archive/Spam/Delete
    - Unread indicator via logo saturation
    """
    
    # Signals
    email_clicked = Signal(str)  # message_id
    unread_count_changed = Signal(int)
    
    DEFAULT_FONT_SIZE = 16

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        position: GmailPosition = GmailPosition.TOP_LEFT,
    ) -> None:
        overlay_pos = OverlayPosition(position.value)
        super().__init__(parent, position=overlay_pos, overlay_name="gmail")

        self._gmail_position = position
        self._limit: int = 5
        self._refresh_interval = timedelta(minutes=5)
        self._filter_label: str = "INBOX"  # INBOX, CATEGORY_PRIMARY, etc.
        self._show_sender: bool = True
        self._show_subject: bool = True
        self._show_actions: bool = True
        self._desaturate_when_no_unread: bool = True

        self._update_timer: Optional[QTimer] = None
        self._update_timer_handle: Optional[OverlayTimerHandle] = None

        # Gmail client
        self._gmail_client: Optional[GmailClient] = None
        self._oauth_manager: Optional[GmailOAuthManager] = None

        # Cached emails and click hit-rects
        self._emails: List[EmailMetadata] = []
        self._row_hit_rects: List[tuple[QRect, str, str]] = []  # (rect, message_id, subject)
        self._action_hit_rects: List[tuple[QRect, str]] = []  # (rect, message_id)
        self._has_displayed_valid_data: bool = False
        self._unread_count: int = 0

        # Override base class font size default
        self._font_size = 16

        # Header/logo metrics
        self._header_font_pt: int = self._font_size
        self._header_logo_size: int = max(12, int(self._font_size * 1.3))
        self._header_logo_margin: int = self._header_logo_size
        self._brand_pixmap: Optional[QPixmap] = self._load_brand_pixmap()
        self._brand_pixmap_desaturated: Optional[QPixmap] = None
        self._header_hit_rect: Optional[QRect] = None

        # Hover state
        self._hover_row_index: Optional[int] = None
        self._hover_timer: Optional[QTimer] = None
        self._hover_global_pos: Optional[QPoint] = None
        self._hover_subject: str = ""

        self._row_vertical_spacing: int = 4

        self._setup_ui()

        logger.debug("GmailWidget created (position=%s)", position.value)

    def _setup_ui(self) -> None:
        """Initialise widget appearance and layout."""
        self._apply_base_styling()
        
        # Apply dark themed tooltip styling
        self.setStyleSheet(self.styleSheet() + """
            QToolTip {
                background-color: rgba(32, 32, 32, 230);
                color: rgba(255, 255, 255, 255);
                border: 1px solid rgba(255, 255, 255, 200);
                border-radius: 4px;
                padding: 5px 10px;
                font-family: 'Segoe UI';
                font-size: 11px;
            }
        """)

        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception:
            pass

        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)
        self.setFont(font)
        self.setWordWrap(False)

        self.setMinimumWidth(500)
        base_min = int(180 * 1.2)
        self.setMinimumHeight(base_min)

        try:
            self.move(10000, 10000)
        except Exception:
            pass

    def _load_brand_pixmap(self) -> Optional[QPixmap]:
        """Load the Gmail logo from assets."""
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            logo_path = os.path.join(base_dir, "images", "google-gmail.svg")
            
            if os.path.exists(logo_path):
                pixmap = QPixmap(logo_path)
                if not pixmap.isNull():
                    return pixmap
            
            # Try PNG fallback
            png_path = os.path.join(base_dir, "images", "google-gmail.png")
            if os.path.exists(png_path):
                pixmap = QPixmap(png_path)
                if not pixmap.isNull():
                    return pixmap
                    
        except Exception as e:
            logger.debug("[GMAIL] Failed to load brand pixmap: %s", e)
        
        return None

    def _create_desaturated_pixmap(self) -> Optional[QPixmap]:
        """Create a desaturated version of the logo for no-unread state."""
        if self._brand_pixmap is None:
            return None
        
        try:
            from PySide6.QtGui import QImage
            
            img = self._brand_pixmap.toImage()
            # Convert to grayscale with 60% saturation reduction
            for y in range(img.height()):
                for x in range(img.width()):
                    pixel = img.pixelColor(x, y)
                    gray = int(0.299 * pixel.red() + 0.587 * pixel.green() + 0.114 * pixel.blue())
                    # Blend 40% original + 60% gray
                    new_r = int(pixel.red() * 0.4 + gray * 0.6)
                    new_g = int(pixel.green() * 0.4 + gray * 0.6)
                    new_b = int(pixel.blue() * 0.4 + gray * 0.6)
                    img.setPixelColor(x, y, QColor(new_r, new_g, new_b, pixel.alpha()))
            
            return QPixmap.fromImage(img)
        except Exception as e:
            logger.debug("[GMAIL] Failed to create desaturated pixmap: %s", e)
            return None

    def _update_content(self) -> None:
        """Required by BaseOverlayWidget - refresh email list."""
        self._fetch_emails()

    def start(self) -> None:
        """Begin periodic email fetches and show widget on first data."""
        if self._enabled:
            logger.warning("[GMAIL] Widget already running")
            return

        self._enabled = True
        self.hide()
        
        # Initialize OAuth and client
        self._oauth_manager = GmailOAuthManager.instance()
        if self._oauth_manager.is_authenticated:
            self._gmail_client = GmailClient(self._oauth_manager)
        
        self._schedule_timer()
        self._fetch_emails()

    def stop(self) -> None:
        """Stop refreshes and hide widget."""
        if not self._enabled:
            return

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

        self._enabled = False
        self._emails.clear()
        self._row_hit_rects.clear()
        self._action_hit_rects.clear()
        try:
            self.hide()
        except Exception:
            pass

    def cleanup(self) -> None:
        """Clean up resources."""
        logger.debug("Cleaning up Gmail widget")
        self.stop()
        try:
            if self._hover_timer is not None:
                self._hover_timer.stop()
                self._hover_timer.deleteLater()
                self._hover_timer = None
        except Exception:
            pass

    def _schedule_timer(self) -> None:
        """Schedule the periodic refresh timer."""
        interval_ms = int(self._refresh_interval.total_seconds() * 1000)
        
        try:
            thread_mgr = ThreadManager()
            self._update_timer_handle = create_overlay_timer(
                self,
                interval_ms,
                self._fetch_emails,
                thread_mgr,
            )
        except Exception:
            self._update_timer = QTimer(self)
            self._update_timer.timeout.connect(self._fetch_emails)
            self._update_timer.start(interval_ms)

    def _fetch_emails(self) -> None:
        """Fetch emails from Gmail API."""
        if not self._enabled:
            return
        
        if self._gmail_client is None or not self._gmail_client.is_authenticated:
            logger.debug("[GMAIL] Not authenticated, skipping fetch")
            return
        
        try:
            thread_mgr = ThreadManager()
            thread_mgr.submit_io_task(self._fetch_emails_async)
        except Exception:
            self._fetch_emails_sync()

    def _fetch_emails_async(self) -> None:
        """Fetch emails on IO thread."""
        try:
            label_ids = [self._filter_label]
            emails = self._gmail_client.list_messages(
                max_results=self._limit,
                label_ids=label_ids,
            )
            
            # Count unread
            unread = sum(1 for e in emails if e.is_unread)
            
            # Update on UI thread
            try:
                thread_mgr = ThreadManager()
                thread_mgr.invoke_in_ui_thread(
                    lambda: self._on_emails_fetched(emails, unread)
                )
            except Exception:
                self._on_emails_fetched(emails, unread)
                
        except Exception as e:
            logger.error("[GMAIL] Fetch failed: %s", e)

    def _fetch_emails_sync(self) -> None:
        """Synchronous email fetch (fallback)."""
        try:
            label_ids = [self._filter_label]
            emails = self._gmail_client.list_messages(
                max_results=self._limit,
                label_ids=label_ids,
            )
            unread = sum(1 for e in emails if e.is_unread)
            self._on_emails_fetched(emails, unread)
        except Exception as e:
            logger.error("[GMAIL] Sync fetch failed: %s", e)

    def _on_emails_fetched(self, emails: List[EmailMetadata], unread_count: int) -> None:
        """Handle fetched emails on UI thread."""
        self._emails = emails
        
        if unread_count != self._unread_count:
            self._unread_count = unread_count
            self.unread_count_changed.emit(unread_count)
        
        if emails:
            self._has_displayed_valid_data = True
            self._update_card_height_from_content(len(emails))
            self.update()
            
            if not self.isVisible():
                self._request_fade_in()
        else:
            if not self._has_displayed_valid_data:
                self.hide()

    def _request_fade_in(self) -> None:
        """Request coordinated fade-in via DisplayWidget."""
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

    def _update_card_height_from_content(self, visible_rows: Optional[int] = None) -> None:
        """Calculate and set widget height based on content."""
        try:
            rows = int(visible_rows) if visible_rows is not None else 0
        except Exception:
            rows = 0
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

    def paintEvent(self, event) -> None:
        """Custom paint for Gmail card layout."""
        super().paintEvent(event)
        
        if not self._emails:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        try:
            self._paint_header(painter)
            self._paint_emails(painter)
        finally:
            painter.end()

    def _paint_header(self, painter: QPainter) -> None:
        """Paint the Gmail logo and header text."""
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

        # Choose logo based on unread state
        pixmap = self._brand_pixmap
        if self._desaturate_when_no_unread and self._unread_count == 0:
            if self._brand_pixmap_desaturated is None:
                self._brand_pixmap_desaturated = self._create_desaturated_pixmap()
            if self._brand_pixmap_desaturated is not None:
                pixmap = self._brand_pixmap_desaturated

        if pixmap is not None:
            dpr = self.devicePixelRatioF()
            scaled = pixmap.scaled(
                int(logo_size * dpr),
                int(logo_size * dpr),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            scaled.setDevicePixelRatio(dpr)
            painter.drawPixmap(logo_x, logo_y, scaled)

        # Header text
        text_x = logo_x + logo_size + 8
        text_y = logo_y + fm.ascent() + (logo_size - fm.height()) // 2

        painter.setPen(QColor(255, 255, 255, 255))
        header_text = "Gmail"
        if self._unread_count > 0:
            header_text = f"Gmail ({self._unread_count})"
        painter.drawText(text_x, text_y, header_text)

        # Store header hit rect
        header_width = logo_size + 8 + fm.horizontalAdvance(header_text)
        self._header_hit_rect = QRect(left, top, header_width, logo_size)

    def _paint_emails(self, painter: QPainter) -> None:
        """Paint the email list."""
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

        for i, email in enumerate(self._emails[:self._limit]):
            # Font weight based on unread status
            weight = QFont.Weight.Bold if email.is_unread else QFont.Weight.Normal
            
            # Time column
            time_font = QFont(self._font_family, base_font_pt - 2, QFont.Weight.Normal)
            painter.setFont(time_font)
            time_fm = QFontMetrics(time_font)
            time_text = email.display_time
            time_width = time_fm.horizontalAdvance(time_text) + 8
            
            # Sender column (if enabled)
            sender_width = 0
            if self._show_sender:
                sender_font = QFont(self._font_family, base_font_pt, weight)
                painter.setFont(sender_font)
                sender_fm = QFontMetrics(sender_font)
                sender_text = email.display_sender
                # Limit sender width
                max_sender_width = min(150, available_width // 3)
                sender_text = sender_fm.elidedText(sender_text, Qt.TextElideMode.ElideRight, max_sender_width)
                sender_width = sender_fm.horizontalAdvance(sender_text) + 12

            # Subject column
            subject_font = QFont(self._font_family, base_font_pt, weight)
            painter.setFont(subject_font)
            subject_fm = QFontMetrics(subject_font)
            
            # Calculate subject width
            subject_max_width = available_width - time_width - sender_width - 30
            subject_text = subject_fm.elidedText(
                email.subject, Qt.TextElideMode.ElideRight, subject_max_width
            )

            line_height = subject_fm.height() + 6
            text_y = row_y + subject_fm.ascent() + 2

            # Draw time (right-aligned, dimmer)
            painter.setFont(time_font)
            painter.setPen(QColor(180, 180, 180, 200))
            time_x = left
            painter.drawText(time_x, text_y, time_text)

            # Draw sender
            if self._show_sender:
                painter.setFont(QFont(self._font_family, base_font_pt, weight))
                painter.setPen(QColor(200, 200, 200, 255) if email.is_unread else QColor(180, 180, 180, 220))
                sender_x = time_x + time_width
                painter.drawText(sender_x, text_y, sender_text)

            # Draw subject
            painter.setFont(subject_font)
            painter.setPen(QColor(255, 255, 255, 255) if email.is_unread else QColor(220, 220, 220, 230))
            subject_x = time_x + time_width + sender_width
            painter.drawText(subject_x, text_y, subject_text)

            # Store hit rect for click handling
            row_rect = QRect(left, row_y, available_width, line_height)
            self._row_hit_rects.append((row_rect, email.id, email.subject))

            # Action button (3 dots) - if enabled
            if self._show_actions:
                action_x = self.width() - margins.right() - 20
                action_rect = QRect(action_x, row_y, 20, line_height)
                self._action_hit_rects.append((action_rect, email.id))
                
                # Draw 3 dots
                painter.setPen(QColor(150, 150, 150, 180))
                dot_y = row_y + line_height // 2
                for j in range(3):
                    painter.drawEllipse(QPoint(action_x + 4 + j * 6, dot_y), 2, 2)

            row_y += line_height + self._row_vertical_spacing

    def handle_click(self, local_pos: QPoint) -> bool:
        """
        Handle a click at the given position.
        
        Args:
            local_pos: Click position in widget-local coordinates
            
        Returns:
            True if a click was handled, False otherwise.
        """
        # Check header click - open Gmail inbox
        if self._header_hit_rect is not None and self._header_hit_rect.contains(local_pos):
            import webbrowser
            try:
                webbrowser.open("https://mail.google.com")
                logger.info("[GMAIL] Opened Gmail inbox")
                return True
            except Exception:
                return False

        # Check action button clicks
        for rect, message_id in self._action_hit_rects:
            if rect.contains(local_pos):
                self._show_action_menu(message_id, self.mapToGlobal(local_pos))
                return True

        # Check row clicks - open email
        for rect, message_id, _subject in self._row_hit_rects:
            if rect.contains(local_pos):
                if self._gmail_client:
                    self._gmail_client.open_message_in_browser(message_id)
                    logger.info("[GMAIL] Opened email %s", message_id)
                    return True
        
        return False

    def _show_action_menu(self, message_id: str, global_pos: QPoint) -> None:
        """Show the action menu for an email."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(43, 43, 43, 255);
                border: 2px solid rgba(154, 154, 154, 200);
                border-radius: 6px;
                padding: 4px 2px;
            }
            QMenu::item {
                background-color: transparent;
                color: #ffffff;
                padding: 6px 20px 6px 12px;
                margin: 1px 3px;
                border-radius: 3px;
                font-size: 12px;
            }
            QMenu::item:selected {
                background-color: rgba(62, 62, 62, 220);
            }
        """)

        # Find the email
        email = next((e for e in self._emails if e.id == message_id), None)
        if not email:
            return

        # Mark as Read/Unread
        if email.is_unread:
            action_read = menu.addAction("Mark as Read")
            action_read.triggered.connect(lambda: self._mark_as_read(message_id))
        else:
            action_unread = menu.addAction("Mark as Unread")
            action_unread.triggered.connect(lambda: self._mark_as_unread(message_id))

        menu.addSeparator()

        # Archive
        action_archive = menu.addAction("Archive")
        action_archive.triggered.connect(lambda: self._archive_message(message_id))

        # Spam
        action_spam = menu.addAction("Mark as Spam")
        action_spam.triggered.connect(lambda: self._mark_as_spam(message_id))

        # Delete
        action_delete = menu.addAction("Delete")
        action_delete.triggered.connect(lambda: self._trash_message(message_id))

        menu.popup(global_pos)

    def _mark_as_read(self, message_id: str) -> None:
        """Mark email as read."""
        if self._gmail_client and self._gmail_client.mark_as_read(message_id):
            logger.info("[GMAIL] Marked %s as read", message_id)
            self._fetch_emails()

    def _mark_as_unread(self, message_id: str) -> None:
        """Mark email as unread."""
        if self._gmail_client and self._gmail_client.mark_as_unread(message_id):
            logger.info("[GMAIL] Marked %s as unread", message_id)
            self._fetch_emails()

    def _archive_message(self, message_id: str) -> None:
        """Archive email."""
        if self._gmail_client and self._gmail_client.archive_message(message_id):
            logger.info("[GMAIL] Archived %s", message_id)
            self._fetch_emails()

    def _mark_as_spam(self, message_id: str) -> None:
        """Mark email as spam."""
        if self._gmail_client and self._gmail_client.mark_as_spam(message_id):
            logger.info("[GMAIL] Marked %s as spam", message_id)
            self._fetch_emails()

    def _trash_message(self, message_id: str) -> None:
        """Move email to trash."""
        if self._gmail_client and self._gmail_client.trash_message(message_id):
            logger.info("[GMAIL] Trashed %s", message_id)
            self._fetch_emails()

    def handle_hover(self, local_pos: QPoint, global_pos: QPoint) -> None:
        """Handle hover for tooltip display."""
        row_index = -1
        for i, (rect, _msg_id, _subject) in enumerate(self._row_hit_rects):
            if rect.contains(local_pos):
                row_index = i
                break

        if row_index < 0:
            if self._hover_timer is not None:
                self._hover_timer.stop()
            self._hover_row_index = None
            QToolTip.hideText()
            return

        if self._hover_row_index == row_index:
            self._hover_global_pos = QPoint(global_pos)
            return

        self._hover_row_index = row_index
        self._hover_global_pos = QPoint(global_pos)
        _rect, _msg_id, subject = self._row_hit_rects[row_index]
        self._hover_subject = subject

        if self._hover_timer is None:
            self._hover_timer = QTimer(self)
            self._hover_timer.setSingleShot(True)
            self._hover_timer.timeout.connect(self._show_subject_tooltip)
        else:
            self._hover_timer.stop()

        self._hover_timer.start(1500)

    def _show_subject_tooltip(self) -> None:
        """Show tooltip with full subject."""
        if not self._hover_subject:
            return
        pos = self._hover_global_pos
        if pos is None:
            return
        try:
            QToolTip.showText(pos, self._hover_subject, self)
        except Exception:
            pass

    # Settings setters
    def set_limit(self, limit: int) -> None:
        """Set number of emails to display (5 or 10)."""
        self._limit = max(5, min(10, limit))
        self._update_card_height_from_content(self._limit)

    def set_filter_label(self, label: str) -> None:
        """Set the label filter (INBOX, CATEGORY_PRIMARY, etc.)."""
        self._filter_label = label

    def set_refresh_interval(self, minutes: int) -> None:
        """Set refresh interval in minutes."""
        self._refresh_interval = timedelta(minutes=max(1, minutes))

    def set_show_sender(self, show: bool) -> None:
        """Set whether to show sender column."""
        self._show_sender = show
        self.update()

    def set_show_subject(self, show: bool) -> None:
        """Set whether to show subject column."""
        self._show_subject = show
        self.update()

    def set_show_actions(self, show: bool) -> None:
        """Set whether to show action buttons."""
        self._show_actions = show
        self.update()

    def set_desaturate_when_no_unread(self, desaturate: bool) -> None:
        """Set whether to desaturate logo when no unread emails."""
        self._desaturate_when_no_unread = desaturate
        self.update()
