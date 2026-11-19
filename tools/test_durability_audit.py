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

# These suites test preset filename/tree/catalogue mechanics themselves and
# therefore legitimately create named preset fixtures. Behaviour/render tests do not.
_PRESET_INFRASTRUCTURE_FILES = frozenset(
    {
        "test_visualizer_presets.py",
        "test_visualizer_preset_tree.py",
        "test_visualizer_preset_transfer.py",
        "test_visualizer_user_authored_preset_catalog.py",
        "test_build_runner.py",
    }
)
_PRESET_FILENAME_RE = re.compile(r"^preset_\d+[^/\\]*\.json$", re.IGNORECASE)
_EXACT_MARKERS = ("DURABILITY: exact", "EXACT-VALUE INVARIANT")

_DOC_CONTENT_MARKERS = ("DOCUMENT-CONTENT INVARIANT",)

# Unlike semantic geometry or test-owned fixtures, today's QML visual recipe
# must never be copied as a production-source golden. This deliberately narrow
# blocking rule complements the broader advisory oracle-review queue.
_MUTABLE_RECIPE_SOURCE_PIN = re.compile(
    r"\b(?:legibilityPanel|tintAlphaScale|additionalOpacityAdjust|"
    r"opacityScale|fontMultiplier|fillOpacityAdjust|borderOpacityAdjust)"
    r"\s*:\s*(?:[-+]?\d|true\b|false\b)"
    r"|\b(?:WizardBackColor|WizardSmallImageBackColor)\s*=\s*#[0-9A-Fa-f]{6}\b"
    r"|\bcolor\.alpha\(\)\s*\*\s*(?:0?\.\d+|1\.0+)",
    re.IGNORECASE,
)
_MUTABLE_RECIPE_PROPERTIES = frozenset({
    "legibilityPanel", "tintAlphaScale", "additionalOpacityAdjust",
    "opacityScale", "fontMultiplier", "fillOpacityAdjust", "borderOpacityAdjust",
})


def _literal_fixture_names(function: ast.AST) -> set[str]:
    """Names assigned literal test-owned strings, not live source reads."""
    found: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        if not isinstance(node.value, (ast.Constant, ast.JoinedStr)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                found.add(target.id)
    return found


def _assert_has_unowned_recipe_pin(
    node: ast.Assert, function: ast.AST, fixture_names: set[str]
) -> bool:
    for compare in ast.walk(node.test):
        if not isinstance(compare, ast.Compare) or len(compare.ops) != 1:
            continue
        lhs, rhs = compare.left, compare.comparators[0]
        if isinstance(compare.ops[0], ast.In):
            # Exact textual implementation recipes are invalid if read from
            # production source. Locally authored literal fixture strings may
            # of course be compared exactly.
            if (isinstance(lhs, ast.Constant) and isinstance(lhs.value, str)
                    and _MUTABLE_RECIPE_SOURCE_PIN.search(lhs.value)):
                if (not isinstance(rhs, ast.Constant)
                        and not (isinstance(rhs, ast.Name) and rhs.id in fixture_names)):
                    return True
        if not isinstance(compare.ops[0], (ast.Eq, ast.Is, ast.IsNot)):
            continue
        if not (isinstance(rhs, ast.Constant) and isinstance(rhs.value, (int, float, bool))):
            continue
        if not (isinstance(lhs, ast.Call) and isinstance(lhs.func, ast.Attribute)
                and lhs.func.attr == "property" and lhs.args
                and isinstance(lhs.args[0], ast.Constant)
                and lhs.args[0].value in _MUTABLE_RECIPE_PROPERTIES):
            continue
        # A direct test-owned value set on that exact object before the assert
        # is an independent oracle (unlike merely observing the live default).
        receiver = ast.dump(lhs.func.value)
        independently_authored = any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "setProperty"
            and ast.dump(call.func.value) == receiver
            and call.args and isinstance(call.args[0], ast.Constant)
            and call.args[0].value == lhs.args[0].value
            and call.lineno < node.lineno
            for call in ast.walk(function)
        )
        if not independently_authored:
            return True
    return False



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


