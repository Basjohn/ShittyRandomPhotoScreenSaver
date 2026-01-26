"""
Presets module for SRPSS.

Provides predefined widget configurations that users can quickly switch between.
The "Custom" preset preserves user's manual settings.

## Adding New Presets

To add a new preset:

1. Add a new entry to PRESET_DEFINITIONS dict below
2. Set 'order' to position in slider (0=leftmost, higher=right)
3. Define all widget settings that differ from defaults
4. Custom preset is always rightmost (order=999)

Example:
    "my_preset": PresetDefinition(
        name="My Preset",
        description="Description shown in UI",
        order=2,  # Position between existing presets
        settings={
            "widgets.clock.enabled": True,
            "widgets.clock.position": "Top Right",
            # ... other settings
        }
    )

The slider will automatically accommodate new notches with even spacing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from copy import deepcopy

from core.logging.logger import get_logger

if TYPE_CHECKING:
    from core.settings.settings_manager import SettingsManager

logger = get_logger(__name__)


@dataclass
class PresetDefinition:
    """Definition of a preset configuration."""
    name: str
    description: str
    order: int  # Position in slider (0=leftmost, 999=Custom always rightmost)
    settings: Dict[str, Any] = field(default_factory=dict)
    is_custom: bool = False  # True only for the Custom preset


# =============================================================================
# PRESET DEFINITIONS
# =============================================================================
# Add new presets here. Order determines slider position (lower = left).
# Custom preset (order=999) is always rightmost and handled specially.

PRESET_DEFINITIONS: Dict[str, PresetDefinition] = {
    "purist": PresetDefinition(
        name="Purist",
        description="Just the wallpapers and transitions, best performance.",
        order=0,
        settings={
            "widgets.clock.enabled": False,
            "widgets.clock2.enabled": False,
            "widgets.clock3.enabled": False,
            "widgets.weather.enabled": False,
            "widgets.media.enabled": False,
            "widgets.reddit.enabled": False,
            "widgets.reddit2.enabled": False,
            "widgets.spotify_visualizer.enabled": False,
            "widgets.media.spotify_volume_enabled": False,
            # Performance: Higher cache for smoother transitions
            "cache.max_items": 60,
        }
    ),
    
    "essentials": PresetDefinition(
        name="Essentials",
        description="Weather and Clock, very high performance.",
        order=1,
        settings={
            # Clock: Enabled, Analog, Top Right, All Displays
            "widgets.clock.enabled": True,
            "widgets.clock.display_mode": "analog",
            "widgets.clock.position": "Top Right",
            "widgets.clock.monitor": "ALL",
            "widgets.clock2.enabled": False,
            "widgets.clock3.enabled": False,
            # Weather: Enabled, Top Left, All Displays
            "widgets.weather.enabled": True,
            "widgets.weather.position": "Top Left",
            "widgets.weather.monitor": "ALL",
            # Everything else disabled
            "widgets.media.enabled": False,
            "widgets.reddit.enabled": False,
            "widgets.reddit2.enabled": False,
            "widgets.spotify_visualizer.enabled": False,
            "widgets.media.spotify_volume_enabled": False,
            # Performance: Higher cache for smoother transitions
            "cache.max_items": 60,
        }
    ),
    
    "media": PresetDefinition(
        name="Media",
        description="Spotify, Weather and Clock, a good middle ground.",
        order=2,
        settings={
            # Clock: Enabled, Analog, Top Right, All Displays
            "widgets.clock.enabled": True,
            "widgets.clock.display_mode": "analog",
            "widgets.clock.position": "Top Right",
            "widgets.clock.monitor": "ALL",
            "widgets.clock2.enabled": False,
            "widgets.clock3.enabled": False,
            # Weather: Enabled, Top Left, All Displays
            "widgets.weather.enabled": True,
            "widgets.weather.position": "Top Left",
            "widgets.weather.monitor": "ALL",
            # Media: Enabled, Bottom Left, Active Display (monitor 1)
            "widgets.media.enabled": True,
            "widgets.media.position": "Bottom Left",
            "widgets.media.monitor": 1,
            "widgets.media.spotify_volume_enabled": True,
            # Visualizer: Enabled (follows media)
            "widgets.spotify_visualizer.enabled": True,
            # Reddit disabled
            "widgets.reddit.enabled": False,
            "widgets.reddit2.enabled": False,
            # Balanced: Moderate cache size
            "cache.max_items": 45,
        }
    ),
    
    "full_monty": PresetDefinition(
        name="Full Monty",
        description="Everything all at once because processors and RAM deserve punishment!",
        order=3,
        settings={
            # Clock: Enabled, Analog, Top Right, All Displays
            "widgets.clock.enabled": True,
            "widgets.clock.display_mode": "analog",
            "widgets.clock.position": "Top Right",
            "widgets.clock.monitor": "ALL",
            "widgets.clock2.enabled": False,
            "widgets.clock3.enabled": False,
            # Weather: Enabled, Top Left, All Displays
            "widgets.weather.enabled": True,
            "widgets.weather.position": "Top Left",
            "widgets.weather.monitor": "ALL",
            # Media: Enabled, Bottom Left, Active Display
            "widgets.media.enabled": True,
            "widgets.media.position": "Bottom Left",
            "widgets.media.monitor": 1,
            "widgets.media.spotify_volume_enabled": True,
            # Visualizer: Enabled
            "widgets.spotify_visualizer.enabled": True,
            # Reddit 1: Enabled, "All" subreddit, Bottom Center, 10 items
            "widgets.reddit.enabled": True,
            "widgets.reddit.subreddit": "All",
            "widgets.reddit.position": "Bottom Center",
            "widgets.reddit.limit": 10,
            "widgets.reddit.monitor": 1,
            # Reddit 2: Enabled, "Pics" subreddit, Bottom Right, 10 items
            "widgets.reddit2.enabled": True,
            "widgets.reddit2.subreddit": "Pics",
            "widgets.reddit2.position": "Bottom Right",
            "widgets.reddit2.limit": 10,
            "widgets.reddit2.monitor": 1,
            # Full: Maximum cache for all widgets
            "cache.max_items": 90,
        }
    ),
    
    "custom": PresetDefinition(
        name="Custom",
        description="Your personal configuration, saved automatically.",
        order=999,  # Always rightmost
        settings={},  # Custom uses saved settings, not predefined
        is_custom=True,
    ),
}


def get_ordered_presets() -> List[str]:
    """Return preset keys in slider order (left to right)."""
    return sorted(PRESET_DEFINITIONS.keys(), key=lambda k: PRESET_DEFINITIONS[k].order)


def get_preset_count() -> int:
    """Return the number of available presets."""
    return len(PRESET_DEFINITIONS)


def get_preset_by_index(index: int) -> Optional[str]:
    """Get preset key by slider index (0-based)."""
    ordered = get_ordered_presets()
    if 0 <= index < len(ordered):
        return ordered[index]
    return None


def get_preset_index(preset_key: str) -> int:
    """Get slider index for a preset key."""
    ordered = get_ordered_presets()
    try:
        return ordered.index(preset_key)
    except ValueError:
        # Default to Custom (last)
        return len(ordered) - 1


def is_mc_mode() -> bool:
    """Check if running in MC (Media Center) mode."""
    import sys
    try:
        exe_name = str(getattr(sys, "argv", [""])[0]).lower()
        return (
            "srpss mc" in exe_name
            or "srpss_mc" in exe_name
            or "srpss media center" in exe_name
            or "srpss_media_center" in exe_name
            or "main_mc.py" in exe_name
        )
    except Exception:
        return False


def adjust_settings_for_mc_mode(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Adjust preset settings for MC mode.
    
    In MC mode, single-display placements use display 2 instead of display 1,
    and "ALL" placements also use display 2.
    """
    if not is_mc_mode():
        return settings
    
    adjusted = deepcopy(settings)
    
    # Keys that specify monitor placement
    monitor_keys = [
        "widgets.clock.monitor",
        "widgets.clock2.monitor",
        "widgets.clock3.monitor",
        "widgets.weather.monitor",
        "widgets.media.monitor",
        "widgets.reddit.monitor",
        "widgets.reddit2.monitor",
        "widgets.spotify_visualizer.monitor",
    ]
    
    for key in monitor_keys:
        if key in adjusted:
            value = adjusted[key]
            # Convert "ALL" or 1 to 2 for MC mode
            if value == "ALL" or value == 1:
                adjusted[key] = 2
    
    return adjusted


