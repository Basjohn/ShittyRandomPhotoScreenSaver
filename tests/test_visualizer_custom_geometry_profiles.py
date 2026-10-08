"""Visualizer planar/freeform CUSTOM profile ownership regressions."""
from __future__ import annotations

from types import SimpleNamespace
from copy import deepcopy

import pytest

from PySide6.QtCore import QRect

from rendering.custom_layout_commit import commit_custom_session
from rendering.custom_layout_contract import get_screen_signature, load_custom_layout_map
from rendering.custom_layout_session import (
    CustomLayoutKey,
    CustomLayoutSession,
    CustomLayoutSessionItem,
)
from rendering.quick.custom_layout_hydration import (
    geometry_variant_for_presentation,
    resolve_quick_custom_entry,
    resolve_visualizer_custom_entry,
)
from rendering.widget_descriptors import get_widget_runtime_descriptor


class _Screen:
    def __init__(self, serial="profile-screen", x=0) -> None:
        self._serial = serial
        self._geometry = QRect(x, 0, 1200, 800)

    def serialNumber(self) -> str:
        return self._serial

    def manufacturer(self) -> str:
        return ""

    def model(self) -> str:
        return ""

    def name(self) -> str:
        return ""

    def geometry(self) -> QRect:
        return QRect(self._geometry)


def _entry(x: float, y: float, width: float, height: float) -> dict[str, object]:
    return {
        "rect": {"x": x, "y": y, "width": width, "height": height},
        "size_payload": {"viewport_extent": [width * 1200, height * 800]},
        "resize_mode": "visualizer_rect",
    }


def _widgets(mode: str, variants: dict[str, object]) -> dict[str, object]:
    screen = _Screen()
    return {
        "spotify_visualizer": {"enabled": True, "position": "Custom", "mode": mode},
        "custom_layout": {
            "version": 2,
            "displays": {get_screen_signature(screen): {"spotify_visualizer": variants}},
        },
    }


def test_profile_resolution_uses_named_family_and_legacy_default_only_when_missing():
    screen = _Screen()
    widgets = _widgets(
        "spectrum",
        {
            "default": _entry(0.10, 0.20, 0.30, 0.25),
            "freeform_3d": _entry(0.55, 0.40, 0.35, 0.45),
        },
    )

    planar = resolve_visualizer_custom_entry(widgets, screen, "spectrum")
    freeform = resolve_visualizer_custom_entry(widgets, screen, "shockwave_grid")

    assert planar is not None and planar.geometry_variant == "default"
    assert freeform is not None and freeform.geometry_variant == "freeform_3d"
    assert freeform.rect.x == 0.55

    widgets["custom_layout"]["displays"][get_screen_signature(screen)]["spotify_visualizer"]["planar"] = _entry(0.25, 0.10, 0.20, 0.20)
    named_planar = resolve_visualizer_custom_entry(widgets, screen, "bubble")
    assert named_planar is not None and named_planar.geometry_variant == "planar"
    assert named_planar.rect.x == 0.25


@pytest.mark.parametrize("mode,target", (("spectrum", "shockwave_grid"), ("shockwave_grid", "spectrum")))
def test_cross_family_lookup_does_not_clone_a_legacy_default_pose(mode, target):
    screen = _Screen()
    widgets = _widgets(mode, {"default": _entry(0.10, 0.20, 0.30, 0.25)})

    # Startup may interpret default for its active planar family. A target
    # freeform activation asks the exact named variant and gets its baseline.
    assert resolve_visualizer_custom_entry(widgets, screen, mode) is not None
    assert resolve_visualizer_custom_entry(widgets, screen, target) is None


@pytest.mark.parametrize("invalid", ({"rect": {}}, None, "corrupt"))
def test_invalid_named_profile_does_not_revive_legacy_pose(invalid):
    screen = _Screen()
    widgets = _widgets(
        "spectrum",
        {"default": _entry(0.10, 0.20, 0.30, 0.25), "planar": invalid},
    )

    assert resolve_visualizer_custom_entry(widgets, screen, "spectrum") is None


