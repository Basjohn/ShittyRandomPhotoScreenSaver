"""Renderer backend abstractions for multi-API support.

Defines the interfaces each rendering backend must implement so the
DisplayWidget and related systems can remain agnostic to the underlying
graphics API (e.g., OpenGL, Direct3D 11).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class BackendCapabilities:
    """Describes the capabilities advertised by a renderer backend."""

    api_name: str
    api_version: str
    supports_triple_buffer: bool
    supports_vsync_toggle: bool
    supports_compute: bool
    supports_hdr: bool = False


@dataclass(frozen=True)
class SurfaceDescriptor:
    """Parameters required to create a render surface."""

    screen_index: int
    width: int
    height: int
    dpi: float
    vsync_enabled: bool
    prefer_triple_buffer: bool


class RenderSurface(ABC):
    """Abstract handle for a swap/presentable surface managed by a backend."""

    descriptor: SurfaceDescriptor

    def __init__(self, descriptor: SurfaceDescriptor) -> None:
        self.descriptor = descriptor

    @abstractmethod
    def resize(self, width: int, height: int, dpi: float) -> None:
        """Resize the underlying swap chain/back buffer to match widget geometry."""

    @abstractmethod
    def begin_frame(self) -> None:
        """Prepare the surface for rendering the next frame."""

    @abstractmethod
    def end_frame(self) -> None:
        """Finalize rendering for the current frame prior to presentation."""

    @abstractmethod
    def present(self) -> None:
        """Present the rendered frame to the display."""

    @abstractmethod
    def shutdown(self) -> None:
        """Release all resources associated with this surface."""


@dataclass
class TransitionRenderPacket:
    """Data required to render a transition on the active backend."""

    old_texture: Optional[Any]
    new_texture: Any
    progress: float
    duration_ms: int
    parameters: dict[str, Any]


class TransitionPipeline(ABC):
    """Interface for transition-specific GPU pipelines."""

    @abstractmethod
    def upload_assets(self, packet: TransitionRenderPacket) -> None:
        """Ensure textures and parameters are ready on the GPU."""

    @abstractmethod
    def render(self, packet: TransitionRenderPacket) -> None:
        """Issue GPU commands for the transition using current frame state."""

    @abstractmethod
    def cleanup(self) -> None:
        """Dispose of GPU resources tied to this pipeline."""


class RendererBackend(ABC):
    """Abstract renderer backend (OpenGL, D3D11, Vulkan, etc.)."""

    def __init__(self) -> None:
        self._capabilities: Optional[BackendCapabilities] = None

    @abstractmethod
    def initialize(self) -> None:
        """Create API devices/contexts. Called once at startup."""

    @abstractmethod
    def shutdown(self) -> None:
        """Release API-level resources and reset state."""

    @abstractmethod
    def create_surface(self, descriptor: SurfaceDescriptor) -> RenderSurface:
        """Create a new render surface (swap chain/backbuffer)."""

    @abstractmethod
    def destroy_surface(self, surface: RenderSurface) -> None:
        """Destroy a render surface previously created by the backend."""

    @abstractmethod
    def create_transition_pipeline(self, transition_name: str) -> TransitionPipeline:
        """Create a transition pipeline implementation for the given transition type."""

    @abstractmethod
    def release_transition_pipeline(self, pipeline: TransitionPipeline) -> None:
        """Dispose of a previously created transition pipeline."""

    def get_capabilities(self) -> BackendCapabilities:
        """Return backend capability metadata (cached after first build)."""

        if self._capabilities is None:
            self._capabilities = self._build_capabilities()
        return self._capabilities

    @abstractmethod
    def _build_capabilities(self) -> BackendCapabilities:
        """Populate capability metadata for this backend."""
