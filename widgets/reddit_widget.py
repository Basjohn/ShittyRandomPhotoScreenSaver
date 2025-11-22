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

import requests

from PySide6.QtCore import Qt, QTimer, QRect, QPoint, QUrl, QVariantAnimation
from PySide6.QtGui import QFont, QColor, QPainter, QFontMetrics, QDesktopServices, QPixmap, QPainterPath
from PySide6.QtWidgets import QLabel, QWidget, QToolTip, QGraphicsOpacityEffect

from core.logging.logger import get_logger, is_verbose_logging
from core.threading.manager import ThreadManager
from widgets.shadow_utils import apply_widget_shadow, ShadowFadeProfile

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


class RedditWidget(QLabel):
    """Reddit widget for displaying subreddit entries.

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

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        subreddit: str = "wallpapers",
        position: RedditPosition = RedditPosition.TOP_RIGHT,
    ) -> None:
        super().__init__(parent)

        # Logical placement and source configuration
        self._position = position
        self._subreddit: str = self._normalise_subreddit(subreddit)
        self._sort: str = "hot"
        self._limit: int = 10
        self._refresh_interval = timedelta(minutes=10)

        self._thread_manager: Optional[ThreadManager] = None
        self._update_timer: Optional[QTimer] = None
        self._enabled: bool = False

        # Cached posts and click hit-rects
        self._posts: List[RedditPost] = []
        self._row_hit_rects: List[tuple[QRect, str, str]] = []
        self._has_displayed_valid_data: bool = False
        self._has_seen_first_sample: bool = False

        # Styling defaults (mirrors MediaWidget/WeatherWidget)
        self._font_family = "Segoe UI"
        self._font_size = 18
        self._text_color = QColor(255, 255, 255, 230)
        self._margin = 20

        # Background frame settings (driven by settings via setters)
        self._show_background = False
        self._bg_opacity = 0.9
        self._bg_color = QColor(64, 64, 64, int(255 * self._bg_opacity))
        self._bg_border_width = 2
        self._bg_border_color = QColor(128, 128, 128, 200)

        # Shared shadow configuration (from DisplayWidget)
        self._shadow_config: Optional[Dict[str, Any]] = None

        # Header/logo metrics, mirroring the Spotify card approach
        self._header_font_pt: int = self._font_size
        self._header_logo_size: int = max(12, int(self._font_size * 1.3))
        self._header_logo_margin: int = self._header_logo_size
        self._brand_pixmap: Optional[QPixmap] = self._load_brand_pixmap()
        self._header_hit_rect: Optional[QRect] = None

        # Fade and hover state
        self._widget_fade_anim: Optional[QVariantAnimation] = None
        self._widget_opacity_effect: Optional[QGraphicsOpacityEffect] = None
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

        self._update_stylesheet()
        try:
            self.move(10000, 10000)
        except Exception:
            pass
        self.hide()

    def start(self) -> None:
        """Begin periodic Reddit fetches and show widget on first data."""

        if self._enabled:
            logger.warning("[FALLBACK] Reddit widget already running")
            return

        self._enabled = True
        self.hide()
        self._schedule_timer()
        self._fetch_feed()

    def stop(self) -> None:
        """Stop refreshes and hide widget."""

        if not self._enabled:
            return

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
        self._position = position
        if self._enabled and self.parent():
            self._update_position()

    def set_font_family(self, family: str) -> None:
        self._font_family = family or self._font_family
        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)
        self.setFont(font)

    def set_font_size(self, size: int) -> None:
        if size <= 0:
            logger.warning("[FALLBACK] Invalid Reddit font size %s, using %s", size, self._font_size)
            return
        self._font_size = size
        font = QFont(self._font_family, self._font_size, QFont.Weight.Normal)
        self.setFont(font)

    def set_text_color(self, color: QColor) -> None:
        self._text_color = color
        self._update_stylesheet()

    def set_margin(self, margin: int) -> None:
        if margin < 0:
            margin = 20
        self._margin = margin
        if self._enabled and self.parent():
            self._update_position()

    def set_show_background(self, show: bool) -> None:
        self._show_background = bool(show)
        self._update_stylesheet()

    def set_show_separators(self, show: bool) -> None:
        self._show_separators = bool(show)
        self.update()

    def set_background_color(self, color: QColor) -> None:
        self._bg_color = color
        if self._show_background:
            self._update_stylesheet()

    def set_background_opacity(self, opacity: float) -> None:
        self._bg_opacity = max(0.0, min(1.0, float(opacity)))
        self._bg_color.setAlpha(int(255 * self._bg_opacity))
        if self._show_background:
            self._update_stylesheet()

    def set_background_border(self, width: int, color: QColor) -> None:
        self._bg_border_width = max(0, int(width))
        self._bg_border_color = color
        if self._show_background:
            self._update_stylesheet()

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
        if self._update_timer is None:
            self._update_timer = QTimer(self)
            self._update_timer.timeout.connect(self._fetch_feed)
        self._update_timer.start(int(self._refresh_interval.total_seconds() * 1000))

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

        first_sample = not self._has_seen_first_sample
        if first_sample:
            self._has_seen_first_sample = True
            parent = self.parent()

            def _starter() -> None:
                self._start_widget_fade_in(1500)

            if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
                try:
                    parent.request_overlay_fade_sync("reddit", _starter)
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
            painter.drawText(x, baseline_y, drawn_label)
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
            painter.drawText(
                age_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                age_text,
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

            measured_width = title_metrics.horizontalAdvance(display_title)
            if measured_width > available_width:
                display_title = title_metrics.elidedText(
                    display_title,
                    Qt.TextElideMode.ElideRight,
                    available_width,
                )
            title_y = y + title_metrics.ascent()
            painter.drawText(title_x, title_y, display_title)

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

    def handle_click(self, local_pos: QPoint) -> bool:
        """Handle a click in widget-local coordinates.

        Returns True if a row or the header was hit and a browser open attempt
        was made.
        """
        header_rect = self._header_hit_rect
        if header_rect is not None and header_rect.contains(local_pos):
            slug = self._subreddit
            if slug:
                url = f"https://www.reddit.com/r/{slug}"
            else:
                url = "https://www.reddit.com"
            try:
                QDesktopServices.openUrl(QUrl(url))
                logger.info("[REDDIT] Opened subreddit %s", url)
                return True
            except Exception:
                logger.debug("[REDDIT] Failed to open subreddit URL %s", url, exc_info=True)
                return False

        for rect, url, _title in self._row_hit_rects:
            if rect.contains(local_pos):
                try:
                    QDesktopServices.openUrl(QUrl(url))
                    logger.info("[REDDIT] Opened %s", url)
                    return True
                except Exception:
                    logger.debug("[REDDIT] Failed to open URL %s", url, exc_info=True)
                    return False
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

        # Base vertical padding inside the card, excluding contentsMargins.
        card_padding = 6 + 6 + 10
        base_min = int(220 * 1.2)
        if self._limit <= 5:
            base_min = int(base_min * 1.25)

        content_no_gaps = header_height + (rows * line_height) + card_padding
        target = max(base_min, content_no_gaps)

        if rows > 1:
            slack = max(0, target - content_no_gaps)
            max_gap = 6
            base_gap = 0
            try:
                base_gap = int(min(max_gap, slack // (rows - 1))) if slack > 0 else 0
            except Exception:
                base_gap = 0

            # Give low-item modes a little extra breathing room regardless
            # of the exact slack so that 5-item ("4-mode") and 10-item
            # layouts do not feel cramped.
            extra_gap = 0
            try:
                limit_val = int(self._limit)
            except Exception:
                limit_val = rows
            if limit_val <= 5:
                extra_gap = 2
            elif limit_val <= 10:
                extra_gap = 1

            gap = min(max_gap, base_gap + extra_gap)
            self._row_vertical_spacing = max(0, gap)
        else:
            self._row_vertical_spacing = 0

        # Ensure the final widget height is large enough for the header plus
        # the requested number of rows inside the actual paint rect,
        # including current row spacing and contents margins. This prevents
        # low-item modes (e.g. 4-item) from losing the last row due to
        # padding/margin discrepancies.

        try:
            margins = self.contentsMargins()
            margin_top = margins.top()
            margin_bottom = margins.bottom()
        except Exception:
            margin_top = 0
            margin_bottom = 0

        inner_required = (
            header_height
            + (rows * line_height)
            + (max(0, rows - 1) * self._row_vertical_spacing)
            + 8  # extra breathing room beneath the last row
        )
        required_total = inner_required + margin_top + margin_bottom

        target = max(target, required_total)

        # For low-item layouts (the 4-item mode), redistribute any remaining
        # vertical slack into the spacing between rows so that the extra
        # height becomes comfortable padding instead of a large empty band
        # beneath the last row.
        try:
            limit_for_spacing = int(self._limit)
        except Exception:
            limit_for_spacing = rows
        if rows > 1 and limit_for_spacing <= 5:
            used_inner = (
                header_height
                + (rows * line_height)
                + (max(0, rows - 1) * self._row_vertical_spacing)
                + 8
            )
            used_total = used_inner + margin_top + margin_bottom
            slack_total = max(0, int(target) - int(used_total))
            if slack_total > 0:
                extra_per_gap = slack_total // max(1, rows - 1)
                # Allow a larger gap for 4-item layouts but keep a hard cap
                # so things do not look exaggerated.
                max_comfy_gap = 18
                new_gap = min(
                    max_comfy_gap,
                    int(self._row_vertical_spacing) + int(extra_per_gap),
                )
                self._row_vertical_spacing = max(0, new_gap)

                used_inner = (
                    header_height
                    + (rows * line_height)
                    + (max(0, rows - 1) * self._row_vertical_spacing)
                    + 8
                )
                target = used_inner + margin_top + margin_bottom

            # Add a tiny safety margin so the last row never clips due to
            # rounding between the layout and paint paths. This keeps the
            # current spacing but guarantees all 4 rows are fully visible.
            target = int(target) + 4

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
        if created_utc <= 0:
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

        painter.save()
        try:
            pen = painter.pen()
            pen.setColor(self._bg_border_color)
            pen.setWidth(max(1, self._bg_border_width))
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            path = QPainterPath()
            radius = min(rect.width(), rect.height()) / 2.5
            path.addRoundedRect(rect, radius, radius)
            painter.drawPath(path)
        finally:
            painter.restore()

    def _update_stylesheet(self) -> None:
        if self._show_background:
            self.setStyleSheet(
                """
                QLabel {
                    color: rgba(%d, %d, %d, %d);
                    background-color: rgba(%d, %d, %d, %d);
                    border: %dpx solid rgba(%d, %d, %d, %d);
                    border-radius: 8px;
                    padding: 6px 12px 6px 16px;
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
                    padding: 6px 12px 6px 16px;
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
        if self._position == RedditPosition.TOP_LEFT:
            x = edge
            y = edge
        elif self._position == RedditPosition.TOP_RIGHT:
            x = parent_width - widget_width - edge
            y = edge
        elif self._position == RedditPosition.BOTTOM_LEFT:
            x = edge
            y = parent_height - widget_height - edge
        elif self._position == RedditPosition.BOTTOM_RIGHT:
            x = parent_width - widget_width - edge
            y = parent_height - widget_height - edge
        else:
            x = edge
            y = edge

        self.move(x, y)

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
