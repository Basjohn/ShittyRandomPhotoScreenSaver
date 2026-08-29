"""Central Settings-theme ownership/regression tests.

The 2026 Settings GUI overhaul moved visual decisions into ThemeSpec/catalog/
runtime authorities.  These tests intentionally target those stable boundaries
rather than pixel geometry or one-off QSS strings.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

import ui.settings_theme_paths as theme_paths
import ui.settings_theme_runtime as theme_runtime
from ui.settings_theme_catalog import (
    BUILTIN_DEFAULT_THEME_ID,
    CANONICAL_DEFAULT_THEME_FILENAME,
    SETTINGS_THEME_SELECTION_KEY,
    activate_persisted_settings_theme,
    build_settings_theme_catalog,
    resolve_persisted_settings_theme,
)
from ui.settings_theme_io import save_settings_theme_file
from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME


class _Store:
    def __init__(self, values=None):
        self.values = dict(values or {})
        self.set_calls = []

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value
        self.set_calls.append((key, value))


@pytest.fixture(autouse=True)
def _isolated_runtime(monkeypatch):
    """Prevent theme listeners/active state leaking between unrelated tests."""
    monkeypatch.setattr(theme_runtime, "_active_theme", DEFAULT_DARK_SETTINGS_THEME)
    monkeypatch.setattr(theme_runtime, "_listeners", [])


def _named_theme(name: str):
    return replace(DEFAULT_DARK_SETTINGS_THEME, name=name)


def test_runtime_noop_does_not_notify_listeners():
    calls = []
    theme_runtime.subscribe_settings_theme(lambda theme: calls.append(theme.name))

    assert theme_runtime.set_active_settings_theme(DEFAULT_DARK_SETTINGS_THEME) is False
    assert calls == []


def test_runtime_listener_failure_rolls_back_active_theme_and_notified_renderers():
    alternate = _named_theme("Transactional Test")
    calls = []

    def first(theme):
        calls.append(("first", theme.name))

    def second(theme):
        calls.append(("second", theme.name))
        if theme == alternate:
            raise RuntimeError("renderer failed")

    theme_runtime.subscribe_settings_theme(first)
    theme_runtime.subscribe_settings_theme(second)

    with pytest.raises(RuntimeError, match="renderer failed"):
        theme_runtime.set_active_settings_theme(alternate)

    assert theme_runtime.get_active_settings_theme() == DEFAULT_DARK_SETTINGS_THEME
    assert calls == [
        ("first", "Transactional Test"),
        ("second", "Transactional Test"),
        ("second", DEFAULT_DARK_SETTINGS_THEME.name),
        ("first", DEFAULT_DARK_SETTINGS_THEME.name),
    ]


def test_catalog_keeps_compiled_default_first_and_excludes_mirror_and_invalid_files(tmp_path):
    alternate = _named_theme("Ocean Test")
    save_settings_theme_file(alternate, tmp_path / "Ocean.srtheme")
    canonical = save_settings_theme_file(
        DEFAULT_DARK_SETTINGS_THEME,
        tmp_path / CANONICAL_DEFAULT_THEME_FILENAME,
    )
    (tmp_path / "Broken.srtheme").write_text("{ definitely not json", encoding="utf-8")

    catalog = build_settings_theme_catalog(tmp_path)

    assert catalog.entries[0].theme_id == BUILTIN_DEFAULT_THEME_ID
    assert catalog.entries[0].is_builtin is True
    assert [entry.theme_id for entry in catalog.entries[1:]] == ["file:Ocean.srtheme"]
    assert catalog.entries[1].theme == alternate
    assert catalog.canonical_default_path == canonical
    assert len(catalog.issues) == 1
    assert catalog.issues[0].source_path.name == "Broken.srtheme"


def test_bad_canonical_default_mirror_cannot_override_compiled_default(tmp_path):
    save_settings_theme_file(
        _named_theme("Not Default Dark"),
        tmp_path / CANONICAL_DEFAULT_THEME_FILENAME,
    )

    catalog = build_settings_theme_catalog(tmp_path)

    assert len(catalog.entries) == 1
    assert catalog.entries[0].theme == DEFAULT_DARK_SETTINGS_THEME
    assert catalog.canonical_default_path is None
    assert len(catalog.issues) == 1
    assert "does not equal the compiled fallback" in catalog.issues[0].error


def test_missing_persisted_file_falls_back_without_destroying_user_selection(tmp_path):
    requested = "file:Temporarily Missing.srtheme"
    store = _Store({SETTINGS_THEME_SELECTION_KEY: requested})
    catalog = build_settings_theme_catalog(tmp_path)

    resolution = resolve_persisted_settings_theme(store, catalog)
    assert resolution.requested_theme_id == requested
    assert resolution.used_fallback is True
    assert resolution.entry.theme_id == BUILTIN_DEFAULT_THEME_ID
    assert store.values[SETTINGS_THEME_SELECTION_KEY] == requested
    assert store.set_calls == []

    startup = activate_persisted_settings_theme(store, tmp_path)
    assert startup.resolution.used_fallback is True
    assert theme_runtime.get_active_settings_theme() == DEFAULT_DARK_SETTINGS_THEME
    assert store.values[SETTINGS_THEME_SELECTION_KEY] == requested
    assert store.set_calls == []


def test_theme_directory_resolution_precedence(monkeypatch, tmp_path):
    explicit = tmp_path / "explicit"
    build = tmp_path / "build"

    monkeypatch.setattr(theme_paths, "THEMES_DIRECTORY_BUILD_REPLACE_BLANK", str(build))
    assert theme_paths.resolve_settings_themes_directory(explicit) == explicit
    assert theme_paths.resolve_settings_themes_directory() == build

    monkeypatch.setattr(theme_paths, "THEMES_DIRECTORY_BUILD_REPLACE_BLANK", "")
    fallback = theme_paths.resolve_settings_themes_directory()
    assert fallback.name == "themes"
    assert fallback.parent == Path(theme_paths.__file__).resolve().parent.parent
