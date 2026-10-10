"""A terminal for the diagnostic flavour, only when asked for with ``--debug``.

Builds compile without a console (``--windows-console-mode=disable``): a console that always opens disturbs
winlogon, breaks soaks, and even appeared when installing the screensaver from Explorer's right-click menu
(operator, 2026-10-10). ``SRPSS_Diagnostic.scr --debug`` reuses the terminal it was started from, or opens its
own, and points ``sys.stdout``/``sys.stderr`` at it before logging starts, so the console log handler writes there.
"""
from __future__ import annotations

import sys

_ATTACH_PARENT_PROCESS = -1
_opened = False


def debug_console_requested(argv: list[str] | tuple[str, ...]) -> bool:
    return any(str(arg).strip().lower() == "--debug" for arg in argv[1:])


def open_debug_console(title: str = "SRPSS Diagnostic") -> bool:
    """Attach to the parent's console or allocate one, and route stdout/stderr to it. Returns
    whether a console is now attached. Windows only; idempotent."""
    global _opened
    if _opened:
        return True
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        if not kernel32.GetConsoleWindow():
            if not kernel32.AttachConsole(_ATTACH_PARENT_PROCESS) and not kernel32.AllocConsole():
                return False
        kernel32.SetConsoleTitleW(str(title))
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
    except Exception:
        return False
    _opened = True
    return True
