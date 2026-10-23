"""EB sectional lazy Settings/preset persistence and cross-bucket conditions.

Run on the operator's PySide6 native environment, never assume a green logical
simulation proves native frame quality.
"""
from copy import deepcopy

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from core.settings.default_contract import require_canonical_default
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
from core.settings.visualizer_presets import get_custom_preset_index
from ui.tabs.media.extruded_bubble_settings_binding import (
    collect_extruded_bubble_mode_settings, load_extruded_bubble_mode_settings,
)
from ui.tabs.visualizers_tab import VisualizersTab
from ui.widgets.continuous_border import BucketToggle

pytestmark = pytest.mark.qt


@pytest.fixture
def eb_tab(qt_app, tmp_path):
    manager = SettingsManager(organization="SRPSSFocusedTests",
                              application=f"ExtrudedBubbleLazy_{tmp_path.name}",
                              storage_base_dir=tmp_path)
    config = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    config.update({"enabled": True, "visualizers_enabled": True, "mode": "extruded_bubble",
                   "mode_activation": build_visualizer_mode_activation(["extruded_bubble"]),
                   "preset_extruded_bubble": get_custom_preset_index("extruded_bubble")})
    manager.set("widgets", {"spotify_visualizer": config})
    tab = VisualizersTab(manager)
    tab._select_mode_page("extruded_bubble")
    try:
        yield tab, config
    finally:
        tab._flush_pending_visualizer_save()
        tab.close()
        tab.deleteLater()
        QCoreApplication.sendPostedEvents(tab, QEvent.Type.DeferredDelete)
        assert manager.flush(timeout=5.0)


def toggle_bucket(tab, key):
    host = tab._extruded_bubble_settings_container.findChild(
        __import__("PySide6").QtWidgets.QWidget, f"extruded_bubble_bucket_{key}")
    assert host is not None
    toggle = host.findChild(BucketToggle)
    assert toggle is not None
    if not toggle.isChecked():
        toggle.setChecked(True)
    return toggle


def test_closed_buckets_preserve_authoritative_values_through_hydration(eb_tab):
    tab, config = eb_tab
    assert not tab._extruded_bubble_lazy_built
    # New source values must exist in persistence even with zero child widgets.
    payload = {**config, "extruded_bubble_large_size": 1.7,
               "extruded_bubble_small_size": 0.65,
               "extruded_bubble_bead_size": 1.15,
               "extruded_bubble_camera_fov": 37.0}
    load_extruded_bubble_mode_settings(tab, payload)
    assert not hasattr(tab, "extruded_bubble_large_size")
    collected = collect_extruded_bubble_mode_settings(tab)
    for key in ("extruded_bubble_large_size", "extruded_bubble_small_size",
                "extruded_bubble_bead_size", "extruded_bubble_camera_fov"):
        assert collected[key] == pytest.approx(payload[key])
    toggle_bucket(tab, "bubbles")
    assert tab._extruded_bubble_lazy_built == {"bubbles"}
    assert collect_extruded_bubble_mode_settings(tab)["extruded_bubble_large_size"] == pytest.approx(1.7)
    # A changed preset/hydration must update both built and still-unbuilt buckets.
    load_extruded_bubble_mode_settings(tab, {**payload, "extruded_bubble_large_size": .9,
                                           "extruded_bubble_camera_fov": 53.0})
    assert collect_extruded_bubble_mode_settings(tab)["extruded_bubble_large_size"] == pytest.approx(.9)
    assert collect_extruded_bubble_mode_settings(tab)["extruded_bubble_camera_fov"] == pytest.approx(53.)
    toggle_bucket(tab, "camera")
    assert collect_extruded_bubble_mode_settings(tab)["extruded_bubble_camera_fov"] == pytest.approx(53.)


def test_cross_bucket_conditional_survives_out_of_order_expansion(eb_tab):
    tab, config = eb_tab
    load_extruded_bubble_mode_settings(tab, {**config, "extruded_bubble_light_type": "Deep Light"})
    toggle_bucket(tab, "water")    # dependent built BEFORE controlling Light bucket
    assert tab._extruded_bubble_rows["extruded_bubble_surface_brightness"].isHidden()
    toggle_bucket(tab, "light")
    tab.extruded_bubble_light_type.setCurrentText("Sunlit Surface")
    assert not tab._extruded_bubble_rows["extruded_bubble_surface_brightness"].isHidden()
    assert collect_extruded_bubble_mode_settings(tab)["extruded_bubble_light_type"] == "Sunlit Surface"


