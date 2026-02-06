"""Compatibility shim — presets module moved to core/settings/presets.py.

All symbols are re-exported so existing ``from core.presets import …``
statements continue to work.  New code should import from
``core.settings.presets`` directly.
"""
from core.settings.presets import *  # noqa: F401,F403
from core.settings.presets import (  # explicit re-exports for type checkers
    PresetDefinition,
    PRESET_DEFINITIONS,
    get_ordered_presets,
    get_preset_by_index,
    apply_preset,
    get_current_preset_info,
    check_and_switch_to_custom,
    adjust_settings_for_mc_mode,
    reset_non_custom_presets,
)
