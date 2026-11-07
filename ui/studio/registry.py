"""Which visualizer modes have a Studio adapter (mode-neutral registry).

A mode joins the Studio by registering ``mode_id -> "module:Factory"``: the factory
builds its ``StudioModeAdapter`` (schema, evaluator, fixtures, scene objects,
renderer). The shell, session, transport, viewport, Settings link and canonical
save path are shared; no mode copies them. Lookups import adapters lazily, so an
unopened Studio loads no mode code (dormancy).

The Studio has no names of its own: the switcher, header and window title all take the
mode's user-facing ``display_name`` from the mode registry
(``core.settings.visualizer_mode_registry``), the same one Settings and Guided Setup show.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module

from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor


def studio_mode_name(mode_id: str) -> str:
    """The mode's user-facing name (the switcher's entry): the registry's ``display_name``."""
    return get_visualizer_mode_descriptor(mode_id).display_name


def studio_title(mode_id: str) -> str:
    """The Studio's header and window title for ``mode_id``."""
    return f"{studio_mode_name(mode_id)} Studio"


@dataclass(frozen=True)
class StudioEntry:
    mode_id: str
    factory: str          # "package.module:Callable"

    @property
    def title(self) -> str:
        return studio_mode_name(self.mode_id)


_ENTRIES: dict[str, StudioEntry] = {}


def register_studio_adapter(mode_id: str, factory: str) -> None:
    if ":" not in factory:
        raise ValueError("Studio adapter factory must be 'module:Callable'")
    _ENTRIES[mode_id] = StudioEntry(mode_id, factory)


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
register_studio_adapter("waveform_ribbon", "ui.studio.waveform_adapter:WaveformStudioAdapter")
register_studio_adapter("extruded_bubble", "ui.studio.extruded_bubble_adapter:ExtrudedBubbleStudioAdapter")
register_studio_adapter("bubble", "ui.studio.bubble_adapter:BubbleStudioAdapter")
register_studio_adapter("sphere", "ui.studio.sphere_adapter:SphereStudioAdapter")
register_studio_adapter("spectrum", "ui.studio.spectrum_adapter:SpectrumStudioAdapter")
register_studio_adapter("extruded_spectrum",
                        "ui.studio.extruded_spectrum_adapter:ExtrudedSpectrumStudioAdapter")
register_studio_adapter("shockwave_grid", "ui.studio.shockwave_grid_adapter:NeonLakeStudioAdapter")
register_studio_adapter("devcurve", "ui.studio.devcurve_adapter:DevCurveStudioAdapter")
register_studio_adapter("oscilloscope", "ui.studio.oscilloscope_adapter:OscilloscopeStudioAdapter")


__all__ = ["StudioEntry", "create_adapter", "has_studio", "register_studio_adapter", "studio_mode_name",
           "studio_modes", "studio_title", "unregister_studio_adapter"]
