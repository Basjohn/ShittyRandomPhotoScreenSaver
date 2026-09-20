from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from core.settings.default_contract import require_canonical_default
from PySide6.QtCore import QPointF, QUrl, Qt
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
        **require_canonical_default("widgets.shadows"),
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
    return replace(AchievementPulsePresentationConfig.from_widgets_mapping({}), **changes)


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
                "progress_pulse": False,
                "shelf_style": True,
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
    assert config.progress_pulse is False
    assert config.shelf_style is True
    assert config.capsule_font_size == 22
    assert config.capsule_fill_color == (12, 34, 56, 78)
    assert config.capsule_border_color == (90, 87, 65, 43)
    assert config.semantic_palette.artwork_border == (199, 213, 224, 255)
    assert dict(config.field_visibility)["source"] is True
    assert dict(config.field_visibility)["previous"] is False
    assert config.authored_size[0] == float(require_canonical_default("widgets.achievement_pulse.preferred_width"))
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

    assert single.authored_size[0] == float(require_canonical_default("widgets.achievement_pulse.preferred_width"))
    # Authored outer height is artwork-shape driven (wide < square < portrait).
    assert 290.0 <= single.authored_size[1] < square.authored_size[1]
    assert square.authored_size[1] < portrait.authored_size[1]
    # Progress Pulse's double-capsule rails reserve a complete second rail per
    # compact row, so doubling never shrinks the authored envelope and grows it
    # once the doubled rail block exceeds the two-rail baseline; a larger capsule
    # font grows it further still.
    assert doubled.authored_size[1] >= single.authored_size[1]
    assert large_capsules.authored_size[1] > doubled.authored_size[1]


def test_custom_content_extent_grows_logical_canvas_and_reflows_major_rails(qt_app) -> None:
    model = _model()
    model.activate()
    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(
            model=build_mock_steam_view_model("achievement_pulse")
        ),
        animate=False,
    )
    base_width = float(model.baseAuthoredWidth)
    base_height = float(model.baseAuthoredHeight)
    engine, component, item = _create_qml_item(model)
    try:
        qt_app.processEvents()
        artwork = _find_visual_item(item, "achievementArtworkFrame")
        rarity = _find_visual_item(item, "achievementField_rarity")
        field_group = _find_visual_item(item, "achievementFieldGroup")
        pulse = _find_visual_item(item, "achievementProgressPulse")
        game_title = _find_visual_item(item, "achievementGameTitle")
        list_frame = _find_visual_item(item, "achievementListGroup")
        assert artwork is not None and rarity is not None and field_group is not None
        assert pulse is not None and game_title is not None and list_frame is not None
        base_title_width = game_title.width()
        base_list_width = list_frame.width()
        base_artwork_x = artwork.x()
        base_rarity_width = rarity.width()
        base_field_group_width = field_group.width()
        base_field_group_y = field_group.y()
        base_pulse_y = pulse.y()

        assert model.set_content_extent(base_width + 220.0, base_height + 120.0) is True
        item.setWidth(model.authoredWidth)
        item.setHeight(model.authoredHeight)
        qt_app.processEvents()

        assert model.contentExtentActive is True
        assert model.authoredWidth == pytest.approx(base_width + 220.0)
        assert model.authoredHeight == pytest.approx(base_height + 120.0)
        assert artwork.x() == pytest.approx(base_artwork_x + 220.0)
        # The authored text rail remains attached to the live artwork-left edge
        # and widens with parent X. Persisted role baselines stay canonical.
        assert game_title.width() == pytest.approx(base_title_width + 220.0)
        assert list_frame.width() == pytest.approx(base_list_width + 220.0)
        if artwork.isVisible():
            assert game_title.x() + game_title.width() <= artwork.x() - 1.0
        # Authored bottom-rail roles translate as a group.
        assert rarity.width() == pytest.approx(base_rarity_width)
        assert field_group.width() == pytest.approx(base_field_group_width)
        assert field_group.y() == pytest.approx(base_field_group_y + 120.0)
        assert pulse.y() == pytest.approx(base_pulse_y + 120.0)

        assert model.clear_content_extent() is True
        item.setWidth(model.authoredWidth)
        item.setHeight(model.authoredHeight)
        qt_app.processEvents()
        assert model.contentExtentActive is False
        assert model.authoredWidth == pytest.approx(base_width)
        assert model.authoredHeight == pytest.approx(base_height)
        assert artwork.x() == pytest.approx(base_artwork_x)
        assert game_title.width() == pytest.approx(base_title_width)
        assert list_frame.width() == pytest.approx(base_list_width)
    finally:
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()


