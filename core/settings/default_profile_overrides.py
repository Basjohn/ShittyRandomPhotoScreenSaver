"""Profile-specific canonical default overrides.

This small data module is written by ``tools/default_settings_editor.py``.
Normal overrides apply to both builds; MC overrides apply on top for the
``Screensaver_MC`` profile. Stable profile names keep generated SST artifacts
and runtime reset behavior on the same source.
"""
from __future__ import annotations


PROFILE_DEFAULT_OVERRIDES = {
    "Screensaver": {},
    "Screensaver_MC": {
        "display": {"show_on_monitors": [1]},
        "input": {"interaction_mode": True},
        "widgets": {
            "gmail": {"monitor": "2"},
            "media": {"monitor": "2"},
        },
    },
}