def apply_preset(settings_manager: "SettingsManager", preset_key: str) -> bool:
    """Apply a preset to the settings manager.
    
    Args:
        settings_manager: The SettingsManager instance
        preset_key: Key of the preset to apply (e.g., "purist", "custom")
        
    Returns:
        True if preset was applied successfully, False otherwise
    """
    if preset_key not in PRESET_DEFINITIONS:
        logger.error("[PRESETS] Unknown preset: %s", preset_key)
        return False
    
    preset = PRESET_DEFINITIONS[preset_key]
    current_preset = settings_manager.get("preset", "custom")
    
    # If switching away from Custom, save current settings
    if current_preset == "custom" and preset_key != "custom":
        _save_custom_backup(settings_manager)
    
    # Apply the preset
    if preset.is_custom:
        # Restore custom backup
        _restore_custom_backup(settings_manager)
    else:
        # Apply preset settings
        preset_settings = adjust_settings_for_mc_mode(preset.settings)
        for key, value in preset_settings.items():
            _set_nested_setting(settings_manager, key, value)
    
    # Save the selected preset
    settings_manager.set("preset", preset_key)
    
    # Persist all changes to disk and trigger reload
    try:
        settings_manager.save()
    except Exception as e:
        logger.error("[PRESETS] Failed to save settings after applying preset: %s", e)
    
    logger.info("[PRESETS] Applied preset: %s", preset.name)
    return True


