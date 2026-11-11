"""A stored preset reference that the catalogue no longer resolves falls back at the owner (1C.1, R-189).

Contract (``Docs/Architecture/Persisted_Input_Compatibility.md``, "Visualizer preset references"): the stored
reference is the slot index plus the preset's identity (its authored name without the slot number) and a signature
of the catalogue it was chosen from. While the catalogue is unchanged the index is the user's choice; when it
changed, the identity decides: the same preset wherever it now sits, Custom as Custom, Preset 1 when it is gone. One
log line, no error, and the settings load stores the repaired reference once.

Every case runs on a temporary copy of the mode's own curated folder, reached through the canonical preset owner's
root; presets are removed, renumbered and added in that copy only. Names, counts and values are read from the
catalogue, never written here.
"""
from __future__ import annotations

import json
import logging
import shutil
import uuid
from pathlib import Path

import pytest

from core.settings import visualizer_presets as vp
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import get_preset_key
from core.settings.visualizer_preset_indices import PRESET_REFERENCES_KEY, preset_identity

_PREFIX = "widgets.spotify_visualizer"


@pytest.fixture(autouse=True)
def _restore_registry():
    registries = (vp._PRESETS, vp._PRESET_SOURCE_PATHS, vp._PRESET_SOURCE_SLOTS, vp._LOADED_SOURCE_PATHS,
                  vp._LOADED_FOLDER_STATE)
    originals = [{mode: (dict(value) if isinstance(value, dict) else
                         (list(value) if isinstance(value, list) else value)) for mode, value in registry.items()}
                 for registry in registries]
    yield
    for registry, original in zip(registries, originals):
        registry.clear()
        registry.update(original)


def _curated_modes() -> list[str]:
    return [mode for mode in vp.MODES if vp.get_custom_preset_index(mode) >= 2]


