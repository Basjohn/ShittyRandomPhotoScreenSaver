"""Profile-specific canonical default overrides.

This small data module contains only genuine profile deltas. Repository defaults
tooling may rewrite it, but Normal defaults live directly in ``default_settings.py``.
Only MC differences
apply on top for the ``Screensaver_MC`` profile. Stable profile names keep
generated SST artifacts and runtime reset behavior on the same source.
"""
from __future__ import annotations


PROFILE_DEFAULT_OVERRIDES = {'Screensaver': {},
 'Screensaver_MC': {'display': {'show_on_monitors': [1]},
                    'input': {'interaction_mode': True},
                    'mc': {'always_on_top': True}}}