def test_profile_identity_comes_from_live_descriptor_not_shell_dimension():
    planar_owner = SimpleNamespace(controller=SimpleNamespace(mode_id="bubble"))
    freeform_owner = SimpleNamespace(controller=SimpleNamespace(mode_id="extruded_spectrum"))

    assert geometry_variant_for_presentation("spotify_visualizer", planar_owner) == "planar"
    assert geometry_variant_for_presentation("spotify_visualizer", freeform_owner) == "freeform_3d"


def test_ordinary_route_does_not_hydrate_stale_saved_profile():
    widgets = _widgets("spectrum", {"planar": _entry(.1, .2, .3, .2)})
    widgets["spotify_visualizer"]["position"] = "Top Left"
    assert resolve_visualizer_custom_entry(widgets, _Screen(), "spectrum") is None


def test_unsaved_live_legacy_profile_retains_original_family_when_mode_selection_changes():
    widgets = _widgets("extruded_spectrum", {"default": _entry(.1, .2, .3, .2)})
    assert resolve_visualizer_custom_entry(
        widgets, _Screen(), "spectrum", legacy_geometry_profile="planar"
    ).geometry_variant == "default"
    assert resolve_visualizer_custom_entry(
        widgets, _Screen(), "extruded_spectrum", legacy_geometry_profile="planar"
    ) is None


@pytest.mark.parametrize("legacy_profile", ("planar", None))
def test_mode_completion_preserves_legacy_family_across_restart_before_custom_save(legacy_profile):
    from engine.display_manager import DisplayManager
    from tests.test_qtquick_custom_layout_owner import _Settings

    widgets = _widgets("spectrum", {"default": _entry(.1, .2, .3, .2)})
    settings = _Settings(widgets)
    def set_mode(key, value):
        assert key == "widgets.spotify_visualizer.mode"
        settings.widgets["spotify_visualizer"]["mode"] = value
    settings.set = set_mode
    owner = SimpleNamespace(_legacy_layout_profile=legacy_profile)
    manager = SimpleNamespace(settings_manager=settings,
        _quick_visualizer_owner=owner, _widgets_config_snapshot=deepcopy(widgets),
        _refresh_all_quick_context_menus=lambda: None,
        _publish_quick_view_orbit_admission=lambda: None,
        _refresh_quick_visualizer_edit_content_envelope=lambda: None)
    DisplayManager._complete_quick_visualizer_mode_change(manager, "extruded_spectrum")
    variants = load_custom_layout_map(settings.widgets)["displays"][get_screen_signature(_Screen())]["spotify_visualizer"]
    assert set(variants) == {"planar"}
    assert settings.widgets["spotify_visualizer"]["mode"] == "extruded_spectrum"
    assert resolve_visualizer_custom_entry(settings.widgets, _Screen(), "extruded_spectrum") is None
    assert resolve_visualizer_custom_entry(settings.widgets, _Screen(), "spectrum").rect.x == .1
    assert manager._widgets_config_snapshot["custom_layout"] == settings.widgets["custom_layout"]
    assert owner._legacy_layout_profile is None
    assert settings.save_calls == 1


def test_profile_save_retires_legacy_default_without_erasing_sibling_profile():
    screen = _Screen()
    signature = get_screen_signature(screen)
    widgets = _widgets(
        "spectrum",
        {
            "default": _entry(0.10, 0.20, 0.30, 0.25),
            "freeform_3d": _entry(0.55, 0.40, 0.35, 0.45),
        },
    )
    item = CustomLayoutSessionItem(
        source_key=CustomLayoutKey("spotify_visualizer", signature, "planar"),
        model_identity="spotify_visualizer",
        baseline_global_rect=QRect(120, 80, 360, 200),
        current_global_rect=QRect(120, 80, 360, 200),
        baseline_size_payload={"viewport_extent": [360.0, 200.0]},
        current_size_payload={"viewport_extent": [360.0, 200.0]},
        baseline_enabled=True,
        current_enabled=True,
        legacy_geometry_variant="planar",
        resize_capable=True,
        viewport_resize_capable=True,
        baseline_viewport_extent=(360.0, 200.0),
        source_monitor_route="1",
    )
    session = CustomLayoutSession()
    session.add_item(item)
    descriptor = get_widget_runtime_descriptor("spotify_visualizer")
    assert descriptor is not None

    commit_custom_session(
        widgets,
        session,
        {item.source_key: descriptor},
        {signature: ((signature,), QRect(0, 0, 1200, 800), "1")},
    )

    variants = load_custom_layout_map(widgets)["displays"][signature]["spotify_visualizer"]
    assert set(variants) == {"planar", "freeform_3d"}
    assert variants["planar"]["rect"]["x"] == 0.1
    assert variants["freeform_3d"]["rect"]["x"] == 0.55