def test_custom_child_geometry_freeforms_artwork_and_scales_intrinsic_progress_as_one_shape(qt_app) -> None:
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
        artwork = _find_visual_item(item, "achievementArtworkFrame")
        metric = _find_visual_item(item, "achievementMetric")
        progress = _find_visual_item(item, "achievementProgressPulse")
        rarity = _find_visual_item(item, "achievementField_rarity")
        field_group = _find_visual_item(item, "achievementFieldGroup")
        assert artwork is not None and metric is not None
        assert progress is not None and rarity is not None and field_group is not None
        base_artwork_width = artwork.width()
        base_artwork_height = artwork.height()
        base_metric_y = metric.y()

        spy = QSignalSpy(model.customGeometryChanged)
        assert model.set_custom_child_geometry(
            {
                "artwork": {"width_scale": 1.35, "height_scale": 0.75},
                # Deliberately mismatched persisted axes: intrinsic roles must
                # canonicalize to one scale before presentation.
                "progress_circle": {"width_scale": 1.40, "height_scale": 0.70},
            }
        ) is True
        qt_app.processEvents()

        assert spy.count() == 1
        assert artwork.width() == pytest.approx(base_artwork_width * 1.35)
        assert artwork.height() == pytest.approx(base_artwork_height * 0.75)
        assert metric.y() == pytest.approx(
            base_metric_y + base_artwork_height * (0.75 - 1.0)
        )
        assert progress.width() == pytest.approx(108.0)
        assert progress.height() == pytest.approx(108.0)
        assert progress.scale() == pytest.approx(1.40)
        # Progress growth reflows the still-authored field group, without
        # rewriting the nested capsule delegates themselves.
        assert field_group.x() == pytest.approx(51.0 + 108.0 * 1.40 + 49.0)

        assert model.customArtworkWidthScale == pytest.approx(1.35)
        assert model.customArtworkHeightScale == pytest.approx(0.75)
        assert model.customProgressCircleScale == pytest.approx(1.40)
    finally:
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()


def test_dense_custom_child_geometry_projects_offsets_alignment_and_header_anchor(qt_app) -> None:
    model = _model()
    spy = QSignalSpy(model.customGeometryChanged)

    assert model.set_custom_child_geometry(
        {
            "header": {
                "width_scale": 1.20,
                "height_scale": 0.80,
                "x_offset": 0.10,
                "y_offset": -0.05,
                "alignment": "right",
                "anchor": "bottom_right",
            },
            "game_name": {
                "width_scale": 1.30,
                "height_scale": 1.15,
                "x_offset": 0.08,
                "y_offset": 0.04,
                "alignment": "right",
            },
            "achievement_list": {
                "width_scale": 0.80,
                "height_scale": 1.25,
                "x_offset": -0.03,
                "y_offset": 0.07,
                "alignment": "right",
            },
            "field_group": {
                "width_scale": 1.10,
                "height_scale": 0.90,
                "x_offset": 0.02,
                "y_offset": -0.06,
            },
        }
    ) is True

    assert spy.count() == 1
    # Uniform header geometry canonicalizes mismatched persisted axes.
    assert model.customHeaderWidthScale == pytest.approx(1.20)
    assert model.customHeaderHeightScale == pytest.approx(1.20)
    assert model.customHeaderAlignment == "right"
    assert model.customHeaderAnchor == "bottom_right"
    assert model.customGameNameWidthScale == pytest.approx(1.30)
    assert model.customGameNameHeightScale == pytest.approx(1.15)
    assert model.customGameNameXOffset == pytest.approx(0.08)
    assert model.customGameNameYOffset == pytest.approx(0.04)
    assert model.customGameNameAlignment == "right"
    assert model.customAchievementListWidthScale == pytest.approx(0.80)
    assert model.customAchievementListHeightScale == pytest.approx(1.25)
    assert model.customAchievementListAlignment == "right"
    assert model.customFieldGroupWidthScale == pytest.approx(1.10)
    assert model.customFieldGroupHeightScale == pytest.approx(0.90)
    assert model.customFieldGroupXOffset == pytest.approx(0.02)
    assert model.customFieldGroupYOffset == pytest.approx(-0.06)


def test_latest_unlock_visibility_does_not_allocate_bottom_capsule_rails() -> None:
    default = _config(artwork_shape="portrait", double_capsules=True)
    no_latest = replace(
        default,
        field_visibility=tuple(
            (field_id, False if field_id == "latest" else enabled)
            for field_id, enabled in default.field_visibility
        ),
    )
    extra_capsule = replace(
        default,
        field_visibility=tuple(
            (field_id, True if field_id == "source" else enabled)
            for field_id, enabled in default.field_visibility
        ),
    )

    # ``latest`` belongs to the unlock hierarchy and must never create an empty
    # bottom capsule rail: toggling it changes no authored geometry. The exact
    # portrait envelope is font-metric/artwork-size driven, so assert the width
    # invariant plus the latest/extra-field behavioural contract rather than a
    # single environment-specific pixel height.
    assert default.authored_size[0] == float(require_canonical_default("widgets.achievement_pulse.preferred_width"))
    assert no_latest.authored_size == default.authored_size
    assert extra_capsule.authored_size[1] > default.authored_size[1]


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
    assert style.card_style.shadow_offset_x == -4.0
    assert style.card_style.shadow_offset_y == -4.0
    assert style.card_style.shadow_extend_left == 3.0
    assert style.card_style.shadow_extend_top == 3.0
    assert style.card_style.shadow_extend_right == 0.0
    assert style.card_style.shadow_extend_bottom == 0.0
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


