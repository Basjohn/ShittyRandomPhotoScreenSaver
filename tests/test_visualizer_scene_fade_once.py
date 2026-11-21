"""The Visualizer's scene fade is applied once, in the content's own fade, on both drawing paths (Current_Plan step 2,
the scene-fade double-rounding box).

The scene fade (the authored scene fade times the startup reveal gate) used to reach the content through Qt's opacity
on the card's presentation root. The Python render node folds Qt's inherited opacity into ``u_fade`` (one rounding);
the native item's surface was faded by Qt's composite after the shader had written it into RGBA8 (two roundings, and
for a shader that mixes with ``u_fade`` another formula). Now the content host carries none of it: the chrome fades in
its own layers, the item is handed the scene opacity, and both paths fold it through
``render_contract.scene_faded_snapshot``.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from tests.test_native_visualizer_route import _Bridge, _identity, route_world  # noqa: F401 (route_world: a fixture)


@dataclass(frozen=True)
class _Snapshot:
    """A stand-in render snapshot (the fold replaces its presentation, as on ``VisualizerRenderSnapshot``)."""

    logical: object
    presentation: object


def _effective_opacity(item) -> float:
    """What Qt multiplies an item's nodes by: its own opacity and every ancestor's."""
    value = 1.0
    while item is not None:
        value *= float(item.opacity())
        item = item.parentItem()
    return value


def test_the_fold_multiplies_the_content_fade_and_leaves_an_unfaded_scene_untouched():
    from rendering.quick.visualizer.render_contract import scene_faded_snapshot
    from tests._visualizer_presentation import resolve_presentation
    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy

    presentation = resolve_presentation(policy=get_visualizer_presentation_policy("devcurve"),
                                        display_size=(1920.0, 1080.0), content_fade=0.5)
    snapshot = _Snapshot(logical=SimpleNamespace(), presentation=presentation)
    assert scene_faded_snapshot(snapshot, 1.0) is snapshot          # nothing allocated at rest
    faded = scene_faded_snapshot(snapshot, 0.25)
    assert faded.presentation.content_fade == presentation.content_fade * 0.25
    assert faded.logical is snapshot.logical
    assert scene_faded_snapshot(snapshot, 0.0).presentation.content_fade == 0.0


def test_the_render_node_folds_the_items_scene_opacity_with_what_qt_still_inherits():
    from rendering.quick.visualizer.node import VisualizerRenderNode

    node = VisualizerRenderNode()
    node.inheritedOpacity = lambda: 0.8                             # an opacity Qt applies above the card
    node.synchronize(identity=None, snapshot=None, presentation=None, scene_opacity=0.5)
    assert node._inherited_scene_opacity() == 0.8 * 0.5
    node.synchronize(identity=None, snapshot=None, presentation=None)
    assert node._inherited_scene_opacity() == 0.8                  # a sync without one: the scene is unfaded


@pytest.fixture
def faded_route(route_world, monkeypatch):
    """The native route tests' stand-in core (``route_world``), the Spectrum settings arithmetic reduced to its fade."""
    from rendering.quick.visualizer.implementations import spectrum as implementation

    monkeypatch.setattr(implementation, "spectrum_settings_values",
                        lambda logical, presentation, **card: {"u_fade": float(presentation.content_fade)})
    return route_world


