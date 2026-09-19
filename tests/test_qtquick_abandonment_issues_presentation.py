from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from core.settings.default_contract import require_canonical_default
from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QImage
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QSignalSpy, QTest

from rendering.quick.widgets.abandonment_issues import (
    AbandonmentIssuesPresentationConfig,
    AbandonmentIssuesPresentationModel,
    AbandonmentIssuesPresentationStyle,
    RetainedAbandonmentIssuesPresentation,
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
from widgets.steam_abandonment_preparation import AbandonmentPreparedPresentation
from widgets.steam_card_models import build_mock_steam_view_model


pytestmark = pytest.mark.usefixtures("qt_app")

QML_ROOT = Path(__file__).resolve().parents[1] / "rendering" / "quick" / "qml"


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


def _config(**changes) -> AbandonmentIssuesPresentationConfig:
    return replace(AbandonmentIssuesPresentationConfig.from_widgets_mapping({}), **changes)


def _model(
    *,
    config: AbandonmentIssuesPresentationConfig | None = None,
    runtime_service=None,
) -> AbandonmentIssuesPresentationModel:
    resolved_config = config or _config()
    return AbandonmentIssuesPresentationModel(
        resolved_config,
        AbandonmentIssuesPresentationStyle.project(
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


def _presentation(path, *, title: str = "Outer Wilds"):
    return AbandonmentPreparedPresentation(
        model=replace(
            build_mock_steam_view_model("abandonment_issues"),
            appid=753640,
            title=title,
        ),
        artwork=_image(path),
        artwork_identity=str(path),
        desaturation_bucket=40,
    )


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
        self.rotation_calls = 0
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

    def request_cache_rotation(self) -> bool:
        self.rotation_calls += 1
        return True

    def on_presentation_fade_complete(self) -> None:
        self.fade_complete_calls += 1


class _QueuedRuntimeManager:
    def __init__(self) -> None:
        self.tasks = []
        self.timers = []

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

    def schedule_recurring(self, interval_ms, callback, *, description=None):
        del description
        timer = QTimer()
        timer.setInterval(int(interval_ms))
        timer.timeout.connect(callback)
        timer.start()
        self.timers.append(timer)
        return timer


def _find_visual_item(root: QQuickItem, object_name: str) -> QQuickItem | None:
    if root.objectName() == object_name:
        return root
    for child in root.childItems():
        found = _find_visual_item(child, object_name)
        if found is not None:
            return found
    return None


def _create_qml_item(model: AbandonmentIssuesPresentationModel):
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(
        engine,
        QUrl.fromLocalFile(str(QML_ROOT / "AbandonmentIssuesPresentation.qml")),
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    item = component.createWithInitialProperties({"abandonmentModel": model})
    assert isinstance(item, QQuickItem), [
        error.toString() for error in component.errors()
    ]
    item.setWidth(model.authoredWidth)
    item.setHeight(model.authoredHeight)
    return engine, component, item


def test_config_projects_current_selection_shelves_artwork_and_shared_cadence() -> None:
    config = AbandonmentIssuesPresentationConfig.from_widgets_mapping(
        {
            "steam": {
                "refresh_minutes": 33,
                "show_connection_info_icon": False,
            },
            "abandonment_issues": {
                "font_family": "Aptos",
                "font_size": 19,
                "color": [1, 2, 3, 204],
                "selection_mode": "pinned",
                "pinned_appid": 753640,
                "minimum_playtime_minutes": 45,
                "preferred_max_playtime_hours": 6,
                "preferred_max_unlocked_achievements": 8,
                "minimum_inactivity_weeks": 20,
                "preferred_minimum_inactivity_weeks": 40,
                "never_show_appids": [10, "20", 10, -1],
                "show_artwork": True,
                "artwork_shape": "square",
                "artwork_size": 180,
                "accent_color": [12, 34, 56, 78],
                "guilt_desaturater": True,
                "guilt_desaturation_strength": 75,
                "show_rediscovery_message": False,
                "show_source": True,
                "show_achievements": False,
            },
        }
    )

    assert config.font_family == "Aptos"
    assert config.font_size == 19
    assert config.text_color == (1, 2, 3, 204)
    assert config.artwork_shape == "portrait"
    assert config.artwork_size == 180
    assert config.accent_color == (12, 34, 56, 78)
    assert dict(config.field_visibility)["source"] is True
    assert dict(config.field_visibility)["achievements"] is False
    assert config.never_show_appids == (10, 20)
    assert config.authored_size[0] == 600.0
    runtime = config.runtime_config
    assert runtime.selection.mode == "pinned"
    assert runtime.selection.pinned_appid == 753640
    assert runtime.selection.preferred_max_playtime_minutes == 360
    assert runtime.selection.minimum_inactivity_days == 140
    assert runtime.refresh_minutes == 33
    assert runtime.show_connection_info_icon is False
    assert runtime.show_rediscovery_message is False


def test_style_uses_shared_steam_card_projection_without_changing_shelf_style() -> None:
    style = AbandonmentIssuesPresentationStyle.project(
        _config(),
        _shadow_values(direction="NW", frame_extra_offset=2, text_extra_offset=1),
        border_width=3,
    )

    assert style.card_style.border_width == 3
    assert style.card_style.shadow_offset_x == -4.0
    assert style.card_style.shadow_offset_y == -4.0
    assert style.card_style.shadow_extend_left == 2.0
    assert style.card_style.shadow_extend_top == 2.0
    assert style.card_style.shadow_extend_right == 0.0
    assert style.card_style.shadow_extend_bottom == 0.0
    assert style.text_shadow_offset_x < 0
    assert style.text_shadow_offset_y < 0


def test_model_is_inert_until_activation_and_retires_external_runtime() -> None:
    service = _RuntimeService()
    model = _model(runtime_service=service)

    assert service.configs == []
    assert service.attached == []
    assert model.activate(object()) is True
    assert service.configs == [model.config.runtime_config]
    assert service.attached == [model]
    assert service.start_args == [True]

    model.retire()
    assert service.stop_calls == 1
    assert service.detached == [model]
    assert model.field_model.rows == ()


def test_accepted_presentation_keeps_model_and_field_identity_stable(tmp_path) -> None:
    model = _model()
    assert model.activate() is True
    field_model = model.field_model
    spy = QSignalSpy(model.stateChanged)
    presentation = _presentation(tmp_path / "abandonment.png")

    model.on_abandonment_presentation(presentation, animate=False)

    assert model.field_model is field_model
    assert model.title == "Outer Wilds"
    assert model.appid == 753640
    assert model.artworkIdentity == str(tmp_path / "abandonment.png")
    assert model.artworkSource.startswith("file:")
    assert model.desaturationBucket == 40
    assert field_model.rowCount() == len(
        tuple(field for field in presentation.model.fields if field.enabled)
    )
    assert spy.count() == 1

    model.on_abandonment_presentation(presentation, animate=False)
    assert spy.count() == 1


def test_unavailable_presentation_stays_literal_and_does_not_invent_artwork() -> None:
    model = _model()
    model.activate()
    unavailable = AbandonmentPreparedPresentation(
        model=replace(
            build_mock_steam_view_model("abandonment_issues"),
            appid=None,
            title="Rediscovery Shelf",
            subtitle="Previous play history is unavailable.",
            metric_label="History",
            metric_value="Unavailable",
            state="unavailable",
        ),
        artwork=QImage(),
        artwork_identity="",
        desaturation_bucket=0,
    )

    model.on_abandonment_presentation(unavailable, animate=False)

    assert model.viewState == "unavailable"
    assert model.title == "Rediscovery Shelf"
    assert model.metricValue == "Unavailable"
    assert model.artworkSource == ""
    assert model.artworkIdentity == ""


def test_animated_acceptance_defers_state_and_semantic_actions_until_commit(
    tmp_path,
) -> None:
    service = _RuntimeService()
    model = _model(runtime_service=service)
    model.activate(object())
    model.set_interaction_enabled(True)
    transition_spy = QSignalSpy(model.contentTransitionRequested)
    presentation = _presentation(
        tmp_path / "rotation.png",
        title="Disco Elysium",
    )

    model.on_abandonment_presentation(presentation, animate=True)

    assert model.title == ""
    assert model.has_pending_transition is True
    assert transition_spy.count() == 1
    assert model.request_manual_refresh() is True
    assert model.on_abandonment_rotation_due() is True
    assert service.refresh_calls == 0
    assert service.rotation_calls == 0

    assert model.commitPendingPresentation() is True
    assert model.title == "Disco Elysium"
    assert model.has_pending_transition is False
    assert service.refresh_calls == 1
    assert service.rotation_calls == 1
    assert model.commitPendingPresentation() is False


def test_actions_are_capability_gated_and_fade_completion_stays_runtime_owned() -> None:
    service = _RuntimeService()
    model = _model(runtime_service=service)
    state_spy = QSignalSpy(model.stateChanged)

    assert model.request_manual_refresh() is False
    assert model.on_abandonment_rotation_due() is False
    model.activate(object())
    assert model.request_manual_refresh() is False
    assert model.set_interaction_enabled(True) is True
    assert state_spy.count() == 1
    assert model.request_manual_refresh() is True
    assert model.on_abandonment_rotation_due() is True
    model.notify_fade_complete()

    assert service.refresh_calls == 1
    assert service.rotation_calls == 1
    assert service.fade_complete_calls == 1


def test_qml_preserves_archive_shelf_age_stamp_and_two_column_ledger(tmp_path) -> None:
    model = _model()
    model.activate()
    model.on_abandonment_presentation(
        _presentation(tmp_path / "archive.png"),
        animate=False,
    )
    engine, component, item = _create_qml_item(model)
    try:
        archive_tab = _find_visual_item(item, "abandonmentArchiveTab")
        artwork = _find_visual_item(item, "abandonmentArtworkFrame")
        age_stamp = _find_visual_item(item, "abandonmentAgeStamp")
        first = _find_visual_item(item, "abandonmentLedgerShelf_playtime")
        second = _find_visual_item(item, "abandonmentLedgerShelf_recent")
        third = _find_visual_item(item, "abandonmentLedgerShelf_confidence")

        assert archive_tab is not None
        assert artwork is not None
        assert age_stamp is not None
        assert first is not None
        assert second is not None
        assert third is not None
        assert archive_tab.x() == pytest.approx(447.0)
        assert archive_tab.width() == pytest.approx(135.0)
        assert artwork.width() == pytest.approx(140.0)
        assert artwork.height() == pytest.approx(196.0)
        assert age_stamp.x() == pytest.approx(186.0)
        assert first.y() == pytest.approx(second.y())
        assert first.x() < second.x()
        assert third.y() > first.y()
    finally:
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()


def test_custom_content_extent_reflows_archive_right_rail_without_rebasing_dense_children(qt_app, tmp_path) -> None:
    model = _model()
    model.activate()
    model.on_abandonment_presentation(
        _presentation(tmp_path / "content-extent.png"),
        animate=False,
    )
    base_width = float(model.baseAuthoredWidth)
    base_height = float(model.baseAuthoredHeight)
    engine, component, item = _create_qml_item(model)
    try:
        qt_app.processEvents()
        archive_tab = _find_visual_item(item, "abandonmentArchiveTab")
        age_stamp = _find_visual_item(item, "abandonmentAgeStamp")
        ledger_group = _find_visual_item(item, "abandonmentLedgerGroup")
        assert archive_tab is not None and age_stamp is not None and ledger_group is not None
        base_tab_x = archive_tab.x()
        base_age_y = age_stamp.y()
        base_age_width = age_stamp.width()
        base_ledger_y = ledger_group.y()

        assert model.set_content_extent(base_width + 200.0, base_height + 100.0) is True
        item.setWidth(model.authoredWidth)
        item.setHeight(model.authoredHeight)
        qt_app.processEvents()

        assert model.contentExtentActive is True
        assert archive_tab.x() == pytest.approx(base_tab_x + 200.0)
        # Parent content extent may move a family-authored edge rail such as
        # BACKLOG, but it must not become a new placement baseline for dense
        # child roles. Otherwise child-driven containment can feed back into the
        # same child's position and amplify outer growth.
        assert age_stamp.y() == pytest.approx(base_age_y)
        assert age_stamp.width() >= base_age_width
        assert ledger_group.y() == pytest.approx(base_ledger_y)

        assert model.clear_content_extent() is True
        item.setWidth(model.authoredWidth)
        item.setHeight(model.authoredHeight)
        qt_app.processEvents()
        assert model.contentExtentActive is False
        assert archive_tab.x() == pytest.approx(base_tab_x)
        assert age_stamp.y() == pytest.approx(base_age_y)
        assert ledger_group.y() == pytest.approx(base_ledger_y)
    finally:
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()



def test_detached_backlog_stays_put_when_parent_width_reclaims_space(qt_app, tmp_path) -> None:
    """Free placement must outlive later parent right-edge reflow.

    BACKLOG is authored against the parent's right rail while on-rail, but once
    the user actually moves it the retained X position belongs to child_geometry.
    Shrinking the parent from the right should therefore close empty space, not
    keep dragging the detached child left until it escapes containment.
    """

    model = _model()
    model.activate()
    model.on_abandonment_presentation(
        _presentation(tmp_path / "backlog-detached-parent-reflow.png"),
        animate=False,
    )
    base_width = float(model.baseAuthoredWidth)
    base_height = float(model.baseAuthoredHeight)
    engine, component, item = _create_qml_item(model)
    try:
        qt_app.processEvents()
        backlog = _find_visual_item(item, "abandonmentArchiveTab")
        assert backlog is not None
        base_x = backlog.x()

        assert model.set_content_extent(base_width + 200.0, base_height) is True
        item.setWidth(model.authoredWidth)
        item.setHeight(model.authoredHeight)
        qt_app.processEvents()

        assert backlog.x() == pytest.approx(base_x + 200.0)
        assert backlog.property("customEditPlacementCompensationX") == pytest.approx(200.0)

        # Simulate the shared owner's first-real-move fold: the live +200 px
        # authored-rail displacement becomes part of the stable normalized offset,
        # then the user moves the role 100 px left.
        moved_offset = 100.0 / base_width
        assert model.set_custom_child_geometry(
            {"backlog_block": {"x_offset": moved_offset}}
        ) is True
        qt_app.processEvents()
        moved_x = backlog.x()
        assert moved_x == pytest.approx(base_x + 100.0)
        assert backlog.property("customEditPlacementCompensationX") == pytest.approx(0.0)

        # Reclaim parent width down to the already-admitted child floor. The
        # presentation model is deliberately not the resize-admission authority:
        # the shared owner clamps a real parent-side gesture to the live child
        # containment floor before publishing content_extent. This presentation
        # test therefore supplies a legal admitted width and proves that the
        # detached BACKLOG stays put while the parent closes empty space around it.
        minimum_containing_width = moved_x + backlog.width()
        assert minimum_containing_width < base_width + 200.0
        assert model.set_content_extent(minimum_containing_width, base_height) is True
        item.setWidth(model.authoredWidth)
        item.setHeight(model.authoredHeight)
        qt_app.processEvents()
        assert backlog.x() == pytest.approx(moved_x)
        assert backlog.x() >= 0.0
        assert backlog.x() + backlog.width() <= model.authoredWidth + 1.0e-6
    finally:
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()

def test_custom_child_geometry_projects_dense_roles_without_distorting_artwork(qt_app, tmp_path) -> None:
    model = _model()
    model.activate()
    model.on_abandonment_presentation(
        _presentation(tmp_path / "child-geometry.png"),
        animate=False,
    )
    engine, component, item = _create_qml_item(model)
    try:
        qt_app.processEvents()
        artwork = _find_visual_item(item, "abandonmentArtworkFrame")
        backlog = _find_visual_item(item, "abandonmentArchiveTab")
        title = _find_visual_item(item, "abandonmentGameTitle")
        last_visit = _find_visual_item(item, "abandonmentAgeStamp")
        shelves = _find_visual_item(item, "abandonmentLedgerGroup")
        first = _find_visual_item(item, "abandonmentLedgerShelf_playtime")
        second = _find_visual_item(item, "abandonmentLedgerShelf_recent")
        assert all(value is not None for value in (artwork, backlog, title, last_visit, shelves, first, second))

        base_art = (artwork.width(), artwork.height())
        base_backlog_h = backlog.height()
        base_title_h = title.height()
        base_last_y = last_visit.y()
        base_shelf_y = shelves.y()
        base_first = (first.width(), first.height())
        base_second = (second.width(), second.height())

        assert model.set_custom_child_geometry(
            {
                "artwork": {"width_scale": 1.40, "height_scale": 0.70},
                "backlog_block": {"width_scale": 1.10, "height_scale": 1.50},
                "game_name": {"width_scale": 1.25, "height_scale": 1.40},
                "last_visit": {"width_scale": 1.15, "height_scale": 1.20},
                "shelf_group": {"width_scale": 1.30, "height_scale": 1.35},
            }
        ) is True
        qt_app.processEvents()

        assert artwork.width() == pytest.approx(base_art[0] * 1.40)
        assert artwork.height() == pytest.approx(base_art[1] * 0.70)
        assert backlog.height() == pytest.approx(base_backlog_h * 1.50)
        assert title.height() == pytest.approx(base_title_h * 1.40)
        assert last_visit.y() > base_last_y
        assert first.width() == pytest.approx(base_first[0] * 1.30)
        assert second.width() == pytest.approx(base_second[0] * 1.30)
        assert first.height() == pytest.approx(base_first[1] * 1.35)
        assert second.height() == pytest.approx(base_second[1] * 1.35)

        grown_last_y = last_visit.y()
        grown_shelf_y = shelves.y()
        assert model.set_custom_child_geometry(
            {
                "artwork": {"width_scale": 0.75, "height_scale": 0.80},
                "backlog_block": {"width_scale": 0.85, "height_scale": 0.75},
                "game_name": {"width_scale": 0.90, "height_scale": 0.70},
                "last_visit": {"width_scale": 0.90, "height_scale": 0.75},
                "shelf_group": {"width_scale": 0.90, "height_scale": 0.80},
            }
        ) is True
        qt_app.processEvents()

        # Dense child blocks reflow in both directions while the shared outer
        # content_extent owner remains grow-only. Shrinking a child therefore
        # reclaims internal space instead of leaving an ever-growing void.
        assert last_visit.y() < base_last_y
        assert shelves.y() < base_shelf_y
        assert last_visit.y() < grown_last_y
        assert shelves.y() < grown_shelf_y

        qml = (QML_ROOT / "AbandonmentIssuesPresentation.qml").read_text(encoding="utf-8")
        assert "fillMode: Image.PreserveAspectCrop" in qml
        assert '"roleId": "shelf_group"' in qml
        assert '"target": ledgerGroupFrame' in qml
    finally:
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()


def test_custom_child_placement_detaches_moved_role_from_authored_reflow_rail(qt_app, tmp_path) -> None:
    model = _model()
    model.activate()
    model.on_abandonment_presentation(
        _presentation(tmp_path / "child-placement.png"),
        animate=False,
    )
    engine, component, item = _create_qml_item(model)
    try:
        qt_app.processEvents()
        backlog = _find_visual_item(item, "abandonmentArchiveTab")
        artwork = _find_visual_item(item, "abandonmentArtworkFrame")
        title = _find_visual_item(item, "abandonmentGameTitle")
        flavour = _find_visual_item(item, "abandonmentRediscoveryText")
        last_visit = _find_visual_item(item, "abandonmentAgeStamp")
        shelves = _find_visual_item(item, "abandonmentLedgerGroup")
        assert all(
            value is not None
            for value in (backlog, artwork, title, flavour, last_visit, shelves)
        )

        base_backlog = (backlog.x(), backlog.y())
        base_downstream_y = (
            artwork.y(), title.y(), flavour.y(), last_visit.y(), shelves.y()
        )

        # Once BACKLOG has an explicit placement displacement, it has left the
        # authored rail. Enlarging it must not silently move unrelated siblings;
        # Edit-time collision admission is responsible for keeping them apart.
        assert model.set_custom_child_geometry(
            {
                "backlog_block": {
                    "width_scale": 1.10,
                    "height_scale": 1.50,
                    "x_offset": -0.08,
                    "y_offset": 0.07,
                }
            }
        ) is True
        qt_app.processEvents()

        assert backlog.x() == pytest.approx(
            base_backlog[0] - 0.08 * model.baseAuthoredWidth
        )
        assert backlog.y() == pytest.approx(
            base_backlog[1] + 0.07 * model.baseAuthoredHeight
        )
        assert (artwork.y(), title.y(), flavour.y(), last_visit.y(), shelves.y()) == pytest.approx(
            base_downstream_y
        )

        # Returning the role to its authored placement re-enables the family's
        # signed rail reflow for the same size override.
        assert model.set_custom_child_geometry(
            {
                "backlog_block": {
                    "width_scale": 1.10,
                    "height_scale": 1.50,
                }
            }
        ) is True
        qt_app.processEvents()
        assert title.y() > base_downstream_y[1]
        assert flavour.y() > base_downstream_y[2]
        assert last_visit.y() > base_downstream_y[3]
        assert shelves.y() > base_downstream_y[4]
    finally:
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()


def test_qml_keeps_delegates_stable_across_same_shape_model_updates(tmp_path) -> None:
    model = _model()
    model.activate()
    model.on_abandonment_presentation(
        _presentation(tmp_path / "first.png"),
        animate=False,
    )
    engine, component, item = _create_qml_item(model)
    try:
        first = _find_visual_item(item, "abandonmentLedgerShelf_playtime")
        assert first is not None
        model.on_abandonment_presentation(
            _presentation(tmp_path / "second.png", title="Return of the Obra Dinn"),
            animate=False,
        )
        second = _find_visual_item(item, "abandonmentLedgerShelf_playtime")

        assert second is first
        assert _find_visual_item(item, "abandonmentGameTitle") is not None
    finally:
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()


def test_qml_no_artwork_variant_reclaims_the_archive_text_rail(tmp_path) -> None:
    model = _model(config=_config(show_artwork=False, artwork_shape="wide"))
    model.activate()
    model.on_abandonment_presentation(
        _presentation(tmp_path / "hidden.png"),
        animate=False,
    )
    engine, component, item = _create_qml_item(model)
    try:
        shelf = _find_visual_item(item, "abandonmentArtworkShelf")
        title = _find_visual_item(item, "abandonmentGameTitle")
        age_stamp = _find_visual_item(item, "abandonmentAgeStamp")

        assert shelf is not None
        assert shelf.isVisible() is False
        assert title is not None
        assert age_stamp is not None
        assert title.x() == pytest.approx(24.0)
        assert title.width() == pytest.approx(554.0)
        assert age_stamp.x() == pytest.approx(24.0)
    finally:
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()


def test_qml_connect_state_keeps_header_and_archive_tab_but_hides_card_shelves() -> None:
    model = _model()
    model.activate()
    engine, component, item = _create_qml_item(model)
    try:
        header = _find_visual_item(item, "abandonmentHeaderFrame")
        archive_tab = _find_visual_item(item, "abandonmentArchiveTab")
        normal = _find_visual_item(item, "abandonmentNormalContent")
        connect = _find_visual_item(item, "abandonmentConnectRequired")

        assert header is not None and header.isVisible() is True
        assert archive_tab is not None and archive_tab.isVisible() is True
        assert normal is not None and normal.isVisible() is False
        assert connect is not None and connect.isVisible() is True
        assert model.settingsTarget == "steam_connection"
    finally:
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()


def test_qml_content_transition_commits_pending_runtime_state(qt_app, tmp_path) -> None:
    model = _model()
    model.activate()
    engine, component, item = _create_qml_item(model)
    try:
        model.on_abandonment_presentation(
            _presentation(tmp_path / "transition.png", title="Pentiment"),
            animate=True,
        )
        assert model.title == ""

        for _ in range(20):
            qt_app.processEvents()
            if model.title == "Pentiment":
                break
            QTest.qWait(20)

        assert model.title == "Pentiment"
        assert model.has_pending_transition is False
        archive_content = _find_visual_item(item, "abandonmentArchiveContent")
        assert archive_content is not None
    finally:
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()


def test_static_registry_and_qml_surface_are_provider_inert() -> None:
    qml = (QML_ROOT / "AbandonmentIssuesPresentation.qml").read_text(
        encoding="utf-8"
    )
    for marker in (
        "SettingsManager",
        "SteamBackend",
        "QDesktopServices",
        "QWidget",
        "QPainter",
        "http://",
        "https://",
    ):
        assert marker not in qml
    assert "onDoubleTapped: abandonmentRoot.refreshRequested()" in qml
    assert "abandonmentRoot.settingsRequested(" in qml
    assert "abandonmentLedgerShelf_" in qml
    assert "AchievementCapsule" not in qml
    descriptor = ordinary_widget_family_component("abandonment_issues")
    assert descriptor.qml_filename == "AbandonmentIssuesPresentation.qml"
    assert (
        descriptor.presentation_model_kind
        == "AbandonmentIssuesPresentationModel"
    )
    assert descriptor in ORDINARY_WIDGET_FAMILY_COMPONENTS
    qmldir = (QML_ROOT / "qmldir").read_text(encoding="utf-8")
    assert (
        "AbandonmentIssuesPresentation 1.0 AbandonmentIssuesPresentation.qml"
        in qmldir
    )


@pytest.mark.qt
def test_real_manager_owner_and_scene_host_keep_one_retained_runtime_chain(
    qt_app,
    tmp_path,
) -> None:
    class _Host:
        @staticmethod
        def get_runtime_widget_registry():
            return {}

    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=82,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    runtime_owner = WidgetRuntimeManager(_Host())
    manager = _QueuedRuntimeManager()
    config = _config()
    model = AbandonmentIssuesPresentationModel(
        config,
        AbandonmentIssuesPresentationStyle.project(config, _shadow_values()),
        parent=window,
    )
    service = runtime_owner.ensure_widget_service(
        "abandonment_issues",
        model,
        {
            "steam": {"refresh_minutes": 10},
            "abandonment_issues": {"enabled": True},
        },
    )
    assert service is not None
    assert model._runtime_service is service
    assert service.is_running() is False
    assert (
        runtime_owner.get_reusable_widget_service(
            "abandonment_issues",
            model,
        )
        is service
    )

    settings_requests = []
    steam_actions = []
    retained = None
    try:
        retained = RetainedAbandonmentIssuesPresentation(
            host=controller.ordinary_widget_host,
            model=model,
            geometry=OverlayWidgetGeometry(25.0, 30.0, 600.0, 331.0),
            on_settings_requested=lambda target: settings_requests.append(target)
            or True,
            on_steam_action_requested=lambda kind, target: steam_actions.append(
                (kind, target)
            )
            or True,
        )
        item = retained.item
        engine = QQmlEngine.contextForObject(item).engine()
        field_model = model.field_model
        assert item.property("fadeOpacity") == pytest.approx(0.0)

        retained._apply_custom_layout_size_payload(
            {
                "content_extent": [config.authored_size[0] + 120.0, config.authored_size[1] + 80.0],
                "child_geometry": {
                    "artwork": {"width_scale": 1.30, "height_scale": 0.75},
                    "backlog_block": {"width_scale": 1.10, "height_scale": 1.25},
                    "game_name": {"width_scale": 1.20, "height_scale": 1.35},
                    "last_visit": {"width_scale": 0.80, "height_scale": 1.15},
                    "shelf_group": {"width_scale": 1.25, "height_scale": 1.40},
                },
            }
        )
        assert model.contentExtentActive is True
        assert model.authoredWidth == pytest.approx(config.authored_size[0] + 120.0)
        assert model.customArtworkWidthScale == pytest.approx(1.30)
        assert model.customArtworkHeightScale == pytest.approx(0.75)
        assert model.customBacklogHeightScale == pytest.approx(1.25)
        assert model.customGameNameHeightScale == pytest.approx(1.35)
        assert model.customLastVisitWidthScale == pytest.approx(0.80)
        assert model.customShelfGroupHeightScale == pytest.approx(1.40)
        retained._apply_custom_layout_size_payload({})
        assert model.contentExtentActive is False
        assert model.customArtworkWidthScale == pytest.approx(1.0)
        assert model.customBacklogWidthScale == pytest.approx(1.0)
        assert model.customGameNameHeightScale == pytest.approx(1.0)
        assert model.customLastVisitHeightScale == pytest.approx(1.0)
        assert model.customShelfGroupWidthScale == pytest.approx(1.0)

        assert retained.activate(manager) is True
        qt_app.processEvents()
        assert service.runtime_generation == 82
        assert service.is_running() is True
        assert [task["category"] for task in manager.tasks] == [
            "steam_abandonment_cache_load"
        ]

        service._deliver_presentation(
            _presentation(tmp_path / "owner.png"),
            animate=False,
        )
        qt_app.processEvents()
        first_field = _find_visual_item(
            item,
            "abandonmentLedgerShelf_playtime",
        )
        assert first_field is not None

        retained.apply_input_state(
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
            "steam_abandonment_cache_load",
            "steam_abandonment_refresh",
        ]

        # The queued cache task deliberately remains unexecuted in this owner
        # test; admit the same metadata/due-time state that its commit supplies
        # so fade completion can prove the single runtime-owned rotation timer.
        service._activation_has_metadata = True
        service._activation_rotation_due_seconds = 60.0
        service._request_consumer_fade()
        qt_app.processEvents()
        assert item.property("fadeOpacity") == pytest.approx(1.0)
        assert service.rotation_timer is not None
        assert retained.item is item
        assert retained.model is model
        assert model.field_model is field_model
        assert QQmlEngine.contextForObject(item).engine() is engine
        assert (
            _find_visual_item(item, "abandonmentLedgerShelf_playtime")
            is first_field
        )
    finally:
        controller.quiesce_for_retirement()
        runtime_owner.cleanup()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()

    assert retained is not None
    assert service.is_retired() is True


def test_backlog_child_requirement_does_not_count_live_parent_rail_twice(qt_app, tmp_path) -> None:
    """Parent-only X expansion may move BACKLOG but not grow its child floor."""
    model = _model()
    model.activate()
    model.on_abandonment_presentation(
        _presentation(tmp_path / "backlog-requirement.png"), animate=False,
    )
    engine, component, item = _create_qml_item(model)
    try:
        qt_app.processEvents()
        from PySide6.QtQml import QJSValue
        target = item.property("customEditableChildRequirementTarget")
        if isinstance(target, QJSValue):
            target = target.toQObject()
        assert target is not None
        baseline_right = float(target.property("backlogRight"))
        baseline_floor = float(target.property("requiredContentWidth"))
        width, height = float(model.baseAuthoredWidth), float(model.baseAuthoredHeight)
        for extra in (90.0, 220.0, 310.0):
            assert model.set_content_extent(width + extra, height)
            item.setWidth(model.authoredWidth)
            item.setHeight(model.authoredHeight)
            qt_app.processEvents()
            assert float(target.property("backlogRight")) == pytest.approx(baseline_right)
            assert float(target.property("requiredContentWidth")) == pytest.approx(baseline_floor)
    finally:
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()


@pytest.mark.qt
def test_semantic_header_flip_exchanges_abandonment_rails_without_mirroring_artwork(qt_app, tmp_path) -> None:
    """BACKLOG and artwork/text regions trade sides, but content does not flip.

    Relocated right-rail artwork can follow parent growth in its PAINT
    coordinates; that movement must not manufacture further parent growth.
    """
    model = _model()
    model.activate()
    model.on_abandonment_presentation(
        _presentation(tmp_path / "semantic-flip.png"), animate=False,
    )
    engine, component, item = _create_qml_item(model)
    try:
        qt_app.processEvents()
        find = lambda name: _find_visual_item(item, name)
        canvas = find("abandonmentAuthoredCanvas")
        art = find("abandonmentArtworkFrame")
        image = find("abandonmentArtworkImage")
        title = find("abandonmentGameTitle")
        flavour = find("abandonmentRediscoveryText")
        age = find("abandonmentAgeStamp")
        shelves = find("abandonmentLedgerGroup")
        backlog = find("abandonmentArchiveTab")
        assert all(obj is not None for obj in
                   (canvas, art, image, title, flavour, age, shelves, backlog))
        def pos(obj):
            return obj.mapToItem(canvas, 0.0, 0.0).x()
        text_roles = (title, flavour, age, shelves)
        original_text = tuple(pos(obj) for obj in text_roles)
        original_art = pos(art)
        original_backlog = pos(backlog)
        art_fill = image.property("fillMode")
        title_align = title.property("horizontalAlignment")
        base_width = float(model.baseAuthoredWidth)
        base_height = float(model.baseAuthoredHeight)
        assert original_art < original_text[0] < original_backlog

        assert model.set_custom_child_geometry({"header": {"alignment": "right"}})
        qt_app.processEvents()
        assert bool(item.property("headerFlipped"))
        flipped_text_x = float(item.property("flippedTextX"))
        for obj in text_roles:
            assert pos(obj) == pytest.approx(flipped_text_x, abs=1.5)
        assert pos(art) == pytest.approx(
            float(item.property("flippedArtworkX")) + art.x(), abs=1.5
        )
        assert pos(backlog) < pos(title) < pos(art)
        assert image.property("fillMode") == art_fill
        assert title.property("horizontalAlignment") == title_align
        req = item.property("customEditableChildRequirementTarget")
        from PySide6.QtQml import QJSValue
        if isinstance(req, QJSValue):
            req = req.toQObject()
        assert req is not None
        required_before = float(req.property("requiredContentWidth"))
        art_before = pos(art)
        backlog_before = pos(backlog)
        assert model.set_content_extent(base_width + 120.0, base_height)
        item.setWidth(model.authoredWidth)
        item.setHeight(model.authoredHeight)
        qt_app.processEvents()
        assert pos(art) == pytest.approx(art_before + 120.0)
        assert pos(backlog) == pytest.approx(backlog_before)
        assert float(req.property("requiredContentWidth")) == pytest.approx(required_before, abs=1.5)

        assert model.clear_content_extent()
        item.setWidth(model.authoredWidth)
        item.setHeight(model.authoredHeight)
        assert model.set_custom_child_geometry({})
        qt_app.processEvents()
        assert not bool(item.property("headerFlipped"))
        assert tuple(pos(obj) for obj in text_roles) == pytest.approx(original_text)
        assert pos(art) == pytest.approx(original_art)
        assert pos(backlog) == pytest.approx(original_backlog)
    finally:
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
