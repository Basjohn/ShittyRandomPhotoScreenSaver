"""Profile-specific canonical default overrides.

This small data module is written by ``tools/default_settings_editor.py``.
Normal defaults live directly in ``default_settings.py``. Only MC differences
apply on top for the ``Screensaver_MC`` profile. Stable profile names keep
generated SST artifacts and runtime reset behavior on the same source.
"""
from __future__ import annotations


PROFILE_DEFAULT_OVERRIDES = {'Screensaver': {},
 'Screensaver_MC': {'display': {'show_on_monitors': [2]},
                    'input': {'interaction_mode': True},
                    'mc': {'always_on_top': True},
                    'widgets': {'clock': {'monitor': 'ALL'},
                                'clock2': {'monitor': 2},
                                'clock3': {'monitor': 'ALL'},
                                'friend_pulse': {'monitor': 'ALL'},
                                'gmail': {'monitor': 2},
                                'media': {'monitor': 2},
                                'reddit': {'monitor': 2},
                                'reddit2': {'monitor': 2},
                                'spotify_visualizer': {'monitor': 'ALL'},
                                'steam_progress': {'monitor': 'ALL'}}}}
