from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QSignalSpy

from rendering.quick.widgets.abandonment_issues import (
    AbandonmentIssuesPresentationConfig,
    AbandonmentIssuesPresentationModel,
    AbandonmentIssuesPresentationStyle,
)
from widgets.steam_abandonment_preparation import AbandonmentPreparedPresentation
from widgets.steam_card_models import build_mock_steam_view_model


pytestmark = pytest.mark.usefixtures("qt_app")


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


def _config(**changes) -> AbandonmentIssuesPresentationConfig:
    return replace(AbandonmentIssuesPresentationConfig(), **changes)


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
    assert style.card_style.shadow_offset_x < 0
    assert style.card_style.shadow_offset_y < 0
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

    assert model.request_manual_refresh() is False
    assert model.on_abandonment_rotation_due() is False
    model.activate(object())
    assert model.request_manual_refresh() is False
    model.set_interaction_enabled(True)
    assert model.request_manual_refresh() is True
    assert model.on_abandonment_rotation_due() is True
    model.notify_fade_complete()

    assert service.refresh_calls == 1
    assert service.rotation_calls == 1
    assert service.fade_complete_calls == 1
