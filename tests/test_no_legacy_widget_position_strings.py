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

        if "WidgetPosition." in text:
            violations.append(rel)

    assert not violations, (
        "Legacy WidgetPosition-prefixed strings found outside tests: "
        + ", ".join(str(path) for path in violations)
    )
