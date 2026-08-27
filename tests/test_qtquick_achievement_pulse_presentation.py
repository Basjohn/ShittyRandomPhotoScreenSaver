from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QImage
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QSignalSpy

from rendering.quick.widgets.achievement_pulse import (
    AchievementPulsePresentationConfig,
    AchievementPulsePresentationModel,
    AchievementPulsePresentationStyle,
    RetainedAchievementPulsePresentation,
)
from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.host import OverlayWidgetGeometry
from rendering.quick.widgets.registry import (
    ORDINARY_WIDGET_FAMILY_COMPONENTS,
    ordinary_widget_family_component,
)
from rendering.quick.window import QuickDisplayWindow
from rendering.widget_runtime_manager import WidgetRuntimeManager
from widgets.steam_achievement_preparation import (
    AchievementPulsePreparedPresentation,
)
from widgets.steam_card_models import build_mock_steam_view_model


pytestmark = pytest.mark.usefixtures("qt_app")

ROOT = Path(__file__).resolve().parents[1]
QML_ROOT = ROOT / "rendering" / "quick" / "qml"


def _shadow_values(**changes):
    values = {
        "enabled": True,
        "text_enabled": True,
        "direction": "SE",
        "color": [0, 0, 0, 255],
        "frame_opacity": 0.77,
        "text_opacity": 0.33,
        "blur_radius": 18,
        "frame_extra_offset": 0,
        "text_extra_offset": 0,
    }
    values.update(changes)
    return values


def _config(**changes) -> AchievementPulsePresentationConfig:
    return replace(AchievementPulsePresentationConfig(), **changes)


def _model(
    *,
    config: AchievementPulsePresentationConfig | None = None,
    runtime_service=None,
) -> AchievementPulsePresentationModel:
    resolved_config = config or _config()
    return AchievementPulsePresentationModel(
        resolved_config,
        AchievementPulsePresentationStyle.project(
            resolved_config,
            _shadow_values(),
        ),
        runtime_service=runtime_service,
    )


def _image(path) -> QImage:
    image = QImage(8, 6, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.cyan)
    assert image.save(str(path)) is True
    return image


class _RuntimeService:
    def __init__(self, *, starts: bool = True) -> None:
        self.starts = starts
        self.configs = []
        self.thread_managers = []
        self.attached = []
        self.detached = []
        self.start_args = []
        self.stop_calls = 0
        self.refresh_calls = 0
        self.fade_complete_calls = 0

    def configure(self, config) -> None:
        self.configs.append(config)

    def set_thread_manager(self, manager) -> None:
        self.thread_managers.append(manager)

    def attach_consumer(self, consumer) -> None:
        self.attached.append(consumer)

    def detach_consumer(self, consumer) -> None:
        self.detached.append(consumer)

    def start(self, *, start_fade_after_load: bool = False) -> bool:
        self.start_args.append(start_fade_after_load)
        return self.starts

    def stop(self) -> None:
        self.stop_calls += 1

    def request_manual_refresh(self) -> bool:
        self.refresh_calls += 1
        return True

    def on_presentation_fade_complete(self) -> None:
        self.fade_complete_calls += 1


class _QueuedRuntimeManager:
    def __init__(self) -> None:
        self.tasks = []

    def submit_io_task(
        self,
        callback_fn,
        *args,
        task_id=None,
        callback=None,
        category=None,
        **kwargs,
    ) -> None:
        self.tasks.append(
            {
                "callback_fn": callback_fn,
                "args": args,
                "kwargs": kwargs,
                "task_id": task_id,
                "callback": callback,
                "category": category,
            }
        )


def _find_visual_item(root: QQuickItem, object_name: str) -> QQuickItem | None:
    if root.objectName() == object_name:
        return root
    for child in root.childItems():
        found = _find_visual_item(child, object_name)
        if found is not None:
            return found
    return None


