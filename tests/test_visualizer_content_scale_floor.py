"""The Visualizer card's content scale has one absolute minimum (R-181).

A planar Visualizer card's content scale is its pixels per world unit: card pixels over ``viewport_extent``. The
canonical card (no CUSTOM entry) draws its world 1:1. Edit's uniform-scaling minimum used to be relative to each
session's starting card, because a Visualizer's size payload stores no scale scalar: every Runtime Edit session,
direct Alt gesture and Settings Arrange session could shrink the content another 0.4x, and a later side drag then grew
the world at that tiny scale (a framed lens widens with the world). These tests compound shrinks across sessions
through the real editors, and repair synthetic stored entries at settings load.

Values are derived from the canonical minimum and canonical world, never from a profile, preset or the operator's file.
"""
from __future__ import annotations

from copy import deepcopy

import pytest
from PySide6.QtCore import QPoint, QRect

from core.settings.default_contract import MC_PROFILE
from core.settings.default_settings import DEFAULT_SETTINGS
from core.settings.visualizer_mode_registry import (
    get_visualizer_geometry_kind,
    get_visualizer_mode_descriptor,
    iter_all_visualizer_mode_descriptors,
)
from rendering.quick.custom_layout_size import (
    VISUALIZER_MIN_PIXELS_PER_WORLD,
    repair_visualizer_card_content_scale,
)
from widgets.spotify_visualizer.render_state import CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE

CANONICAL = tuple(float(v) for v in CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE)
MINIMUM = VISUALIZER_MIN_PIXELS_PER_WORLD


def _card_modes() -> tuple[str, ...]:
    """One plain 2D card mode and one framed 3D card mode, from the registry."""

    planar = [d for d in iter_all_visualizer_mode_descriptors()
              if get_visualizer_geometry_kind(d.mode_id) == "planar"]
    plain = next(d.mode_id for d in planar if not d.framed_camera)
    framed = next(d.mode_id for d in planar if d.framed_camera)
    return plain, framed


def _legal(width: float, height: float, extent) -> bool:
    """A card encodes a content scale at or above the minimum within its half-pixel rounding."""

    return min((float(width) + 0.5) / float(extent[0]), (float(height) + 0.5) / float(extent[1])) >= MINIMUM


# ----------------------------------------------------------------------------------------- Runtime Edit (the writer)


