"""Open Studio on every preset slot, and the Studio's Save To <Preset> (Edit Preset's Notepad path retired).

Drives the real SettingsDialog (its Visualizers tab, lazy mode bodies and preset sliders) and the real Studio
bridge on the hidden offscreen surface; nothing is shown. Membership comes from the Studio registry and the
preset owner, never a hand list. Writes go only to a tmp copy of a real curated preset folder, reached through
the canonical preset owner's own root, so no authored file is touched; no preset value or wording is pinned.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
from copy import deepcopy
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QAbstractButton

from core.animation import AnimationManager
from core.settings import visualizer_presets as vp
from core.settings.capability_activation import set_widget_family_activated
from core.settings.default_contract import require_canonical_default
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
from core.settings.visualizer_mode_settings import require_mode_settings
from ui.studio.registry import has_studio, studio_modes
from ui.studio.schema import SCALAR

pytestmark = pytest.mark.qt

STUDIO_MODES = tuple(entry.mode_id for entry in studio_modes())
OTHER_MODES = tuple(mode for mode in vp.MODES if not has_studio(mode))
MODE = "waveform_ribbon"          # the Studio driven end to end (its quiet test renderer draws nothing)


def _manager(tmp_path, mode, modes):
    manager = SettingsManager(organization="SRPSSFocusedTests", application="StudioPresetRow",
                              storage_base_dir=tmp_path / "profile")
    config = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    config.update({"enabled": True, "visualizers_enabled": True, "mode": mode,
                   "mode_activation": build_visualizer_mode_activation(list(modes))})
    widgets = manager.get("widgets", {})
    widgets["spotify_visualizer"] = config
    for family in ("media", "visualizers"):
        set_widget_family_activated(widgets, family, True)
    manager.set("widgets", widgets)
    return manager


@pytest.fixture
def real_dialog(qt_app, tmp_path):
    from ui.settings_dialog import SettingsDialog
    from ui.studio.controller import StudioController
    built = []

    def make(mode=MODE, modes=(MODE,)):
        manager = _manager(tmp_path, mode, modes)
        dialog = SettingsDialog(manager, AnimationManager())
        QCoreApplication.processEvents()
        dialog._switch_tab(dialog._tab_index_for_key("visualizers"), animate=False)
        built.append((dialog, manager))
        tab = dialog.visualizers_tab
        tab._select_mode_page(mode)                # mode bodies are lazy: build the one the test starts on
        return dialog, tab

    yield make
    active = StudioController.active()
    if active is not None:
        active.close()
    for dialog, manager in built:
        dialog.close()
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert manager.flush(timeout=5.0)


def _slider(tab, mode):
    return tab._get_visualizer_preset_slider(mode)


def _launcher(tab, mode):
    return getattr(tab, f"_{require_mode_settings(mode).prefix}_studio_button", None)


# ------------------------------------------------------------------------------------- the preset row
def test_every_studio_mode_offers_open_studio_on_curated_and_custom_and_no_edit_preset(real_dialog):
    dialog, tab = real_dialog(STUDIO_MODES[0], STUDIO_MODES + OTHER_MODES)
    assert STUDIO_MODES
    for mode in STUDIO_MODES:
        tab._select_mode_page(mode)
        slider, launcher = _slider(tab, mode), _launcher(tab, mode)
        assert launcher is not None and slider.isAncestorOf(launcher), mode
        assert slider._edit_btn is None, mode                       # Edit Preset is retired here
        row_buttons = {id(b) for b in slider.findChildren(QAbstractButton) if b is not slider._include_starting_view}
        assert row_buttons == {id(launcher), id(slider._custom_action_btn)}, mode   # never two launchers
        for index in (0, slider.custom_index()):
            slider._slider.setValue(index)
            assert launcher.isVisibleTo(tab) and launcher.isEnabled(), (mode, index)


def test_modes_without_a_studio_keep_edit_preset_and_get_no_launcher(real_dialog):
    if not OTHER_MODES:
        pytest.skip("every visualizer mode has a Studio: Edit Preset is gone everywhere")
    dialog, tab = real_dialog(OTHER_MODES[0], OTHER_MODES)
    for mode in OTHER_MODES:
        tab._select_mode_page(mode)
        slider = _slider(tab, mode)
        assert _launcher(tab, mode) is None, mode
        assert slider._edit_btn is not None and slider.isAncestorOf(slider._edit_btn), mode
        slider._slider.setValue(0)
        assert slider._edit_btn.isVisibleTo(tab), mode


# ------------------------------------------------------------------------------- the Studio, offscreen
def _quiet_adapter():
    from ui.studio.waveform_adapter import WaveformStudioAdapter

    class Adapter(WaveformStudioAdapter):
        def create_renderer(self):
            class Quiet:
                def prepare(self, card, frame):
                    return True

                def render(self, card, frame):
                    pass

                def release(self):
                    pass
            return Quiet()

        def recorded_clips(self):
            return ()
    return Adapter()


@pytest.fixture
def offscreen_launch(monkeypatch):
    """The launcher's own click path, with the Studio on the hidden offscreen surface (never a window)."""
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from ui.studio import settings_link
    from ui.studio.surface import OffscreenStudioSurface
    disable_per_call_gl_error_checking()
    real = settings_link.open_mode_studio
    opened = []

    def launch(tab, mode_id):
        surfaces = []

        def factory(controller):
            surfaces.append(OffscreenStudioSurface(controller, size=(960, 600), present_on_show=False))
            return surfaces[-1]
        controller = real(tab, mode_id, adapter=_quiet_adapter(), surface_factory=factory)
        surfaces[0].pump()
        opened.append(controller)
        return controller

    monkeypatch.setattr(settings_link, "open_mode_studio", launch)
    return opened