def _create_qml_item(model: AchievementPulsePresentationModel):
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(
        engine,
        QUrl.fromLocalFile(
            str(QML_ROOT / "AchievementPulsePresentation.qml")
        ),
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    item = component.createWithInitialProperties({"achievementModel": model})
    assert isinstance(item, QQuickItem), [
        error.toString() for error in component.errors()
    ]
    item.setWidth(model.authoredWidth)
    item.setHeight(model.authoredHeight)
    return engine, component, item


def test_config_projects_current_steam_runtime_and_visual_settings() -> None:
    config = AchievementPulsePresentationConfig.from_widgets_mapping(
        {
            "steam": {
                "refresh_minutes": 33,
                "show_connection_info_icon": False,
            },
            "achievement_pulse": {
                "font_family": "Aptos",
                "font_size": 19,
                "color": [1, 2, 3, 204],
                "selection_mode": "custom",
                "custom_appid": 367520,
                "show_artwork": True,
                "artwork_shape": "square",
                "square_artwork_size": 190,
                "show_latest_achievement_artwork": False,
                "latest_unlock_count": 5,
                "double_capsules": False,
                "capsule_font_size": 22,
                "capsule_fill_color": [12, 34, 56, 78],
                "capsule_border_color": [90, 87, 65, 43],
                "show_source": True,
                "show_previous": False,
            },
        }
    )

    assert config.font_family == "Aptos"
    assert config.font_size == 19
    assert config.text_color == (1, 2, 3, 204)
    assert config.artwork_shape == "square"
    assert config.square_artwork_size == 190
    assert config.double_capsules is False
    assert config.capsule_font_size == 22
    assert config.capsule_fill_color == (12, 34, 56, 78)
    assert config.capsule_border_color == (90, 87, 65, 43)
    assert dict(config.field_visibility)["source"] is True
    assert dict(config.field_visibility)["previous"] is False
    assert config.authored_size[0] == 600.0
    runtime = config.runtime_config
    assert runtime.selection.mode == "custom"
    assert runtime.selection.custom_appid == 367520
    assert runtime.refresh_minutes == 33
    assert runtime.show_connection_info_icon is False
    assert runtime.latest_unlock_count == 5
    assert runtime.show_latest_artwork is False


def test_retained_layout_policy_preserves_shapes_and_grows_complete_capsule_rails() -> None:
    single = _config(double_capsules=False, artwork_shape="wide")
    portrait = replace(single, artwork_shape="portrait")
    square = replace(single, artwork_shape="square")
    doubled = replace(single, double_capsules=True)
    large_capsules = replace(doubled, capsule_font_size=32)

    assert single.authored_size[0] == 600.0
    assert 290.0 <= single.authored_size[1] < square.authored_size[1]
    assert square.authored_size[1] < portrait.authored_size[1]
    assert doubled.authored_size[1] > single.authored_size[1]
    assert large_capsules.authored_size[1] > doubled.authored_size[1]


def test_style_uses_canonical_shadow_direction_and_independent_alpha() -> None:
    config = _config(
        background_color=(20, 30, 40, 200),
        background_opacity=0.5,
        border_color=(90, 80, 70, 180),
        border_opacity=0.25,
    )
    style = AchievementPulsePresentationStyle.project(
        config,
        _shadow_values(
            direction="NW",
            frame_extra_offset=3,
            text_extra_offset=2,
        ),
        border_width=5,
    )

    assert style.card_style.padding == 0.0
    assert style.card_style.border_width == 5.0
    assert style.card_style.background_color.alpha() == 100
    assert style.card_style.border_color.alpha() == 45
    assert style.card_style.shadow_offset_x < 0
    assert style.card_style.shadow_offset_y < 0
    assert style.text_shadow_offset_x < 0
    assert style.text_shadow_offset_y < 0


def test_accepted_presentation_mutates_stable_models_and_image_sources(
    tmp_path,
) -> None:
    model = _model()
    assert model.activate() is True
    model.set_interaction_enabled(True)
    field_model = model.field_model
    unlock_model = model.unlock_model
    field_reset_spy = QSignalSpy(field_model.modelReset)
    unlock_reset_spy = QSignalSpy(unlock_model.modelReset)
    signal_spy = QSignalSpy(model.stateChanged)
    artwork_path = tmp_path / "game.png"
    icon_path = tmp_path / "unlock.png"

    card = build_mock_steam_view_model("achievement_pulse")
    presentation = AchievementPulsePreparedPresentation(
        model=card,
        artwork=_image(artwork_path),
        artwork_identity=str(artwork_path),
        artwork_key="101:portrait",
        latest_artwork=_image(icon_path),
        latest_artwork_identity=str(icon_path),
        latest_artwork_key="unlock-key",
    )
    model.on_achievement_presentation(presentation, animate=True)

    assert model.field_model is field_model
    assert model.unlock_model is unlock_model
    assert [row.field_id for row in field_model.rows] == [
        "rarity",
        "session",
        "total",
        "source",
        "selected",
    ]
    assert [row.text for row in unlock_model.rows][:2] == [
        "Steel Soul",
        "False Knight",
    ]
    assert model.artworkSource == artwork_path.resolve().as_uri()
    assert model.latestArtworkSource == icon_path.resolve().as_uri()
    assert model.title == "Hollow Knight"
    assert signal_spy.count() == 1

    model.on_achievement_presentation(presentation, animate=False)
    assert model.field_model is field_model
    assert model.unlock_model is unlock_model
    assert signal_spy.count() == 1

    changed_card = replace(
        card,
        fields=(replace(card.fields[0], value="9%"), *card.fields[1:]),
        latest_unlocks=("Steel Heart", *card.latest_unlocks[1:]),
    )
    model.on_achievement_presentation(
        replace(presentation, model=changed_card),
        animate=True,
    )
    assert field_model.rows[0].value == "9%"
    assert unlock_model.rows[0].text == "Steel Heart"
    assert field_reset_spy.count() == 0
    assert unlock_reset_spy.count() == 0


def test_runtime_activation_configures_existing_owner_and_routes_admitted_refresh() -> None:
    service = _RuntimeService()
    thread_manager = object()
    config = _config(
        selection_mode="custom",
        custom_appid=620,
        refresh_minutes=25,
    )
    model = _model(config=config, runtime_service=service)

    assert model.request_manual_refresh() is False
    assert model.activate(thread_manager) is True
    assert service.thread_managers == [thread_manager]
    assert service.attached == [model]
    assert service.start_args == [True]
    assert service.configs[0] == config.runtime_config
    assert model.request_manual_refresh() is False

    model.set_interaction_enabled(True)
    assert model.request_manual_refresh() is True
    assert service.refresh_calls == 1
    model.notify_fade_complete()
    assert service.fade_complete_calls == 1

    fade_spy = QSignalSpy(model.fadeRequested)
    model.request_achievement_fade()
    assert fade_spy.count() == 1
    model.retire()
    assert service.stop_calls == 1
    assert service.detached == [model]
    assert model.is_achievement_consumer_alive() is False
    assert model.request_manual_refresh() is False


def test_failed_runtime_start_detaches_and_fails_closed() -> None:
    service = _RuntimeService(starts=False)
    model = _model(runtime_service=service)

    with pytest.raises(RuntimeError, match="failed to start"):
        model.activate(object())

    assert service.detached == [model]
    assert model.is_achievement_consumer_alive() is False


@pytest.mark.qt
def test_qml_preserves_authored_regions_and_delegate_identity(qt_app) -> None:
    model = _model()
    model.activate()
    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(
            model=build_mock_steam_view_model("achievement_pulse")
        ),
        animate=False,
    )
    engine, component, item = _create_qml_item(model)
    try:
        qt_app.processEvents()
        canvas = _find_visual_item(item, "achievementAuthoredCanvas")
        header = _find_visual_item(item, "achievementHeaderFrame")
        artwork = _find_visual_item(item, "achievementArtworkFrame")
        metric = _find_visual_item(item, "achievementMetric")
        subtitle = _find_visual_item(item, "achievementSubtitle")
        rarity = _find_visual_item(item, "achievementField_rarity")
        rarity_detail = _find_visual_item(
            item, "achievementCapsuleDetail_rarity"
        )
        assert canvas is not None
        assert header is not None
        assert artwork is not None
        assert metric is not None
        assert subtitle is not None
        assert rarity is not None
        assert rarity_detail is not None
        assert float(item.property("contentScale")) == pytest.approx(1.0)
        assert (header.x(), header.y(), header.width(), header.height()) == (
            18.0,
            14.0,
            302.0,
            38.0,
        )
        assert (artwork.x(), artwork.y(), artwork.width(), artwork.height()) == (
            442.0,
            14.0,
            140.0,
            196.0,
        )
        assert metric.y() == pytest.approx(216.0)
        assert subtitle.isVisible() is False
        assert rarity_detail.isVisible() is True

        card = build_mock_steam_view_model("achievement_pulse")
        changed_card = replace(
            card,
            fields=(replace(card.fields[0], value="7%"), *card.fields[1:]),
        )
        model.on_achievement_presentation(
            AchievementPulsePreparedPresentation(model=changed_card),
            animate=True,
        )
        qt_app.processEvents()
        assert _find_visual_item(item, "achievementField_rarity") is rarity
        assert QQmlEngine.contextForObject(item).engine() is engine

        model.on_achievement_presentation(
            AchievementPulsePreparedPresentation(
                model=replace(changed_card, latest_unlocks=())
            ),
            animate=False,
        )
        qt_app.processEvents()
        assert _find_visual_item(item, "achievementSubtitle") is subtitle
        assert subtitle.isVisible() is True

        item.setWidth(model.authoredWidth * 1.5)
        item.setHeight(model.authoredHeight * 1.5)
        qt_app.processEvents()
        assert float(item.property("contentScale")) == pytest.approx(1.5)
        assert _find_visual_item(item, "achievementField_rarity") is rarity
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        qt_app.processEvents()


