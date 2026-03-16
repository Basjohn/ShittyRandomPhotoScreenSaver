#!/usr/bin/env python3
"""Static parity checks for settings UI widgets.

This script scans the UI tab modules and reports places where base Qt widgets
(QSlider/QComboBox/QFontComboBox) are instantiated directly instead of using the
shared helpers (`NoWheelSlider`, `StyledComboBox`, `StyledFontComboBox`).

Extend `BANNED_CALLS` / `BANNED_BASES` to enforce new rules as the styling
contract evolves.
"""
from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

# Relative (from repo root) paths that are noise for these checks. These modules
# legitimately touch the base widgets while defining the shared helpers.
DEFAULT_SKIP_PATHS = {
    Path("ui/tabs/shared_styles.py"),
}

# Base widget calls we never want to see inside settings tabs.
BANNED_CALLS = {
    "QSlider": "Use NoWheelSlider from ui.tabs.shared_styles instead of QSlider.",
    "QComboBox": "Use StyledComboBox for settings dropdowns (chrome + knob overlay).",
    "QFontComboBox": "Use StyledFontComboBox so font previews inherit shared chrome.",
}

# Likewise, disallow new subclasses based on the raw Qt widgets.
BANNED_BASES = {
    "QSlider": "Subclass NoWheelSlider (or its successors) instead of QSlider directly.",
    "QComboBox": "Subclass StyledComboBox instead of QComboBox inside settings tabs.",
    "QFontComboBox": "Subclass StyledFontComboBox instead of QFontComboBox.",
}


@dataclass
class Violation:
    path: Path
    line: int
    column: int
    message: str
    rule: str

    def format(self, root: Path) -> str:
        try:
            rel = self.path.relative_to(root)
        except ValueError:
            rel = self.path
        return f"{rel}:{self.line}:{self.column}: {self.message} ({self.rule})"


class ParityVisitor(ast.NodeVisitor):
    def __init__(self, filename: Path) -> None:
        self.filename = filename
        self.violations: list[Violation] = []

    # -- helpers -----------------------------------------------------------------
    @staticmethod
    def _extract_name(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

    def _add(self, node: ast.AST, message: str, rule: str) -> None:
        line = getattr(node, "lineno", 0)
        col = getattr(node, "col_offset", 0) + 1
        self.violations.append(
            Violation(self.filename, line, col, message=message, rule=rule)
        )

    # -- AST hooks ---------------------------------------------------------------
    def visit_Call(self, node: ast.Call) -> None:  # type: ignore[override]
        name = self._extract_name(node.func)
        if name in BANNED_CALLS:
            self._add(node, BANNED_CALLS[name], f"banned_call:{name}")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # type: ignore[override]
        for base in node.bases:
            base_name = self._extract_name(base)
            if base_name in BANNED_BASES:
                self._add(node, BANNED_BASES[base_name], f"banned_base:{base_name}")
        self.generic_visit(node)


def iter_python_files(paths: Sequence[Path]) -> Iterator[Path]:
    for path in paths:
        if path.is_dir():
            yield from sorted(p for p in path.rglob("*.py") if p.is_file())
        elif path.suffix == ".py":
            yield path


def normalize_paths(entries: Sequence[str], root: Path) -> list[Path]:
    resolved: list[Path] = []
    for entry in entries:
        path = Path(entry)
        if not path.is_absolute():
            path = (root / path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {entry}")
        resolved.append(path)
    return resolved


def build_skip_set(entries: Iterable[str], root: Path) -> set[Path]:
    skip_paths: set[Path] = set(DEFAULT_SKIP_PATHS)
    for entry in entries:
        path = Path(entry)
        if not path.is_absolute():
            path = (root / path).resolve()
        skip_paths.add(path.relative_to(root) if path.exists() else Path(entry))
    return skip_paths


def should_skip(path: Path, root: Path, skip_set: set[Path]) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    return rel in skip_set


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check settings UI parity rules.")
    parser.add_argument(
        "paths",
        nargs="*",
        default=["ui/tabs"],
        help="Directories/files to scan (default: ui/tabs).",
    )
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="Repository root (defaults to script/../..).",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        help="Additional paths to skip (relative to root).",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    paths = normalize_paths(args.paths, root)
    skip_set = build_skip_set(args.skip or [], root)

    all_violations: list[Violation] = []
    scanned_files = 0

    for file_path in iter_python_files(paths):
        if should_skip(file_path, root, skip_set):
            continue
        scanned_files += 1
        source = file_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as exc:  # pragma: no cover - fails fast
            print(f"Failed to parse {file_path}: {exc}", file=sys.stderr)
            return 2
        visitor = ParityVisitor(file_path)
        visitor.visit(tree)
        all_violations.extend(visitor.violations)

    if all_violations:
        for violation in sorted(all_violations, key=lambda v: (v.path, v.line, v.column)):
            print(violation.format(root))
        print(
            f"\nParity check FAILED: {len(all_violations)} violation(s) across {scanned_files} file(s).",
            file=sys.stderr,
        )
        return 1

    print(f"Parity check passed across {scanned_files} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
