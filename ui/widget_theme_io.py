"""Strict file I/O for semantic runtime Widget Themes (``.srwtheme``).

Mirrors ``ui/settings_theme_io.py``: a ``.srwtheme`` file is an optional
serialized override, never required for the runtime to render. The compiled
:data:`DEFAULT_DARK_WIDGET_THEME` is the unconditional safe fallback. The strict
loader requires the complete core card/context role set and rejects unknown/mistyped
roles whole. Schema-v3 specialized semantic roles are intentionally sparse: omitted
optional roles inherit at runtime through ``ui.widget_visual_roles`` rather than being
partially merged here. The safe loader converts every failure into Default Dark plus
an error string.

Automatic user ``Custom`` state is **not** a file — it lives in normal SRPSS
Settings persistence. A real ``.srwtheme`` is produced only by explicit
export/authoring, which is what :func:`save_widget_theme_file` serves.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from ui.settings_theme_spec import Rgba
from ui.widget_theme_spec import (
    DEFAULT_DARK_WIDGET_THEME,
    WIDGET_THEME_CORE_COLOR_ROLES,
    WIDGET_THEME_SCHEMA_VERSION,
    WidgetThemeSpec,
)
from ui.widget_visual_roles import WIDGET_THEME_OPTIONAL_COLOR_ROLES


WIDGET_THEME_FILE_FORMAT = "srpss.widget-theme"
WIDGET_THEME_FILE_EXTENSION = ".srwtheme"

_TOP_LEVEL_KEYS = frozenset(
    {
        "format",
        "schema_version",
        "theme_id",
        "name",
        "linked_settings_theme_id",
        "colors",
    }
)


class WidgetThemeFileError(ValueError):
    """A ``.srwtheme`` file is readable but not a valid Widget theme."""


@dataclass(frozen=True, slots=True)
class WidgetThemeLoadResult:
    """Outcome returned by the non-throwing safe loader."""

    theme: WidgetThemeSpec
    source_path: Path | None
    loaded_from_file: bool
    error: str | None = None

    @property
    def used_fallback(self) -> bool:
        return not self.loaded_from_file


def _error(path: str, message: str) -> WidgetThemeFileError:
    return WidgetThemeFileError(f"{path}: {message}")


def _expect_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise _error(path, "must be an object")
    return value


def _expect_exact_keys(
    value: Mapping[str, Any],
    expected: set[str] | frozenset[str],
    path: str,
) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append(f"missing {missing!r}")
        if unexpected:
            details.append(f"unexpected {unexpected!r}")
        raise _error(path, "; ".join(details))


def _expect_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _error(path, "must be an integer")
    return value


def _rgba_from_payload(value: Any, path: str) -> Rgba:
    if not isinstance(value, list) or len(value) != 4:
        raise _error(path, "must be an [r, g, b, a] list")
    channels = [_expect_int(channel, f"{path}[{index}]") for index, channel in enumerate(value)]
    try:
        return Rgba(*channels)
    except (TypeError, ValueError) as exc:
        raise _error(path, str(exc)) from exc


def _require_role_set(
    value: Mapping[str, Any],
    reference: Mapping[str, Any],
    path: str,
    *,
    allow_optional: bool,
) -> None:
    required = set(reference)
    allowed = required | (set(WIDGET_THEME_OPTIONAL_COLOR_ROLES) if allow_optional else set())
    actual = set(value)
    missing = sorted(required - actual)
    unexpected = sorted(actual - allowed)
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append(f"missing semantic roles {missing!r}")
        if unexpected:
            details.append(f"unknown semantic roles {unexpected!r}")
        raise _error(path, "; ".join(details))


def widget_theme_to_payload(theme: WidgetThemeSpec) -> dict[str, Any]:
    """Return the canonical JSON-compatible payload for one WidgetThemeSpec."""

    if not isinstance(theme, WidgetThemeSpec):
        raise TypeError("theme must be a WidgetThemeSpec")
    return {
        "format": WIDGET_THEME_FILE_FORMAT,
        "schema_version": theme.schema_version,
        "theme_id": theme.theme_id,
        "name": theme.name,
        "linked_settings_theme_id": theme.linked_settings_theme_id,
        "colors": {token: color.as_list() for token, color in theme.colors.items()},
    }


def widget_theme_to_json(theme: WidgetThemeSpec) -> str:
    """Serialize one WidgetThemeSpec deterministically in the canonical format."""

    return json.dumps(widget_theme_to_payload(theme), ensure_ascii=False, indent=2) + "\n"


def widget_theme_from_payload(payload: Any) -> WidgetThemeSpec:
    """Strictly validate a decoded ``.srwtheme`` payload (whole or reject)."""

    obj = _expect_mapping(payload, "theme")
    if "schema_version" not in obj:
        raise _error("theme", "missing ['schema_version']")
    schema_version = _expect_int(obj["schema_version"], "theme.schema_version")
    if schema_version != WIDGET_THEME_SCHEMA_VERSION:
        raise _error(
            "theme.schema_version",
            f"unsupported version {schema_version}; expected {WIDGET_THEME_SCHEMA_VERSION}",
        )
    _expect_exact_keys(obj, _TOP_LEVEL_KEYS, "theme")

    file_format = obj["format"]
    if file_format != WIDGET_THEME_FILE_FORMAT:
        raise _error(
            "theme.format",
            f"expected {WIDGET_THEME_FILE_FORMAT!r}, got {file_format!r}",
        )

    theme_id = obj["theme_id"]
    if not isinstance(theme_id, str) or not theme_id.strip():
        raise _error("theme.theme_id", "must be a non-empty string")

    name = obj["name"]
    if not isinstance(name, str) or not name.strip():
        raise _error("theme.name", "must be a non-empty string")
    name = name.strip()

    link = obj["linked_settings_theme_id"]
    if link is not None and (not isinstance(link, str) or not link.strip()):
        raise _error("theme.linked_settings_theme_id", "must be a string or null")

    raw_colors = _expect_mapping(obj["colors"], "colors")
    # Core card/context roles remain whole-or-reject. Schema v3 retains the sparse
    # optional role vocabulary introduced for specialized Widget semantics.
    _require_role_set(
        raw_colors,
        {role: None for role in WIDGET_THEME_CORE_COLOR_ROLES},
        "colors",
        allow_optional=True,
    )
    colors = {
        token: _rgba_from_payload(value, f"colors.{token}")
        for token, value in raw_colors.items()
    }

    try:
        return WidgetThemeSpec(
            theme_id=theme_id,
            name=name,
            linked_settings_theme_id=link,
            colors=colors,
            schema_version=WIDGET_THEME_SCHEMA_VERSION,
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, WidgetThemeFileError):
            raise
        raise _error("theme", str(exc)) from exc


def widget_theme_from_json(text: str) -> WidgetThemeSpec:
    """Strictly parse and validate canonical ``.srwtheme`` JSON text."""

    if not isinstance(text, str):
        raise TypeError("Widget theme JSON text must be a string")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise WidgetThemeFileError(
            f"Invalid Widget theme JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    return widget_theme_from_payload(payload)


def load_widget_theme_file(path: str | os.PathLike[str]) -> WidgetThemeSpec:
    """Strictly load one complete Widget theme or raise on any failure."""

    return widget_theme_from_json(Path(path).read_text(encoding="utf-8"))


def load_widget_theme_or_default(
    path: str | os.PathLike[str] | None,
) -> WidgetThemeLoadResult:
    """Load one Widget theme without ever returning an invalid theme."""

    if path is None:
        return WidgetThemeLoadResult(
            theme=DEFAULT_DARK_WIDGET_THEME,
            source_path=None,
            loaded_from_file=False,
            error=None,
        )
    source = Path(path)
    try:
        theme = load_widget_theme_file(source)
    except (OSError, WidgetThemeFileError, TypeError, ValueError) as exc:
        return WidgetThemeLoadResult(
            theme=DEFAULT_DARK_WIDGET_THEME,
            source_path=source,
            loaded_from_file=False,
            error=str(exc),
        )
    return WidgetThemeLoadResult(
        theme=theme,
        source_path=source,
        loaded_from_file=True,
        error=None,
    )


def save_widget_theme_file(
    theme: WidgetThemeSpec,
    path: str | os.PathLike[str],
) -> Path:
    """Atomically write one complete canonical ``.srwtheme`` file (explicit export)."""

    target = Path(path)
    if target.suffix.lower() != WIDGET_THEME_FILE_EXTENSION:
        raise ValueError(f"Widget theme files must use {WIDGET_THEME_FILE_EXTENSION}")

    target.parent.mkdir(parents=True, exist_ok=True)
    text = widget_theme_to_json(theme)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
    return target


def discover_widget_theme_files(
    directory: str | os.PathLike[str],
) -> tuple[Path, ...]:
    """Return deterministic ``.srwtheme`` candidates without loading them."""

    root = Path(directory)
    if not root.is_dir():
        return ()
    return tuple(
        sorted(
            (
                path
                for path in root.iterdir()
                if path.is_file() and path.suffix.lower() == WIDGET_THEME_FILE_EXTENSION
            ),
            key=lambda path: (path.name.casefold(), path.name),
        )
    )


__all__ = [
    "WIDGET_THEME_FILE_EXTENSION",
    "WIDGET_THEME_FILE_FORMAT",
    "WidgetThemeFileError",
    "WidgetThemeLoadResult",
    "discover_widget_theme_files",
    "load_widget_theme_file",
    "load_widget_theme_or_default",
    "save_widget_theme_file",
    "widget_theme_from_json",
    "widget_theme_from_payload",
    "widget_theme_to_json",
    "widget_theme_to_payload",
]
