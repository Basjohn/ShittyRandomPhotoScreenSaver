"""
Minimal Reddit helper installer/runtime utilities.

Scheduled-task registration belongs to the Inno Setup installer. This module
only detects SYSTEM context and writes small bounded diagnostic breadcrumbs.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from core.logging.logger import get_logger
from core.windows.reddit_helper_storage import append_bounded_log

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"
BASE_DIR = Path(
    os.getenv("PROGRAMDATA", r"C:\ProgramData")
) / "SRPSS"

_BREADCRUMB_FAILURE_REPORTED = False


def _running_as_system() -> bool:
    username = os.getenv("USERNAME", "")
    domain = os.getenv("USERDOMAIN", "")
    qualified = f"{domain}\\{username}" if domain else username
    upper = qualified.strip().upper()

    return (
        upper.endswith("\\SYSTEM")
        or upper == "SYSTEM"
        or upper.endswith("NT AUTHORITY\\SYSTEM")
    )


def _log_helper_event(message: str) -> None:
    global _BREADCRUMB_FAILURE_REPORTED

    if (
        os.getenv("PYTEST_CURRENT_TEST")
        and not os.getenv(
            "SRPSS_ALLOW_TEST_HELPER_BREADCRUMBS"
        )
    ):
        return

    stamp = (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    log_file = BASE_DIR / "logs" / "scr_helper.log"

    try:
        if append_bounded_log(
            log_file,
            f"{stamp} {message}",
        ):
            _BREADCRUMB_FAILURE_REPORTED = False
            return

        if not _BREADCRUMB_FAILURE_REPORTED:
            logger.warning(
                "[REDDIT] Helper breadcrumb diagnostics "
                "are unavailable at %s",
                log_file,
            )
            _BREADCRUMB_FAILURE_REPORTED = True
    except Exception as exc:
        if not _BREADCRUMB_FAILURE_REPORTED:
            logger.warning(
                "[REDDIT] Failed to write helper breadcrumb: %s",
                exc,
                exc_info=True,
            )
            _BREADCRUMB_FAILURE_REPORTED = True
