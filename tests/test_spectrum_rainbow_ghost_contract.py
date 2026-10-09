"""Spectrum and Extruded independently own rainbow peak styling.

No curated visualizer preset can be a fixed oracle for these capabilities.
"""
from dataclasses import asdict


def test_owned_ghost_rainbow_survives_model_save_reload_and_normalization():
    from core.settings.models._spotify_visualizer import SpotifyVisualizerSettings
    from core.settings.visualizer_settings_snapshot import normalize_visualizer_mode_payload

    for spectrum, extruded in ((True, False), (False, True)):
        model = SpotifyVisualizerSettings.from_mapping({
            "spectrum_rainbow_ghost": spectrum,
            "extruded_spectrum_rainbow_ghost": extruded,
        }, apply_preset_overlay=False)
        persisted = model.to_dict()
        restored = SpotifyVisualizerSettings.from_mapping(persisted, apply_preset_overlay=False)
        assert asdict(restored)["spectrum_rainbow_ghost"] is spectrum
        assert asdict(restored)["extruded_spectrum_rainbow_ghost"] is extruded
        assert normalize_visualizer_mode_payload(
            "spectrum", {"mode": "spectrum", "spectrum_rainbow_ghost": spectrum}
        )["spectrum_rainbow_ghost"] is spectrum
        assert normalize_visualizer_mode_payload(
            "extruded_spectrum", {"mode": "extruded_spectrum", "extruded_spectrum_rainbow_ghost": extruded}
        )["extruded_spectrum_rainbow_ghost"] is extruded


def test_ghost_rainbow_presentation_uses_single_existing_spectrum_runtime():
    from pathlib import Path
    root = Path(__file__).parents[1]
    cap = (root / "widgets/spotify_visualizer/logical_frame_capture.py").read_text()
    assert 'or (extra["spectrum_rainbow_ghost"] and extra["spectrum_ghosting_enabled"])' in cap
    assert 'parameters["extruded_spectrum_rainbow_ghost"]' in cap
    two_d = (root / "rendering/quick/visualizer/implementations/spectrum.py").read_text()
    three_d = (root / "rendering/quick/visualizer/implementations/extruded_spectrum.py").read_text()
    assert 'uniforms["u_rainbow_ghost"]' in two_d
    assert 'uniforms["uRainbowGhost"]' in three_d
    source = (root / "rendering/gl_programs/extruded_spectrum_program.py").read_text()
    assert '(uPass == 1 && uRainbowGhost == 1)' in source


def test_spectrum_ghosting_survives_production_mode_source_projection():
    """Exercise the config seam that previously disabled both 2D ghost modes.

    Shader- and model-only checks cannot catch the source-policy projection
    silently overriding an enabled setting with False before logical capture.
    Test-owned values only: curated presets are intentionally not oracles.
    """
    from types import SimpleNamespace

    from widgets.spotify_visualizer.config_applier import apply_logical_vis_mode_kwargs
    from widgets.spotify_visualizer.source_config_applier import resolve_mode_source_config

    for enabled in (False, True):
        for rainbow in (False, True):
            authored = {
                "spectrum_render_mode": "bars",
                "spectrum_ghosting_enabled": enabled,
                "spectrum_ghost_alpha": 0.73,
                "spectrum_ghost_decay": 0.22,
                "spectrum_rainbow_ghost": rainbow,
            }
            resolved = resolve_mode_source_config("spectrum", authored)
            assert resolved["spectrum_ghosting_enabled"] is enabled
            assert resolved["spectrum_ghost_alpha"] == 0.73
            assert resolved["spectrum_ghost_decay"] == 0.22
            assert resolved["spectrum_rainbow_ghost"] is rainbow

            # Production owner applies precisely this projected map to its
            # logical state before the Spectrum frame runtime reads the flag.
            logical = SimpleNamespace()
            apply_logical_vis_mode_kwargs(logical, resolved)
            assert logical._spectrum_ghosting_enabled is enabled
            assert logical._spectrum_ghost_decay == 0.22

    # Separate mode profile: do not accidentally merge Extruded's own settings
    # into Spectrum, or alter its already physically accepted Rainbow Ghost.
    extruded = resolve_mode_source_config("extruded_spectrum", {
        "spectrum_ghosting_enabled": False,
        "extruded_spectrum_ghosting_enabled": True,
        "extruded_spectrum_ghost_alpha": 0.64,
        "extruded_spectrum_ghost_decay": 0.31,
        "extruded_spectrum_rainbow_ghost": True,
    })
    assert extruded["spectrum_ghosting_enabled"] is True
    assert extruded["spectrum_ghost_alpha"] == 0.64
    assert extruded["spectrum_ghost_decay"] == 0.31
    assert extruded["extruded_spectrum_rainbow_ghost"] is True
