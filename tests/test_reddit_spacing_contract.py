"""Minimal compatibility guard for Reddit column-order semantics.

Spacing, sizes and exact positioning expressions are visual/layout decisions,
not source-text goldens; validate readability with native scene inspection.
"""
from pathlib import Path

QML = Path(__file__).resolve().parents[1] / "rendering/quick/qml/RedditPresentation.qml"


def test_reddit_column_order_keeps_distinct_semantic_rails() -> None:
    source = QML.read_text(encoding="utf-8")
    assert "visualColumnOrder" in source
    for role in ("age", "ago", "title"):
        assert f'postRow.columnX("{role}")' in source
    assert 'postRow.columnWidth("title")' in source
    # A general-purpose layout mirror must not silently reverse these roles.
    assert "LayoutMirroring.enabled:" not in source