def test_progress_pulse_is_event_owned_and_only_fires_for_numeric_total_changes() -> None:
    model = _model()
    assert model.config.progress_pulse is True
    assert model.activate() is True
    pulse_spy = QSignalSpy(model.progressPulseRequested)

    card = build_mock_steam_view_model("achievement_pulse")
    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(model=card),
        animate=False,
    )
    # First resolved value establishes the baseline; opening the widget is not a
    # fake achievement-progress event.
    assert pulse_spy.count() == 0
    assert model.progressText == "67%"
    assert "total" not in [row.field_id for row in model.field_model.rows]

    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(model=card),
        animate=True,
    )
    assert pulse_spy.count() == 0

    changed_fields = tuple(
        replace(field, value="68%") if field.field_id == "total" else field
        for field in card.fields
    )
    changed = replace(card, fields=changed_fields)
    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(model=changed),
        animate=True,
    )
    assert pulse_spy.count() == 1
    assert model.progressText == "68%"

    # Unrelated refresh content is not a pulse trigger.
    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(
            model=replace(changed, status="same progress, newer metadata")
        ),
        animate=True,
    )
    assert pulse_spy.count() == 1

    zero_fields = tuple(
        replace(field, value="0%") if field.field_id == "total" else field
        for field in changed.fields
    )
    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(model=replace(changed, fields=zero_fields)),
        animate=True,
    )
    assert pulse_spy.count() == 2
    assert model.progressText == "0%"


