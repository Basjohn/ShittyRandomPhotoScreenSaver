"""Theme Sorter Foundry file operations, independent of Qt and product Settings.

Author-owned .srtheme files are paired by WidgetThemeSpec.linked_settings_theme_id,
NOT by filename or display name. Operations never modify the selected product theme.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re
import sys
import tempfile
import types
import uuid

# The pure theme IO packages must not import ui.__init__ (which loads Qt).
if "ui" not in sys.modules:
    package = types.ModuleType("ui")
    package.__path__ = [str(Path(__file__).resolve().parent.parent / "ui")]
    sys.modules["ui"] = package

from ui.settings_theme_io import (
    discover_settings_theme_files, load_settings_theme_file,
    settings_theme_to_json,
)
from ui.widget_theme_io import (
    discover_widget_theme_files, load_widget_theme_file,
    widget_theme_to_json,
)
from tools.generate_widget_theme_mirrors import widget_counterpart_for_settings_theme

_CANONICAL_FILE = "Default Dark.srtheme"
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class ThemeSorterError(ValueError):
    """A safe thematic operation was rejected without mutating the catalogue."""


@dataclass(frozen=True)
class ThemePair:
    settings_path: Path
    name: str
    widget_path: Path | None


def _root(root: Path) -> Path:
    return Path(root).resolve()


def _widget_for(root: Path, settings_path: Path) -> Path | None:
    linked_id = f"file:{settings_path.name}"
    matches = []
    for path in discover_widget_theme_files(root / "widgets"):
        spec = load_widget_theme_file(path)
        if spec.linked_settings_theme_id == linked_id:
            matches.append(path)
    if len(matches) > 1:
        raise ThemeSorterError(f"Ambiguous linked Widget themes for {settings_path.name}: {matches}")
    return matches[0] if matches else None


def list_theme_pairs(root: Path) -> tuple[ThemePair, ...]:
    """List every authored Settings theme, retaining each linked Widget path."""
    root = _root(root)
    pairs = []
    for path in discover_settings_theme_files(root):
        # The compiled built-in default is not an authored, deletable theme.
        if path.name.casefold() == _CANONICAL_FILE.casefold():
            continue
        spec = load_settings_theme_file(path)
        pairs.append(ThemePair(path, spec.name, _widget_for(root, path)))
    return tuple(pairs)


def _source(root: Path, filename: str) -> Path:
    if not filename or Path(filename).name != filename or not filename.endswith('.srtheme'):
        raise ThemeSorterError("Select one Settings theme filename")
    path = root / filename
    if path.name.casefold() == _CANONICAL_FILE.casefold():
        raise ThemeSorterError("The compiled Default Dark mirror is not an authored theme")
    if not path.is_file() or path.is_symlink():
        raise ThemeSorterError("Selected Settings theme is missing or not a regular file")
    return path


def _new_name(name: str) -> str:
    name = str(name).strip()
    if not name or name in {'.', '..'} or len(name) > 150 or _INVALID.search(name) or name.endswith((' ', '.')):
        raise ThemeSorterError("Use a non-empty Windows-safe theme name (up to 150 characters)")
    return name


def _collision(directory: Path, wanted: Path, originals: set[Path]) -> None:
    for existing in directory.iterdir() if directory.is_dir() else ():
        if existing.name.casefold() == wanted.name.casefold() and existing not in originals:
            raise ThemeSorterError(f"Destination already exists: {existing}")


def _commit(root: Path, originals: tuple[Path, ...], replacements: dict[Path, bytes]) -> None:
    """Stage outputs and originals; roll back failed replacements without data loss.

    A crash can leave a hidden stage directory retaining originals; never delete it
    when rollback failed. Ordinary success and recoverable exceptions clean it up.
    """
    stage = root / f".theme-sorter-transaction-{uuid.uuid4().hex}"
    stage.mkdir(parents=True)
    backups: dict[Path, Path] = {}
    committed: list[Path] = []
    try:
        for i, (dest, content) in enumerate(replacements.items()):
            (stage / f"new-{i}").write_bytes(content)
        for i, old in enumerate(originals):
            backup = stage / f"old-{i}"
            old.replace(backup)
            backups[old] = backup
        for i, dest in enumerate(replacements):
            dest.parent.mkdir(parents=True, exist_ok=True)
            (stage / f"new-{i}").replace(dest)
            committed.append(dest)
    except Exception as error:
        recovery_errors = []
        for dest in reversed(committed):
            try:
                dest.unlink()
            except OSError as exc:
                recovery_errors.append(str(exc))
        for old, backup in backups.items():
            try:
                backup.replace(old)
            except OSError as exc:
                recovery_errors.append(str(exc))
        if recovery_errors:
            raise ThemeSorterError(
                f"Theme operation failed: {error}. Backup retained at {stage}. "
                f"Recovery required: {recovery_errors}"
            ) from error
        raise ThemeSorterError(f"Theme operation rolled back: {error}") from error
    else:
        for backup in backups.values():
            backup.unlink()
    finally:
        # Never discard a backup when an unforeseen restore problem occurred.
        if not any(p.name.startswith('old-') for p in stage.iterdir()):
            for remaining in stage.iterdir():
                remaining.unlink()
            stage.rmdir()


def rename_theme_pair(root: Path, filename: str, requested_name: str) -> ThemePair:
    root = _root(root)
    source = _source(root, filename)
    new_name = _new_name(requested_name)
    spec = load_settings_theme_file(source)
    linked = _widget_for(root, source)
    new_settings = root / f"{new_name}.srtheme"
    if new_settings == source and spec.name == new_name:
        return ThemePair(source, spec.name, linked)
    # The Widget's display name has no Settings-specific Glass/Acrylic suffix.
    from tools.generate_widget_theme_mirrors import _widget_display_name
    widget_name = _widget_display_name(new_name) or new_name
    new_widget = root / 'widgets' / f"{widget_name}.srwtheme"
    _collision(root, new_settings, {source})
    _collision(root / 'widgets', new_widget, {linked} if linked else set())
    old_id = f"file:{source.name}"
    new_id = f"file:{new_settings.name}"
    renamed_settings = replace(spec, name=new_name)
    if linked is None:
        renamed_widget = widget_counterpart_for_settings_theme(renamed_settings, settings_theme_id=new_id)
    else:
        current = load_widget_theme_file(linked)
        widget_id = f"mirror:{new_id}" if current.theme_id == f"mirror:{old_id}" else current.theme_id
        renamed_widget = replace(current, name=widget_name,
                                  theme_id=widget_id, linked_settings_theme_id=new_id)
    originals = (source,) + ((linked,) if linked else ())
    _commit(root, originals, {
        new_settings: settings_theme_to_json(renamed_settings).encode('utf-8'),
        new_widget: widget_theme_to_json(renamed_widget).encode('utf-8'),
    })
    return ThemePair(new_settings, new_name, new_widget)


def delete_theme_pair(root: Path, filename: str) -> tuple[Path, ...]:
    root = _root(root)
    source = _source(root, filename)
    load_settings_theme_file(source)  # reject invalid data before destructive action
    linked = _widget_for(root, source)
    originals = (source,) + ((linked,) if linked else ())
    _commit(root, originals, {})
    return originals
