"""One camera control contract across every orbiting Visualizer mode (checklist AC-11).

* Every mode that orbits declares a Reset Camera path: the framed physical camera, ``home`` (turn/tilt to the preset
  home, the freeform modes Sphere and Extruded Spectrum), or ``none: <reason>``. Inertia and wrap match the table in
  ``Docs/Reference/Visualizer_Reference.md`` ("One camera control contract").
* Sphere and Extruded Spectrum gain Reset Camera: the card glyph is offered and the R / glyph route returns the view
  to its home and saves it. Before AC-11 the route returned at once for them and the glyph was never offered.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.settings.visualizer_mode_registry import (
    get_visualizer_mode_descriptor, iter_visualizer_mode_descriptors,
)

ROOT = Path(__file__).resolve().parents[1]
FREEFORM = ("sphere", "extruded_spectrum")


def _contract_table() -> dict[str, tuple[str, bool, bool]]:
    text = (ROOT / "Docs" / "Reference" / "Visualizer_Reference.md").read_text(encoding="utf-8")
    section = text.split("One camera control contract across every orbiting mode", 1)[1].split("\n- **", 1)[0]
    rows = {}
    for match in re.finditer(r"^\s*\| `(\w+)` \| (\w+(?::[^|]*)?) \| (yes|no) \| (yes|no) \|", section, re.M):
        rows[match.group(1)] = (match.group(2).strip(), match.group(3) == "yes", match.group(4) == "yes")
    return rows


def _reset_path(mode_id: str) -> str:
    from core.settings import visualizer_mode_registry as registry
    path = getattr(registry, "visualizer_camera_reset_path", None)
    if path is not None:
        return path(mode_id)
    descriptor = get_visualizer_mode_descriptor(mode_id)
    return "framed" if descriptor.framed_camera else getattr(descriptor, "view_camera_reset", "")


def test_every_orbiting_mode_declares_its_reset_path_inertia_and_wrap_as_the_reference_table():
    orbiting = [d.mode_id for d in iter_visualizer_mode_descriptors() if d.view_orbit_settings]
    table = _contract_table()
    assert sorted(table) == sorted(orbiting), "the reference table lists exactly the orbiting modes"
    for mode_id in orbiting:
        descriptor = get_visualizer_mode_descriptor(mode_id)
        path = _reset_path(mode_id)
        assert path in ("framed", "home") or path.startswith("none:"), f"{mode_id} declares no Reset Camera path"
        assert (path, descriptor.view_orbit_inertia, descriptor.view_orbit_turn_wraps) == table[mode_id], mode_id


def test_framed_cameras_stay_the_framed_standard():
    from core.settings.framed_camera import spec_for_mode
    for descriptor in iter_visualizer_mode_descriptors():
        if descriptor.framed_camera:
            assert spec_for_mode(descriptor.mode_id) is not None
            assert _reset_path(descriptor.mode_id) == "framed"
    for mode_id in FREEFORM:
        assert spec_for_mode(mode_id) is None, f"{mode_id} must not join the framed physical camera"


# ------------------------------------------------------------------------- the route (R and the card glyph)
@pytest.fixture
def manager(qt_app, tmp_path):
    from core.settings import SettingsManager
    from tests._display_manager_doubles import bare_display_manager, visualizer_owner_double
    settings = SettingsManager(application=f"CameraContract_{uuid.uuid4().hex}", storage_base_dir=tmp_path)
    manager = bare_display_manager(settings_manager=settings, _widgets_config_snapshot={})
    manager._refresh_quick_visualizer_edit_content_envelope = lambda *a: None
    manager._refresh_all_quick_context_menus = lambda: None
    manager._quick_view_orbit_admitted = lambda: True

    def own(mode_id):
        from widgets.spotify_visualizer.presentation_state import install_default_presentation_state
        from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
        widgets = settings.get_widgets_map()
        widgets["spotify_visualizer"].update({"enabled": True, "mode": mode_id})
        settings.set_widgets_map(widgets)
        controller = VisualizerRuntimeController(runtime_generation=0, initial_mode=mode_id,
                                                 engine_factory=lambda _n: None)
        install_default_presentation_state(controller.presentation_state)
        manager._quick_visualizer_owner = visualizer_owner_double(controller)
        return controller
    manager.own = own
    return manager


class _Recorder:
    def __init__(self):
        self.calls = {}

    def __getattr__(self, name):
        return lambda *args, **kwargs: self.calls.__setitem__(name, args)


@pytest.mark.parametrize("mode_id", FREEFORM)
def test_freeform_modes_offer_reset_camera_on_the_card(manager, mode_id):
    manager.own(mode_id)
    runtime = SimpleNamespace(input_controller=_Recorder(), scene_controller=_Recorder())
    manager._configure_quick_visualizer_input_admission(SimpleNamespace(runtime=runtime), admitted=True)
    assert runtime.scene_controller.calls["set_visualizer_camera_reset_available"] == (True,), \
        f"{mode_id}: the in-card Reset Camera glyph is not offered"
    assert runtime.input_controller.calls["set_framed_flight_enabled"] == (False,)   # no physical camera flight


@pytest.mark.parametrize("mode_id", FREEFORM)
def test_reset_camera_returns_a_freeform_view_to_its_home_and_saves_it(manager, mode_id):
    from core.settings.default_contract import require_canonical_default
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
    from widgets.spotify_visualizer.view_orbit import view_pose_values
    controller = manager.own(mode_id)
    keys = get_visualizer_mode_descriptor(mode_id).view_orbit_settings
    home = {key: float(require_canonical_default(f"widgets.spotify_visualizer.{key}")) for key in keys}
    orbited = {key: (0.37 if index == 0 else 0.21) for index, key in enumerate(keys)}
    assert orbited != home
    apply_presentation_vis_mode_kwargs(controller.presentation_state, orbited)
    assert view_pose_values(controller.presentation_state, mode_id) == pytest.approx(orbited)
    manager._reset_quick_visualizer_camera()
    assert view_pose_values(controller.presentation_state, mode_id) == pytest.approx(home), \
        f"{mode_id}: Reset Camera left the orbited view"
    saved = manager.settings_manager.get("widgets.spotify_visualizer")
    assert {key: saved[key] for key in keys} == pytest.approx(home)
