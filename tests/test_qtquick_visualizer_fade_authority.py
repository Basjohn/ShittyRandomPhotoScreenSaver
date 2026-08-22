"""Phase-D fade-authority guard.

There is exactly ONE authored temporal fade authority for the whole visualizer
presentation (the single animation/progress owned by ``presentation_fade``).
``ResolvedVisualizerPresentation`` exposes two DERIVED per-layer values of that
one authority:

    scene_fade   -> presentation-root / card opacity (root.setOpacity)
    content_fade -> GL content opacity fed to shader ``u_fade`` (the Quick-era
                    successor of the authored bars-stagger fade)

These bars must fail if any Quick visualizer renderer diverts ``u_fade`` away
from the shared ``content_fade`` contract, if the scene root stops deriving its
opacity from ``scene_fade``, or if any Quick visualizer render-path module
introduces a second fade clock (its own animation/timer) for content.
"""

from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
_RENDERERS = ROOT / "rendering" / "quick" / "visualizer" / "implementations"
_MODE_FILES = {
    "spectrum": _RENDERERS / "spectrum.py",
    "oscilloscope": _RENDERERS / "oscilloscope.py",
    "sine_wave": _RENDERERS / "sine_wave.py",
    "bubble": _RENDERERS / "bubble.py",
    "devcurve": _RENDERERS / "devcurve.py",
}


@pytest.mark.parametrize("mode_id", sorted(_MODE_FILES))
def test_each_mode_renderer_feeds_u_fade_from_the_shared_content_fade(mode_id):
    source = _MODE_FILES[mode_id].read_text(encoding="utf-8")
    # u_fade must be present and fed only from the single presentation contract
    # value, never a per-renderer constant or a separately animated scalar.
    assert '"u_fade"' in source, f"{mode_id} renderer no longer sets u_fade"
    assert "presentation.content_fade" in source, (
        f"{mode_id} renderer must feed u_fade from presentation.content_fade"
    )
    # No renderer may own a fade clock.
    for banned in ("QVariantAnimation", "QPropertyAnimation", "QTimer"):
        assert banned not in source, (
            f"{mode_id} renderer must not own a fade clock ({banned})"
        )


def test_scene_root_opacity_derives_from_scene_fade():
    source = (
        ROOT / "rendering" / "quick" / "scene_controller.py"
    ).read_text(encoding="utf-8")
    assert "setOpacity(presentation.scene_fade)" in source, (
        "the presentation root opacity must derive from scene_fade"
    )


def test_no_quick_visualizer_render_module_owns_a_second_fade_clock():
    render_dir = ROOT / "rendering" / "quick" / "visualizer"
    offenders: list[str] = []
    for path in render_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for banned in ("QVariantAnimation", "QPropertyAnimation"):
            if banned in text:
                offenders.append(f"{path.relative_to(ROOT)}::{banned}")
    assert not offenders, (
        "Quick visualizer render path must not introduce a second fade "
        f"animation/clock: {offenders}"
    )


def test_presentation_fade_remains_the_single_derivation_authority():
    source = (
        ROOT / "widgets" / "spotify_visualizer" / "presentation_fade.py"
    ).read_text(encoding="utf-8")
    # The bars/content layer is a pure function of the one progress, not a second
    # animation.
    assert "def bars_fade_from_progress(" in source
    assert "one animation, one progress scalar" in source.lower() or (
        "one animation" in source.lower()
    )
