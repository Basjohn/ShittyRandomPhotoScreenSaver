"""Studio/rotate glyphs must traverse the real hover admission and editor owners."""
from types import SimpleNamespace

from engine.display_manager import DisplayManager
from rendering.quick.scene_controller import QuickSceneController
from tests._display_manager_doubles import (
    bare_display_manager,
    display_runtime_double,
    display_unit_double,
    input_controller_double,
    scene_controller_double,
    visualizer_owner_double,
)
from ui.settings_launch_targets import resolve_settings_launch_target


class SignalCollector:
    def __init__(self):
        self.values = []

    def emit(self, *values):
        self.values.append(values)


def _scene():
    # Deliberately the scene's private admission state (_input_state, the hover signal): the real
    # QuickSceneController._publish_hover_edit_glyph and DisplayManager both read it, and the setter double
    # refuses instance-only names.
    state = SimpleNamespace(admission_open=True, exiting=False, context_menu_active=False,
                            interaction_mode_enabled=True, ctrl_held=False, always_show_glyphs=True)
    return SimpleNamespace(_custom_layout_session=None, _input_state=state,
                           hover_edit_glyph_requested=SignalCollector())


def test_studio_action_is_not_silently_removed_by_scene_admission():
    scene = _scene()
    QuickSceneController._publish_hover_edit_glyph(scene, "studio", "spotify_visualizer")
    assert scene.hover_edit_glyph_requested.values == [("studio", "spotify_visualizer")]
    scene._input_state.context_menu_active = True
    QuickSceneController._publish_hover_edit_glyph(scene, "studio", "spotify_visualizer")
    assert len(scene.hover_edit_glyph_requested.values) == 1


def test_studio_click_routes_to_lifecycle_target_with_live_mode_without_entering_edit(monkeypatch):
    from widgets.spotify_visualizer import view_orbit
    monkeypatch.setattr(view_orbit, "view_pose_values", lambda state, mode, now: {})
    scene = _scene()
    unit = display_unit_double(display_runtime_double(scene_controller=scene))
    owner = visualizer_owner_double(SimpleNamespace(mode_id="spectrum", presentation_state=object()))
    signals = SignalCollector()
    manager = bare_display_manager(_retired=False, displays=[unit], _quick_visualizer_unit=unit,
                                   _quick_visualizer_owner=owner, settings_target_requested=signals,
                                   _start_quick_custom_layout_session=lambda _entry: (_ for _ in ()).throw(
                                       AssertionError("Studio click must not enter CUSTOM")))
    assert DisplayManager._route_hover_edit_glyph(manager, unit, "studio", "spotify_visualizer")
    assert len(signals.values) == 1
    target = resolve_settings_launch_target(signals.values[0][0])
    assert target is not None and target.studio_mode == "spectrum"
    assert target.tab_key == "visualizers"


def test_studio_action_rejected_for_wrong_identity_or_closed_admission(monkeypatch):
    from widgets.spotify_visualizer import view_orbit
    monkeypatch.setattr(view_orbit, "view_pose_values", lambda state, mode, now: {})
    scene = _scene()
    unit = display_unit_double(display_runtime_double(scene_controller=scene))
    signals = SignalCollector()
    manager = bare_display_manager(_retired=False, displays=[unit], _quick_visualizer_unit=unit,
                                   _quick_visualizer_owner=visualizer_owner_double(
                                       SimpleNamespace(mode_id="spectrum", presentation_state=object())),
                                   settings_target_requested=signals)
    assert not DisplayManager._route_hover_edit_glyph(manager, unit, "studio", "clock")
    scene._input_state.context_menu_active = True
    assert not DisplayManager._route_hover_edit_glyph(manager, unit, "studio", "spotify_visualizer")
    assert not signals.values


