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

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"

BASE_DIR = Path(os.getenv("PROGRAMDATA", r"C:\ProgramData")) / "SRPSS"


def _running_as_system() -> bool:
    username = os.getenv("USERNAME", "")
    domain = os.getenv("USERDOMAIN", "")
    qualified = f"{domain}\\{username}" if domain else username
    upper = qualified.strip().upper()
    return upper.endswith("\\SYSTEM") or upper == "SYSTEM" or upper.endswith("NT AUTHORITY\\SYSTEM")


def _log_helper_event(message: str) -> None:
    try:
        log_dir = BASE_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "scr_helper.log"
        stamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {message}\n")
    except Exception as e:
        logger.debug("[REDDIT] Exception suppressed: %s", e)
