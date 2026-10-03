"""A mode that borrows another mode's profiles (Extruded Spectrum and Shockwave Grid borrow
Spectrum's technical profile, bar colours and frame-runtime source settings) sees the lender as
the lender shows itself: resolved through the lender's own active preset.

Regression (2026-10-03): the runtime activation applied only the active mode's preset, so a
borrower read the lender's raw stored keys or its factory defaults; with Spectrum on a curated
preset the bars of Extruded Spectrum sat pinned at full height. Expected values are derived from
the lender resolving itself, never pinned."""
from __future__ import annotations

import pytest

from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    get_profile_lender_modes,
    get_visualizer_mode_descriptor,
)
from core.settings.visualizer_presets import (
    get_custom_preset_index,
    get_preset_settings,
    resolve_visualizer_activation_payload,
)
from widgets.spotify_visualizer.technical_config import build_technical_cache, resolve_technical_config

_BORROWERS = tuple(mode for mode in VISUALIZER_MODE_IDS if get_profile_lender_modes(mode))


def _runtime_model(config):
    """The production runtime path: activation payload, then the model without a second overlay."""
    activation = resolve_visualizer_activation_payload(config)
    return SpotifyVisualizerSettings.from_mapping(
        activation.resolved_config, apply_preset_overlay=False, resolve_preset_indices=False
    )


def _shown(model, mode, lender):
    technical = resolve_technical_config(build_technical_cache(None, model), mode)
    colours = (model.resolve_bar_fill_color(lender), model.resolve_bar_border_color(lender))
    source = tuple(getattr(model, name) for name in sorted(vars(model)) if name.startswith(f"{lender}_"))
    return technical, colours, source


def _presets(**indices):
    return {f"preset_{mode}": indices.get(mode, 0) for mode in VISUALIZER_MODE_IDS}


def test_the_borrowers_are_the_spectrum_family_and_sphere_keeps_its_raw_profile():
    assert {"extruded_spectrum", "shockwave_grid"} <= set(_BORROWERS)
    assert get_profile_lender_modes("spectrum") == ()
    sphere = get_visualizer_mode_descriptor("sphere")
    assert sphere.technical_profile_mode == "spectrum" and get_profile_lender_modes("sphere") == ()


@pytest.mark.parametrize("mode", _BORROWERS)
def test_a_borrower_sees_the_lender_through_the_lenders_active_preset(mode):
    differing = 0
    for lender in get_profile_lender_modes(mode):
        for index in range(get_custom_preset_index(lender)):
            config = _presets(**{lender: index})
            lender_model = _runtime_model({**config, "mode": lender})
            borrower_model = _runtime_model({**config, "mode": mode})
            assert _shown(borrower_model, mode, lender) == _shown(lender_model, lender, lender), (lender, index)
            # Negative control: the stored-key resolution this replaced differs for a preset that
            # sets the lender's technical profile.
            raw_model = SpotifyVisualizerSettings.from_mapping(
                {**config, "mode": mode}, apply_preset_overlay=False, resolve_preset_indices=False
            )
            if _shown(raw_model, mode, lender)[0] != _shown(lender_model, lender, lender)[0]:
                differing += 1
    if any(key.endswith(("_sensitivity", "_bar_count", "_audio_block_size"))
           for lender in get_profile_lender_modes(mode)
           for index in range(get_custom_preset_index(lender))
           for key in get_preset_settings(lender, index)):
        assert differing, "no curated lender preset distinguishes the fix from the stored keys"


@pytest.mark.parametrize("mode", _BORROWERS)
def test_a_custom_lender_lends_its_stored_values(mode):
    for lender in get_profile_lender_modes(mode):
        custom = get_custom_preset_index(lender)
        config = {**_presets(**{lender: custom}), f"{lender}_bar_count": 21, f"{lender}_sensitivity": 0.61}
        borrower = _runtime_model({**config, "mode": mode})
        technical = resolve_technical_config(build_technical_cache(None, borrower), mode)
        assert technical["bar_count"] == 21 and technical["sensitivity"] == pytest.approx(0.61)


def test_the_settings_model_overlay_agrees_with_the_runtime_activation():
    for mode in _BORROWERS:
        config = {**_presets(), "mode": mode}
        overlaid = SpotifyVisualizerSettings.from_mapping(config)
        assert _shown(overlaid, mode, "spectrum")[0] == _shown(_runtime_model(config), mode, "spectrum")[0]
