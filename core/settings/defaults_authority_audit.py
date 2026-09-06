"""Headless repository audit for SRPSS defaults authority.

This module guards the architectural rules behind the Settings/defaults sweep.
It intentionally performs static checks in addition to snapshot parity so future
features cannot quietly reintroduce a second product-default table in runtime or
Settings presentation code.

It is safe to import without Qt.  ``tools/check_defaults_authority.py`` exposes
it as a repository tool and the focused defaults test suite exercises the same
checks.
"""
from __future__ import annotations

from dataclasses import dataclass
import ast
from pathlib import Path
from typing import Iterable

from core.settings.default_contract import MISSING_DEFAULT, get_canonical_default
from core.settings.defaults_snapshot_builder import defaults_snapshot_matches


@dataclass(frozen=True, slots=True)
class DefaultsAuthorityIssue:
    path: str
    line: int
    message: str

    def render(self) -> str:
        location = self.path if self.line <= 0 else f"{self.path}:{self.line}"
        return f"{location}: {self.message}"


_SCAN_EXCLUDED_PARTS = frozenset({
    ".git",
    ".godzip",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "deleteme",
    "tests",
    "venv",
})

_DIRECT_DEFAULT_AUTHORITY_IMPORT_ALLOWLIST = frozenset({
    "core/settings/default_contract.py",
    "core/settings/defaults.py",
})
_DEAD_DEFAULT_MIRRORS = (
    "core/settings/defaults_generated.py",
    "core/settings/defaults_snapshot.py",
)
_SENSITIVE_MAPPER_PREFIXES = ("save", "_save", "collect")
_SENSITIVE_MAPPING_OWNER_TOKENS = (
    "config",
    "settings",
    "widgets",
    "values",
    "merged",
    "section",
    "defaults",
)


def _iter_python_files(root: Path) -> Iterable[Path]:
    """Yield every first-party Python source subject to defaults ownership rules.

    The authority guard deliberately includes root entrypoints, tools, helpers,
    providers, and future top-level source packages. Tests/caches/virtual-env or
    deletion-staging trees are excluded because they are not production or
    authoring surfaces.
    """

    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if any(part in _SCAN_EXCLUDED_PARTS for part in relative.parts):
            continue
        yield path


def _literal(node: ast.AST) -> object:
    try:
        return ast.literal_eval(node)
    except Exception:
        return MISSING_DEFAULT


def _is_literal_default(node: ast.AST) -> bool:
    return isinstance(
        node,
        (ast.Constant, ast.List, ast.Tuple, ast.Dict, ast.Set),
    )


