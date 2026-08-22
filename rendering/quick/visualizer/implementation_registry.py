"""Static metadata with lazy internal Qt Quick visualizer resolution."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module

from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS

from .render_contract import QuickVisualizerRenderer


@dataclass(frozen=True, slots=True)
class QuickVisualizerImplementationDescriptor:
    mode_id: str
    module_name: str
    factory_name: str = "create_visualizer_renderer"


_IMPLEMENTATIONS = (
    QuickVisualizerImplementationDescriptor(
        mode_id="spectrum",
        module_name=(
            "rendering.quick.visualizer.implementations.spectrum"
        ),
    ),
    QuickVisualizerImplementationDescriptor(
        mode_id="oscilloscope",
        module_name=(
            "rendering.quick.visualizer.implementations.oscilloscope"
        ),
    ),
    QuickVisualizerImplementationDescriptor(
        mode_id="sine_wave",
        module_name=(
            "rendering.quick.visualizer.implementations.sine_wave"
        ),
    ),
    QuickVisualizerImplementationDescriptor(
        mode_id="bubble",
        module_name=(
            "rendering.quick.visualizer.implementations.bubble"
        ),
    ),
)
_BY_ID = {descriptor.mode_id: descriptor for descriptor in _IMPLEMENTATIONS}


def iter_quick_visualizer_implementations(
) -> tuple[QuickVisualizerImplementationDescriptor, ...]:
    return _IMPLEMENTATIONS


def resolve_quick_visualizer_renderer(
    mode_id: object,
) -> QuickVisualizerRenderer | None:
    canonical = str(mode_id or "").strip().lower()
    if canonical not in VISUALIZER_MODE_IDS:
        raise ValueError(f"unknown canonical visualizer mode: {mode_id!r}")
    descriptor = _BY_ID.get(canonical)
    if descriptor is None:
        return None
    module = import_module(descriptor.module_name)
    factory = getattr(module, descriptor.factory_name, None)
    if not callable(factory):
        raise RuntimeError(
            f"Quick visualizer factory is unavailable: {descriptor.module_name}:"
            f"{descriptor.factory_name}"
        )
    renderer = factory()
    if getattr(renderer, "mode_id", None) != canonical:
        raise RuntimeError(
            f"Quick visualizer implementation identity mismatch: {canonical}"
        )
    if not callable(getattr(renderer, "render", None)) or not callable(
        getattr(renderer, "release_resources", None)
    ):
        raise TypeError(
            f"Quick visualizer implementation violates render contract: {canonical}"
        )
    return renderer


__all__ = [
    "QuickVisualizerImplementationDescriptor",
    "iter_quick_visualizer_implementations",
    "resolve_quick_visualizer_renderer",
]
