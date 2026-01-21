"""
Helpers for detecting Manual Controller (MC) builds.

Historically this logic lived inside the Eco Mode module. Now that the
resource-throttling feature is retired we keep the build detection in this
lightweight helper so other modules can retain MC-specific behaviour (window
flags, context menu affordances, etc.) without depending on Eco Mode.
"""
from __future__ import annotations

import sys
from core.logging.logger import get_logger

logger = get_logger(__name__)


def is_mc_build() -> bool:
    """
    Check whether the current process is the Manual Controller build.

    Returns:
        bool: True if the executable or main module name indicates MC mode or
        if the QSettings application name contains the MC suffix.
    """
    # Check executable/entry point name first to avoid importing SettingsManager
    exe0 = str(getattr(sys, "argv", [""])[0]).lower()
    mc_markers = (
        "srpss_mc",
        "srpss mc",
        "srpss_media_center",
        "srpss media center",
        "main_mc.py",
    )
    if any(marker in exe0 for marker in mc_markers):
        return True

    # Fall back to SettingsManager application name detection (best effort)
    try:
        from core.settings.settings_manager import SettingsManager

        mgr = SettingsManager()
        app_name = mgr.get_application_name()
        return "MC" in app_name or "mc" in app_name.lower()
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("[MC] Unable to detect MC build via settings: %s", exc)
        return False
