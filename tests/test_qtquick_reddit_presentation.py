"""F5 destination gates for the retained Reddit/Reddit2 presentation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QObject
from PySide6.QtQml import QQmlEngine
from PySide6.QtQuick import QQuickItem

from core.reddit_preparation import RedditPost
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.widgets import (
    OrdinaryWidgetPresentationHost,
    OverlayWidgetGeometry,
    RedditPresentationConfig,
    RedditPresentationModel,
    RedditPresentationStyle,
    RetainedRedditPresentation,
)
from rendering.quick.widgets.registry import (
    ORDINARY_WIDGET_FAMILY_COMPONENTS,
    ordinary_widget_family_component,
)


ROOT = Path(__file__).resolve().parents[1]
QML_ROOT = ROOT / "rendering" / "quick" / "qml"


def _values(**overrides):
    values = {
        "subreddit": "wallpapers",
        "limit": 4,
        "font_family": "Inter",
        "font_size": 18,
        "color": [245, 248, 252, 235],
        "show_background": True,
        "bg_color": [25, 32, 42, 255],
        "bg_opacity": 0.7,
        "border_color": [120, 195, 255, 255],
        "border_opacity": 0.9,
        "show_separators": True,
        "show_refresh_spiral": True,
        "header_logo_px_adjust": 1,
    }
    values.update(overrides)
    return values


def _shadows(**overrides):
    values = {
        "enabled": True,
        "color": [0, 0, 0, 255],
        "blur_radius": 18,
        "frame_opacity": 0.77,
        "frame_extra_offset": 1,
        "text_enabled": True,
        "text_opacity": 0.4,
        "text_extra_offset": 1,
        "direction": "SE",
    }
    values.update(overrides)
    return values


def _post(index: int, *, title: str | None = None, now: float = 20_000.0):
    return RedditPost(
        title=title or f"post number {index}",
        url=f"https://reddit.com/r/test/comments/{index}",
        score=index * 10,
        created_utc=now - index * 3600.0,
    )


def _model(*, widget_id="reddit", **overrides):
    config = RedditPresentationConfig.from_mapping(
        _values(**overrides), widget_id=widget_id
    )
    style = RedditPresentationStyle.project(config, _shadows())
    return RedditPresentationModel(config, style)


def _create_host(factory: QuickSceneFactory, owner: QObject):
    context, root = factory.create_display_root(
        owner=owner, screen_index=0, runtime_generation=51
    )
    host_item = root.findChild(QQuickItem, "ordinaryWidgetHost")
    assert host_item is not None
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
        create_family_item=factory.create_ordinary_widget_family,
    )
    return context, root, host


def _find_visual_item(root: QQuickItem, object_name: str) -> QQuickItem | None:
    if root.objectName() == object_name:
        return root
    for child in root.childItems():
        found = _find_visual_item(child, object_name)
        if found is not None:
            return found
    return None


def test_reddit2_config_inherits_base_style_but_keeps_member_feed_settings() -> None:
    config = RedditPresentationConfig.from_widgets_mapping(
        {
            "reddit": {
                "font_family": "Aptos",
                "font_size": 26,
                "color": [1, 2, 3, 240],
                "show_separators": False,
                "subreddit": "technology",
                "limit": 11,
            },
            "reddit2": {
                "subreddit": "games",
                "limit": 3,
                "font_size": 31,
            },
        },
        widget_id="reddit2",
    )
    style = RedditPresentationStyle.project(
        config,
        _shadows(direction="NW", frame_extra_offset=2, text_extra_offset=3),
    )

    assert config.widget_id == "reddit2"
    assert config.subreddit == "games"
    assert config.limit == 3
    assert config.font_family == "Aptos"
    assert config.font_size == 31
    assert config.text_color == (1, 2, 3, 240)
    assert config.show_separators is False
    assert style.card_style.shadow_offset_x == pytest.approx(-6.0)
    assert style.card_style.shadow_offset_y == pytest.approx(-6.0)
    assert style.text_shadow_offset_x == pytest.approx(-5.0)
    assert style.text_shadow_offset_y == pytest.approx(-5.0)


def test_reddit_model_keeps_one_row_model_and_coherent_ready_cached_error_state() -> None:
    model = _model(limit=2)
    row_model = model.row_model
    changes: list[str] = []
    model.stateChanged.connect(lambda: changes.append(model.viewState))

    assert model.viewState == "loading"
    assert model.publish_posts(
        (
            _post(1, title="NASA launches again - source"),
            _post(2),
            _post(3),
        ),
        from_cache=True,
        now_ts=20_000.0,
    )

    assert model.row_model is row_model
    assert row_model.rowCount() == 2
    assert row_model.rows[0].title == "NASA Launches Again"
    assert row_model.rows[0].age == "01HR AGO"
    assert model.viewState == "ready"
    assert model.fromCache is True

    model.publish_error("offline")
    assert model.viewState == "ready"
    assert model.errorText == "offline"
    assert model.row_model is row_model
    assert row_model.rowCount() == 2

    model.apply_config(replace(model.config, subreddit="python"))
    assert model.viewState == "loading"
    assert model.errorText == ""
    assert row_model.rowCount() == 0
    assert changes


@pytest.mark.qt
def test_reddit_family_mutates_rows_style_and_actions_without_recreation(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory(owner)
    context, root, host = _create_host(factory, owner)
    model = _model()
    opened: list[str] = []
    refreshes: list[str] = []
    model.publish_posts((_post(1), _post(2)), now_ts=20_000.0)
    presentation = RetainedRedditPresentation(
        host=host,
        model=model,
        geometry=OverlayWidgetGeometry(25.0, 30.0, 620.0, 300.0),
        on_open_requested=lambda url: opened.append(url) or True,
        on_refresh_requested=lambda: refreshes.append("refresh") or True,
    )
    item = presentation.item
    engine = QQmlEngine.contextForObject(item).engine()
    try:
        presentation.activate()
        qt_app.processEvents()
        row_model = model.row_model
        first_row = _find_visual_item(item, "redditPostRow_0")
        assert first_row is not None
        assert _find_visual_item(item, "redditHeaderLogo") is not None

        item.openPostRequested.emit(row_model.rows[0].url)
        item.refreshRequested.emit()
        assert opened == []
        assert refreshes == []

        presentation.apply_input_state(
            {
                "admission_open": True,
                "exiting": False,
                "interaction_mode_enabled": False,
                "ctrl_held": True,
            }
        )
        item.openPostRequested.emit(row_model.rows[0].url)
        item.openPostRequested.emit("https://untrusted.example")
        item.refreshRequested.emit()
        assert opened == [row_model.rows[0].url]
        assert refreshes == ["refresh"]

        presentation.apply_input_state(
            {
                "admission_open": True,
                "exiting": True,
                "interaction_mode_enabled": True,
                "ctrl_held": True,
            }
        )
        item.openPostRequested.emit(row_model.rows[0].url)
        item.refreshRequested.emit()
        assert opened == [row_model.rows[0].url]
        assert refreshes == ["refresh"]

        model.publish_posts(
            (_post(1, title="updated first post"), _post(2)),
            now_ts=20_000.0,
        )
        presentation.apply_config(
            replace(model.config, font_size=24, show_background=False),
            _shadows(direction="W", text_extra_offset=2),
        )
        qt_app.processEvents()

        assert presentation.item is item
        assert presentation.model is model
        assert model.row_model is row_model
        assert QQmlEngine.contextForObject(item).engine() is engine
        assert _find_visual_item(item, "redditPostRow_0") is first_row
        assert model.fontSize == 24.0
        assert model.showBackground is False
        assert model.textShadowOffsetX == pytest.approx(-4.0)
        assert model.textShadowOffsetY == pytest.approx(0.0)
        assert item.property("cardShellEnabled") is False
    finally:
        host.retire_all()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        owner.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()

    assert model.is_active is False
    assert model.row_model.rowCount() == 0


@pytest.mark.qt
def test_reddit_and_reddit2_share_component_not_model_or_rows(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory(owner)
    context, root, host = _create_host(factory, owner)
    first = _model(widget_id="reddit", subreddit="pics")
    second = _model(widget_id="reddit2", subreddit="games")
    first.publish_posts((_post(1),), now_ts=20_000.0)
    second.publish_posts((_post(7), _post(8)), now_ts=20_000.0)
    one = RetainedRedditPresentation(
        host=host,
        model=first,
        geometry=OverlayWidgetGeometry(10, 10, 500, 240),
    )
    two = RetainedRedditPresentation(
        host=host,
        model=second,
        geometry=OverlayWidgetGeometry(530, 10, 500, 280),
    )
    try:
        one.activate()
        two.activate()
        qt_app.processEvents()
        assert one.item is not two.item
        assert first.row_model is not second.row_model
        assert first.row_model.rowCount() == 1
        assert second.row_model.rowCount() == 2
        assert one.item.metaObject().className() == two.item.metaObject().className()
    finally:
        host.retire_all()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        owner.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


def test_reddit_qml_and_registry_are_static_presentation_only() -> None:
    qml = (QML_ROOT / "RedditPresentation.qml").read_text(encoding="utf-8")
    for marker in (
        "Timer {",
        "SettingsManager",
        "RedditPostProvider",
        "RedditRateLimiter",
        "QDesktopServices",
        "QWidget",
        "MultiEffect",
        "layer.enabled",
    ):
        assert marker not in qml
    assert "RedditPresentation 1.0 RedditPresentation.qml" in (
        QML_ROOT / "qmldir"
    ).read_text(encoding="utf-8")

    descriptors = [
        descriptor
        for descriptor in ORDINARY_WIDGET_FAMILY_COMPONENTS
        if descriptor.family_id == "reddit"
    ]
    assert len(descriptors) == 1
    descriptor = ordinary_widget_family_component("reddit")
    assert descriptor.qml_filename == "RedditPresentation.qml"
    assert descriptor.presentation_model_kind == "RedditPresentationModel"