def test_progress_pulse_off_restores_total_to_the_supporting_field_model() -> None:
    model = _model(config=_config(progress_pulse=False))
    assert model.activate() is True
    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(
            model=build_mock_steam_view_model("achievement_pulse")
        ),
        animate=False,
    )
    assert "total" in [row.field_id for row in model.field_model.rows]


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
def test_qml_preserves_authored_regions_and_delegate_identity(qt_app, tmp_path) -> None:
    model = _model()
    model.activate()
    latest_icon_path = tmp_path / "latest-unlock.png"
    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(
            model=build_mock_steam_view_model("achievement_pulse"),
            latest_artwork=_image(latest_icon_path),
            latest_artwork_identity=str(latest_icon_path),
            latest_artwork_key="latest-unlock",
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
        latest_badge = _find_visual_item(item, "achievementLatestArtworkFrame")
        first_unlock = _find_visual_item(item, "achievementUnlock_0")
        second_unlock = _find_visual_item(item, "achievementUnlock_1")
        artwork_border = _find_visual_item(item, "achievementArtworkBorder")
        latest_badge_border = _find_visual_item(
            item, "achievementLatestArtworkBorder"
        )
        card = _find_visual_item(item, "overlayWidgetCard")
        rarity = _find_visual_item(item, "achievementField_rarity")
        field_group = _find_visual_item(item, "achievementFieldGroup")
        rarity_detail = _find_visual_item(
            item, "achievementCapsuleDetail_rarity"
        )
        progress_pulse = _find_visual_item(item, "achievementProgressPulse")
        assert canvas is not None
        assert header is not None
        assert artwork is not None
        assert metric is not None
        assert subtitle is not None
        assert latest_badge is not None
        assert first_unlock is not None
        assert second_unlock is not None
        assert artwork_border is not None
        assert latest_badge_border is not None
        assert card is not None
        assert rarity is not None
        assert field_group is not None
        assert rarity_detail is not None
        assert progress_pulse is not None
        assert progress_pulse.isVisible() is True
        assert (progress_pulse.x(), progress_pulse.width(), progress_pulse.height()) == (51.0, 108.0, 108.0)
        assert str(model.progressText) == "67%"
        assert _find_visual_item(item, "achievementField_total") is None
        # Dense rollout groups the repeated capsules under one shared editable
        # field-group target.  Delegate-local X is therefore zero for the first
        # field; its authored scene X is preserved by the group itself.
        assert field_group.x() + rarity.x() == pytest.approx(208.0)
        assert float(item.property("contentScale")) == pytest.approx(1.0)
        # The shared BrandedHeader owns content-driven dimensions; the named
        # frame fills that owner, which sits at the family-authored anchor.
        header_owner = header.parentItem()
        assert (header_owner.x(), header_owner.y()) == (18.0, 14.0)
        assert (header.x(), header.y()) == (0.0, 0.0)
        assert header.width() == pytest.approx(header_owner.implicitWidth())
        assert header.height() == pytest.approx(header_owner.implicitHeight())
        # Canonical square_artwork_size is 160; portrait aspect 1.4 -> 160x224,
        # centred on x=491 so the left edge sits at 411.
        assert (artwork.x(), artwork.y(), artwork.width(), artwork.height()) == (
            411.0,
            14.0,
            160.0,
            224.0,
        )
        assert metric.x() == pytest.approx(401.0)
        assert artwork.x() + artwork.width() / 2.0 == pytest.approx(491.0)
        assert metric.x() + metric.width() / 2.0 == pytest.approx(491.0)
        assert latest_badge.y() == pytest.approx(130.0)
        assert latest_badge.width() == pytest.approx(40.0)
        assert latest_badge.height() == pytest.approx(40.0)
        # Badge starts materially left of the old fixed x=130 rail but is allowed
        # to move right when the rendered smaller unlock strings require room.
        assert latest_badge.x() < 130.0
        assert latest_badge.x() >= 102.0
        assert latest_badge.x() >= (
            second_unlock.x() + second_unlock.implicitWidth() + 8.0 - 0.5
        )
        assert first_unlock.width() > second_unlock.width()
        assert str(metric.property("text")).startswith("Unlocked: ")
        # Metric sits below the artwork; the 160x224 portrait is 28px taller than
        # the former 140x196, so the caption drops from 216 to 244.
        assert metric.y() == pytest.approx(244.0)
        assert subtitle.isVisible() is False
        # Progress Pulse double capsules default on (shelf off), so each capsule
        # exposes its detail rail.
        assert rarity_detail.isVisible() is True

        # A taller committed/CUSTOM root may retain its outer interaction rect,
        # but the complete card shell must keep the authored aspect. Spare height
        # belongs outside the card, never as dead bands inside it. Assert against
        # the model's authored height so the bar tracks the canonical layout
        # rather than one environment's font-metric pixel total.
        authored_height = float(model.authoredHeight)
        item.setWidth(model.authoredWidth)
        item.setHeight(authored_height + 66.0)
        qt_app.processEvents()
        assert bool(item.property("uniformScaleTransform")) is True
        assert float(item.property("presentationScale")) == pytest.approx(1.0)
        assert float(item.property("cardShadowVisualHeight")) == pytest.approx(authored_height)
        assert float(item.property("cardShadowVisualY")) == pytest.approx(33.0)
        assert card.height() == pytest.approx(authored_height)

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


@pytest.mark.qt
def test_qml_shelf_style_reuses_abandonment_ledger_treatment(qt_app) -> None:
    model = _model(config=_config(shelf_style=True))
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
        shelf = _find_visual_item(item, "achievementShelf_rarity")
        primary = _find_visual_item(item, "achievementCapsulePrimary_rarity")
        assert shelf is not None and shelf.isVisible() is True
        assert primary is not None and primary.isVisible() is False
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
    assert 'objectName: "achievementArtworkBorder"' in qml
    assert 'objectName: "achievementLatestArtworkBorder"' in qml
    assert 'uniformScaleTransform: true' in qml
    assert 'id: fieldGroupFrame' in qml
    assert 'readonly property real canonicalX: progressPulse.visible' in qml
    assert 'resolvedRailX()' in qml
    assert 'headerFlipped' in qml
    assert 'fontSizeMode: Text.HorizontalFit' in qml
    assert '+ ": " + achievementRoot.achievementModel.metricValue' in qml
    assert "latestArtworkBackground" not in qml
    assert 'objectName: "achievementProgressPulse"' in qml
    assert "onProgressPulseRequested" in qml
    assert "duration: 2000" in qml
    assert "duration: 3000" in qml
    assert 'fragmentShader: "shaders/widget_glow.frag.qsb"' in qml
    assert "widgetFrameDemand" not in qml
    assert "SequentialAnimation" in qml
    assert "NumberAnimation" in qml
    assert 'objectName: "achievementShelf_" + capsule.fieldId' in capsule_qml
    assert "capsule.shelfSeparatorColor" in capsule_qml
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
    steam_actions = []
    presentation = None
    try:
        presentation = RetainedAchievementPulsePresentation(
            host=controller.ordinary_widget_host,
            model=model,
            geometry=OverlayWidgetGeometry(25.0, 30.0, 600.0, 334.0),
            on_settings_requested=lambda target: settings_requests.append(target)
            or True,
            on_steam_action_requested=lambda kind, target: steam_actions.append(
                (kind, target)
            )
            or True,
        )
        item = presentation.item
        engine = QQmlEngine.contextForObject(item).engine()
        field_model = model.field_model
        unlock_model = model.unlock_model
        assert item.property("fadeOpacity") == pytest.approx(0.0)

        presentation._apply_custom_layout_size_payload(
            {"content_extent": [config.authored_size[0] + 120.0, config.authored_size[1] + 80.0]}
        )
        assert model.contentExtentActive is True
        assert model.authoredWidth == pytest.approx(config.authored_size[0] + 120.0)
        presentation._apply_custom_layout_size_payload({})
        assert model.contentExtentActive is False

        assert presentation.activate(manager) is True
        qt_app.processEvents()
        assert service.runtime_generation == 81
        assert service.is_running() is True
        assert [task["category"] for task in manager.tasks] == [
            "steam_achievement_cache_load"
        ]

        service._accept_model(
            replace(build_mock_steam_view_model("achievement_pulse"), appid=620),
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
        item.storeRequested.emit()
        assert settings_requests == ["steam_connection"]
        assert steam_actions == [("store", str(model.appid))]
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


def test_first_achievement_child_role_is_independent_of_remainder_list() -> None:
    model = _model()
    assert model.set_custom_child_geometry({
        "first_achievement": {
            "width_scale": 1.35, "height_scale": 1.25,
            "x_offset": 0.05, "y_offset": 0.06, "alignment": "right",
        },
        "achievement_list": {
            "width_scale": 0.80, "height_scale": 0.75,
            "x_offset": -0.04, "y_offset": 0.03, "alignment": "left",
        },
    })
    assert model.customFirstAchievementWidthScale == pytest.approx(1.35)
    assert model.customFirstAchievementHeightScale == pytest.approx(1.25)
    assert model.customFirstAchievementAlignment == "right"
    assert model.customAchievementListWidthScale == pytest.approx(0.80)
    assert model.customAchievementListAlignment == "left"
    qml = (QML_ROOT / "AchievementPulsePresentation.qml").read_text(encoding="utf-8")
    assert '"collisionIgnoreRoleIds": ["achievement_list"]' in qml
    assert '"collisionIgnoreRoleIds": ["first_achievement"]' in qml
    assert 'customFirstAchievementXOffset\n                                - achievementRoot.achievementModel.customAchievementListXOffset' in qml


@pytest.mark.qt
def test_first_unlock_authored_empty_custom_and_remainder_edit_keep_scene_position(qt_app, tmp_path) -> None:
    """A new child descriptor must not move unedited first-unlock glyphs."""
    model = _model()
    model.activate()
    icon_path = tmp_path / "achievement-first-unlock.png"
    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(
            model=build_mock_steam_view_model("achievement_pulse"),
            latest_artwork=_image(icon_path),
            latest_artwork_identity=str(icon_path),
            latest_artwork_key="first-unlock-parity",
        ),
        animate=False,
    )
    engine, component, root = _create_qml_item(model)
    try:
        qt_app.processEvents()
        canvas = _find_visual_item(root, "achievementAuthoredCanvas")
        first = _find_visual_item(root, "achievementUnlock_0")
        remainder = _find_visual_item(root, "achievementUnlock_1")
        assert canvas is not None and first is not None and remainder is not None

        def scene_position(item):
            point = item.mapToItem(canvas, QPointF(0.0, 0.0))
            return (point.x(), point.y())

        first_before = scene_position(first)
        remainder_before = scene_position(remainder)
        first_size = (first.width(), first.height())
        assert model.set_custom_child_geometry({}) is False
        qt_app.processEvents()
        assert scene_position(first) == pytest.approx(first_before)
        assert (first.width(), first.height()) == pytest.approx(first_size)

        assert model.set_custom_child_geometry({
            "achievement_list": {
                "width_scale": 0.80, "height_scale": 1.25,
                "x_offset": 0.09, "y_offset": 0.08, "alignment": "right",
            }
        }) is True
        qt_app.processEvents()
        assert scene_position(first) == pytest.approx(first_before)
        assert (first.width(), first.height()) == pytest.approx(first_size)
        assert scene_position(remainder) != pytest.approx(remainder_before)

        assert model.set_custom_child_geometry({}) is True
        qt_app.processEvents()
        assert scene_position(first) == pytest.approx(first_before)
        assert scene_position(remainder) == pytest.approx(remainder_before)
    finally:
        root.deleteLater()
        component.deleteLater()
        engine.deleteLater()


@pytest.mark.qt
def test_semantic_header_flip_exchanges_achievement_regions_not_image_or_text_pixels(qt_app) -> None:
    """Existing Header intent changes region positions, not their rendering.

    A parent-width change must not make a mirrored child's logical requirement
    grow in a self-reinforcing loop. The original authored positions must return
    after removing the single normalized child-geometry flip record.
    """
    model = _model()
    model.activate()
    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(
            model=build_mock_steam_view_model("achievement_pulse")
        ), animate=False,
    )
    engine, component, item = _create_qml_item(model)
    try:
        qt_app.processEvents()
        find = lambda name: _find_visual_item(item, name)
        canvas = find("achievementAuthoredCanvas")
        art = find("achievementArtworkFrame")
        image = find("achievementArtworkImage")
        title = find("achievementGameTitle")
        unlocks = find("achievementListGroup")
        progress = find("achievementProgressPulse")
        fields = find("achievementFieldGroup")
        requirement = item.property("customEditableChildRequirementTarget")
        from PySide6.QtQml import QJSValue
        if isinstance(requirement, QJSValue):
            requirement = requirement.toQObject()
        # Parent sizing is owned by content_extent; the old child-driven
        # requirement object was retired to prevent reflow feedback.
        assert requirement is None
        painted = {
            "canvas": canvas, "artwork": art, "image": image,
            "title": title, "unlocks": unlocks,
            "progress": progress, "fields": fields,
        }
        assert all(obj is not None for obj in painted.values()), [
            name for name, obj in painted.items() if obj is None
        ]
        assert art.isVisible() and progress.isVisible() and fields.isVisible()
        def pos(obj):
            return obj.mapToItem(canvas, 0.0, 0.0).x()
        roles = (art, title, unlocks, progress, fields)
        original = tuple(pos(obj) for obj in roles)
        art_fill = image.property("fillMode")
        title_alignment = title.property("horizontalAlignment")
        base_width = float(model.baseAuthoredWidth)
        base_height = float(model.baseAuthoredHeight)
        assert title.x() < art.x()

        assert model.set_custom_child_geometry({"header": {"alignment": "right"}})
        qt_app.processEvents()
        assert bool(item.property("headerFlipped"))
        for obj, initial_x in zip(roles, original):
            assert pos(obj) == pytest.approx(base_width - initial_x - obj.width(), abs=1.5)
        assert art.x() < title.x() and progress.x() > fields.x()
        assert image.property("fillMode") == art_fill
        # Header reverses semantic text alignment as well as region placement;
        # image pixels are not mirrored and per-role flips remain independent.
        assert int(title.property("horizontalAlignment")) == int(Qt.AlignmentFlag.AlignRight)
        flipped_title_width = title.width()
        flipped_art_x = art.x()
        assert model.set_content_extent(base_width + 140.0, base_height)
        item.setWidth(model.authoredWidth)
        item.setHeight(model.authoredHeight)
        qt_app.processEvents()
        assert art.x() == pytest.approx(flipped_art_x)
        assert title.width() == pytest.approx(flipped_title_width + 140.0)
        # The painted right-rail relation may reflow, but it must not publish
        # another outer-size request after event-loop settling.
        for _ in range(3):
            qt_app.processEvents()
            assert float(model.authoredWidth) == pytest.approx(base_width + 140.0)
            assert float(model.baseAuthoredWidth) == pytest.approx(base_width)
            assert float(item.property("extraContentWidth")) == pytest.approx(140.0)
            assert art.x() == pytest.approx(flipped_art_x)

        assert model.clear_content_extent()
        item.setWidth(model.authoredWidth)
        item.setHeight(model.authoredHeight)
        assert model.set_custom_child_geometry({})
        qt_app.processEvents()
        assert not bool(item.property("headerFlipped"))
        assert tuple(pos(obj) for obj in roles) == pytest.approx(original)
        assert title.property("horizontalAlignment") == title_alignment
    finally:
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()


