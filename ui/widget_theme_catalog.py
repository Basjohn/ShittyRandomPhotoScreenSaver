"""Widget Theme catalogue (built-in Default Dark + optional ``.srwtheme`` files).

Mirrors ``ui/settings_theme_catalog.py``: the compiled
:data:`DEFAULT_DARK_WIDGET_THEME` is always catalogue entry zero and is never
loaded from disk. ``themes/widgets/Default Dark.srwtheme`` is an optional canonical
mirror only and cannot override the built-in fallback. Callers inject the
``themes/widgets`` directory; this layer chooses no install path.

Selection resolution never mutates persistence or runtime state and always yields
a valid entry (the built-in fallback when a requested id is absent/invalid), so the
runtime can never be left without a Widget Theme.
"""

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from pathlib import Path

from ui.widget_theme_io import (
    WIDGET_THEME_FILE_EXTENSION,
    WidgetThemeFileError,
    discover_widget_theme_files,
    load_widget_theme_file,
)
from ui.widget_theme_spec import (
    DEFAULT_DARK_WIDGET_THEME,
    DEFAULT_DARK_WIDGET_THEME_ID,
    WidgetThemeSpec,
)


CANONICAL_DEFAULT_WIDGET_THEME_FILENAME = "Default Dark.srwtheme"


@dataclass(frozen=True, slots=True)
class WidgetThemeCatalogEntry:
    """One selectable, fully validated Widget theme."""

    theme_id: str
    name: str
    theme: WidgetThemeSpec
    source_path: Path | None
    is_builtin: bool = False


@dataclass(frozen=True, slots=True)
class WidgetThemeCatalogIssue:
    """One discovered theme file intentionally excluded from selection."""

    source_path: Path
    error: str


@dataclass(frozen=True, slots=True)
class WidgetThemeCatalog:
    """Resolved selectable Widget themes plus non-fatal discovery issues."""

    entries: tuple[WidgetThemeCatalogEntry, ...]
    issues: tuple[WidgetThemeCatalogIssue, ...]
    canonical_default_path: Path | None = None

    @property
    def builtin_default(self) -> WidgetThemeCatalogEntry:
        return self.entries[0]

    def entry_by_id(self, theme_id: str) -> WidgetThemeCatalogEntry | None:
        normalized = str(theme_id)
        for entry in self.entries:
            if entry.theme_id == normalized:
                return entry
        return None


@dataclass(frozen=True, slots=True)
class WidgetThemeSelectionResolution:
    """A requested id resolved to one always-valid Widget theme entry."""

    requested_theme_id: str
    entry: WidgetThemeCatalogEntry
    used_fallback: bool
    error: str | None = None


def _builtin_default_entry() -> WidgetThemeCatalogEntry:
    return WidgetThemeCatalogEntry(
        theme_id=DEFAULT_DARK_WIDGET_THEME_ID,
        name=DEFAULT_DARK_WIDGET_THEME.name,
        theme=DEFAULT_DARK_WIDGET_THEME,
        source_path=None,
        is_builtin=True,
    )


_current_widget_theme_catalog = WidgetThemeCatalog(
    entries=(_builtin_default_entry(),),
    issues=(),
)


def get_current_widget_theme_catalog() -> WidgetThemeCatalog:
    """Return the last startup-resolved catalogue, or built-in-only fallback."""

    return _current_widget_theme_catalog


def set_current_widget_theme_catalog(catalog: WidgetThemeCatalog) -> None:
    """Publish the catalogue resolved by startup/Settings authority."""

    if not isinstance(catalog, WidgetThemeCatalog):
        raise TypeError("catalog must be a WidgetThemeCatalog")
    global _current_widget_theme_catalog
    _current_widget_theme_catalog = catalog


