"""
Display modes for image rendering.

Defines how images should be scaled and positioned on the screen.
"""
from enum import Enum


class DisplayMode(Enum):
    """
    Display mode for image rendering.
    
    Modes:
    - FILL: Crop and scale to fill screen (no letterboxing) - PRIMARY MODE
    - FIT: Scale to fit within screen (may have letterboxing)
    - SHRINK: Only scale down, never upscale (may have letterboxing)
    """
    FILL = "fill"      # Crop and scale to fill screen (primary mode)
    FIT = "fit"        # Scale to fit within screen with letterboxing
    SHRINK = "shrink"  # Only scale down, never upscale
    
    def __str__(self) -> str:
        """String representation."""
        return self.value
    
    @classmethod
    def from_string(cls, value: str) -> 'DisplayMode':
        """
        Create DisplayMode from string.
        
        Args:
            value: String value (e.g., 'fill', 'fit', 'shrink')
        
        Returns:
            DisplayMode enum
        
        Raises:
            ValueError: If value is not a valid display mode
        """
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Invalid display mode: {value}. "
                           f"Valid modes: {', '.join([m.value for m in cls])}")
