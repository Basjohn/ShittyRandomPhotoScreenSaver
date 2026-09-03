"""Phase-D fade-authority guard.

There is exactly ONE authored temporal fade authority for the whole visualizer
presentation (the single animation/progress owned by ``presentation_fade``).
``ResolvedVisualizerPresentation`` exposes two DERIVED per-layer values of that
one authority:

    scene_fade   -> presentation-root authoredSceneOpacity
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


def test_scene_root_opacity_derives_from_scene_fade_without_owning_startup_gate():
    source = (
        ROOT / "rendering" / "quick" / "scene_controller.py"
    ).read_text(encoding="utf-8")
    qml = (
        ROOT / "rendering" / "quick" / "qml" / "VisualizerPresentation.qml"
    ).read_text(encoding="utf-8")
    assert 'setProperty("authoredSceneOpacity", presentation.scene_fade)' in source, (
        "the presentation root authored opacity must derive from scene_fade"
    )
    assert "opacity: authoredSceneOpacity * startupRevealOpacity" in qml
    assert "QVariantAnimation" not in qml


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


def test_render_node_folds_inherited_opacity_into_content_fade():
    """The GL content must fade with the QML root, not ignore its opacity.

    The visualizer render node draws raw GL, so the scene graph cannot apply the
    inherited item opacity (authored scene fade x generation startup-reveal gate)
    for it. Before this was folded into ``content_fade``, the GL bars rendered at
    full opacity through the coordinated startup reveal and popped in while the
    card faded. This guards that the fold stays in place.
    """

    source = (
        ROOT / "rendering" / "quick" / "visualizer" / "node.py"
    ).read_text(encoding="utf-8")
    assert "inheritedOpacity" in source, (
        "the visualizer render node must read the QML root's inherited opacity"
    )
    assert "content_fade" in source and "inherited" in source.lower(), (
        "inherited opacity must be folded into the authored content fade so the "
        "coordinated startup reveal fades the GL content, not just the card"
    )


def test_owner_scene_fade_eases_from_zero_on_activation():
    """The Quick owner eases ``scene_fade`` 0 -> 1 once per activation.

    This is the visualizer's own authored first-appearance fade in the Qt Quick
    path: it must start hidden the moment it is armed and land exactly on full
    opacity, so a heavy first frame that arrives outside the coordinated reveal
    window never snaps the whole scene in. Before arming it must be fully opaque
    so no pre-start metrics resolve can hide the scene.
    """

    from dataclasses import dataclass, replace as _replace  # noqa: F401

    from widgets.spotify_visualizer.quick_display_visualizer_owner import (
        QuickDisplayVisualizerOwner,
        _ACTIVATION_SCENE_FADE_DURATION_S,
    )

    @dataclass(frozen=True)
    class _StubPresentation:
        scene_fade: float = 1.0
        content_fade: float = 1.0

    clock = {"now": 100.0}
    owner = object.__new__(QuickDisplayVisualizerOwner)
    owner._presentation_resolver = lambda: _StubPresentation()
    owner._mode_transition_fade = 1.0
    owner._activation_fade_started_at = None
    owner._transition_clock = lambda: clock["now"]

    # Not yet armed -> fully opaque (never hidden by the fade before start).
    assert owner._resolve_current_presentation().scene_fade == 1.0

    # Armed -> starts hidden, eases up, lands exactly on 1.0 and stays there.
    owner._activation_fade_started_at = 100.0
    assert owner._resolve_current_presentation().scene_fade == 0.0
    clock["now"] = 100.0 + _ACTIVATION_SCENE_FADE_DURATION_S / 2.0
    midway = owner._resolve_current_presentation().scene_fade
    assert 0.0 < midway < 1.0
    clock["now"] = 100.0 + _ACTIVATION_SCENE_FADE_DURATION_S + 5.0
    assert owner._resolve_current_presentation().scene_fade == 1.0
    # content_fade stays the mode-transition layer, untouched by the scene fade.
    assert owner._resolve_current_presentation().content_fade == 1.0
