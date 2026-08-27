"""Theme catalogue and persisted selection for the Settings GUI.

This layer deliberately does not choose where the packaged ``themes`` directory
lives. Callers inject that directory, allowing source, portable and frozen
builds to resolve installation layout in their own build/startup authority.

The compiled ``DEFAULT_DARK_SETTINGS_THEME`` is always catalogue entry zero and
is never loaded from disk. ``themes/Default Dark.srtheme`` is an optional
canonical mirror/template only; it cannot override the built-in fallback.

Startup ordering rule
---------------------
Resolve and activate the persisted selection before constructing Settings
widgets. ``activate_persisted_settings_theme`` performs one resolved runtime
activation only; it never resets to Default Dark before trying a custom theme.
This avoids a loader-created Default->custom visual flash while retaining an
unconditional built-in fallback when the selection cannot be resolved.
"""

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any, Protocol

from ui.settings_theme_io import (
    SETTINGS_THEME_FILE_EXTENSION,
    SettingsThemeFileError,
    discover_settings_theme_files,
    load_settings_theme_file,
)
from ui.settings_theme_runtime import set_active_settings_theme
from ui.settings_theme_spec import (
    DEFAULT_DARK_SETTINGS_THEME,
    SettingsThemeSpec,
)


BUILTIN_DEFAULT_THEME_ID = "builtin:default-dark"
CANONICAL_DEFAULT_THEME_FILENAME = "Default Dark.srtheme"
SETTINGS_THEME_SELECTION_KEY = "ui.settings_theme_selection"


class SettingsThemeSelectionStore(Protocol):
    """Minimal SettingsManager-compatible persistence surface."""

    def get(self, key: str, default: Any = None) -> Any:
        ...

    def set(self, key: str, value: Any) -> None:
        ...


@dataclass(frozen=True, slots=True)
class SettingsThemeCatalogEntry:
    """One selectable, fully validated theme."""

    theme_id: str
    name: str
    theme: SettingsThemeSpec
    source_path: Path | None
    is_builtin: bool = False


@dataclass(frozen=True, slots=True)
class SettingsThemeCatalogIssue:
    """One discovered theme file intentionally excluded from selection."""

    source_path: Path
    error: str


@dataclass(frozen=True, slots=True)
class SettingsThemeCatalog:
    """Resolved selectable themes plus non-fatal discovery issues."""

    entries: tuple[SettingsThemeCatalogEntry, ...]
    issues: tuple[SettingsThemeCatalogIssue, ...]
    canonical_default_path: Path | None = None

    @property
    def builtin_default(self) -> SettingsThemeCatalogEntry:
        return self.entries[0]

    def entry_by_id(self, theme_id: str) -> SettingsThemeCatalogEntry | None:
        normalized = str(theme_id)
        for entry in self.entries:
            if entry.theme_id == normalized:
                return entry
        return None


def _builtin_default_entry() -> SettingsThemeCatalogEntry:
    return SettingsThemeCatalogEntry(
        theme_id=BUILTIN_DEFAULT_THEME_ID,
        name=DEFAULT_DARK_SETTINGS_THEME.name,
        theme=DEFAULT_DARK_SETTINGS_THEME,
        source_path=None,
        is_builtin=True,
    )


_current_settings_theme_catalog = SettingsThemeCatalog(
    entries=(_builtin_default_entry(),),
    issues=(),
)


def get_current_settings_theme_catalog() -> SettingsThemeCatalog:
    """Return the last startup-resolved catalogue, or built-in-only fallback."""

    return _current_settings_theme_catalog


@dataclass(frozen=True, slots=True)
class SettingsThemeSelectionResolution:
    """A persisted request resolved to one always-valid ThemeSpec."""

    requested_theme_id: str
    entry: SettingsThemeCatalogEntry
    used_fallback: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class SettingsThemeStartupResult:
    """Catalogue + one resolved activation outcome."""

    catalog: SettingsThemeCatalog
    resolution: SettingsThemeSelectionResolution

    @property
    def theme(self) -> SettingsThemeSpec:
        return self.resolution.entry.theme


def _file_theme_id(filename: str) -> str:
    """Return a portable file-backed identity containing no install path."""

    name = str(filename)
    path = Path(name)
    if (
        not name
        or path.name != name
        or name in {".", ".."}
        or path.suffix.lower() != SETTINGS_THEME_FILE_EXTENSION
    ):
        raise ValueError("Theme filename must be one plain .srtheme basename")
    return f"file:{name}"


def _filename_from_theme_id(theme_id: str) -> str | None:
    prefix = "file:"
    if not isinstance(theme_id, str) or not theme_id.startswith(prefix):
        return None
    filename = theme_id[len(prefix):]
    try:
        if _file_theme_id(filename) != theme_id:
            return None
    except ValueError:
        return None
    return filename


