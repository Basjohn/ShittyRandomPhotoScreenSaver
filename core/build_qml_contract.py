"""Import-light source checks for QML mistakes that must block packaging.

This intentionally does not replace Qt's QQmlComponent compile gate.  It catches
one high-value class of source error without importing PySide6 so Build Foundry
can reject malformed QML even before a native Qt runtime is available.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

_PROPERTY_ASSIGNMENT = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_.]*)\s*:")


@dataclass(frozen=True)
class QmlSourceIssue:
    path: Path
    property_name: str
    first_line: int
    second_line: int

    def render(self, root: Path | None = None) -> str:
        path = self.path
        if root is not None:
            try:
                path = path.relative_to(root)
            except ValueError:
                pass
        return (
            f"{path.as_posix()}:{self.second_line}: property {self.property_name!r} "
            f"is assigned more than once in the same QML object "
            f"(first assignment line {self.first_line})"
        )


def _code_only_lines(text: str) -> list[str]:
    """Remove comments/string contents while retaining structural punctuation."""
    lines: list[str] = []
    in_block_comment = False
    quote: str | None = None
    escaped = False
    current: list[str] = []

    i = 0
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if ch == "\n":
            lines.append("".join(current))
            current = []
            if quote not in {"`"}:
                # Ordinary QML/JS quoted strings cannot cross a raw newline.
                quote = None
                escaped = False
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                current.extend("  ")
                i += 2
            else:
                current.append(" ")
                i += 1
            continue

        if quote is not None:
            if escaped:
                escaped = False
                current.append(" ")
            elif ch == "\\":
                escaped = True
                current.append(" ")
            elif ch == quote:
                quote = None
                current.append(" ")
            else:
                current.append(" ")
            i += 1
            continue

        if ch == "/" and nxt == "*":
            in_block_comment = True
            current.extend("  ")
            i += 2
            continue
        if ch == "/" and nxt == "/":
            # Preserve column shape only; the rest of this physical line is a comment.
            current.extend(" " * (len(text) - i if "\n" not in text[i:] else text[i:].find("\n")))
            i = text.find("\n", i)
            if i == -1:
                i = len(text)
            continue
        if ch in {'"', "'", "`"}:
            quote = ch
            current.append(" ")
            i += 1
            continue

        current.append(ch)
        i += 1

    if current or not text.endswith("\n"):
        lines.append("".join(current))
    return lines


def duplicate_direct_property_assignments(path: Path) -> tuple[QmlSourceIssue, ...]:
    """Return repeated direct property bindings within the same brace scope."""
    text = path.read_text(encoding="utf-8")
    lines = _code_only_lines(text)
    scopes: list[dict[str, int]] = [{}]
    issues: list[QmlSourceIssue] = []

    for lineno, line in enumerate(lines, 1):
        match = _PROPERTY_ASSIGNMENT.match(line)
        if match:
            name = match.group(1)
            first = scopes[-1].get(name)
            if first is not None:
                issues.append(QmlSourceIssue(path, name, first, lineno))
            else:
                scopes[-1][name] = lineno

        for ch in line:
            if ch == "{":
                scopes.append({})
            elif ch == "}" and len(scopes) > 1:
                scopes.pop()

    return tuple(issues)


def audit_qml_source_contract(repo_root: Path) -> tuple[QmlSourceIssue, ...]:
    qml_root = repo_root / "rendering" / "quick" / "qml"
    if not qml_root.is_dir():
        return ()
    issues: list[QmlSourceIssue] = []
    for path in sorted(qml_root.rglob("*.qml")):
        issues.extend(duplicate_direct_property_assignments(path))
    return tuple(issues)
