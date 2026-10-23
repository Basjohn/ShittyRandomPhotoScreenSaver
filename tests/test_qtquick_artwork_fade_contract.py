"""Static guard for the retained dynamic-artwork fade invariant."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml"


def test_shared_artwork_fade_primitive_is_event_driven_and_timerless() -> None:
    source = (QML / "ArtworkFadeImage.qml").read_text(encoding="utf-8")

    assert "Qt.callLater" not in source
    assert "Image.Ready" in source
    # Functional compositor invariant: crossfade buffers stay clipped to the
    # card, with the incoming image drawn over the current image in both states.
    assert "clip: true" in source
    assert 'z: fadeImage._activeIndex === 0 ? 0 : 1' in source
    assert 'z: fadeImage._activeIndex === 0 ? 1 : 0' in source
    assert "_activeIndex" in source
    assert "_inactiveImage" in source
    assert "fadeOut.running" in source
    assert "QTimer" not in source
    assert "Timer {" not in source
    assert "onSourceChanged" in source
    assert "incoming.status !== Image.Ready" in source
    assert '_setSource(oldIndex, "")' in source


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


def test_abandonment_rotation_fades_values_not_static_archive_chrome() -> None:
    source = (QML / "AbandonmentIssuesPresentation.qml").read_text(encoding="utf-8")

    assert 'property real dynamicContentOpacity: 1.0' in source
    assert 'target: abandonmentRoot' in source
    assert 'property: "dynamicContentOpacity"' in source
    assert 'target: archiveContent' not in source
    shared = (QML / "ArtworkFadeImage.qml").read_text(encoding="utf-8")
    assert "fadeInDuration:" not in source
    # Static metric chrome/label remains at full opacity; only the per-game value
    # participates in the transition.
    metric_label = 'text: abandonmentRoot.abandonmentModel.metricLabel.toUpperCase()'
    metric_value = 'text: abandonmentRoot.abandonmentModel.metricValue'
    assert metric_label in source
    value_tail = source[source.index(metric_value):source.index(metric_value) + 220]
    assert 'opacity: abandonmentRoot.dynamicContentOpacity' in value_tail


def test_media_metadata_crossfade_paints_incoming_snapshot_on_top() -> None:
    source = (QML / "MediaMetadataColumn.qml").read_text(encoding="utf-8")

    current = source[source.index("id: currentColumn"):source.index("id: outgoingColumn")]
    outgoing = source[source.index("id: outgoingColumn"):source.index("ParallelAnimation {")]
    assert "z: 1" in current
    assert "z: 0" in outgoing
