"""Import-free hover/cursor parity for clickable retained widget surfaces.

The contract is deliberately paint/input-only: no timers, polling, source work,
or geometry publication may be introduced merely to advertise clickability.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml"


def _text(name: str) -> str:
    return (QML / name).read_text("utf-8")


def test_text_dense_rows_use_surface_text_feedback_without_cutting_strokes():
    feeds = _text("FeedPresentation.qml")
    reddit = _text("RedditPresentation.qml")
    gmail = _text("GmailPresentation.qml")

    for source, marker in (
        (feeds, 'objectName: "feedListHoverFrame" + index'),
        (reddit, 'objectName: "redditPostHoverFrame_" + postRow.index'),
        (gmail, 'objectName: "gmailMessageHoverFrame_" + messageRow.index'),
    ):
        section = source.split(marker, 1)[1].split("HoverHandler {", 1)[0]
        assert "anchors.margins: 2.0" in section
        assert "0.065" in section
        assert "border.width: 0.0" in section

    # Hover is neutral bright white across families. Semantic color belongs to
    # the resting presentation/state, not to mutually inconsistent hover cues.
    reddit_title = reddit.split("id: titleText", 1)[1].split("font.family", 1)[0]
    gmail_subject = gmail.split("id: subjectText", 1)[1].split("font.family", 1)[0]
    assert "postHover.hovered" in reddit_title and '? "white"' in reddit_title
    assert "messageHover.hovered" in gmail_subject and '? "white"' in gmail_subject
    reddit_separator = reddit.split('objectName: "redditPostSeparator_" + postRow.index', 1)[1].split("}", 1)[0]
    gmail_separator = gmail.split('objectName: "gmailSeparator_" + messageRow.index', 1)[1].split("}", 1)[0]
    assert 'postHover.hovered && postRow.canActivate' in reddit_separator and '? "white"' in reddit_separator
    assert 'messageHover.hovered && openArea.canActivate' in gmail_separator and '? "white"' in gmail_separator

    # Grid/card surfaces may retain a proper card outline because it does not
    # cross a compact text rail. Active card/story outlines use the same white cue.
    assert "id: gridHover" in feeds and "scaleAwareStrokeWidth(1.25)" in feeds
    assert '? "white" : feedRoot.feedModel.headerBorderColor' in feeds
    followed = _text("GamesYouFollowPresentation.qml")
    assert 'objectName: "followedStoryHoverOutline" + storySlot' in followed
    assert "id: tileHover" in followed and "cursorShape: Qt.PointingHandCursor" in followed
    followed_hover = followed.split('objectName: "followedStoryHoverOutline" + storySlot', 1)[1].split("TapHandler", 1)[0]
    assert 'border.color: "white"' in followed_hover
    refresh = followed.split('objectName: "followedRefreshTarget"', 1)[1].split("TapHandler", 1)[0]
    assert '? "white"' in refresh

    branded = _text("BrandedHeader.qml")
    assert 'headerHover.hovered && header.interactionEnabled' in branded
    assert '? "white" : header.borderColor' in branded

    assert "id: actionHover" in gmail
    gmail_action = gmail.split("id: actionHover", 1)[1].split("}", 1)[0]
    assert "cursorShape: Qt.PointingHandCursor" in gmail_action

    for source in (feeds, reddit, gmail, followed):
        assert "Timer {" not in source


def test_friend_pulse_click_targets_have_obvious_white_hover_feedback():
    friend = _text("FriendPulsePresentation.qml")

    # Friend-profile click lives on the avatar, so avatar/name and independent
    # game actions all use the same bright-white hover cue.
    assert "rowAvatarHover.hovered && rowAvatarHover.enabled ? 2.25 : 1.0" in friend
    row_name = friend.split("id: rowNameText", 1)[1].split("font.family", 1)[0]
    assert "rowAvatarHover.hovered" in row_name and '? "white"' in row_name
    assert "gridAvatarHover.hovered && gridAvatarHover.enabled ? 2.25 : 1.0" in friend
    grid_name = friend.split("id: gridNameText", 1)[1].split("font.family", 1)[0]
    assert "gridAvatarHover.hovered" in grid_name and '? "white"' in grid_name
    assert 'color: rowGameHover.hovered ? "white"' in friend
    assert 'color: gridGameHover.hovered ? "white"' in friend
    assert 'rowAvatarHover.hovered && rowAvatarHover.enabled\n                        ? "white"' in friend
    assert 'gridAvatarHover.hovered && gridAvatarHover.enabled\n                            ? "white"' in friend
    # Semantic accent remains a resting/selected-state color, never the hover
    # transition itself. Neutral washes cover pin/menu/action targets.
    assert "rowAvatarHover.hovered ? 0.38 : 0.22" not in friend
    assert "gridAvatarHover.hovered ? 0.38 : 0.22" not in friend
    assert "rowMenuHover.hovered ? Qt.rgba(1.0, 1.0, 1.0, 0.14)" in friend
    assert "gridMenuHover.hovered ? Qt.rgba(1.0, 1.0, 1.0, 0.14)" in friend
    assert "actionHover.hovered ? Qt.rgba(1.0, 1.0, 1.0, 0.12)" in friend
    assert "Timer {" not in friend


def test_steam_artwork_click_hover_uses_one_full_stroke_language():
    achievement = _text("AchievementPulsePresentation.qml")
    abandonment = _text("AbandonmentIssuesPresentation.qml")

    assert 'objectName: "achievementArtworkBorder"' in achievement
    assert "border.color: artworkHover.hovered" in achievement
    assert '? "white" : achievementRoot.achievementModel.steamArtworkBorderColor' in achievement
    assert "artworkFrame.artworkStrokeWidth" in achievement

    # Abandonment's decorative stripes/image remain clipped, but the hover
    # outline is a sibling so clip cannot amputate half the white active stroke.
    assert 'objectName: "abandonmentArtworkHoverBorder"' in abandonment
    hover_border = abandonment.split('objectName: "abandonmentArtworkHoverBorder"', 1)[1].split("HoverHandler", 1)[0]
    assert "x: artworkFrame.x" in hover_border
    assert "width: artworkFrame.width" in hover_border
    assert "border.color: artworkHover.hovered" in hover_border
    assert '? "white" : abandonmentRoot.abandonmentModel.steamArtworkBorderColor' in hover_border
    assert "border.width: artworkFrame.artworkStrokeWidth" in hover_border


def test_media_seek_and_transport_use_pointer_and_gesture_feedback_without_hover_borders():
    media = _text("MediaPresentation.qml")

    assert 'objectName: "mediaProgressHoverWash"' in media
    seek = media.split('id: progressSeekArea', 1)[1].split('}', 1)[0]
    assert "hoverEnabled: enabled" in seek
    assert "cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor" in seek
    assert "border." not in seek

    for button_id, hover_id, tap_id in (
        ("previousButton", "previousHover", "previousTap"),
        ("playPauseButton", "playPauseHover", "playPauseTap"),
        ("nextButton", "nextHover", "nextTap"),
    ):
        section = media.split(f"id: {button_id}", 1)[1].split("TapHandler {", 1)[0]
        assert f"id: {hover_id}" in section
        assert "cursorShape: Qt.PointingHandCursor" in section
        assert "1.055" in section
        assert "border.color" not in section
        assert "border.width" not in section
        assert f"enabled: {tap_id}.enabled" in section

    assert "id: systemMuteHover" in media
    assert 'objectName: "mediaAppVolumeInputArea"' in media
    assert media.count("cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor") >= 2
    assert "Timer {" not in media
