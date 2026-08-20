"""Inline custom-render items for the single Qt Quick runtime scene."""

from .background_item import BackgroundRenderItem
from .background_node import BackgroundRenderNode, SlideProofState
from .image_textures import PresentationTextureBinding, PresentationTextureHost
from .telemetry import RenderNodeSnapshot, RenderNodeTelemetry

__all__ = [
    "BackgroundRenderItem",
    "BackgroundRenderNode",
    "PresentationTextureBinding",
    "PresentationTextureHost",
    "RenderNodeSnapshot",
    "RenderNodeTelemetry",
    "SlideProofState",
]
