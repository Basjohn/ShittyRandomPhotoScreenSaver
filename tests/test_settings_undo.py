"""Settings' session undo/redo (``ui/settings_undo.py``) on the real SettingsDialog.

User gestures on sliders and visual editors are undoable edits; values set by loading or by an undo are not. Undo
applies the old value as a user edit would, so the setting is saved back. Test-owned profile; no authored preset or
default values are asserted.
"""
from copy import deepcopy

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from core.animation import AnimationManager
from core.settings.capability_activation import set_widget_family_activated
from core.settings.default_contract import require_canonical_default
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
from ui.settings_dialog import SettingsDialog
from ui.settings_undo import settings_undo_for
from ui.tabs.shared_styles import NoWheelSlider
from ui.widgets.visual_controls import RangeSlider

pytestmark = pytest.mark.qt


@pytest.fixture
def dialog(tmp_path):
    QApplication.instance() or QApplication([])
    manager = SettingsManager(application="settings_undo", storage_base_dir=tmp_path)
    config = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    config.update({"enabled": True, "visualizers_enabled": True, "mode": "extruded_bubble",
                   "mode_activation": build_visualizer_mode_activation(["extruded_bubble"])})
    widgets = manager.get("widgets", {})
    widgets["spotify_visualizer"] = config
    for family in ("media", "visualizers"):
        set_widget_family_activated(widgets, family, True)
    manager.set("widgets", widgets)
    manager.set("sources.folders", [str(tmp_path)])
    dialog = SettingsDialog(manager, AnimationManager())
    QCoreApplication.processEvents()
    index = dialog._tab_index_for_key("visualizers")
    dialog._switch_tab(index, animate=False)
    QCoreApplication.processEvents()
    yield dialog, manager, dialog.content_stack.widget(index)
    dialog.close()
    QCoreApplication.processEvents()
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert manager.flush(timeout=5.0)


def _steppable(page, kind):
    for control in page.findChildren(kind):
        if kind is NoWheelSlider and control.isEnabled() and control.minimum() < control.value() < control.maximum():
            return control
        if kind is RangeSlider and control.isEnabled():
            low, high = control.value()
            if control._min < low < high:
                return control
    pytest.skip(f"no steppable {kind.__name__} on the page")


def _visualizer_settings(manager):
    return deepcopy(manager.get("widgets", {}).get("spotify_visualizer", {}))


def test_the_dialog_owns_undo_and_redo_shortcuts(dialog):
    owner_dialog, _manager, page = dialog
    owner = settings_undo_for(page)
    assert owner is not None and owner is owner_dialog._settings_undo
    keys = {shortcut.key().toString() for shortcut in owner._shortcuts}
    assert QKeySequence(QKeySequence.StandardKey.Undo).toString() in keys
    assert "Ctrl+Shift+Z" in keys


def test_a_slider_step_undoes_and_redoes_and_saves_back(dialog):
    _owner_dialog, manager, page = dialog
    owner = settings_undo_for(page)
    slider = _steppable(page, NoWheelSlider)
    original, saved_before = slider.value(), _visualizer_settings(manager)
    QTest.keyClick(slider, Qt.Key.Key_Right)
    changed = slider.value()
    assert changed != original and owner.can_undo
    assert owner.undo()
    assert slider.value() == original
    assert _visualizer_settings(manager) == saved_before         # the undo was saved like any edit
    assert not owner.can_undo and owner.can_redo
    assert owner.redo()
    assert slider.value() == changed


def test_values_set_by_loading_or_by_undo_are_not_edits(dialog):
    _owner_dialog, _manager, page = dialog
    owner = settings_undo_for(page)
    slider = _steppable(page, NoWheelSlider)
    slider.setValue(slider.value() + 1)                          # as loading or a preset does
    assert not owner.can_undo
    QTest.keyClick(slider, Qt.Key.Key_Left)
    assert owner.undo()
    assert not owner.can_undo                                    # undo's own setValue recorded nothing


def test_a_range_control_step_is_undoable(dialog):
    """Range (and Triangle, Direction, the scene mappers) record through their shared base: a key step on one placed
    in the real dialog undoes to its old value and re-commits it (the page saves from that commit)."""
    _owner_dialog, _manager, page = dialog
    owner = settings_undo_for(page)
    control = RangeSlider(0, 100, page)
    control.setValue((20, 60))
    commits = []
    control.valueCommitted.connect(commits.append)
    control.show()
    control.setFocus()
    QTest.keyClick(control, Qt.Key.Key_Right)
    stepped = control.value()
    assert stepped != (20, 60) and owner.can_undo
    assert owner.undo()
    assert control.value() == (20, 60) and commits[-1] == (20, 60)
    assert owner.redo() and control.value() == stepped


def test_a_picked_colour_is_undoable(dialog, monkeypatch):
    from ui.styled_popup import ColorSwatchButton, StyledColorPicker
    _owner_dialog, _manager, page = dialog
    owner = settings_undo_for(page)
    swatch = next((s for s in page.findChildren(ColorSwatchButton) if s._auto_picker), None)
    if swatch is None:
        pytest.skip("no colour swatch on the page")
    original = swatch.color().getRgb()
    seen = []
    swatch.color_changed.connect(lambda c: seen.append(c.getRgb()))
    picked = QColor(12, 34, 56, 255) if original != (12, 34, 56, 255) else QColor(65, 43, 21, 255)
    monkeypatch.setattr(StyledColorPicker, "get_color", staticmethod(lambda *a, **k: QColor(picked)))
    swatch._open_picker()
    assert swatch.color().getRgb() == picked.getRgb()
    assert owner.undo()
    assert swatch.color().getRgb() == original and seen[-1] == original   # the page hears it, as for a pick


def test_an_undo_inside_a_gesture_is_not_recorded_again(dialog):
    _owner_dialog, _manager, page = dialog
    owner = settings_undo_for(page)
    slider = _steppable(page, NoWheelSlider)
    QTest.keyClick(slider, Qt.Key.Key_Right)
    QTest.keyPress(slider, Qt.Key.Key_Up)        # a gesture opens ..
    owner.undo()                                 # .. an undo lands inside it ..
    QTest.keyRelease(slider, Qt.Key.Key_Up)      # .. and its end records nothing
    assert owner.can_redo


def test_controls_outside_settings_record_nothing():
    QApplication.instance() or QApplication([])
    slider = NoWheelSlider(Qt.Orientation.Horizontal)
    slider.setRange(0, 10)
    slider.setValue(5)
    QTest.keyClick(slider, Qt.Key.Key_Right)     # no Settings dialog: nothing to record into, no error
    assert slider.value() == 6
    assert settings_undo_for(slider) is None
