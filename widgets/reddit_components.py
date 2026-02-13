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
import sys
import ctypes
from ctypes import wintypes

from core.logging.logger import get_logger

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
    
    return " ".join(result)


def try_bring_reddit_window_to_front() -> None:
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