def test_lighting_coverage_is_independent_and_survives_lazy_hydration(eb_tab):
    """Test-owned BEAM/SCENE edits must round-trip independently of emission.

    Authored preset contents are intentionally NEVER loaded or asserted. Each
    operator-authored preset may legally use different coverage and beam width.
    """
    tab, config = eb_tab
    payload = {**config, "extruded_bubble_lighting_coverage": "SCENE",
               "extruded_bubble_beam_width": 1.75,
               "extruded_bubble_emission_geometry": "BEAM"}
    load_extruded_bubble_mode_settings(tab, payload)
    toggle_bucket(tab, "rays")  # dependent first, controlling bucket still closed
    width_row = tab._extruded_bubble_rows["extruded_bubble_beam_width"]
    path_row = tab._extruded_bubble_rows["extruded_bubble_ray_path"]
    assert width_row.isHidden() and path_row.isHidden()
    toggle_bucket(tab, "light")
    tab.extruded_bubble_lighting_coverage.setCurrentText("BEAM")
    assert not width_row.isHidden() and not path_row.isHidden()
    assert tab.extruded_bubble_beam_width.value() == 175
    tab.extruded_bubble_beam_width.setValue(225)
    tab.extruded_bubble_lighting_coverage.setCurrentText("SCENE")
    saved = collect_extruded_bubble_mode_settings(tab)
    assert saved["extruded_bubble_beam_width"] == 2.25
    assert saved["extruded_bubble_lighting_coverage"] == "SCENE"
    assert saved["extruded_bubble_emission_geometry"] == "BEAM"
    tab._save_settings_now()
    persisted = tab._settings.get("widgets")["spotify_visualizer"]
    for key in ("extruded_bubble_lighting_coverage", "extruded_bubble_beam_width",
                "extruded_bubble_emission_geometry"):
        assert persisted[key] == saved[key]
    load_extruded_bubble_mode_settings(tab, config)
    assert not width_row.isHidden()
    load_extruded_bubble_mode_settings(tab, saved)
    assert width_row.isHidden()
    assert collect_extruded_bubble_mode_settings(tab)["extruded_bubble_beam_width"] == 2.25


def test_every_eb_bucket_constructs_and_hydrates_in_real_settings_page(eb_tab):
    """Native end-to-end catch for a failure in *any* lazily constructed control.

    Earlier tests checked the camera mapper in isolation but missed the full
    Settings path, where exceptions raised from Qt toggle callbacks can be
    printed without failing the test directly. The built-set assertion catches
    those swallowed exceptions as well.
    """
    tab, _config = eb_tab
    spec = __import__('core.settings.visualizer_mode_settings', fromlist=['require_mode_settings']).require_mode_settings('extruded_bubble')
    assert not tab._extruded_bubble_lazy_built
    for bucket in spec.buckets:
        toggle_bucket(tab, bucket.key)
        assert bucket.key in tab._extruded_bubble_lazy_built, (
            f'EB bucket {bucket.key!r} did not finish constructing; inspect Qt slot traceback')
        for control in spec.controls:
            if control.bucket != bucket.key:
                continue
            assert control.key in tab._extruded_bubble_rows, control.key
            assert hasattr(tab, control.key) or hasattr(tab, f'{control.key}_btn'), control.key
            widget = getattr(tab, control.key, None)
            if widget is None:
                widget = getattr(tab, f'{control.key}_btn', None)
            assert widget is not None, control.key
            from PySide6.QtGui import QTextDocument
            for tooltip in (widget.toolTip(), tab._extruded_bubble_rows[control.key].toolTip()):
                rendered = QTextDocument()
                rendered.setHtml(tooltip)
                # Compare the actual human-readable tooltip, not the Qt rich-text
                # wrapper used to keep EB descriptions from becoming one long line.
                assert " ".join(rendered.toPlainText().split()) == " ".join(control.tooltip.split()), control.key
    collected = collect_extruded_bubble_mode_settings(tab)
    assert all(entry.key in collected for entry in spec.controls if entry.bucket)