@pytest.mark.qt
def test_achievement_list_flip_mirrors_small_text_and_unedited_badge(qt_app, tmp_path) -> None:
    """Flip must exchange the small-text and badge lanes, not align in a left stub.

    The first unlock has its own descriptor/persisted role. The badge may also
    be moved independently; neither is reauthored by flipping the list.
    """
    model = _model()
    model.activate()
    badge_file = tmp_path / "achievement-flip-badge.png"
    card = replace(
        build_mock_steam_view_model("achievement_pulse"),
        latest_unlocks=("First large unlock", "Second small unlock", "Third unlock"),
    )
    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(
            model=card,
            latest_artwork=_image(badge_file),
            latest_artwork_identity=str(badge_file),
            latest_artwork_key="flip-badge",
        ),
        animate=False,
    )
    engine, component, item = _create_qml_item(model)
    try:
        qt_app.processEvents()
        canvas = _find_visual_item(item, "achievementAuthoredCanvas")
        group = _find_visual_item(item, "achievementListGroup")
        first = _find_visual_item(item, "achievementUnlock_0")
        second = _find_visual_item(item, "achievementUnlock_1")
        badge = _find_visual_item(item, "achievementLatestArtworkFrame")
        assert all(part is not None for part in (canvas, group, first, second, badge))
        assert badge.isVisible() and second.isVisible()

        def at_canvas(part):
            return part.mapToItem(canvas, 0.0, 0.0).x()

        first_x = at_canvas(first)
        original_badge = at_canvas(badge)
        original_second = at_canvas(second)
        assert original_second + second.width() <= original_badge - 5.0

        assert model.set_custom_child_geometry({
            "achievement_list": {"alignment": "right"},
        })
        qt_app.processEvents()
        assert first_x == pytest.approx(at_canvas(first), abs=0.1)
        assert badge is _find_visual_item(item, "achievementLatestArtworkFrame")
        assert second is _find_visual_item(item, "achievementUnlock_1")
        assert int(second.property("horizontalAlignment")) == int(Qt.AlignmentFlag.AlignRight)
        assert at_canvas(badge) > original_badge + 20.0
        assert at_canvas(second) >= at_canvas(badge) + badge.width() * badge.scale() + 5.0
        assert at_canvas(second) + second.width() == pytest.approx(
            at_canvas(group) + group.width(), abs=0.1,
        ), "Small text must right-align at the true group edge, not the old left-side stub"

        # An independent badge drag is its own persisted geometry. Flipping
        # the list does not overwrite its explicit placement record.
        assert model.set_custom_child_geometry({
            "achievement_list": {"alignment": "right"},
            "badge": {"x_offset": 0.10},
        })
        qt_app.processEvents()
        manually_moved = at_canvas(badge)
        assert model.set_custom_child_geometry({
            "achievement_list": {"alignment": "left"},
            "badge": {"x_offset": 0.10},
        })
        qt_app.processEvents()
        assert at_canvas(badge) == pytest.approx(manually_moved, abs=0.1)
        assert int(second.property("horizontalAlignment")) == int(Qt.AlignmentFlag.AlignLeft)
        assert first_x == pytest.approx(at_canvas(first), abs=0.1)

        assert model.set_custom_child_geometry({})
        qt_app.processEvents()
        assert at_canvas(badge) == pytest.approx(original_badge, abs=0.1)
        assert at_canvas(second) == pytest.approx(original_second, abs=0.1)
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        qt_app.processEvents()

