"""Static parity contract for Reddit's retained left time rail."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml" / "RedditPresentation.qml"


def test_reddit_ago_column_is_tightened_without_moving_title_rail() -> None:
    source = QML.read_text(encoding="utf-8")
    assert 'objectName: "redditPostAgeAgo_" + postRow.index' in source
    assert "anchors.rightMargin: 17.0" in source
    assert "readonly property real canonicalTitleX: canonicalAgeWidth + 4.0" in source
    assert "readonly property real authoredBaseX: postRow.canonicalTitleX" in source
    assert 'x: authoredBaseX + redditRoot.childOffsetX("post_titles")' in source
    assert "anchors.left: ageText.right" not in source
