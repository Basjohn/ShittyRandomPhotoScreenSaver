"""H9 regression bars: ordinary-widget CUSTOM resize is one uniform scale.

These would fail under the pre-H9 partial-payload design, where CUSTOM resize
scaled the outer rect (and a couple of Settings-like values such as ``font_size``
/ ``artwork_size``) while the retained QML relaid the rest of the card from many
unscaled authored constants. That let Reddit rows escape a shrunk card and let
Media bands recentre independently, and Gmail fixed rows/header escaped the
shell. Save/replay faithfully reproduced the broken geometry.

The fix is a single retained-presentation scale (``OverlayWidget``
``uniformScaleTransform``): the whole authored card is laid out once at its
baseline content size and scaled as one coordinate relationship, with the factor
derived from the Python-assigned outer rect / baseline-preferred ratio (no
QML->Python feedback, no second geometry owner). CUSTOM resize for these families
is therefore purely geometric; font/artwork stay Settings-owned.

Reddit/Media/Gmail have operator acceptance; this file is the permanent deterministic contract.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject
from PySide6.QtQuick import QQuickItem

from core.reddit_preparation import RedditPost
from rendering.quick.custom_layout_size import (
    capture_quick_size_payload,
    is_uniform_transform_resize_mode,
    scale_quick_size_payload,
)
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost
from rendering.widget_descriptors import get_widget_runtime_descriptor


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


def _reddit_item(host, *, rows: int = 0, model_identity: str = "reddit"):
    from rendering.quick.widgets.reddit import (
        RedditPresentationConfig,
        RedditPresentationModel,
        RedditPresentationStyle,
    )

    config = RedditPresentationConfig.from_widgets_mapping({}, widget_id="reddit")
    model = RedditPresentationModel(
        config, RedditPresentationStyle.project(config, _shadow_values())
    )
    if rows:
        model.publish_posts(
            [
                RedditPost(
                    title=f"A representative post title number {index}",
                    url=f"https://example.com/post/{index}",
                    score=index,
                    created_utc=1_600_000_000.0 - index * 3600,
                )
                for index in range(rows)
            ],
            from_cache=True,
            now_ts=1_600_100_000.0,
        )
    item = host.create_family_widget(
        "reddit",
        initial_properties={"redditModel": model},
        model_identity=model_identity,
    ).item
    return item


def _media_item(host, *, model_identity: str = "media"):
    from rendering.quick.media_artwork import MediaArtworkImageProvider
    from rendering.quick.widgets.media import (
        MediaPresentationConfig,
        MediaPresentationModel,
        MediaPresentationStyle,
    )

    config = MediaPresentationConfig.from_mapping(
        {"artwork_size": 180, "font_size": 18, "show_header_frame": True}
    )
    model = MediaPresentationModel(
        config,
        MediaPresentationStyle.project(config, _shadow_values()),
        MediaArtworkImageProvider(),
    )
    return host.create_family_widget(
        "media",
        initial_properties={"mediaModel": model},
        model_identity=model_identity,
    ).item


def _baseline(item) -> tuple[float, float]:
    return (
        float(item.property("preferredContentWidth")),
        float(item.property("preferredContentHeight")),
    )


def _set_outer(item, width: float, height: float, qt_app) -> None:
    item.setWidth(float(width))
    item.setHeight(float(height))
    qt_app.processEvents()


def _child(item, object_name: str) -> QQuickItem:
    child = item.findChild(QQuickItem, object_name)
    assert child is not None, f"missing child {object_name!r}"
    return child


def _geom(child: QQuickItem) -> tuple[float, float, float, float]:
    return (
        float(child.property("x")),
        float(child.property("y")),
        float(child.property("width")),
        float(child.property("height")),
    )


# --------------------------------------------------------------------------- #
# Pure descriptor / payload contract (no Qt).                                 #
# --------------------------------------------------------------------------- #
def test_uniform_transform_scope_includes_reddit_media_and_gmail() -> None:
    for widget_id in ("reddit", "reddit2", "media", "gmail"):
        mode = get_widget_runtime_descriptor(widget_id).custom_layout_resize_mode
        assert is_uniform_transform_resize_mode(mode), widget_id
    # Families deliberately left on their existing payload path (audited, inert).
    for widget_id in ("clock", "weather", "steam"):
        descriptor = get_widget_runtime_descriptor(widget_id)
        if descriptor is None:
            continue
        assert not is_uniform_transform_resize_mode(
            descriptor.custom_layout_resize_mode
        ), widget_id
    # The Visualizer keeps its separate visualizer_rect / viewport contract.
    assert not is_uniform_transform_resize_mode("visualizer_rect")


def test_transform_family_resize_carries_no_settings_like_payload() -> None:
    reddit = get_widget_runtime_descriptor("reddit")
    media = get_widget_runtime_descriptor("media")
    gmail = get_widget_runtime_descriptor("gmail")

    # Capture is geometry-only for the uniform-transform families...
    assert capture_quick_size_payload(reddit, None, None) == {}
    assert capture_quick_size_payload(media, None, None) == {}
    assert capture_quick_size_payload(gmail, None, None) == {}
    # ...and scaling never manufactures a per-value payload from the geometry.
    assert scale_quick_size_payload(reddit, {}, 1.6) == {}
    assert scale_quick_size_payload(media, {}, 0.5) == {}
    assert scale_quick_size_payload(gmail, {}, 0.4) == {}

    # A payload family still scales its authored values (unchanged behaviour).
    weather = get_widget_runtime_descriptor("weather")
    scaled = scale_quick_size_payload(
        weather, {"font_size": 20, "icon_size": 40}, 2.0
    )
    assert scaled["font_size"] == 40
    assert scaled["icon_size"] == 80


def test_visualizer_rect_payload_scaling_is_unchanged() -> None:
    visualizer = get_widget_runtime_descriptor("spotify_visualizer")
    scaled = scale_quick_size_payload(
        visualizer, {"width": 200, "height": 100}, 1.5
    )
    assert scaled["width"] == 300
    assert scaled["height"] == 150


# --------------------------------------------------------------------------- #
# Uniform scale math + aspect (Qt).                                           #
# --------------------------------------------------------------------------- #
@pytest.mark.qt
def test_reddit_uniform_scale_is_min_ratio_and_preserves_aspect(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    host = _host(factory, owner)
    try:
        item = _reddit_item(host, rows=6)
        assert bool(item.property("uniformScaleTransform")) is True
        base_w, base_h = _baseline(item)
        assert base_w > 0.0 and base_h > 0.0

        # Baseline outer == preferred -> scale 1, authored box fills it exactly.
        _set_outer(item, base_w, base_h, qt_app)
        assert float(item.property("presentationScale")) == pytest.approx(1.0, abs=1e-3)
        authored = _child(item, "overlayAuthoredRoot")
        assert float(authored.property("width")) == pytest.approx(base_w)
        assert float(authored.property("height")) == pytest.approx(base_h)

        for factor in (0.5, 0.75, 1.4, 2.0):
            _set_outer(item, base_w * factor, base_h * factor, qt_app)
            # One uniform factor, derived from the outer/baseline ratio.
            assert float(item.property("presentationScale")) == pytest.approx(
                factor, abs=2e-3
            )
            assert float(authored.property("scale")) == pytest.approx(
                float(item.property("presentationScale"))
            )
            # The authored coordinate box never changes; only the whole scales.
            assert float(authored.property("width")) == pytest.approx(base_w)
            assert float(authored.property("height")) == pytest.approx(base_h)
            # Scaled box fills the outer rect (uniform, no single-axis distortion).
            scale = float(authored.property("scale"))
            assert float(authored.property("width")) * scale == pytest.approx(
                float(item.property("width")), rel=2e-3
            )
            assert float(authored.property("height")) * scale == pytest.approx(
                float(item.property("height")), rel=2e-3
            )
    finally:
        host.retire_all()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_reddit_rows_stay_contained_by_scaled_card_on_shrink_and_grow(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    host = _host(factory, owner)
    try:
        item = _reddit_item(host, rows=8)
        base_w, base_h = _baseline(item)
        _set_outer(item, base_w, base_h, qt_app)

        content = _child(item, "redditContent")
        baseline_content_geom = _geom(content)
        baseline_children = content.property("childrenRect")
        # The authored rows fit within the authored content box at baseline.
        assert (
            float(baseline_children.y()) + float(baseline_children.height())
            <= float(content.property("height")) + 1.0
        )
        assert float(baseline_children.height()) > 0.0

        # Shrinking or growing the OUTER rect must not change the authored
        # content layout - it is decoupled from the outer rect and scaled whole,
        # so rows can never escape a shrunk card (the pre-H9 falsifier).
        for factor in (0.5, 0.6, 1.7):
            _set_outer(item, base_w * factor, base_h * factor, qt_app)
            assert _geom(content) == pytest.approx(baseline_content_geom)
            children = content.property("childrenRect")
            assert (
                float(children.y()) + float(children.height())
                <= float(content.property("height")) + 1.0
            )
    finally:
        host.retire_all()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_media_bands_keep_authored_placement_under_resize(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    host = _host(factory, owner)
    try:
        item = _media_item(host)
        assert bool(item.property("uniformScaleTransform")) is True
        base_w, base_h = _baseline(item)
        _set_outer(item, base_w, base_h, qt_app)

        # The band container (mainBand centres metadata/artwork) and the header
        # frame keep identical authored geometry at every outer size: a resize
        # scales the whole card, it never recentres bands independently.
        band_names = ("mediaContent", "mediaMainBand", "mediaHeaderFrame")
        baseline_geoms = {name: _geom(_child(item, name)) for name in band_names}

        for factor in (0.6, 0.8, 1.5):
            _set_outer(item, base_w * factor, base_h * factor, qt_app)
            assert float(item.property("presentationScale")) == pytest.approx(
                factor, abs=2e-3
            )
            for name in band_names:
                assert _geom(_child(item, name)) == pytest.approx(
                    baseline_geoms[name]
                ), name
    finally:
        host.retire_all()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_committed_replay_ignores_stale_font_payload_and_keeps_uniform_scale(
    qt_app,
) -> None:
    """Save/reconstruction replays a coherent rect + derived scale.

    A pre-H9 committed layout persisted a *scaled* ``font_size`` in its payload.
    Replaying that must not shift the baseline preferred size (which would make
    the derived scale wrong); the uniform scale comes from geometry alone.
    """

    owner = QObject()
    factory = QuickSceneFactory()
    host = _host(factory, owner)
    try:
        widget = host.presentation_for_model_identity("reddit")
        assert widget is None
        from rendering.quick.widgets.reddit import (
            RedditPresentationConfig,
            RedditPresentationModel,
            RedditPresentationStyle,
        )

        config = RedditPresentationConfig.from_widgets_mapping({}, widget_id="reddit")
        model = RedditPresentationModel(
            config, RedditPresentationStyle.project(config, _shadow_values())
        )
        retained = host.create_family_widget(
            "reddit",
            initial_properties={"redditModel": model},
            model_identity="reddit",
        )
        item = retained.item
        qt_app.processEvents()
        base_w, base_h = _baseline(item)

        # Simulate replay of a committed 1.5x layout carrying a stale scaled font.
        retained.apply_custom_layout_size_payload({"font_size": 40})
        qt_app.processEvents()
        # Baseline preferred is unchanged: the stale font is ignored, and the
        # authored font stays Settings-owned.
        assert model.config.font_size == config.font_size
        assert _baseline(item) == pytest.approx((base_w, base_h))

        # The committed outer rect (1.5x) then derives exactly a 1.5x scale.
        _set_outer(item, base_w * 1.5, base_h * 1.5, qt_app)
        assert float(item.property("presentationScale")) == pytest.approx(
            1.5, abs=2e-3
        )
    finally:
        host.retire_all()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_non_transform_family_shell_change_is_inert(qt_app) -> None:
    """A non-opt-in family keeps scale 1 and fills the assigned rect exactly."""

    from rendering.quick.widgets.clock import (
        ClockPresentationConfig,
        ClockPresentationModel,
        ClockPresentationStyle,
    )

    owner = QObject()
    factory = QuickSceneFactory()
    host = _host(factory, owner)
    try:
        config = ClockPresentationConfig(
            widget_id="clock", font_size=48, display_mode="digital"
        )
        model = ClockPresentationModel(
            config, ClockPresentationStyle.project(config, _shadow_values())
        )
        item = host.create_family_widget(
            "clocks",
            initial_properties={"clockModel": model},
            model_identity="clock",
        ).item
        assert bool(item.property("uniformScaleTransform")) is False

        _set_outer(item, 900.0, 300.0, qt_app)
        # No uniform transform: scale stays 1 and the authored root fills the
        # assigned rect (historical behaviour preserved for opt-out families).
        assert float(item.property("presentationScale")) == pytest.approx(1.0)
        authored = _child(item, "overlayAuthoredRoot")
        assert float(authored.property("width")) == pytest.approx(900.0)
        assert float(authored.property("height")) == pytest.approx(300.0)
        assert float(authored.property("scale")) == pytest.approx(1.0)
    finally:
        host.retire_all()
        factory.deleteLater()
        qt_app.processEvents()
