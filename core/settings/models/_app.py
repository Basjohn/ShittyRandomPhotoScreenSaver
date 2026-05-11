"""Top-level AppSettings container."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.settings.models._core import (
    CacheSettings,
    DisplaySettings,
    InputSettings,
    ShadowSettings,
    SourceSettings,
    TransitionSettings,
)
from core.settings.models._widget_settings import AccessibilitySettings

if TYPE_CHECKING:
    from core.settings.settings_manager import SettingsManager


@dataclass
class AppSettings:
    """Complete application settings container."""
    display: DisplaySettings = field(default_factory=DisplaySettings)
    transitions: TransitionSettings = field(default_factory=TransitionSettings)
    input: InputSettings = field(default_factory=InputSettings)
    cache: CacheSettings = field(default_factory=CacheSettings)
    sources: SourceSettings = field(default_factory=SourceSettings)
    shadows: ShadowSettings = field(default_factory=ShadowSettings)
    accessibility: AccessibilitySettings = field(default_factory=AccessibilitySettings)
    
    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "AppSettings":
        """Load all settings from SettingsManager."""
        return cls(
            display=DisplaySettings.from_settings(settings),
            transitions=TransitionSettings.from_settings(settings),
            input=InputSettings.from_settings(settings),
            cache=CacheSettings.from_settings(settings),
            sources=SourceSettings.from_settings(settings),
            shadows=ShadowSettings.from_settings(settings),
            accessibility=AccessibilitySettings.from_settings(settings),
        )