def test_missing_profile_selects_baseline_instead_of_copying_the_outgoing_pose():
    from widgets.spotify_visualizer.quick_display_visualizer_owner import (
        QuickDisplayVisualizerOwner,
    )
    from widgets.spotify_visualizer.render_state import (
        CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
    )

    class _Controller:
        def __init__(self) -> None:
            self.hydrated = None

        def hydrate_committed_layout_metrics(self, extent, rotations) -> None:
            self.hydrated = (extent, rotations)

    owner = object.__new__(QuickDisplayVisualizerOwner)
    owner._controller = _Controller()
    owner._committed_layout_rect = (40.0, 50.0, 700.0, 160.0)
    owner._committed_layout_extent = (700.0, 160.0)
    owner._committed_layout_profile_resolver = lambda _mode: None

    owner._activate_committed_layout_profile("extruded_spectrum")

    assert owner._committed_layout_rect is None
    assert owner._committed_layout_extent is None
    assert owner._controller.hydrated == (
        CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
        {},
    )


def _session_item(screen, profile, *, legacy=None):
    rect = QRect(screen.geometry().x() + 120, 80, 360, 200)
    return CustomLayoutSessionItem(
        source_key=CustomLayoutKey("spotify_visualizer", get_screen_signature(screen), profile),
        model_identity="spotify_visualizer",
        baseline_global_rect=rect,
        current_global_rect=QRect(rect),
        baseline_size_payload={"viewport_extent": [360.0, 200.0]},
        current_size_payload={"viewport_extent": [360.0, 200.0]},
        baseline_enabled=True, current_enabled=True,
        legacy_geometry_variant=legacy,
        resize_capable=True, viewport_resize_capable=True,
        baseline_viewport_extent=(360.0, 200.0), source_monitor_route="1",
    )


def _commit(widgets, item, displays):
    session = CustomLayoutSession()
    session.add_item(item)
    descriptor = get_widget_runtime_descriptor("spotify_visualizer")
    commit_custom_session(widgets, session, {item.source_key: descriptor}, displays)


@pytest.mark.parametrize("original,target", (("planar", "freeform_3d"), ("freeform_3d", "planar")))
def test_first_opposite_family_save_promotes_legacy_on_all_displays_and_preserves_named_siblings(original, target):
    a, b = _Screen(), _Screen("other-screen", 1200)
    sa, sb = get_screen_signature(a), get_screen_signature(b)
    widgets = _widgets("spectrum", {"default": _entry(.4, .1, .2, .2)})
    named = _entry(.7, .3, .2, .4)
    widgets["custom_layout"]["displays"][sb] = {"spotify_visualizer": {
        "default": _entry(.6, .2, .3, .2), original: deepcopy(named), target: _entry(.2, .2, .4, .3),
    }}
    item = _session_item(a, target, legacy=original)
    # ALL preserves independently authored per-display family records.
    _commit(widgets, item, {sa: ((sa,), a.geometry(), "ALL")})
    displays = load_custom_layout_map(widgets)["displays"]
    assert displays[sa]["spotify_visualizer"][original]["rect"]["x"] == .4
    assert displays[sb]["spotify_visualizer"][original] == named
    assert displays[sb]["spotify_visualizer"][target]["rect"]["x"] == .2
    assert all("default" not in layouts["spotify_visualizer"] for layouts in displays.values())


def test_named_save_retires_stale_default_without_migration_provenance():
    screen = _Screen()
    signature = get_screen_signature(screen)
    sibling = _entry(.5, .2, .4, .6)
    widgets = _widgets("spectrum", {"default": _entry(.6, .1, .3, .3), "freeform_3d": deepcopy(sibling)})
    _commit(widgets, _session_item(screen, "planar"), {signature: ((signature,), screen.geometry(), "1")})
    variants = load_custom_layout_map(widgets)["displays"][signature]["spotify_visualizer"]
    assert set(variants) == {"planar", "freeform_3d"}
    assert variants["freeform_3d"] == sibling