def test_r34_volume_aim_edits_existing_pose_without_touching_lens(eb_tab):
    """Native Qt event routing: draggable aim must save ordinary yaw/pitch only."""
    tab, _ = eb_tab
    toggle_bucket(tab, "camera")
    view = tab.extruded_bubble_camera_position
    before = collect_extruded_bubble_mode_settings(tab)
    from ui.tabs.media.spec_mode_builder import _eb_base_eye
    from core.constants.extruded_bubble_world import WORLD_HALF
    eye_before = tuple(_eb_base_eye(tab)[i] + view.value()[i]*WORLD_HALF[i] for i in range(3))
    assert view._marker(view._aim()) is not None
    angles = (0.18, -0.11)
    view.cameraAimChanged.emit(angles)
    assert tab._extruded_bubble_loaded_camera_pose['extruded_bubble_turn'] == pytest.approx(angles[0])
    assert tab._extruded_bubble_loaded_camera_pose['extruded_bubble_tilt'] == pytest.approx(angles[1])
    view.cameraAimCommitted.emit(angles)
    after = collect_extruded_bubble_mode_settings(tab)
    assert after['extruded_bubble_turn'] == pytest.approx(angles[0])
    assert after['extruded_bubble_tilt'] == pytest.approx(angles[1])
    assert after['extruded_bubble_camera_fov'] == before['extruded_bubble_camera_fov']
    eye_after = tuple(_eb_base_eye(tab)[i] + view.value()[i]*WORLD_HALF[i] for i in range(3))
    assert eye_after == pytest.approx(eye_before, abs=1e-4)
    # The lens and physical dolly are independently owned and untouched.


def test_r34_deep_ray_source_node_moves_the_one_real_light_source(eb_tab):
    """Deep linked source is never merely a preview; the Light cache must change."""
    tab, cfg = eb_tab
    load_extruded_bubble_mode_settings(tab, {**cfg, 'extruded_bubble_light_type': 'Deep Light'})
    toggle_bucket(tab, 'rays')
    ray = tab.extruded_bubble_ray_path
    assert ray._linked_source is not None
    source = (0.25, -0.35, 0.65)
    ray.linkedSourceChanged.emit(source)
    assert tuple(tab._extruded_bubble_lazy_values['extruded_bubble_light_direction'][:3]) == pytest.approx(source)
    ray.linkedSourceCommitted.emit(source)
    assert tuple(collect_extruded_bubble_mode_settings(tab)['extruded_bubble_light_direction'][:3]) == pytest.approx(source)
    toggle_bucket(tab, 'light')
    assert tuple(tab.extruded_bubble_light_direction.value()[:3]) == pytest.approx(source)


