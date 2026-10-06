"""Review test assertions that may copy today's canonical defaults.

Run::

    python tools/default_pin_scan.py
    python tools/default_pin_scan.py --summary

This is review-only. It deliberately does not fail the suite. The scanner removes
high-confidence fixture round-trips from its queue: when the same test explicitly
authors ``{key: value}`` before asserting that key/value, the literal belongs to
the fixture rather than being an unexplained copy of the production default.
The blocking high-confidence bar remains ``tools/test_durability_audit.py``.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.settings.default_contract import get_raw_default_settings  # noqa: E402

_EXACT_MARKER = "EXACT-VALUE INVARIANT"
_SELF_TEST_FILES = {"test_default_pin_scan.py", "test_test_suite_durability.py"}


def flatten(node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, dict):
                flatten(v, out)
            else:
                out.setdefault(str(k), []).append(v)
    return out


def _literal_value(node: ast.AST):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def _fixture_pairs_before(function: ast.AST, line: int) -> set[tuple[str, str]]:
    """Return literal mapping entries explicitly authored before ``line``.

    This intentionally recognizes only high-confidence dict-literal fixtures.
    Control setters, helper calls and computed mappings stay in the review queue.
    """

    pairs: set[tuple[str, str]] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Dict) or getattr(node, "lineno", line) >= line:
            continue
        for key_node, value_node in zip(node.keys, node.values):
            if key_node is None:
                continue
            key = _literal_value(key_node)
            value = _literal_value(value_node)
            if isinstance(key, str):
                pairs.add((key, repr(value)))
    return pairs


def _has_exact_marker(lines: list[str], line: int) -> bool:
    start = max(0, line - 5)
    return any(_EXACT_MARKER in text for text in lines[start:line])


def scan_file(path: Path, defaults: dict[str, list[object]]) -> list[tuple[str, int, str, object, str]]:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    lines = source.splitlines()
    hits: list[tuple[str, int, str, object, str]] = []

    functions = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    # Nested functions own their assertions before their parents do.
    functions.sort(key=lambda node: (node.end_lineno - node.lineno, node.lineno))
    scopes: list[ast.AST] = functions + [tree]
    seen_asserts: set[int] = set()
    for scope in scopes:
        for node in ast.walk(scope):
            if not isinstance(node, ast.Assert) or id(node) in seen_asserts:
                continue
            seen_asserts.add(id(node))
            if _has_exact_marker(lines, node.lineno):
                continue
            fixture_pairs = _fixture_pairs_before(scope, node.lineno)
            consts = [n.value for n in ast.walk(node.test) if isinstance(n, ast.Constant)]
            keys = [c for c in consts if isinstance(c, str) and c in defaults]
            literals = [c for c in consts if not (isinstance(c, str) and c in defaults)]
            for key in keys:
                for value in defaults[key]:
                    if isinstance(value, bool) or value in (None, "", 0, 0.0, 1, 1.0):
                        continue
                    if (key, repr(value)) in fixture_pairs:
                        continue
                    if value in literals or (
                        isinstance(value, list)
                        and any(isinstance(literal, (list, tuple)) for literal in literals)
                    ):
                        hits.append(
                            (
                                path.name,
                                node.lineno,
                                key,
                                value,
                                lines[node.lineno - 1].strip()[:110],
                            )
                        )
    return hits


def scan_tests(root: Path = ROOT) -> list[tuple[str, int, str, object, str]]:
    defaults = flatten(get_raw_default_settings(), {})
    hits = []
    for path in sorted((root / "tests").glob("test_*.py")):
        if path.name in _SELF_TEST_FILES:
            continue
        hits.extend(scan_file(path, defaults))
    return sorted(set(hits))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    hits = scan_tests()
    by_file: dict[str, int] = {}
    for hit in hits:
        by_file[hit[0]] = by_file.get(hit[0], 0) + 1
    if "--summary" in argv:
        for name, count in sorted(by_file.items(), key=lambda item: -item[1]):
            print(f"{count:4d}  {name}")
    else:
        for hit in hits:
            print(*hit, sep=" | ")
    print(len(hits), "candidate pins in", len(by_file), "files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
