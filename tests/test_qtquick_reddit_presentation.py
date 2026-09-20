"""F5 destination gates for the retained Reddit/Reddit2 presentation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QObject
from PySide6.QtQml import QQmlEngine
from PySide6.QtQuick import QQuickItem

from core.reddit_post_provider import RedditProviderResult
from core.reddit_preparation import RedditPost
from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.host import (
    OrdinaryWidgetPresentationHost,
    OverlayWidgetGeometry,
)
from rendering.quick.widgets.reddit import (
    RedditPresentationConfig,
    RedditPresentationModel,
    RedditPresentationStyle,
    RetainedRedditPresentation,
)
from rendering.quick.widgets.registry import (
    ORDINARY_WIDGET_FAMILY_COMPONENTS,
    ordinary_widget_family_component,
)
from rendering.widget_runtime_manager import WidgetRuntimeManager
from rendering.quick.window import QuickDisplayWindow


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
        "header_enabled": True,
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
    assert style.card_style.shadow_offset_x == pytest.approx(-4.0)
    assert style.card_style.shadow_offset_y == pytest.approx(-4.0)
    assert style.card_style.shadow_extend_left == pytest.approx(2.0)
    assert style.card_style.shadow_extend_top == pytest.approx(2.0)
    assert style.card_style.shadow_extend_right == pytest.approx(0.0)
    assert style.card_style.shadow_extend_bottom == pytest.approx(0.0)
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
    # Python retains the accepted buffer, but normal retained QML materializes
    # only the authored visible limit. CUSTOM may project more on demand.
    assert len(model._held_rows) == 3
    assert row_model.rowCount() == 2
    assert model.postLimit == 2
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


def test_runtime_manager_injects_complete_owner_into_retained_reddit_model() -> None:
    class _Host:
        @staticmethod
        def get_runtime_widget_registry():
            return {}

    owner = WidgetRuntimeManager(_Host())
    model = _model()
    service = owner.ensure_widget_service(
        "reddit",
        model,
        {"reddit": {"provider": "public_json", "subreddit": "wallpapers"}},
    )

    assert service is not None
    assert model._runtime_service is service
    assert service.config.subreddit == "wallpapers"
    assert getattr(service.provider, "provider_id", None) == "public_json"
    assert service.is_running() is False
    assert owner.retire_widget_service("reddit") is True
    assert service.is_retired() is True


@pytest.mark.qt
def test_real_reddit_runtime_drives_current_scene_host_actions_and_geometry_in_place(
    qt_app, monkeypatch, tmp_path
) -> None:
    import core.reddit_post_provider as provider_module
    import widgets.reddit_runtime as runtime_module

    class _Provider:
        provider_id = "public_json"

        def __init__(self) -> None:
            self.requests = []

        def fetch_posts(self, request):
            self.requests.append(request)
            return RedditProviderResult.with_posts(
                [
                    {
                        "title": "runtime refreshed post",
                        "url": "https://reddit.com/r/wallpapers/comments/runtime",
                        "score": 4,
                        "created_utc": 19_900.0,
                    }
                ],
                source_id="public_json",
                attempted_sources=("public_json",),
            )

    class _ImmediateThreadManager:
        def submit_io_task(self, callback_fn, *args, callback=None, **_kwargs):
            try:
                result = callback_fn(*args)
            except Exception as exc:
                outcome = type(
                    "Outcome",
                    (),
                    {"success": False, "result": None, "error": str(exc)},
                )()
            else:
                outcome = type(
                    "Outcome",
                    (),
                    {"success": True, "result": result, "error": None},
                )()
            if callback is not None:
                callback(outcome)
            return "task"

    class _Host:
        @staticmethod
        def get_runtime_widget_registry():
            return {}

    provider = _Provider()
    monkeypatch.setattr(
        provider_module, "build_reddit_post_provider", lambda _provider_id: provider
    )
    monkeypatch.setattr(runtime_module, "_REDDIT_CACHE_DIR", tmp_path)
    monkeypatch.setattr(runtime_module, "automatic_service_updates_enabled", lambda: False)
    runtime_module.RedditRuntimeService.periodic_due_by_cache_key.clear()
    runtime_module.RedditRuntimeService.periodic_due_reason_by_cache_key.clear()
    runtime_module.RedditRuntimeService.manual_due_by_cache_key.clear()
    monkeypatch.setattr(
        runtime_module.ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda callback, *args: callback(*args)),
    )

    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=58,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    owner = WidgetRuntimeManager(_Host())
    model = _model(limit=3)
    service = owner.ensure_widget_service(
        "reddit",
        model,
        {"reddit": {"provider": "public_json", "subreddit": "wallpapers"}},
    )
    assert service is not None
    service._candidates = (_post(1), _post(2))
    opened = []
    presentation = None
    try:
        presentation = RetainedRedditPresentation(
            host=controller.ordinary_widget_host,
            model=model,
            geometry=OverlayWidgetGeometry(25.0, 30.0, 620.0, 300.0),
            on_open_requested=lambda url: opened.append(url) or True,
        )
        item = presentation.item
        engine = QQmlEngine.contextForObject(item).engine()
        presentation.activate(_ImmediateThreadManager())
        presentation.apply_input_state(
            {
                "admission_open": True,
                "exiting": False,
                "interaction_mode_enabled": True,
                "ctrl_held": False,
            }
        )
        qt_app.processEvents()

        assert owner.get_widget_service("reddit") is service
        assert service._consumer() is model
        assert service.is_running() is True
        assert model.viewState == "ready"
        assert model.row_model.rowCount() == 2

        item.refreshRequested.emit()
        qt_app.processEvents()
        assert len(provider.requests) == 1
        assert provider.requests[0].subreddit == "wallpapers"
        assert service.accepted_revision == 1
        assert model.row_model.rowCount() == 1
        assert model.row_model.rows[0].title == "Runtime Refreshed Post"
        assert model.refreshing is False

        item.openPostRequested.emit(model.row_model.rows[0].url)
        assert opened == [model.row_model.rows[0].url]

        presentation.set_geometry(
            OverlayWidgetGeometry(80.0, 95.0, 540.0, 260.0)
        )
        presentation.apply_config(
            replace(model.config, limit=1, font_size=24),
            _shadows(direction="W", text_extra_offset=2),
        )
        qt_app.processEvents()
        assert presentation.item is item
        assert QQmlEngine.contextForObject(item).engine() is engine
        assert item.x() == pytest.approx(80.0)
        assert item.y() == pytest.approx(95.0)
        assert item.width() == pytest.approx(540.0)
        assert item.height() == pytest.approx(260.0)
        assert model.fontSize == 24.0

        controller.quiesce_for_retirement()
        assert service._consumer() is None
        assert service.is_running() is False
        assert owner.get_reusable_widget_service("reddit", model) is None
        assert service.is_retired() is True
    finally:
        controller.quiesce_for_retirement()
        owner.cleanup()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()

    assert presentation is not None
    assert service.is_retired() is True


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


def test_reddit_content_extent_override_is_ssot_safe() -> None:
    model = _model(limit=20)
    assert model.postLimit == 20
    assert model.maxHeldPosts == 25
    assert model.contentExtentWidth == 0.0
    assert model.contentExtentHeight == 0.0

    assert model.set_content_extent(720.0, 900.0) is True
    assert model.contentExtentWidth == pytest.approx(720.0)
    assert model.contentExtentHeight == pytest.approx(900.0)
    # The extent is CUSTOM-scoped presentation state; it never rewrites the
    # `limit` SSOT default.
    assert model.postLimit == 20

    # Idempotent + clearing returns to no override without touching the setting.
    assert model.set_content_extent(720.0, 900.0) is False
    assert model.clear_content_extent() is True
    assert model.contentExtentHeight == 0.0
    assert model.postLimit == 20


def test_reddit_content_extent_drives_visible_count_and_spread(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory(owner)
    context, root, host = _create_host(factory, owner)
    model = _model(limit=4)
    # Held buffer of 10 posts (> the SSOT limit of 4).
    model.publish_posts(tuple(_post(i) for i in range(1, 11)), now_ts=20_000.0)
    presentation = RetainedRedditPresentation(
        host=host,
        model=model,
        geometry=OverlayWidgetGeometry(25.0, 30.0, 620.0, 400.0),
        on_open_requested=lambda url: True,
        on_refresh_requested=lambda: True,
    )
    item = presentation.item
    engine = QQmlEngine.contextForObject(item).engine()
    try:
        presentation.activate()
        qt_app.processEvents()
        natural = float(item.property("naturalRowHeight"))
        # Default: the SSOT `limit` governs both visible and materialized rows.
        assert model.row_model.rowCount() == 4
        assert len(model._held_rows) == 10
        assert int(item.property("effectiveVisibleCount")) == 4

        # Tall extent reveals more posts (up to the 10 held) and, past the count
        # cap, spreads rows taller + thickens separators.
        model.set_content_extent(620.0, 2000.0)
        qt_app.processEvents()
        assert model.row_model.rowCount() == 10
        assert int(item.property("effectiveVisibleCount")) == 10
        assert float(item.property("extentRowHeight")) > natural
        assert float(item.property("extentSeparatorThickness")) > 1.0

        # Short extent decreases the visible count below the default.
        model.set_content_extent(620.0, 140.0)
        qt_app.processEvents()
        assert int(item.property("effectiveVisibleCount")) < 4

        # Clearing returns to the SSOT default exactly.
        model.clear_content_extent()
        qt_app.processEvents()
        assert model.row_model.rowCount() == 4
        assert int(item.property("effectiveVisibleCount")) == 4
        assert QQmlEngine.contextForObject(item).engine() is engine
    finally:
        host.retire_all()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        owner.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
@pytest.mark.parametrize("family", ["reddit", "reddit2"])
def test_header_flip_rearranges_reddit_rails_without_mirroring_post_text(qt_app, family):
    """The one header flip swaps header/refresh and timestamp/title rails."""
    owner = QObject()
    factory = QuickSceneFactory(owner)
    context, root, host = _create_host(factory, owner)
    model = _model(widget_id=family, limit=2)
    model.publish_posts((_post(1), _post(2)), now_ts=20_000.0)
    presentation = RetainedRedditPresentation(
        host=host, model=model,
        geometry=OverlayWidgetGeometry(25.0, 30.0, 620.0, 300.0),
        on_open_requested=lambda url: True,
    )
    item = presentation.item
    try:
        presentation.activate()
        qt_app.processEvents()
        header = _find_visual_item(item, "brandedHeader")
        refresh = _find_visual_item(item, "redditRefreshTarget")
        area = _find_visual_item(item, "redditHeaderArea")
        row = _find_visual_item(item, "redditPostRow_0")
        age = _find_visual_item(item, "redditPostAge_0")
        age_value = _find_visual_item(item, "redditPostAgeValue_0")
        age_ago = _find_visual_item(item, "redditPostAgeAgo_0")
        title = _find_visual_item(item, "redditPostTitle_0")
        assert all(v is not None for v in (header, refresh, area, row,
                                           age, age_value, age_ago, title))
        assert row.isVisible()
        authored = (header.x(), refresh.x(), age.x(), title.x())
        assert header.x() < refresh.x() and age.x() < title.x()
        title_align = title.property("horizontalAlignment")
        assert model.set_custom_child_geometry({"header": {"alignment": "right"}})
        qt_app.processEvents()
        assert header.x() > refresh.x()
        assert header.x() + header.width() * header.scale() <= area.width() + 0.1
        assert age.x() > title.x() and title.x() >= -0.1
        assert title.x() + title.width() <= age.x() - 3.0
        assert age_value.x() < age_ago.x(), "flipped timestamp must read 01HR then AGO"
        assert age_ago.x() - (age_value.x() + age_value.width()) == pytest.approx(2.0)
        gap = age.x() - (title.x() + title.width())
        assert gap == pytest.approx(float(item.property("titleAgeGap")))
        assert gap * float(item.property("presentationScale")) >= 8.9
        assert age.x() + age.width() == pytest.approx(row.width())
        assert title.property("horizontalAlignment") == title_align
        assert bool(item.property("headerFlipped"))
        preferred = (float(item.property("preferredContentWidth")),
                     float(item.property("preferredContentHeight")))
        assert preferred[0] > 100.0 and preferred[1] > 60.0
        for width, height in ((740.0, 355.0), (500.0, 260.0), (620.0, 300.0)):
            presentation.set_geometry(OverlayWidgetGeometry(25.0, 30.0, width, height))
            qt_app.processEvents()
            assert item.isVisible() and row.isVisible(), (
                "Reddit lost content after flipped parent resize", family,
                width, height, item.property("preferredContentWidth"),
                item.property("preferredContentHeight"),
                item.property("presentationScale"), row.width(), row.height(),
            )
            assert header.width() > 20.0 and header.height() > 20.0
            assert row.width() > 100.0 and row.height() > 20.0
            assert item.property("preferredContentWidth") == pytest.approx(preferred[0])
            assert float(item.property("presentationScale")) > 0.0
            assert bool(item.property("headerFlipped"))
        assert model.set_custom_child_geometry({})
        qt_app.processEvents()
        assert (header.x(), refresh.x(), age.x(), title.x()) == pytest.approx(authored)
        assert age_value.x() < age_ago.x()
        assert item.isVisible() and row.isVisible()
        assert row.width() > 100.0 and row.height() > 20.0
        # Explicitly cover the user's two-consecutive-flips blank-state: the
        # role record crosses authored -> flipped -> authored -> flipped
        # without resetting its QQuick scene or remaking the row delegates.
        for cycle in range(3):
            assert model.set_custom_child_geometry({"header": {"alignment": "right"}})
            qt_app.processEvents()
            title_rect = title.mapRectToItem(row, title.boundingRect())
            assert bool(item.property("headerFlipped")) and row.isVisible()
            assert str(title.property("text")).strip()
            assert title.width() > 30.0 and title_rect.x() >= -1.0
            assert title_rect.right() <= row.width() + 1.0
            assert float(item.property("preferredContentWidth")) > 100.0
            assert model.set_custom_child_geometry({})
            qt_app.processEvents()
            assert not bool(item.property("headerFlipped"))
            assert row.isVisible() and title.isVisible() and title.width() > 30.0
            assert (header.x(), refresh.x(), age.x(), title.x()) == pytest.approx(authored)
    finally:
        host.retire_all()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        owner.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
@pytest.mark.parametrize("family", ["reddit", "reddit2"])
def test_flipped_reddit_long_and_short_titles_keep_one_legible_timestamp_rail(qt_app, family):
    """Rendered row geometry regression for the operator's 19-post screenshot.

    Source-string checks previously stayed green while short titles pulled the
    timestamp rail to the middle. This asserts the actual retained delegates,
    their text bounds, and their mapping after every width and flip cycle.
    """
    owner = QObject()
    factory = QuickSceneFactory(owner)
    context, root, host = _create_host(factory, owner)
    model = _model(widget_id=family, limit=3)
    model.publish_posts((
        _post(1, title="Indeed"),
        _post(2, title="A headline so long that it must be elided before the timestamp even on a very wide card"),
        _post(3, title="PostForEverything"),
    ), now_ts=20_000.0)
    presentation = RetainedRedditPresentation(
        host=host, model=model,
        geometry=OverlayWidgetGeometry(25.0, 30.0, 620.0, 330.0),
    )
    item = presentation.item
    try:
        presentation.activate()
        for width, flipped in ((620.0, True), (410.0, True),
                               (770.0, True), (620.0, False),
                               (620.0, True)):
            presentation.set_geometry(OverlayWidgetGeometry(25.0, 30.0, width, 330.0))
            model.set_custom_child_geometry(
                {"header": {"alignment": "right"}} if flipped else {}
            )
            qt_app.processEvents()
            rails = []
            for i in range(3):
                row = _find_visual_item(item, f"redditPostRow_{i}")
                title = _find_visual_item(item, f"redditPostTitle_{i}")
                age = _find_visual_item(item, f"redditPostAge_{i}")
                value = _find_visual_item(item, f"redditPostAgeValue_{i}")
                ago = _find_visual_item(item, f"redditPostAgeAgo_{i}")
                assert all(v is not None and v.isVisible()
                           for v in (row, title, age, value, ago))
                assert title.width() > 1 and age.width() > 0
                assert str(title.property("text")).strip()
                assert str(value.property("text")).strip()
                assert value.x() + value.width() <= ago.x() + 0.1
                assert ago.x() + ago.width() <= age.width() + 0.1
                mapped_age = age.mapRectToItem(row, age.boundingRect())
                mapped_title = title.mapRectToItem(row, title.boundingRect())
                assert mapped_age.left() >= -0.1
                assert mapped_age.right() <= row.width() + 0.1
                assert mapped_title.left() >= -0.1
                assert mapped_title.right() <= row.width() + 0.1
                # Compare actual retained rails after whole-card scaling, not
                # a source literal. Both post directions need a clear painted
                # separation at small CUSTOM sizes, for every row.
                gap = (mapped_age.left() - mapped_title.right()) if flipped else (
                    mapped_title.left() - mapped_age.right()
                )
                assert gap == pytest.approx(float(item.property("titleAgeGap")), abs=0.25)
                assert gap * float(item.property("presentationScale")) >= 8.9
                rails.append((round(age.x(), 2), round(age.width(), 2)))
            if flipped:
                assert rails[0] == rails[1] == rails[2], (
                    "Timestamp shifts with post-title length", family, width, rails
                )
    finally:
        host.retire_all()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        owner.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
@pytest.mark.parametrize("family", ("reddit", "reddit2"))
def test_reddit_loading_and_ready_state_use_the_same_authored_height(qt_app, family):
    """Restore Size may not capture the compact provisional loading height."""
    owner = QObject()
    factory = QuickSceneFactory(owner)
    context, root, host = _create_host(factory, owner)
    model = _model(widget_id=family, limit=4)
    presentation = RetainedRedditPresentation(
        host=host, model=model,
        geometry=OverlayWidgetGeometry(22.0, 35.0, 600.0, 350.0),
    )
    item = presentation.item
    try:
        # Before data admission, authored dimensions must already reserve the
        # post-limit card instead of inferring height from zero ready delegates.
        qt_app.processEvents()
        authored = float(item.property("canonicalAuthoredHeight"))
        initial = float(item.property("preferredContentHeight"))
        assert authored >= 4 * 28.0
        assert initial >= authored - 0.1
        assert model.publish_posts(tuple(_post(i) for i in range(1, 5)),
                                   from_cache=True, now_ts=20_000.0)
        presentation.activate()
        qt_app.processEvents()
        assert float(item.property("preferredContentHeight")) >= authored - 0.1
        # A deliberate CUSTOM vertical extent remains a different authority.
        assert model.set_content_extent(600.0, authored + 55.0)
        qt_app.processEvents()
        assert float(item.property("preferredContentHeight")) == pytest.approx(authored + 55.0)
        assert model.clear_content_extent()
        qt_app.processEvents()
        assert float(item.property("preferredContentHeight")) >= authored - 0.1
        # Empty/error/repopulation edges must not shrink or bounce the authored
        # reference, which a subsequent Restore Size captures independently.
        assert model.publish_posts((), from_cache=True, now_ts=20_000.0)
        qt_app.processEvents()
        assert model.viewState == "empty"
        assert float(item.property("preferredContentHeight")) >= authored - 0.1
    finally:
        host.retire_all()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        owner.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()

@pytest.mark.qt
@pytest.mark.parametrize("family", ("reddit", "reddit2"))
def test_three_semantic_column_rails_reorder_every_retained_post_and_rehydrate(qt_app, family):
    """A single saved permutation moves all three painted columns on every row."""
    owner = QObject()
    factory = QuickSceneFactory(owner)
    context, root, host = _create_host(factory, owner)
    model = _model(widget_id=family, limit=3)
    model.publish_posts((_post(1, title="short"),
                         _post(2, title="a significantly longer title"),
                         _post(3, title="last")), now_ts=20_000.0)
    presentation = RetainedRedditPresentation(
        host=host, model=model,
        geometry=OverlayWidgetGeometry(25, 30, 620, 340),
    )
    try:
        presentation.activate()
        qt_app.processEvents()
        item = presentation.item
        from PySide6.QtCore import QPointF

        def row_rails(index):
            row = _find_visual_item(item, f"redditPostRow_{index}")
            assert row is not None and row.isVisible()
            texts = {key: _find_visual_item(item, f"redditPost{name}_{index}")
                     for key, name in (("age", "AgeValue"), ("ago", "AgeAgo"), ("title", "Title"))}
            assert all(v is not None and v.isVisible() for v in texts.values())
            return row, texts, {key: text.mapToItem(row, QPointF(0, 0)).x()
                                for key, text in texts.items()}

        originals = [row_rails(i)[1] for i in range(3)]
        order = ["age", "title", "ago"]
        presentation._apply_custom_layout_size_payload({"column_rails": order})
        qt_app.processEvents()
        for i in range(3):
            row, texts, pos = row_rails(i)
            assert pos["age"] < pos["title"] < pos["ago"]
            assert pos["ago"] + texts["ago"].width() <= row.width() + 1.0
            assert all(texts[key] is originals[i][key] for key in order)
        # An independent header flip must not scramble an explicitly saved order.
        model.set_custom_child_geometry({"header": {"alignment": "right"}})
        qt_app.processEvents()
        for i in range(3):
            _, _, pos = row_rails(i)
            assert pos["age"] < pos["title"] < pos["ago"]
        presentation.set_geometry(OverlayWidgetGeometry(25, 30, 540, 285))
        qt_app.processEvents()
        for i in range(3):
            _, _, pos = row_rails(i)
            assert pos["age"] < pos["title"] < pos["ago"]
        # The same live family consumes committed CUSTOM payload without row replacement.
        presentation._apply_custom_layout_size_payload({"column_rails": ["title", "ago", "age"]})
        qt_app.processEvents()
        for i in range(3):
            _, texts, pos = row_rails(i)
            assert pos["title"] < pos["ago"] < pos["age"]
            assert all(texts[key] is originals[i][key] for key in order)
    finally:
        host.retire_all()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        owner.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()