def test_all_3d_camera_editors_admit_legal_eye_before_save_and_aim_in_place(eb_tab):
    from itertools import product
    from core.constants.extruded_bubble_world import WORLD_HALF
    from core.settings.extruded_bubble_camera import CAMERA_CLEARANCE, admit_camera_parameters
    from ui.tabs.media.spec_mode_builder import _eb_base_eye

    tab, config = eb_tab
    rejected = {**config, 'extruded_bubble_turn': .05069708824, 'extruded_bubble_tilt': -.2253050804,
                'extruded_bubble_scene_pan_x': .3, 'extruded_bubble_scene_pan_y': -.2,
                'extruded_bubble_camera_position': [.320911, -1.110771, 1.90208]}
    load_extruded_bubble_mode_settings(tab, rejected)
    assert not tab._extruded_bubble_lazy_built
    collected = collect_extruded_bubble_mode_settings(tab)
    assert collected['extruded_bubble_camera_position'] == pytest.approx(admit_camera_parameters(rejected))
    saves = []
    save = tab._save_settings
    def record_save(*args):
        values = collect_extruded_bubble_mode_settings(tab)
        widget = getattr(tab, 'extruded_bubble_camera_position', None)
        if widget is not None:
            # Inspect synchronously, before the real save: post-signal refresh
            # must not be allowed to repair a stale marker after persistence.
            offset = tuple(widget.value())
            eye = tuple(_eb_base_eye(tab)[i]+offset[i]*WORLD_HALF[i] for i in range(3))
            assert all(abs(v)<=h-CAMERA_CLEARANCE+1e-6 for v,h in zip(eye,WORLD_HALF))
            assert values['extruded_bubble_camera_position'] == pytest.approx(offset)
        saves.append(values)
        return save()
    tab._save_settings = record_save
    for bucket in ('motion', 'light', 'rays', 'camera'):
        toggle_bucket(tab, bucket)

    def check():
        values = collect_extruded_bubble_mode_settings(tab)
        offset = tuple(tab.extruded_bubble_camera_position.value())
        eye = tuple(_eb_base_eye(tab)[i]+offset[i]*WORLD_HALF[i] for i in range(3))
        assert all(abs(v) <= h-CAMERA_CLEARANCE+1e-6 for v,h in zip(eye,WORLD_HALF))
        assert values['extruded_bubble_camera_position'] == pytest.approx(offset)
        for key in ('stream_direction', 'light_direction', 'ray_path', 'camera_position'):
            widget = getattr(tab, 'extruded_bubble_'+key)
            assert tuple(v*h for v,h in zip(widget._eye(),WORLD_HALF)) == pytest.approx(eye)
        return eye

    for corner in product((-8.,8.), repeat=3):
        tab.extruded_bubble_camera_position.setValue(corner)
        tab.extruded_bubble_camera_position.valueChanged.emit(corner)
        check()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    at_wall = check()
    QTest.keyClick(tab.extruded_bubble_camera_position, Qt.Key.Key_Right)
    assert check() == pytest.approx(at_wall)
    QTest.keyClick(tab.extruded_bubble_camera_position, Qt.Key.Key_Left)
    assert check()[0] == pytest.approx(at_wall[0]-.05*WORLD_HALF[0])
    for key in ('stream_direction','light_direction','ray_path'):
        editor = getattr(tab, 'extruded_bubble_'+key)
        editor.cameraOffsetChanged.emit((-8.,8.,-8.))
        before = check()
        editor.cameraAimChanged.emit((-.35,.4))
        assert check() == pytest.approx(before, abs=1e-4)
        editor.cameraOffsetCommitted.emit((8.,-8.,8.))
        check()
    # These controls synchronously save: their markers must already agree.
    tab.extruded_bubble_camera_fov.setValue(62)
    check()
    tab.extruded_bubble_light_type.setCurrentText('Deep Light')
    check()
    assert saves
    saved = collect_extruded_bubble_mode_settings(tab)
    load_extruded_bubble_mode_settings(tab, {**rejected, **saved})
    check()


def test_scene_emission_choice_and_volume_face_repaint_use_one_settings_owner(eb_tab):
    """Native Qt gate: switching the choice updates the real Motion mapper and saves.\n\n    This intentionally does not claim production pixels or performance.\n    """
    from ui.widgets.visual_controls import SceneVolumeMapper
    tab, config = eb_tab
    toggle_bucket(tab, 'motion')
    editor = tab.extruded_bubble_stream_direction
    selector = tab.extruded_bubble_emission_geometry
    assert isinstance(editor, SceneVolumeMapper)
    assert selector.currentText() == 'BEAM'
    assert editor._emission_geometry == 'BEAM'
    selector.setCurrentText('SCENE')
    assert editor._emission_geometry == 'SCENE'
    assert editor._scene_direction[1] != 0
    assert collect_extruded_bubble_mode_settings(tab)['extruded_bubble_emission_geometry'] == 'SCENE'
    # The operator can toggle back without losing the authored Stream nodes.
    prior_path = tuple(editor.value())
    selector.setCurrentText('BEAM')
    assert editor._emission_geometry == 'BEAM'
    assert tuple(editor.value()) == prior_path
    # Saving/hydrating must keep the current choice under the same Settings body.
    load_extruded_bubble_mode_settings(tab, {**config, 'extruded_bubble_emission_geometry': 'SCENE'})
    assert selector.currentText() == 'SCENE'
    assert editor._emission_geometry == 'SCENE'
