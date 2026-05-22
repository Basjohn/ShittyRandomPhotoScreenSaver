"""Reddit widget helper components.

Extracted from reddit_widget.py to keep the main widget under the 1500-line
monolith threshold. Contains:
- RedditPosition — enum for widget screen position
- RedditPost — dataclass for post representation
- _smart_title_case — title casing utility
- _try_bring_reddit_window_to_front — Windows focus helper
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from core.logging.logger import get_logger
from core.windows.browser_window_routing import try_bring_browser_window_to_front_by_keywords

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


TITLE_FILTER_RE = re.compile(r"\b(daily|weekly|question thread)\b", re.IGNORECASE)

# Words to keep lowercase in title case (unless first word)
TITLE_CASE_SMALL_WORDS = frozenset()


def smart_title_case(text: str) -> str:
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
    
    result = " ".join(result)

    # Normalize r/subreddit capitalization: r/yummy → R/Yummy
    result = re.sub(r"(?i)\br/([a-z])", lambda m: f"R/{m.group(1).upper()}", result)

    return result


def try_bring_reddit_window_to_front() -> None:
    """Best-effort attempt to foreground a browser window with 'reddit' in title.

    Uses ``AllowSetForegroundWindow``, ``IsIconic``/``ShowWindow(SW_RESTORE)``,
    and ``SetForegroundWindow`` for reliable cross-process focus stealing.

    Windows-only; no-op on other platforms. All failures are silent to avoid
    introducing new focus or flicker problems.
    """

    try:
        try_bring_browser_window_to_front_by_keywords(("reddit",), preferred_display_index=0)
    except Exception as e:
        logger.debug("[REDDIT] Exception suppressed: %s", e)
