"""Allocation-conscious visualizer frame transport.

The recurring visualizer tick updates one packet in place. DisplayWidget then
passes its payload directly to the GL overlay without rebuilding the full
keyword mapping at each intermediate layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Sequence


@dataclass(slots=True)
class VisualizerFramePacket:
    """Mutable accepted-frame payload shared by the widget and display."""

    bars: Sequence[float] = ()
    bar_count: int = 0
    segments: int = 0
    fill_color: Any = None
    border_color: Any = None
    fade: float = 0.0
    playing: bool = False
    ghosting_enabled: bool = True
    ghost_alpha: float = 0.4
    ghost_decay: float = -1.0
    vis_mode: str = "spectrum"
    static_token: Any = None
    extra_kwargs: Dict[str, Any] = field(default_factory=dict)
