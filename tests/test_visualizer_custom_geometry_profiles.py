"""Visualizer CUSTOM layout-profile ownership and hot-swap regressions."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect

from rendering.custom_layout_commit import commit_custom_session
from rendering.custom_layout_contract import get_screen_signature, load_custom_layout_map
from rendering.custom_layout_session import CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem
from rendering.quick.custom_layout_hydration import (
    geometry_variant_for_presentation,
    resolve_quick_custom_entry,
    resolve_visualizer_custom_entry,
)
from rendering.widget_descriptors import get_widget_runtime_descriptor

PLANAR = "planar"
EXTRUDED = "3d:extruded_spectrum"
SHOCKWAVE = "3d:shockwave_grid"
SPHERE = "3d:sphere"
THREE_D_PROFILES = (EXTRUDED, SHOCKWAVE, SPHERE)
ALL_PROFILES = (PLANAR, *THREE_D_PROFILES)
MODE_PROFILE = {
    "spectrum": PLANAR,
    "bubble": PLANAR,
    "extruded_spectrum": EXTRUDED,
    "shockwave_grid": SHOCKWAVE,
    "sphere": SPHERE,
}


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


def _entry(x: float, y: float, width: float, height: float, *, extent=None) -> dict[str, object]:
    if extent is None:
        extent = (width * 1200, height * 800)
    return {
        "rect": {"x": x, "y": y, "width": width, "height": height},
        "size_payload": {"viewport_extent": list(extent)},
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


def _canonical_variants() -> dict[str, object]:
    return {
        PLANAR: _entry(.10, .10, .30, .20, extent=(960., 320.)),
        EXTRUDED: _entry(.20, .18, .34, .42, extent=(235., 205.)),
        SHOCKWAVE: _entry(.47, .28, .46, .25, extent=(390., 150.)),
        SPHERE: _entry(.62, .09, .24, .55, extent=(180., 420.)),
    }


def _session_item(screen, profile, *, geometry_kind="planar", legacy_profile=None, legacy_source=None):
    rect = QRect(screen.geometry().x() + 120, 80, 360, 200)
    return CustomLayoutSessionItem(
        source_key=CustomLayoutKey("spotify_visualizer", get_screen_signature(screen), profile),
        model_identity="spotify_visualizer",
        baseline_global_rect=rect,
        current_global_rect=QRect(rect),
        baseline_size_payload={"viewport_extent": [360.0, 200.0]},
        current_size_payload={"viewport_extent": [360.0, 200.0]},
        baseline_enabled=True,
        current_enabled=True,
        geometry_kind=geometry_kind,
        legacy_layout_profile=legacy_profile,
        legacy_source_variant=legacy_source,
        resize_capable=True,
        viewport_resize_capable=True,
        baseline_viewport_extent=(360.0, 200.0),
        source_monitor_route="1",
    )


def _commit(widgets, item, displays):
    session = CustomLayoutSession()
    session.add_item(item)
    descriptor = get_widget_runtime_descriptor("spotify_visualizer")
    assert descriptor is not None
    commit_custom_session(widgets, session, {item.source_key: descriptor}, displays)


def test_profile_identity_is_descriptor_owned_and_independent_from_geometry_kind():
    from core.settings.visualizer_mode_registry import (
        get_visualizer_geometry_kind,
        get_visualizer_layout_profile,
    )

    for mode, profile in MODE_PROFILE.items():
        owner = SimpleNamespace(controller=SimpleNamespace(mode_id=mode))
        assert geometry_variant_for_presentation("spotify_visualizer", owner) == profile
        assert get_visualizer_layout_profile(mode) == profile
    assert {get_visualizer_geometry_kind(mode) for mode in ("extruded_spectrum", "shockwave_grid", "sphere")} == {"freeform_3d"}
    assert len({MODE_PROFILE[mode] for mode in ("extruded_spectrum", "shockwave_grid", "sphere")}) == 3


def test_freeform_3d_uniform_wheel_uses_stable_unscaled_stage_and_side_shape_resets_it():
    """Four reversible wheel steps must not convert 480x270 into 480x269.

    Source is the one CUSTOM session rectangle; the unscaled reference is only
    a transient rounding aid, never a persisted or renderer-owned geometry.
    """
    from rendering.quick.custom_layout_size import uniform_scale_geometry

    screen = _Screen()
    item = _session_item(screen, EXTRUDED, geometry_kind="freeform_3d")
    item.set_geometry(QRect(100, 70, 480, 270), resize_scale=1.0,
                      viewport_extent=(160.0, 90.0))
    assert item.uniform_stage_reference == (480.0, 270.0)
    descriptor = get_widget_runtime_descriptor("spotify_visualizer")
    before = QRect(item.current_global_rect)
    for scale in (1.05, 1.0, 0.95, 1.0):
        projected = uniform_scale_geometry(item, descriptor, scale,
                                           QRect(item.current_global_rect),
                                           screen.geometry())
        assert projected is not None
        item.set_geometry(projected.rect, resize_scale=projected.scale)
    assert item.current_global_rect.size() == before.size()
    assert item.current_viewport_extent == (160.0, 90.0)

    # Non-uniform stage authoring changes the shape, so future whole-stage
    # scaling preserves the NEW authored ratio instead of the old one.
    item.set_geometry(QRect(100, 70, 550, 200))
    changed_shape = QRect(item.current_global_rect)
    for scale in (1.05, 1.0, 0.95, 1.0):
        projected = uniform_scale_geometry(item, descriptor, scale,
                                           QRect(item.current_global_rect),
                                           screen.geometry())
        assert projected is not None
        item.set_geometry(projected.rect, resize_scale=projected.scale)
    assert item.current_global_rect.size() == changed_shape.size()
    item.restore_baseline()
    assert item.uniform_stage_reference == (
        item.baseline_global_rect.width() / item.baseline_resize_scale,
        item.baseline_global_rect.height() / item.baseline_resize_scale,
    )


def test_freeform_3d_stage_resize_keeps_authored_aspect_and_renderer_world_independent():
    """A 3D stage is not required to have the renderer's logical-world aspect.

    Side/corner handles and the whole-stage scale must enlarge the *mesh* with
    the stage, not grow viewport_extent at the same rate to cancel the change.
    The historical planar invariant is deliberately retained separately.
    """
    from rendering.quick.custom_layout_size import (
        pixels_per_world_from_geometry, viewport_extent_resize_payload,
        uniform_scale_geometry,
    )

    screen = _Screen()
    item = _session_item(screen, EXTRUDED, geometry_kind="freeform_3d")
    item.current_global_rect = QRect(120, 80, 610, 180)
    item.current_viewport_extent = (480.0, 145.0)
    scalar = pixels_per_world_from_geometry(
        item.current_global_rect, item.current_viewport_extent,
        geometry_kind=item.geometry_kind,
    )
    assert scalar > 0.0
    with pytest.raises(RuntimeError, match="one pixels-per-world scale"):
        pixels_per_world_from_geometry(
            item.current_global_rect, item.current_viewport_extent,
            geometry_kind="planar",
        )

    # One-axis resize changes the stage, never the 3D camera/world extent.
    payload, extent = viewport_extent_resize_payload(
        item, scalar, QRect(120, 80, 800, 180),
        change_width=True, change_height=False,
    )
    assert extent == (480.0, 145.0)
    assert payload["viewport_extent"] == [480.0, 145.0]
    assert (payload["width"], payload["height"]) == (800, 180)

    scaled = uniform_scale_geometry(
        item, get_widget_runtime_descriptor("spotify_visualizer"), 1.1,
        item.current_global_rect, screen.geometry(), pixels_per_world=scalar,
    )
    assert scaled is not None
    assert scaled.rect.width() / 610.0 == pytest.approx(1.1, abs=0.01)
    assert scaled.rect.height() / 180.0 == pytest.approx(1.1, abs=0.01)


def test_active_mode_claims_legacy_input_but_sibling_3d_modes_never_borrow_it():
    screen = _Screen()
    widgets = _widgets("extruded_spectrum", {
        "default": _entry(.10, .20, .30, .25),
        "freeform_3d": _entry(.55, .40, .35, .45),
    })

    extruded = resolve_visualizer_custom_entry(widgets, screen, "extruded_spectrum")
    assert extruded is not None and extruded.geometry_variant == "freeform_3d"
    assert extruded.rect.x == .55
    assert resolve_visualizer_custom_entry(widgets, screen, "shockwave_grid") is None
    assert resolve_visualizer_custom_entry(widgets, screen, "sphere") is None
    assert resolve_visualizer_custom_entry(widgets, screen, "spectrum") is None


def test_explicit_legacy_claim_remains_with_original_profile_when_mode_selection_changes():
    screen = _Screen()
    widgets = _widgets("shockwave_grid", {"freeform_3d": _entry(.1, .2, .3, .2)})
    claimed = resolve_visualizer_custom_entry(
        widgets, screen, "extruded_spectrum", legacy_layout_profile=EXTRUDED,
    )
    assert claimed is not None and claimed.geometry_variant == "freeform_3d"
    assert resolve_visualizer_custom_entry(
        widgets, screen, "shockwave_grid", legacy_layout_profile=EXTRUDED,
    ) is None


@pytest.mark.parametrize("invalid", ({"rect": {}}, None, "corrupt"))
def test_invalid_named_profile_does_not_revive_legacy_pose(invalid):
    screen = _Screen()
    widgets = _widgets("extruded_spectrum", {
        "freeform_3d": _entry(.10, .20, .30, .25),
        EXTRUDED: invalid,
    })
    assert resolve_visualizer_custom_entry(widgets, screen, "extruded_spectrum") is None


def test_ordinary_route_does_not_hydrate_stale_saved_profile():
    widgets = _widgets("sphere", {SPHERE: _entry(.1, .2, .3, .2)})
    widgets["spotify_visualizer"]["position"] = "Top Left"
    assert resolve_visualizer_custom_entry(widgets, _Screen(), "sphere") is None


def test_mode_completion_promotes_only_the_authored_legacy_claim_and_preserves_3d_siblings():
    from engine.display_manager import DisplayManager
    from tests.test_qtquick_custom_layout_owner import _Settings

    screen = _Screen()
    signature = get_screen_signature(screen)
    sibling = deepcopy(_canonical_variants()[SHOCKWAVE])
    widgets = _widgets("extruded_spectrum", {
        "freeform_3d": _entry(.11, .22, .33, .44),
        SHOCKWAVE: sibling,
    })
    settings = _Settings(widgets)

    def set_mode(key, value):
        assert key == "widgets.spotify_visualizer.mode"
        settings.widgets["spotify_visualizer"]["mode"] = value

    settings.set = set_mode
    owner = SimpleNamespace(
        _legacy_layout_profile=EXTRUDED,
        _legacy_layout_source_variant="freeform_3d",
    )
    manager = SimpleNamespace(
        settings_manager=settings,
        _quick_visualizer_owner=owner,
        _widgets_config_snapshot=deepcopy(widgets),
        _refresh_all_quick_context_menus=lambda: None,
        _publish_quick_view_orbit_admission=lambda: None,
        _refresh_quick_visualizer_edit_content_envelope=lambda: None,
    )

    DisplayManager._complete_quick_visualizer_mode_change(manager, "sphere")
    variants = load_custom_layout_map(settings.widgets)["displays"][signature]["spotify_visualizer"]
    assert set(variants) == {EXTRUDED, SHOCKWAVE}
    assert variants[EXTRUDED]["rect"]["x"] == .11
    assert variants[SHOCKWAVE] == sibling
    assert SPHERE not in variants
    assert settings.widgets["spotify_visualizer"]["mode"] == "sphere"
    assert owner._legacy_layout_profile is None
    assert owner._legacy_layout_source_variant is None
    assert settings.save_calls == 1


def test_canonical_save_retires_default_without_erasing_any_sibling_profile():
    screen = _Screen()
    signature = get_screen_signature(screen)
    siblings = _canonical_variants()
    widgets = _widgets("spectrum", {"default": _entry(.6, .1, .3, .3), **deepcopy(siblings)})
    item = _session_item(screen, PLANAR)
    _commit(widgets, item, {signature: ((signature,), screen.geometry(), "1")})
    variants = load_custom_layout_map(widgets)["displays"][signature]["spotify_visualizer"]
    assert set(variants) == set(ALL_PROFILES)
    for profile in THREE_D_PROFILES:
        assert variants[profile] == siblings[profile]


def test_claimed_legacy_freeform_save_promotes_one_profile_only_then_retires_legacy():
    screen = _Screen()
    signature = get_screen_signature(screen)
    sphere = deepcopy(_canonical_variants()[SPHERE])
    widgets = _widgets("extruded_spectrum", {
        "freeform_3d": _entry(.41, .12, .31, .37),
        SPHERE: sphere,
    })
    item = _session_item(
        screen, EXTRUDED, geometry_kind="freeform_3d",
        legacy_profile=EXTRUDED, legacy_source="freeform_3d",
    )
    _commit(widgets, item, {signature: ((signature,), screen.geometry(), "1")})
    variants = load_custom_layout_map(widgets)["displays"][signature]["spotify_visualizer"]
    assert set(variants) == {EXTRUDED, SPHERE}
    assert variants[SPHERE] == sphere
    assert SHOCKWAVE not in variants
    assert "freeform_3d" not in variants


def test_missing_profile_selects_baseline_instead_of_copying_outgoing_3d_pose():
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner
    from widgets.spotify_visualizer.render_state import CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE

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
    owner._activate_committed_layout_profile("shockwave_grid")
    assert owner._committed_layout_rect is None
    assert owner._committed_layout_extent is None
    assert owner._controller.hydrated == (CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE, {})


@pytest.mark.parametrize("active", ALL_PROFILES)
def test_active_profile_transfer_preserves_dormant_siblings_on_both_displays(active):
    a, b = _Screen(), _Screen("other-screen", 1200)
    sa, sb = get_screen_signature(a), get_screen_signature(b)
    variants_a = _canonical_variants()
    variants_b = {
        profile: _entry(.55 + index * .03, .18, .20, .22)
        for index, profile in enumerate(ALL_PROFILES)
    }
    widgets = _widgets("spectrum", deepcopy(variants_a))
    widgets["custom_layout"]["displays"][sb] = {"spotify_visualizer": deepcopy(variants_b)}
    item = _session_item(a, active, geometry_kind="freeform_3d" if active != PLANAR else "planar")
    item.current_display_identity = sb
    item.current_global_rect.translate(1200, 0)
    _commit(widgets, item, {sa: ((sa,), a.geometry(), "1"), sb: ((sb,), b.geometry(), "2")})
    displays = load_custom_layout_map(widgets)["displays"]
    assert active not in displays[sa]["spotify_visualizer"]
    for profile in ALL_PROFILES:
        if profile != active:
            assert displays[sa]["spotify_visualizer"][profile] == variants_a[profile]
            assert displays[sb]["spotify_visualizer"][profile] == variants_b[profile]
    assert displays[sb]["spotify_visualizer"][active]["rect"]["x"] == .1
    assert widgets["spotify_visualizer"]["monitor"] == "2"


def test_alias_save_merges_all_profiles_once_under_canonical_monitor():
    from rendering.custom_layout_contract import get_screen_signature_aliases

    screen = _Screen()
    signature, *aliases = get_screen_signature_aliases(screen)
    old = aliases[-1]
    variants = _canonical_variants()
    widgets = _widgets("spectrum", {PLANAR: deepcopy(variants[PLANAR])})
    widgets["custom_layout"]["displays"][old] = {
        "spotify_visualizer": {profile: deepcopy(variants[profile]) for profile in THREE_D_PROFILES}
    }
    _commit(widgets, _session_item(screen, PLANAR), {signature: ((signature, *aliases), screen.geometry(), "1")})
    displays = load_custom_layout_map(widgets)["displays"]
    assert set(displays) == {signature}
    assert set(displays[signature]["spotify_visualizer"]) == set(ALL_PROFILES)


@pytest.mark.parametrize("mode", ("spectrum", "extruded_spectrum", "shockwave_grid", "sphere"))
def test_layout_slot_restores_mode_before_exact_profile_hydration_and_does_not_own_camera(mode):
    from core.settings.layout_slots import apply_layout_slot, get_layout_slot_payload, save_layout_slot
    from rendering.quick.custom_layout_hydration import resolve_quick_committed_entry

    widgets = _widgets(mode, deepcopy(_canonical_variants()))
    widgets["spotify_visualizer"]["extruded_spectrum_turn"] = 42
    widgets["spotify_visualizer"]["shockwave_grid_tilt"] = .19
    assert save_layout_slot(widgets, "1")
    payload = get_layout_slot_payload(widgets, "1")
    widgets["spotify_visualizer"]["mode"] = "spectrum" if mode != "spectrum" else "sphere"
    widgets["spotify_visualizer"]["extruded_spectrum_turn"] = 73
    widgets["spotify_visualizer"]["shockwave_grid_tilt"] = .37
    widgets["custom_layout"]["displays"] = {}
    assert apply_layout_slot(widgets, "1")
    entry = resolve_quick_committed_entry(widgets, _Screen(), "spotify_visualizer")
    assert entry is not None and entry.geometry_variant == MODE_PROFILE[mode]
    assert widgets["custom_layout"] == payload["custom_layout"]
    # Layout slots own layout/mode, not per-mode camera authoring.
    assert widgets["spotify_visualizer"]["extruded_spectrum_turn"] == 73
    assert widgets["spotify_visualizer"]["shockwave_grid_tilt"] == .37


def test_transferred_manager_resolves_target_profile_on_current_display():
    from engine.display_manager import DisplayManager

    class _Unit:
        def __init__(self, screen, index):
            self.screen_index = index
            self.runtime = SimpleNamespace(window=SimpleNamespace(screen=lambda: screen))
            self.is_retired = False
            self.visualizer_owner = None
        def attach_visualizer_owner(self, owner): self.visualizer_owner = owner
        def detach_visualizer_owner(self, owner):
            assert self.visualizer_owner is owner
            self.visualizer_owner = None
            return True

    class _Owner:
        is_retired = False
        def set_presentation_runtime(self, runtime): self.presentation_runtime = runtime

    a, b = _Screen(), _Screen("other-screen", 1200)
    source, target = _Unit(a, 0), _Unit(b, 1)
    owner = _Owner(); owner.presentation_runtime = source.runtime; source.visualizer_owner = owner
    widgets = _widgets("extruded_spectrum", {EXTRUDED: _entry(.1, .1, .3, .2)})
    widgets["custom_layout"]["displays"][get_screen_signature(b)] = {
        "spotify_visualizer": {EXTRUDED: _entry(.5, .3, .4, .5)},
    }
    manager = DisplayManager.__new__(DisplayManager)
    manager._retired = False; manager.displays = [source, target]
    manager._quick_visualizer_owner = owner; manager._quick_visualizer_unit = source
    manager._widgets_config_snapshot = widgets
    assert manager._resolve_quick_visualizer_layout_profile("extruded_spectrum")[0] == (120., 80., 360., 160.)
    assert manager._transfer_quick_visualizer_unit(target)
    resolved = manager._resolve_quick_visualizer_layout_profile("extruded_spectrum")
    assert resolved[:2] == ((600., 240., 480., 400.), (480., 400.))
    owner.presentation_runtime = source.runtime
    with pytest.raises(RuntimeError, match="disagrees"):
        manager._resolve_quick_visualizer_layout_profile("extruded_spectrum")


@pytest.mark.qt
@pytest.mark.parametrize("mode", ("spectrum", "extruded_spectrum", "shockwave_grid", "sphere"))
def test_production_manager_startup_hydrates_exact_named_profile_before_first_retained_publish(qt_app, monkeypatch, mode):
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from engine.display_manager import DisplayManager
    from rendering.quick.display_unit import QuickDisplayUnit
    from tests.test_onboarding_arrange_model import _only_default_widget
    from tests.test_qtquick_custom_layout_owner import _Settings
    from tests.test_qtquick_h_cutover import _ManagerVisualizerEngine
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    screen = qt_app.primaryScreen(); geometry = screen.geometry()
    widgets = _only_default_widget("spotify_visualizer")
    widgets["media"]["enabled"] = False
    widgets["spotify_visualizer"].update(enabled=True, position="Custom", monitor="1", mode=mode,
        mode_activation=build_visualizer_mode_activation((mode,)))
    rects = {
        PLANAR: (70., 90., 480., 160.), EXTRUDED: (180., 140., 420., 380.),
        SHOCKWAVE: (330., 90., 560., 190.), SPHERE: (770., 120., 260., 460.),
    }
    extents = {
        PLANAR: (960., 320.), EXTRUDED: (210., 190.),
        SHOCKWAVE: (420., 140.), SPHERE: (180., 400.),
    }
    variants = {}
    for profile, rect in rects.items():
        x, y, w, h = rect
        variants[profile] = {"rect": {"x": x/geometry.width(), "y": y/geometry.height(), "width": w/geometry.width(), "height": h/geometry.height()},
            "size_payload": {"viewport_extent": list(extents[profile])}, "resize_mode": "visualizer_rect"}
    widgets["custom_layout"] = {"version": 2, "displays": {get_screen_signature(screen): {"spotify_visualizer": variants}}}
    settings = _Settings(widgets); settings.get_application_name = lambda: "Screensaver"
    engine = _ManagerVisualizerEngine()
    monkeypatch.setattr("widgets.spotify_visualizer.beat_engine.get_shared_spotify_beat_engine", lambda _count: engine)
    monkeypatch.setattr(QuickDisplayVisualizerOwner, "_start_logical_runtime", lambda self, **_kwargs: None)
    monkeypatch.setattr(QuickDisplayUnit, "show_on_screen", lambda _unit: None)
    manager = DisplayManager(settings_manager=settings, runtime_generation=965)
    try:
        assert manager.initialize_displays() == len(qt_app.screens())
        owner = manager._quick_visualizer_owner; profile = MODE_PROFILE[mode]
        assert owner is not None and owner.controller.mode_id == mode
        assert owner._committed_layout_rect == rects[profile]
        presentation = owner._resolve_current_presentation()
        assert presentation.outer_rect == rects[profile]
        assert presentation.viewport_extent == extents[profile]
    finally:
        manager.cleanup(); manager.retire_runtime(); qt_app.processEvents()


@pytest.mark.parametrize("mode,legacy_source", (("spectrum", "default"), ("extruded_spectrum", "freeform_3d")))
def test_arrange_active_profile_save_discard_and_legacy_migration_preserve_all_siblings(qt_app, mode, legacy_source):
    from tests.test_onboarding_arrange_model import _only_default_widget
    from ui.onboarding.arrange_model import ArrangeDisplay, ArrangeModel

    screen = _Screen(); signature = get_screen_signature(screen); profile = MODE_PROFILE[mode]
    widgets = _only_default_widget("spotify_visualizer"); widgets["media"]["enabled"] = False
    widgets["spotify_visualizer"].update(enabled=True, position="Custom", mode=mode, monitor="1")
    siblings = {p: deepcopy(_canonical_variants()[p]) for p in ALL_PROFILES if p != profile}
    widgets["custom_layout"] = _widgets(mode, {legacy_source: _entry(.1, .2, .3, .25), **siblings})["custom_layout"]
    display = ArrangeDisplay(signature, (signature,), screen.geometry(), "1")
    model = ArrangeModel(widgets, (display,))
    item = next(item for item in model.session.items() if item.model_identity == "spotify_visualizer")
    assert item.source_key.geometry_variant == profile
    assert item.legacy_layout_profile == profile
    assert item.legacy_source_variant == legacy_source
    baseline = QRect(item.current_global_rect)
    model.move(item.source_key, baseline.translated(30, 25), snap=False); model.discard()
    assert model.widgets == widgets
    item = next(item for item in model.session.items() if item.model_identity == "spotify_visualizer")
    model.move(item.source_key, baseline.translated(30, 25), snap=False)
    committed = model.apply(); variants = committed["custom_layout"]["displays"][signature]["spotify_visualizer"]
    assert set(variants) == set(ALL_PROFILES)
    for sibling, payload in siblings.items(): assert variants[sibling] == payload
    resolved = resolve_visualizer_custom_entry(committed, screen, mode)
    assert resolved is not None and resolved.geometry_variant == profile
    assert resolved.rect.x == pytest.approx(.125)


@pytest.mark.qt
@pytest.mark.parametrize("mode", ("spectrum", "extruded_spectrum", "shockwave_grid", "sphere"))
def test_runtime_edit_save_touches_only_active_profile_and_preserves_all_siblings(qt_app, monkeypatch, mode):
    from rendering import runtime_input
    from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
    from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner
    from rendering.quick.display_unit import create_quick_display_unit
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from tests._visualizer_presentation import neutral_card_shadow_kwargs
    from tests.test_qtquick_custom_layout_owner import _configure_visualizer, _LiveCommitEngine, _Settings
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    screen = qt_app.primaryScreen(); signature = get_screen_signature(screen); profile = MODE_PROFILE[mode]
    variants = _canonical_variants(); baseline_payload = deepcopy(variants[profile])
    widgets = {"spotify_visualizer": {"enabled": True, "position": "Custom", "mode": mode, "monitor": "1"},
        "custom_layout": {"version": 2, "displays": {signature: {"spotify_visualizer": deepcopy(variants)}}}}
    factory = QuickSceneFactory()
    unit = create_quick_display_unit(screen=screen, screen_index=0, runtime_generation=964,
        scene_factory=factory, window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
        ctrl_coordinator=SharedCtrlCoordinator(), adapters=())
    owner = QuickDisplayVisualizerOwner(unit.runtime, bar_count=24, initial_mode=mode,
        engine_factory=lambda _count: _LiveCommitEngine(), card_shadow_kwargs=neutral_card_shadow_kwargs())
    unit.attach_visualizer_owner(owner); settings = _Settings(widgets); reloads = []
    layout = QuickCustomLayoutOwner(settings_manager=settings, participants_provider=lambda: (unit,),
        visualizer_provider=lambda: (owner, unit), reload_request=reloads.append, live_config_commit=lambda _widgets: None)
    monkeypatch.setattr(owner, "_start_logical_runtime", lambda **_kwargs: None)
    monkeypatch.setattr(runtime_input, "suppress_runtime_pointer_input", lambda *_args, **_kwargs: None)
    try:
        _configure_visualizer(owner)
        active = resolve_visualizer_custom_entry(widgets, screen, mode); assert active is not None
        geom = screen.geometry(); r = active.rect
        owner.configure_committed_layout(
            local_rect=(r.x * geom.width(), r.y * geom.height(), r.width * geom.width(), r.height * geom.height()),
            viewport_extent=tuple(active.size_payload["viewport_extent"]),
        )
        identity = owner.bind(engine_generation=3, activation_id=5)
        owner._apply_resolved_presentation(owner._resolve_current_presentation()); owner.start()
        assert layout.start()
        item = next(entry for entry in layout.session.items() if entry.model_identity == "spotify_visualizer")
        assert item.source_key.geometry_variant == profile
        item.current_global_rect.translate(17, 13)
        layout.session.notify_item_changed(item)
        # An Edit-mode hot-swap retains this unsaved draft and its siblings in
        # the SAME session. Return to the outgoing profile and Cancel once.
        other = "shockwave_grid" if mode != "shockwave_grid" else "extruded_spectrum"
        assert layout.activate_edit_visualizer_profile(other)
        assert layout.session is not None
        parked = next(x for x in layout.session.items() if x is item)
        assert parked.profile_parked
        assert parked.current_global_rect == item.current_global_rect
        assert len([x for x in layout.session.active_items()
                    if x.model_identity == "spotify_visualizer"]) == 1
        assert layout.activate_edit_visualizer_profile(mode)
        assert not item.profile_parked
        assert layout.cancel(); assert settings.widgets == widgets
        assert layout.start(); item = next(entry for entry in layout.session.items() if entry.model_identity == "spotify_visualizer")
        item.current_global_rect.translate(17, 13)
        # The real pointer editor publishes on every accepted geometry edge;
        # bare QRect mutation in a test bypasses that required retained update.
        layout.session.notify_item_changed(item)
        assert layout.save()
        saved = settings.widgets["custom_layout"]["displays"][signature]["spotify_visualizer"]
        assert set(saved) == set(ALL_PROFILES)
        for sibling in ALL_PROFILES:
            if sibling != profile: assert saved[sibling] == variants[sibling]
        assert saved[profile] != baseline_payload
        assert owner.render_identity is identity
        assert settings.save_calls == 1 and reloads == []
    finally:
        layout.retire(); unit.retire(); factory.deleteLater(); qt_app.processEvents()


@pytest.mark.qt
def test_hidden_mode_cycles_restore_each_independent_profile_on_one_retained_owner(qt_app, monkeypatch):
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation, get_visualizer_layout_profile
    from engine.display_manager import DisplayManager
    from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
    from rendering.quick.display_unit import create_quick_display_unit
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.state import QuickWindowPolicy
    from tests._visualizer_presentation import neutral_card_shadow_kwargs
    from tests.test_qtquick_custom_layout_owner import _configure_visualizer, _Settings
    from tests.test_qtquick_h_cutover import _ManagerVisualizerEngine
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    screen = qt_app.primaryScreen(); signature = get_screen_signature(screen); geometry = screen.geometry()
    poses = {
        PLANAR: ((70., 90., 480., 160.), (960., 320.)),
        EXTRUDED: ((180., 140., 420., 380.), (210., 190.)),
        SHOCKWAVE: ((420., 80., 610., 180.), (480., 145.)),
        SPHERE: ((820., 170., 250., 470.), (175., 410.)),
    }
    variants = {}
    for profile, (rect, extent) in poses.items():
        x, y, w, h = rect
        variants[profile] = {"rect": {"x": x/geometry.width(), "y": y/geometry.height(), "width": w/geometry.width(), "height": h/geometry.height()},
            "size_payload": {"viewport_extent": list(extent)}, "resize_mode": "visualizer_rect"}
    start_mode = "spectrum"
    mode_cycle = ("extruded_spectrum", "shockwave_grid", "sphere", "bubble", "extruded_spectrum", "sphere", start_mode)
    widgets = {"spotify_visualizer": {"enabled": True, "position": "Custom", "mode": start_mode},
        "custom_layout": {"version": 2, "displays": {signature: {"spotify_visualizer": variants}}}}
    widgets["spotify_visualizer"]["mode_activation"] = build_visualizer_mode_activation(mode_cycle)
    factory = QuickSceneFactory()
    unit = create_quick_display_unit(screen=screen, screen_index=0, runtime_generation=963,
        scene_factory=factory, window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
        ctrl_coordinator=SharedCtrlCoordinator(), adapters=())
    manager = DisplayManager.__new__(DisplayManager); manager._widgets_config_snapshot = deepcopy(widgets)
    manager.settings_manager = _Settings(widgets); manager._quick_visualizer_unit = unit
    manager._quick_custom_layout_owner = SimpleNamespace(is_editing=False, is_direct=False, is_active=False)
    engine = _ManagerVisualizerEngine()
    owner = QuickDisplayVisualizerOwner(unit.runtime, bar_count=32, initial_mode=start_mode,
        engine_factory=lambda _count: engine, card_shadow_kwargs=neutral_card_shadow_kwargs(),
        committed_layout_profile_resolver=manager._resolve_quick_visualizer_layout_profile)
    manager._quick_visualizer_owner = owner; unit.attach_visualizer_owner(owner)
    monkeypatch.setattr(owner, "_start_logical_runtime", lambda **_kwargs: None)
    lookups = []; real_resolver = owner._committed_layout_profile_resolver
    owner._committed_layout_profile_resolver = lambda mode: lookups.append((mode, owner._mode_transition_fade)) or real_resolver(mode)
    try:
        _configure_visualizer(owner)
        owner.configure_committed_layout(local_rect=poses[PLANAR][0], viewport_extent=poses[PLANAR][1])
        owner.bind(engine_generation=17, activation_id=23); owner._apply_resolved_presentation(owner._resolve_current_presentation()); owner.start()
        retained_item = unit.runtime.scene_controller.visualizer_item; current_profile = PLANAR
        before_settings = deepcopy(manager._widgets_config_snapshot); profile_scale = {}
        for mode in mode_cycle:
            previous_lookups = len(lookups); target_profile = get_visualizer_layout_profile(mode)
            assert manager._request_quick_visualizer_mode(mode)
            assert len(lookups) == previous_lookups
            owner._mode_transition_fade = 0.; owner._activate_pending_mode(10.)
            assert owner._mode_transition_phase == "waiting_target" and owner._mode_transition_fade == 0.
            assert unit.runtime.scene_controller.visualizer_item is retained_item
            expected_lookup = 0 if target_profile == current_profile else 1
            assert len(lookups) == previous_lookups + expected_lookup
            assert owner._committed_layout_rect == poses[target_profile][0]
            assert owner.controller.committed_viewport_extent == poses[target_profile][1]
            presentation = owner._resolve_current_presentation(); owner._apply_resolved_presentation(presentation)
            assert presentation.outer_rect == pytest.approx(poses[target_profile][0], abs=.001)
            assert presentation.viewport_extent == poses[target_profile][1]
            if target_profile in profile_scale:
                assert presentation.uniform_visual_scale == profile_scale[target_profile]
            else:
                profile_scale[target_profile] = presentation.uniform_visual_scale
            owner._mode_transition_phase = "idle"; owner._pending_mode_activation = None
            current_profile = target_profile
        assert all(fade == 0 for _, fade in lookups)
        assert manager._widgets_config_snapshot == before_settings
        assert engine.acquire_count == 1
    finally:
        unit.retire(); factory.deleteLater(); qt_app.processEvents()


@pytest.mark.qt
def test_parked_custom_profile_is_not_duplicate_but_remains_saved_sibling():
    from rendering.custom_layout_session import (
        CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem,
    )
    from PySide6.QtCore import QRect
    session = CustomLayoutSession()
    for profile, parked in ((EXTRUDED, True), (SHOCKWAVE, False), (SPHERE, True)):
        item = CustomLayoutSessionItem(
            source_key=CustomLayoutKey("spotify_visualizer", "screen:test", profile),
            model_identity="spotify_visualizer",
            baseline_global_rect=QRect(10, 20, 250, 170),
            current_global_rect=QRect(10, 20, 250, 170),
            baseline_size_payload={}, current_size_payload={},
            baseline_enabled=True, current_enabled=True,
            geometry_kind="freeform_3d", profile_parked=parked,
        )
        session.add_item(item)
    session.refresh_duplicate_state()
    assert len(session.items()) == 3  # all authored poses survive a Save
    assert len(session.active_items()) == 1  # one visible Visualizer
    assert all(not item.is_duplicate for item in session.items())
    session.items()[0].profile_parked = False
    session.items()[1].profile_parked = True
    session.refresh_duplicate_state()
    assert len(session.active_items()) == 1
    assert all(not item.is_duplicate for item in session.items())


def test_edit_save_refuses_inflight_or_failed_visualizer_activation_before_persisting():
    """A hidden target cannot be committed as though it were a live retained mesh."""
    from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner

    screen = _Screen()
    session = CustomLayoutSession()
    session.add_item(_session_item(screen, EXTRUDED, geometry_kind="freeform_3d"))
    calls = []
    owner = SimpleNamespace(
        _mode_transition_phase="fading_out",
        controller=SimpleNamespace(mode_id="extruded_spectrum"),
    )
    layout = QuickCustomLayoutOwner.__new__(QuickCustomLayoutOwner)
    layout._active = True
    layout._session = session
    layout._direct = False
    layout._visualizer_provider = lambda: (owner, None)
    layout._settings_manager = SimpleNamespace(
        get_widgets_map=lambda: calls.append("read_settings"),
        save=lambda: calls.append("save_settings"),
    )
    assert layout.save() is False
    assert layout.cancel() is False
    assert session.active_items()
    assert calls == []
    owner._mode_transition_phase = "failed"
    assert layout.save() is False
    assert calls == []
    owner._mode_transition_phase = "idle"
    session_item = next(iter(session.active_items()))
    session_item.current_viewport_extent = None
    assert layout.save() is False
    assert calls == []
    session_item.current_viewport_extent = (360.0, 200.0)
    owner.controller.mode_id = "shockwave_grid"
    assert layout.save() is False
    assert calls == []


def test_hidden_mode_preflight_failure_preserves_running_outgoing_logical_owner():
    """No fallible Edit-QML projection runs after the old cadence is stopped."""
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    calls = []
    controller = SimpleNamespace(
        mode_id="extruded_spectrum",
        ensure_engine=lambda: calls.append("ensure_engine"),
        stop_logical_runtime=lambda: calls.append("stop_logical_runtime"),
    )
    owner = QuickDisplayVisualizerOwner.__new__(QuickDisplayVisualizerOwner)
    owner._controller = controller
    owner._pending_mode_activation = {"kind": "mode", "mode": "shockwave_grid"}
    owner._mode_transition_phase = "fading_out"
    owner._mode_transition_fade = 0.0
    owner._edit_layout_profile_activator = lambda _target: (_ for _ in ()).throw(
        RuntimeError("synthetic target QML projection error")
    )
    owner._activate_pending_mode(10.0)
    assert calls == []
    assert controller.mode_id == "extruded_spectrum"
    assert owner._mode_transition_phase == "idle"
    assert owner._mode_transition_fade == 1.0
    assert owner._pending_mode_activation is None


def test_in_edit_profile_with_missing_legacy_world_gets_canonical_viewport_not_outgoing():
    """Old saved 3D slots may omit extent; never lend the outgoing 3D world."""
    from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner, _DisplayBinding
    from widgets.spotify_visualizer.render_state import CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE

    screen = _Screen()
    signature = get_screen_signature(screen)
    original = _session_item(screen, EXTRUDED, geometry_kind="freeform_3d")
    original.current_viewport_extent = (729.0, 321.0)
    session = CustomLayoutSession()
    session.add_item(original)
    variants = {EXTRUDED: _entry(.1, .1, .3, .2)}
    variants[SHOCKWAVE] = {
        "rect": {"x": .2, "y": .1, "width": .5, "height": .3},
        "size_payload": {}, "resize_mode": "visualizer_rect",
    }
    widgets = _widgets("extruded_spectrum", variants)
    updates = []
    scene = SimpleNamespace(refresh_custom_layout_session=lambda: updates.append(True))
    unit = SimpleNamespace(runtime=SimpleNamespace(scene_controller=scene))
    binding = _DisplayBinding(signature, "1", unit, screen, screen.geometry())
    owner = QuickCustomLayoutOwner.__new__(QuickCustomLayoutOwner)
    owner._active = True
    owner._direct = False
    owner._retired = False
    owner._session = session
    owner._bindings = {signature: binding}
    owner._descriptors = {original.source_key: get_widget_runtime_descriptor("spotify_visualizer")}
    owner._visualizer_pixels_per_world = {}
    owner._undo_pending = None
    owner._undo_history = []
    owner._settings_manager = SimpleNamespace(get_widgets_map=lambda: widgets)
    assert owner.activate_edit_visualizer_profile("shockwave_grid")
    active = next(item for item in session.active_items() if item.model_identity == "spotify_visualizer")
    assert active.source_key.geometry_variant == SHOCKWAVE
    assert active.current_viewport_extent == tuple(float(n) for n in CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE)
    assert active.current_viewport_extent != original.current_viewport_extent
    assert len(updates) == 1


def test_failed_first_edit_profile_projection_does_not_leave_phantom_sibling():
    """A failed QML Edit admission rolls back *all* session-owned draft metadata."""
    from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner, _DisplayBinding

    screen = _Screen()
    signature = get_screen_signature(screen)
    original = _session_item(screen, EXTRUDED, geometry_kind="freeform_3d")
    session = CustomLayoutSession()
    session.add_item(original)
    tries = []

    def refresh():
        tries.append(True)
        if len(tries) == 1:
            raise RuntimeError("target projection failed")

    scene = SimpleNamespace(refresh_custom_layout_session=refresh)
    unit = SimpleNamespace(runtime=SimpleNamespace(scene_controller=scene))
    binding = _DisplayBinding(signature, "1", unit, screen, screen.geometry())
    owner = QuickCustomLayoutOwner.__new__(QuickCustomLayoutOwner)
    owner._active = True
    owner._direct = False
    owner._retired = False
    owner._session = session
    owner._bindings = {signature: binding}
    owner._descriptors = {original.source_key: get_widget_runtime_descriptor("spotify_visualizer")}
    owner._visualizer_pixels_per_world = {}
    owner._undo_pending = None
    owner._undo_history = []
    owner._settings_manager = SimpleNamespace(
        get_widgets_map=lambda: _widgets("extruded_spectrum", {EXTRUDED: _entry(.1, .1, .3, .2)}),
    )
    before = session.items()
    with pytest.raises(RuntimeError, match="target projection failed"):
        owner.activate_edit_visualizer_profile("shockwave_grid")
    assert session.items() == before
    assert original.profile_parked is False
    assert tuple(owner._descriptors) == (original.source_key,)
    assert not owner._visualizer_pixels_per_world
    assert len(tries) == 2  # one rejected target, one restored outgoing projection


def test_visualizer_mode_deadline_is_one_shot_and_never_resurrects_a_retired_owner(monkeypatch):
    """Silent target failure gets one fenced recovery; late/stale timers do nothing."""
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    scheduled = []
    reported = []
    owner = QuickDisplayVisualizerOwner.__new__(QuickDisplayVisualizerOwner)
    owner._retired = False
    owner._mode_transition_phase = "waiting_target"
    owner._transition_request_serial = 13
    owner._transition_recovery_issued = False
    owner._transition_failure_callback = reported.append
    owner._transition_deadline_scheduler = lambda ms, callback: scheduled.append((ms, callback))
    owner._arm_transition_deadline()
    assert len(scheduled) == 1 and scheduled[0][0] >= 3000
    scheduled[0][1]()
    scheduled[0][1]()
    assert reported == ["deadline:waiting_target"]
    assert owner._mode_transition_phase == "failed"
    owner._transition_request_serial += 1
    owner._retired = True
    scheduled[0][1]()
    assert reported == ["deadline:waiting_target"]


def test_stalled_outgoing_fade_cancels_uncommitted_switch_without_reconstruction(monkeypatch):
    """Before logical retirement, a silent fade must leave its old source alive."""
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    scheduled = []
    recovered = []
    presented = []
    owner = QuickDisplayVisualizerOwner.__new__(QuickDisplayVisualizerOwner)
    owner._retired = False
    owner._mode_transition_phase = "fading_out"
    owner._mode_transition_started_at = 10.0
    owner._mode_transition_fade = 0.0
    owner._pending_mode_activation = {"kind": "mode", "mode": "shockwave_grid"}
    owner._transition_request_serial = 7
    owner._transition_recovery_issued = False
    owner._transition_failure_callback = recovered.append
    owner._transition_deadline_scheduler = lambda ms, callback: scheduled.append(callback)
    owner._resolve_current_presentation = lambda: "outgoing_stage"
    owner._apply_resolved_presentation = presented.append
    owner._request_retained_present = lambda: presented.append("request")
    owner._arm_transition_deadline()
    scheduled[0]()
    assert owner._mode_transition_phase == "idle"
    assert owner._mode_transition_fade == 1.0
    assert owner._pending_mode_activation is None
    assert recovered == []
    assert presented == ["outgoing_stage", "request"]


def test_failed_edit_projection_preserves_existing_parked_authored_sibling():
    """Rollback removes provisional drafts only, never earlier authored profiles."""
    from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner, _DisplayBinding

    screen = _Screen()
    signature = get_screen_signature(screen)
    outgoing = _session_item(screen, EXTRUDED, geometry_kind="freeform_3d")
    sibling = _session_item(screen, SHOCKWAVE, geometry_kind="freeform_3d")
    sibling.profile_parked = True
    sibling.current_global_rect.translate(19, 31)
    stage = QRect(sibling.current_global_rect)
    session = CustomLayoutSession()
    session.add_item(outgoing)
    session.add_item(sibling)
    calls = []

    def refresh():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("synthetic peer projection failure")

    scene = SimpleNamespace(refresh_custom_layout_session=refresh)
    unit = SimpleNamespace(runtime=SimpleNamespace(scene_controller=scene))
    binding = _DisplayBinding(signature, "1", unit, screen, screen.geometry())
    owner = QuickCustomLayoutOwner.__new__(QuickCustomLayoutOwner)
    owner._active = True
    owner._direct = False
    owner._retired = False
    owner._session = session
    owner._bindings = {signature: binding}
    owner._descriptors = {
        outgoing.source_key: get_widget_runtime_descriptor("spotify_visualizer"),
        sibling.source_key: get_widget_runtime_descriptor("spotify_visualizer"),
    }
    owner._visualizer_pixels_per_world = {}
    owner._undo_pending = None
    owner._undo_history = []
    owner._settings_manager = SimpleNamespace(get_widgets_map=lambda: {})
    with pytest.raises(RuntimeError, match="synthetic peer projection failure"):
        owner.activate_edit_visualizer_profile("shockwave_grid")
    assert session.items() == (outgoing, sibling)
    assert outgoing.profile_parked is False
    assert sibling.profile_parked is True
    assert sibling.current_global_rect == stage
    assert len(calls) == 2


def test_mode_activation_sync_exception_requests_one_reload_not_repeating_wake_errors():
    """Engine/controller failure after logical teardown cannot storm the GUI event loop."""
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    requested = []
    owner = QuickDisplayVisualizerOwner.__new__(QuickDisplayVisualizerOwner)
    owner._retired = False
    owner._sync = SimpleNamespace(sync_latest=lambda: (_ for _ in ()).throw(RuntimeError("source dead")))
    owner._mode_transition_phase = "fading_out"
    owner._mode_transition_started_at = 0.0
    owner._mode_transition_fade = 1.0
    owner._transition_clock = lambda: 0.05
    owner._transition_half_duration_s = 0.25
    owner._transition_recovery_issued = False
    owner._transition_failure_callback = requested.append
    assert owner.sync_present() is False
    assert owner._mode_transition_phase == "failed"
    assert requested == ["activation_exception"]
    assert owner.sync_present() is False
    assert requested == ["activation_exception"]


def test_mode_completion_persistence_exception_never_reports_idle_success():
    """The final callback is also inside activation failure ownership."""
    from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

    requested = []
    owner = QuickDisplayVisualizerOwner.__new__(QuickDisplayVisualizerOwner)
    owner._retired = False
    owner._sync = SimpleNamespace(sync_latest=lambda: True)
    owner._mode_transition_phase = "fading_in"
    owner._mode_transition_started_at = 0.0
    owner._mode_transition_fade = 0.0
    owner._transition_clock = lambda: 1.0
    owner._transition_half_duration_s = 0.25
    owner._transition_recovery_issued = False
    owner._transition_failure_callback = requested.append
    owner._controller = SimpleNamespace(mode_id="shockwave_grid")

    def fail_persistence(_mode):
        raise RuntimeError("settings persistence failed")

    owner._pending_mode_activation = {"kind": "mode", "mode": "shockwave_grid", "on_complete": fail_persistence}
    assert owner.sync_present() is True
    assert owner._mode_transition_phase == "failed"
    assert requested == ["completion_failed"]
