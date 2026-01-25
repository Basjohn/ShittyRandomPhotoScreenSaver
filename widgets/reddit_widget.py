"""Reddit overlay widget for screensaver.

Displays a small card listing the top N posts from a configured
subreddit, styled similarly to the Spotify media widget.

The widget is strictly read-only: clicking a row opens the post in the
system default browser. Interaction is gated by DisplayWidget's
Ctrl-held / hard-exit modes; this widget itself does not handle mouse
or keyboard input directly.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple, Callable
from datetime import timedelta, datetime
import time
import re
import sys
import ctypes
from ctypes import wintypes
import json
from pathlib import Path

import requests

from PySide6.QtCore import Qt, QTimer, QRect, QPoint, QUrl
from PySide6.QtGui import QFont, QColor, QPainter, QFontMetrics, QDesktopServices, QPixmap
from PySide6.QtWidgets import QWidget, QToolTip
from shiboken6 import isValid as shiboken_isValid

from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled
from core.performance import widget_paint_sample
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
    """Reddit widget position on screen."""

    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    CENTER = "center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
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
        
        # CRITICAL: Defer visibility until fade sync triggers
        # This prevents the widget from flashing before the compositor is ready
        self._defer_visibility_for_fade_sync = True

        # Logical placement and source configuration
        self._reddit_position = position  # Keep original enum for compatibility
        self._subreddit: str = self._normalise_subreddit(subreddit)
        self._sort: str = "hot"
        self._limit: int = 10  # Target limit (may be reduced during progressive loading)
        self._target_limit: int = 10  # User's desired limit
        self._refresh_interval = timedelta(minutes=10)
        self._display_refresh_interval = timedelta(minutes=10)
        self._last_display_refresh: Optional[datetime] = None
        self._display_refresh_deadline: Optional[datetime] = None
        self._force_next_display_refresh: bool = True
        self._last_display_signature: Optional[Tuple[Any, ...]] = None
        self._pending_payload_signature: Optional[Tuple[Any, ...]] = None
        self._pending_display_payload: Optional[Tuple[List[RedditPost], bool]] = None
        self._pending_refresh_deadline_token: Optional[object] = None

        self._update_timer: Optional[QTimer] = None
        self._update_timer_handle: Optional[OverlayTimerHandle] = None

        # Progressive loading: start with fewer posts, expand as rate limit allows
        # Stages: 4 → 10 → target (if target > 10)
        self._progressive_stage: int = 0  # 0=initial(4), 1=medium(10), 2=full(target)
        self._progressive_stages: List[int] = [4, 10]  # Will add target if > 10
        self._all_fetched_posts: List[RedditPost] = []  # Store all posts for progressive reveal

        # Cached posts and click hit-rects
        self._posts: List[RedditPost] = []
        self._row_hit_rects: List[tuple[QRect, str, str]] = []
        self._has_displayed_valid_data: bool = False
        self._has_seen_first_sample: bool = False
        
        # Cache key for persistent storage (set by factory, fallback to subreddit)
        self._cache_key: str = self._subreddit
        
        # Paint caching: only repaint when data changes (every 10 min)
        self._cached_content_pixmap: Optional[QPixmap] = None
        self._cache_invalidated: bool = True  # Start invalidated to force first paint

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
        except Exception as e:
            logger.debug("[REDDIT] Exception suppressed: %s", e)

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
        except Exception as e:
            logger.debug("[REDDIT] Exception suppressed: %s", e)
    
    def _update_content(self) -> None:
        """Required by BaseOverlayWidget - refresh reddit display."""
        self._fetch_feed()

    # -------------------------------------------------------------------------
    # Lifecycle Implementation Hooks
    # -------------------------------------------------------------------------
    
    def _initialize_impl(self) -> None:
        """Initialize reddit resources (lifecycle hook)."""
        logger.debug("[LIFECYCLE] RedditWidget initialized")
    
    def _activate_impl(self) -> None:
        """Activate reddit widget - start fetching (lifecycle hook)."""
        if not self._ensure_thread_manager("RedditWidget._activate_impl"):
            raise RuntimeError("ThreadManager not available")
        
        self._schedule_timer()
        self._fetch_feed()
        logger.debug("[LIFECYCLE] RedditWidget activated")
    
    def _deactivate_impl(self) -> None:
        """Deactivate reddit widget - stop fetching (lifecycle hook)."""
        if self._update_timer_handle is not None:
            try:
                self._update_timer_handle.stop()
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)
            self._update_timer_handle = None
        
        if self._update_timer is not None:
            try:
                self._update_timer.stop()
                self._update_timer.deleteLater()
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)
            self._update_timer = None
        
        self._posts.clear()
        self._row_hit_rects.clear()
        logger.debug("[LIFECYCLE] RedditWidget deactivated")
    
    def _cleanup_impl(self) -> None:
        """Clean up reddit resources (lifecycle hook)."""
        self._deactivate_impl()
        if self._hover_timer is not None:
            try:
                self._hover_timer.stop()
                self._hover_timer.deleteLater()
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)
            self._hover_timer = None
        logger.debug("[LIFECYCLE] RedditWidget cleaned up")
    
    # -------------------------------------------------------------------------
    # Legacy Start/Stop Methods (for backward compatibility)
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Start fetching Reddit posts."""
        if self._enabled:
            logger.debug("Reddit widget already running")
            return
        if not self._ensure_thread_manager("RedditWidget.start"):
            return

        self._enabled = True
        
        # CRITICAL: Hide widget immediately - it will be shown by fade sync
        self.hide()
        
        # Setup progressive loading stages based on target limit
        self._setup_progressive_stages()
        
        # Load cached posts for data preparation (widget stays hidden)
        cached_posts = self._load_cached_posts()
        if cached_posts:
            logger.info("[REDDIT] Loaded %d cached posts (cache_key=%s)", 
                       len(cached_posts), self._cache_key)
            self._all_fetched_posts = cached_posts
            self._progressive_stage = self._get_stage_for_post_count(len(cached_posts))
            # Prepare data and force a display refresh so startup shows immediately.
            self._prepare_posts_for_display(cached_posts, force_refresh=True)
        else:
            logger.info("[REDDIT] No cached posts found (cache_key=%s)", self._cache_key)
        
        self._schedule_timer()
        self._fetch_feed()

    def stop(self) -> None:
        """Stop refreshes and hide widget."""

        if not self._enabled:
            return

        if self._update_timer_handle is not None:
            try:
                self._update_timer_handle.stop()
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)
            self._update_timer_handle = None

        if self._update_timer is not None:
            try:
                self._update_timer.stop()
                self._update_timer.deleteLater()
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)
            self._update_timer = None

        self._enabled = False
        self._posts.clear()
        self._row_hit_rects.clear()
        try:
            self.hide()
        except Exception as e:
            logger.debug("[REDDIT] Exception suppressed: %s", e)

    def cleanup(self) -> None:
        logger.debug("Cleaning up Reddit widget")
        self.stop()
        try:
            if self._hover_timer is not None:
                self._hover_timer.stop()
                self._hover_timer.deleteLater()
        except Exception as e:
            logger.debug("[REDDIT] Exception suppressed: %s", e)
        self._hover_timer = None

    def is_running(self) -> bool:
        return self._enabled

    # ------------------------------------------------------------------
    # External configuration (called from DisplayWidget/Settings)
    # ------------------------------------------------------------------

    def set_thread_manager(self, thread_manager: ThreadManager) -> None:
        self._thread_manager = thread_manager

    def set_subreddit(self, subreddit: str) -> None:
        self._subreddit = self._normalise_subreddit(subreddit)
        # Refresh immediately on change
        self._request_display_refresh()
        if self._enabled:
            self._fetch_feed()

    def set_position(self, position: RedditPosition) -> None:
        """Set widget position using RedditPosition enum."""
        self._reddit_position = position
        # Update base class position
        overlay_pos = OverlayPosition(position.value)
        super().set_position(overlay_pos)
        self._request_display_refresh()
        if self._all_fetched_posts:
            self._display_progressive_posts()

    def set_show_separators(self, show: bool) -> None:
        """Enable or disable row separators."""
        self._show_separators = bool(show)
        self._request_display_refresh()
        if self._all_fetched_posts:
            self._display_progressive_posts()
        else:
            self.update()

    def set_item_limit(self, limit: int) -> None:
        self._limit = max(1, min(int(limit), 25))
        self._target_limit = self._limit  # Store user's desired limit
        self._update_card_height_from_limit()
        self._request_display_refresh()
        if self._enabled and self._posts:
            # Trim existing posts to the new visible limit
            self._posts = self._posts[: self._limit]
            self.update()
        if self._all_fetched_posts:
            self._setup_progressive_stages()
            self._display_progressive_posts()

    # ------------------------------------------------------------------
    # Progressive Loading
    # ------------------------------------------------------------------

    def _setup_progressive_stages(self) -> None:
        """Setup progressive loading stages based on target limit.
        
        Progressive loading allows widgets to display partial data immediately
        while respecting rate limits. Stages: 4 → 10 → target (if > 10).
        """
        self._progressive_stages = [4]
        if self._target_limit > 4:
            self._progressive_stages.append(min(10, self._target_limit))
        if self._target_limit > 10:
            self._progressive_stages.append(self._target_limit)
        self._progressive_stage = 0
        logger.debug("[REDDIT] Progressive stages setup: %s (target=%d)", 
                    self._progressive_stages, self._target_limit)

    def _get_stage_for_post_count(self, post_count: int) -> int:
        """Get the appropriate stage index for a given post count."""
        for i, stage_limit in enumerate(self._progressive_stages):
            if post_count <= stage_limit:
                return i
        return len(self._progressive_stages) - 1

    def _get_current_stage_limit(self) -> int:
        """Get the post limit for the current progressive stage."""
        if self._progressive_stage < len(self._progressive_stages):
            return self._progressive_stages[self._progressive_stage]
        return self._target_limit

    def _display_progressive_posts(self, fade: bool = False) -> None:
        """Display posts up to current progressive stage limit.
        
        Args:
            fade: If True, fade in the widget after size change (for stage transitions)
        """
        stage_limit = self._get_current_stage_limit()
        posts_to_show = self._all_fetched_posts[:stage_limit]
        
        if not posts_to_show:
            return

        signature = self._build_display_signature(posts_to_show, stage_limit)
        now = datetime.now()
        refresh_due = (
            self._force_next_display_refresh
            or self._last_display_refresh is None
            or self._display_refresh_deadline is None
            or now >= self._display_refresh_deadline
        )

        if not refresh_due:
            if signature != self._last_display_signature:
                self._pending_payload_signature = signature
                self._pending_display_payload = (list(posts_to_show), fade)
                self._schedule_pending_refresh_consumption()
            return

        if signature == self._last_display_signature and not self._force_next_display_refresh:
            return

        self._apply_display_payload(posts_to_show, signature, fade)

        logger.debug(
            "[REDDIT] Progressive display: stage=%d, showing %d/%d posts (target=%d, fade=%s)",
            self._progressive_stage,
            len(posts_to_show),
            len(self._all_fetched_posts),
            self._target_limit,
            fade,
        )

    def _prepare_posts_for_display(
        self,
        posts: List[RedditPost],
        *,
        force_refresh: bool = False,
    ) -> None:
        """Seed posts for display while respecting the cadence gate."""
        if not posts:
            return

        # Sort posts newest-first so progressive slices stay deterministic.
        try:
            def _sort_key(p: RedditPost) -> tuple[int, float]:
                ts = float(getattr(p, "created_utc", 0.0) or 0.0)
                if ts <= 0.0:
                    return (1, 0.0)
                return (0, -ts)

            posts = sorted(posts, key=_sort_key)
        except Exception as e:
            logger.debug("[REDDIT] Exception suppressed: %s", e)

        self._all_fetched_posts = posts

        if force_refresh:
            self._request_display_refresh()

        self._display_progressive_posts()

    def _advance_progressive_stage(self) -> bool:
        """Advance to next progressive stage if possible.
        
        Returns True if advanced, False if already at final stage.
        """
        if self._progressive_stage >= len(self._progressive_stages) - 1:
            return False
        
        self._progressive_stage += 1
        # Fade in when advancing stages to avoid flash
        self._display_progressive_posts(fade=True)
        return True

    def _request_display_refresh(self) -> None:
        """Force the next display update to bypass cadence throttling."""
        self._force_next_display_refresh = True

    def _schedule_pending_refresh_consumption(self) -> None:
        """Schedule a deadline-bound flush of any pending payload."""
        deadline = self._display_refresh_deadline
        if deadline is None:
            return

        delay_ms = int(max(0, (deadline - datetime.now()).total_seconds() * 1000))
        runner: Optional[Callable[..., None]] = None
        if self._thread_manager is not None:
            runner = self._thread_manager.single_shot  # type: ignore[attr-defined]
        else:
            runner = ThreadManager.single_shot

        token = object()
        self._pending_refresh_deadline_token = token

        try:
            runner(delay_ms, self._consume_pending_payload_at_deadline, token)
        except Exception:
            self._pending_refresh_deadline_token = None
            logger.debug("[REDDIT] Failed to schedule pending payload flush", exc_info=True)

    def _consume_pending_payload_at_deadline(self, token: object) -> None:
        """Consume any queued payload once the cadence deadline elapses."""
        if token is not self._pending_refresh_deadline_token:
            return
        self._pending_refresh_deadline_token = None

        if not shiboken_isValid(self):
            return

        pending_payload = self._pending_display_payload
        if not pending_payload:
            return

        deadline = self._display_refresh_deadline
        if deadline is not None and datetime.now() < deadline:
            self._schedule_pending_refresh_consumption()
            return

        posts_to_show, fade = pending_payload
        signature = self._pending_payload_signature or self._build_display_signature(
            posts_to_show, len(posts_to_show)
        )
        self._force_next_display_refresh = True
        self._pending_display_payload = None
        self._pending_payload_signature = None
        self._apply_display_payload(posts_to_show, signature, fade)

    def _build_display_signature(
        self, posts: List[RedditPost], stage_limit: int
    ) -> Tuple[Any, ...]:
        """Return a coarse signature describing the UI-visible Reddit payload."""
        post_entries = tuple(
            (post.title, post.url, post.score, int(post.created_utc))
            for post in posts
        )
        return (
            self._progressive_stage,
            stage_limit,
            len(posts),
            self._show_separators,
            self._font_size,
            self._show_background,
            post_entries,
        )

    def _apply_display_payload(
        self,
        posts_to_show: List[RedditPost],
        signature: Tuple[Any, ...],
        fade: bool,
    ) -> None:
        """Apply a posts payload immediately and update cadence tracking."""
        self._force_next_display_refresh = False
        self._pending_payload_signature = None
        self._pending_display_payload = None
        self._pending_refresh_deadline_token = None

        self._update_posts_internal(posts_to_show, fade=fade)

        now = datetime.now()
        self._last_display_signature = signature
        self._last_display_refresh = now
        self._display_refresh_deadline = now + self._display_refresh_interval

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
        except Exception as e:
            logger.debug("[REDDIT] Exception suppressed: %s", e)
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
            import time
            start_time = time.perf_counter()
            
            # Use centralized rate limiter to coordinate with RSS source
            try:
                from core.reddit_rate_limiter import RedditRateLimiter
                wait_time = RedditRateLimiter.wait_if_needed()
                if wait_time > 0:
                    logger.info(f"[RATE_LIMIT] Reddit widget waiting {wait_time:.1f}s for rate limit")
                    time.sleep(wait_time)
                RedditRateLimiter.record_request()
            except ImportError:
                logger.debug("[REDDIT] RedditRateLimiter not available")
            
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

            if is_perf_metrics_enabled():
                logger.debug(
                    "[PERF] Reddit API call starting: subreddit=%s sort=%s",
                    subreddit, sort,
                )
            else:
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
            
            if is_perf_metrics_enabled():
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.debug(
                    "[PERF] Reddit API call completed in %.2fms: subreddit=%s posts=%d",
                    elapsed_ms, subreddit, len(payload.get("data", {}).get("children", [])),
                )

            children = payload.get("data", {}).get("children", [])
            posts: List[Dict[str, Any]] = []
            for child in children:
                data = child.get("data") or {}
                title = str(data.get("title") or "").strip()
                if not title:
                    continue
                try:
                    score = int(data.get("score") or 0)
                except Exception as e:
                    logger.debug("[REDDIT] Exception suppressed: %s", e)
                    score = 0
                try:
                    created_utc = float(data.get("created_utc") or 0.0)
                except Exception as e:
                    logger.debug("[REDDIT] Exception suppressed: %s", e)
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
                except Exception as e:
                    logger.debug("[REDDIT] Exception suppressed: %s", e)
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
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)
                score = 0

            try:
                created_utc = float(raw.get("created_utc") or 0.0)
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)
                created_utc = 0.0

            posts.append(
                RedditPost(
                    title=title,
                    url=url,
                    score=score,
                    created_utc=created_utc,
                )
            )
        
        # Store all fetched posts for progressive loading
        self._all_fetched_posts = posts
        
        # Save full post list to cache for next startup
        self._save_cached_posts(posts[:self._target_limit])

        if not posts:
            # Edge case: Rate limited and got 0 posts
            # If we have cached posts, keep showing them
            # If not, hide and wait for next fetch attempt
            if not self._has_displayed_valid_data:
                logger.info("[REDDIT] No posts fetched (likely rate limited), hiding until next attempt")
                try:
                    self.hide()
                except Exception as e:
                    logger.debug("[REDDIT] Exception suppressed: %s", e)
            else:
                logger.debug("[REDDIT] No new posts fetched, keeping existing display")
            return

        # Determine stage based on how many posts we have vs target
        new_stage = self._get_stage_for_post_count(len(posts))
        stage_changed = new_stage != self._progressive_stage
        self._progressive_stage = new_stage
        
        # Display posts progressively, with fade if stage changed
        self._display_progressive_posts(fade=stage_changed)

    def _update_posts_internal(self, posts: List[RedditPost], fade: bool = False) -> None:
        """Internal method to update displayed posts (used by progressive loading).
        
        Args:
            posts: Posts to display
            fade: If True, fade in after update (for stage transitions)
        """
        if not posts:
            return
        
        first_sample = not self._has_seen_first_sample

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

            posts = sorted(posts, key=_sort_key)
        except Exception as e:
            logger.debug("[REDDIT] Exception suppressed: %s", e)

        self._posts = posts
        self._row_hit_rects.clear()
        
        # Invalidate paint cache since data changed
        self._invalidate_paint_cache()

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
        
        if self.parent():
            self._update_position()
            # Notify parent to recalculate stacking after height change
            if hasattr(self.parent(), 'recalculate_stacking'):
                try:
                    self.parent().recalculate_stacking()
                except Exception as e:
                    logger.debug("[REDDIT] Exception suppressed: %s", e)
        
        # Trigger repaint if widget is visible
        if self.isVisible():
            self.update()
        
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
                except Exception as e:
                    logger.debug("[REDDIT] Exception suppressed: %s", e)
                    _starter()
            else:
                _starter()
        elif fade:
            # Fade in for stage transitions (not first sample)
            try:
                self._start_widget_fade_in(600)  # Shorter fade for expansions
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)
        # else: widget is already visible, just update() was called above

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
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)

    # ------------------------------------------------------------------
    # Painting & hit testing
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # type: ignore[override]
        """Paint background via QLabel then overlay header and posts.
        
        Uses paint caching: content is rendered to a pixmap only when data
        changes (every 10 minutes). Subsequent paints just blit the cached
        pixmap, reducing paint time from ~6ms to <0.5ms.
        """
        with widget_paint_sample(self, "reddit.paint"):
            self._paint_cached(event)

    def _paint_cached(self, event) -> None:
        """Paint using cached pixmap, regenerating only when invalidated."""
        # Let QLabel paint its background
        super().paintEvent(event)
        
        if not self._posts:
            return
        
        widget_size = self.size()
        
        # Check if cache needs regeneration (compare logical sizes accounting for DPR)
        cache_valid = False
        if self._cached_content_pixmap is not None and not self._cached_content_pixmap.isNull():
            try:
                cached_dpr = self._cached_content_pixmap.devicePixelRatio()
                cached_logical_w = int(self._cached_content_pixmap.width() / cached_dpr)
                cached_logical_h = int(self._cached_content_pixmap.height() / cached_dpr)
                cache_valid = (cached_logical_w == widget_size.width() and 
                              cached_logical_h == widget_size.height())
            except Exception:
                cache_valid = False
        
        needs_regen = self._cache_invalidated or not cache_valid
        
        if needs_regen:
            # Regenerate the cached pixmap
            if is_perf_metrics_enabled():
                logger.debug("[PERF] Reddit widget regenerating paint cache (invalidated=%s, cache_valid=%s)",
                           self._cache_invalidated, cache_valid)
            self._regenerate_cache(widget_size)
            self._cache_invalidated = False
        
        # Blit cached content
        if self._cached_content_pixmap is not None and not self._cached_content_pixmap.isNull():
            painter = QPainter(self)
            try:
                painter.drawPixmap(0, 0, self._cached_content_pixmap)
            finally:
                painter.end()
    
    def _regenerate_cache(self, size) -> None:
        """Regenerate the cached content pixmap."""
        try:
            dpr = self.devicePixelRatioF()
        except Exception:
            dpr = 1.0
        
        # Create pixmap with proper DPI scaling
        pixmap = QPixmap(int(size.width() * dpr), int(size.height() * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            self._paint_content_to_painter(painter)
        finally:
            painter.end()
        
        self._cached_content_pixmap = pixmap
    
    def _invalidate_paint_cache(self) -> None:
        """Mark the paint cache as needing regeneration."""
        self._cache_invalidated = True
    
    def _paint_content_to_painter(self, painter: QPainter) -> None:
        """Paint the actual content to a painter (used for caching)."""
        if not self._posts:
            return

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
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)
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
                except Exception as e:
                    logger.debug("[REDDIT] Exception suppressed: %s", e)

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
            # Draw header text with shadow (cached, only regenerated when data changes)
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
            # Draw age text with shadow (cached, only regenerated when data changes)
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
            # Draw title with shadow (cached, only regenerated when data changes)
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
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)

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
        except Exception as e:
            logger.debug("[REDDIT] Exception suppressed: %s", e)
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
        except Exception as e:
            logger.debug("[REDDIT] Exception suppressed: %s", e)
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
        except Exception as e:
            logger.debug("[REDDIT] Exception suppressed: %s", e)
            try:
                self.setMinimumHeight(target)
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)

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
                except Exception as e:
                    logger.debug("[REDDIT] Exception suppressed: %s", e)
            try:
                self.show()
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)
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
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)

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
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)
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
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)

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

        self._hover_timer.start(1000)

    def _show_title_tooltip(self) -> None:
        if not self._hover_title:
            return
        pos = self._hover_global_pos
        if pos is None:
            return
        try:
            QToolTip.showText(pos, self._hover_title, self)
        except Exception as e:
            logger.debug("[REDDIT] Exception suppressed: %s", e)

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
        except Exception as e:
            logger.debug("[REDDIT] Exception suppressed: %s", e)
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
        # Match the main card border-radius of 8px for visual consistency
        radius = 8.0

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
        """Update widget position using centralized base class logic.
        
        Delegates to BaseOverlayWidget._update_position() which handles:
        - Margin-based positioning for all 9 anchor positions
        - Visual padding offsets (when background is disabled)
        - Pixel shift and stack offset application
        - Bounds clamping to prevent off-screen drift
        
        This ensures consistent margin alignment across all overlay widgets.
        """
        # Sync RedditPosition to OverlayPosition for base class
        position_map = {
            RedditPosition.TOP_LEFT: OverlayPosition.TOP_LEFT,
            RedditPosition.TOP_CENTER: OverlayPosition.TOP_CENTER,
            RedditPosition.TOP_RIGHT: OverlayPosition.TOP_RIGHT,
            RedditPosition.MIDDLE_LEFT: OverlayPosition.MIDDLE_LEFT,
            RedditPosition.CENTER: OverlayPosition.CENTER,
            RedditPosition.MIDDLE_RIGHT: OverlayPosition.MIDDLE_RIGHT,
            RedditPosition.BOTTOM_LEFT: OverlayPosition.BOTTOM_LEFT,
            RedditPosition.BOTTOM_CENTER: OverlayPosition.BOTTOM_CENTER,
            RedditPosition.BOTTOM_RIGHT: OverlayPosition.BOTTOM_RIGHT,
        }
        
        # Update base class position
        self._position = position_map.get(self._reddit_position, OverlayPosition.TOP_RIGHT)
        
        # Delegate to base class for centralized margin/positioning logic
        super()._update_position()

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

    def _get_cache_file_path(self) -> Path:
        """Get cache file path for this widget's posts."""
        cache_dir = Path(__file__).resolve().parent.parent / "cache" / "reddit"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"{self._cache_key}_posts.json"
    
    def _save_cached_posts(self, posts: List[RedditPost]) -> None:
        """Save posts to cache for next startup."""
        try:
            cache_path = self._get_cache_file_path()
            data = [asdict(post) for post in posts]
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logger.debug("[REDDIT] Saved %d posts to cache: %s", len(posts), cache_path)
        except Exception as e:
            logger.debug("[REDDIT] Failed to save post cache: %s", e)
    
    def _load_cached_posts(self) -> List[RedditPost]:
        """Load cached posts from previous session."""
        try:
            cache_path = self._get_cache_file_path()
            if not cache_path.exists():
                return []
            
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            posts = [RedditPost(**item) for item in data]
            logger.debug("[REDDIT] Loaded %d posts from cache: %s", len(posts), cache_path)
            return posts
        except Exception as e:
            logger.debug("[REDDIT] Failed to load post cache: %s", e)
            return []

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
            except Exception as e:
                logger.debug("[REDDIT] Exception suppressed: %s", e)
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
    except Exception as e:
        logger.debug("[REDDIT] Exception suppressed: %s", e)
        return

    try:
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    except Exception as e:
        logger.debug("[REDDIT] Exception suppressed: %s", e)
        return

    try:
        user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    except Exception as e:
        logger.debug("[REDDIT] Exception suppressed: %s", e)
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
    except Exception as e:
        logger.debug("[REDDIT] Exception suppressed: %s", e)
        return

    if not candidates:
        return

    hwnd = candidates[0]
    try:
        user32.SetForegroundWindow(hwnd)
    except Exception:
        # Foreground requests may fail silently depending on OS policy.
        return
