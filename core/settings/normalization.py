"""
Centralized settings normalization and coercion system.

This module provides a single, reliable, normalized method for converting
persisted settings values into typed Python objects. All settings coercion
should go through this module to ensure consistency.

Design Principles:
1. Single source of truth for all type coercion
2. Explicit fallback values for safety
3. Comprehensive logging of normalization failures
4. Support for legacy formats and migration
5. Type-safe enum handling

Usage:
    from core.settings.normalization import SettingsNormalizer
    
    normalizer = SettingsNormalizer()
    position = normalizer.to_widget_position(raw_value, fallback=WidgetPosition.TOP_RIGHT)
    enabled = normalizer.to_bool(raw_value, fallback=True)
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional, TypeVar, Type, Union, List

from core.settings.models import (
    WidgetPosition,
    DisplayMode,
    TransitionType,
)

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Enum)


class SettingsNormalizer:
    """
    Centralized settings normalization with comprehensive type coercion.
    
    This class handles all conversions from persisted settings (strings, QVariant, etc.)
    into typed Python objects. It provides consistent error handling, logging, and
    fallback behavior across the entire application.
    """
    
    def __init__(self, log_failures: bool = True):
        """
        Initialize the normalizer.
        
        Args:
            log_failures: Whether to log normalization failures (default True)
        """
        self.log_failures = log_failures
        self._normalization_stats = {
            'successes': 0,
            'fallbacks': 0,
            'errors': 0,
        }
    
    def to_bool(self, value: Any, fallback: bool = False) -> bool:
        """
        Normalize a value to boolean.
        
        Handles: bool, int (0/1), str ("true"/"false"/"yes"/"no"/"1"/"0"), QVariant
        
        Args:
            value: Raw value from settings
            fallback: Default value if normalization fails
            
        Returns:
            Normalized boolean value
        """
        if isinstance(value, bool):
            self._normalization_stats['successes'] += 1
            return value
        
        if value is None:
            self._normalization_stats['fallbacks'] += 1
            return fallback
        
        # Handle numeric types
        if isinstance(value, (int, float)):
            self._normalization_stats['successes'] += 1
            return bool(value)
        
        # Handle string representations
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {'true', 'yes', '1', 'on', 'enabled'}:
                self._normalization_stats['successes'] += 1
                return True
            if normalized in {'false', 'no', '0', 'off', 'disabled'}:
                self._normalization_stats['successes'] += 1
                return False
        
        # Fallback
        if self.log_failures:
            logger.warning("[SETTINGS_NORM] Failed to normalize bool: value=%r, using fallback=%r", 
                         value, fallback)
        self._normalization_stats['fallbacks'] += 1
        return fallback
    
    def to_int(self, value: Any, fallback: int = 0, min_val: Optional[int] = None, 
               max_val: Optional[int] = None) -> int:
        """
        Normalize a value to integer with optional bounds.
        
        Args:
            value: Raw value from settings
            fallback: Default value if normalization fails
            min_val: Minimum allowed value (inclusive)
            max_val: Maximum allowed value (inclusive)
            
        Returns:
            Normalized integer value
        """
        if isinstance(value, int):
            result = value
        elif isinstance(value, float):
            result = int(value)
        elif isinstance(value, str):
            try:
                result = int(value)
            except ValueError:
                if self.log_failures:
                    logger.warning("[SETTINGS_NORM] Failed to parse int: value=%r, using fallback=%r",
                                 value, fallback)
                self._normalization_stats['fallbacks'] += 1
                return fallback
        elif value is None:
            self._normalization_stats['fallbacks'] += 1
            return fallback
        else:
            if self.log_failures:
                logger.warning("[SETTINGS_NORM] Invalid int type: value=%r (type=%s), using fallback=%r",
                             value, type(value).__name__, fallback)
            self._normalization_stats['fallbacks'] += 1
            return fallback
        
        # Apply bounds
        if min_val is not None and result < min_val:
            if self.log_failures:
                logger.warning("[SETTINGS_NORM] Int below minimum: value=%d, min=%d, clamping",
                             result, min_val)
            result = min_val
        if max_val is not None and result > max_val:
            if self.log_failures:
                logger.warning("[SETTINGS_NORM] Int above maximum: value=%d, max=%d, clamping",
                             result, max_val)
            result = max_val
        
        self._normalization_stats['successes'] += 1
        return result
    
    def to_float(self, value: Any, fallback: float = 0.0, min_val: Optional[float] = None,
                 max_val: Optional[float] = None) -> float:
        """
        Normalize a value to float with optional bounds.
        
        Args:
            value: Raw value from settings
            fallback: Default value if normalization fails
            min_val: Minimum allowed value (inclusive)
            max_val: Maximum allowed value (inclusive)
            
        Returns:
            Normalized float value
        """
        if isinstance(value, (int, float)):
            result = float(value)
        elif isinstance(value, str):
            try:
                result = float(value)
            except ValueError:
                if self.log_failures:
                    logger.warning("[SETTINGS_NORM] Failed to parse float: value=%r, using fallback=%r",
                                 value, fallback)
                self._normalization_stats['fallbacks'] += 1
                return fallback
        elif value is None:
            self._normalization_stats['fallbacks'] += 1
            return fallback
        else:
            if self.log_failures:
                logger.warning("[SETTINGS_NORM] Invalid float type: value=%r (type=%s), using fallback=%r",
                             value, type(value).__name__, fallback)
            self._normalization_stats['fallbacks'] += 1
            return fallback
        
        # Apply bounds
        if min_val is not None and result < min_val:
            if self.log_failures:
                logger.warning("[SETTINGS_NORM] Float below minimum: value=%f, min=%f, clamping",
                             result, min_val)
            result = min_val
        if max_val is not None and result > max_val:
            if self.log_failures:
                logger.warning("[SETTINGS_NORM] Float above maximum: value=%f, max=%f, clamping",
                             result, max_val)
            result = max_val
        
        self._normalization_stats['successes'] += 1
        return result
    
    def to_string(self, value: Any, fallback: str = "") -> str:
        """
        Normalize a value to string.
        
        Args:
            value: Raw value from settings
            fallback: Default value if normalization fails
            
        Returns:
            Normalized string value
        """
        if value is None:
            self._normalization_stats['fallbacks'] += 1
            return fallback
        
        if isinstance(value, str):
            self._normalization_stats['successes'] += 1
            return value
        
        # Convert to string
        try:
            result = str(value)
            self._normalization_stats['successes'] += 1
            return result
        except Exception as e:
            if self.log_failures:
                logger.warning("[SETTINGS_NORM] Failed to convert to string: value=%r, error=%s, using fallback=%r",
                             value, e, fallback)
            self._normalization_stats['fallbacks'] += 1
            return fallback
    
    def to_enum(self, value: Any, enum_type: Type[T], fallback: T) -> T:
        """
        Normalize a value to an enum with comprehensive format support.
        
        Handles:
        - Direct enum instances
        - Enum values (e.g., "top_left")
        - Qualified names (e.g., "WidgetPosition.TOP_LEFT")
        - Display names (e.g., "Top Left")
        - Legacy formats
        
        Args:
            value: Raw value from settings
            enum_type: Target enum class
            fallback: Default enum value if normalization fails
            
        Returns:
            Normalized enum value
        """
        # Already correct type
        if isinstance(value, enum_type):
            self._normalization_stats['successes'] += 1
            return value
        
        if value is None:
            self._normalization_stats['fallbacks'] += 1
            return fallback
        
        # Convert to string for processing
        text = str(value)
        
        # Strip enum class prefix if present (e.g., "WidgetPosition.TOP_LEFT" -> "TOP_LEFT")
        if "." in text:
            text = text.split(".")[-1]
        
        # Normalize: lowercase, replace spaces/hyphens with underscores
        text = text.strip().lower().replace(" ", "_").replace("-", "_")
        
        if not text:
            self._normalization_stats['fallbacks'] += 1
            return fallback
        
        # Try direct value match
        try:
            result = enum_type(text)
            self._normalization_stats['successes'] += 1
            return result
        except ValueError:
            pass
        
        # Try name match (case-insensitive)
        for member in enum_type:
            if member.name.lower() == text:
                self._normalization_stats['successes'] += 1
                return member
        
        # Fallback
        if self.log_failures:
            logger.warning("[SETTINGS_NORM] Failed to normalize enum %s: value=%r, using fallback=%s",
                         enum_type.__name__, value, fallback.name)
        self._normalization_stats['fallbacks'] += 1
        return fallback
    
    def to_widget_position(self, value: Any, fallback: WidgetPosition = WidgetPosition.TOP_RIGHT) -> WidgetPosition:
        """
        Normalize a value to WidgetPosition enum.
        
        This is a convenience wrapper around to_enum() specifically for widget positions.
        
        Args:
            value: Raw value from settings
            fallback: Default position if normalization fails
            
        Returns:
            Normalized WidgetPosition
        """
        return self.to_enum(value, WidgetPosition, fallback)
    
    def to_display_mode(self, value: Any, fallback: DisplayMode = DisplayMode.FILL) -> DisplayMode:
        """
        Normalize a value to DisplayMode enum.
        
        Args:
            value: Raw value from settings
            fallback: Default mode if normalization fails
            
        Returns:
            Normalized DisplayMode
        """
        return self.to_enum(value, DisplayMode, fallback)
    
    def to_transition_type(self, value: Any, fallback: TransitionType = TransitionType.CROSSFADE) -> TransitionType:
        """
        Normalize a value to TransitionType enum.
        
        Args:
            value: Raw value from settings
            fallback: Default transition if normalization fails
            
        Returns:
            Normalized TransitionType
        """
        return self.to_enum(value, TransitionType, fallback)
    
    def to_string_list(self, value: Any, fallback: Optional[List[str]] = None) -> List[str]:
        """
        Normalize a value to a list of strings.
        
        Handles: list, tuple, comma-separated string
        
        Args:
            value: Raw value from settings
            fallback: Default list if normalization fails
            
        Returns:
            Normalized list of strings
        """
        if fallback is None:
            fallback = []
        
        if value is None:
            self._normalization_stats['fallbacks'] += 1
            return fallback
        
        if isinstance(value, (list, tuple)):
            self._normalization_stats['successes'] += 1
            return [str(item) for item in value]
        
        if isinstance(value, str):
            # Handle comma-separated values
            if "," in value:
                result = [item.strip() for item in value.split(",") if item.strip()]
                self._normalization_stats['successes'] += 1
                return result
            # Single value
            if value.strip():
                self._normalization_stats['successes'] += 1
                return [value.strip()]
            # Empty string
            self._normalization_stats['fallbacks'] += 1
            return fallback
        
        # Fallback
        if self.log_failures:
            logger.warning("[SETTINGS_NORM] Failed to normalize string list: value=%r (type=%s), using fallback",
                         value, type(value).__name__)
        self._normalization_stats['fallbacks'] += 1
        return fallback
    
    def get_stats(self) -> dict:
        """
        Get normalization statistics.
        
        Returns:
            Dictionary with success/fallback/error counts
        """
        return self._normalization_stats.copy()
    
    def reset_stats(self) -> None:
        """Reset normalization statistics."""
        self._normalization_stats = {
            'successes': 0,
            'fallbacks': 0,
            'errors': 0,
        }


# Global singleton instance for convenience
_global_normalizer: Optional[SettingsNormalizer] = None


def get_normalizer() -> SettingsNormalizer:
    """
    Get the global settings normalizer instance.
    
    Returns:
        Global SettingsNormalizer instance
    """
    global _global_normalizer
    if _global_normalizer is None:
        _global_normalizer = SettingsNormalizer()
    return _global_normalizer


# Convenience functions that use the global normalizer
def normalize_bool(value: Any, fallback: bool = False) -> bool:
    """Normalize to bool using global normalizer."""
    return get_normalizer().to_bool(value, fallback)


def normalize_int(value: Any, fallback: int = 0, min_val: Optional[int] = None,
                  max_val: Optional[int] = None) -> int:
    """Normalize to int using global normalizer."""
    return get_normalizer().to_int(value, fallback, min_val, max_val)


def normalize_float(value: Any, fallback: float = 0.0, min_val: Optional[float] = None,
                    max_val: Optional[float] = None) -> float:
    """Normalize to float using global normalizer."""
    return get_normalizer().to_float(value, fallback, min_val, max_val)


def normalize_string(value: Any, fallback: str = "") -> str:
    """Normalize to string using global normalizer."""
    return get_normalizer().to_string(value, fallback)


def normalize_widget_position(value: Any, fallback: WidgetPosition = WidgetPosition.TOP_RIGHT) -> WidgetPosition:
    """Normalize to WidgetPosition using global normalizer."""
    return get_normalizer().to_widget_position(value, fallback)


def normalize_display_mode(value: Any, fallback: DisplayMode = DisplayMode.FILL) -> DisplayMode:
    """Normalize to DisplayMode using global normalizer."""
    return get_normalizer().to_display_mode(value, fallback)


def normalize_transition_type(value: Any, fallback: TransitionType = TransitionType.CROSSFADE) -> TransitionType:
    """Normalize to TransitionType using global normalizer."""
    return get_normalizer().to_transition_type(value, fallback)
