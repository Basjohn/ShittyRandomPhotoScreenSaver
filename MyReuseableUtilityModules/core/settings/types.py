"""
Types and data structures for the settings system.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

# Type variables
T = TypeVar('T')
SettingValue = Union[str, int, float, bool, None]
SettingChangeHandler = Callable[[str, SettingValue], None]


class SettingsCategory(Enum):
    """Categories for organizing settings."""
    GENERAL = "General"
    APPEARANCE = "Appearance"
    BEHAVIOR = "Behavior"
    PERFORMANCE = "Performance"
    HOTKEYS = "Hotkeys"
    EXPERIMENTAL = "Experimental"


@dataclass
class SettingDefinition:
    """Definition for a single setting."""
    default: SettingValue
    setting_type: Type
    validator: Optional[Callable[[Any], bool]] = None
    options: Optional[list] = None
    description: str = ""
    requires_restart: bool = False
    category: SettingsCategory = SettingsCategory.GENERAL
