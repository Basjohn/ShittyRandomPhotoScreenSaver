"""Pure safety/transaction helpers for SRPSS Defaults Foundry tooling.

This module deliberately has no Qt or SettingsManager dependency.  The GUI may
import it, and headless regeneration may import it, without touching installed
profile storage or constructing application runtime owners.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from pprint import pformat
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

_MISSING = object()
_NO_DEFAULT = object()

# These are transport/runtime/profile-local state, not values that a machine
# snapshot is allowed to turn into canonical defaults through Foundry import.
# Existing source values are preserved unless deliberately edited in source.
NON_IMPORTABLE_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("ui",),
    ("preset",),
    ("custom_preset_backup",),
    ("visualizer_custom_presets",),
    ("widgets", "custom_layout"),
    ("widgets", "custom_layout_restore"),
    ("widgets", "layout_slots"),
    ("sources", "folders"),
    ("sources", "rss_feeds"),
    ("widgets", "weather", "location"),
    ("widgets", "weather", "latitude"),
    ("widgets", "weather", "longitude"),
)

# Existing canonical leaves in these paths are deliberately not exposed in the
# GUI.  They are compatibility/operational payloads and must not be casually
# edited while the H settings epoch is still settling.
NON_EDITABLE_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("preset",),
    ("custom_preset_backup",),
    ("visualizer_custom_presets",),
    ("widgets", "custom_layout"),
    ("widgets", "custom_layout_restore"),
    ("widgets", "layout_slots"),
)

_PRIVATE_EXACT = frozenset(
    {
        "api_key",
        "client_secret",
        "credential",
        "credentials",
        "password",
        "refresh_token",
        "access_token",
        "token",
    }
)
_PRIVATE_SUFFIXES = ("_api_key", "_password", "_secret", "_token")


@dataclass(frozen=True)
class SchemaFilterResult:
    settings: dict[str, Any]
    accepted_leaf_count: int
    skipped_paths: tuple[str, ...]


@dataclass(frozen=True)
class TransactionResult:
    paths: tuple[Path, ...]
    changed_paths: tuple[Path, ...]


def path_is_under(path: Sequence[str], prefixes: Iterable[Sequence[str]]) -> bool:
    target = tuple(str(part) for part in path)
    for raw_prefix in prefixes:
        prefix = tuple(str(part) for part in raw_prefix)
        if len(target) >= len(prefix) and target[: len(prefix)] == prefix:
            return True
    return False


def looks_private_key(key: str) -> bool:
    lowered = str(key).strip().casefold()
    return (
        lowered in _PRIVATE_EXACT
        or lowered.endswith(_PRIVATE_SUFFIXES)
        or "credential" in lowered
    )


def walk_private_paths(value: Any, prefix: tuple[str, ...] = ()) -> tuple[str, ...]:
    matches: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            part = str(key)
            path = (*prefix, part)
            if looks_private_key(part):
                matches.append(".".join(path))
                continue
            matches.extend(walk_private_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.extend(walk_private_paths(child, (*prefix, f"[{index}]")))
    return tuple(matches)


def load_literal_assignment(path: Path, assignment_name: str) -> Mapping[str, Any]:
    source = Path(path).read_text(encoding="utf-8")
    parsed = ast.parse(source, filename=str(path))
    for node in parsed.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(
            isinstance(target, ast.Name) and target.id == assignment_name
            for target in targets
        ):
            continue
        value = ast.literal_eval(node.value)
        if isinstance(value, Mapping):
            return value
        break
    raise ValueError(f"{path} does not define a literal {assignment_name} mapping")


def iter_leaf_settings(
    mapping: Mapping[str, Any],
    prefix: tuple[str, ...] = (),
    *,
    skip_prefixes: Iterable[Sequence[str]] = (),
) -> Iterable[tuple[tuple[str, ...], Any]]:
    for raw_key, value in mapping.items():
        path = (*prefix, str(raw_key))
        if path_is_under(path, skip_prefixes):
            continue
        if isinstance(value, Mapping) and value:
            yield from iter_leaf_settings(value, path, skip_prefixes=skip_prefixes)
        else:
            yield path, value


def leaf_paths(
    mapping: Mapping[str, Any],
    *,
    skip_prefixes: Iterable[Sequence[str]] = (),
) -> set[tuple[str, ...]]:
    return {path for path, _value in iter_leaf_settings(mapping, skip_prefixes=skip_prefixes)}


def get_path(mapping: Mapping[str, Any], path: Sequence[str], default: Any = _NO_DEFAULT) -> Any:
    current: Any = mapping
    for part in path:
        if not isinstance(current, Mapping) or part not in current:
            if default is _NO_DEFAULT:
                raise KeyError(".".join(path))
            return default
        current = current[part]
    return current


def set_path(mapping: MutableMapping[str, Any], path: Sequence[str], value: Any) -> None:
    if not path:
        raise ValueError("Cannot set an empty settings path")
    current: MutableMapping[str, Any] = mapping
    for part in path[:-1]:
        child = current.get(part)
        if not isinstance(child, MutableMapping):
            child = {}
            current[part] = child
        current = child
    current[path[-1]] = deepcopy(value)


def remove_path(mapping: MutableMapping[str, Any], path: Sequence[str]) -> bool:
    if not path:
        return False
    current: Any = mapping
    for part in path[:-1]:
        if not isinstance(current, MutableMapping) or part not in current:
            return False
        current = current[part]
    if not isinstance(current, MutableMapping) or path[-1] not in current:
        return False
    current.pop(path[-1], None)
    return True


def _types_compatible(reference: Any, value: Any) -> bool:
    if reference is None:
        return value is None
    if isinstance(reference, bool):
        return isinstance(value, bool)
    if isinstance(reference, (int, float)) and not isinstance(reference, bool):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if isinstance(reference, str):
        return isinstance(value, str)
    if isinstance(reference, list):
        return isinstance(value, list)
    if isinstance(reference, Mapping):
        return isinstance(value, Mapping)
    return type(value) is type(reference)


def filter_import_to_existing_schema(
    imported: Mapping[str, Any],
    schema_model: Mapping[str, Any],
    *,
    blocked_prefixes: Iterable[Sequence[str]] = NON_IMPORTABLE_PREFIXES,
) -> SchemaFilterResult:
    """Keep only existing canonical leaves with compatible value types.

    Imports are overlays, never schema-authoring operations.  Unknown keys,
    machine/profile-local paths, private fields, and incompatible values are
    skipped loudly via the returned path list.
    """

    accepted: dict[str, Any] = {}
    skipped: list[str] = []
    accepted_count = 0

    def visit(value: Any, path: tuple[str, ...]) -> None:
        nonlocal accepted_count
        dotted = ".".join(path)
        if path_is_under(path, blocked_prefixes):
            skipped.append(f"{dotted} [profile/runtime-local]")
            return
        if any(looks_private_key(part) for part in path):
            skipped.append(f"{dotted} [private]")
            return
        reference = get_path(schema_model, path, _MISSING)
        if reference is _MISSING:
            if isinstance(value, Mapping):
                for child_key, child_value in value.items():
                    visit(child_value, (*path, str(child_key)))
            else:
                skipped.append(f"{dotted} [unknown-schema]")
            return
        if isinstance(value, Mapping) and isinstance(reference, Mapping):
            if not value and not reference:
                set_path(accepted, path, {})
                accepted_count += 1
                return
            for child_key, child_value in value.items():
                visit(child_value, (*path, str(child_key)))
            return
        if not _types_compatible(reference, value):
            skipped.append(
                f"{dotted} [type {type(value).__name__} != {type(reference).__name__}]"
            )
            return
        set_path(accepted, path, value)
        accepted_count += 1

    for key, value in imported.items():
        visit(value, (str(key),))

    return SchemaFilterResult(
        settings=accepted,
        accepted_leaf_count=accepted_count,
        skipped_paths=tuple(sorted(set(skipped))),
    )


def validate_model_schema_unchanged(
    original: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    skip_prefixes: Iterable[Sequence[str]] = NON_EDITABLE_PREFIXES,
) -> None:
    original_paths = leaf_paths(original, skip_prefixes=skip_prefixes)
    candidate_paths = leaf_paths(candidate, skip_prefixes=skip_prefixes)
    added = sorted(candidate_paths - original_paths)
    removed = sorted(original_paths - candidate_paths)
    if added or removed:
        parts: list[str] = []
        if added:
            parts.append("added=" + ", ".join(".".join(path) for path in added[:20]))
        if removed:
            parts.append("removed=" + ", ".join(".".join(path) for path in removed[:20]))
        raise ValueError("Defaults schema changed through Foundry: " + "; ".join(parts))

    incompatible: list[str] = []
    for path in sorted(original_paths):
        before = get_path(original, path)
        after = get_path(candidate, path)
        if not _types_compatible(before, after):
            incompatible.append(
                f"{'.'.join(path)} ({type(before).__name__}->{type(after).__name__})"
            )
    if incompatible:
        raise ValueError(
            "Defaults value types changed through Foundry: " + ", ".join(incompatible[:20])
        )


def validate_no_private_fields(mapping: Mapping[str, Any], *, label: str) -> None:
    private = walk_private_paths(mapping)
    if private:
        raise ValueError(f"{label} contains private/credential fields: " + ", ".join(private))


def validate_no_absolute_machine_paths(
    original: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> None:
    """Reject newly introduced absolute filesystem paths in canonical defaults."""
    violations: list[str] = []
    for path, value in iter_leaf_settings(candidate):
        if not isinstance(value, str) or not value:
            continue
        key = path[-1].casefold()
        if not any(token in key for token in ("path", "file", "folder", "directory")):
            continue
        try:
            is_absolute = Path(value).is_absolute()
        except (OSError, ValueError):
            is_absolute = False
        if not is_absolute:
            continue
        before = get_path(original, path, _MISSING)
        if before != value:
            violations.append(".".join(path))
    if violations:
        raise ValueError(
            "Foundry would introduce machine-local absolute paths: " + ", ".join(violations)
        )


def deep_difference(base: Mapping[str, Any], target: Mapping[str, Any]) -> dict[str, Any]:
    difference: dict[str, Any] = {}
    for key, value in target.items():
        inherited = base.get(key, _MISSING)
        if isinstance(inherited, Mapping) and isinstance(value, Mapping):
            nested = deep_difference(inherited, value)
            if nested:
                difference[key] = nested
        elif inherited is _MISSING or inherited != value:
            difference[key] = deepcopy(value)
    return difference


def render_literal_module(header: str, assignment_name: str, mapping: Mapping[str, Any]) -> str:
    return header + assignment_name + " = " + pformat(dict(mapping), width=100, sort_dicts=True) + "\n"


def stable_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write_many(payloads: Mapping[Path, bytes]) -> TransactionResult:
    """Replace multiple files transactionally, rolling all targets back on failure."""
    if not payloads:
        return TransactionResult((), ())

    ordered = tuple(Path(path) for path in payloads)
    originals: dict[Path, bytes | None] = {}
    staged: dict[Path, Path] = {}
    changed: list[Path] = []

    for path in ordered:
        data = payloads[path]
        originals[path] = path.read_bytes() if path.exists() else None
        if originals[path] == data:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temp_path = Path(raw_temp)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        staged[path] = temp_path
        changed.append(path)

    committed: list[Path] = []
    try:
        for path in ordered:
            temp_path = staged.get(path)
            if temp_path is None:
                continue
            os.replace(temp_path, path)
            committed.append(path)
            staged.pop(path, None)
    except Exception:
        rollback_errors: list[str] = []
        for path in reversed(committed):
            original = originals[path]
            try:
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    fd, raw_temp = tempfile.mkstemp(
                        prefix=f".{path.name}.rollback.", suffix=".tmp", dir=path.parent
                    )
                    rollback_temp = Path(raw_temp)
                    with os.fdopen(fd, "wb") as handle:
                        handle.write(original)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(rollback_temp, path)
            except Exception as exc:  # pragma: no cover - catastrophic filesystem failure
                rollback_errors.append(f"{path}: {exc}")
        if rollback_errors:
            raise RuntimeError(
                "Defaults transaction failed and rollback was incomplete: "
                + "; ".join(rollback_errors)
            )
        raise
    finally:
        for temp_path in staged.values():
            temp_path.unlink(missing_ok=True)

    return TransactionResult(paths=ordered, changed_paths=tuple(changed))