@pytest.mark.parametrize("active,sibling", (("planar", "freeform_3d"), ("freeform_3d", "planar")))
def test_active_profile_transfer_preserves_both_displays_dormant_siblings(active, sibling):
    a, b = _Screen(), _Screen("other-screen", 1200)
    sa, sb = get_screen_signature(a), get_screen_signature(b)
    a_sibling, b_sibling = _entry(.2, .1, .3, .2), _entry(.6, .2, .3, .4)
    widgets = _widgets("spectrum", {active: _entry(.1, .2, .3, .2), sibling: deepcopy(a_sibling)})
    widgets["custom_layout"]["displays"][sb] = {"spotify_visualizer": {active: _entry(.7, .4, .2, .2), sibling: deepcopy(b_sibling)}}
    item = _session_item(a, active)
    item.current_display_identity = sb
    item.current_global_rect.translate(1200, 0)
    _commit(widgets, item, {sa: ((sa,), a.geometry(), "1"), sb: ((sb,), b.geometry(), "2")})
    displays = load_custom_layout_map(widgets)["displays"]
    assert displays[sa]["spotify_visualizer"] == {sibling: a_sibling}
    assert displays[sb]["spotify_visualizer"][sibling] == b_sibling
    assert displays[sb]["spotify_visualizer"][active]["rect"]["x"] == .1
    assert widgets["spotify_visualizer"]["monitor"] == "2"


@pytest.mark.parametrize("active", ("planar", "freeform_3d"))
def test_alias_save_merges_both_profiles_once_under_canonical_monitor(active):
    from rendering.custom_layout_contract import get_screen_signature_aliases
    screen = _Screen()
    signature, *aliases = get_screen_signature_aliases(screen)
    old = aliases[-1]
    sibling = "freeform_3d" if active == "planar" else "planar"
    sibling_entry = _entry(.55, .3, .3, .4)
    widgets = _widgets("spectrum", {active: _entry(.1, .1, .2, .2)})
    widgets["custom_layout"]["displays"][old] = {"spotify_visualizer": {sibling: deepcopy(sibling_entry)}}
    _commit(widgets, _session_item(screen, active), {signature: ((signature, *aliases), screen.geometry(), "1")})
    displays = load_custom_layout_map(widgets)["displays"]
    assert set(displays) == {signature}
    assert set(displays[signature]["spotify_visualizer"]) == {active, sibling}
    assert displays[signature]["spotify_visualizer"][sibling] == sibling_entry


@pytest.mark.parametrize("mode", ("spectrum", "extruded_spectrum"))
def test_layout_slot_restores_mode_before_profile_hydration_and_retains_both(mode):
    from core.settings.layout_slots import apply_layout_slot, save_layout_slot, get_layout_slot_payload
    from rendering.quick.custom_layout_hydration import resolve_quick_committed_entry
    widgets = _widgets(mode, {"planar": _entry(.1, .2, .3, .2), "freeform_3d": _entry(.5, .3, .4, .5)})
    widgets["spotify_visualizer"]["extruded_turn_deg"] = 42
    assert save_layout_slot(widgets, "1")
    payload = get_layout_slot_payload(widgets, "1")
    widgets["spotify_visualizer"]["mode"] = "extruded_spectrum" if mode == "spectrum" else "spectrum"
    widgets["spotify_visualizer"]["extruded_turn_deg"] = 73
    widgets["custom_layout"]["displays"] = {}
    assert apply_layout_slot(widgets, "1")
    entry = resolve_quick_committed_entry(widgets, _Screen(), "spotify_visualizer")
    assert entry.geometry_variant == ("planar" if mode == "spectrum" else "freeform_3d")
    assert widgets["custom_layout"] == payload["custom_layout"]
    assert widgets["spotify_visualizer"]["extruded_turn_deg"] == 73