def _is_named_curated_theme_oracle(node: ast.AST) -> bool:
    """Detect *explicit named* repo theme files used as an artistic oracle.

    Generated/temp fixture paths are intentionally not included. More complex
    dynamic catalogue readers remain a review task, not a blanket failure.
    """
    values = _function_string_constants(node)
    named = any(
        (v.lower().endswith(('.srtheme', '.srwtheme')) and '{' not in v
         and v not in {'Default Dark.srtheme', 'Default Dark.srwtheme'})
        for v in values
    )
    return named and 'themes' in values and any(
        isinstance(n, ast.Name) and n.id in {'ROOT', '__file__'}
        for n in ast.walk(node)
    )


def _has_art_value_assert(node: ast.AST) -> bool:
    # Schema and stable identity checks are valid even for named user files;
    # only assertions about the hand-authored contents (colour, shadow, etc.)
    # are forbidden from using a shipped theme as oracle.
    artistic_fields = {'colors', 'shadows', 'gradients', 'backdrop'}
    for item in ast.walk(node):
        if isinstance(item, ast.Assert):
            if any(
                isinstance(sub, ast.Constant) and sub.value in artistic_fields
                for sub in ast.walk(item.test)
            ):
                return True
    return False


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


_AUTHORED_DEFAULT_SOURCE_PIN = re.compile(
    r"[\"'][a-z][a-z0-9_]*[\"']\s*:\s*(?:[\"'][^\"']+[\"']|true\b|false\b|[-+]?\d)",
    re.IGNORECASE,
)


def _default_source_text_names(function: ast.AST) -> set[str]:
    """Recognize tests reading shipped editable defaults as text/JSON."""
    names: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        value = node.value
        target_nodes = node.targets if isinstance(node, ast.Assign) else [node.target]
        strings = _function_string_constants(value)
        is_canonical_source = (
            "core/settings/default_settings.py" in strings
            and isinstance(value, ast.Call)
        )
        is_canonical_json = (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr == "dumps"
            and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                    and child.func.id == "build_defaults_snapshot" for child in ast.walk(value))
        )
        if is_canonical_source or is_canonical_json:
            for target in target_nodes:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _assert_copies_shipped_default_text(assertion: ast.Assert, names: set[str]) -> bool:
    if not names:
        return False
    for compare in ast.walk(assertion.test):
        if not isinstance(compare, ast.Compare) or not any(
            isinstance(op, ast.In) for op in compare.ops
        ):
            continue
        # Bound to an actual shipped source or serialized canonical tree, not
        # a test-owned settings object coincidentally named "defaults".
        if not any(isinstance(child, ast.Name) and child.id in names
                   for child in ast.walk(compare)):
            continue
        if any(isinstance(child, ast.Constant) and isinstance(child.value, str)
               and _AUTHORED_DEFAULT_SOURCE_PIN.search(child.value)
               for child in ast.walk(compare)):
            return True
    return False


def _canonical_value_origin(node: ast.AST, names: set[str], local_getters: set[str]) -> bool:
    """Track real canonical snapshots through field lookup and accessor calls.

    A test-owned fixture's ordinary mapping is not canonical. Callers of local
    helpers that parse ``core/settings/default_settings.py`` ARE canonical;
    otherwise AST-literal-eval indirection can disguise the same frozen oracle.
    """
    while isinstance(node, ast.Subscript):
        node = node.value
    if isinstance(node, ast.Name):
        return node.id in names or node.id in {"DEFAULT_SETTINGS", "CANONICAL_DEFAULTS"}
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id in {
            "get_default_settings", "get_base_default_settings", "get_raw_default_settings",
            "build_defaults_snapshot", *local_getters,
        }
    return False


