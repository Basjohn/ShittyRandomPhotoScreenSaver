"""Manual Controller (MC) build utilities."""
from __future__ import annotations

import sys

from core.logging.logger import get_logger

logger = get_logger(__name__)


def is_mc_build() -> bool:
    """Return True when the current process is running the MC build."""
    main_module = sys.modules.get("__main__")
    if main_module is not None:
        main_file = getattr(main_module, "__file__", "") or ""
        if "main_mc" in main_file.lower():
            return True

    try:
        from core.settings.settings_manager import SettingsManager

        mgr = SettingsManager()
        app_name = mgr.get_application_name()
        return "mc" in app_name.lower()
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.debug("[MC] Detection failed: %s", exc)

    return False
