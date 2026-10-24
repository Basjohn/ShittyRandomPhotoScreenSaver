"""Neon Lake's Settings Camera Position editor is the shared framed-camera editor (real Settings body)."""
from copy import deepcopy

import pytest
from PySide6.QtCore import QCoreApplication, QEvent

from core.settings.default_contract import require_canonical_default
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
from core.settings.visualizer_presets import get_custom_preset_index
from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings, load_spec_mode_settings
from ui.tabs.visualizers_tab import VisualizersTab
from ui.widgets.continuous_border import BucketToggle

pytestmark = pytest.mark.qt
MODE = "shockwave_grid"


@pytest.fixture
def neon_tab(qt_app, tmp_path):
    manager = SettingsManager(organization="SRPSSFocusedTests", application=f"NeonCamera_{tmp_path.name}",
                              storage_base_dir=tmp_path)
    config = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    config.update({"enabled": True, "visualizers_enabled": True, "mode": MODE,
                   "mode_activation": build_visualizer_mode_activation([MODE]),
                   "preset_shockwave_grid": get_custom_preset_index(MODE)})
    manager.set("widgets", {"spotify_visualizer": config})
    tab = VisualizersTab(manager)
    tab._select_mode_page(MODE)
    try:
        yield tab, config
    finally:
        tab._flush_pending_visualizer_save()
        tab.close()
        tab.deleteLater()
        QCoreApplication.sendPostedEvents(tab, QEvent.Type.DeferredDelete)
        assert manager.flush(timeout=5.0)


def _open_camera(tab):
    from PySide6.QtWidgets import QWidget
    host = tab._shockwave_grid_settings_container.findChild(QWidget, f"{MODE}_bucket_camera")
    assert host is not None
    toggle = host.findChild(BucketToggle)
    if not toggle.isChecked():
        toggle.setChecked(True)
    return tab.shockwave_grid_camera_position


def _eye(tab, offset):
    from core.settings.neon_lake_camera import SPEC
    from ui.tabs.media import framed_camera_editor as fce
    base = fce.base_eye(tab, MODE)
    return tuple(base[i] + offset[i] * SPEC.offset_scale[i] for i in range(3))


def test_camera_position_editor_uses_the_neon_spec_and_keeps_the_eye_above_the_land(neon_tab):
    from core.settings.neon_lake_camera import SPEC, floor
    from ui.tabs.media import framed_camera_editor as fce
    tab, config = neon_tab
    editor = _open_camera(tab)
    assert editor._camera_spec is SPEC
    assert editor._references   # the basin outline is drawn inside the eye box
    saves = []
    tab._save_settings = lambda *args: saves.append(collect_spec_mode_settings(tab, MODE))
    # Push the eye far below the water: the editor admits the bounded eye before saving.
    fce.set_offset(tab, MODE, (0.0, -8.0, 0.0), commit=True)
    offset = tuple(editor.value())
    eye = _eye(tab, offset)
    values = {**config, **saves[-1]}
    assert eye[1] >= floor(values)(eye[0], eye[2]) + SPEC.clearance - 1e-6
    assert saves[-1]["shockwave_grid_camera_position"] == pytest.approx(offset)
    assert offset[1] > -8.0


def test_aiming_turns_the_neon_camera_in_place(neon_tab):
    from ui.tabs.media import framed_camera_editor as fce
    tab, config = neon_tab
    editor = _open_camera(tab)
    tab._save_settings = lambda *args: None
    before = _eye(tab, tuple(editor.value()))
    fce.set_aim(tab, MODE, (0.12, 0.05), commit=True)
    assert fce.camera_angles(tab, MODE) == pytest.approx((0.12, 0.05))
    # Offsets persist at 6 decimals (x the 7-unit offset scale): the eye stays within a few micro-units.
    assert _eye(tab, tuple(editor.value())) == pytest.approx(before, abs=1e-5)
    collected = collect_spec_mode_settings(tab, MODE)
    assert (collected["shockwave_grid_turn"], collected["shockwave_grid_tilt"]) == pytest.approx((0.12, 0.05))
    # Reloading the saved body keeps the aimed pose and the editor's eye.
    load_spec_mode_settings(tab, MODE, {**config, **collected})
    assert fce.camera_angles(tab, MODE) == pytest.approx((0.12, 0.05))


def test_ctrl_z_steps_back_through_the_last_few_camera_gestures(neon_tab, qtbot):
    from PySide6.QtCore import Qt
    from ui.tabs.media import framed_camera_editor as fce
    from ui.widgets.edit_history import EDIT_HISTORY_DEPTH
    tab, _config = neon_tab
    editor = _open_camera(tab)
    tab._save_settings = lambda *args: None
    states = [fce.camera_state(tab, MODE)]
    for step in range(EDIT_HISTORY_DEPTH + 1):     # one more gesture than the history keeps
        fce.set_offset(tab, MODE, (0.05 * (step + 1), 0.1, -0.05 * step), commit=True)
        fce.set_aim(tab, MODE, (0.03 * (step + 1), 0.04), commit=True)
        states.append(fce.camera_state(tab, MODE))
    undone = []
    for _ in range(2 * EDIT_HISTORY_DEPTH + 2):    # past the bound: further presses do nothing
        qtbot.keyClick(editor, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        undone.append(fce.camera_state(tab, MODE))
    # Each gesture's aim is one action; the bounded history reaches back EDIT_HISTORY_DEPTH actions.
    assert undone[-1] == undone[EDIT_HISTORY_DEPTH - 1] != states[-1]
    assert tuple(editor.value()) == pytest.approx(undone[-1][0], abs=1e-6)
    qtbot.keyClick(editor, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    assert fce.camera_state(tab, MODE) == undone[EDIT_HISTORY_DEPTH - 2]
    # A new gesture after undo starts a fresh branch: nothing left to redo.
    fce.set_aim(tab, MODE, (0.2, 0.1), commit=True)
    branched = fce.camera_state(tab, MODE)
    assert not fce.redo(tab, MODE) and fce.camera_state(tab, MODE) == branched
