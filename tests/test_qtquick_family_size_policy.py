"""Family outer-geometry size-policy regression bars (H option A).

These lock the historical pre-F QWidget size policies onto the Quick preferred
content sizes: intrinsic QML measurement may enlarge a card where content
genuinely requires it, but must never silently shrink below the authored/minimum
footprints. Deterministic assertions on the specific policies, not merely
``preferred size > 0``.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject
from PySide6.QtQuick import QQuickItem

from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost


def _shadow_values():
    return {
        "enabled": True,
        "color": [0, 0, 0, 255],
        "blur_radius": 18,
        "frame_opacity": 0.77,
        "text_enabled": True,
        "text_opacity": 0.33,
        "direction": "SE",
    }


def _host(factory: QuickSceneFactory, owner: QObject):
    context, root = factory.create_display_root(
        owner=owner, screen_index=0, runtime_generation=7
    )
    return OrdinaryWidgetPresentationHost(
        host_item=root.findChild(QQuickItem, "ordinaryWidgetHost"),
        context=context,
        create_overlay_item=factory.create_overlay_widget,
        create_family_item=factory.create_ordinary_widget_family,
    )


def _size(item) -> tuple[float, float]:
    return (
        float(item.property("preferredContentWidth")),
        float(item.property("preferredContentHeight")),
    )


# --------------------------------------------------------------------------- #
# Gmail width clamp is a pure config policy (no Qt needed).                    #
# --------------------------------------------------------------------------- #
def test_gmail_authored_width_defaults_600_and_clamps_200_to_1200() -> None:
    from rendering.quick.widgets.gmail import GmailPresentationConfig

    def width(value) -> int:
        cfg = {"gmail": {"width": value}} if value is not None else {}
        return GmailPresentationConfig.from_widgets_mapping(cfg).width

    assert GmailPresentationConfig.from_widgets_mapping({}).width == 600
    assert width(800) == 800
    assert width(100) == 200  # clamped up to the floor
    assert width(5000) == 1200  # clamped down to the ceiling
    assert width(200) == 200
    assert width(1200) == 1200


@pytest.mark.qt
def test_clock_analogue_preserves_authored_natural_geometry(qt_app) -> None:
    from rendering.quick.widgets.clock import (
        ClockPresentationConfig,
        ClockPresentationModel,
        ClockPresentationStyle,
    )

    owner = QObject()
    factory = QuickSceneFactory()
    host = _host(factory, owner)
    try:
        def analogue_size(font_size: int) -> tuple[float, float]:
            config = ClockPresentationConfig(
                widget_id="clock", font_size=font_size, display_mode="analog"
            )
            model = ClockPresentationModel(
                config, ClockPresentationStyle.project(config, _shadow_values())
            )
            item = host.create_family_widget(
                "clocks",
                initial_properties={"clockModel": model},
                model_identity=f"clock_{font_size}",
            ).item
            return _size(item)

        # width = max(160, font * 4.5); height = max(width, width * 1.3).
        w48, h48 = analogue_size(48)
        assert w48 == pytest.approx(48 * 4.5)  # 216
        assert h48 == pytest.approx(216.0 * 1.3)  # 280.8

        # The 160 floor holds for small fonts.
        w20, h20 = analogue_size(20)
        assert w20 == pytest.approx(160.0)
        assert h20 == pytest.approx(160.0 * 1.3)
    finally:
        host.retire_all()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_weather_and_reddit_honour_600_minimum_width(qt_app) -> None:
    from rendering.quick.widgets.reddit import (
        RedditPresentationConfig,
        RedditPresentationModel,
        RedditPresentationStyle,
    )
    from rendering.quick.widgets.weather import (
        WeatherPresentationConfig,
        WeatherPresentationModel,
        WeatherPresentationStyle,
    )

    owner = QObject()
    factory = QuickSceneFactory()
    host = _host(factory, owner)
    try:
        wc = WeatherPresentationConfig.from_widgets_mapping({})
        wm = WeatherPresentationModel(
            wc, WeatherPresentationStyle.project(wc, _shadow_values())
        )
        weather = host.create_family_widget(
            "weather", initial_properties={"weatherModel": wm}, model_identity="weather"
        ).item
        assert _size(weather)[0] >= 600.0

        rc = RedditPresentationConfig.from_widgets_mapping({}, widget_id="reddit")
        rm = RedditPresentationModel(
            rc, RedditPresentationStyle.project(rc, _shadow_values())
        )
        reddit = host.create_family_widget(
            "reddit", initial_properties={"redditModel": rm}, model_identity="reddit"
        ).item
        assert _size(reddit)[0] >= 600.0
    finally:
        host.retire_all()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_media_honours_min_width_600_and_height_floor(qt_app) -> None:
    from rendering.quick.media_artwork import MediaArtworkImageProvider
    from rendering.quick.widgets.media import (
        MediaPresentationConfig,
        MediaPresentationModel,
        MediaPresentationStyle,
    )

    owner = QObject()
    factory = QuickSceneFactory()
    host = _host(factory, owner)
    try:
        def media_size(artwork: int) -> tuple[float, float]:
            config = MediaPresentationConfig.from_mapping({"artwork_size": artwork})
            model = MediaPresentationModel(
                config,
                MediaPresentationStyle.project(config, _shadow_values()),
                MediaArtworkImageProvider(),
            )
            item = host.create_family_widget(
                "media",
                initial_properties={"mediaModel": model},
                model_identity=f"media_{artwork}",
            ).item
            return _size(item)

        # Height floor is max(220, artwork_size + 60); width never below 600.
        w_small, h_small = media_size(100)
        assert w_small >= 600.0
        assert h_small == pytest.approx(220.0)  # max(220, 160)

        w_mid, h_mid = media_size(250)
        assert w_mid >= 600.0
        assert h_mid == pytest.approx(310.0)  # max(220, 310)

        _, h_large = media_size(500)
        assert h_large == pytest.approx(560.0)  # max(220, 560)
    finally:
        host.retire_all()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_steam_cards_use_authored_preferred_dimensions(qt_app) -> None:
    from rendering.quick.widgets.abandonment_issues import (
        AbandonmentIssuesPresentationConfig,
        AbandonmentIssuesPresentationModel,
        AbandonmentIssuesPresentationStyle,
    )
    from rendering.quick.widgets.achievement_pulse import (
        AchievementPulsePresentationConfig,
        AchievementPulsePresentationModel,
        AchievementPulsePresentationStyle,
    )

    owner = QObject()
    factory = QuickSceneFactory()
    host = _host(factory, owner)
    try:
        ac = AchievementPulsePresentationConfig.from_widgets_mapping({})
        am = AchievementPulsePresentationModel(
            ac, AchievementPulsePresentationStyle.project(ac, _shadow_values())
        )
        achievement = host.create_family_widget(
            "achievement_pulse",
            initial_properties={"achievementModel": am},
            model_identity="achievement_pulse",
        ).item
        assert _size(achievement) == (
            float(achievement.property("authoredWidth")),
            float(achievement.property("authoredHeight")),
        )

        bc = AbandonmentIssuesPresentationConfig.from_widgets_mapping({})
        bm = AbandonmentIssuesPresentationModel(
            bc, AbandonmentIssuesPresentationStyle.project(bc, _shadow_values())
        )
        abandonment = host.create_family_widget(
            "abandonment_issues",
            initial_properties={"abandonmentModel": bm},
            model_identity="abandonment_issues",
        ).item
        assert _size(abandonment) == (
            float(abandonment.property("authoredWidth")),
            float(abandonment.property("authoredHeight")),
        )
    finally:
        host.retire_all()
        factory.deleteLater()
        qt_app.processEvents()
