from __future__ import annotations

from typing import Any, Dict, Optional, Set

from PySide6.QtGui import QPixmap

from core.logging.logger import get_logger

logger = get_logger(__name__)


def _sanitize_details(details: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = dict(details)
    if "base_pixmap" in sanitized:
        try:
            bp = sanitized["base_pixmap"]
            if isinstance(bp, QPixmap) and not bp.isNull():
                sanitized["base_pixmap"] = (
                    f"Pixmap(size={bp.width()}x{bp.height()}, "
                    f"dpr={bp.devicePixelRatioF():.2f})"
                )
            else:
                sanitized["base_pixmap"] = "<pixmap>"
        except Exception as e:
            logger.debug("[MISC] Exception suppressed: %s", e)
            sanitized["base_pixmap"] = "<pixmap>"
    return sanitized


def record_overlay_ready(
    log,
    screen_index: int,
    overlay_name: str,
    stage: str,
    stage_counts: Dict[str, int],
    overlay_swap_warned: Set[str],
    seed_age_ms: Optional[float],
    details: Dict[str, Any],
) -> None:
    key = f"{overlay_name}:{stage}"
    stage_counts[key] = stage_counts.get(key, 0) + 1
    count = stage_counts[key]

    sanitized_details = _sanitize_details(details)

    if count == 1:
        log.debug(
            "[DIAG] Overlay readiness (screen=%s, name=%s, stage=%s, seed_age_ms=%s, "
            "count=%s, details=%s)",
            screen_index,
            overlay_name,
            stage,
            f"{seed_age_ms:.2f}" if seed_age_ms is not None else "N/A",
            count,
            sanitized_details,
        )

    if stage != "gl_initialized":
        return

    try:
        actual_swap = str(details.get("swap", ""))
    except Exception as e:
        logger.debug("[MISC] Exception suppressed: %s", e)
        actual_swap = str(details.get("swap", ""))

    if "triple" in actual_swap.lower():
        return

    if overlay_name in overlay_swap_warned:
        return

    log.info(
        "[DIAG] Overlay swap = %s (screen=%s, name=%s, interval=%s) — driver enforced double buffer",
        actual_swap or "Unknown",
        screen_index,
        overlay_name,
        details.get("interval", "?"),
    )
    overlay_swap_warned.add(overlay_name)