@pytest.mark.qt
@pytest.mark.parametrize("mode_id", _card_modes())
def test_runtime_edit_sessions_never_compound_the_content_scale_below_the_minimum(qt_app, monkeypatch, mode_id):
    """Three Edit sessions each wheel the card down as far as Edit allows, then a side drag grows the card.

    Before the fix each session's 0.4 floor restarted from that session's card: 1.0 -> 0.4 -> 0.16 -> the 48x32
    pixel floor, and the final side drag grew the world to card / 0.11. The minimum is absolute now.
    """
    from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
    from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner
    from rendering.quick.display_unit import create_quick_display_unit
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from tests.test_qtquick_custom_layout_owner import _configure_visualizer, _LiveCommitEngine, _Settings
    from widgets.spotify_visualizer import tick_pipeline
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    monkeypatch.setattr(tick_pipeline, "consume_engine_bars", lambda _o, _n: (True, True))
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda _o, _n: None)
    screen = qt_app.primaryScreen()
    factory = QuickSceneFactory()
    unit = create_quick_display_unit(
        screen=screen, screen_index=0, runtime_generation=1181, scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
        ctrl_coordinator=SharedCtrlCoordinator(), adapters=(),
    )
    visualizer = QuickDisplayVisualizerOwner(
        unit.runtime, bar_count=24, initial_mode=mode_id,
        card_shadow_kwargs={
            "background_color": (0, 0, 0, 0), "border_color": (255, 255, 255, 255),
            "border_width": 4., "corner_radius": 6., "content_inset": 14.,
            "shadow_enabled": False, "shadow_color": (0, 0, 0, 0),
            "shadow_blur": 0., "shadow_offset": (0., 0.), "shadow_spread": 0.,
            "shadow_extensions": (0., 0., 0., 0.),
        },
        engine_factory=lambda _count: _LiveCommitEngine(),
    )
    unit.attach_visualizer_owner(visualizer)
    settings = _Settings({"spotify_visualizer": {"enabled": True, "position": "Custom", "monitor": "1",
                                                 "mode": mode_id}})
    layout = QuickCustomLayoutOwner(
        settings_manager=settings, participants_provider=lambda: (unit,),
        visualizer_provider=lambda: (visualizer, unit), reload_request=lambda _kind: None,
    )
    scene = unit.runtime.scene_controller

    def present():
        assert tick_pipeline.logical_tick(state) is not None and visualizer.sync_present()
        return scene.visualizer_item.presentation

    try:
        _configure_visualizer(visualizer, playing=True)
        # The canonical card: its canonical world drawn 1:1.
        visualizer.configure_committed_layout(local_rect=(40.0, 40.0) + CANONICAL, viewport_extent=CANONICAL)
        visualizer.bind(engine_generation=3, activation_id=5)
        visualizer._apply_resolved_presentation(visualizer._resolve_current_presentation())
        visualizer.start(interval_s=10.0)
        state = visualizer.controller.logical_tick_state
        state._mode_teardown_block_until_ready = False
        state._mode_transition_ready = True
        state._waiting_for_fresh_engine_frame = False
        state._display_bars_source_generation = 3
        state._display_bars_source_activation = 5
        present()

        for _session in range(3):
            assert layout.start()
            item = next(e for e in layout.session.items() if e.model_identity == "spotify_visualizer")
            steps = 0
            while layout.resize_wheel(item, -120):
                layout.session.notify_item_changed(item)
                steps += 1
                assert steps < 200
            assert layout.save()
            shown = present()
            assert _legal(shown.outer_rect[2], shown.outer_rect[3], shown.viewport_extent), (
                _session, shown.outer_rect, shown.viewport_extent)

        # A later side drag grows the card at the (held) content scale, never at a compounded one.
        assert layout.start()
        item = next(e for e in layout.session.items() if e.model_identity == "spotify_visualizer")
        rect = QRect(item.current_global_rect)
        start = QPoint(rect.center().x(), rect.bottom())
        assert layout.begin_resize(item, "bottom", start)
        assert layout.update_resize(item, "bottom", start + QPoint(0, 220), True)
        layout.session.notify_item_changed(item)            # as the overlay does after each sample
        assert layout.save()
        shown = present()
        assert shown.outer_rect[3] > rect.height()
        assert _legal(shown.outer_rect[2], shown.outer_rect[3], shown.viewport_extent)
    finally:
        layout.retire()
        unit.retire()
        factory.deleteLater()
        qt_app.processEvents()


# ------------------------------------------------------------------------------------ Settings Arrange (same rule)


def _arrange_display():
    from ui.onboarding.arrange_model import ArrangeDisplay

    return ArrangeDisplay("screen:test", ("screen:test",), QRect(0, 0, 1000, 700), "1")


def _arrange_widgets() -> dict:
    widgets = deepcopy(DEFAULT_SETTINGS["widgets"])
    widgets["family_activation"] = {family: family in {"media", "visualizers"}
                                    for family in widgets["family_activation"]}
    widgets["media"].update(enabled=True, position="Top Left", monitor="1")
    widgets["spotify_visualizer"].update(enabled=True, mode=_card_modes()[0])
    return widgets