def build_settings_theme_catalog(
    themes_directory: str | PathLike[str],
) -> SettingsThemeCatalog:
    """Build a catalogue without changing the active runtime theme.

    The built-in Default Dark entry exists even when ``themes_directory`` does
    not exist. Invalid files are reported as issues and never become selectable.
    """

    root = Path(themes_directory)
    builtin = _builtin_default_entry()

    entries: list[SettingsThemeCatalogEntry] = [builtin]
    issues: list[SettingsThemeCatalogIssue] = []
    canonical_default_path: Path | None = None

    for path in discover_settings_theme_files(root):
        try:
            theme = load_settings_theme_file(path)
        except (OSError, SettingsThemeFileError, TypeError, ValueError) as exc:
            issues.append(
                SettingsThemeCatalogIssue(
                    source_path=path,
                    error=str(exc),
                )
            )
            continue

        # The canonical Default Dark file is a serialization mirror/template,
        # not a second authority. It may assist Foundry/export later but startup
        # does not depend on reading it to obtain the default appearance.
        if path.name.casefold() == CANONICAL_DEFAULT_THEME_FILENAME.casefold():
            if theme == DEFAULT_DARK_SETTINGS_THEME:
                canonical_default_path = path
            else:
                issues.append(
                    SettingsThemeCatalogIssue(
                        source_path=path,
                        error=(
                            "Canonical Default Dark mirror does not equal the "
                            "compiled fallback and was excluded."
                        ),
                    )
                )
            continue

        try:
            theme_id = _file_theme_id(path.name)
        except ValueError as exc:
            issues.append(
                SettingsThemeCatalogIssue(
                    source_path=path,
                    error=str(exc),
                )
            )
            continue

        entries.append(
            SettingsThemeCatalogEntry(
                theme_id=theme_id,
                name=theme.name,
                theme=theme,
                source_path=path,
                is_builtin=False,
            )
        )

    # Discovery is already deterministic by filename; built-in remains first.
    return SettingsThemeCatalog(
        entries=tuple(entries),
        issues=tuple(issues),
        canonical_default_path=canonical_default_path,
    )


def read_persisted_theme_id(
    settings: SettingsThemeSelectionStore,
) -> str:
    """Return the persisted portable theme identity or built-in default."""

    raw = settings.get(
        SETTINGS_THEME_SELECTION_KEY,
        BUILTIN_DEFAULT_THEME_ID,
    )
    if not isinstance(raw, str):
        return BUILTIN_DEFAULT_THEME_ID
    normalized = raw.strip()
    return normalized or BUILTIN_DEFAULT_THEME_ID


def resolve_theme_selection(
    catalog: SettingsThemeCatalog,
    requested_theme_id: str | None,
) -> SettingsThemeSelectionResolution:
    """Resolve one identity without mutating persistence or runtime state."""

    requested = (
        str(requested_theme_id).strip()
        if requested_theme_id is not None
        else BUILTIN_DEFAULT_THEME_ID
    )
    if not requested:
        requested = BUILTIN_DEFAULT_THEME_ID

    entry = catalog.entry_by_id(requested)
    if entry is not None:
        return SettingsThemeSelectionResolution(
            requested_theme_id=requested,
            entry=entry,
            used_fallback=False,
            error=None,
        )

    filename = _filename_from_theme_id(requested)
    if filename is None and requested != BUILTIN_DEFAULT_THEME_ID:
        error = f"Invalid persisted Settings theme identity: {requested!r}"
    elif filename is not None:
        error = (
            f"Selected Settings theme {filename!r} is unavailable or invalid; "
            "using compiled Default Dark."
        )
    else:
        error = "Built-in Default Dark entry is unavailable."

    return SettingsThemeSelectionResolution(
        requested_theme_id=requested,
        entry=catalog.builtin_default,
        used_fallback=True,
        error=error,
    )


def resolve_persisted_settings_theme(
    settings: SettingsThemeSelectionStore,
    catalog: SettingsThemeCatalog,
) -> SettingsThemeSelectionResolution:
    """Resolve the stored selection without changing the active theme."""

    return resolve_theme_selection(
        catalog,
        read_persisted_theme_id(settings),
    )


def persist_settings_theme_selection(
    settings: SettingsThemeSelectionStore,
    catalog: SettingsThemeCatalog,
    theme_id: str,
) -> SettingsThemeCatalogEntry:
    """Persist only a currently selectable portable catalogue identity."""

    entry = catalog.entry_by_id(theme_id)
    if entry is None:
        raise ValueError(f"Unknown or invalid Settings theme id: {theme_id!r}")

    settings.set(SETTINGS_THEME_SELECTION_KEY, entry.theme_id)
    return entry


def activate_catalog_theme(
    entry: SettingsThemeCatalogEntry,
) -> bool:
    """Activate one already-validated catalogue entry exactly once."""

    return set_active_settings_theme(entry.theme)


def activate_persisted_settings_theme(
    settings: SettingsThemeSelectionStore,
    themes_directory: str | PathLike[str],
) -> SettingsThemeStartupResult:
    """Resolve the persisted selection, then perform one runtime activation.

    Call this before constructing Settings widgets. Catalogue construction and
    persistence reads do not alter runtime state. There is intentionally no
    preliminary reset to Default Dark before resolving a custom selection.

    If the requested custom theme is absent/invalid, the single resolved
    activation is the compiled Default Dark ThemeSpec. The bad/missing persisted
    identity is deliberately retained so a temporarily unavailable file can
    recover on a later run instead of silently destroying the user's choice.
    """

    global _current_settings_theme_catalog

    catalog = build_settings_theme_catalog(themes_directory)
    resolution = resolve_persisted_settings_theme(settings, catalog)
    activate_catalog_theme(resolution.entry)
    _current_settings_theme_catalog = catalog
    return SettingsThemeStartupResult(
        catalog=catalog,
        resolution=resolution,
    )


__all__ = [
    "BUILTIN_DEFAULT_THEME_ID",
    "CANONICAL_DEFAULT_THEME_FILENAME",
    "SETTINGS_THEME_SELECTION_KEY",
    "SettingsThemeCatalog",
    "SettingsThemeCatalogEntry",
    "SettingsThemeCatalogIssue",
    "SettingsThemeSelectionResolution",
    "SettingsThemeSelectionStore",
    "SettingsThemeStartupResult",
    "activate_catalog_theme",
    "activate_persisted_settings_theme",
    "build_settings_theme_catalog",
    "get_current_settings_theme_catalog",
    "persist_settings_theme_selection",
    "read_persisted_theme_id",
    "resolve_persisted_settings_theme",
    "resolve_theme_selection",
]
