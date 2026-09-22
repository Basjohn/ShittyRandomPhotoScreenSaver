"""Import-free event-driven click-affordance contract for external-link surfaces."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml"


def _text(name: str) -> str:
    return (QML / name).read_text("utf-8")


def test_direct_external_link_surfaces_have_event_driven_hover_clarity():
    branded = _text("BrandedHeader.qml")
    feeds = _text("FeedPresentation.qml")
    reddit = _text("RedditPresentation.qml")
    gmail = _text("GmailPresentation.qml")
    followed = _text("GamesYouFollowPresentation.qml")

    assert "id: headerHover" in branded and "cursorShape: Qt.PointingHandCursor" in branded
    assert 'objectName: "feedListHoverFrame" + index' in feeds
    assert "id: listHover" in feeds and "id: gridHover" in feeds
    assert 'objectName: "redditPostHoverFrame_" + postRow.index' in reddit
    assert "id: postHover" in reddit and "cursorShape: Qt.PointingHandCursor" in reddit
    assert "postHover.hovered && postRow.canActivate" in reddit
    assert 'objectName: "gmailMessageHoverFrame_" + messageRow.index' in gmail
    assert "id: messageHover" in gmail and "cursorShape: Qt.PointingHandCursor" in gmail
    assert "messageHover.hovered && openArea.canActivate" in gmail
    assert "id: tileHover" in followed and "cursorShape: Qt.PointingHandCursor" in followed

    # Affordance is hover/input-event driven only. It must never grow a cadence.
    for source in (branded, feeds, reddit, gmail, followed):
        assert "Timer {" not in source


def test_steam_friend_and_store_actions_reuse_pointer_hover_not_polling():
    friend = _text("FriendPulsePresentation.qml")
    achievement = _text("AchievementPulsePresentation.qml")
    abandonment = _text("AbandonmentIssuesPresentation.qml")
    for hover_id in ("rowAvatarHover", "rowGameHover", "rowMenuHover",
                     "gridAvatarHover", "gridGameHover", "gridMenuHover", "actionHover"):
        marker = f"id: {hover_id}; cursorShape: Qt.PointingHandCursor"
        assert marker in friend
    for source in (achievement, abandonment):
        compact = " ".join(source.split())
        assert "id: artworkHover cursorShape: Qt.PointingHandCursor" in compact
        assert "Timer {" not in source
