"""Context menu "Save Image": destination, byte-for-byte copy, and no live source rebuild."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from core.sources.image_collection import (
    COLLECTION_FOLDER_NAME, resolve_collection_target, save_image_to_collection,
)


class _Settings:
    def __init__(self, values, on_set=None):
        self.values = values
        self.on_set = on_set
        self.saved = 0

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value
        if self.on_set is not None:
            self.on_set(key)  # the real bridge publishes synchronously

    def save(self):
        self.saved += 1


def test_target_is_the_chosen_save_folder_else_pictures_collection(tmp_path):
    chosen = resolve_collection_target(_Settings({"sources.rss_save_directory": str(tmp_path)}))
    assert chosen.directory == tmp_path and not chosen.is_default
    fallback = resolve_collection_target(_Settings({"sources.rss_save_directory": ""}))
    assert fallback.directory.name == COLLECTION_FOLDER_NAME and fallback.is_default


def test_save_copies_bytes_once_and_numbers_name_clashes(tmp_path):
    source = tmp_path / "feed" / "sunset.jpg"
    source.parent.mkdir()
    source.write_bytes(b"jpeg-bytes")
    collection = tmp_path / "collection"
    first = save_image_to_collection(source, collection)
    assert first == collection / "sunset.jpg" and first.read_bytes() == b"jpeg-bytes"
    assert save_image_to_collection(source, collection) == first  # already saved: no second copy
    other = tmp_path / "other" / "sunset.jpg"
    other.parent.mkdir()
    other.write_bytes(b"a different picture")
    assert save_image_to_collection(other, collection) == collection / "sunset (2).jpg"
    assert save_image_to_collection(tmp_path / "missing.jpg", collection) is None


def test_save_image_is_always_in_the_context_menu():
    from rendering.quick.context_menu import build_quick_context_menu_entries
    for edit_mode in (False, True):
        entries = build_quick_context_menu_entries(
            transition_names=(), current_transition="", random_enabled=True, random_selectable=True,
            visualizer_modes=(), current_visualizer="", visualizer_available=False, dimming_enabled=False,
            interaction_mode_enabled=False, interaction_mode_locked=False, edit_mode_active=edit_mode)
        assert "save_image" in [entry.action_id for entry in entries]


def test_engine_saves_the_displayed_file_and_registers_the_collection_without_rebuild(tmp_path, monkeypatch):
    from core.threading import ThreadManager
    from engine.screensaver_engine import ScreensaverEngine
    import core.sources.image_collection as collection

    source = tmp_path / "cache" / "wall.png"
    source.parent.mkdir()
    source.write_bytes(b"png")
    pictures = tmp_path / "Pictures" / COLLECTION_FOLDER_NAME
    monkeypatch.setattr(collection, "default_collection_directory", lambda: pictures)
    monkeypatch.setattr(ThreadManager, "run_on_ui_thread", staticmethod(lambda callback: callback()))

    engine = ScreensaverEngine.__new__(ScreensaverEngine)
    rebuilds = []
    engine._on_sources_changed = lambda: rebuilds.append(True)
    engine._update_rotation_interval = engine._update_display_mode = engine._update_shuffle_mode = lambda: None
    engine._own_sources_write = None
    engine._current_image = None
    engine._display_image_history = [[SimpleNamespace(local_path=tmp_path / "left.png"), SimpleNamespace(local_path=source)]]
    engine.settings_manager = _Settings(
        {"sources.rss_save_directory": "", "sources.folders": ["C:/Pictures"]},
        on_set=lambda key: engine._on_settings_changed(SimpleNamespace(data={"key": key})),
    )
    submitted = []
    engine.thread_manager = SimpleNamespace(
        submit_io_task=lambda func, *args, task_id, callback: submitted.append(1) or callback(
            SimpleNamespace(success=True, result=func(*args))))

    engine._on_save_image_requested(1)  # the right display's image, not display 0's
    assert submitted == [1]
    assert (pictures / "wall.png").read_bytes() == b"png"
    assert engine.settings_manager.values["sources.folders"] == ["C:/Pictures", str(pictures)]
    assert rebuilds == []  # its own registration never rebuilds the running sources
    engine._on_save_image_requested(1)
    assert engine.settings_manager.values["sources.folders"] == ["C:/Pictures", str(pictures)]  # added once
    engine.settings_manager.set("sources.folders", ["D:/Other"])  # any other change still rebuilds
    assert rebuilds == [True]
