"""Reddit overlay widget for screensaver.

Displays a small card listing the top N posts from a configured
subreddit, styled similarly to the Spotify media widget.

The widget is strictly read-only: clicking a row opens the post in the
system default browser. Interaction is gated by DisplayWidget's
Ctrl-held / hard-exit modes; this widget itself does not handle mouse
or keyboard input directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import timedelta
import time
import re
import sys
import ctypes
from ctypes import wintypes

import requests

from PySide6.QtCore import Qt, QTimer, QRect, QPoint, QUrl
from PySide6.QtGui import QFont, QColor, QPainter, QFontMetrics, QDesktopServices, QPixmap
from PySide6.QtWidgets import QWidget, QToolTip
from shiboken6 import isValid as shiboken_isValid

from core.logging.logger import get_logger, is_verbose_logging
from core.threading.manager import ThreadManager
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.shadow_utils import (
    apply_widget_shadow,
    ShadowFadeProfile,
    draw_text_with_shadow,
    draw_text_rect_with_shadow,
    draw_rounded_rect_with_shadow,
)
from widgets.overlay_timers import create_overlay_timer, OverlayTimerHandle

logger = get_logger(__name__)


class RedditPosition(Enum):
    """Reddit widget position on screen (corner positions)."""

    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


@dataclass
class RedditPost:
    """Lightweight representation of a Reddit post for display."""

    title: str
    url: str
    score: int
    created_utc: float


_TITLE_FILTER_RE = re.compile(r"\b(daily|weekly|question thread)\b", re.IGNORECASE)

# Words to keep lowercase in title case (unless first word)
_TITLE_CASE_SMALL_WORDS = frozenset()


def _smart_title_case(text: str) -> str:
    """Convert text to title case while preserving acronyms and handling exceptions.
    
    - Preserves ALL CAPS words (likely acronyms: USA, NASA, AI, etc.)
    - Capitalizes every word (including short words like "a", "to", "with")
    - Preserves standalone "I"
    - Handles punctuation correctly
    """
    if not text:
        return text
    
    words = text.split()
    result = []
    
    for i, word in enumerate(words):
        # Preserve ALL CAPS words (2+ chars) - likely acronyms
        if len(word) >= 2 and word.isupper() and word.isalpha():
            result.append(word)
            continue
        
        # Handle words with leading punctuation (e.g., quotes, brackets)
        leading = ""
        trailing = ""
        core = word
        
        # Strip leading punctuation
        while core and not core[0].isalnum():
            leading += core[0]
            core = core[1:]
        
        # Strip trailing punctuation
        while core and not core[-1].isalnum():
            trailing = core[-1] + trailing
            core = core[:-1]
        
        if not core:
            result.append(word)
            continue
        
        # Preserve ALL CAPS core (acronyms)
        if len(core) >= 2 and core.isupper() and core.isalpha():
            result.append(word)
            continue
        
        # Preserve "I" as uppercase
        if core.lower() == "i":
            result.append(leading + "I" + trailing)
            continue

        # Title case the core word (capitalize first character of every word)
        result.append(leading + core[:1].upper() + core[1:] + trailing)
    
    return " ".join(result)


class RedditWidget(BaseOverlayWidget):
    """Reddit widget for displaying subreddit entries.

    Extends BaseOverlayWidget for common styling/positioning functionality.

    Features:
    - Fetches top N posts from a configured subreddit via Reddit's
      public JSON listing endpoints (no API key / OAuth).
    - Displays each post as a single-line entry: small score on the
      left, elided title on the right.
    - Header row with Reddit logo + ``r/<subreddit>`` text, matching the
      Spotify card header style.
    - Configurable position, font, colours, and background frame.
    - Non-interactive at the widget level; click handling is delegated
      to DisplayWidget during Ctrl-held / hard-exit interaction mode.
    """
    
    # Override defaults for reddit widget
    DEFAULT_FONT_SIZE = 18

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        subreddit: str = "wallpapers",
        position: RedditPosition = RedditPosition.TOP_RIGHT,
    ) -> None:
        # Convert RedditPosition to OverlayPosition for base class
        overlay_pos = OverlayPosition(position.value)
        super().__init__(parent, position=overlay_pos, overlay_name="reddit")

        # Logical placement and source configuration
        self._reddit_position = position  # Keep original enum for compatibility
        self._subreddit: str = self._normalise_subreddit(subreddit)
        self._sort: str = "hot"
        self._limit: int = 10
        self._refresh_interval = timedelta(minutes=10)

        self._update_timer: Optional[QTimer] = None
        self._update_timer_handle: Optional[OverlayTimerHandle] = None

        # Cached posts and click hit-rects
        self._posts: List[RedditPost] = []
        self._row_hit_rects: List[tuple[QRect, str, str]] = []
        self._has_displayed_valid_data: bool = False
        self._has_seen_first_sample: bool = False

        # Override base class font size default
        self._font_size = 18

        # Header/logo metrics, mirroring the Spotify card approach
        self._header_font_pt: int = self._font_size
        self._header_logo_size: int = max(12, int(self._font_size * 1.3))
        self._header_logo_margin: int = self._header_logo_size
        self._brand_pixmap: Optional[QPixmap] = self._load_brand_pixmap()
        self._header_hit_rect: Optional[QRect] = None

        # Hover state and tooltip management
        self._hover_row_index: Optional[int] = None
        self._hover_timer: Optional[QTimer] = None
        self._hover_global_pos: Optional[QPoint] = None
        self._hover_title: str = ""

        self._row_vertical_spacing: int = 0
        self._show_separators: bool = False

        self._setup_ui()

        logger.debug("RedditWidget created (subreddit=%s, position=%s)", self._subreddit, position.value)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Initialise widget appearance and layout."""
        # Use base class styling setup
        self._apply_base_styling()
        
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        try:
            # Non-interactive; DisplayWidget owns input routing.
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception:
            pass

        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)
        self.setFont(font)
        # We paint text manually; QLabel's text property is unused, but
        # we can still take advantage of stylesheet-based background.
        self.setWordWrap(False)

        # Reasonable default footprint
        self.setMinimumWidth(600)
        base_min = int(220 * 1.2)
        self.setMinimumHeight(base_min)

        try:
            self.move(10000, 10000)
        except Exception:
            pass
    
    def _update_content(self) -> None:
        """Required by BaseOverlayWidget - refresh reddit display."""
        self._fetch_feed()

    def start(self) -> None:
        """Start fetching Reddit posts."""
        if self._enabled:
            logger.debug("Reddit widget already running")
            return
        if not self._ensure_thread_manager("RedditWidget.start"):
            return

        self._enabled = True
        self.hide()
        self._schedule_timer()
        self._fetch_feed()

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
        self._posts.clear()
        self._row_hit_rects.clear()
        try:
            self.hide()
        except Exception:
            pass

    def cleanup(self) -> None:
        logger.debug("Cleaning up Reddit widget")
        self.stop()
        try:
            if self._hover_timer is not None:
                self._hover_timer.stop()
                self._hover_timer.deleteLater()
        except Exception:
            pass
        self._hover_timer = None

    def is_running(self) -> bool:
        return self._enabled

    # ------------------------------------------------------------------
    # External configuration (called from DisplayWidget/Settings)
    # ------------------------------------------------------------------

    def set_thread_manager(self, thread_manager: ThreadManager) -> None:
        self._thread_manager = thread_manager

    def set_shadow_config(self, config: Optional[Dict[str, Any]]) -> None:
        self._shadow_config = config

    def set_subreddit(self, subreddit: str) -> None:
        self._subreddit = self._normalise_subreddit(subreddit)
        # Refresh immediately on change
        if self._enabled:
            self._fetch_feed()

    def set_position(self, position: RedditPosition) -> None:
        """Set widget position using RedditPosition enum."""
        self._reddit_position = position
        # Update base class position
        overlay_pos = OverlayPosition(position.value)
        super().set_position(overlay_pos)

    def set_show_separators(self, show: bool) -> None:
        """Enable or disable row separators."""
        self._show_separators = bool(show)
        self.update()

    def set_item_limit(self, limit: int) -> None:
        self._limit = max(1, min(int(limit), 25))
        self._update_card_height_from_limit()
        if self._enabled and self._posts:
            # Trim existing posts to the new visible limit
            self._posts = self._posts[: self._limit]
            self.update()

    # ------------------------------------------------------------------
    # Networking
    # ------------------------------------------------------------------

    def _schedule_timer(self) -> None:
        if self._update_timer_handle is not None:
            # Timer already running; nothing to do.
            return

        interval_ms = int(self._refresh_interval.total_seconds() * 1000)
        handle = create_overlay_timer(self, interval_ms, self._fetch_feed, description="RedditWidget refresh")
        self._update_timer_handle = handle
        try:
            self._update_timer = getattr(handle, "_timer", None)
        except Exception:
            self._update_timer = None

    def _fetch_feed(self) -> None:
        """Request subreddit listing via ThreadManager or synchronously.

        Failures are silent from the user's perspective: the widget
        simply remains hidden until at least one successful fetch has
        occurred.
        """

        if not self._subreddit:
            return

        tm = self._thread_manager

        def _do_fetch(subreddit: str, sort: str, limit: int) -> List[Dict[str, Any]]:
            url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
            headers = {
                "User-Agent": "ShittyRandomPhotoScreenSaver/1.0 (+https://github.com/Basjohn/ShittyRandomPhotoScreenSaver)",
            }

            # Visible item limit (what the UI will actually show) is still
            # derived from the configured limit, but we always fetch the same
            # number of Reddit entries so that 4-item and 10-item modes share
            # a common candidate pool before recency sorting.
            effective_limit = max(1, min(int(limit), 25))
            fetch_limit = 25

            params = {"limit": fetch_limit}

            logger.debug(
                "[REDDIT] Fetching feed: subreddit=%s sort=%s limit=%s (visible_limit=%s)",
                subreddit,
                sort,
                params["limit"],
                effective_limit,
            )
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            payload = resp.json()

            children = payload.get("data", {}).get("children", [])
            posts: List[Dict[str, Any]] = []
            for child in children:
                data = child.get("data") or {}
                title = str(data.get("title") or "").strip()
                if not title:
                    continue
                try:
                    score = int(data.get("score") or 0)
                except Exception:
                    score = 0
                try:
                    created_utc = float(data.get("created_utc") or 0.0)
                except Exception:
                    created_utc = 0.0
                permalink = data.get("permalink")
                if permalink:
                    url_str = f"https://www.reddit.com{permalink}"
                else:
                    direct_url = data.get("url") or data.get("url_overridden_by_dest")
                    if not direct_url:
                        continue
                    url_str = str(direct_url)
                posts.append({
                    "title": title,
                    "url": url_str,
                    "score": score,
                    "created_utc": created_utc,
                })

            return posts

        def _on_result(result) -> None:
            try:
                if getattr(result, "success", False) and isinstance(getattr(result, "result", None), list):
                    posts_data = result.result
                    ThreadManager.run_on_ui_thread(self._on_feed_fetched, posts_data)
                else:
                    err = getattr(result, "error", None) or "No Reddit data returned"
                    ThreadManager.run_on_ui_thread(self._on_fetch_error, str(err))
            except Exception as exc:  # pragma: no cover - defensive
                ThreadManager.run_on_ui_thread(
                    self._on_fetch_error,
                    f"Reddit fetch failed: {exc}",
                )

        if tm is not None:
            try:
                tm.submit_io_task(_do_fetch, self._subreddit, self._sort, self._limit, callback=_on_result)
                return
            except Exception as exc:
                logger.exception("[REDDIT] ThreadManager submission failed, falling back to sync fetch: %s", exc)

        # Fallback: synchronous fetch on UI thread (rare, but bounded by timeout)
        try:
            posts_data = _do_fetch(self._subreddit, self._sort, self._limit)
            self._on_feed_fetched(posts_data)
        except Exception as exc:
            self._on_fetch_error(str(exc))

    def _on_feed_fetched(self, posts_data: List[Dict[str, Any]]) -> None:
        # Guard against callback arriving after widget destruction
        if not shiboken_isValid(self):
            return
        
        if not posts_data:
            logger.warning("[REDDIT] Empty listing for subreddit %s", self._subreddit)
            if not self._has_displayed_valid_data:
                try:
                    self.hide()
                except Exception:
                    pass
            return

        posts: List[RedditPost] = []
        for raw in posts_data:
            title = str(raw.get("title") or "").strip()
            url = str(raw.get("url") or "").strip()
            if not title or not url:
                continue
            if _TITLE_FILTER_RE.search(title):
                continue

            try:
                score = int(raw.get("score") or 0)
            except Exception:
                score = 0

            try:
                created_utc = float(raw.get("created_utc") or 0.0)
            except Exception:
                created_utc = 0.0

            posts.append(
                RedditPost(
                    title=title,
                    url=url,
                    score=score,
                    created_utc=created_utc,
                )
            )

        if not posts:
            if not self._has_displayed_valid_data:
                try:
                    self.hide()
                except Exception:
                    pass
            return

        # Order posts so that the newest entries appear at the top of the
        # list, while still using Reddit's hot/top/etc. listing as the
        # source. Posts with invalid timestamps fall back to their original
        # order and sink to the bottom.
        try:
            def _sort_key(p: RedditPost) -> tuple[int, float]:
                ts = float(getattr(p, "created_utc", 0.0) or 0.0)
                if ts <= 0.0:
                    return (1, 0.0)
                return (0, -ts)

            posts.sort(key=_sort_key)
        except Exception:
            pass

        # Only keep as many posts as we can actually display for the
        # current limit; oversampling still happens at fetch time for
        # filtering, but the rendered list is always capped.
        try:
            visible_limit = max(1, int(self._limit))
        except Exception:
            visible_limit = max(1, len(posts))

        self._posts = posts[:visible_limit]
        self._row_hit_rects.clear()

        # Update typography metrics for the header based on the current
        # base font size; the header itself is painted in paintEvent.
        base_font = max(6, self._font_size)
        header_font = max(6, int(base_font * 1.2))
        self._header_font_pt = header_font
        self._header_logo_size = max(12, int(header_font * 1.3))
        self._header_logo_margin = self._header_logo_size

        # Size the card to the actual number of visible rows so we avoid
        # large empty regions while still leaving enough headroom for the
        # chosen limit and current font metrics.
        self._update_card_height_from_content(len(self._posts))
        self.update()

        if self.parent():
            self._update_position()
            # Notify parent to recalculate stacking after height change
            if hasattr(self.parent(), 'recalculate_stacking'):
                try:
                    self.parent().recalculate_stacking()
                except Exception:
                    pass

        first_sample = not self._has_seen_first_sample
        if first_sample:
            self._has_seen_first_sample = True
            parent = self.parent()

            def _starter() -> None:
                # Guard against widget being deleted before deferred callback runs
                if not shiboken_isValid(self):
                    return
                self._start_widget_fade_in(1500)

            if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
                try:
                    # Use configured overlay name (defaults to "reddit")
                    overlay_name = getattr(self, '_overlay_name', None) or "reddit"
                    parent.request_overlay_fade_sync(overlay_name, _starter)
                except Exception:
                    _starter()
            else:
                _starter()
        else:
            try:
                self.show()
            except Exception:
                pass

        self._has_displayed_valid_data = True

    def _on_fetch_error(self, error: str) -> None:
        # Guard against callback arriving after widget destruction
        if not shiboken_isValid(self):
            return
        
        if is_verbose_logging():
            logger.warning("[REDDIT] Fetch error: %s", error)

        # If we have never displayed valid data, remain hidden; otherwise
        # keep showing the last successful sample.
        if not self._has_displayed_valid_data:
            try:
                self.hide()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Painting & hit testing
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # type: ignore[override]
        """Paint background via QLabel then overlay header and posts."""

        super().paintEvent(event)

        if not self._posts:
            return

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        except Exception:
            pass

        margins = self.contentsMargins()
        rect = self.rect().adjusted(
            margins.left(),
            margins.top(),
            -margins.right(),
            -margins.bottom(),
        )
        if rect.width() <= 0 or rect.height() <= 0:
            return

        # Header: Reddit logo + r/<subreddit>
        self._header_hit_rect = None
        header_font = QFont(self._font_family, self._header_font_pt, QFont.Weight.Bold)
        painter.setFont(header_font)
        header_metrics = QFontMetrics(header_font)
        header_top = rect.top() + 4
        baseline_y = header_top + header_metrics.ascent()

        self._paint_header_frame(painter)

        x = rect.left() + 3
        logo_size = max(0, int(self._header_logo_size))
        if self._brand_pixmap is not None and not self._brand_pixmap.isNull() and logo_size > 0:
            try:
                dpr = float(self.devicePixelRatioF())
            except Exception:
                dpr = 1.0
            scale_dpr = max(1.0, dpr)
            target_px = int(logo_size * scale_dpr)
            if target_px > 0:
                pm = self._brand_pixmap.scaled(
                    target_px,
                    target_px,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                try:
                    pm.setDevicePixelRatio(scale_dpr)
                except Exception:
                    pass

                line_height = header_metrics.height()
                line_centre = header_top + (line_height * 0.6)
                icon_half = float(logo_size) / 2.0
                y_logo = int(line_centre - icon_half)
                if y_logo < header_top:
                    y_logo = header_top
                painter.drawPixmap(int(x), int(y_logo), pm)

            x += logo_size + 8
        else:
            x += 4

        subreddit_label = f"r/{self._subreddit}" if self._subreddit else "r/<subreddit>"
        painter.setPen(QColor(255, 255, 255, 255))
        available_header_width = max(0, rect.right() - x)
        if available_header_width > 0:
            drawn_label = header_metrics.elidedText(
                subreddit_label,
                Qt.TextElideMode.ElideRight,
                available_header_width,
            )
            # Draw header text with shadow for better readability
            draw_text_with_shadow(painter, x, baseline_y, drawn_label, font_size=self._header_font_pt)
            header_text_width = header_metrics.horizontalAdvance(drawn_label)
        else:
            header_text_width = 0

        header_height = header_metrics.height()
        header_bottom = header_top + header_height + 8

        header_width = (x - rect.left()) + header_text_width + 8
        if header_width > 0:
            self._header_hit_rect = QRect(
                rect.left(),
                header_top,
                min(header_width, rect.width()),
                header_height + 8,
            )

        # Posts list
        title_font = QFont(self._font_family, self._font_size, QFont.Weight.Bold)
        title_metrics = QFontMetrics(title_font)
        age_font_size = max(8, self._font_size - 3)
        age_font = QFont(self._font_family, age_font_size, QFont.Weight.DemiBold)
        painter.setFont(age_font)
        age_metrics = QFontMetrics(age_font)

        now_ts = time.time()
        age_labels: List[str] = []
        for post in self._posts:
            age_labels.append(self._format_age(post.created_utc, now_ts))

        max_age_width = 0
        for label in age_labels:
            if not label:
                continue
            w = age_metrics.horizontalAdvance(label)
            if w > max_age_width:
                max_age_width = w
        age_col_width = max(max_age_width, 48)

        line_height = max(age_metrics.height(), title_metrics.height()) + 4

        y = header_bottom + 4
        self._row_hit_rects = []
        row_bottoms: List[int] = []

        for idx, post in enumerate(self._posts):
            row_spacing = max(0, int(self._row_vertical_spacing))
            if y + line_height > rect.bottom():
                break

            age_text = age_labels[idx] if idx < len(age_labels) else ""

            painter.setFont(age_font)
            painter.setPen(QColor(200, 200, 200, 220))
            age_rect = QRect(rect.left(), y, age_col_width, line_height)
            # Draw age text with shadow (smaller text, less shadow)
            draw_text_rect_with_shadow(
                painter,
                age_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                age_text,
                font_size=age_font_size,
            )

            painter.setFont(title_font)
            painter.setPen(self._text_color)
            title_x = rect.left() + age_col_width + 8
            available_width = max(0, rect.right() - title_x)
            if available_width <= 0:
                break
            full_title = post.title
            display_title = full_title

            trim_index = -1
            for sep in (" - ", " – "):
                idx = display_title.find(sep)
                if idx > 0:
                    trim_index = idx
                    break
            if trim_index > 0:
                display_title = display_title[:trim_index].rstrip()

            # Apply smart title case (preserves acronyms, handles small words)
            display_title = _smart_title_case(display_title)

            measured_width = title_metrics.horizontalAdvance(display_title)
            if measured_width > available_width:
                display_title = title_metrics.elidedText(
                    display_title,
                    Qt.TextElideMode.ElideRight,
                    available_width,
                )
            title_y = y + title_metrics.ascent()
            # Draw title with shadow for better readability
            draw_text_with_shadow(painter, title_x, title_y, display_title, font_size=self._font_size)

            row_rect = QRect(rect.left(), y, rect.width(), line_height)
            self._row_hit_rects.append((row_rect, post.url, full_title))

            row_bottoms.append(y + line_height)
            y += line_height + row_spacing

        if self._show_separators and row_bottoms:
            try:
                pen = painter.pen()
                sep_color = self._bg_border_color
                if sep_color.alpha() <= 0:
                    sep_color = QColor(
                        self._text_color.red(),
                        self._text_color.green(),
                        self._text_color.blue(),
                        int(self._text_color.alpha() * 0.4),
                    )
                pen.setColor(sep_color)
                pen.setWidth(1)
                painter.setPen(pen)

                left = rect.left()
                right = rect.right()
                for y_line in row_bottoms[:-1]:
                    painter.drawLine(left, y_line, right, y_line)
            except Exception:
                pass

    def resolve_click_target(self, local_pos: QPoint) -> Optional[str]:
        """Return the Reddit URL associated with the given click, if any."""
        header_rect = self._header_hit_rect
        if header_rect is not None and header_rect.contains(local_pos):
            slug = self._subreddit
            if slug:
                return f"https://www.reddit.com/r/{slug}"
            return "https://www.reddit.com"

        for rect, url, _title in self._row_hit_rects:
            if rect.contains(local_pos):
                return url
        return None

    def handle_click(self, local_pos: QPoint) -> bool:
        """Handle a click in widget-local coordinates.

        Args:
            local_pos: Click position in widget-local coordinates

        Returns:
            True if a link was clicked and opened, False otherwise.
        """
        url = self.resolve_click_target(local_pos)
        if not url:
            return False

        try:
            QDesktopServices.openUrl(QUrl(url))
            logger.info("[REDDIT] Opened %s", url)
            return True
        except Exception:
            logger.debug("[REDDIT] Failed to open URL %s", url, exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_card_height_from_content(self, visible_rows: Optional[int] = None) -> None:
        try:
            rows = int(visible_rows) if visible_rows is not None else 0
        except Exception:
            rows = 0
        if rows <= 0:
            rows = len(self._posts) or self._limit or 1

        rows = max(1, min(rows, max(1, self._limit)))

        base_font_pt = max(8, int(self._font_size))
        header_font_pt = int(self._header_font_pt or base_font_pt)

        header_font = QFont(self._font_family, header_font_pt, QFont.Weight.Bold)
        header_metrics = QFontMetrics(header_font)
        header_height = header_metrics.height() + 8

        age_font_pt = max(8, base_font_pt - 3)
        age_font = QFont(self._font_family, age_font_pt, QFont.Weight.DemiBold)
        age_metrics = QFontMetrics(age_font)

        title_font = QFont(self._font_family, base_font_pt, QFont.Weight.Bold)
        title_metrics = QFontMetrics(title_font)

        line_height = max(age_metrics.height(), title_metrics.height()) + 4

        # Base vertical padding inside the card
        card_padding = 22  # 6 + 6 + 10

        # Use consistent small spacing between rows
        self._row_vertical_spacing = 4 if rows > 1 else 0
        
        # Get content margins
        try:
            margins = self.contentsMargins()
            margin_top = margins.top()
            margin_bottom = margins.bottom()
        except Exception:
            margin_top = 0
            margin_bottom = 0

        # Calculate exact height needed for content
        content_height = (
            header_height
            + (rows * line_height)
            + (max(0, rows - 1) * self._row_vertical_spacing)
            + card_padding
        )
        
        # Add margins and a small safety buffer
        target = content_height + margin_top + margin_bottom + 4

        try:
            self.setMinimumHeight(target)
            self.setMaximumHeight(target)
        except Exception:
            try:
                self.setMinimumHeight(target)
            except Exception:
                pass

    def _update_card_height_from_limit(self) -> None:
        # Fallback used when the limit changes before we have data.
        self._update_card_height_from_content(self._limit)

    def _format_age(self, created_utc: float, now_ts: Optional[float] = None) -> str:
        if created_utc <= 0 and now_ts is None:
            return ""
        if now_ts is None:
            now_ts = time.time()
        delta = max(0.0, float(now_ts) - float(created_utc))
        minutes = int(delta // 60)
        hours = int(delta // 3600)
        days = int(delta // 86400)
        if minutes < 1:
            minutes = 1
        if hours < 1:
            return f"{minutes}M AGO"
        if days < 1:
            return f"{hours}HR AGO"
        if days < 7:
            return f"{days}D AGO"
        weeks = days // 7
        if weeks < 52:
            return f"{weeks}W AGO"
        years = days // 365
        return f"{years}Y AGO"

    def _start_widget_fade_in(self, duration_ms: int = 1000) -> None:
        logger.debug("[REDDIT] _start_widget_fade_in: duration_ms=%s", duration_ms)
        if duration_ms <= 0:
            if self.parent():
                try:
                    self._update_position()
                except Exception:
                    pass
            try:
                self.show()
            except Exception:
                pass
            try:
                ShadowFadeProfile.attach_shadow(
                    self,
                    self._shadow_config,
                    has_background_frame=self._show_background,
                )
            except Exception:
                logger.debug(
                    "[REDDIT] Failed to attach shadow without fade",
                    exc_info=True,
                )
            return

        if self.parent():
            try:
                self._update_position()
            except Exception:
                pass

        try:
            ShadowFadeProfile.start_fade_in(
                self,
                self._shadow_config,
                has_background_frame=self._show_background,
            )
        except Exception:
            logger.debug(
                "[REDDIT] _start_widget_fade_in fallback: ShadowFadeProfile failed",
                exc_info=True,
            )
            try:
                self.show()
            except Exception:
                pass
            if self._shadow_config is not None:
                try:
                    apply_widget_shadow(
                        self,
                        self._shadow_config,
                        has_background_frame=self._show_background,
                    )
                except Exception:
                    logger.debug(
                        "[REDDIT] Failed to apply widget shadow in fallback path",
                        exc_info=True,
                    )

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._enabled and self._has_seen_first_sample and self.parent():
            try:
                self._update_position()
            except Exception:
                pass

    def handle_hover(self, local_pos: QPoint, global_pos: QPoint) -> None:
        if not self._row_hit_rects:
            if self._hover_timer is not None:
                self._hover_timer.stop()
            self._hover_row_index = None
            QToolTip.hideText()
            return

        row_index = -1
        for idx, (rect, _url, _title) in enumerate(self._row_hit_rects):
            if rect.contains(local_pos):
                row_index = idx
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
        _rect, _url, title = self._row_hit_rects[row_index]
        self._hover_title = title

        if self._hover_timer is None:
            self._hover_timer = QTimer(self)
            self._hover_timer.setSingleShot(True)
            self._hover_timer.timeout.connect(self._show_title_tooltip)
        else:
            self._hover_timer.stop()

        self._hover_timer.start(2000)

    def _show_title_tooltip(self) -> None:
        if not self._hover_title:
            return
        pos = self._hover_global_pos
        if pos is None:
            return
        try:
            QToolTip.showText(pos, self._hover_title, self)
        except Exception:
            pass

    def _paint_header_frame(self, painter: QPainter) -> None:
        """Paint a rounded sub-frame around the logo + subreddit header.

        The frame inherits the widget's background/border colours so it feels
        like a subtle inner container, mirroring the Spotify widget header.
        Now includes a drop shadow for better visual depth.
        """

        if not self._show_background:
            return
        if self._bg_border_width <= 0 or self._bg_border_color.alpha() <= 0:
            return

        margins = self.contentsMargins()
        left = margins.left() - 4
        top = margins.top() + 2

        try:
            header_font_pt = int(self._header_font_pt) if self._header_font_pt > 0 else self._font_size
        except Exception:
            header_font_pt = self._font_size

        font = QFont(self._font_family, header_font_pt, QFont.Weight.Bold)
        fm = QFontMetrics(font)
        text = f"r/{self._subreddit}" if self._subreddit else "r/<subreddit>"
        text_w = fm.horizontalAdvance(text)
        text_h = fm.height()

        logo_size = max(1, int(self._header_logo_size))
        gap = max(6, self._header_logo_margin - logo_size)

        pad_x = 8
        pad_y = 4

        inner_w = logo_size + gap + text_w
        row_h = max(text_h, logo_size)

        total_w = int(inner_w + pad_x * 2)
        total_h = int(row_h + pad_y * 2)

        max_width = max(0, self.width() - margins.right() - left - 10)
        if max_width and total_w > max_width:
            total_w = max_width

        if total_w <= 0 or total_h <= 0:
            return

        rect = QRect(left, top, total_w, total_h)
        radius = min(rect.width(), rect.height()) / 2.5

        # Use shadow helper for border with drop shadow
        draw_rounded_rect_with_shadow(
            painter,
            rect,
            radius,
            self._bg_border_color,
            max(1, self._bg_border_width),
        )

    def _update_stylesheet(self) -> None:
        if self._show_background:
            self.setStyleSheet(
                """
                QLabel {
                    color: rgba(%d, %d, %d, %d);
                    background-color: rgba(%d, %d, %d, %d);
                    border: %dpx solid rgba(%d, %d, %d, %d);
                    border-radius: 8px;
                    padding: 6px 28px 6px 21px;
                }
                """
                % (
                    self._text_color.red(),
                    self._text_color.green(),
                    self._text_color.blue(),
                    self._text_color.alpha(),
                    self._bg_color.red(),
                    self._bg_color.green(),
                    self._bg_color.blue(),
                    self._bg_color.alpha(),
                    self._bg_border_width,
                    self._bg_border_color.red(),
                    self._bg_border_color.green(),
                    self._bg_border_color.blue(),
                    self._bg_border_color.alpha(),
                )
            )
        else:
            self.setStyleSheet(
                """
                QLabel {
                    color: rgba(%d, %d, %d, %d);
                    background-color: transparent;
                    padding: 6px 28px 6px 21px;
                }
                """
                % (
                    self._text_color.red(),
                    self._text_color.green(),
                    self._text_color.blue(),
                    self._text_color.alpha(),
                )
            )

    def _update_position(self) -> None:
        if not self.parent():
            return

        parent_width = self.parent().width()
        parent_height = self.parent().height()
        widget_width = self.width()
        widget_height = self.height()

        edge = max(10, self._margin)
        pos = self._reddit_position
        
        if pos == RedditPosition.TOP_LEFT:
            x = edge
            y = edge
        elif pos == RedditPosition.TOP_RIGHT:
            x = parent_width - widget_width - edge
            y = edge
        elif pos == RedditPosition.BOTTOM_LEFT:
            x = edge
            y = parent_height - widget_height - edge
        elif pos == RedditPosition.BOTTOM_RIGHT:
            x = parent_width - widget_width - edge
            y = parent_height - widget_height - edge
        else:
            x = edge
            y = edge

        # Apply pixel shift and stack offset (inherited from BaseOverlayWidget)
        x += self._pixel_shift_offset.x() + self._stack_offset.x()
        y += self._pixel_shift_offset.y() + self._stack_offset.y()

        self.move(x, y)
        
        # Notify PixelShiftManager of our new "original" position so it doesn't
        # apply offsets to a stale position. This prevents the teleport bug where
        # the widget briefly appears at an old position during transitions.
        parent = self.parent()
        if parent is not None:
            psm = getattr(parent, "_pixel_shift_manager", None)
            if psm is not None and hasattr(psm, "update_original_position"):
                try:
                    psm.update_original_position(self)
                except Exception:
                    pass

    def _load_brand_pixmap(self) -> Optional[QPixmap]:
        """Load Reddit logo glyph from images/Reddit_Logo_C.png if present."""

        try:
            from pathlib import Path

            images_dir = (Path(__file__).resolve().parent.parent / "images").resolve()
            logo_path = images_dir / "Reddit_Logo_C.png"
            pm = QPixmap(str(logo_path))
            if not pm.isNull():
                logger.debug(
                    "[REDDIT] Loaded logo pixmap from %s (exists=%s, null=%s)",
                    logo_path,
                    logo_path.exists(),
                    pm.isNull(),
                )
                return pm
        except Exception:
            logger.debug("[REDDIT] Failed to load Reddit_Logo_C.png", exc_info=True)
        return None

    @staticmethod
    def _normalise_subreddit(name: str) -> str:
        """Normalise user input into a clean subreddit slug.

        Accepts values like "wallpapers", "r/wallpapers", or
        "https://www.reddit.com/r/wallpapers" and extracts ``wallpapers``.
        """

        slug = (name or "").strip()
        if not slug:
            return ""

        slug = slug.replace("\\", "/")
        lower = slug.lower()
        if "reddit.com" in lower:
            # Strip scheme and domain
            try:
                parts = lower.split("/r/")[1]
                slug = parts.split("/")[0]
            except Exception:
                pass
        elif lower.startswith("/r/"):
            slug = slug[3:]
        elif lower.startswith("r/"):
            slug = slug[2:]

        # Final cleanup
        slug = slug.strip("/ ")
        return slug


def _try_bring_reddit_window_to_front() -> None:
    """Best-effort attempt to foreground a browser window with 'reddit' in title.

    Windows-only; no-op on other platforms. All failures are silent to avoid
    introducing new focus or flicker problems.
    """

    if sys.platform != "win32":  # pragma: no cover - platform guard
        return

    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    except Exception:
        return

    try:
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    except Exception:
        return

    try:
        user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    except Exception:
        return

    candidates: list[wintypes.HWND] = []

    @EnumWindowsProc
    def _enum_proc(hwnd: wintypes.HWND, lparam: wintypes.LPARAM) -> bool:  # noqa: ARG001
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value or ""
            if "reddit" in title.lower():
                candidates.append(hwnd)
        except Exception:
            # Enum callbacks must not raise; keep scanning.
            return True
        return True

    try:
        user32.EnumWindows(_enum_proc, 0)
    except Exception:
        return

    if not candidates:
        return

    hwnd = candidates[0]
    try:
        user32.SetForegroundWindow(hwnd)
    except Exception:
        # Foreground requests may fail silently depending on OS policy.
        return
