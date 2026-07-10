"""Profile-specific canonical default overrides.

This small data module is written by ``tools/default_settings_editor.py``.
Normal overrides apply to both builds; MC overrides apply on top for the
``Screensaver_MC`` profile. Stable profile names keep generated SST artifacts
and runtime reset behavior on the same source.
"""
from __future__ import annotations


PROFILE_DEFAULT_OVERRIDES = {'Screensaver': {'accessibility': {'dimming': {'opacity': 40}},
                 'sources': {'local_ratio': 55, 'rss_stale_minutes': 60},
                 'timing': {'interval': 60},
                 'transitions': {'particle': {'particle_radius': 8.000000000000004}},
                 'widgets': {'gmail': {'max_sender_words': 2,
                                       'max_subject_words': 3,
                                       'sender_column_width': 120,
                                       'separator_thickness': 2}}},
 'Screensaver_MC': {'display': {'show_on_monitors': [1]},
                    'input': {'interaction_mode': True},
                    'timing': {'interval': 180},
                    'widgets': {'gmail': {'monitor': '2'}, 'media': {'monitor': '2'}}}}