def test_glyph_capabilities_are_retained_until_qml_root_creation():
    scene = SimpleNamespace(_visualizer_studio_glyph_available=False,
                            _visualizer_content_rotate_glyph_available=False, _visualizer_root=None)
    QuickSceneController.set_visualizer_studio_rotate_glyphs(scene, True, True)
    assert scene._visualizer_studio_glyph_available
    assert scene._visualizer_content_rotate_glyph_available
    calls = []
    scene._visualizer_root = SimpleNamespace(setProperty=lambda *args: calls.append(args))
    QuickSceneController.set_visualizer_studio_rotate_glyphs(scene, True, True)
    assert not calls
    QuickSceneController.set_visualizer_studio_rotate_glyphs(scene, False, True)
    assert calls == [("studioGlyphAvailable", False), ("contentRotateGlyphAvailable", True)]


def test_fullscreen_rotate_uses_existing_edit_card_and_model(monkeypatch):
    """The expanded card's Rotate runs Fullscreen Edit's card turn (``rotateContent``). Outside Edit it is Saved in
    the same call (plan 1D.7: Rotate never drops the user into Edit); inside Edit it stays the draft step."""
    from engine import display_manager
    from core.expanded_visualizer_takeover import Phase
    from rendering.quick.fullscreen_overlay_edit import CARD_EDIT_ID

    scene = _scene()
    card = SimpleNamespace(model_identity=CARD_EDIT_ID)
    actions = []
    scene.custom_layout_overlay = SimpleNamespace(model=SimpleNamespace(_items=[card],
                                          rotateContent=lambda index: actions.append(index) or True))
    unit = display_unit_double(display_runtime_double(scene_controller=scene))
    layout = SimpleNamespace(is_fullscreen=True, is_editing=False, visualizer_activation_idle=True)
    coordinator = SimpleNamespace(phase=Phase.EXPANDED, blocks_ordinary_layout=True)
    owner = visualizer_owner_double(SimpleNamespace(presentation_policy=SimpleNamespace(
        content_rotation_capable=True)))
    manager = bare_display_manager(_retired=False, displays=[unit], _quick_visualizer_unit=unit,
                                   _quick_visualizer_owner=owner, _quick_custom_layout_owner=layout,
                                   _expanded_display_coordinator=coordinator,
                                   _start_quick_custom_layout_session=lambda _entry: actions.append("start") or True,
                                   _save_quick_custom_layout=lambda: actions.append("save") or True)
    assert DisplayManager._route_hover_edit_glyph(manager, unit, "rotate", "spotify_visualizer")
    assert actions == ["start", 0, "save"]
    actions.clear()
    layout.is_editing = True
    assert DisplayManager._route_hover_edit_glyph(manager, unit, "rotate", "spotify_visualizer")
    assert actions == ["start", 0]
    layout.is_editing = False
    actions.clear()
    coordinator.phase = Phase.ENTERING
    assert not DisplayManager._route_hover_edit_glyph(manager, unit, "rotate", "spotify_visualizer")
    assert actions == []


def test_2d_mode_offers_studio_without_3d_camera_orbit():
    """A false view-orbit flag must not suppress a real 2D Visualizer's Studio glyph."""
    calls = []
    ic = input_controller_double(set_view_orbit_enabled=lambda value: calls.append(("orbit", value)))
    sc = scene_controller_double(
        set_visualizer_studio_rotate_glyphs=lambda *args: calls.append(("glyphs", args)))
    owner = visualizer_owner_double(SimpleNamespace(mode_id="spectrum",
                                                    presentation_policy=SimpleNamespace(
                                                        content_rotation_capable=True)))
    manager = bare_display_manager(_quick_visualizer_owner=owner, _quick_view_orbit_admitted=lambda: False)
    unit = display_unit_double(display_runtime_double(input_controller=ic, scene_controller=sc))
    DisplayManager._configure_quick_visualizer_input_admission(manager, unit)
    assert ("orbit", False) in calls
    assert ("glyphs", (True, True)) in calls
