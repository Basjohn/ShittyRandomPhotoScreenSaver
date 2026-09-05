from __future__ import annotations

import pathlib
import sys
import types

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def _install_inert_package(name: str, path: pathlib.Path) -> None:
    package = types.ModuleType(name)
    package.__path__ = [str(path)]
    sys.modules[name] = package


# Keep this source-only contract runnable in audit containers without PySide6.
# The real runtime imports the same modules through the normal package graph.
#
# The inert-package stubs MUST be installed only for the duration of this
# module's own imports and then removed: a leaked inert ``core.settings`` (a
# fileless module object) stays in the shared ``sys.modules`` for the rest of the
# collection and breaks every later ``from core.settings import SettingsManager``
# with "cannot import name 'SettingsManager' from 'core.settings' (unknown
# location)". The already-bound symbols below keep working after restoration.
_STUBBED_PACKAGES = ("core.settings", "widgets.spotify_visualizer")
_saved_modules = {name: sys.modules.get(name) for name in _STUBBED_PACKAGES}

_install_inert_package("core.settings", ROOT / "core" / "settings")
_install_inert_package(
    "widgets.spotify_visualizer",
    ROOT / "widgets" / "spotify_visualizer",
)

try:
    from widgets.spotify_visualizer.spectrum_frame_runtime import SpectrumFrameRuntime
    from widgets.spotify_visualizer.spectrum_solid_hysteresis import (
        canonical_spectrum_solid_hysteresis_segments,
        compute_spectrum_height_scale,
        spectrum_bar_to_boosted,
    )
    from widgets.spotify_visualizer.spectrum_temporal_contract import (
        spectrum_vertical_temporal_ratio,
        spectrum_visual_alpha,
    )
finally:
    for _name, _original in _saved_modules.items():
        if _original is None:
            sys.modules.pop(_name, None)
        else:
            sys.modules[_name] = _original


