"""Generic secure-desktop URL launcher.

Wraps the existing ProgramData queue bridge (originally for Reddit) so that
any widget can open URLs safely from Winlogon / SYSTEM / secure-desktop mode.
"""
from __future__ import annotations

import webbrowser

from core.logging.logger import get_logger
from core.windows import reddit_helper_bridge

logger = get_logger(__name__)


def open_url(url: str, *, fallback: bool = True) -> bool:
    """Open *url* via the helper bridge when available, otherwise browser.

    Args:
        url: The URL to open.
        fallback: If True, try ``webbrowser.open()`` when the bridge is unavailable.

    Returns:
        True if the URL was queued or opened, False on complete failure.
    """
    if reddit_helper_bridge.is_bridge_available():
        ok = reddit_helper_bridge.enqueue_url(url, source="gmail")
        if ok:
            logger.debug("[URL-LAUNCH] Queued via bridge: %s", url)
            return True
        logger.warning("[URL-LAUNCH] Bridge available but enqueue failed; trying fallback")

    if not fallback:
        logger.error("[URL-LAUNCH] No bridge and fallback disabled")
        return False

    try:
        webbrowser.open(url)
        logger.debug("[URL-LAUNCH] Opened via webbrowser: %s", url)
        return True
    except Exception as exc:
        logger.error("[URL-LAUNCH] webbrowser.open failed: %s", exc)
        return False
