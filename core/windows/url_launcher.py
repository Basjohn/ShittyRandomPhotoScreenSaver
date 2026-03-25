"""
Session-aware Windows URL launcher (gutted).

Previously contained token manipulation (WTSQueryUserToken,
DuplicateTokenEx, CreateProcessWithTokenW), rundll32 launching, and
hidden process creation — all of which triggered AV heuristics.

All process-based URL launching has been removed.  URLs are now opened
either:
- **SCR builds**: via the ProgramData file queue + user-session watcher
- **MC builds**: via ``QDesktopServices.openUrl()`` directly

This module retains stub functions so callers that haven't been updated
yet won't crash.  Phase 3 (click handler refactor) will remove these
callers entirely.
"""

from __future__ import annotations

from core.logging.logger import get_logger

logger = get_logger(__name__)


def should_use_session_launcher() -> bool:
    """Always returns False — the session launcher path has been removed."""
    return False


def launch_url_via_user_desktop(url: str) -> bool:
    """Stub — no longer launches processes. Always returns False."""
    logger.debug("[SCR-HELPER] launch_url_via_user_desktop is deprecated (url=%s)", url)
    return False
