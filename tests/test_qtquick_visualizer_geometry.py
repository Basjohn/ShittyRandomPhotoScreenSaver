"""Phase-D3/D4 canonical Quick visualizer geometry regressions."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    VisualizerClipPolicy,
    VisualizerModePresentationPolicy,
    VisualizerShellPolicy,
    get_visualizer_presentation_policy,
)
from widgets.spotify_visualizer.presentation_geometry import (
    CANONICAL_VISUALIZER_BASELINE_ASPECT_RATIO,
    CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
    resize_visualizer_presentation,
    resize_visualizer_presentation_uniformly,
    resolve_visualizer_presentation,
)


def test_canonical_baseline_is_the_healthy_committed_custom_size() -> None:
    assert CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE == (420.0, 280.0)
    assert CANONICAL_VISUALIZER_BASELINE_ASPECT_RATIO == 1.5


def test_every_current_mode_resolves_the_same_baseline_geometry() -> None:
    presentations = tuple(
        resolve_visualizer_presentation(
            policy=get_visualizer_presentation_policy(mode_id),
            display_size=(1920.0, 1080.0),
            outer_origin=(120.0, 90.0),
        )
        for mode_id in VISUALIZER_MODE_IDS
    )

    assert len(presentations) == 5
    assert {state.outer_rect for state in presentations} == {
        (120.0, 90.0, 420.0, 280.0)
    }
    assert {state.baseline_aspect_ratio for state in presentations} == {1.5}
    assert {state.viewport_extent for state in presentations} == {(420.0, 280.0)}


def test_uniform_scale_changes_shell_and_viewport_coherently() -> None:
    state = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("spectrum"),
        display_size=(1920.0, 1080.0),
        outer_origin=(40.0, 60.0),
        uniform_visual_scale=1.5,
        border_width=4.0,
        corner_radius=8.0,
        content_inset=2.0,
        shadow_blur=18.0,
        shadow_offset=(2.0, 4.0),
    )

    assert state.outer_rect == (40.0, 60.0, 630.0, 420.0)
    assert state.uniform_visual_scale == 1.5
    assert state.current_aspect_ratio == 1.5
    assert state.border_width == 5.0
    assert state.content_rect == (48.0, 68.0, 614.0, 404.0)
    assert state.shell_style["corner_radius"] == 12.0
    assert state.shell_style["inner_corner_radius"] == 4.0
    assert state.shell_style["content_inset"] == 3.0
    assert state.shell_style["shadow_blur"] == 27.0
    assert state.shell_style["shadow_offset"] == (3.0, 6.0)


@pytest.mark.parametrize("target_scale", (1.0, 1.5, 2.25))
def test_retained_uniform_resize_preserves_viewport_and_rescales_authored_chrome(
    target_scale,
) -> None:
    baseline = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("spectrum"),
        display_size=(2560.0, 1440.0),
        outer_origin=(40.0, 60.0),
        border_width=4.0,
        corner_radius=8.0,
        content_inset=2.0,
        shadow_blur=18.0,
        shadow_offset=(2.0, 4.0),
    )

    resized = resize_visualizer_presentation_uniformly(
        baseline,
        display_size=(2560.0, 1440.0),
        outer_origin=(120.0, 90.0),
        relative_scale=target_scale,
    )

    assert resized.uniform_visual_scale == pytest.approx(target_scale)
    assert resized.viewport_extent == baseline.viewport_extent
    assert resized.outer_rect == pytest.approx(
        (120.0, 90.0, 420.0 * target_scale, 280.0 * target_scale)
    )
    assert resized.border_width == pytest.approx(
        max(1.0, 4.0 + max(-1.0, min(1.0, (target_scale - 1.0) * 2.0)))
    )
    assert resized.shell_style["shadow_blur"] == pytest.approx(
        18.0 * target_scale
    )


@pytest.mark.parametrize(
    ("extent", "expected_aspect"),
    (
        ((630.0, 280.0), 2.25),
        ((420.0, 420.0), 1.0),
        ((420.0, 217.0), 420.0 / 217.0),
    ),
)
def test_edge_reproject_changes_extent_only_without_touching_uniform_scale(
    extent,
    expected_aspect,
) -> None:
    baseline = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("spectrum"),
        display_size=(2560.0, 1440.0),
        outer_origin=(40.0, 60.0),
        uniform_visual_scale=1.5,
        border_width=4.0,
        corner_radius=8.0,
        content_inset=2.0,
        shadow_blur=18.0,
        shadow_offset=(2.0, 4.0),
    )

    reprojected = resize_visualizer_presentation(
        baseline,
        display_size=(2560.0, 1440.0),
        outer_origin=(120.0, 90.0),
        relative_scale=1.0,
        viewport_extent=extent,
    )

    # Uniform scale is untouched by an extent-only operation.
    assert reprojected.uniform_visual_scale == pytest.approx(1.5)
    assert reprojected.viewport_extent == extent
    assert reprojected.current_aspect_ratio == pytest.approx(expected_aspect)
    # Outer pixels are extent * scale on both axes independently: no X/Y stretch
    # of finished pixels, the outer rect simply reflects the new world.
    assert reprojected.outer_rect == pytest.approx(
        (120.0, 90.0, extent[0] * 1.5, extent[1] * 1.5)
    )
    # Baseline identity survives an arbitrary custom extent.
    assert reprojected.baseline_viewport_size == (420.0, 280.0)
    assert reprojected.baseline_aspect_ratio == 1.5
    # Authored chrome remains scaled by uniform scale only, never by aspect.
    assert reprojected.border_width == pytest.approx(5.0)
    assert reprojected.shell_style["shadow_blur"] == pytest.approx(18.0 * 1.5)


def test_edge_and_uniform_reproject_compose_independently() -> None:
    baseline = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("bubble"),
        display_size=(3840.0, 2160.0),
        outer_origin=(100.0, 100.0),
    )

    # A wide extent plus a 2x uniform scale compose to extent * scale with no
    # cross-contamination between the two operations.
    reprojected = resize_visualizer_presentation(
        baseline,
        display_size=(3840.0, 2160.0),
        outer_origin=(100.0, 100.0),
        relative_scale=2.0,
        viewport_extent=(560.0, 280.0),
    )

    assert reprojected.uniform_visual_scale == pytest.approx(2.0)
    assert reprojected.viewport_extent == (560.0, 280.0)
    assert reprojected.current_aspect_ratio == pytest.approx(2.0)
    assert reprojected.outer_rect == pytest.approx(
        (100.0, 100.0, 560.0 * 2.0, 280.0 * 2.0)
    )


def test_uniform_reproject_preserves_a_previously_committed_custom_extent() -> None:
    # Corner/wheel resize must never reset a previously committed non-baseline
    # viewport extent back to the 1.5 baseline aspect.
    tall_baseline = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("oscilloscope"),
        display_size=(2560.0, 1440.0),
        outer_origin=(80.0, 80.0),
        viewport_extent=(420.0, 560.0),
    )

    resized = resize_visualizer_presentation_uniformly(
        tall_baseline,
        display_size=(2560.0, 1440.0),
        outer_origin=(80.0, 80.0),
        relative_scale=1.5,
    )

    assert resized.viewport_extent == (420.0, 560.0)
    assert resized.current_aspect_ratio == pytest.approx(420.0 / 560.0)
    assert resized.uniform_visual_scale == pytest.approx(1.5)
    assert resized.outer_rect == pytest.approx(
        (80.0, 80.0, 420.0 * 1.5, 560.0 * 1.5)
    )


def test_repeated_screen_fit_and_reproject_never_compound_visualizer_border_thinness() -> None:
    policy = get_visualizer_presentation_policy("bubble")
    state = resolve_visualizer_presentation(
        policy=policy,
        display_size=(300.0, 200.0),
        outer_origin=(0.0, 0.0),
        border_width=4.0,
    )

    # Small-display screen fit may reduce the card but the visible frame stays
    # comfortably above the authored-minus-one floor.
    assert state.uniform_visual_scale == pytest.approx(5.0 / 7.0)
    assert state.border_width >= 3.0
    assert state.shell_style["authored_border_width"] == pytest.approx(4.0)

    # Reproject the already-fitted presentation repeatedly, including onto a
    # larger display. Border authority comes from the retained authored scalar,
    # not from reverse-scaling the previously clamped visible result.
    for display, factor in (
        ((300.0, 200.0), 0.8),
        ((2560.0, 1440.0), 1.0),
        ((2560.0, 1440.0), 1.6),
        ((300.0, 200.0), 1.0),
    ):
        state = resize_visualizer_presentation_uniformly(
            state,
            display_size=display,
            outer_origin=(0.0, 0.0),
            relative_scale=factor,
        )
        assert state.border_width >= 3.0
        assert state.shell_style["authored_border_width"] == pytest.approx(4.0)


def test_screen_fit_reduces_uniformly_and_clamps_display_local_origin() -> None:
    state = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("bubble"),
        display_size=(300.0, 200.0),
        outer_origin=(250.0, 180.0),
    )

    assert state.uniform_visual_scale == pytest.approx(5.0 / 7.0)
    assert state.outer_rect == pytest.approx((0.0, 0.0, 300.0, 200.0))
    assert state.outer_rect[2] / state.outer_rect[3] == pytest.approx(1.5)


@pytest.mark.parametrize(
    ("extent", "expected_aspect"),
    (
        ((630.0, 280.0), 2.25),
        ((420.0, 420.0), 1.0),
        ((420.0, 217.0), 420.0 / 217.0),
    ),
)
def test_viewport_extent_can_be_wide_tall_or_restored_custom_without_mutating_baseline(
    extent,
    expected_aspect,
) -> None:
    state = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy("devcurve"),
        display_size=(1920.0, 1080.0),
        outer_origin=(207.0, 310.0),
        viewport_extent=extent,
    )

    assert state.outer_rect == (207.0, 310.0, extent[0], extent[1])
    assert state.viewport_extent == extent
    assert state.current_aspect_ratio == pytest.approx(expected_aspect)
    assert state.baseline_viewport_size == (420.0, 280.0)
    assert state.baseline_aspect_ratio == 1.5


def test_frameless_policy_keeps_same_root_geometry_without_card_dependencies() -> None:
    state = resolve_visualizer_presentation(
        policy=VisualizerModePresentationPolicy(
            shell_policy=VisualizerShellPolicy.FRAMELESS,
            clip_policy=VisualizerClipPolicy.VIEWPORT_RECT,
            viewport_resize_capable=True,
        ),
        display_size=(1000.0, 700.0),
        outer_origin=(20.0, 30.0),
        border_width=9.0,
        corner_radius=24.0,
        content_inset=6.0,
        shadow_enabled=True,
    )

    assert state.content_rect == state.outer_rect
    assert state.border_width == 0.0
    assert state.shell_style["corner_radius"] == 0.0
    assert state.shell_style["inner_corner_radius"] == 0.0
    assert state.shell_style["shadow_enabled"] is False
    assert state.shell_style["shadow_blur"] == 0.0


def test_quick_geometry_has_no_legacy_growth_or_qt_authority() -> None:
    import widgets.spotify_visualizer.presentation_geometry as geometry

    source = inspect.getsource(geometry)
    tree = ast.parse(source)
    imports = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    for forbidden in (
        "DEFAULT_GROWTH",
        "spectrum_growth",
        "osc_growth",
        "sine_wave_growth",
        "bubble_growth",
        "devcurve_growth",
    ):
        assert forbidden not in source
    assert not any(name.startswith("PySide6") for name in imports)
    assert "widgets.spotify_visualizer.card_geometry" not in imports
    assert "growth" not in inspect.signature(
        geometry.resolve_visualizer_presentation
    ).parameters


def test_visualizer_card_shadow_extensions_scale_with_committed_presentation() -> None:
    state = resolve_visualizer_presentation(
        policy=VisualizerModePresentationPolicy(
            shell_policy=VisualizerShellPolicy.CARD,
            clip_policy=VisualizerClipPolicy.VIEWPORT_RECT,
            viewport_resize_capable=True,
        ),
        display_size=(1920.0, 1080.0),
        uniform_visual_scale=1.5,
        shadow_offset=(4.0, 4.0),
        shadow_extensions=(0.0, 0.0, 6.0, 6.0),
    )
    assert state.shell_style["shadow_offset"] == pytest.approx((6.0, 6.0))
    assert state.shell_style["shadow_extensions"] == pytest.approx((0.0, 0.0, 9.0, 9.0))


def test_visualizer_shadow_projection_is_owner_time_and_cached() -> None:
    root = Path(__file__).resolve().parents[1]
    display_manager = (root / "engine" / "display_manager.py").read_text(encoding="utf-8")
    owner = (root / "widgets" / "spotify_visualizer" / "quick_display_visualizer_owner.py").read_text(encoding="utf-8")
    qml = (root / "rendering" / "quick" / "qml" / "VisualizerPresentation.qml").read_text(encoding="utf-8")

    assert "card_shadow_kwargs = {" in display_manager
    assert "resolve_directional_extensions(direction, frame_extra)" in display_manager
    assert "card_shadow_kwargs=card_shadow_kwargs" in display_manager
    assert "self._card_shadow_kwargs = dict(card_shadow_kwargs or {})" in owner
    assert "**self._card_shadow_kwargs" in owner

    # Global settings are projected when the display owner is built/rebuilt;
    # the Visualizer tick/render path must not poll Settings for shadow style.
    resolver_body = owner.split("def _resolve_current_presentation", 1)[1].split("def _apply_resolved_presentation", 1)[0]
    assert "SettingsManager" not in resolver_body
    assert "settings.get(" not in resolver_body
    assert "cached: true" in qml
    assert "cardShadowExtendLeft" in qml and "cardShadowExtendBottom" in qml
    # Card shadows never use RectangularShadow translation: signed base
    # direction plus Extra Offset are folded into asymmetric surface geometry.
    assert "cardShadowBaseLeft" in qml and "cardShadowBaseBottom" in qml
    assert "offset: Qt.vector2d(0.0, 0.0)" in qml
