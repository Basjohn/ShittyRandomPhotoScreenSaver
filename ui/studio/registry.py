"""Which visualizer modes have a Studio adapter (mode-neutral registry).

A mode joins the Studio by registering ``mode_id -> "module:Factory"``: the factory
builds its ``StudioModeAdapter`` (schema, evaluator, fixtures, scene objects,
renderer). The shell, session, transport, viewport, Settings link and canonical
save path are shared; no mode copies them. Lookups import adapters lazily, so an
unopened Studio loads no mode code (dormancy).
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module


@dataclass(frozen=True)
class StudioEntry:
    mode_id: str
    title: str
    factory: str          # "package.module:Callable"


_ENTRIES: dict[str, StudioEntry] = {}


def register_studio_adapter(mode_id: str, title: str, factory: str) -> None:
    if ":" not in factory:
        raise ValueError("Studio adapter factory must be 'module:Callable'")
    _ENTRIES[mode_id] = StudioEntry(mode_id, title, factory)


def unregister_studio_adapter(mode_id: str) -> None:
    _ENTRIES.pop(mode_id, None)


def studio_modes() -> tuple[StudioEntry, ...]:
    return tuple(_ENTRIES.values())


def has_studio(mode_id: str) -> bool:
    return mode_id in _ENTRIES


def create_adapter(mode_id: str):
    module, _, name = _ENTRIES[mode_id].factory.partition(":")
    return getattr(import_module(module), name)()


# Built-in registrations (one line per mode).
register_studio_adapter("waveform_ribbon", "Waveform", "ui.studio.waveform_adapter:WaveformStudioAdapter")
register_studio_adapter("extruded_bubble", "Extruded Bubble", "ui.studio.extruded_bubble_adapter:ExtrudedBubbleStudioAdapter")
register_studio_adapter("bubble", "Bubble", "ui.studio.bubble_adapter:BubbleStudioAdapter")
register_studio_adapter("sphere", "Sphere", "ui.studio.sphere_adapter:SphereStudioAdapter")
register_studio_adapter("spectrum", "Spectrum", "ui.studio.spectrum_adapter:SpectrumStudioAdapter")
register_studio_adapter("extruded_spectrum", "Extruded Spectrum",
                        "ui.studio.extruded_spectrum_adapter:ExtrudedSpectrumStudioAdapter")
register_studio_adapter("shockwave_grid", "Neon Lake", "ui.studio.shockwave_grid_adapter:NeonLakeStudioAdapter")
register_studio_adapter("oscilloscope", "Oscilloscope", "ui.studio.oscilloscope_adapter:OscilloscopeStudioAdapter")


__all__ = ["StudioEntry", "create_adapter", "has_studio", "register_studio_adapter", "studio_modes",
           "unregister_studio_adapter"]
