"""Central browser launcher with an explicit secure-desktop fallback.

Normal interactive surfaces use Qt's native desktop URL route.  The existing
ProgramData helper queue is reserved for a genuine secure-desktop fallback,
where the browser cannot be opened by the current process.
"""
from __future__ import annotations

import webbrowser

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from core.logging.logger import get_logger
from core.windows import reddit_helper_bridge
from core.windows import reddit_helper_runtime
from core.mc import is_mc_build

logger = get_logger(__name__)


def open_url(
    url: str,
    *,
    fallback: bool = True,
    prefer_direct: bool = False,
    source: str = "gmail",
) -> bool:
    """Open *url* directly when appropriate, otherwise use secure handoff.

    Args:
        url: The URL to open.
        fallback: If True, try ``webbrowser.open()`` after other routes fail.
        prefer_direct: Request MC-style native URL launch before any queue route.
        source: Safe route label for helper diagnostics.

    Returns:
        True if the URL was queued or opened, False on complete failure.
    """
    if not url:
        return False

    direct_requested = bool(prefer_direct or is_mc_build())
    if direct_requested:
        try:
            if QDesktopServices.openUrl(QUrl(url)):
                logger.info("[URL-LAUNCH] Opened directly source=%s", source)
                return True
            logger.warning("[URL-LAUNCH] Native direct URL launch was rejected source=%s", source)
        except Exception as exc:
            logger.warning("[URL-LAUNCH] Native direct URL launch failed source=%s error=%s", source, exc)

    # MC is always interactive: a failed direct route must not enqueue work for
    # the SCR helper, which intentionally does not run in MC sessions.
    if not is_mc_build() and reddit_helper_bridge.is_bridge_available():
        ok = reddit_helper_bridge.enqueue_url(url, source=source)
        if ok:
            try:
                reddit_helper_runtime.ensure_helper_runtime(
                    source=f"{source}_url",
                    owner_pid=None,
                    idle_exit_seconds=60,
                    allow_system=True,
                )
            except Exception:
                logger.warning("[URL-LAUNCH] Secure URL handoff helper wake failed source=%s", source, exc_info=True)
            logger.info("[URL-LAUNCH] Queued secure-desktop URL handoff source=%s", source)
            return True
        logger.warning("[URL-LAUNCH] Secure URL handoff enqueue failed source=%s; trying fallback", source)

    if not fallback:
        logger.error("[URL-LAUNCH] No URL route and fallback disabled source=%s", source)
        return False

    try:
        # new=1 forces a new browser window (not just a tab), which is
        # important for OAuth flows where the user needs to see both the
        # authorization page and the app simultaneously.
        webbrowser.open(url, new=1)
        logger.info("[URL-LAUNCH] Opened via webbrowser source=%s", source)
        return True
    except Exception as exc:
        logger.error("[URL-LAUNCH] webbrowser.open failed: %s", exc)
        return False