def test_transferred_manager_resolves_target_profile_on_current_display():
    from engine.display_manager import DisplayManager

    class _Unit:
        def __init__(self, screen, index):
            self.screen_index = index
            self.runtime = SimpleNamespace(window=SimpleNamespace(screen=lambda: screen))
            self.is_retired = False
            self.visualizer_owner = None

        def attach_visualizer_owner(self, owner):
            self.visualizer_owner = owner

        def detach_visualizer_owner(self, owner):
            assert self.visualizer_owner is owner
            self.visualizer_owner = None
            return True

    class _Owner:
        is_retired = False

        def set_presentation_runtime(self, runtime):
            self.presentation_runtime = runtime

    a, b = _Screen(), _Screen("other-screen", 1200)
    source, target = _Unit(a, 0), _Unit(b, 1)
    owner = _Owner()
    owner.presentation_runtime = source.runtime
    source.visualizer_owner = owner
    widgets = _widgets("spectrum", {"freeform_3d": _entry(.1, .1, .3, .2)})
    widgets["custom_layout"]["displays"][get_screen_signature(b)] = {
        "spotify_visualizer": {"freeform_3d": _entry(.5, .3, .4, .5)},
    }
    manager = DisplayManager.__new__(DisplayManager)
    manager._retired = False
    manager.displays = [source, target]
    manager._quick_visualizer_owner = owner
    manager._quick_visualizer_unit = source
    manager._widgets_config_snapshot = widgets
    assert manager._resolve_quick_visualizer_layout_profile("extruded_spectrum")[0] == (120., 80., 360., 160.)
    assert manager._transfer_quick_visualizer_unit(target)
    resolved = manager._resolve_quick_visualizer_layout_profile("extruded_spectrum")
    assert resolved[:2] == ((600., 240., 480., 400.), (480., 400.))
    assert manager._quick_visualizer_owner is owner
    owner.presentation_runtime = source.runtime
    with pytest.raises(RuntimeError, match="disagrees"):
        manager._resolve_quick_visualizer_layout_profile("extruded_spectrum")


@pytest.mark.qt
@pytest.mark.parametrize("mode,profile", (("spectrum", "planar"), ("extruded_spectrum", "freeform_3d")))
def test_production_manager_startup_hydrates_named_profile_before_first_retained_publish(qt_app, monkeypatch, mode, profile):
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from engine.display_manager import DisplayManager
    from rendering.quick.display_unit import QuickDisplayUnit
    from tests.test_onboarding_arrange_model import _only_default_widget
    from tests.test_qtquick_custom_layout_owner import _Settings
    from tests.test_qtquick_h_cutover import _ManagerVisualizerEngine
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner
    screen = qt_app.primaryScreen()
    geometry = screen.geometry()
    widgets = _only_default_widget("spotify_visualizer")
    widgets["media"]["enabled"] = False
    widgets["spotify_visualizer"].update(enabled=True, position="Custom", monitor="1", mode=mode,
        mode_activation=build_visualizer_mode_activation((mode,)))
    variants = {}
    rects = {"planar": (70., 90., 480., 160.), "freeform_3d": (180., 140., 420., 380.)}
    extents = {"planar": (960., 320.), "freeform_3d": (210., 190.)}
    for family, rect in rects.items():
        x, y, w, h = rect
        variants[family] = {"rect": {"x": x/geometry.width(), "y": y/geometry.height(), "width": w/geometry.width(), "height": h/geometry.height()},
            "size_payload": {"viewport_extent": list(extents[family])}, "resize_mode": "visualizer_rect"}
    widgets["custom_layout"] = {"version": 2, "displays": {get_screen_signature(screen): {"spotify_visualizer": variants}}}
    settings = _Settings(widgets)
    settings.get_application_name = lambda: "Screensaver"
    engine = _ManagerVisualizerEngine()
    monkeypatch.setattr("widgets.spotify_visualizer.beat_engine.get_shared_spotify_beat_engine", lambda _count: engine)
    monkeypatch.setattr(QuickDisplayVisualizerOwner, "_start_logical_runtime", lambda self, **_kwargs: None)
    monkeypatch.setattr(QuickDisplayUnit, "show_on_screen", lambda _unit: None)
    manager = DisplayManager(settings_manager=settings, runtime_generation=965)
    try:
        assert manager.initialize_displays() == len(qt_app.screens())
        owner = manager._quick_visualizer_owner
        assert owner is not None and owner.controller.mode_id == mode
        assert owner._committed_layout_rect == rects[profile]
        presentation = owner._resolve_current_presentation()
        assert presentation.outer_rect == rects[profile]
        assert presentation.viewport_extent == extents[profile]
        assert owner._committed_layout_profile_resolver.__self__ is manager
        assert owner._committed_layout_profile_resolver.__func__ is DisplayManager._resolve_quick_visualizer_layout_profile
    finally:
        manager.cleanup()
        manager.retire_runtime()
        qt_app.processEvents()