@pytest.mark.qt
def test_header_flip_mirrors_actual_title_first_unlock_and_small_text_lanes(qt_app, tmp_path) -> None:
    """Exercise the operator's real Header-flip gesture, NOT a list-only flip.

    The parent Header flip moves the artwork/text regions. The painted glyphs
    and the badge/list lanes must follow the resulting semantic orientation,
    while independently flipping a child must still invert that child's lane.
    """
    model = _model()
    model.activate()
    badge_file = tmp_path / "achievement-header-flip-badge.png"
    card = replace(
        build_mock_steam_view_model("achievement_pulse"),
        latest_unlocks=("First large unlock", "Second small unlock", "Third unlock"),
    )
    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(
            model=card, latest_artwork=_image(badge_file),
            latest_artwork_identity=str(badge_file),
            latest_artwork_key="header-flip-badge",
        ),
        animate=False,
    )
    engine, component, item = _create_qml_item(model)
    try:
        qt_app.processEvents()
        canvas = _find_visual_item(item, "achievementAuthoredCanvas")
        group = _find_visual_item(item, "achievementListGroup")
        title = _find_visual_item(item, "achievementGameTitle")
        first = _find_visual_item(item, "achievementUnlock_0")
        second = _find_visual_item(item, "achievementUnlock_1")
        badge = _find_visual_item(item, "achievementLatestArtworkFrame")
        assert all(part is not None for part in (canvas, group, title, first, second, badge))
        assert badge.isVisible() and second.isVisible()

        def x_at_canvas(part):
            return part.mapToItem(canvas, 0.0, 0.0).x()

        starting_group_x = x_at_canvas(group)
        assert int(second.property("horizontalAlignment")) == int(Qt.AlignmentFlag.AlignLeft)
        assert model.set_custom_child_geometry({"header": {"alignment": "right"}})
        qt_app.processEvents()
        assert x_at_canvas(group) > starting_group_x + 30.0
        assert int(title.property("horizontalAlignment")) == int(Qt.AlignmentFlag.AlignRight)
        assert int(first.property("horizontalAlignment")) == int(Qt.AlignmentFlag.AlignRight)
        assert int(second.property("horizontalAlignment")) == int(Qt.AlignmentFlag.AlignRight)
        assert x_at_canvas(second) >= x_at_canvas(badge) + badge.width() * badge.scale() + 5.0
        assert x_at_canvas(second) + second.width() == pytest.approx(
            x_at_canvas(group) + group.width(), abs=0.1,
        )
        # Independently flip text roles while the Header is still reversed.
        assert model.set_custom_child_geometry({
            "header": {"alignment": "right"},
            "game_name": {"alignment": "right"},
            "first_achievement": {"alignment": "right"},
            "achievement_list": {"alignment": "right"},
        })
        qt_app.processEvents()
        assert int(title.property("horizontalAlignment")) == int(Qt.AlignmentFlag.AlignLeft)
        assert int(first.property("horizontalAlignment")) == int(Qt.AlignmentFlag.AlignLeft)
        assert int(second.property("horizontalAlignment")) == int(Qt.AlignmentFlag.AlignLeft)
        # No overlay-role replacement, timer, or re-parenting to implement a flip.
        assert second is _find_visual_item(item, "achievementUnlock_1")
        assert badge is _find_visual_item(item, "achievementLatestArtworkFrame")
        assert model.set_custom_child_geometry({})
        qt_app.processEvents()
        assert x_at_canvas(group) == pytest.approx(starting_group_x, abs=0.1)
        assert int(second.property("horizontalAlignment")) == int(Qt.AlignmentFlag.AlignLeft)
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        qt_app.processEvents()

