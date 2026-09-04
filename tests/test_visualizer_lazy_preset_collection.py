"""V5b hazard 2: preset-index collection is safe under lazy mode bodies.

Under lazy Settings bodies an absent preset slider means the mode was never
constructed, NOT that its preset setting is missing. Writing a fallback index
for an absent slider would silently reset an unbuilt mode's preset on an
unrelated save (R-13 cross-mode loss / R-32 lazy-save hydration). The collector
must contribute no key for an absent slider, so the persisted index stays
authoritative through the save merge.
"""
from __future__ import annotations

from ui.tabs.media.visualizer_mode_binding import collect_visualizer_preset_indices
from core.settings.visualizer_mode_registry import (
    get_preset_key,
    iter_visualizer_mode_descriptors,
)


class _Slider:
    def __init__(self, index: int) -> None:
        self._index = index

    def preset_index(self) -> int:
        return self._index


class _Tab:
    pass


def _tab_with_built_modes(built: dict[str, int]) -> _Tab:
    tab = _Tab()
    for descriptor in iter_visualizer_mode_descriptors():
        if descriptor.mode_id in built:
            setattr(tab, descriptor.preset_slider_attr, _Slider(built[descriptor.mode_id]))
    return tab


def test_absent_sliders_write_no_preset_key():
    # Only Bubble is built; every other mode's body is absent (unbuilt).
    tab = _tab_with_built_modes({"bubble": 1})
    config: dict = {}
    collect_visualizer_preset_indices(tab, config)

    assert config == {get_preset_key("bubble"): 1}
    for mode in ("spectrum", "oscilloscope", "sine_wave", "devcurve"):
        assert get_preset_key(mode) not in config


def test_absent_slider_does_not_overwrite_persisted_index():
    # A save with only Spectrum built must not disturb a persisted Bubble index.
    tab = _tab_with_built_modes({"spectrum": 2})
    persisted = {get_preset_key("bubble"): 3, get_preset_key("spectrum"): 0}

    collect_visualizer_preset_indices(tab, persisted)

    # Spectrum (built) is refreshed from its slider; Bubble (unbuilt) is untouched.
    assert persisted[get_preset_key("spectrum")] == 2
    assert persisted[get_preset_key("bubble")] == 3


def test_built_sliders_write_their_index():
    tab = _tab_with_built_modes({"spectrum": 0, "bubble": 2, "sine_wave": 1})
    config: dict = {}
    collect_visualizer_preset_indices(tab, config)
    assert config == {
        get_preset_key("spectrum"): 0,
        get_preset_key("bubble"): 2,
        get_preset_key("sine_wave"): 1,
    }