@pytest.mark.parametrize("mode,profile,sibling", (("spectrum", "planar", "freeform_3d"), ("extruded_spectrum", "freeform_3d", "planar")))
def test_arrange_active_profile_save_discard_and_legacy_migration_preserve_sibling(qt_app, mode, profile, sibling):
    from tests.test_onboarding_arrange_model import _only_default_widget
    from ui.onboarding.arrange_model import ArrangeDisplay, ArrangeModel
    screen = _Screen()
    signature = get_screen_signature(screen)
    widgets = _only_default_widget("spotify_visualizer")
    widgets["media"]["enabled"] = False
    widgets["spotify_visualizer"].update(enabled=True, position="Custom", mode=mode, monitor="1")
    sibling_entry = _entry(.55, .3, .3, .4)
    widgets["custom_layout"] = _widgets(mode, {"default": _entry(.1, .2, .3, .25), sibling: deepcopy(sibling_entry)})["custom_layout"]
    display = ArrangeDisplay(signature, (signature,), screen.geometry(), "1")
    model = ArrangeModel(widgets, (display,))
    visualizers = [item for item in model.session.items() if item.model_identity == "spotify_visualizer"]
    assert len(visualizers) == 1
    item = visualizers[0]
    assert item.source_key.geometry_variant == profile
    assert item.legacy_geometry_variant == profile
    baseline = QRect(item.current_global_rect)
    model.move(item.source_key, baseline.translated(30, 25), snap=False)
    model.discard()
    assert model.widgets == widgets
    item = next(item for item in model.session.items() if item.model_identity == "spotify_visualizer")
    assert item.current_global_rect == baseline
    model.move(item.source_key, baseline.translated(30, 25), snap=False)
    committed = model.apply()
    variants = committed["custom_layout"]["displays"][signature]["spotify_visualizer"]
    assert set(variants) == {profile, sibling}
    assert variants[sibling] == sibling_entry
    resolved = resolve_visualizer_custom_entry(committed, screen, mode)
    assert resolved.geometry_variant == profile
    assert resolved.rect.x == pytest.approx(.125)
    assert model.session.items()[0].source_key.geometry_variant == profile