@pytest.mark.qt
def test_reversed_custom_pulse_can_trim_only_real_leading_gutter_without_shrinking_children(qt_app) -> None:
    """The operator's flipped/independently moved artwork and field-row case.

    An authored-width floor must not block a left-edge trim if the left lane is
    actually empty. The retained family reports only that measured clearance;
    layout targets preserve their authored footprints while the card contracts.
    """
    model = _model()
    model.activate()
    model.on_achievement_presentation(
        AchievementPulsePreparedPresentation(
            model=build_mock_steam_view_model("achievement_pulse")
        ), animate=False,
    )
    base_width = float(model.baseAuthoredWidth)
    base_height = float(model.baseAuthoredHeight)
    assert model.set_custom_child_geometry({
        "header": {"alignment": "right"},
        "artwork": {"x_offset": -0.518148},
        "field_group": {"x_offset": -0.229815},
    })
    engine, component, item = _create_qml_item(model)
    try:
        qt_app.processEvents()
        allowance = float(item.property("customLeadingTrimAllowance"))
        assert 20.0 < allowance < base_width / 2.0
        art = _find_visual_item(item, "achievementArtworkFrame")
        fields = _find_visual_item(item, "achievementFieldGroup")
        header = _find_visual_item(item, "achievementHeaderFrame")
        title = _find_visual_item(item, "achievementGameTitle")
        assert all(part is not None for part in (art, fields, header, title))
        sizes = [(part.width(), part.height()) for part in (art, fields, header, title)]
        old_art_x = art.mapToItem(item, 0, 0).x()
        trim = int(allowance * 0.70)
        assert model.set_content_extent(base_width - trim, base_height)
        item.setWidth(model.authoredWidth)
        qt_app.processEvents()
        assert model.authoredWidth == pytest.approx(base_width - trim)
        assert item.property("leadingTrim") == pytest.approx(trim)
        assert art.mapToItem(item, 0, 0).x() == pytest.approx(old_art_x - trim, abs=0.1)
        for part, size in zip((art, fields, header, title), sizes):
            assert (part.width(), part.height()) == pytest.approx(size, abs=0.1)
            bounds = part.mapRectToItem(item, part.boundingRect())
            assert bounds.left() >= -0.2, (part.objectName(), bounds)
            assert bounds.right() <= item.width() + 0.2, (part.objectName(), bounds)
        assert float(item.property("customLeadingTrimAllowance")) == pytest.approx(allowance, abs=0.1)
        assert model.clear_content_extent()
        item.setWidth(model.authoredWidth)
        qt_app.processEvents()
        assert art.mapToItem(item, 0, 0).x() == pytest.approx(old_art_x, abs=0.1)
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        qt_app.processEvents()

