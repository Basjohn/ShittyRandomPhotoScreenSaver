"""AC-07: a settings publication means a change.

``SettingsManager.set`` publishes (Qt signal, every handler, the engine's EventSystem bridge) only when the store's
state actually changed. Before AC-07 the store dropped an unchanged write but the manager published it anyway, so
re-saving ``sources.folders`` unchanged rebuilt the engine's sources.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from core.settings import SettingsManager


@pytest.fixture
def manager(tmp_path):
    return SettingsManager(
        organization="Test", application=f"AC07_{uuid.uuid4().hex}", storage_base_dir=tmp_path,
    )


def _record(manager) -> list:
    published: list = []
    manager.settings_changed.connect(lambda key, value: published.append((key, value)))
    return published


def test_the_same_write_twice_publishes_once(manager):
    published = _record(manager)
    handled: list = []
    manager.on_changed("timing.interval", lambda value, old: handled.append((value, old)))

    current = manager.get("timing.interval")
    manager.set("timing.interval", int(current) + 7)
    manager.set("timing.interval", int(current) + 7)

    assert published == [("timing.interval", int(current) + 7)]
    assert len(handled) == 1


def test_a_structured_leaf_and_a_whole_root_rewritten_unchanged_publish_nothing(manager):
    published = _record(manager)
    manager.set("widgets", manager.get("widgets"))
    manager.set("widgets.clock.enabled", manager.get("widgets.clock.enabled"))
    manager.set("transitions", manager.get("transitions"))
    # The section writers Settings tabs re-save whole groups through (Visualizers: set_widgets_map).
    manager.set_widgets_map(manager.get_widgets_map())
    manager.set_section("transitions", manager.get_section("transitions"))
    manager.set_spotify_visualizer_settings(manager.get_spotify_visualizer_settings())
    manager.remove(f"ac07_probe.missing_{uuid.uuid4().hex[:8]}")
    assert published == []

    manager.set("widgets.clock.enabled", not manager.get("widgets.clock.enabled"))   # control: a real change
    assert [key for key, _ in published] == ["widgets.clock.enabled"]


def test_an_unchanged_display_section_publishes_nothing(manager):
    published = _record(manager)
    section = {"show_on_monitors": manager.get("display.show_on_monitors"),
               "monitor_bindings": manager.get("display.monitor_bindings")}
    manager.set("display", section)    # may seed the derived bindings once
    published.clear()
    manager.set("display", section)
    manager.set("display.show_on_monitors", section["show_on_monitors"])
    assert published == []


def test_seeding_a_nullable_value_to_none_still_publishes_once(manager):
    published = _record(manager)
    key = f"ac07_probe.nullable_{uuid.uuid4().hex[:8]}"
    manager.set(key, None)        # missing -> explicit null is a change
    manager.set(key, None)
    assert published == [(key, None)]

    manager.remove("widget_theme.custom")
    published.clear()
    manager.set("widget_theme.custom", None)
    manager.set("widget_theme.custom", None)
    assert published == [("widget_theme.custom", None)]


def test_rewriting_the_current_source_folders_does_not_rebuild_the_engine_sources(monkeypatch, manager, tmp_path):
    from engine import screensaver_engine
    from engine.screensaver_engine import ScreensaverEngine

    class _Shared:
        def __init__(self, *args, **kwargs) -> None:
            return None

        @staticmethod
        def set_app_shared(_instance) -> None:
            return None

    monkeypatch.setattr(screensaver_engine, "ResourceManager", _Shared)
    monkeypatch.setattr(screensaver_engine, "ThreadManager", _Shared)
    monkeypatch.setattr("core.sources.image_bans.ImageBanStore", lambda *_a, **_k: SimpleNamespace())
    engine = ScreensaverEngine()
    engine.settings_manager = manager
    assert engine._initialize_core_systems()          # the real Qt-signal -> EventSystem bridge
    engine._subscribe_to_events()
    rebuilds: list = []
    monkeypatch.setattr(engine, "_on_sources_changed", lambda: rebuilds.append(True))

    folders = [str(tmp_path / "pictures")]
    manager.set("sources.folders", folders)
    assert rebuilds == [True]                          # control: a real change rebuilds once
    manager.set("sources.folders", list(folders))
    assert rebuilds == [True]
