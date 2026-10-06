"""High-signal audit for accidental brittleness in the SRPSS test suite.

The audit intentionally does *not* ban literals. Fixture-owned values, protocol
constants, goldens and negative controls should be exact. It flags only patterns
where a mutable product authority has been copied into a test as a second source
of truth.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "tests"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS  # noqa: E402


def _load_transition_catalog_tokens() -> frozenset[str]:
    """Read transition identities without importing Qt-bearing animation modules."""

    path = ROOT / "rendering" / "transition_registry.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: set[str] = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "TransitionDescriptor"
        ):
            continue
        for keyword in node.keywords:
            if (
                keyword.arg in {"setting_name", "stable_id"}
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ):
                values.add(keyword.value.value)
    return frozenset(values)


_TRANSITION_CATALOG_TOKENS = _load_transition_catalog_tokens()

# These suites test preset filename/manifest/catalogue mechanics themselves and
# therefore legitimately create named preset fixtures. Behaviour/render tests do not.
_PRESET_INFRASTRUCTURE_FILES = frozenset(
    {
        "test_visualizer_presets.py",
        "test_visualizer_preset_manifest.py",
        "test_visualizer_preset_transfer.py",
        "test_visualizer_user_authored_preset_catalog.py",
        "test_build_runner.py",
    }
)
_PRESET_FILENAME_RE = re.compile(r"^preset_\d+[^/\\]*\.json$", re.IGNORECASE)
_EXACT_MARKERS = ("DURABILITY: exact", "EXACT-VALUE INVARIANT")

_DOC_CONTENT_MARKERS = ("DOCUMENT-CONTENT INVARIANT",)


@dataclass(frozen=True)
class Finding:
    rule: str
    path: Path
    line: int
    detail: str

    def render(self) -> str:
        return f"{self.path.relative_to(ROOT)}:{self.line}: [{self.rule}] {self.detail}"




def _source_has_doc_content_marker(lines: list[str], line: int) -> bool:
    start = max(0, line - 6)
    return any(
        any(marker in text for marker in _DOC_CONTENT_MARKERS)
        for text in lines[start:line]
    )


def _is_markdown_read(node: ast.AST) -> bool:
    """Return True for a direct ``*.md`` ``read_text``/``read`` expression.

    This deliberately stays narrow: the blocking rule is for tests that use
    authored Markdown prose as a behavioral oracle, not for ordinary path
    selection or generated-artifact existence checks.
    """

    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr in {"read_text", "read"}):
        return False
    constants = {
        child.value
        for child in ast.walk(func.value)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    }
    return any(value.lower().endswith(".md") for value in constants)


def _markdown_text_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, (ast.Assign, ast.AnnAssign)):
            continue
        value = child.value
        if value is None or not _is_markdown_read(value):
            continue
        targets = child.targets if isinstance(child, ast.Assign) else [child.target]
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _assert_reads_markdown_prose(assert_node: ast.Assert, markdown_names: set[str]) -> bool:
    if any(_is_markdown_read(child) for child in ast.walk(assert_node.test)):
        return True
    referenced = {
        child.id for child in ast.walk(assert_node.test) if isinstance(child, ast.Name)
    }
    return bool(referenced.intersection(markdown_names))

def _source_has_exact_marker(lines: list[str], line: int) -> bool:
    start = max(0, line - 6)
    return any(any(marker in text for marker in _EXACT_MARKERS) for text in lines[start:line])


def _is_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(_is_literal(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            (key is None or _is_literal(key)) and _is_literal(value)
            for key, value in zip(node.keys, node.values)
        )
    return False


def _is_require_canonical_default(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "require_canonical_default"
    )


def _literal_strings(node: ast.AST) -> tuple[str, ...]:
    if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return ()
    values: list[str] = []
    for item in node.elts:
        if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
            return ()
        values.append(item.value)
    return tuple(values)




def _literal_mapping_string_keys(node: ast.AST) -> tuple[str, ...]:
    if not isinstance(node, ast.Dict):
        return ()
    values: list[str] = []
    for key in node.keys:
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            return ()
        values.append(key.value)
    return tuple(values)

def _function_string_constants(node: ast.AST) -> set[str]:
    return {
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    }


def _uses_repo_authored_preset_path(node: ast.AST) -> bool:
    constants = _function_string_constants(node)
    has_catalogue = "presets" in constants and "visualizer_modes" in constants
    has_named_preset = any(_PRESET_FILENAME_RE.match(value) for value in constants)
    has_repo_anchor = any(
        isinstance(child, ast.Name) and child.id in {"ROOT", "__file__"}
        for child in ast.walk(node)
    )
    return has_catalogue and has_named_preset and has_repo_anchor




def _canonical_default_names(node: ast.AST) -> set[str]:
    assignments: list[tuple[list[ast.AST], ast.AST]] = []
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, (ast.Assign, ast.AnnAssign)):
            continue
        value = child.value
        if value is None:
            continue
        targets = child.targets if isinstance(child, ast.Assign) else [child.target]
        assignments.append((list(targets), value))
        if _is_require_canonical_default(value):
            for target in targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)

    # A canonical mapping stays canonical when a test aliases/subscripts it.
    # Propagate to a fixed point so ``defaults -> widgets -> media`` cannot hide
    # a copied authored literal from the audit.
    changed = True
    while changed:
        changed = False
        for targets, value in assignments:
            if _root_name(value) not in names:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in names:
                    names.add(target.id)
                    changed = True
    return names


def _canonical_snapshot_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    authority_calls = {
        "build_defaults_snapshot",
        "get_default_settings",
        "get_base_default_settings",
    }
    assignments: list[tuple[list[ast.AST], ast.AST]] = []
    for child in ast.walk(node):
        if not isinstance(child, (ast.Assign, ast.AnnAssign)):
            continue
        value = child.value
        if value is None:
            continue
        targets = child.targets if isinstance(child, ast.Assign) else [child.target]
        assignments.append((list(targets), value))
        is_authority = (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id in authority_calls
        ) or _root_name(value) in {"DEFAULT_SETTINGS", "CANONICAL_DEFAULTS"}
        if is_authority:
            for target in targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)

    changed = True
    while changed:
        changed = False
        for targets, value in assignments:
            if _root_name(value) not in names:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in names:
                    names.add(target.id)
                    changed = True
    return names


def _root_name(node: ast.AST) -> str | None:
    current = node
    while isinstance(current, ast.Subscript):
        current = current.value
    return current.id if isinstance(current, ast.Name) else None

def _registry_derived_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    authority_names = {
        "VISUALIZER_MODE_IDS",
        "MODES",
        "iter_visualizer_mode_descriptors",
        "iter_transition_descriptors",
        "iter_quick_transition_implementations",
        "get_transition_setting_names",
    }
    for child in ast.walk(node):
        if not isinstance(child, (ast.Assign, ast.AnnAssign)):
            continue
        value = child.value
        if value is None:
            continue
        refs = {
            ref.id for ref in ast.walk(value)
            if isinstance(ref, ast.Name)
        }
        if not refs.intersection(authority_names):
            continue
        targets = child.targets if isinstance(child, ast.Assign) else [child.target]
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _fixed_len_of_registry_name(compare: ast.Compare, derived_names: set[str]) -> bool:
    nodes = [compare.left, *compare.comparators]
    has_literal = any(isinstance(item, ast.Constant) and isinstance(item.value, int) for item in nodes)
    if not has_literal:
        return False
    for item in nodes:
        if not (isinstance(item, ast.Call) and isinstance(item.func, ast.Name) and item.func.id == "len"):
            continue
        if len(item.args) != 1:
            continue
        arg = item.args[0]
        if isinstance(arg, ast.Name) and arg.id in derived_names:
            return True
        if isinstance(arg, ast.Name) and arg.id in {"VISUALIZER_MODE_IDS", "MODES"}:
            return True
    return False


def audit_test_file(path: Path) -> list[Finding]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    findings: list[Finding] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.NotEq, ast.Is, ast.IsNot)):
            sides = [node.left, *node.comparators]
            if any(_is_require_canonical_default(side) for side in sides) and any(_is_literal(side) for side in sides):
                if not _source_has_exact_marker(lines, node.lineno):
                    findings.append(
                        Finding(
                            "canonical-default-literal",
                            path,
                            node.lineno,
                            "derive the expected value from canonical defaults instead of pinning today's authored value",
                        )
                    )

    for node in ast.walk(tree):
        literal_modes: tuple[str, ...] = ()
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            literal_modes = _literal_strings(node)
        elif isinstance(node, ast.Dict):
            literal_modes = _literal_mapping_string_keys(node)
        copied_modes = tuple(value for value in literal_modes if value in VISUALIZER_MODE_IDS)
        # Five or more registry identities in one literal is almost always a copied
        # catalog/subcatalog. Smaller scenario-owned subsets remain review-only.
        if len(copied_modes) >= 5 and not _source_has_exact_marker(lines, node.lineno):
            findings.append(
                Finding(
                    "visualizer-catalog-literal",
                    path,
                    node.lineno,
                    "derive extensible Visualizer membership from the registry/capabilities instead of copying mode IDs",
                )
            )
        copied_transitions = tuple(
            value for value in literal_modes if value in _TRANSITION_CATALOG_TOKENS
        )
        # Transition-specific tests commonly name one or a small semantic subset.
        # A large literal is usually an accidental hand-copied catalog.
        if len(copied_transitions) >= 8 and not _source_has_exact_marker(lines, node.lineno):
            findings.append(
                Finding(
                    "transition-catalog-literal",
                    path,
                    node.lineno,
                    "derive extensible transition membership from transition_registry instead of copying the catalog",
                )
            )

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        canonical_default_names = _canonical_default_names(node)
        canonical_names = _canonical_snapshot_names(node)
        markdown_names = _markdown_text_names(node)
        for child in ast.walk(node):
            if not isinstance(child, ast.Assert):
                continue
            if (
                _assert_reads_markdown_prose(child, markdown_names)
                and not _source_has_doc_content_marker(lines, child.lineno)
            ):
                findings.append(
                    Finding(
                        "documentation-prose-oracle",
                        path,
                        child.lineno,
                        "test reads authored Markdown and asserts its prose; test runtime/generated behavior instead, or mark a deliberately generated documentation artifact",
                    )
                )

        for child in ast.walk(node):
            if not (
                isinstance(child, ast.Compare)
                and len(child.ops) == 1
                and isinstance(child.ops[0], (ast.Eq, ast.NotEq, ast.Is, ast.IsNot))
            ):
                continue
            sides = [child.left, *child.comparators]
            if (
                any(isinstance(side, ast.Name) and side.id in canonical_default_names for side in sides)
                and any(_is_literal(side) for side in sides)
                and not _source_has_exact_marker(lines, child.lineno)
            ):
                findings.append(
                    Finding(
                        "canonical-default-alias-literal",
                        path,
                        child.lineno,
                        "a canonical default was assigned then compared to a literal; compare consumers to the authority instead",
                    )
                )

        for child in ast.walk(node):
            if not (
                isinstance(child, ast.Compare)
                and len(child.ops) == 1
                and isinstance(child.ops[0], (ast.Eq, ast.Is))
            ):
                continue
            sides = [child.left, *child.comparators]
            if (
                any(_root_name(side) in canonical_names or _root_name(side) in {"DEFAULT_SETTINGS", "CANONICAL_DEFAULTS"} for side in sides)
                and any(_is_literal(side) for side in sides)
                and not _source_has_exact_marker(lines, child.lineno)
            ):
                findings.append(
                    Finding(
                        "canonical-snapshot-literal",
                        path,
                        child.lineno,
                        "assert schema/relationship or compare to the canonical authority; do not pin a mutable authored default",
                    )
                )

        if path.name not in _PRESET_INFRASTRUCTURE_FILES and _uses_repo_authored_preset_path(node):
            findings.append(
                Finding(
                    "named-shipped-preset",
                    path,
                    node.lineno,
                    "behaviour test depends on a specifically named shipped preset; use a self-owned fixture or catalogue/schema query",
                )
            )
        derived_names = _registry_derived_names(node)
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Compare)
                and len(child.ops) == 1
                and isinstance(child.ops[0], (ast.Eq, ast.NotEq))
                and _fixed_len_of_registry_name(child, derived_names)
            ):
                if not _source_has_exact_marker(lines, child.lineno):
                    findings.append(
                        Finding(
                            "extensible-registry-count",
                            path,
                            child.lineno,
                            "derive membership/cardinality from the registry instead of pinning a current count",
                        )
                    )

    return findings


def audit_tests(paths: Iterable[Path] | None = None) -> list[Finding]:
    candidates = list(paths) if paths is not None else sorted(TEST_ROOT.glob("test_*.py"))
    findings: list[Finding] = []
    for path in candidates:
        findings.extend(audit_test_file(Path(path)))
    return sorted(findings, key=lambda item: (str(item.path), item.line, item.rule))


def main() -> int:
    findings = audit_tests()
    for finding in findings:
        print(finding.render())
    if findings:
        print(f"\n{len(findings)} blocking durability finding(s)")
        return 1
    print("Test durability audit: no blocking authority-copy findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
