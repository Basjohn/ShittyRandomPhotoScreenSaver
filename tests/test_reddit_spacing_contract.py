"""Source contract for stable full-list age/AGO/title rails and projected gap."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml" / "RedditPresentation.qml"


def test_reddit_flipped_age_value_and_ago_stay_legible_in_any_column_order():
    source = QML.read_text(encoding="utf-8")
    assert '9.0 / Math.max(0.2, redditRoot.presentationScale)' in source
    assert 'readonly property real ageValueAgoGap: 2.0' in source
    assert 'visualColumnOrder' in source
    assert '["age", "ago", "title"]' in source
    assert '["title", "age", "ago"]' in source
    assert 'postRow.columnX("age") - ageText.x' in source
    assert 'postRow.columnX("ago") - ageText.x' in source
    assert 'postRow.columnX("title")' in source
    assert 'postRow.columnWidth("title")' in source
    assert 'Math.max(44.0, redditRoot.redditModel.ageFontSize * 4.4)' in source
    assert 'readonly property var columnTargets:' in source
    assert 'LayoutMirroring.enabled:' not in source
    assert 'childOffsetX("post_titles")' not in source