def test_qml_is_presentation_only_and_keeps_family_authored_capsule_shadow() -> None:
    qml = (QML_ROOT / "AchievementPulsePresentation.qml").read_text(
        encoding="utf-8"
    )
    capsule_qml = (QML_ROOT / "AchievementCapsule.qml").read_text(
        encoding="utf-8"
    )
    for marker in (
        "Timer {",
        "SettingsManager",
        "AchievementPulseRuntimeService",
        "SteamBackend",
        "QDesktopServices",
        "QWidget",
        "QPainter",
        "http://",
        "https://",
    ):
        assert marker not in qml
        assert marker not in capsule_qml
    assert "onDoubleTapped: achievementRoot.refreshRequested()" in qml
    assert "achievementRoot.settingsRequested(" in qml
    assert "AchievementCapsule" in qml
    assert "RectangularShadow" in capsule_qml
    assert "offset: Qt.vector2d(1.5, 1.5)" in capsule_qml
    assert "cached: true" in capsule_qml
    descriptor = ordinary_widget_family_component("achievement_pulse")
    assert descriptor.qml_filename == "AchievementPulsePresentation.qml"
    assert (
        descriptor.presentation_model_kind
        == "AchievementPulsePresentationModel"
    )
    assert descriptor in ORDINARY_WIDGET_FAMILY_COMPONENTS
    qmldir = (QML_ROOT / "qmldir").read_text(encoding="utf-8")
    assert (
        "AchievementPulsePresentation 1.0 AchievementPulsePresentation.qml"
        in qmldir
    )
    assert "AchievementCapsule 1.0 AchievementCapsule.qml" in qmldir