def test_the_native_route_draws_the_scene_opacity_in_its_content_fade_not_in_the_composite(faded_route):
    world = faded_route
    route, core = world.make()
    bridge = _Bridge()
    identity = _identity("spectrum")
    presentation = world.presentation
    raw = _Snapshot(logical=SimpleNamespace(value=1, logical_timestamp=1.0, present_frame=True),
                    presentation=presentation)
    bridge.snapshots = [raw]
    assert route.sync(bridge=bridge, identity=identity, presentation=presentation, authority=True,
                      scene_opacity=0.75) is True
    card = [entry[1][0] for entry in core.log if entry[0] == "present_raw"][-1]
    settings = [entry[1][0] for entry in core.log if entry[0] == "settings"][-1]
    assert card["content_fade"] == presentation.content_fade * 0.75
    assert settings["u_fade"] == presentation.content_fade * 0.75
    # The composite is placed at full opacity: it never fades the surface for the scene.
    place = next(entry for entry in core.log if entry[0] == "place")
    assert place[2].get("opacity", 1.0) == 1.0
    # The retained frame is the published one (Edit reads it), not the faded copy.
    assert route.retained_snapshot(identity) is raw
    # The scene opacity moves with no new frame: the retained frame is carded again at the new fade.
    mark = len(core.log)
    assert route.sync(bridge=bridge, identity=identity, presentation=presentation, authority=True,
                      scene_opacity=1.0) is False
    card = [entry[1][0] for entry in core.log[mark:] if entry[0] == "present_raw"][-1]
    assert card["content_fade"] == presentation.content_fade
    # And at rest nothing is sent.
    mark = len(core.log)
    route.sync(bridge=bridge, identity=identity, presentation=presentation, authority=True, scene_opacity=1.0)
    assert core.log[mark:] == []


@pytest.mark.qt
def test_the_content_host_carries_no_scene_opacity_and_the_item_is_handed_it(qt_app):
    """The scene's chrome fades with the scene opacity; the content host does not (both renderers fold it themselves),
    and the item holds the root's own ``sceneOpacity`` at every edge that changes it."""
    from PySide6.QtQuick import QQuickItem

    from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
    from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from rendering.quick.window import QuickDisplayWindow
    from tests._visualizer_presentation import resolve_presentation

    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(screen_index=0, runtime_generation=0, screen=screen,       # never shown
                                policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False))
    controller = QuickSceneController(window=window, factory=QuickSceneFactory())
    presentation = resolve_presentation(policy=get_visualizer_presentation_policy("spectrum"),
                                        display_size=(1920.0, 1080.0), outer_origin=(207.0, 310.0),
                                        uniform_visual_scale=1.5, scene_fade=0.75)
    controller.apply_visualizer_presentation(presentation)
    root = controller._visualizer_root
    item = controller._visualizer_item
    host = root.findChild(QQuickItem, "visualizerContentHost")
    assert item.parentItem() is host
    scene = float(root.property("sceneOpacity"))
    assert scene == pytest.approx(0.75)
    assert item.scene_opacity == scene
    assert _effective_opacity(host) == 1.0
    # The chrome under and over the content fades with the scene, in that order around the host.
    under = root.findChild(QQuickItem, "visualizerSceneUnderLayer")
    over = root.findChild(QQuickItem, "visualizerSceneOverLayer")
    assert under.z() < host.z() < over.z()
    for name in ("visualizerCardBackground",):
        assert root.findChild(QQuickItem, name).parentItem() is under
    for name in ("visualizerCardFrame", "visualizerGlyphRow", "visualizerExpandedOverlays",
                 "visualizerInteractionGlowLoader"):
        assert root.findChild(QQuickItem, name).parentItem() is over, name
    assert _effective_opacity(root.findChild(QQuickItem, "visualizerCardBackground")) == pytest.approx(scene)
    assert _effective_opacity(root.findChild(QQuickItem, "visualizerCardFrame")) == pytest.approx(scene)
    # The card's shadow, drawn in the display's shadow lane, fades with it too.
    shadow = controller._scene_root.findChild(QQuickItem, "visualizerCardShadowUnderlay")
    assert float(shadow.opacity()) == pytest.approx(scene)
    # The startup reveal gate multiplies it, and the item follows.
    assert controller.set_visualizer_startup_reveal_opacity(0.5)
    assert float(root.property("sceneOpacity")) == pytest.approx(0.375)
    assert item.scene_opacity == float(root.property("sceneOpacity"))
    assert _effective_opacity(host) == 1.0
    controller.set_visualizer_startup_reveal_opacity(1.0)
    assert item.scene_opacity == pytest.approx(0.75)