@pytest.mark.qt
@pytest.mark.parametrize("mode,profile,sibling", (("spectrum", "planar", "freeform_3d"), ("extruded_spectrum", "freeform_3d", "planar")))
def test_runtime_edit_restore_size_cancel_and_save_touch_only_active_profile(qt_app, monkeypatch, mode, profile, sibling):
    from rendering import runtime_input
    from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
    from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner
    from rendering.quick.display_unit import create_quick_display_unit
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from tests._visualizer_presentation import neutral_card_shadow_kwargs
    from tests.test_qtquick_custom_layout_owner import _configure_visualizer, _LiveCommitEngine, _Settings
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner
    screen = qt_app.primaryScreen()
    signature = get_screen_signature(screen)
    sibling_entry = _entry(.55, .3, .3, .4)
    widgets = {"spotify_visualizer": {"enabled": True, "position": "Custom", "mode": mode, "monitor": "1"},
        "custom_layout": {"version": 2, "displays": {signature: {"spotify_visualizer": {
            sibling: deepcopy(sibling_entry), "default": _entry(.1, .2, .3, .25)}}}}}
    factory = QuickSceneFactory()
    unit = create_quick_display_unit(screen=screen, screen_index=0, runtime_generation=964,
        scene_factory=factory, window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
        ctrl_coordinator=SharedCtrlCoordinator(), adapters=())
    owner = QuickDisplayVisualizerOwner(unit.runtime, bar_count=24, initial_mode=mode,
        engine_factory=lambda _count: _LiveCommitEngine(), card_shadow_kwargs=neutral_card_shadow_kwargs())
    unit.attach_visualizer_owner(owner)
    settings = _Settings(widgets)
    reloads = []
    layout = QuickCustomLayoutOwner(settings_manager=settings, participants_provider=lambda: (unit,),
        visualizer_provider=lambda: (owner, unit), reload_request=reloads.append,
        live_config_commit=lambda _widgets: None)
    monkeypatch.setattr(owner, "_start_logical_runtime", lambda **_kwargs: None)
    # Physical input grace after Edit closes is separately covered; do not let
    # this geometry-only test suppress another test's synthetic gestures.
    monkeypatch.setattr(runtime_input, "suppress_runtime_pointer_input", lambda *_args, **_kwargs: None)
    try:
        _configure_visualizer(owner)
        owner.configure_committed_layout(local_rect=(120., 90., 480., 180.), viewport_extent=(960., 360.), legacy_geometry_profile=profile)
        identity = owner.bind(engine_generation=3, activation_id=5)
        owner._apply_resolved_presentation(owner._resolve_current_presentation())
        owner.start()
        baseline = unit.runtime.scene_controller.visualizer_item.presentation
        assert layout.start()
        (item,) = [entry for entry in layout.session.items() if entry.model_identity == "spotify_visualizer"]
        assert item.source_key.geometry_variant == profile
        assert layout.restore_item_size(item)
        assert (item.current_global_rect.x(), item.current_global_rect.y()) == (120 + screen.geometry().x(), 90 + screen.geometry().y())
        assert item.current_viewport_extent == item.authored_viewport_extent
        assert layout.cancel()
        assert settings.widgets == widgets
        assert owner._legacy_layout_profile == profile
        restored = owner._resolve_current_presentation()
        assert restored.outer_rect == baseline.outer_rect
        assert restored.viewport_extent == baseline.viewport_extent
        assert layout.start()
        item = next(entry for entry in layout.session.items() if entry.model_identity == "spotify_visualizer")
        assert layout.restore_item_size(item)
        assert layout.save()
        variants = settings.widgets["custom_layout"]["displays"][signature]["spotify_visualizer"]
        assert set(variants) == {profile, sibling}
        assert variants[sibling] == sibling_entry
        assert owner._legacy_layout_profile is None
        assert owner.render_identity is identity
        assert settings.save_calls == 1 and reloads == []
    finally:
        layout.retire()
        unit.retire()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_hidden_family_cycles_on_one_retained_owner_restore_exact_pose_extent_and_scale(qt_app, monkeypatch):
    from engine.display_manager import DisplayManager
    from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
    from core.settings.visualizer_mode_registry import (
        build_visualizer_mode_activation, get_visualizer_geometry_profile, iter_visualizer_mode_descriptors,
    )
    from rendering.quick.display_unit import create_quick_display_unit
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from tests._visualizer_presentation import neutral_card_shadow_kwargs
    from tests.test_qtquick_custom_layout_owner import _configure_visualizer, _Settings
    from tests.test_qtquick_h_cutover import _ManagerVisualizerEngine
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    screen = qt_app.primaryScreen()
    signature = get_screen_signature(screen)
    poses = {
        "planar": ((70., 90., 480., 160.), (960., 320.)),
        "freeform_3d": ((180., 140., 420., 380.), (210., 190.)),
    }
    geometry = screen.geometry()
    variants = {}
    for profile, (rect, extent) in poses.items():
        x, y, w, h = rect
        variants[profile] = {
            "rect": {"x": x / geometry.width(), "y": y / geometry.height(), "width": w / geometry.width(), "height": h / geometry.height()},
            "size_payload": {"viewport_extent": list(extent)}, "resize_mode": "visualizer_rect",
        }
    modes_by_profile = {
        profile: tuple(descriptor.mode_id for descriptor in iter_visualizer_mode_descriptors()
                       if get_visualizer_geometry_profile(descriptor.mode_id) == profile)
        for profile in poses
    }
    assert all(modes_by_profile.values())
    start_mode = modes_by_profile["planar"][0]
    mode_cycle = (modes_by_profile["freeform_3d"] + modes_by_profile["planar"]
                  + modes_by_profile["freeform_3d"][:1] + (start_mode,))
    widgets = {"spotify_visualizer": {"enabled": True, "position": "Custom", "mode": start_mode},
        "custom_layout": {"version": 2, "displays": {signature: {"spotify_visualizer": variants}}}}
    widgets["spotify_visualizer"]["mode_activation"] = build_visualizer_mode_activation(mode_cycle)
    factory = QuickSceneFactory()
    unit = create_quick_display_unit(screen=screen, screen_index=0, runtime_generation=963,
        scene_factory=factory, window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
        ctrl_coordinator=SharedCtrlCoordinator(), adapters=())
    manager = DisplayManager.__new__(DisplayManager)
    manager._widgets_config_snapshot = deepcopy(widgets)
    manager.settings_manager = _Settings(widgets)
    manager._quick_visualizer_unit = unit
    manager._quick_custom_layout_owner = SimpleNamespace(is_editing=False, is_direct=False, is_active=False)
    engine = _ManagerVisualizerEngine()
    owner = QuickDisplayVisualizerOwner(unit.runtime, bar_count=32, initial_mode=start_mode,
        engine_factory=lambda _count: engine, card_shadow_kwargs=neutral_card_shadow_kwargs(),
        committed_layout_profile_resolver=manager._resolve_quick_visualizer_layout_profile)
    manager._quick_visualizer_owner = owner
    unit.attach_visualizer_owner(owner)
    # Keep this geometry/activation gate deterministic without adding audio or
    # a logical thread; the real controller, activation transaction and retained
    # QQuickItem still execute their production configuration/hydration seams.
    monkeypatch.setattr(owner, "_start_logical_runtime", lambda **_kwargs: None)
    lookups = []
    real_resolver = owner._committed_layout_profile_resolver
    owner._committed_layout_profile_resolver = lambda mode: lookups.append((mode, owner._mode_transition_fade)) or real_resolver(mode)
    try:
        _configure_visualizer(owner)
        owner.configure_committed_layout(local_rect=poses["planar"][0], viewport_extent=poses["planar"][1])
        owner.bind(engine_generation=17, activation_id=23)
        owner._apply_resolved_presentation(owner._resolve_current_presentation())
        owner.start()
        retained_item = unit.runtime.scene_controller.visualizer_item
        initial = retained_item.presentation
        before_settings = deepcopy(manager._widgets_config_snapshot)
        profile_presentations = {"planar": initial}
        for mode in mode_cycle:
            before_rect, before_extent = owner._committed_layout_rect, owner._committed_layout_extent
            previous_lookups = len(lookups)
            assert manager._request_quick_visualizer_mode(mode)
            assert len(lookups) == previous_lookups  # outgoing fade cannot select target geometry
            owner._mode_transition_fade = 0.
            owner._activate_pending_mode(10.)
            assert owner._mode_transition_phase == "waiting_target" and owner._mode_transition_fade == 0.
            assert unit.runtime.scene_controller.visualizer_item is retained_item
            profile = get_visualizer_geometry_profile(mode)
            assert owner._committed_layout_rect == poses[profile][0]
            assert owner.controller.committed_viewport_extent == poses[profile][1]
            assert owner._committed_layout_extent in (None, poses[profile][1])
            same_family = before_rect == poses[profile][0]
            assert len(lookups) == previous_lookups + (0 if same_family else 1)
            if same_family:
                assert owner._committed_layout_rect is before_rect
                assert owner._committed_layout_extent is before_extent
            presentation = owner._resolve_current_presentation()
            owner._apply_resolved_presentation(presentation)
            assert presentation.outer_rect == pytest.approx(poses[profile][0], abs=.001)
            assert presentation.viewport_extent == poses[profile][1]
            if profile in profile_presentations:
                previous = profile_presentations[profile]
                assert presentation.uniform_visual_scale == previous.uniform_visual_scale
            else:
                profile_presentations[profile] = presentation
            # Readiness/reveal has separate production coverage. Start the next
            # admission after this test has asserted the fully hidden boundary.
            owner._mode_transition_phase = "idle"
            owner._pending_mode_activation = None
        assert all(fade == 0 for _, fade in lookups)
        assert manager._widgets_config_snapshot == before_settings
        assert engine.acquire_count == 1
    finally:
        unit.retire()
        factory.deleteLater()
        qt_app.processEvents()
