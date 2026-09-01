"""Static guard for the retained dynamic-artwork fade invariant."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml"


def test_shared_artwork_fade_primitive_is_event_driven_and_timerless() -> None:
    source = (QML / "ArtworkFadeImage.qml").read_text(encoding="utf-8")

    assert source.count("NumberAnimation {") == 2
    assert "Qt.callLater" in source
    assert "Image.Ready" in source
    assert "fadeOut.running" in source
    assert "QTimer" not in source
    assert "Timer {" not in source
    assert "onSourceChanged" in source


def test_all_current_dynamic_artwork_surfaces_use_shared_fade_primitive() -> None:
    cases = {
        "MediaPresentation.qml": (
            "mediaRoot.mediaModel.artworkSource",
            1,
        ),
        "AbandonmentIssuesPresentation.qml": (
            "abandonmentRoot.abandonmentModel.artworkSource",
            1,
        ),
        "AchievementPulsePresentation.qml": (
            "achievementRoot.achievementModel.artworkSource",
            2,  # main art + latest-achievement art use the shared primitive
        ),
    }

    for filename, (artwork_token, minimum_fade_images) in cases.items():
        source = (QML / filename).read_text(encoding="utf-8")
        assert artwork_token in source
        assert source.count("ArtworkFadeImage {") >= minimum_fade_images

    achievement = (QML / "AchievementPulsePresentation.qml").read_text(
        encoding="utf-8"
    )
    assert "achievementRoot.achievementModel.latestArtworkSource" in achievement
    assert achievement.count("ArtworkFadeImage {") >= 2


def test_media_artwork_frame_survives_long_enough_to_fade_artwork_out() -> None:
    source = (QML / "MediaPresentation.qml").read_text(encoding="utf-8")
    assert (
        "visible: mediaRoot.mediaModel.hasArtwork || mediaArtwork.transitionVisible"
        in source
    )
