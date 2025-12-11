"""
Transition State Management - Extracted from GLCompositor for better separation.

Contains dataclasses for per-transition state and helper functions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Callable

from PySide6.QtCore import QPoint
from PySide6.QtGui import QPixmap, QRegion


@dataclass
class TransitionStateBase:
    """Base class for transition state."""
    old_pixmap: Optional[QPixmap] = None
    new_pixmap: Optional[QPixmap] = None
    progress: float = 0.0  # 0..1


@dataclass
class CrossfadeState(TransitionStateBase):
    """State for a compositor-driven crossfade transition."""
    pass


@dataclass
class SlideState(TransitionStateBase):
    """State for a compositor-driven slide transition.
    
    PERFORMANCE: Float coordinates are pre-computed at creation time to avoid
    repeated QPoint.x()/y() calls and float() conversions in the hot render path.
    """
    old_start: QPoint = field(default_factory=lambda: QPoint(0, 0))
    old_end: QPoint = field(default_factory=lambda: QPoint(0, 0))
    new_start: QPoint = field(default_factory=lambda: QPoint(0, 0))
    new_end: QPoint = field(default_factory=lambda: QPoint(0, 0))
    
    # Pre-computed float coordinates for hot path
    _old_start_x: float = 0.0
    _old_start_y: float = 0.0
    _old_delta_x: float = 0.0
    _old_delta_y: float = 0.0
    _new_start_x: float = 0.0
    _new_start_y: float = 0.0
    _new_delta_x: float = 0.0
    _new_delta_y: float = 0.0
    
    def __post_init__(self) -> None:
        """Pre-compute float coordinates to avoid per-frame conversions."""
        self._old_start_x = float(self.old_start.x())
        self._old_start_y = float(self.old_start.y())
        self._old_delta_x = float(self.old_end.x()) - self._old_start_x
        self._old_delta_y = float(self.old_end.y()) - self._old_start_y
        self._new_start_x = float(self.new_start.x())
        self._new_start_y = float(self.new_start.y())
        self._new_delta_x = float(self.new_end.x()) - self._new_start_x
        self._new_delta_y = float(self.new_end.y()) - self._new_start_y


@dataclass
class WipeState(TransitionStateBase):
    """State for a compositor-driven wipe transition."""
    region: Optional[QRegion] = None
    direction: int = 0  # WipeDirection enum value


@dataclass
class BlockFlipState(TransitionStateBase):
    """State for a compositor-driven block flip transition.
    
    The detailed per-block progression is managed by the controller; the
    compositor only needs the reveal region to clip the new pixmap.
    """
    region: Optional[QRegion] = None
    cols: int = 0
    rows: int = 0
    direction: Optional[int] = None  # SlideDirection enum value


@dataclass
class BlockSpinState(TransitionStateBase):
    """State for a compositor-driven block spin transition.
    
    GLSL-backed Block Spins render a single thin 3D slab that flips the old
    image to the new one over a black void, with edge-only specular highlights.
    """
    direction: int = 0  # SlideDirection enum value (0=left, 1=right, 2=up, 3=down)


@dataclass
class BlindsState(TransitionStateBase):
    """State for a compositor-driven blinds transition.
    
    Like BlockFlip, the controller owns per-slat progression and provides an
    aggregate reveal region; the compositor only clips the new pixmap.
    """
    region: Optional[QRegion] = None
    cols: int = 0
    rows: int = 0


@dataclass
class DiffuseState(TransitionStateBase):
    """State for a compositor-driven diffuse transition."""
    region: Optional[QRegion] = None
    cols: int = 0
    rows: int = 0
    shape_mode: int = 0  # 0=Rectangle, 1=Membrane, etc.


@dataclass
class PeelState(TransitionStateBase):
    """State for a compositor-driven peel transition."""
    direction: int = 0
    strips: int = 8


@dataclass
class WarpState(TransitionStateBase):
    """State for a compositor-driven warp dissolve transition."""
    pass


@dataclass
class RaindropsState(TransitionStateBase):
    """State for a compositor-driven raindrops/ripple transition."""
    pass


@dataclass
class CrumbleState(TransitionStateBase):
    """State for a compositor-driven crumble transition."""
    seed: float = 0.0
    piece_count: float = 8.0
    crack_complexity: float = 1.0
    mosaic_mode: bool = False


class TransitionStateManager:
    """
    Manages active transition states.
    
    Provides a clean interface for getting/setting transition state
    without polluting the compositor with state management logic.
    """
    
    def __init__(self):
        self._crossfade: Optional[CrossfadeState] = None
        self._slide: Optional[SlideState] = None
        self._wipe: Optional[WipeState] = None
        self._blockflip: Optional[BlockFlipState] = None
        self._blockspin: Optional[BlockSpinState] = None
        self._blinds: Optional[BlindsState] = None
        self._diffuse: Optional[DiffuseState] = None
        self._peel: Optional[PeelState] = None
        self._warp: Optional[WarpState] = None
        self._raindrops: Optional[RaindropsState] = None
        self._crumble: Optional[CrumbleState] = None
        
        # Callbacks for state changes
        self._on_state_change: Optional[Callable[[str, bool], None]] = None
    
    def set_on_state_change(self, callback: Callable[[str, bool], None]) -> None:
        """Set callback for state changes. Args: (transition_name, is_active)"""
        self._on_state_change = callback
    
    def _notify(self, name: str, active: bool) -> None:
        if self._on_state_change:
            try:
                self._on_state_change(name, active)
            except Exception:
                pass
    
    @property
    def crossfade(self) -> Optional[CrossfadeState]:
        return self._crossfade
    
    @crossfade.setter
    def crossfade(self, value: Optional[CrossfadeState]) -> None:
        was_active = self._crossfade is not None
        self._crossfade = value
        is_active = value is not None
        if was_active != is_active:
            self._notify("crossfade", is_active)
    
    @property
    def slide(self) -> Optional[SlideState]:
        return self._slide
    
    @slide.setter
    def slide(self, value: Optional[SlideState]) -> None:
        was_active = self._slide is not None
        self._slide = value
        is_active = value is not None
        if was_active != is_active:
            self._notify("slide", is_active)
    
    @property
    def wipe(self) -> Optional[WipeState]:
        return self._wipe
    
    @wipe.setter
    def wipe(self, value: Optional[WipeState]) -> None:
        was_active = self._wipe is not None
        self._wipe = value
        is_active = value is not None
        if was_active != is_active:
            self._notify("wipe", is_active)
    
    @property
    def diffuse(self) -> Optional[DiffuseState]:
        return self._diffuse
    
    @diffuse.setter
    def diffuse(self, value: Optional[DiffuseState]) -> None:
        was_active = self._diffuse is not None
        self._diffuse = value
        is_active = value is not None
        if was_active != is_active:
            self._notify("diffuse", is_active)
    
    @property
    def peel(self) -> Optional[PeelState]:
        return self._peel
    
    @peel.setter
    def peel(self, value: Optional[PeelState]) -> None:
        was_active = self._peel is not None
        self._peel = value
        is_active = value is not None
        if was_active != is_active:
            self._notify("peel", is_active)
    
    @property
    def blockspin(self) -> Optional[BlockSpinState]:
        return self._blockspin
    
    @blockspin.setter
    def blockspin(self, value: Optional[BlockSpinState]) -> None:
        was_active = self._blockspin is not None
        self._blockspin = value
        is_active = value is not None
        if was_active != is_active:
            self._notify("blockspin", is_active)
    
    @property
    def blockflip(self) -> Optional[BlockFlipState]:
        return self._blockflip
    
    @blockflip.setter
    def blockflip(self, value: Optional[BlockFlipState]) -> None:
        was_active = self._blockflip is not None
        self._blockflip = value
        is_active = value is not None
        if was_active != is_active:
            self._notify("blockflip", is_active)
    
    @property
    def blinds(self) -> Optional[BlindsState]:
        return self._blinds
    
    @blinds.setter
    def blinds(self, value: Optional[BlindsState]) -> None:
        was_active = self._blinds is not None
        self._blinds = value
        is_active = value is not None
        if was_active != is_active:
            self._notify("blinds", is_active)
    
    @property
    def warp(self) -> Optional[WarpState]:
        return self._warp
    
    @warp.setter
    def warp(self, value: Optional[WarpState]) -> None:
        was_active = self._warp is not None
        self._warp = value
        is_active = value is not None
        if was_active != is_active:
            self._notify("warp", is_active)
    
    @property
    def raindrops(self) -> Optional[RaindropsState]:
        return self._raindrops
    
    @raindrops.setter
    def raindrops(self, value: Optional[RaindropsState]) -> None:
        was_active = self._raindrops is not None
        self._raindrops = value
        is_active = value is not None
        if was_active != is_active:
            self._notify("raindrops", is_active)
    
    @property
    def crumble(self) -> Optional[CrumbleState]:
        return self._crumble
    
    @crumble.setter
    def crumble(self, value: Optional[CrumbleState]) -> None:
        was_active = self._crumble is not None
        self._crumble = value
        is_active = value is not None
        if was_active != is_active:
            self._notify("crumble", is_active)
    
    def get_active_transition(self) -> Optional[str]:
        """Get the name of the currently active transition, or None."""
        if self._crossfade is not None:
            return "crossfade"
        if self._slide is not None:
            return "slide"
        if self._wipe is not None:
            return "wipe"
        if self._diffuse is not None:
            return "diffuse"
        if self._peel is not None:
            return "peel"
        if self._blockspin is not None:
            return "blockspin"
        if self._blockflip is not None:
            return "blockflip"
        if self._blinds is not None:
            return "blinds"
        if self._warp is not None:
            return "warp"
        if self._raindrops is not None:
            return "raindrops"
        if self._crumble is not None:
            return "crumble"
        return None
    
    def clear_all(self) -> None:
        """Clear all transition states."""
        self._crossfade = None
        self._slide = None
        self._wipe = None
        self._blockflip = None
        self._blockspin = None
        self._blinds = None
        self._diffuse = None
        self._peel = None
        self._warp = None
        self._raindrops = None
        self._crumble = None