def _resolve(
    runtime: SpectrumFrameRuntime,
    *,
    timestamp: float,
    value: float,
    viewport_height: float,
    first_frame: bool = False,
    single_piece: bool = False,
    smoothing_enabled: bool = True,
) -> float:
    dynamic_segments = max(8, min(64, int(max(0.0, viewport_height - 12.0) // 5.0)))
    result = runtime.resolve(
        [value],
        bar_count=1,
        now_ts=timestamp,
        runtime_generation=1,
        engine_generation=1,
        activation_id=1,
        source_generation=1,
        source_activation_id=1,
        playing=True,
        first_frame=first_frame,
        smoothing_enabled=smoothing_enabled,
        smoothing_strength=0.5,
        single_piece=single_piece,
        segments=dynamic_segments,
        viewport_height=viewport_height,
        ghosting_enabled=False,
        ghost_decay=0.4,
        animation_enabled=False,
    )
    assert result is not None
    return float(result.bars[0])


def test_vertical_temporal_ratio_is_canonical_exact_and_tall_only() -> None:
    assert spectrum_vertical_temporal_ratio(280.0) == pytest.approx(1.0)
    assert spectrum_vertical_temporal_ratio(140.0) == pytest.approx(1.0)
    assert spectrum_vertical_temporal_ratio(560.0) == pytest.approx(548.0 / 268.0)
    assert spectrum_vertical_temporal_ratio(816.0) == pytest.approx(3.0)
    assert spectrum_vertical_temporal_ratio(5000.0) == pytest.approx(4.0)

    # Width has no parameter and no authority in the temporal contract.  A
    # canonical-height wide viewport therefore keeps the canonical alpha.
    canonical_alpha = spectrum_visual_alpha(1.0 / 90.0, 0.5, viewport_height=280.0)
    wide_alpha = spectrum_visual_alpha(1.0 / 90.0, 0.5, viewport_height=280.0)
    assert wide_alpha == pytest.approx(canonical_alpha, abs=0.0)



def test_retired_compatibility_smoothing_helper_is_absent_after_r77() -> None:
    # R-76 moved viewport treatment to the live Quick frame runtime. R-77 then
    # retired the old QWidget/present-loop helper entirely, so it must not return
    # as a second smoothing owner.
    helper = ROOT / "widgets" / "spotify_visualizer" / "spectrum_presentation_smoothing.py"
    assert not helper.exists()


def test_tall_smoothing_reduces_pixel_jump_growth_without_flattening_reaction() -> None:
    dt = 1.0 / 90.0
    prior = 0.30
    target = 0.70

    def visible_step(viewport_height: float) -> float:
        alpha = spectrum_visual_alpha(dt, 0.5, viewport_height=viewport_height)
        resolved = prior + (target - prior) * alpha
        height_scale = compute_spectrum_height_scale(viewport_height)
        span = viewport_height - 12.0
        return (
            spectrum_bar_to_boosted(resolved, height_scale=height_scale)
            - spectrum_bar_to_boosted(prior, height_scale=height_scale)
        ) * span

    canonical = visible_step(280.0)
    tall_2x = visible_step(560.0)
    tall_3x = visible_step(816.0)

    # Without viewport-temporal treatment these would grow roughly 2x/3x.
    # The conservative time-constant scaling keeps them much closer while still
    # allowing larger tall-card travel rather than globally compressing response.
    assert canonical > 0.0
    assert canonical < tall_2x < canonical * 1.40
    assert tall_2x < tall_3x < canonical * 1.55


def test_frame_runtime_preserves_canonical_response_and_smooths_only_tall_extent() -> None:
    dt = 1.0 / 90.0

    canonical = SpectrumFrameRuntime()
    wide_same_height = SpectrumFrameRuntime()
    tall = SpectrumFrameRuntime()

    for runtime, height in (
        (canonical, 280.0),
        (wide_same_height, 280.0),
        (tall, 560.0),
    ):
        _resolve(
            runtime,
            timestamp=1.0,
            value=0.0,
            viewport_height=height,
            first_frame=True,
        )

    canonical_rise = _resolve(
        canonical,
        timestamp=1.0 + dt,
        value=1.0,
        viewport_height=280.0,
    )
    wide_rise = _resolve(
        wide_same_height,
        timestamp=1.0 + dt,
        value=1.0,
        viewport_height=280.0,
    )
    tall_rise = _resolve(
        tall,
        timestamp=1.0 + dt,
        value=1.0,
        viewport_height=560.0,
    )

    assert canonical_rise == pytest.approx(0.7506477912227038)
    assert wide_rise == pytest.approx(canonical_rise, abs=0.0)
    assert 0.48 < tall_rise < 0.51
    assert tall_rise < canonical_rise


def test_solid_hysteresis_domain_does_not_retune_when_viewport_becomes_tall() -> None:
    # The old dynamic domain used ~53 helper segments at canonical height and 64
    # at tall height.  A 0.300 -> 0.329 source step is deliberately near the
    # normal/fast threshold: 53 segments classify it normal, 64 classify it fast.
    # The continuous solid renderer has no actual segment topology, so viewport
    # height must not change that authored temporal branch.
    assert canonical_spectrum_solid_hysteresis_segments() == 53

    canonical = SpectrumFrameRuntime()
    tall = SpectrumFrameRuntime()
    for runtime, height in ((canonical, 280.0), (tall, 560.0)):
        _resolve(
            runtime,
            timestamp=2.0,
            value=0.300,
            viewport_height=height,
            first_frame=True,
            single_piece=True,
            smoothing_enabled=False,
        )

    canonical_next = _resolve(
        canonical,
        timestamp=2.0 + 1.0 / 90.0,
        value=0.329,
        viewport_height=280.0,
        single_piece=True,
        smoothing_enabled=False,
    )
    tall_next = _resolve(
        tall,
        timestamp=2.0 + 1.0 / 90.0,
        value=0.329,
        viewport_height=560.0,
        single_piece=True,
        smoothing_enabled=False,
    )

    # Both heights use the same canonical temporal segment domain.  Height still
    # changes renderer geometry later; it no longer changes hysteresis semantics.
    assert tall_next == pytest.approx(canonical_next, abs=1e-12)


def test_live_runtime_source_has_no_width_based_smoothing_or_dynamic_solid_domain() -> None:
    runtime_source = (
        ROOT / "widgets" / "spotify_visualizer" / "spectrum_frame_runtime.py"
    ).read_text(encoding="utf-8")
    temporal_source = (
        ROOT / "widgets" / "spotify_visualizer" / "spectrum_temporal_contract.py"
    ).read_text(encoding="utf-8")

    assert "viewport_width" not in temporal_source
    assert "max(width / baseline_width, height / baseline_height)" not in temporal_source
    assert "spectrum_visual_alpha(" in runtime_source
    assert "canonical_spectrum_solid_hysteresis_segments()" in runtime_source