@pytest.mark.usefixtures("qt_app")
def test_settings_arrange_sessions_never_compound_the_content_scale_below_the_minimum():
    from ui.onboarding.arrange_model import ArrangeModel

    widgets = _arrange_widgets()
    display = _arrange_display()
    for session in range(4):
        model = ArrangeModel(widgets, (display,))
        vis = next(i for i in model.session.items() if i.model_identity == "spotify_visualizer")
        if session == 0:
            # Give the card a saved world first, exactly as a side drag in either editor does.
            model.resize_edge(vis.source_key, "right", QRect(vis.current_global_rect), QPoint(30, 0))
        for _step in range(60):
            model.wheel_scale(vis.source_key, -120)
        widgets = model.apply()
        variants = widgets["custom_layout"]["displays"]["screen:test"]["spotify_visualizer"]
        payload = variants[vis.source_key.geometry_variant]["size_payload"]
        extent = payload.get("viewport_extent") or CANONICAL
        assert _legal(payload["width"], payload["height"], extent), (session, payload)


# ------------------------------------------------------------------------------ The stored-entry repair rule (pure)


def _card_payload(scale: float, extent=(600.0, 250.0), **extra) -> dict:
    """A card of ``extent`` drawn at content ``scale``: the payload Edit writes."""

    return {"width": int(round(extent[0] * scale)), "height": int(round(extent[1] * scale)),
            "viewport_extent": [float(extent[0]), float(extent[1])], **extra}


@pytest.mark.parametrize("scale", (MINIMUM * 0.25, MINIMUM * 0.7, MINIMUM * 0.97))
def test_repair_brings_content_scale_to_the_minimum_keeping_the_card_and_world_aspect(scale):
    payload = _card_payload(scale, content_rotation_quarters_by_mode={"bubble": 2})
    original = deepcopy(payload)
    repaired = repair_visualizer_card_content_scale(payload)

    assert repaired is not None and payload == original                 # a copy; the input is untouched
    assert (repaired["width"], repaired["height"]) == (payload["width"], payload["height"])   # the visible card
    assert repaired["content_rotation_quarters_by_mode"] == payload["content_rotation_quarters_by_mode"]
    world = repaired["viewport_extent"]
    assert world[0] / world[1] == pytest.approx(payload["viewport_extent"][0] / payload["viewport_extent"][1])
    assert min(payload["width"] / world[0], payload["height"] / world[1]) == pytest.approx(MINIMUM)
    assert repair_visualizer_card_content_scale(repaired) is None      # idempotent


@pytest.mark.parametrize("payload", (
    _card_payload(1.0),
    _card_payload(MINIMUM),
    _card_payload(MINIMUM * 3.0),
    # Exactly at the minimum within the half-pixel a card rect carries (Edit's own floor output).
    {"width": 100, "height": 40, "viewport_extent": [100.5 / MINIMUM, 40.5 / MINIMUM]},
    # Nothing to judge: no stored card size, no stored world, malformed values.
    {"viewport_extent": [5000.0, 5000.0]},
    {"width": 300, "height": 200},
    {"width": 300, "height": 200, "viewport_extent": "bad"},
    {"width": True, "height": 200, "viewport_extent": [9000.0, 9000.0]},
    {"width": 0, "height": 200, "viewport_extent": [9000.0, 9000.0]},
))
def test_repair_leaves_legal_or_unjudgeable_payloads_alone(payload):
    assert repair_visualizer_card_content_scale(deepcopy(payload)) is None


# -------------------------------------------------------------------------- The repair at settings load (the owner)


def _scale_repairs(repairs: dict) -> list[str]:
    return [key for key in repairs if key.endswith(".viewport_extent")]


def _entry(payload: dict) -> dict:
    return {"rect": {"x": 0.01, "y": 0.04, "width": 0.23, "height": 0.41}, "resize_mode": "visualizer_rect",
            "size_payload": deepcopy(payload)}