def _source_parsing_canonical_helpers(tree: ast.AST) -> set[str]:
    """Identify local test helpers extracting *shipped* defaults from source.

    Do not treat arbitrary functions called ``default_widgets`` as production
    authorities; their body must actually point to the canonical source file.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        constants = _function_string_constants(node)
        has_canonical_name = any(
            isinstance(child, ast.Name) and child.id == "DEFAULT_SETTINGS"
            for child in ast.walk(node)
        ) or "DEFAULT_SETTINGS" in constants
        if "core/settings/default_settings.py" in constants and has_canonical_name:
            found.add(node.name)
    return found


def _canonical_source_snapshot_names(node: ast.AST) -> set[str]:
    """Catch the AST literal-eval escape hatch for copied shipped defaults."""
    constants = _function_string_constants(node)
    if "core/settings/default_settings.py" not in constants:
        return set()
    if "DEFAULT_SETTINGS" not in constants and not any(
        isinstance(child, ast.Name) and child.id == "DEFAULT_SETTINGS"
        for child in ast.walk(node)
    ):
        return set()
    names: set[str] = set()
    for assignment in ast.walk(node):
        if not isinstance(assignment, (ast.Assign, ast.AnnAssign)):
            continue
        value = assignment.value
        if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                and value.func.attr == "literal_eval"):
            continue
        targets = assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _canonical_snapshot_names(node: ast.AST, local_getters: set[str] | None = None) -> set[str]:
    names: set[str] = set()
    local_getters = local_getters or set()
    assignments: list[tuple[list[ast.AST], ast.AST]] = []
    for child in ast.walk(node):
        if not isinstance(child, (ast.Assign, ast.AnnAssign)):
            continue
        value = child.value
        if value is None:
            continue
        targets = child.targets if isinstance(child, ast.Assign) else [child.target]
        assignments.append((list(targets), value))
        is_authority = _canonical_value_origin(value, names, local_getters)
        if is_authority:
            for target in targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)

    changed = True
    while changed:
        changed = False
        for targets, value in assignments:
            if not _canonical_value_origin(value, names, local_getters):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in names:
                    names.add(target.id)
                    changed = True
    return names


def _canonical_monitor_catalog_findings(function: ast.AST, path: Path) -> list[Finding]:
    """Track only asserted route membership, retiring explicit fixture writes.

    Canonical mappings share an origin through aliases; changing their monitor
    field authors that origin. Scalar route aliases retain the value they read.
    No inference about SettingsManager repair outputs or nonoracle branches.
    """
    findings: list[Finding] = []
    authority_calls = {"build_defaults_snapshot", "get_default_settings",
                       "get_base_default_settings", "get_raw_default_settings"}

    def walk(statements, names, authored):
        def provenance(value):
            if isinstance(value, ast.Name):
                if value.id in {"DEFAULT_SETTINGS", "CANONICAL_DEFAULTS"}:
                    return ("mapping", value.id)
                return names.get(value.id)
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
                if value.func.id in authority_calls:
                    return ("mapping", id(value))
                if value.func.id == "str" and len(value.args) == 1:
                    return provenance(value.args[0])
            if (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                    and value.func.attr == "strip" and not value.args and not value.keywords):
                source = provenance(value.func.value)
                return source if source and source[0] == "route" else None
            if isinstance(value, ast.Subscript):
                source = provenance(value.value)
                if source and source[0] == "mapping":
                    if isinstance(value.slice, ast.Constant) and value.slice.value == "monitor":
                        return ("route", source[1]) if source[1] not in authored else None
                    return source
            return None

        for statement in statements:
            if isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
                source = provenance(statement.value)
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        if source is None:
                            names.pop(target.id, None)
                        else:
                            names[target.id] = source
                    elif (isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant)
                          and target.slice.value == "monitor"):
                        container = provenance(target.value)
                        if container and container[0] == "mapping":
                            authored.add(container[1])
            elif isinstance(statement, ast.Assert):
                for comparison in ast.walk(statement.test):
                    if not (isinstance(comparison, ast.Compare) and len(comparison.ops) == 1
                            and isinstance(comparison.ops[0], ast.In)):
                        continue
                    source = provenance(comparison.left)
                    catalog = comparison.comparators[0]
                    if not source or source[0] != "route" or not isinstance(catalog, (ast.Set, ast.List, ast.Tuple)):
                        continue
                    if any(isinstance(item, ast.Constant) and isinstance(item.value, str)
                           and item.value.isdecimal() for item in catalog.elts):
                        findings.append(Finding(
                            "canonical-monitor-catalog", path, comparison.lineno,
                            "numbered monitor routes are extensible; validate ALL or a positive integer instead of a finite default catalog",
                        ))
            # Branches are checked locally, without pretending a conditional
            # assignment executed unconditionally in a later assertion.
            elif isinstance(statement, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                walk(statement.body, dict(names), set(authored))
                walk(getattr(statement, "orelse", ()), dict(names), set(authored))
                for handler in getattr(statement, "handlers", ()):
                    walk(handler.body, dict(names), set(authored))
                walk(getattr(statement, "finalbody", ()), dict(names), set(authored))

    walk(function.body, {}, set())
    return findings


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

    parses_shipped_defaults = "core/settings/default_settings.py" in source
    local_canonical_getters = (
        _source_parsing_canonical_helpers(tree) if parses_shipped_defaults else set()
    )
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        canonical_default_names = _canonical_default_names(node)
        canonical_names = _canonical_snapshot_names(node, local_canonical_getters)
        if parses_shipped_defaults:
            canonical_names.update(_canonical_source_snapshot_names(node))
        findings.extend(_canonical_monitor_catalog_findings(node, path))
        markdown_names = _markdown_text_names(node)
        literal_fixture_names = _literal_fixture_names(node)
        for assertion in ast.walk(node):
            if (isinstance(assertion, ast.Assert)
                    and _assert_has_unowned_recipe_pin(assertion, node, literal_fixture_names)):
                findings.append(Finding(
                    "mutable-presentation-recipe-pin", path, assertion.lineno,
                    "do not assert today's visual recipe; exercise explicit settings, semantic routing and fallback instead",
                ))
        shipped_default_source_names = (
            _default_source_text_names(node)
            if parses_shipped_defaults or "build_defaults_snapshot" in source else set()
        )
        for child in ast.walk(node):
            if not isinstance(child, ast.Assert):
                continue
            if _assert_copies_shipped_default_text(child, shipped_default_source_names):
                findings.append(Finding(
                    "authored-default-source-string",
                    path, child.lineno,
                    "copied an editable default's current textual value; assert schema, owner/consumer agreement, or test-owned round-trip",
                ))
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

        # A branch that *interprets* an authored value is not an oracle.
        # Only asserted equality with a copied literal freezes that value.
        for assertion in ast.walk(node):
            if not isinstance(assertion, ast.Assert):
                continue
            for child in ast.walk(assertion.test):
                if not (
                    isinstance(child, ast.Compare)
                    and len(child.ops) == 1
                    and isinstance(child.ops[0], (ast.Eq, ast.Is))
                ):
                    continue
                sides = [child.left, *child.comparators]
                if (
                    any(_canonical_value_origin(side, canonical_names, local_canonical_getters) for side in sides)
                    and any(_is_literal(side) for side in sides)
                ):
                    findings.append(
                        Finding(
                            "canonical-snapshot-literal",
                            path,
                            child.lineno,
                            "assert schema/relationship or compare to the canonical authority; do not pin a mutable authored default",
                        )
                    )

        if _is_named_curated_theme_oracle(node) and _has_art_value_assert(node):
            findings.append(Finding(
                "named-shipped-theme-art-oracle", path, node.lineno,
                "a named operator-authored theme is used as an artistic value golden; use test-owned theme data",
            ))
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
    candidates = list(paths) if paths is not None else sorted(
        [*TEST_ROOT.rglob("test_*.py"), *ROOT.joinpath("tools").glob("test_*.py"),
         *ROOT.joinpath(".github", "tests").rglob("test_*.py")]
    )
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
