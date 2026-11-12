"""Switching the expanded card's display style (Current_Plan 1D.2, box 4): retarget in place, never rebuild.

The production owner (``QuickDisplayVisualizerOwner`` on an unshown ``QuickDisplayRuntime``; no window is shown)
replays a recorded clip through its real publication edge (``sync_present``), as
``tools/expanded_visualizer_evidence.owner_replay`` does. While the card is display-wide, a style change runs the
existing expanded-to-expanded fade-through: out in the old style, the swap at the bottom of the fade, in in the new
one, sampled on the publication edge against the owner's transition clock (no timer). The engine, controller, scene
item and render item stay the same objects, the full-display overlays stay drawn, and no frame is drawn without the
card. A change while collapsed draws nothing then and applies at the next expansion; the collapsed card never moves.
The display manager's route hands the stored value to the owner (``refresh_expanded_display_style``).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from core.settings.fullscreen_overlays import (
    DISPLAY_STYLE_BORDERS_TO_EDGE,
    DISPLAY_STYLE_DEFAULT,
    DISPLAY_STYLE_HIDE_BORDERS,
)

pytestmark = pytest.mark.qt
MODE = "extruded_bubble"


@dataclass
class _Run:
    frames: list = field(default_factory=list)           # (index, drawn style, scene_fade, outer_rect, overlays)
    identities: list = field(default_factory=list)
    returned: list = field(default_factory=list)


def _replay(clip, *, events: dict, half: float = 0.25) -> _Run:
    """Replay ``clip``; at frame ``i`` run ``events[i](owner)``. Records what the scene draws on every frame."""
    from PySide6.QtWidgets import QApplication

    from rendering.quick.runtime import QuickDisplayRuntime
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from tests._visualizer_frozen_settings import frozen_visualizer_settings
    from tools.expanded_visualizer_evidence import CARD, fresh_drift_revisions
    from tools.visualizer_replay.engine import ReplayBeatEngine
    from widgets.spotify_visualizer.feature_replay import configure_offline_controller, deterministic_clock
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner
    from widgets.spotify_visualizer.tick_pipeline import logical_tick

    app = QApplication.instance()
    run = _Run()
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(screen_index=0, runtime_generation=4242, screen=app.primaryScreen(),
                                  scene_factory=factory,
                                  window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False))
    owner = None
    try:
        with deterministic_clock() as clock, fresh_drift_revisions():
            engine = ReplayBeatEngine(32)
            owner = QuickDisplayVisualizerOwner(runtime, bar_count=32, initial_mode=MODE,
                                                engine_factory=lambda _count: engine, card_shadow_kwargs=CARD,
                                                transition_clock=lambda: clock[0], transition_half_duration_s=half)
            controller = owner.controller
            controller.engine = engine
            configure_offline_controller(controller, MODE, settings=frozen_visualizer_settings(MODE))
            owner.bind(engine_generation=engine.get_generation_id(), activation_id=engine.get_activation_id())
            scene = runtime.scene_controller

            def identity():
                return (id(owner.controller), id(engine), id(scene.visualizer_item),
                        id(scene.visualizer_item.render_identity) if scene.visualizer_item else None)

            for index, feature in enumerate(clip.frames):
                clock[0] = feature.timestamp_us / 1_000_000.0
                controller.playing = feature.playing
                engine.set_playback_state(feature.playing)
                assert engine.accept_feature_frame(feature)
                if index in events:
                    run.identities.append(identity())
                    run.returned.append(events[index](owner))
                assert logical_tick(controller.logical_tick_state) is not None
                owner.sync_present()
                drawn = scene.visualizer_item.presentation if scene.visualizer_item is not None else None
                run.frames.append((index, None if drawn is None else drawn.display_style,
                                   None if drawn is None else drawn.scene_fade,
                                   None if drawn is None else tuple(drawn.outer_rect),
                                   scene.visualizer_expanded_overlays_drawn))
            run.identities.append(identity())
    finally:
        if owner is not None and not owner.is_retired:
            owner.retire()
        runtime.close_runtime()
        factory.deleteLater()
        app.processEvents()
    return run


@pytest.fixture(scope="module")
def clip():
    from tools.expanded_visualizer_evidence import looped_fixture

    return looped_fixture(loops=4)


def _expand(owner):
    return owner.set_expanded_display(True)


def _style(style):
    return lambda owner: owner.set_expanded_display_style(style)


def _switch_frames(run: _Run, start: int):
    return [frame for frame in run.frames if frame[0] >= start]


def test_a_style_change_while_expanded_fades_through_in_place(qt_app, clip):
    run = _replay(clip, events={5: _expand, 30: _style(DISPLAY_STYLE_HIDE_BORDERS)})
    assert run.returned == [True, True]
    assert len(set(run.identities)) == 1                    # nothing created or torn down
    before = [frame for frame in run.frames if 5 <= frame[0] < 30]
    assert {frame[1] for frame in before} == {DISPLAY_STYLE_DEFAULT}
    after = _switch_frames(run, 30)
    styles = [frame[1] for frame in after]
    fades = [frame[2] for frame in after]
    # Every frame draws the card (never vanishes) with the overlays (display-wide throughout).
    assert all(frame[1] is not None and frame[4] for frame in after)
    # One swap, from the old style to the new, never back.
    swap = styles.index(DISPLAY_STYLE_HIDE_BORDERS)
    assert set(styles[:swap]) == {DISPLAY_STYLE_DEFAULT} and set(styles[swap:]) == {DISPLAY_STYLE_HIDE_BORDERS}
    # Out in the old style, the swap at the bottom of the fade, in in the new one, ending fully visible.
    assert swap > 1 and min(fades[:swap]) < 1.0 and fades[-1] == 1.0
    assert all(a >= b for a, b in zip(fades[:swap], fades[1:swap]))           # fading out
    assert all(a <= b for a, b in zip(fades[swap:], fades[swap + 1:]))          # fading in
    bottom = min(fades)
    assert bottom < 0.1 and max(fades[swap - 1], fades[swap]) < 0.35
    # The new style's card is the whole display; the old one was inset.
    assert after[0][3][0] > 0.0 and after[-1][3][:2] == (0.0, 0.0)


def test_negative_control_a_swap_without_the_fade_is_caught(qt_app, clip, monkeypatch):
    """The bars above see a style applied directly (no fade-through): the swap lands at full opacity."""
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    def snap(self, _source_style):
        self._reapply_route(request_present=True)

    monkeypatch.setattr(QuickDisplayVisualizerOwner, "_begin_style_fade", snap)
    run = _replay(clip, events={5: _expand, 30: _style(DISPLAY_STYLE_HIDE_BORDERS)})
    after = _switch_frames(run, 30)
    swap = [frame[1] for frame in after].index(DISPLAY_STYLE_HIDE_BORDERS)
    assert swap == 0 and after[0][2] == 1.0                 # popped: what the fade bars forbid


def test_a_change_while_collapsed_applies_at_the_next_expansion(qt_app, clip):
    run = _replay(clip, events={10: _style(DISPLAY_STYLE_BORDERS_TO_EDGE), 40: _expand})
    collapsed = [frame for frame in run.frames if frame[0] < 40]
    assert {frame[1] for frame in collapsed} == {DISPLAY_STYLE_DEFAULT}       # the ordinary record: untouched
    assert len({frame[3] for frame in collapsed}) == 1 and {frame[2] for frame in collapsed} == {1.0}
    assert not any(frame[4] for frame in collapsed)
    expanded = _switch_frames(run, 40)
    assert {frame[1] for frame in expanded} == {DISPLAY_STYLE_BORDERS_TO_EDGE}
    assert expanded[0][3][:2] == (0.0, 0.0)


def test_a_change_during_an_expansion_fade_lands_on_its_target_side(qt_app, clip):
    """An expansion fading through takes a change for its display-wide side when that side is not drawn yet; once it
    is drawn, the change follows with its own fade-through (never a pop)."""
    def expand_animated(owner):
        return owner.set_expanded_display(True, animate=True)

    early = _replay(clip, events={5: expand_animated, 6: _style(DISPLAY_STYLE_HIDE_BORDERS)})
    expanded_styles = {frame[1] for frame in early.frames if frame[4]}
    assert expanded_styles == {DISPLAY_STYLE_HIDE_BORDERS}, expanded_styles
    late = _replay(clip, events={5: expand_animated, 26: _style(DISPLAY_STYLE_HIDE_BORDERS)})
    after = [frame for frame in late.frames if frame[4]]
    labels = [frame[1] for frame in after]
    assert labels[0] == DISPLAY_STYLE_DEFAULT and labels[-1] == DISPLAY_STYLE_HIDE_BORDERS
    swap = labels.index(DISPLAY_STYLE_HIDE_BORDERS)
    assert max(after[swap - 1][2], after[swap][2]) < 0.35 and after[-1][2] == 1.0


def test_the_display_managers_route_hands_the_stored_style_to_the_owner(tmp_path):
    """``refresh_expanded_display_style`` reads ``fullscreen_overlays.display_style`` from a real SettingsManager
    (normalised by its owner) and hands it to the admitted owner; a malformed value is the canonical style; no owner,
    nothing."""
    import uuid

    from core.settings.fullscreen_overlays import FULLSCREEN_OVERLAYS_KEY, canonical_fullscreen_overlays
    from core.settings.settings_manager import SettingsManager
    from tests._display_manager_doubles import bare_display_manager, visualizer_owner_double

    received = []
    owner = visualizer_owner_double(None, set_expanded_display_style=lambda style: received.append(style) or True)
    settings = SettingsManager(organization="TestOrg", application=f"TestApp_{uuid.uuid4().hex}",
                               storage_base_dir=tmp_path)
    manager = bare_display_manager(settings_manager=settings, _quick_visualizer_owner=owner)
    settings.set(FULLSCREEN_OVERLAYS_KEY, {**canonical_fullscreen_overlays(), "display_style": "hide_borders"})
    assert manager.refresh_expanded_display_style() is True
    settings.set(FULLSCREEN_OVERLAYS_KEY, {**canonical_fullscreen_overlays(), "display_style": "nonsense"})
    manager.refresh_expanded_display_style()
    assert received == ["hide_borders", canonical_fullscreen_overlays()["display_style"]]
    manager._quick_visualizer_owner = None
    assert manager.refresh_expanded_display_style() is False


def test_a_settings_change_reaches_the_display_manager_through_the_engines_route():
    """The engine's ``settings.changed`` route (the bridge of ``SettingsManager.settings_changed``) refreshes the
    display style for a write of the Visualizer section or the record, and for nothing else."""
    from types import SimpleNamespace

    from engine.screensaver_engine import ScreensaverEngine

    calls = []
    engine = SimpleNamespace(display_manager=SimpleNamespace(refresh_expanded_display_style=lambda: calls.append(1)))
    for key, expected in (("widgets.spotify_visualizer.fullscreen_overlays", 1), ("widgets.spotify_visualizer", 1),
                          ("widgets", 1), ("widgets.clock.enabled", 0), ("accessibility.dimming.enabled", 0)):
        calls.clear()
        ScreensaverEngine._on_settings_changed(engine, SimpleNamespace(data={"key": key, "value": None}))
        assert len(calls) == expected, key



def test_a_card_on_the_displays_edges_uses_the_exact_display_size():
    """2560 px at 150 %: Qt's screen geometry reads 1707 logical (whole pixels), the monitor is 1706.67. A margin-0
    card resolved on 1707 puts its right edge half a device pixel past the monitor, snapped to one whole pixel off it
    (the frame's outer pixel cut away by the window's shared edge, or lost in the overscan). The owner resolves those
    styles on the scene's published visible rect; Default keeps its input (its record unchanged)."""
    from types import SimpleNamespace

    from tests._display_manager_doubles import scene_controller_double
    from tests._expanded_display_style_cases import ordinary
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_card_drawn_rect,
        resolve_expanded_visualizer_presentation,
    )
    from widgets.spotify_visualizer.quick_display_visualizer_owner import _expanded_display_size

    exact = (2560 / 1.5, 1440 / 1.5)
    scene = scene_controller_double(visible_display_size=lambda: exact)
    runtime = SimpleNamespace(display_identity=SimpleNamespace(geometry=(0, 0, 1707, 960)), scene_controller=scene)
    assert _expanded_display_size(runtime, DISPLAY_STYLE_DEFAULT) == (1707.0, 960.0)
    for style in (DISPLAY_STYLE_BORDERS_TO_EDGE, DISPLAY_STYLE_HIDE_BORDERS):
        size = _expanded_display_size(runtime, style)
        assert size == exact
        record = resolve_expanded_visualizer_presentation(ordinary("devcurve", "canonical", "no_shadow",
                                                                   "2560x1440_150"), display_size=size, dpr=1.5,
                                                          display_style=style)
        x, _y, width, _h = resolve_card_drawn_rect(record)
        assert round((x + width) * 1.5) == 2560
        # Negative control: Qt's whole-logical geometry puts the snapped card one device pixel past the monitor.
        wrong = resolve_expanded_visualizer_presentation(ordinary("devcurve", "canonical", "no_shadow",
                                                                  "2560x1440_150"), display_size=(1707.0, 960.0),
                                                         dpr=1.5, display_style=style)
        x, _y, width, _h = resolve_card_drawn_rect(wrong)
        assert round((x + width) * 1.5) == 2561
    # Before the window publishes its rect (an unshown window) the identity stands in.
    runtime.scene_controller = scene_controller_double(visible_display_size=lambda: None)
    assert _expanded_display_size(runtime, DISPLAY_STYLE_HIDE_BORDERS) == (1707.0, 960.0)