def _stored_widgets(bad: dict, good: dict, freeform: dict, stale: dict) -> dict:
    """Every place a Visualizer card entry is stored: the live CUSTOM map (named + legacy) and a layout slot."""

    plain, _framed = _card_modes()
    sphere_profile = next(d.layout_profile for d in iter_all_visualizer_mode_descriptors()
                          if get_visualizer_geometry_kind(d.mode_id) == "freeform_3d")
    return {
        "spotify_visualizer": {"enabled": True, "position": "Custom", "mode": plain},
        "custom_layout": {"version": 2, "displays": {
            "screen:a": {"spotify_visualizer": {
                get_visualizer_mode_descriptor(plain).layout_profile: _entry(bad),
                sphere_profile: _entry(freeform),
                "3d:retired_profile": _entry(stale),
            }},
            "screen:b": {"spotify_visualizer": {"default": _entry(good)}},
        }},
        "layout_slots": {"version": 1, "slots": {"5": {"custom_layout": {"version": 2, "displays": {
            "screen:a": {"spotify_visualizer": {"default": _entry(bad)}},
            "screen:b": {"spotify_visualizer": {"default": _entry(good)}},
        }}}}},
    }


@pytest.mark.parametrize("application", (None, MC_PROFILE), ids=("standard", "media_center"))
def test_settings_load_repairs_every_stored_card_entry_and_leaves_legal_ones_bit_identical(tmp_path, application):
    import uuid

    from core.settings.settings_manager import SettingsManager

    bad, good = _card_payload(MINIMUM * 0.5), _card_payload(MINIMUM * 1.5)
    # Freeform stages keep an independent world (never tied to the card), and an unread retired profile is not a
    # card: neither is the card rule's to judge, however small their ratio.
    freeform, stale = _card_payload(MINIMUM * 0.1), _card_payload(MINIMUM * 0.1)
    manager = SettingsManager(organization="TestOrg", application=application or f"TestApp_{uuid.uuid4().hex}",
                              storage_base_dir=tmp_path / uuid.uuid4().hex)
    stored = _stored_widgets(bad, good, freeform, stale)
    manager._settings.setValue("widgets", deepcopy(stored))

    repairs = manager.validate_and_repair()
    widgets = manager.get("widgets")

    plain_profile = get_visualizer_mode_descriptor(_card_modes()[0]).layout_profile
    live = widgets["custom_layout"]["displays"]
    slot = widgets["layout_slots"]["slots"]["5"]["custom_layout"]["displays"]
    for repaired in (live["screen:a"]["spotify_visualizer"][plain_profile]["size_payload"],
                     slot["screen:a"]["spotify_visualizer"]["default"]["size_payload"]):
        assert (repaired["width"], repaired["height"]) == (bad["width"], bad["height"])
        assert _legal(repaired["width"], repaired["height"], repaired["viewport_extent"])
    expected = stored["custom_layout"]["displays"]
    for untouched in (("screen:b", "default"), ("screen:a", "3d:retired_profile")):
        display, variant = untouched
        assert live[display]["spotify_visualizer"][variant] == expected[display]["spotify_visualizer"][variant]
    freeform_variant = next(v for v in live["screen:a"]["spotify_visualizer"]
                            if v not in {plain_profile, "3d:retired_profile"})
    assert (live["screen:a"]["spotify_visualizer"][freeform_variant]
            == expected["screen:a"]["spotify_visualizer"][freeform_variant])
    assert (slot["screen:b"]["spotify_visualizer"]["default"]
            == stored["layout_slots"]["slots"]["5"]["custom_layout"]["displays"]["screen:b"]["spotify_visualizer"]["default"])
    assert len(_scale_repairs(repairs)) == 2

    # The next load finds nothing to repair: the repaired entries are legal.
    assert not _scale_repairs(manager.validate_and_repair())


def test_settings_load_with_only_legal_entries_writes_nothing(tmp_path):
    import uuid

    from core.settings.settings_manager import SettingsManager

    good = _card_payload(MINIMUM * 1.5)
    manager = SettingsManager(organization="TestOrg", application=f"TestApp_{uuid.uuid4().hex}",
                              storage_base_dir=tmp_path / uuid.uuid4().hex)
    stored = _stored_widgets(good, good, good, good)
    manager._settings.setValue("widgets", deepcopy(stored))
    before = manager.get("widgets")

    repairs = manager.validate_and_repair()

    assert not _scale_repairs(repairs)
    assert manager.get("widgets")["custom_layout"] == before["custom_layout"]
    assert manager.get("widgets")["layout_slots"] == before["layout_slots"]
