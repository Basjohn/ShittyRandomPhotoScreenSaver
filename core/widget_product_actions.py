"""Presentation-neutral product consequences for retained family actions.

Retained QML/presentations emit semantic actions.  This module keeps the small
mapping/lifecycle consequences independently testable without giving QML, a
family adapter, or a retained presentation Settings/browser ownership.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

_CLOCK_WIDGET_IDS = frozenset({"clock", "clock2", "clock3"})
_CLOCK_DISPLAY_MODES = frozenset({"analog", "digital"})


def update_clock_display_mode_override(
    widgets: Mapping[str, Any],
    *,
    widget_id: str,
    display_identity: str,
    normalized_mode: str,
) -> tuple[dict[str, Any], bool]:
    """Return a detached widgets map with one per-display Clock mode override.

    The shared ``display_mode`` baseline is intentionally untouched.  Only the
    requested Clock instance's ``display_mode_overrides[screen_signature]`` is
    changed, preserving mixed analogue/digital state across displays.
    """

    normalized_widget_id = str(widget_id or "")
    identity = str(display_identity or "").strip()
    mode = str(normalized_mode or "").strip().lower()
    if normalized_widget_id not in _CLOCK_WIDGET_IDS:
        raise ValueError(f"unsupported Clock widget id: {normalized_widget_id!r}")
    if not identity:
        raise ValueError("Clock display identity must not be empty")
    if mode not in _CLOCK_DISPLAY_MODES:
        raise ValueError(f"unsupported Clock display mode: {mode!r}")

    result = dict(widgets) if isinstance(widgets, Mapping) else {}
    section_value = result.get(normalized_widget_id, {})
    section = dict(section_value) if isinstance(section_value, Mapping) else {}
    overrides_value = section.get("display_mode_overrides", {})
    overrides = (
        dict(overrides_value)
        if isinstance(overrides_value, Mapping)
        else {}
    )
    if overrides.get(identity) == mode:
        return result, False

    overrides[identity] = mode
    section["display_mode_overrides"] = overrides
    result[normalized_widget_id] = section
    return result, True


def dispatch_reddit_url_product_action(
    url: str,
    *,
    opener: Callable[[str], bool],
    request_saver_exit: Callable[[], None],
    interactive_build: bool,
) -> bool:
    """Execute an already-admitted Reddit URL consequence exactly once.

    URL trust/admission happens in ``RedditPresentationModel`` before this seam.
    The injected opener owns direct-vs-secure-handoff policy.  A successful
    ordinary-saver handoff requests normal saver exit; MC/diagnostic interactive
    builds remain running.  Helper readiness is deliberately not represented.
    """

    normalized_url = str(url or "").strip()
    if not normalized_url:
        return False
    if not bool(opener(normalized_url)):
        return False
    if not bool(interactive_build):
        request_saver_exit()
    return True


__all__ = [
    "dispatch_reddit_url_product_action",
    "update_clock_display_mode_override",
]