def _audit_python_file(root: Path, path: Path) -> list[DefaultsAuthorityIssue]:
    relative = path.relative_to(root).as_posix()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
    except (OSError, SyntaxError) as exc:
        return [DefaultsAuthorityIssue(relative, 0, f"cannot parse source: {exc}")]

    issues: list[DefaultsAuthorityIssue] = []

    # Editable product-default tables are implementation details of the
    # canonical authority.  Runtime/UI/tooling consumers must use the contract
    # API so profile overlays, validation, and future schema changes cannot be
    # bypassed by direct imports.
    if relative not in _DIRECT_DEFAULT_AUTHORITY_IMPORT_ALLOWLIST:
        for import_node in [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]:
            module = str(import_node.module or "")
            imported = {alias.name for alias in import_node.names}
            direct_default_settings = module in {
                "core.settings.default_settings", "default_settings"
            }
            direct_profile_overrides = module in {
                "core.settings.default_profile_overrides", "default_profile_overrides"
            }
            if direct_default_settings or direct_profile_overrides:
                issues.append(
                    DefaultsAuthorityIssue(
                        relative,
                        import_node.lineno,
                        "direct editable defaults-table import bypasses canonical default_contract",
                    )
                )

    # Resolved Quick presentation contracts must never be default-constructible.
    # Their only product-state entrypoint is canonical-aware projection.
    for class_node in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        if class_node.name.endswith("PresentationConfig"):
            for member in class_node.body:
                if isinstance(member, ast.AnnAssign) and member.value is not None:
                    field_name = (
                        member.target.id if isinstance(member.target, ast.Name) else "<field>"
                    )
                    issues.append(
                        DefaultsAuthorityIssue(
                            relative,
                            member.lineno,
                            f"{class_node.name}.{field_name} has a local default; "
                            "resolved presentation config must be explicit",
                        )
                    )

        # Runtime configs may have canonical-derived factories, named constraints,
        # or session-container factories, but not anonymous literal product values.
        if class_node.name.endswith("RuntimeConfig"):
            for member in class_node.body:
                if (
                    isinstance(member, ast.AnnAssign)
                    and member.value is not None
                    and _is_literal_default(member.value)
                ):
                    field_name = (
                        member.target.id if isinstance(member.target, ast.Name) else "<field>"
                    )
                    issues.append(
                        DefaultsAuthorityIssue(
                            relative,
                            member.lineno,
                            f"{class_node.name}.{field_name} has a literal runtime-config default; "
                            "use canonical authority or an explicitly named runtime constraint",
                        )
                    )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue

        # Quick visualizer implementations consume an immutable resolved frame.
        # Their accessors are deliberately required-only: adding a third
        # ``parameter`` argument or an RGBA fallback recreates a renderer-local
        # shadow defaults table.
        if relative.startswith("rendering/quick/visualizer/implementations/"):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "parameter"
                and len(node.args) != 2
            ):
                issues.append(DefaultsAuthorityIssue(
                    relative, node.lineno,
                    "Quick visualizer renderer parameter access must be required-only",
                ))
            if isinstance(node.func, ast.Name) and node.func.id == "rgba":
                if len(node.args) != 1 or node.keywords:
                    issues.append(DefaultsAuthorityIssue(
                        relative, node.lineno,
                        "Quick visualizer renderer RGBA access must be required-only",
                    ))

        # Raw QSettings startup/migration readers may exist, but a persisted
        # canonical product key may never carry its own literal default there.
        if node.func.attr == "value" and len(node.args) >= 2:
            key_node = node.args[0]
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                product_key = key_node.value
                canonical = get_canonical_default(product_key, missing=MISSING_DEFAULT)
                fallback = _literal(node.args[1])
                if (
                    "." in product_key
                    and canonical is not MISSING_DEFAULT
                    and fallback is not MISSING_DEFAULT
                ):
                    issues.append(DefaultsAuthorityIssue(
                        relative, node.lineno,
                        f"raw QSettings read for {product_key!r} has a literal product fallback",
                    ))

        # Any explicit scalar fallback attached directly to a canonical dotted
        # product key is a duplicate authority, even if today's value happens
        # to match.  Root names such as ``ui``/``widgets`` are intentionally
        # excluded here: those are common keys in unrelated runtime/session
        # payloads.  Empty structural containers are likewise not product
        # values; they are shape sentinels and are audited at the actual
        # Settings projection/save boundaries below.
        # Canonical product booleans read directly from SettingsManager must use
        # ``get_bool``. Wrapping ``settings.get("dotted.key")`` in the static
        # coercer recreates a call-site fallback seam and, historically, allowed
        # missing canonical-True values to collapse to False. Mapping-local bool
        # coercion (for an already-resolved transitions/widget section) remains
        # valid because its fallback comes from that section's canonical owner.
        if (
            node.func.attr == "to_bool"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "SettingsManager"
            and node.args
            and isinstance(node.args[0], ast.Call)
            and isinstance(node.args[0].func, ast.Attribute)
            and node.args[0].func.attr == "get"
            and node.args[0].args
            and isinstance(node.args[0].args[0], ast.Constant)
            and isinstance(node.args[0].args[0].value, str)
        ):
            product_key = node.args[0].args[0].value
            canonical_bool = get_canonical_default(
                product_key, missing=MISSING_DEFAULT
            )
            if "." in product_key and isinstance(canonical_bool, bool):
                issues.append(
                    DefaultsAuthorityIssue(
                        relative,
                        node.lineno,
                        "direct SettingsManager.to_bool around canonical product read; "
                        "use SettingsManager.get_bool so missing-state repair stays canonical",
                    )
                )

        if node.func.attr == "get" and len(node.args) >= 2:
            key_node = node.args[0]
            if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                key = key_node.value
                canonical = get_canonical_default(key, missing=MISSING_DEFAULT)
                fallback = _literal(node.args[1])
                structural_empty = isinstance(fallback, (dict, list, tuple, set)) and not fallback
                if (
                    "." in key
                    and canonical is not MISSING_DEFAULT
                    and fallback is not MISSING_DEFAULT
                    and not structural_empty
                ):
                    issues.append(
                        DefaultsAuthorityIssue(
                            relative,
                            node.lineno,
                            f"canonical product key {key!r} has a call-site literal fallback",
                        )
                    )

    # Settings save/collect/from_mapping functions are especially dangerous:
    # a scalar mapping.get(..., literal) can turn a transiently incomplete UI or
    # mapping into persisted state. Structural empty mappings/lists are excluded.
    for func in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        sensitive = (
            func.name.startswith(_SENSITIVE_MAPPER_PREFIXES)
            or func.name == "from_mapping"
            or ("load" in func.name and "settings" in func.name)
        )
        if not sensitive:
            continue
        for node in ast.walk(func):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and len(node.args) >= 2
            ):
                continue
            owner_text = ast.unparse(node.func.value).lower()
            if not any(token in owner_text for token in _SENSITIVE_MAPPING_OWNER_TOKENS):
                continue
            fallback = _literal(node.args[1])
            if fallback is MISSING_DEFAULT:
                continue
            if isinstance(fallback, (dict, list, tuple, set)):
                continue
            issues.append(
                DefaultsAuthorityIssue(
                    relative,
                    node.lineno,
                    f"{func.name} uses scalar mapping fallback {fallback!r}; "
                    "repair through canonical authority or an explicit projection contract",
                )
            )

    return issues


def audit_defaults_authority(root: str | Path | None = None) -> list[DefaultsAuthorityIssue]:
    """Return every detected secondary/default-authority violation."""

    repo_root = (
        Path(root).resolve()
        if root is not None
        else Path(__file__).resolve().parents[2]
    )
    issues: list[DefaultsAuthorityIssue] = []

    snapshot = repo_root / "core" / "settings" / "defaults_snapshot.json"
    if not defaults_snapshot_matches(snapshot):
        issues.append(
            DefaultsAuthorityIssue(
                snapshot.relative_to(repo_root).as_posix(),
                0,
                "derived defaults snapshot is stale",
            )
        )

    for relative in _DEAD_DEFAULT_MIRRORS:
        if (repo_root / relative).exists():
            issues.append(
                DefaultsAuthorityIssue(
                    relative,
                    0,
                    "retired Python defaults mirror exists; use canonical defaults/snapshot builder",
                )
            )

    for path in _iter_python_files(repo_root):
        issues.extend(_audit_python_file(repo_root, path))

    return sorted(issues, key=lambda issue: (issue.path, issue.line, issue.message))


__all__ = ["DefaultsAuthorityIssue", "audit_defaults_authority"]
