"""
Reddit helper installer utilities (gutted).

Previously contained token manipulation, privilege escalation, EXE payload
extraction, and scheduled-task registration code.  All of that has been
removed to eliminate AV triggers.  The helper EXE is now placed at install
time by the Inno Setup installer and started via a standard HKCU\\Run
registry entry.

Retained utilities:
- ``_running_as_system()`` — detect Winlogon SYSTEM context
- ``_log_helper_event()`` — append diagnostic line to helper log
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