class _Tree:
    """A copy of one mode's curated folder made the preset owner's root."""

    def __init__(self, tmp_path: Path, monkeypatch, mode: str) -> None:
        self.mode = mode
        self.root = tmp_path / "presets"
        self.folder = self.root / mode
        shutil.copytree(vp.get_visualizer_presets_dir(mode), self.folder)
        monkeypatch.setattr(vp, "_presets_root", lambda: self.root)
        monkeypatch.setattr(vp, "_snapshot_presets_root", lambda: tmp_path / "no_overrides")
        vp.reload_presets(mode)

    def files(self) -> list[Path]:
        return [vp.get_preset_file_path(self.mode, index) for index in range(vp.get_custom_preset_index(self.mode))]

    def add(self, stem_suffix: str) -> Path:
        """A user-authored preset (Save Preset As): a copy of the first file, after the highest slot."""
        source = self.files()[0]
        payload = json.loads(source.read_text(encoding="utf-8"))
        slot = vp.get_next_visualizer_preset_ordinal(self.mode)
        path = self.folder / f"preset_{slot}_{stem_suffix}.json"
        payload.pop("name", None)
        payload["preset_index"] = slot - 1
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        vp.reload_presets(self.mode)
        return path

    def renumber(self, path: Path, slot: int) -> Path:
        """The same preset moved to another slot number (its file renamed, as round 2 did)."""
        suffix = path.stem.split("_", 2)[2] if path.stem.count("_") >= 2 else "moved"
        target = path.with_name(f"preset_{slot}_{suffix}.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.pop("name", None)
        payload["preset_index"] = slot - 1
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        path.unlink()
        return target


def _identities(mode: str) -> list[str]:
    return [preset_identity(name) for name in vp.get_preset_names(mode)]


def _disk_identities(mode: str, folder: Path) -> list[str]:
    """What the folder holds now, read with the owner's own parser (the registry is not touched)."""
    slots = {}
    for path in folder.glob("*.json"):
        parsed = vp._parse_preset_payload(path, json.loads(path.read_text(encoding="utf-8")), mode,
                                          prefer_filename_index=True, prefer_filename_name=True)
        if parsed:
            slots[parsed[0]] = preset_identity(parsed[1].name)
    return [slots[slot] for slot in sorted(slots)] + [preset_identity("Custom")]


def _manager(tmp_path: Path, name: str) -> SettingsManager:
    return SettingsManager(organization="SRPSSFocusedTests", application=f"PresetRefs_{name}",
                           storage_base_dir=tmp_path / "profile")


def _store(manager: SettingsManager, mode: str, index: int) -> None:
    widgets = manager.get("widgets", {})
    section = dict(widgets.get("spotify_visualizer", {}))
    section[get_preset_key(mode)] = index
    widgets["spotify_visualizer"] = section
    manager.set("widgets", widgets)
    assert manager.flush(timeout=5.0)


def _stored(manager: SettingsManager, mode: str) -> tuple[int, dict]:
    section = manager.get("widgets", {})["spotify_visualizer"]
    return int(section[get_preset_key(mode)]), dict(section.get(PRESET_REFERENCES_KEY, {}).get(mode, {}))


# --------------------------------------------------------------------------------------- every curated mode
@pytest.mark.parametrize("mode", _curated_modes())
def test_every_mode_follows_its_preset_through_a_catalogue_change(tmp_path, monkeypatch, caplog, mode):
    tree = _Tree(tmp_path, monkeypatch, mode)
    user = tree.add("refs_test_user")                  # a user-authored preset, last before Custom
    before = _identities(mode)
    custom = vp.get_custom_preset_index(mode)
    picks = {"first": 0, "moved": 1, "removed": custom - 2, "user": custom - 1, "custom": custom}
    stored = {}
    for case, index in picks.items():
        manager = _manager(tmp_path / case, case)
        _store(manager, mode, index)
        stored[case] = (manager, before[index])
        assert _stored(manager, mode) == (index, {"preset": before[index],
                                                  "catalogue": _stored(manager, mode)[1]["catalogue"]})

    # The catalogue changes: one curated preset is removed, another renumbered past the user's preset.
    files = tree.files()
    files[picks["removed"]].unlink()
    tree.renumber(files[picks["moved"]], vp.get_next_visualizer_preset_ordinal(mode) + 3)
    vp.reload_presets(mode)
    after = _identities(mode)
    assert before[picks["removed"]] not in after and after.index(before[picks["moved"]]) != picks["moved"]

    caplog.set_level(logging.INFO, logger="core.settings.visualizer_preset_indices")
    for case, (manager, identity) in stored.items():
        reloaded = _manager(tmp_path / case, case)       # a fresh load: the one repair
        index, reference = _stored(reloaded, mode)
        from core.settings.visualizer_preset_indices import get_missing_preset_fallback_index
        expected = after.index(identity) if identity in after else get_missing_preset_fallback_index(mode)
        assert index == expected, (case, identity, after)
        assert reference["preset"] == after[index]
        again = _manager(tmp_path / case, case)          # idempotent: a second load changes nothing
        assert _stored(again, mode) == (index, reference)
    lines = [r.getMessage() for r in caplog.records if "[VIS_PRESETS]" in r.getMessage()]
    assert any(before[picks["removed"]] in line for line in lines)
    assert len(lines) == len(set(lines))                 # each repair reported once
    assert user.is_file()


def test_an_old_profile_without_references_keeps_its_index_and_gains_references(tmp_path, monkeypatch):
    """The bridge for profiles written before 12 Nov 2026: the index is all they have; an index past the catalogue
    falls back to Preset 1; either way the load stores a reference, once."""
    mode = _curated_modes()[0]
    _Tree(tmp_path, monkeypatch, mode)
    fixture = json.loads((Path(__file__).parent / "fixtures" / "visualizer_preset_reference_old_profile.json")
                         .read_text(encoding="utf-8"))
    custom = vp.get_custom_preset_index(mode)
    for label, raw in (("in_range", 1), ("past_catalogue", custom + 7)):
        manager = _manager(tmp_path / label, label)
        widgets = manager.get("widgets", {})
        section = dict(widgets["spotify_visualizer"])
        section.update(fixture)
        section.pop(PRESET_REFERENCES_KEY, None)
        section[get_preset_key(mode)] = raw
        widgets["spotify_visualizer"] = section
        # Written raw (no normalisation), exactly as an older build left the file.
        manager._settings.setValue("widgets", widgets)
        manager._settings.sync()
        reloaded = _manager(tmp_path / label, label)
        index, reference = _stored(reloaded, mode)
        from core.settings.visualizer_preset_indices import get_missing_preset_fallback_index
        assert index == (raw if raw <= custom else get_missing_preset_fallback_index(mode))
        assert reference["preset"] == _identities(mode)[index]


# ------------------------------------------------------------------- the real Settings dialog and Studio
@pytest.fixture
def popups(monkeypatch):
    from ui.styled_popup import StyledPopup
    seen = []

    def fake_exec(popup):
        seen.append(popup.windowTitle())
        popup._result_value = "ok"
        return 1
    monkeypatch.setattr(StyledPopup, "exec", fake_exec)
    return seen


@pytest.mark.qt
@pytest.mark.parametrize("case", ["preset_1", "renumbered", "removed", "user_authored"])
def test_settings_and_studio_open_on_the_followed_preset_with_no_error(qt_app, tmp_path, monkeypatch, popups,
                                                                        case):
    from PySide6.QtCore import QCoreApplication, QEvent
    from core.animation import AnimationManager
    from core.settings.capability_activation import set_widget_family_activated
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_preset_indices import get_missing_preset_fallback_index
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    from tests.test_spectrum_studio import LightAdapter
    from ui.settings_dialog import SettingsDialog
    from ui.studio.controller import StudioController
    from ui.studio.settings_link import open_mode_studio
    from ui.studio.surface import OffscreenStudioSurface

    mode = "spectrum"
    tree = _Tree(tmp_path, monkeypatch, mode)
    user = tree.add("refs_test_user")
    before = _identities(mode)
    custom = vp.get_custom_preset_index(mode)
    index = {"preset_1": 0, "renumbered": 1, "removed": custom - 2, "user_authored": custom - 1}[case]
    manager = _manager(tmp_path, case)
    widgets = manager.get("widgets", {})
    section = dict(widgets["spotify_visualizer"])
    section.update({"enabled": True, "visualizers_enabled": True, "mode": mode,
                    "mode_activation": build_visualizer_mode_activation([mode])})
    widgets["spotify_visualizer"] = section
    for family in ("media", "visualizers"):
        set_widget_family_activated(widgets, family, True)
    manager.set("widgets", widgets)
    _store(manager, mode, index)
    identity = before[index]

    files = tree.files()
    if case == "renumbered":
        tree.renumber(files[1], vp.get_next_visualizer_preset_ordinal(mode) + 3)
    if case == "removed":
        files[custom - 2].unlink()
    # The catalogue on disk changed after this process loaded it (an install, another process's save).
    after_disk = _disk_identities(mode, tree.folder)
    profile = _manager(tmp_path, case)
    dialog = SettingsDialog(profile, AnimationManager())
    try:
        QCoreApplication.processEvents()
        dialog._switch_tab(dialog._tab_index_for_key("visualizers"), animate=False)
        tab = dialog.visualizers_tab
        tab._select_mode_page(mode)
        assert _identities(mode) == after_disk          # the page opened on what is on disk now
        expected = (after_disk.index(identity) if identity in after_disk
                    else get_missing_preset_fallback_index(mode))
        slider = tab._get_visualizer_preset_slider(mode)
        assert slider.preset_index() == expected, (case, identity, after_disk)
        disable_per_call_gl_error_checking()
        surfaces = []

        def factory(controller):
            surfaces.append(OffscreenStudioSurface(controller, size=(960, 600), present_on_show=False))
            return surfaces[-1]
        controller = open_mode_studio(tab, mode, adapter=LightAdapter(), surface_factory=factory)
        surfaces[0].pump(2)
        assert controller.state == "presented"
        assert preset_identity(controller.session.preset_label) == after_disk[expected]
        controller.close()
    finally:
        active = StudioController.active()
        if active is not None:
            active.close()
        dialog.close()
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert profile.flush(timeout=5.0)
    assert popups == []                                   # never a dialog
    if case == "user_authored":
        assert user.is_file()
