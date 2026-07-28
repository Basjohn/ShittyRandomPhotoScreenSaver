"""
Minimal Reddit helper installer/runtime utilities.

The old token-manipulation and runtime extraction paths were removed to avoid
AV-hostile behavior. The current shipped design keeps only two low-risk
utilities here while the installer owns scheduled-task registration:

- ``_running_as_system()`` — detect Winlogon SYSTEM context
- ``_log_helper_event()`` — append breadcrumb lines to ProgramData helper logs
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

from core.logging.logger import get_logger
from core.windows.reddit_helper_storage import append_bounded_log

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"

BASE_DIR = Path(os.getenv("PROGRAMDATA", r"C:\ProgramData")) / "SRPSS"
_BREADCRUMB_FAILURE_REPORTED = False


def _running_as_system() -> bool:
    username = os.getenv("USERNAME", "")
    domain = os.getenv("USERDOMAIN", "")
    qualified = f"{domain}\\{username}" if domain else username
    upper = qualified.strip().upper()
    return upper.endswith("\\SYSTEM") or upper == "SYSTEM" or upper.endswith("NT AUTHORITY\\SYSTEM")


def _log_helper_event(message: str) -> None:
    global _BREADCRUMB_FAILURE_REPORTED
    if os.getenv("PYTEST_CURRENT_TEST") and not os.getenv("SRPSS_ALLOW_TEST_HELPER_BREADCRUMBS"):
        return
    try:
        log_dir = BASE_DIR / "logs"
        log_file = log_dir / "scr_helper.log"
        stamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        if not append_bounded_log(log_file, f"{stamp} {message}"):
            if not _BREADCRUMB_FAILURE_REPORTED:
                logger.warning("[REDDIT] Helper breadcrumb diagnostics are unavailable")
                _BREADCRUMB_FAILURE_REPORTED = True
        else:
            _BREADCRUMB_FAILURE_REPORTED = False
    except Exception as e:
        logger.debug("[REDDIT] Exception suppressed: %s", e)