def test_open_studio_on_a_curated_slot_opens_the_studio_on_that_slot(real_dialog, offscreen_launch):
    dialog, tab = real_dialog()
    slider = _slider(tab, MODE)
    names = vp.get_preset_names(MODE)
    curated = slider.custom_index() - 1                      # the last curated slot (never the default first)
    slider._slider.setValue(curated)
    _launcher(tab, MODE).click()
    bridge = offscreen_launch[-1].bridge
    assert bridge.presetLabel == names[curated]
    assert [p["index"] for p in bridge.presets if p["current"]] == [curated]
    assert bridge.savePresetTarget == ""                     # nothing edited yet: no Save To offered
    assert not hasattr(bridge, "editPresetFile") and not hasattr(bridge, "presetFileEditable")


# ------------------------------------------------------------------------------------ Save To <Preset>
@pytest.fixture
def preset_copy(tmp_path, monkeypatch):
    """A tmp copy of the mode's real curated folder, made the preset owner's root (then restored)."""
    root = tmp_path / "presets"
    shutil.copytree(vp.get_visualizer_presets_dir(MODE), root / MODE)
    monkeypatch.setattr(vp, "_presets_root", lambda: root)
    vp.reload_presets(MODE)
    yield root
    monkeypatch.undo()
    vp.reload_presets(MODE)
    for path in (root / MODE).glob("*.json"):
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)


class _Prompts(list):
    state: dict


@pytest.fixture
def popups(monkeypatch):
    """Patched StyledPopup.exec: records each prompt and answers with ``answer`` (a button value)."""
    from ui.styled_popup import StyledPopup
    seen = _Prompts()
    state = {"answer": "cancel"}

    def fake_exec(popup):
        seen.append({"icon": popup._icon_type, "buttons": [value for _label, value in popup._buttons]})
        popup._result_value = state["answer"] if state["answer"] in seen[-1]["buttons"] else None
        return 1

    monkeypatch.setattr(StyledPopup, "exec", fake_exec)
    seen.state = state
    return seen


def _edited_studio(real_dialog, offscreen_launch, *, crlf=False):
    """Studio opened on a curated slot; one scalar the slot's file authors is changed (moving to Custom)."""
    from ui.studio.waveform_adapter import build_schema
    dialog, tab = real_dialog()
    slider = _slider(tab, MODE)
    curated = slider.custom_index() - 1
    path = vp.get_preset_file_path(MODE, curated)
    if crlf:
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    else:
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    vp.reload_presets(MODE)
    slider._slider.setValue(curated)
    _launcher(tab, MODE).click()
    bridge = offscreen_launch[-1].bridge
    text = path.read_text(encoding="utf-8")
    authored = vp.resolve_preset_payload_settings(MODE, json.loads(text))
    prop = next(p for p in build_schema().properties
                if p.instrument == SCALAR and not p.integer and len(p.path) == 1 and not p.view_pose
                and p.id in authored and text.count(f'"{p.id}"') == 1)
    shown = bridge.values[prop.id]
    span = prop.maximum - prop.minimum
    target = round(prop.minimum + span * (0.25 if float(shown) > prop.minimum + span / 2 else 0.75), 2)
    bridge.commitValue(prop.id, 0, target)
    assert slider.preset_index() == slider.custom_index()          # a Studio edit lands in Custom
    return tab, bridge, curated, path, prop.id, target


