"""Shared visualizer mode contract metadata.

This module centralizes the stable mode identifiers and the UI/runtime wiring
metadata that had been duplicated across presets, WidgetsTab plumbing, and
tests. It is intentionally small: the goal is one source of truth for mode
identity and preset ownership without rebuilding the whole visualizer stack
around a giant generic schema.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class VisualizerShellPolicy(str, Enum):
    """Retained chrome owned by the visualizer presentation root."""

    CARD = "card"
    FRAMELESS = "frameless"


class VisualizerClipPolicy(str, Enum):
    """Content clip resolved before a frame reaches the render thread."""

    CARD_INTERIOR = "card_interior"
    VIEWPORT_RECT = "viewport_rect"


@dataclass(frozen=True, slots=True)
class VisualizerModePresentationPolicy:
    shell_policy: VisualizerShellPolicy
    clip_policy: VisualizerClipPolicy
    viewport_resize_capable: bool


_REFLOWING_CARDED_POLICY = VisualizerModePresentationPolicy(
    shell_policy=VisualizerShellPolicy.CARD,
    clip_policy=VisualizerClipPolicy.CARD_INTERIOR,
    # All five current modes recompute their domain from committed geometry
    # (Bubble via its baseline-relative logical domain), so every mode is
    # viewport-resize-capable. The deterministic G4 implementation is complete;
    # installed eyes-on acceptance is deferred until Quick is production
    # authoritative after H.
    viewport_resize_capable=True,
)

@dataclass(frozen=True)
class VisualizerModeDescriptor:
    mode_id: str
    display_name: str
    preset_slider_attr: str
    setting_prefixes: tuple[str, ...]
    presentation_policy: VisualizerModePresentationPolicy
    # Lazy wiring identity: import-path/name strings only. Holding these as
    # strings keeps this metadata module free of Qt/renderer/runtime imports;
    # the actual module is imported on demand by the owning caller
    # (quick_display_visualizer_owner for the frame runtime, the Quick renderer
    # implementation_registry for the renderer). This is the single source of
    # per-mode runtime/renderer wiring; the previous duplicate five-way tables
    # now derive from here.
    frame_runtime_module: str
    frame_runtime_class: str
    renderer_module: str
    renderer_factory: str = "create_visualizer_renderer"

    @property
    def preset_key(self) -> str:
        return f"preset_{self.mode_id}"


_ALL_DESCRIPTORS: tuple[VisualizerModeDescriptor, ...] = (
    VisualizerModeDescriptor(
        "spectrum",
        "Spectrum",
        "_spectrum_preset_slider",
        ("spectrum_",),
        _REFLOWING_CARDED_POLICY,
        frame_runtime_module="widgets.spotify_visualizer.spectrum_frame_runtime",
        frame_runtime_class="SpectrumFrameRuntime",
        renderer_module="rendering.quick.visualizer.implementations.spectrum",
    ),
    VisualizerModeDescriptor(
        "oscilloscope",
        "Oscilloscope",
        "_osc_preset_slider",
        ("osc_", "oscilloscope_"),
        _REFLOWING_CARDED_POLICY,
        frame_runtime_module="widgets.spotify_visualizer.oscilloscope_frame_runtime",
        frame_runtime_class="OscilloscopeFrameRuntime",
        renderer_module="rendering.quick.visualizer.implementations.oscilloscope",
    ),
    VisualizerModeDescriptor(
        "sine_wave",
        "Sine Waves",
        "_sine_preset_slider",
        ("sine_", "sine_wave_", "sinewave_"),
        _REFLOWING_CARDED_POLICY,
        frame_runtime_module="widgets.spotify_visualizer.sine_frame_runtime",
        frame_runtime_class="SineFrameRuntime",
        renderer_module="rendering.quick.visualizer.implementations.sine_wave",
    ),
    VisualizerModeDescriptor(
        "bubble",
        "Bubble",
        "_bubble_preset_slider",
        ("bubble_",),
        _REFLOWING_CARDED_POLICY,
        frame_runtime_module="widgets.spotify_visualizer.bubble_frame_runtime",
        frame_runtime_class="BubbleFrameRuntime",
        renderer_module="rendering.quick.visualizer.implementations.bubble",
    ),
    VisualizerModeDescriptor(
        "devcurve",
        "Spline Curve",
        "_devcurve_preset_slider",
        ("devcurve_",),
        _REFLOWING_CARDED_POLICY,
        frame_runtime_module="widgets.spotify_visualizer.devcurve_frame_runtime",
        frame_runtime_class="DevCurveFrameRuntime",
        renderer_module="rendering.quick.visualizer.implementations.devcurve",
    ),
)

_GATED_MODES: dict[str, callable] = {}

def _active_descriptors() -> tuple[VisualizerModeDescriptor, ...]:
    return tuple(d for d in _ALL_DESCRIPTORS if d.mode_id not in _GATED_MODES or _GATED_MODES[d.mode_id]())


VISUALIZER_MODE_IDS: tuple[str, ...] = tuple(d.mode_id for d in _ALL_DESCRIPTORS)


def iter_visualizer_mode_descriptors() -> tuple[VisualizerModeDescriptor, ...]:
    """Return only the currently active (non-gated) mode descriptors."""
    return _active_descriptors()


def iter_all_visualizer_mode_descriptors() -> tuple[VisualizerModeDescriptor, ...]:
    """Return every registered canonical mode descriptor, gated or not.

    Schema/default/renderer-registration authority uses this (every canonical
    mode has a renderer/runtime regardless of enable-state); runtime *selection*
    and cycling use :func:`iter_visualizer_mode_descriptors` instead.
    """
    return _ALL_DESCRIPTORS


def get_visualizer_mode_descriptor(mode_id: str) -> VisualizerModeDescriptor:
    """Look up by mode_id.  Searches ALL modes (including gated) so
    settings plumbing never crashes on a stored gated-off mode."""
    for descriptor in _ALL_DESCRIPTORS:
        if descriptor.mode_id == mode_id:
            return descriptor
    raise KeyError(f"Unknown visualizer mode: {mode_id}")


def get_default_visualizer_mode_id() -> str:
    """Return the canonical default active mode id."""
    try:
        from core.settings.default_settings import DEFAULT_SETTINGS

        configured = str(DEFAULT_SETTINGS.get("widgets.spotify_visualizer.mode", "") or "").strip().lower()
        if not configured:
            widgets = DEFAULT_SETTINGS.get("widgets")
            if isinstance(widgets, dict):
                spotify_vis = widgets.get("spotify_visualizer")
                if isinstance(spotify_vis, dict):
                    configured = str(spotify_vis.get("mode", "") or "").strip().lower()
        if configured in VISUALIZER_MODE_IDS and is_mode_active(configured):
            return configured
    except Exception:
        pass

    active = _active_descriptors()
    return active[0].mode_id if active else "spectrum"


def get_preset_slider_attr(mode_id: str) -> str:
    return get_visualizer_mode_descriptor(mode_id).preset_slider_attr


def get_preset_key(mode_id: str) -> str:
    return get_visualizer_mode_descriptor(mode_id).preset_key


def get_setting_prefixes(mode_id: str) -> tuple[str, ...]:
    return get_visualizer_mode_descriptor(mode_id).setting_prefixes


def get_visualizer_presentation_policy(
    mode_id: str,
) -> VisualizerModePresentationPolicy:
    return get_visualizer_mode_descriptor(mode_id).presentation_policy


def is_mode_active(mode_id: str) -> bool:
    """True if *mode_id* is not behind a closed dev gate."""
    gate = _GATED_MODES.get(mode_id)
    return gate is None or gate()


def coerce_visualizer_mode_id(mode_id: str | None) -> str:
    """Return canonical mode id when known, else fallback to default active mode.

    Unknown values fall back to the first active mode.
    """
    raw = str(mode_id or "").strip().lower()
    if raw in VISUALIZER_MODE_IDS:
        return raw
    return get_default_visualizer_mode_id()
