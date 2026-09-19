"""Static contract for Reddit's compact flipped title / age / AGO rails."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml" / "RedditPresentation.qml"


def test_reddit_flipped_age_value_precedes_ago_close_to_post_title() -> None:
    source = QML.read_text(encoding="utf-8")
    assert 'readonly property real flippedTitleAgeGap: 4.0' in source
    assert 'objectName: "redditPostAgeAgo_" + postRow.index' in source
    assert 'x: redditRoot.headerFlipped ? parent.width - width : 0.0' in source
    assert 'parent.width - ageText.width - redditRoot.flippedTitleAgeGap' in source
    assert 'readonly property real ageValueAgoGap: 4.0' in source
    assert 'ageValueText.width + redditRoot.ageValueAgoGap' in source
    assert 'titleText.x + titleText.width + redditRoot.flippedTitleAgeGap' not in source
    assert 'x: 0.0' in source.split('id: ageValueText', 1)[1].split('id: ageAgoText', 1)[0]
    assert 'LayoutMirroring.enabled:' not in source
    assert 'childOffsetX("post_titles")' not in source
