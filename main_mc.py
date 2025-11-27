"""Alternate entry point for SRPSS manual controller (MC) build.

This launcher forces RUN (/s) mode by default when no explicit
screensaver argument is provided, while still delegating all real
initialisation and mode handling to ``main.main``.

Usage:
- ``SRPSS MC.exe``            -> runs the screensaver (RUN mode)
- ``SRPSS MC.exe /c``         -> opens settings (CONFIG mode)
- ``SRPSS MC.exe --debug /s`` -> runs screensaver with debug logging
"""

from __future__ import annotations

import sys
import ctypes
import winreg

from main import main as core_main
from core.settings.settings_manager import SettingsManager

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002


def _inject_run_mode_arg() -> None:
    """Ensure a screensaver mode argument is present, defaulting to /s.

    If the user has not supplied any of the standard screensaver
    arguments (/s, /c, /p, -c, -p, -s, --s), we append ``/s`` so that
    ``parse_screensaver_args`` inside ``main`` will treat this launch as
    RUN mode.
    """

    lower_args = [str(a).lower() for a in sys.argv[1:]]
    has_ss_arg = any(a in ("/s", "/c", "/p", "-c", "-p", "-s", "--s") for a in lower_args)
    if not has_ss_arg:
        sys.argv.append("/s")


def _is_srpss_configured_screensaver() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\\Desktop")
        value, _ = winreg.QueryValueEx(key, "SCRNSAVE.EXE")
        winreg.CloseKey(key)
        if isinstance(value, str) and "srpss.scr" in value.lower():
            return True
    except Exception:
        return False
    return False


def _set_screensaver_block(enabled: bool) -> None:
    try:
        flags = _ES_CONTINUOUS
        if enabled:
            flags |= _ES_DISPLAY_REQUIRED | _ES_SYSTEM_REQUIRED
        ctypes.windll.kernel32.SetThreadExecutionState(flags)
    except Exception:
        pass


def main() -> int:
    _inject_run_mode_arg()

    try:
        mgr = SettingsManager()
        mgr.set("input.hard_exit", True)
    except Exception:
        pass

    prevent_ss = _is_srpss_configured_screensaver()
    result = 0
    try:
        if prevent_ss:
            _set_screensaver_block(True)
        result = core_main()
    finally:
        if prevent_ss:
            _set_screensaver_block(False)

    return result


if __name__ == "__main__":  # pragma: no cover - thin wrapper
    sys.exit(main())