def build_widget_theme_catalog(
    widget_themes_directory: str | PathLike[str],
) -> WidgetThemeCatalog:
    """Build a catalogue without changing runtime state.

    The built-in Default Dark entry exists even when the directory does not.
    Invalid files are reported as issues and never become selectable. A file whose
    embedded ``theme_id`` collides with an already-admitted id is rejected so the
    built-in fallback and portable ids stay unambiguous.
    """

    root = Path(widget_themes_directory)
    entries: list[WidgetThemeCatalogEntry] = [_builtin_default_entry()]
    issues: list[WidgetThemeCatalogIssue] = []
    canonical_default_path: Path | None = None
    seen_ids = {DEFAULT_DARK_WIDGET_THEME_ID}

    for path in discover_widget_theme_files(root):
        try:
            theme = load_widget_theme_file(path)
        except (OSError, WidgetThemeFileError, TypeError, ValueError) as exc:
            issues.append(WidgetThemeCatalogIssue(source_path=path, error=str(exc)))
            continue

        if path.name.casefold() == CANONICAL_DEFAULT_WIDGET_THEME_FILENAME.casefold():
            # Optional serialization mirror of the compiled default; never a second
            # authority. It must match the built-in exactly or it is excluded.
            if theme == DEFAULT_DARK_WIDGET_THEME:
                canonical_default_path = path
            else:
                issues.append(
                    WidgetThemeCatalogIssue(
                        source_path=path,
                        error=(
                            "Canonical Default Dark mirror does not equal the "
                            "compiled fallback and was excluded."
                        ),
                    )
                )
            continue

        if theme.theme_id in seen_ids:
            issues.append(
                WidgetThemeCatalogIssue(
                    source_path=path,
                    error=f"Duplicate Widget theme id {theme.theme_id!r}; excluded.",
                )
            )
            continue

        seen_ids.add(theme.theme_id)
        entries.append(
            WidgetThemeCatalogEntry(
                theme_id=theme.theme_id,
                name=theme.name,
                theme=theme,
                source_path=path,
                is_builtin=False,
            )
        )

    return WidgetThemeCatalog(
        entries=tuple(entries),
        issues=tuple(issues),
        canonical_default_path=canonical_default_path,
    )


def resolve_widget_theme_selection(
    catalog: WidgetThemeCatalog,
    requested_theme_id: str | None,
) -> WidgetThemeSelectionResolution:
    """Resolve one requested id to an always-valid entry (built-in fallback)."""

    requested = (
        str(requested_theme_id).strip()
        if requested_theme_id is not None
        else DEFAULT_DARK_WIDGET_THEME_ID
    ) or DEFAULT_DARK_WIDGET_THEME_ID

    entry = catalog.entry_by_id(requested)
    if entry is not None:
        return WidgetThemeSelectionResolution(
            requested_theme_id=requested,
            entry=entry,
            used_fallback=False,
            error=None,
        )

    return WidgetThemeSelectionResolution(
        requested_theme_id=requested,
        entry=catalog.builtin_default,
        used_fallback=True,
        error=(
            f"Selected Widget theme {requested!r} is unavailable or invalid; "
            "using compiled Default Dark."
        ),
    )


def widget_theme_file_id(filename: str) -> str:
    """Return a portable file-backed identity containing no install path.

    Disk-backed themes are addressed by ``file:<basename>``; the embedded
    ``theme_id`` remains the theme's own identity for link metadata.
    """

    name = str(filename)
    path = Path(name)
    if (
        not name
        or path.name != name
        or name in {".", ".."}
        or path.suffix.lower() != WIDGET_THEME_FILE_EXTENSION
    ):
        raise ValueError("Widget theme filename must be one plain .srwtheme basename")
    return f"file:{name}"


__all__ = [
    "CANONICAL_DEFAULT_WIDGET_THEME_FILENAME",
    "WidgetThemeCatalog",
    "WidgetThemeCatalogEntry",
    "WidgetThemeCatalogIssue",
    "WidgetThemeSelectionResolution",
    "build_widget_theme_catalog",
    "get_current_widget_theme_catalog",
    "resolve_widget_theme_selection",
    "set_current_widget_theme_catalog",
    "widget_theme_file_id",
]
