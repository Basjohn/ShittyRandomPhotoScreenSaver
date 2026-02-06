"""Guards against reintroducing legacy WidgetPosition-prefixed strings in runtime code."""

from __future__ import annotations

from pathlib import Path


def test_no_widgetposition_prefixes_outside_tests() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    violations: list[Path] = []

    for path in repo_root.rglob("*.py"):
        # Allow dedicated regression tests to exercise legacy strings explicitly.
        try:
            rel = path.relative_to(repo_root)
        except ValueError:
            rel = path

        if "tests" in rel.parts:
            continue
        if ".__" in rel.name:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        # Only flag legacy STRING LITERALS like "WidgetPosition.TOP_LEFT" in quotes,
        # not legitimate enum references like WidgetPosition.TOP_RIGHT in code.
        # Also exclude normalization.py which legitimately handles legacy conversion.
        if "normalization" in rel.name:
            continue
        in_docstring = False
        found = False
        for line in text.splitlines():
            stripped = line.strip()
            # Track multi-line docstrings
            for delim in ('"""', "'''"):
                count = stripped.count(delim)
                if count == 1:
                    in_docstring = not in_docstring
                # count >= 2 means open+close on same line (no state change)
            if in_docstring:
                continue
            # Skip comments
            if stripped.startswith("#"):
                continue
            # Check for quoted legacy strings: "WidgetPosition." or 'WidgetPosition.'
            if '"WidgetPosition.' in line or "'WidgetPosition." in line:
                found = True
                break
        if found:
            violations.append(rel)

    assert not violations, (
        "Legacy WidgetPosition-prefixed strings found outside tests: "
        + ", ".join(str(path) for path in violations)
    )
