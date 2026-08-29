"""Legacy widget delegation for controller-owned presentation state (H).

While ``SpotifyVisualizerWidget`` remains the pre-cutover production presenter,
its pure renderer/presentation-only config fields are owned by the controller's
``VisualizerPresentationState``. This mixin makes each such widget field a
delegating property to ``self._runtime_controller.presentation_state`` so the
existing widget setup, the legacy compositor overlay and the widget-free Quick
capture all read one storage.

This is an explicit, enumerated delegation - not a generic ``__getattr__`` facade.
Only pure renderer/render-styling values are here; authored logical inputs stay in
``VisualizerLogicalTickState`` (see ``logical_tick_state_adapter``). When the atomic
production cutover deletes the legacy widget, this mixin is deleted with it and only
the controller-owned presentation state remains.
"""

from __future__ import annotations

from typing import Any


# Pure renderer/presentation-only fields consumed by the legacy adapter's extras
# builders (config_applier._populate_shared_visualizer_extras /
# _append_line_mode_visual_extras / _append_bubble_visual_extras / _common_style).
# Authored logical inputs are deliberately absent - they belong to
# LOCAL_LOGICAL_TICK_FIELDS.
LOCAL_PRESENTATION_FIELDS: tuple[str, ...] = (
    # Shared / cross-mode styling.
    "_rainbow_enabled",
    "_rainbow_speed",
    "_rainbow_per_bar",
    "_spectrum_rainbow_border",
    "_spectrum_glow_enabled",
    "_spectrum_glow_intensity",
    "_spectrum_glow_color",
    "_spectrum_ghost_alpha",
    "_spectrum_border_radius",
    "_bar_fill_color",
    "_bar_border_color",
    "_ghosting_enabled",
    "_ghost_alpha",
    "_ghost_decay_rate",
    "_sine_density",
    "_sine_displacement",
    # Oscilloscope styling.
    "_osc_glow_enabled",
    "_osc_glow_intensity",
    "_osc_glow_size",
    "_osc_glow_reactivity",
    "_osc_glow_color",
    "_osc_reactive_glow",
    "_osc_smoothing",
    "_osc_line_dim",
    "_osc_line_offset_bias",
    "_osc_vertical_shift",
    "_osc_line_color",
    "_osc_line_count",
    "_osc_line2_color",
    "_osc_line3_color",
    "_osc_line4_color",
    "_osc_line5_color",
    "_osc_line6_color",
    "_osc_line2_glow_color",
    "_osc_line3_glow_color",
    "_osc_line4_glow_color",
    "_osc_line5_glow_color",
    "_osc_line6_glow_color",
    "_osc_ghost_line2_enabled",
    "_osc_ghost_line3_enabled",
    "_osc_ghost_line4_enabled",
    "_osc_ghost_line5_enabled",
    "_osc_ghost_line6_enabled",
    # Sine styling.
    "_sine_glow_enabled",
    "_sine_glow_intensity",
    "_sine_glow_size",
    "_sine_glow_reactivity",
    "_sine_glow_color",
    "_sine_reactive_glow",
    "_sine_smoothing",
    "_sine_line_dim",
    "_sine_line_offset_bias",
    "_sine_vertical_shift",
    "_sine_card_adaptation",
    "_sine_wave_effect",
    "_sine_micro_wobble",
    "_sine_crawl_amount",
    "_sine_line_color",
    "_sine_line2_color",
    "_sine_line3_color",
    "_sine_line4_color",
    "_sine_line5_color",
    "_sine_line6_color",
    "_sine_line2_glow_color",
    "_sine_line3_glow_color",
    "_sine_line4_glow_color",
    "_sine_line5_glow_color",
    "_sine_line6_glow_color",
    "_sine_ghost_line2_enabled",
    "_sine_ghost_line3_enabled",
    "_sine_ghost_line4_enabled",
    "_sine_ghost_line5_enabled",
    "_sine_ghost_line6_enabled",
    # Bubble renderer styling (simulation controls stay logical).
    "_bubble_outline_color",
    "_bubble_specular_color",
    "_bubble_gradient_light",
    "_bubble_gradient_dark",
    "_bubble_pop_color",
    "_bubble_specular_direction",
    "_bubble_gradient_direction",
    "_bubble_tail_opacity",
    "_bubble_ghosting_enabled",
    "_bubble_ghost_alpha",
    "_bubble_ghost_decay",
)


def _make_delegated_property(field_name: str) -> property:
    def getter(self: Any) -> Any:
        return getattr(self._runtime_controller.presentation_state, field_name)

    def setter(self: Any, value: Any) -> None:
        setattr(self._runtime_controller.presentation_state, field_name, value)

    getter.__name__ = field_name
    setter.__name__ = field_name
    return property(getter, setter)


class LegacyVisualizerPresentationStateAdapterMixin:
    """Named delegating properties for controller-owned presentation fields."""


for _field in LOCAL_PRESENTATION_FIELDS:
    setattr(
        LegacyVisualizerPresentationStateAdapterMixin,
        _field,
        _make_delegated_property(_field),
    )


__all__ = [
    "LegacyVisualizerPresentationStateAdapterMixin",
    "LOCAL_PRESENTATION_FIELDS",
]
