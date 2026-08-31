"""Settings roots that must remain nested across JSON persistence.

These roots are semantic mappings, not dotted compatibility namespaces.  Keep
the list shared by the store, writer and SettingsManager so a mapping cannot be
written intact and then flattened into an unreadable shape on the next load.
"""

from __future__ import annotations


STRUCTURED_SETTINGS_ROOTS = frozenset(
    {
        "transitions",
        "ui",
        "visualizer_custom_presets",
        "widgets",
    }
)


__all__ = ["STRUCTURED_SETTINGS_ROOTS"]