@pytest.mark.qt
def test_pulse_trimmed_extent_rehydrates_only_after_header_flip_and_unflipped_floor(qt_app) -> None:
    """A narrow saved CUSTOM box is valid only with its matching flip record."""
    base = _model()
    width, height = base.baseAuthoredWidth, base.baseAuthoredHeight
    assert base.set_content_extent(width - 35, height)
    assert base.authoredWidth == pytest.approx(width)
    assert base.set_custom_child_geometry({"header": {"alignment": "right"}})
    assert base.set_content_extent(width - 35, height)
    assert base.authoredWidth == pytest.approx(width - 35)
    # Use the production retained-payload handler, not hand-applied model calls.
    from rendering.quick.widgets.achievement_pulse import RetainedAchievementPulsePresentation
    rebound = _model()
    carrier = object.__new__(RetainedAchievementPulsePresentation)
    carrier._model = rebound
    carrier._apply_custom_layout_size_payload({
        "child_geometry": {"header": {"alignment": "right"}},
        "content_extent": [width - 35, height],
    })
    assert rebound.customHeaderAlignment == "right"
    assert rebound.authoredWidth == pytest.approx(width - 35)
    carrier._apply_custom_layout_size_payload({
        "child_geometry": {}, "content_extent": [width - 35, height],
    })
    assert rebound.customHeaderAlignment != "right"
    assert rebound.authoredWidth == pytest.approx(width)