def _save_custom_backup(settings_manager: "SettingsManager") -> None:
    """Save current settings to custom backup.
    
    Saves all major setting categories:
    - widgets (all widget configurations)
    - display (interval, transition_duration, fit_mode, etc.)
    - transitions (enabled, random, selected effects)
    - accessibility (high_contrast, reduce_motion, etc.)
    - sources (image directories, RSS feeds, etc.)
    """
    backup = {}
    
    # Categories to backup
    categories = ["widgets", "display", "transitions", "accessibility", "sources"]
    
    for category in categories:
        category_data = settings_manager.get(category, {})
        if isinstance(category_data, dict):
            # For nested categories like widgets
            for section, section_data in category_data.items():
                if isinstance(section_data, dict):
                    for key, value in section_data.items():
                        backup[f"{category}.{section}.{key}"] = deepcopy(value)
                else:
                    # For simple key-value pairs
                    backup[f"{category}.{section}"] = deepcopy(section_data)
        else:
            # For non-dict categories, save the whole value
            backup[category] = deepcopy(category_data)
    
    settings_manager.set("custom_preset_backup", backup)
    logger.debug("[PRESETS] Saved custom backup with %d settings across %d categories", 
                len(backup), len(categories))


def _restore_custom_backup(settings_manager: "SettingsManager") -> None:
    """Restore widget settings from custom backup."""
    backup = settings_manager.get("custom_preset_backup", {})
    
    if not isinstance(backup, dict) or not backup:
        logger.debug("[PRESETS] No custom backup to restore")
        return
    
    for key, value in backup.items():
        _set_nested_setting(settings_manager, key, value)
    
    logger.debug("[PRESETS] Restored custom backup with %d settings", len(backup))


def _set_nested_setting(settings_manager: "SettingsManager", dotted_key: str, value: Any) -> None:
    """Set a nested setting using dot notation.
    
    Example: _set_nested_setting(sm, "widgets.clock.enabled", True)
    """
    parts = dotted_key.split(".")
    
    if len(parts) < 2:
        settings_manager.set(dotted_key, value)
        return
    
    # For widget settings like "widgets.clock.enabled"
    if parts[0] == "widgets" and len(parts) >= 3:
        section = parts[1]  # e.g., "clock"
        key = ".".join(parts[2:])  # e.g., "enabled"
        
        # Get current widgets dict
        widgets = settings_manager.get("widgets", {})
        if not isinstance(widgets, dict):
            widgets = {}
        
        # Get or create section
        if section not in widgets or not isinstance(widgets.get(section), dict):
            widgets[section] = {}
        
        # Set the value - handle nested keys like "spotify_volume_enabled"
        if "." in key:
            # Further nested key, need to drill down
            current = widgets[section]
            key_parts = key.split(".")
            for part in key_parts[:-1]:
                if part not in current or not isinstance(current.get(part), dict):
                    current[part] = {}
                current = current[part]
            current[key_parts[-1]] = value
        else:
            widgets[section][key] = value
        
        # Save back
        settings_manager.set("widgets", widgets)
    else:
        # For other nested settings, use direct set
        settings_manager.set(dotted_key, value)


