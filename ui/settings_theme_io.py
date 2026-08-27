"""Strict file I/O for semantic Settings GUI themes.

A ``.srtheme`` file is an optional serialized override. It is never required
for Settings to render: :data:`DEFAULT_DARK_SETTINGS_THEME` remains compiled
into Python and is the unconditional safe fallback.

The strict loader rejects incomplete or mistyped semantic role sets rather
than silently merging them. The safe loader converts every file/read/parse/
schema/validation failure into the built-in Default Dark ThemeSpec plus an
error string suitable for a future Themes UI.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from ui.settings_theme_spec import (
    NativeBackdropStyle,
    DEFAULT_DARK_SETTINGS_THEME,
    GradientStop,
    GradientStyle,
    Rgba,
    SETTINGS_THEME_SCHEMA_VERSION,
    SettingsThemeSpec,
    ShadowStyle,
)


SETTINGS_THEME_FILE_FORMAT = "srpss.settings-theme"
SETTINGS_THEME_FILE_EXTENSION = ".srtheme"

_TOP_LEVEL_KEYS = frozenset(
    {
        "format",
        "schema_version",
        "name",
        "backdrop",
        "colors",
        "shadows",
        "gradients",
    }
)


class SettingsThemeFileError(ValueError):
    """A ``.srtheme`` file is readable but not a valid Settings theme."""


@dataclass(frozen=True, slots=True)
class SettingsThemeLoadResult:
    """Outcome returned by the non-throwing safe loader."""

    theme: SettingsThemeSpec
    source_path: Path | None
    loaded_from_file: bool
    error: str | None = None

    @property
    def used_fallback(self) -> bool:
        return not self.loaded_from_file


def _error(path: str, message: str) -> SettingsThemeFileError:
    return SettingsThemeFileError(f"{path}: {message}")


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


def _expect_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise _error(path, "must be a boolean")
    return value


def _expect_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _error(path, "must be an integer")
    return value


def _expect_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error(path, "must be numeric")
    return float(value)


def _rgba_from_payload(value: Any, path: str) -> Rgba:
    if not isinstance(value, list) or len(value) != 4:
        raise _error(path, "must be an [r, g, b, a] list")
    channels = [
        _expect_int(channel, f"{path}[{index}]")
        for index, channel in enumerate(value)
    ]
    try:
        return Rgba(*channels)
    except (TypeError, ValueError) as exc:
        raise _error(path, str(exc)) from exc


def _require_role_set(
    value: Mapping[str, Any],
    reference: Mapping[str, Any],
    path: str,
) -> None:
    expected = set(reference)
    actual = set(value)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append(f"missing semantic roles {missing!r}")
        if unexpected:
            details.append(f"unknown semantic roles {unexpected!r}")
        raise _error(path, "; ".join(details))


def _backdrop_from_payload(value: Any) -> NativeBackdropStyle:
    obj = _expect_mapping(value, "backdrop")
    _expect_exact_keys(obj, {"mode", "tint"}, "backdrop")

    mode = obj["mode"]
    if not isinstance(mode, str) or not mode.strip():
        raise _error("backdrop.mode", "must be a non-empty string")

    try:
        return NativeBackdropStyle(
            mode=mode,
            tint=_rgba_from_payload(obj["tint"], "backdrop.tint"),
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, SettingsThemeFileError):
            raise
        raise _error("backdrop", str(exc)) from exc


def _shadow_from_payload(value: Any, path: str) -> ShadowStyle:
    obj = _expect_mapping(value, path)
    _expect_exact_keys(
        obj,
        {
            "blur_radius",
            "offset_x",
            "offset_y",
            "color",
            "disabled_alpha_scale",
        },
        path,
    )
    try:
        return ShadowStyle(
            blur_radius=_expect_number(obj["blur_radius"], f"{path}.blur_radius"),
            offset_x=_expect_number(obj["offset_x"], f"{path}.offset_x"),
            offset_y=_expect_number(obj["offset_y"], f"{path}.offset_y"),
            color=_rgba_from_payload(obj["color"], f"{path}.color"),
            disabled_alpha_scale=_expect_number(
                obj["disabled_alpha_scale"],
                f"{path}.disabled_alpha_scale",
            ),
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, SettingsThemeFileError):
            raise
        raise _error(path, str(exc)) from exc


def _gradient_from_payload(value: Any, path: str) -> GradientStyle:
    obj = _expect_mapping(value, path)
    _expect_exact_keys(obj, {"stops"}, path)
    raw_stops = obj["stops"]
    if not isinstance(raw_stops, list):
        raise _error(f"{path}.stops", "must be a list")

    stops: list[GradientStop] = []
    for index, raw_stop in enumerate(raw_stops):
        stop_path = f"{path}.stops[{index}]"
        stop_obj = _expect_mapping(raw_stop, stop_path)
        _expect_exact_keys(stop_obj, {"position", "color"}, stop_path)
        try:
            stops.append(
                GradientStop(
                    position=_expect_number(
                        stop_obj["position"],
                        f"{stop_path}.position",
                    ),
                    color=_rgba_from_payload(
                        stop_obj["color"],
                        f"{stop_path}.color",
                    ),
                )
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, SettingsThemeFileError):
                raise
            raise _error(stop_path, str(exc)) from exc

    try:
        return GradientStyle(stops=tuple(stops))
    except (TypeError, ValueError) as exc:
        raise _error(path, str(exc)) from exc


def settings_theme_to_payload(theme: SettingsThemeSpec) -> dict[str, Any]:
    """Return the canonical JSON-compatible payload for one resolved ThemeSpec."""

    if not isinstance(theme, SettingsThemeSpec):
        raise TypeError("theme must be a SettingsThemeSpec")

    return {
        "format": SETTINGS_THEME_FILE_FORMAT,
        "schema_version": theme.schema_version,
        "name": theme.name,
        "backdrop": {
            "mode": theme.backdrop.mode,
            "tint": theme.backdrop.tint.as_list(),
        },
        "colors": {
            token: color.as_list()
            for token, color in theme.colors.items()
        },
        "shadows": {
            token: {
                "blur_radius": shadow.blur_radius,
                "offset_x": shadow.offset_x,
                "offset_y": shadow.offset_y,
                "color": shadow.color.as_list(),
                "disabled_alpha_scale": shadow.disabled_alpha_scale,
            }
            for token, shadow in theme.shadows.items()
        },
        "gradients": {
            token: {
                "stops": [
                    {
                        "position": stop.position,
                        "color": stop.color.as_list(),
                    }
                    for stop in gradient.stops
                ]
            }
            for token, gradient in theme.gradients.items()
        },
    }


def settings_theme_to_json(theme: SettingsThemeSpec) -> str:
    """Serialize one ThemeSpec deterministically in the canonical file format."""

    return (
        json.dumps(
            settings_theme_to_payload(theme),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


def settings_theme_from_payload(payload: Any) -> SettingsThemeSpec:
    """Strictly validate a decoded ``.srtheme`` payload."""

    obj = _expect_mapping(payload, "theme")
    _expect_exact_keys(obj, _TOP_LEVEL_KEYS, "theme")

    file_format = obj["format"]
    if file_format != SETTINGS_THEME_FILE_FORMAT:
        raise _error(
            "theme.format",
            f"expected {SETTINGS_THEME_FILE_FORMAT!r}, got {file_format!r}",
        )

    schema_version = _expect_int(obj["schema_version"], "theme.schema_version")
    if schema_version != SETTINGS_THEME_SCHEMA_VERSION:
        raise _error(
            "theme.schema_version",
            f"unsupported version {schema_version}; "
            f"expected {SETTINGS_THEME_SCHEMA_VERSION}",
        )

    name = obj["name"]
    if not isinstance(name, str) or not name.strip():
        raise _error("theme.name", "must be a non-empty string")

    raw_colors = _expect_mapping(obj["colors"], "colors")
    raw_shadows = _expect_mapping(obj["shadows"], "shadows")
    raw_gradients = _expect_mapping(obj["gradients"], "gradients")

    # A typo or omitted role is a whole-theme validation failure. Schema
    # evolution is explicit through SETTINGS_THEME_SCHEMA_VERSION instead of
    # silently blending arbitrary file fragments with the built-in fallback.
    _require_role_set(
        raw_colors,
        DEFAULT_DARK_SETTINGS_THEME.colors,
        "colors",
    )
    _require_role_set(
        raw_shadows,
        DEFAULT_DARK_SETTINGS_THEME.shadows,
        "shadows",
    )
    _require_role_set(
        raw_gradients,
        DEFAULT_DARK_SETTINGS_THEME.gradients,
        "gradients",
    )

    colors = {
        token: _rgba_from_payload(raw_colors[token], f"colors.{token}")
        for token in DEFAULT_DARK_SETTINGS_THEME.colors
    }
    shadows = {
        token: _shadow_from_payload(raw_shadows[token], f"shadows.{token}")
        for token in DEFAULT_DARK_SETTINGS_THEME.shadows
    }
    gradients = {
        token: _gradient_from_payload(
            raw_gradients[token],
            f"gradients.{token}",
        )
        for token in DEFAULT_DARK_SETTINGS_THEME.gradients
    }

    try:
        return SettingsThemeSpec(
            name=name,
            backdrop=_backdrop_from_payload(obj["backdrop"]),
            colors=colors,
            shadows=shadows,
            gradients=gradients,
            schema_version=schema_version,
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, SettingsThemeFileError):
            raise
        raise _error("theme", str(exc)) from exc


def settings_theme_from_json(text: str) -> SettingsThemeSpec:
    """Strictly parse and validate canonical ``.srtheme`` JSON text."""

    if not isinstance(text, str):
        raise TypeError("Theme JSON text must be a string")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SettingsThemeFileError(
            f"Invalid Settings theme JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc
    return settings_theme_from_payload(payload)


def load_settings_theme_file(path: str | os.PathLike[str]) -> SettingsThemeSpec:
    """Strictly load one complete theme or raise on any failure."""

    source = Path(path)
    text = source.read_text(encoding="utf-8")
    return settings_theme_from_json(text)


def load_settings_theme_or_default(
    path: str | os.PathLike[str] | None,
) -> SettingsThemeLoadResult:
    """Load one theme without ever returning an invalid Settings theme.

    ``None`` means no file-backed override was requested. Any file/read/parse/
    schema/semantic validation failure returns the compiled-in Default Dark
    ThemeSpec instead.
    """

    if path is None:
        return SettingsThemeLoadResult(
            theme=DEFAULT_DARK_SETTINGS_THEME,
            source_path=None,
            loaded_from_file=False,
            error=None,
        )

    source = Path(path)
    try:
        theme = load_settings_theme_file(source)
    except (OSError, SettingsThemeFileError, TypeError, ValueError) as exc:
        return SettingsThemeLoadResult(
            theme=DEFAULT_DARK_SETTINGS_THEME,
            source_path=source,
            loaded_from_file=False,
            error=str(exc),
        )

    return SettingsThemeLoadResult(
        theme=theme,
        source_path=source,
        loaded_from_file=True,
        error=None,
    )


def save_settings_theme_file(
    theme: SettingsThemeSpec,
    path: str | os.PathLike[str],
) -> Path:
    """Atomically write one complete canonical ``.srtheme`` file."""

    target = Path(path)
    if target.suffix.lower() != SETTINGS_THEME_FILE_EXTENSION:
        raise ValueError(
            f"Settings theme files must use {SETTINGS_THEME_FILE_EXTENSION}"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    text = settings_theme_to_json(theme)

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


def discover_settings_theme_files(
    directory: str | os.PathLike[str],
) -> tuple[Path, ...]:
    """Return deterministic ``.srtheme`` candidates without loading them."""

    root = Path(directory)
    if not root.is_dir():
        return ()
    return tuple(
        sorted(
            (
                path
                for path in root.iterdir()
                if path.is_file()
                and path.suffix.lower() == SETTINGS_THEME_FILE_EXTENSION
            ),
            key=lambda path: (path.name.casefold(), path.name),
        )
    )


__all__ = [
    "SETTINGS_THEME_FILE_EXTENSION",
    "SETTINGS_THEME_FILE_FORMAT",
    "SettingsThemeFileError",
    "SettingsThemeLoadResult",
    "discover_settings_theme_files",
    "load_settings_theme_file",
    "load_settings_theme_or_default",
    "save_settings_theme_file",
    "settings_theme_from_json",
    "settings_theme_from_payload",
    "settings_theme_to_json",
    "settings_theme_to_payload",
]
