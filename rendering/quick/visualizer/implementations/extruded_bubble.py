"""Extruded Bubble's Qt Quick renderer.

S2 admits the mode's frame and owns no GL resources: the mode is registered behind its closed gate while S3 ports
the lab's proven passes (``tools/labs/extruded_bubble_lab.py``) onto the shared Scene3D owners
(``Extruded_Bubble_Target.md`` section 10). Until then it draws nothing.
"""
from __future__ import annotations

from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame
from widgets.spotify_visualizer.render_state import ExtrudedBubbleFrame


class QuickExtrudedBubbleRenderer:
    mode_id = "extruded_bubble"

    @property
    def has_resources(self) -> bool:
        return False

    def prepare_step(self, frame: QuickVisualizerRenderFrame) -> bool:
        """Nothing to compile or allocate yet (S3 warms its programs and targets here, one unit a frame)."""
        return True

    def render(self, frame: QuickVisualizerRenderFrame) -> None:
        if not isinstance(frame.snapshot.logical.mode_state, ExtrudedBubbleFrame):
            raise TypeError("Extruded Bubble renderer received another mode frame")

    def release_resources(self) -> None:
        return None


def create_visualizer_renderer() -> QuickExtrudedBubbleRenderer:
    return QuickExtrudedBubbleRenderer()