def get_current_preset_info(settings_manager: "SettingsManager") -> Dict[str, Any]:
    """Get information about the currently selected preset.
    
    Returns:
        Dict with 'key', 'name', 'description', 'index'
    """
    preset_key = settings_manager.get("preset", "custom")
    
    if preset_key not in PRESET_DEFINITIONS:
        preset_key = "custom"
    
    preset = PRESET_DEFINITIONS[preset_key]
    
    return {
        "key": preset_key,
        "name": preset.name,
        "description": preset.description,
        "index": get_preset_index(preset_key),
    }


def reset_non_custom_presets(settings_manager: "SettingsManager") -> None:
    """Reset all preset definitions to their defaults, preserving Custom preset.
    
    This resets the preset definitions themselves (stored in custom_preset_backup
    for Custom) but does NOT change the currently active preset selection.
    
    Use case: User has modified presets and wants to restore them to defaults
    without losing their Custom preset configuration.
    """
    # Clear the custom preset backup so it doesn't contain stale data
    # The next time user switches to Custom, it will use current settings
    current_preset = settings_manager.get("preset", "custom")
    
    # If currently on Custom, save current settings as the new Custom backup
    if current_preset == "custom":
        _save_custom_backup(settings_manager)
    
    # No other action needed - preset definitions are in code (PRESET_DEFINITIONS)
    # They don't need to be "reset" as they're immutable constants
    # The only persistent preset data is the custom_preset_backup
    
    logger.info("[PRESETS] Non-custom presets reset (custom backup preserved)")


def check_and_switch_to_custom(settings_manager: "SettingsManager") -> bool:
    """Check if current settings match the active preset, switch to custom if not.
    
    This should be called after user manually changes widget settings in the UI.
    If the current preset is not "custom" and settings have diverged, it will:
    1. Save current settings as custom backup
    2. Switch preset marker to "custom"
    
    Returns:
        True if switched to custom, False if still on original preset
    """
    current_preset = settings_manager.get("preset", "custom")
    
    # Already on custom, nothing to do
    if current_preset == "custom":
        return False
    
    # Check if current settings match the preset definition
    if current_preset not in PRESET_DEFINITIONS:
        return False
    
    preset = PRESET_DEFINITIONS[current_preset]
    preset_settings = adjust_settings_for_mc_mode(preset.settings)
    
    # Compare each preset setting with current value
    for key, expected_value in preset_settings.items():
        current_value = _get_nested_setting(settings_manager, key)
        if current_value != expected_value:
            # Settings diverged, switch to custom
            logger.info(
                "[PRESETS] Settings diverged from %s preset (key=%s), switching to custom",
                preset.name, key
            )
            _save_custom_backup(settings_manager)
            settings_manager.set("preset", "custom")
            try:
                settings_manager.save()
            except Exception as e:
                logger.error("[PRESETS] Failed to save after switching to custom: %s", e)
            return True
    
    return False


def _get_nested_setting(settings_manager: "SettingsManager", dotted_key: str) -> Any:
    """Get a nested setting using dot notation.
    
    Example: _get_nested_setting(sm, "widgets.clock.enabled") -> True
    """
    parts = dotted_key.split(".")
    
    if len(parts) < 2:
        return settings_manager.get(dotted_key)
    
    # For widget settings like "widgets.clock.enabled"
    if parts[0] == "widgets" and len(parts) >= 3:
        section = parts[1]  # e.g., "clock"
        key = ".".join(parts[2:])  # e.g., "enabled"
        
        widgets = settings_manager.get("widgets", {})
        if not isinstance(widgets, dict):
            return None
        
        section_data = widgets.get(section)
        if not isinstance(section_data, dict):
            return None
        
        # Handle nested keys
        if "." in key:
            current = section_data
            key_parts = key.split(".")
            for part in key_parts[:-1]:
                if not isinstance(current, dict):
                    return None
                current = current.get(part)
                if current is None:
                    return None
            return current.get(key_parts[-1]) if isinstance(current, dict) else None
        else:
            return section_data.get(key)
    else:
        # For other nested settings
        return settings_manager.get(dotted_key)