@pytest.mark.parametrize("crlf", (False, True), ids=("lf", "crlf"))
def test_save_to_preset_confirms_then_writes_only_the_changed_key_in_the_files_own_shape(
        real_dialog, offscreen_launch, preset_copy, popups, crlf):
    tab, bridge, curated, path, key, target = _edited_studio(real_dialog, offscreen_launch, crlf=crlf)
    assert bridge.savePresetTarget == vp.get_preset_names(MODE)[curated]
    before = path.read_bytes()

    popups.state["answer"] = "cancel"                             # cancel writes nothing
    bridge.saveToPreset()
    assert [p["icon"] for p in popups] == ["question"] and "save" in popups[0]["buttons"]
    assert path.read_bytes() == before

    popups.state["answer"] = "save"
    bridge.saveToPreset()
    assert [p["icon"] for p in popups] == ["question", "question"]
    after = path.read_bytes()
    old_text, new_text = before.decode("utf-8"), after.decode("utf-8")
    assert ("\r\n" in new_text) == crlf and new_text.count("\n") == old_text.count("\n")
    assert new_text.endswith("\n") == old_text.endswith("\n")
    old_lines, new_lines = old_text.splitlines(), new_text.splitlines()
    differing = [i for i, (a, b) in enumerate(zip(old_lines, new_lines)) if a != b]
    assert len(old_lines) == len(new_lines) and len(differing) == 1 and f'"{key}"' in new_lines[differing[0]]
    from core.settings.visualizer_preset_file import key_order
    old_payload, new_payload = json.loads(old_text), json.loads(new_text)
    assert key_order(old_payload) == key_order(new_payload)
    old_resolved = vp.resolve_preset_payload_settings(MODE, old_payload)
    new_resolved = vp.resolve_preset_payload_settings(MODE, new_payload)
    assert new_resolved[key] == pytest.approx(target)
    assert {k: v for k, v in new_resolved.items() if k != key} == {k: v for k, v in old_resolved.items() if k != key}
    assert vp.get_preset_settings(MODE, curated)[key] == pytest.approx(target)    # presets were reloaded
    assert _slider(tab, MODE).preset_index() == _slider(tab, MODE).custom_index()  # Custom stays as it was

    bridge.saveToPreset()                                          # now identical: no prompt, no write
    assert len(popups) == 2 and path.read_bytes() == after


def test_save_to_preset_on_a_read_only_file_gives_a_clear_message_and_writes_nothing(
        real_dialog, offscreen_launch, preset_copy, popups):
    tab, bridge, curated, path, key, target = _edited_studio(real_dialog, offscreen_launch)
    before = path.read_bytes()
    os.chmod(path, stat.S_IREAD)
    try:
        popups.state["answer"] = "save"
        bridge.saveToPreset()
    finally:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    assert [p["icon"] for p in popups] == ["error"]                # the message, never a save prompt or crash
    assert path.read_bytes() == before
    # Negative control: the same edit on a writable file prompts instead.
    popups.state["answer"] = "cancel"
    bridge.saveToPreset()
    assert [p["icon"] for p in popups] == ["error", "question"]


def test_save_to_is_not_offered_when_the_studio_opened_on_custom(real_dialog, offscreen_launch):
    dialog, tab = real_dialog()
    slider = _slider(tab, MODE)
    slider._slider.setValue(slider.custom_index())
    _launcher(tab, MODE).click()
    bridge = offscreen_launch[-1].bridge
    assert bridge.savePresetTarget == ""                     # Custom's source is unknown: only Save Preset As


# --------------------------------------------------------------------------- the shared preset-file owner
def test_setting_changes_patch_every_loaded_section_in_place_and_add_nothing_else():
    from core.settings.visualizer_preset_file import apply_setting_changes_in_place, key_order
    spec = require_mode_settings(MODE)
    keys = [c.key for c in spec.controls][:3]
    assert len(keys) == 3
    payload = {"note": "kept", "name": "N", "snapshot": {"widgets": {"spotify_visualizer": {
        keys[2]: 1, "inert": "x", keys[0]: 2}}},
        "settings": {"widgets.spotify_visualizer." + keys[0]: 3, "other.key": 4}}
    original = deepcopy(payload)
    apply_setting_changes_in_place(payload, MODE, {keys[0]: 9})
    section = payload["snapshot"]["widgets"]["spotify_visualizer"]
    assert section[keys[0]] == 9 and section[keys[2]] == 1 and section["inert"] == "x"
    assert payload["settings"]["widgets.spotify_visualizer." + keys[0]] == 9
    assert payload["settings"]["other.key"] == 4 and payload["note"] == "kept"
    original["snapshot"]["widgets"]["spotify_visualizer"][keys[0]] = 9
    original["settings"]["widgets.spotify_visualizer." + keys[0]] = 9
    assert payload == original and key_order(payload) == key_order(original)
