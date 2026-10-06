"""Review-only scanner for brittle source oracles and operator-intrusive tests.

This tool is intentionally advisory. Static architecture tests can be valuable,
and some native/GL/input tests genuinely require an exposed platform window.
The goal is to surface candidates for human classification, not to make either
pattern automatically illegal.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "tests"

_SOURCE_MARKER = "SOURCE-ORACLE INVARIANT"
_VISIBLE_MARKER = "VISIBLE-WINDOW INVARIANT"
_UI_COPY_MARKER = "UI-COPY INVARIANT"
_SAFE_WINDOW_TOKENS = (
    "keep_off_screen",
    "WA_DontShowOnScreen",
    'QT_QPA_PLATFORM"] = "offscreen"',
    "QT_QPA_PLATFORM', 'offscreen'",
    'QT_QPA_PLATFORM\"] = \"offscreen\"',
    '"QT_QPA_PLATFORM": "offscreen"',
    "WindowTransparentForInput",
    "setOpacity(0",
    "setWindowOpacity(0",
)
_INTRUSIVE_CALLS = {"show", "showFullScreen", "showMaximized", "raise_", "activateWindow"}
_SELF_TEST_FILES = {"test_test_oracle_review.py", "test_test_suite_durability.py"}


@dataclass(frozen=True)
class Candidate:
    kind: str
    path: Path
    line: int
    detail: str

    def render(self) -> str:
        try:
            display = self.path.relative_to(ROOT)
        except ValueError:
            display = self.path
        return f"{display}:{self.line}: [{self.kind}] {self.detail}"


def _has_marker(lines: list[str], line: int, marker: str) -> bool:
    start = max(0, line - 6)
    return any(marker in text for text in lines[start:line])


def _read_text_names(function: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr in {"read_text", "read_bytes"}
        ):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _assert_references_name_and_string(node: ast.Assert, names: set[str]) -> bool:
    refs = {child.id for child in ast.walk(node.test) if isinstance(child, ast.Name)}
    if not refs.intersection(names):
        return False
    return any(
        isinstance(child, ast.Constant) and isinstance(child.value, str)
        for child in ast.walk(node.test)
    )




def _is_text_call(node: ast.AST) -> bool:
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "text"
        and not node.args
        and not node.keywords
    ):
        return False
    # QApplication.clipboard().text() is test output/data, not widget copy.
    receiver = node.func.value
    return not (
        isinstance(receiver, ast.Call)
        and isinstance(receiver.func, ast.Attribute)
        and receiver.func.attr == "clipboard"
    )


def _assert_is_direct_ui_copy_equality(node: ast.Assert) -> bool:
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    if len(test.comparators) != 1:
        return False
    left, right = test.left, test.comparators[0]

    def literal_text(value: ast.AST) -> bool:
        return (
            isinstance(value, ast.Constant) and isinstance(value.value, str)
        ) or isinstance(value, ast.JoinedStr)

    return (_is_text_call(left) and literal_text(right)) or (_is_text_call(right) and literal_text(left))

def _modal_receiver_name(node: ast.Call) -> str | None:
    if not isinstance(node.func, ast.Attribute) or node.func.attr not in {"exec", "exec_"}:
        return None
    receiver = node.func.value
    if isinstance(receiver, ast.Name):
        name = receiver.id
    elif isinstance(receiver, ast.Attribute):
        name = receiver.attr
    else:
        return None
    lowered = name.casefold()
    return name if ("dialog" in lowered or "popup" in lowered or "message" in lowered) else None


def review_test_file(path: Path) -> list[Candidate]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    found: list[Candidate] = []

    for function in (
        node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        source_names = _read_text_names(function)
        if source_names:
            for node in ast.walk(function):
                if (
                    isinstance(node, ast.Assert)
                    and _assert_references_name_and_string(node, source_names)
                    and not _has_marker(lines, node.lineno, _SOURCE_MARKER)
                ):
                    found.append(
                        Candidate(
                            "source-string-oracle",
                            path,
                            node.lineno,
                            "asserts literal source spelling; keep only when spelling/absence is the architecture contract",
                        )
                    )

        for node in ast.walk(function):
            if (
                isinstance(node, ast.Assert)
                and _assert_is_direct_ui_copy_equality(node)
                and not _has_marker(lines, node.lineno, _UI_COPY_MARKER)
            ):
                found.append(
                    Candidate(
                        "ui-copy-oracle",
                        path,
                        node.lineno,
                        "asserts exact widget text; keep exact copy only when wording itself is the product contract",
                    )
                )

        function_text = "\n".join(lines[function.lineno - 1 : function.end_lineno])
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            receiver = _modal_receiver_name(node)
            if receiver is None:
                continue
            local_safe = (
                "WA_DontShowOnScreen" in function_text
                or f"keep_off_screen({receiver})" in function_text
            )
            if not local_safe and not _has_marker(lines, node.lineno, _VISIBLE_MARKER):
                found.append(
                    Candidate(
                        "modal-dialog-candidate",
                        path,
                        node.lineno,
                        f"{receiver}.exec() may briefly expose/activate a modal test window; use WA_DontShowOnScreen when visibility is not the contract",
                    )
                )

        safe = any(token in function_text for token in _SAFE_WINDOW_TOKENS)
        if safe:
            continue
        for node in ast.walk(function):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in _INTRUSIVE_CALLS:
                continue
            if _has_marker(lines, node.lineno, _VISIBLE_MARKER):
                continue
            found.append(
                Candidate(
                    "visible-window-candidate",
                    path,
                    node.lineno,
                    f".{node.func.attr}() may expose/activate a test window; prefer offscreen or keep_off_screen when evidence permits",
                )
            )

    return found


def review_tests(paths: Iterable[Path] | None = None) -> list[Candidate]:
    candidates = (
        list(paths)
        if paths is not None
        else [path for path in sorted(TEST_ROOT.glob("test_*.py")) if path.name not in _SELF_TEST_FILES]
    )
    found: list[Candidate] = []
    for path in candidates:
        found.extend(review_test_file(Path(path)))
    return sorted(found, key=lambda item: (str(item.path), item.line, item.kind))


def main() -> int:
    found = review_tests()
    try:
        for item in found:
            print(item.render())
        source_count = sum(item.kind == "source-string-oracle" for item in found)
        copy_count = sum(item.kind == "ui-copy-oracle" for item in found)
        window_count = sum(
            item.kind in {"visible-window-candidate", "modal-dialog-candidate"}
            for item in found
        )
        print(
            f"\nReview queue: {source_count} source-string oracle(s), "
            f"{copy_count} exact UI-copy oracle(s), "
            f"{window_count} potentially visible/focus-stealing window operation(s)."
        )
        print("Review-only: always exits 0; never skip/xfail/stop a test or request operator action solely because of this queue.")
    except BrokenPipeError:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