@pytest.mark.qt
def test_real_manager_owner_and_scene_host_keep_one_retained_runtime_chain(
    qt_app,
) -> None:
    class _Host:
        @staticmethod
        def get_runtime_widget_registry():
            return {}

    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=81,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    runtime_owner = WidgetRuntimeManager(_Host())
    manager = _QueuedRuntimeManager()
    config = _config()
    model = AchievementPulsePresentationModel(
        config,
        AchievementPulsePresentationStyle.project(config, _shadow_values()),
        parent=window,
    )
    service = runtime_owner.ensure_widget_service(
        "achievement_pulse",
        model,
        {
            "steam": {"refresh_minutes": 10},
            "achievement_pulse": {"enabled": True},
        },
    )
    assert service is not None
    assert model._achievement_runtime_service is service
    assert service.is_running() is False

    settings_requests = []
    presentation = None
    try:
        presentation = RetainedAchievementPulsePresentation(
            host=controller.ordinary_widget_host,
            model=model,
            geometry=OverlayWidgetGeometry(25.0, 30.0, 600.0, 334.0),
            on_settings_requested=lambda target: settings_requests.append(target)
            or True,
        )
        item = presentation.item
        engine = QQmlEngine.contextForObject(item).engine()
        field_model = model.field_model
        unlock_model = model.unlock_model
        assert item.property("fadeOpacity") == pytest.approx(0.0)

        assert presentation.activate(manager) is True
        qt_app.processEvents()
        assert service.runtime_generation == 81
        assert service.is_running() is True
        assert [task["category"] for task in manager.tasks] == [
            "steam_achievement_cache_load"
        ]

        service._accept_model(
            build_mock_steam_view_model("achievement_pulse"),
            profile_key="",
            animate=False,
        )
        qt_app.processEvents()
        first_field = _find_visual_item(item, "achievementField_rarity")
        assert first_field is not None

        presentation.apply_input_state(
            {
                "admission_open": True,
                "exiting": False,
                "interaction_mode_enabled": True,
                "ctrl_held": False,
            }
        )
        item.settingsRequested.emit("steam_connection")
        item.refreshRequested.emit()
        assert settings_requests == ["steam_connection"]
        assert [task["category"] for task in manager.tasks] == [
            "steam_achievement_cache_load",
            "steam_achievement_refresh",
        ]

        service._request_consumer_fade()
        qt_app.processEvents()
        assert item.property("fadeOpacity") == pytest.approx(1.0)
        assert presentation.item is item
        assert presentation.model is model
        assert model.field_model is field_model
        assert model.unlock_model is unlock_model
        assert QQmlEngine.contextForObject(item).engine() is engine
        assert _find_visual_item(item, "achievementField_rarity") is first_field
    finally:
        controller.quiesce_for_retirement()
        runtime_owner.cleanup()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()

    assert presentation is not None
    assert service.is_retired() is True
