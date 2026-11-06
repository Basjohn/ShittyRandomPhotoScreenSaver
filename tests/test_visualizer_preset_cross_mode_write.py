"""A preset-file write never crosses modes (R-174: Neon Lake's Preset 1 overwritten with Bubble values, 6 Nov).

The operator's Save Preset As on Bubble's Custom wrote a Bubble payload over
``shockwave_grid/preset_1_synthwave.json``: the file dialog puts no bound on the folder, and the writer checked
nothing and logged nothing. Every preset-file write now goes through the owner
(``core.settings.visualizer_preset_file``), which refuses a target outside the mode's own folder or a file of another
mode, and logs one info line per write. Writes go only to a tmp copy of the real curated tree, made the preset owner's
root, so no authored file is touched. The Settings tab is never shown.
"""
from __future__ import annotations

import json
import logging
import shutil

import pytest

from core.settings import visualizer_presets as vp
from core.settings import visualizer_preset_file as preset_file

SOURCE, VICTIM = "bubble", "shockwave_grid"


@pytest.fixture
def preset_root(tmp_path, monkeypatch):
    root = tmp_path / "presets"
    shutil.copytree(vp.get_visualizer_presets_dir(), root)          # every mode keeps its presets for a reload
    monkeypatch.setattr(vp, "_presets_root", lambda: root)
    vp.reload_presets()
    yield root
    monkeypatch.undo()
    vp.reload_presets()


def _victim_file():
    path = vp.get_preset_file_path(VICTIM, 0)
    assert path is not None and json.loads(path.read_text(encoding="utf-8"))["mode"] == VICTIM
    return path


def _bubble_payload(name="x"):
    return {"mode": SOURCE, "name": name, "preset_index": 0, "visualizer_preset_mode": SOURCE,
            "snapshot": {"widgets": {"spotify_visualizer": {"bubble_specular_direction": "top"}}}}


# --------------------------------------------------------------------------------------------- the owner's check
def test_a_payload_of_one_mode_is_never_written_over_another_modes_preset(preset_root):
    victim = _victim_file()
    before = victim.read_bytes()
    with pytest.raises(preset_file.PresetModeMismatch):
        preset_file.write_new_preset_file(SOURCE, victim, _bubble_payload())        # the 21:45:04 write
    with pytest.raises(preset_file.PresetModeMismatch):
        preset_file.write_new_preset_file(VICTIM, victim, _bubble_payload())        # a mislabelled payload
    assert victim.read_bytes() == before


def test_a_new_preset_outside_the_modes_own_folder_is_refused(preset_root):
    stray = preset_root / VICTIM / "preset_99_new.json"
    with pytest.raises(preset_file.PresetModeMismatch):
        preset_file.write_new_preset_file(SOURCE, stray, _bubble_payload())
    assert not stray.exists()


def test_a_write_into_the_modes_own_folder_is_written_and_logged_negative_control(preset_root, caplog):
    target = preset_root / SOURCE / "preset_99_new.json"
    with caplog.at_level(logging.INFO):
        preset_file.write_new_preset_file(SOURCE, target, _bubble_payload())
    assert json.loads(target.read_text(encoding="utf-8"))["mode"] == SOURCE
    lines = [r.getMessage() for r in caplog.records if "wrote preset file" in r.getMessage()]
    assert len(lines) == 1 and f"mode={SOURCE}" in lines[0] and str(target) in lines[0]


def test_save_to_preset_refuses_a_slot_whose_file_holds_another_modes_preset(preset_root):
    """The patch path (Save To <Preset>, Overwrite) checks the file it patches too."""
    victim = _victim_file()
    victim.write_text(json.dumps(_bubble_payload("Preset 1 (Synthwave)"), indent=2), encoding="utf-8")
    vp.reload_presets(VICTIM)
    before = victim.read_bytes()
    with pytest.raises(preset_file.PresetModeMismatch):
        preset_file.save_changes_to_preset(VICTIM, 0, {}, starting_view={"turn": 0.1})
    assert victim.read_bytes() == before


# ------------------------------------------------------------------------- the operator's path: Save Preset As
@pytest.fixture
def bubble_tab(qt_app, tmp_path, preset_root):
    from PySide6.QtWidgets import QDialog, QVBoxLayout
    from core.settings.settings_manager import SettingsManager
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui.tabs.visualizers_tab import VisualizersTab
    manager = SettingsManager(organization="SRPSSFocusedTests", application="PresetCrossMode",
                              storage_base_dir=tmp_path / "profile")
    manager.set("widgets", {"spotify_visualizer": {
        "enabled": True, "visualizers_enabled": True, "mode": SOURCE,
        "mode_activation": build_visualizer_mode_activation([SOURCE, VICTIM]),
        f"preset_{SOURCE}": get_custom_preset_index(SOURCE)}})
    dialog = QDialog()                                               # never shown
    QVBoxLayout(dialog).addWidget(tab := VisualizersTab(manager))
    tab._select_mode_page(SOURCE)
    yield tab
    dialog.deleteLater()
    qt_app.processEvents()
    assert manager.flush(timeout=5.0)


@pytest.fixture
def prompts(monkeypatch):
    from ui.styled_popup import StyledPopup
    seen = []

    def fake_exec(popup):
        seen.append(popup._icon_type)
        popup._result_value = "ok"
        return 1
    monkeypatch.setattr(StyledPopup, "exec", fake_exec)
    return seen


def _save_as(tab, monkeypatch, target):
    from ui.tabs.media import preset_slider
    monkeypatch.setattr(preset_slider.QFileDialog, "getSaveFileName", lambda *_a, **_k: (str(target), ""))
    slider = tab._get_visualizer_preset_slider(SOURCE)
    assert slider.preset_index() == slider.custom_index()
    return slider._save_custom_preset_as()


def test_save_preset_as_on_bubble_never_overwrites_neon_lakes_preset_1(bubble_tab, monkeypatch, prompts):
    """The 6 Nov loss, through the preset row's own Save Preset As: the dialog answered Neon Lake's Preset 1."""
    victim = _victim_file()
    before = victim.read_bytes()
    _save_as(bubble_tab, monkeypatch, victim)
    assert victim.read_bytes() == before, "a Bubble payload was written over Neon Lake's preset"
    assert prompts == ["error"]                                      # told, nothing written


def test_save_preset_as_into_bubbles_own_folder_still_saves_negative_control(bubble_tab, monkeypatch, prompts,
                                                                             preset_root):
    target = preset_root / SOURCE / "preset_99_mine.json"
    _save_as(bubble_tab, monkeypatch, target)
    assert json.loads(target.read_text(encoding="utf-8"))["mode"] == SOURCE
    assert prompts == ["success"]
