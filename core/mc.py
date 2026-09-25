"""Manual Controller (MC) build utilities."""
from __future__ import annotations

import sys

from core.settings.storage_paths import detect_current_profile


def is_mc_build() -> bool:
    """Return True when the current process is running the MC build.

    The MC identity is the process entry point, resolved side-effect free by
    ``detect_current_profile``. Constructing a ``SettingsManager`` here re-ran
    settings migration, repair and a synchronous durability flush on the GUI
    thread for every per-display window/menu/interaction query (21 managers per
    cold start plus rebuild on the 2026-09-25 churn trace).
    """
    main_module = sys.modules.get("__main__")
    if main_module is not None:
        main_file = getattr(main_module, "__file__", "") or ""
        if "main_mc" in main_file.lower():
            return True
    return "mc" in detect_current_profile(default="Screensaver").lower()
