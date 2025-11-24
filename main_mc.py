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

from main import main as core_main
from core.settings.settings_manager import SettingsManager


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


def main() -> int:
    _inject_run_mode_arg()

    # Ensure hard-exit mode is enabled by default for the MC variant so that
    # keyboard exits (Esc/Q) are required and mouse movement/clicks do not
    # close the saver unless the user explicitly disables it in settings.
    try:
        mgr = SettingsManager()
        mgr.set("input.hard_exit", True)
    except Exception:
        # Failing to toggle hard-exit should never prevent the saver from
        # starting; fall back to whatever the current configuration is.
        pass

    return core_main()


if __name__ == "__main__":  # pragma: no cover - thin wrapper
    sys.exit(main())
