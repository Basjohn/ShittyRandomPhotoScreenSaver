"""Production owner Save -> live promotion -> retired display -> fresh family/Edit.

External Weather/Steam providers are deliberately absent.  The real Quick
presentations, session owner, committed writer/reader, and generation teardown
are exercised.  The Reddit equivalent is already accepted separately.
"""
from __future__ import annotations

from copy import deepcopy

import pytest
from PySide6.QtCore import QRect
from PySide6.QtQuick import QQuickItem
from shiboken6 import getCppPointer, isValid as is_valid_qobject

from core.settings.default_contract import require_canonical_default
from rendering.custom_child_geometry import normalize_child_geometry, update_child_geometry_payload
from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
from rendering.quick.custom_layout_hydration import (
    apply_quick_committed_payloads, resolve_quick_committed_geometry,
    resolve_quick_committed_variant_state,
)
from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner
from rendering.quick.display_unit import create_quick_display_unit
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.family_binder import (
    AchievementPulseFamilyAdapter, WeatherFamilyAdapter,
)
from rendering.quick.widgets.achievement_pulse import (
    AchievementPulsePresentationConfig, AchievementPulsePresentationModel,
    AchievementPulsePresentationStyle, RetainedAchievementPulsePresentation,
)
from rendering.quick.widgets.weather import (
    WeatherPresentationConfig, WeatherPresentationModel,
    WeatherPresentationStyle, RetainedWeatherPresentation,
)
from rendering.widget_descriptors import get_widget_runtime_descriptor


class _Settings:
    def __init__(self, widgets):
        self.widgets = deepcopy(widgets)
        self.save_calls = 0
        self.update_calls = 0

    def get_widgets_map(self):
        return deepcopy(self.widgets)

    def set_widgets_map(self, widgets, *, emit_change=True):
        self.update_calls += 1
        self.widgets = deepcopy(widgets)

    def save(self):
        self.save_calls += 1


class _CachedWeatherProvider:
    """Test-only cached provider: no network, worker, timer, or runtime polling."""

    def __init__(self):
        self.location = ""
        self.consumer = None
        self.running = False

    def attach_consumer(self, consumer):
        self.consumer = consumer

    def detach_consumer(self, consumer=None):
        if consumer is None or self.consumer is consumer:
            self.consumer = None

    def set_thread_manager(self, manager):
        pass

    def set_location(self, location):
        self.location = str(location)

    def has_cached_data(self):
        return True

    def start(self, *, immediate_refresh_on_miss=False):
        self.running = True
        self.consumer.on_weather_state({
            "location": self.location, "temperature": 22.4,
            "condition": "partly cloudy", "weather_code": 2, "is_day": 1,
            "humidity": 68, "windspeed": 12.6,
            "forecast": "Tomorrow: 19°C, light rain",
            "forecast_days": (
                "Fri: 19°-24°C / Light Rain",
                "Sat: 18°-25°C / Partly Cloudy",
                "Sun: 17°-26°C / Clear Sky",
                "Mon: 16°-23°C / Overcast",
                "Tue: 15°-22°C / Moderate Rain",
            ),
        }, from_cache=True)
        return True

    def stop(self):
        self.running = False

    def is_running(self):
        return self.running


class _OfflineWeatherAdapter(WeatherFamilyAdapter):
    def build(self, *, widget_id, widgets_config, host, geometry, shadow_values, **_kwargs):
        config = WeatherPresentationConfig.from_widgets_mapping(widgets_config)
        style = WeatherPresentationStyle.project(config, shadow_values)
        # No fake QML. Only the external provider is excluded from this gate.
        model = WeatherPresentationModel(config, style)
        # Supply only a cached provider; binder phase 2 remains the sole
        # activation authority, as it is for a real Weather family.
        model.set_runtime_service(_CachedWeatherProvider())
        return RetainedWeatherPresentation(host=host, model=model, geometry=geometry)


class _OfflinePulseAdapter(AchievementPulseFamilyAdapter):
    def build(self, *, widget_id, widgets_config, host, geometry, shadow_values, **_kwargs):
        config = AchievementPulsePresentationConfig.from_widgets_mapping(widgets_config)
        style = AchievementPulsePresentationStyle.project(config, shadow_values)
        model = AchievementPulsePresentationModel(config, style)
        # No provider is required, and binder phase 2 remains the sole activator.
        return RetainedAchievementPulsePresentation(host=host, model=model, geometry=geometry)


def _walk(root: QQuickItem):
    yield root
    for child in root.childItems():
        yield from _walk(child)


def _target(root: QQuickItem, name: str) -> QQuickItem:
    matches = [item for item in _walk(root) if item.objectName() == name]
    assert len(matches) == 1, (name, len(matches))
    return matches[0]


def _mapped_box(item: QQuickItem, root: QQuickItem):
    corners = [item.mapToItem(root, x, y) for x, y in (
        (0.0, 0.0), (item.width(), 0.0),
        (0.0, item.height()), (item.width(), item.height()),
    )]
    left, top = min(p.x() for p in corners), min(p.y() for p in corners)
    return (left, top, max(p.x() for p in corners) - left,
            max(p.y() for p in corners) - top)


@pytest.mark.qt
@pytest.mark.parametrize("family", ("achievement_pulse", "weather"))
def test_other_family_real_owner_save_live_promotion_fresh_generation_and_reedit(
    qt_app, family: str,
) -> None:
    """A second generation must rehydrate the same child and parent geometry read-only."""
    spec = {
        "achievement_pulse": {
            "edit_role": "artwork", "paint_role": "achievementArtworkFrame",
            "activation": "steam", "adapter": _OfflinePulseAdapter,
            "section": {"enabled": True, "position": "Top Left", "monitor": "ALL"},
            "children": {
                "header": {"width_scale": 0.9, "alignment": "right"},
                "artwork": {"width_scale": 0.85, "x_offset": -0.02},
            },
            "target": "achievementArtworkFrame",
        },
        "weather": {
            "edit_role": "location_text", "paint_role": "weatherLocationText",
            "activation": "weather", "adapter": _OfflineWeatherAdapter,
            "section": {"enabled": True, "position": "Top Left", "monitor": "ALL",
                        "location": "Cape Town", "show_five_day_forecast": True},
            "children": {
                "location_text": {"width_scale": 1.12, "x_offset": 0.025},
                "condition_text": {"height_scale": 1.15, "y_offset": 0.015},
            },
            "target": "weatherLocationText",
        },
    }[family]
    old_quit_policy = qt_app.quitOnLastWindowClosed()
    qt_app.setQuitOnLastWindowClosed(False)
    settings = _Settings({
        "family_activation": {spec["activation"]: True},
        family: spec["section"],
    })
    owners, units, factories = [], [], []
    reloads = []

    def generation(widgets, number):
        screen = qt_app.primaryScreen()
        assert screen is not None and is_valid_qobject(screen)
        factory = QuickSceneFactory()
        factories.append(factory)
        unit = create_quick_display_unit(
            screen=screen, screen_index=0, runtime_generation=number,
            scene_factory=factory,
            window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
            ctrl_coordinator=SharedCtrlCoordinator(),
            adapters=(spec["adapter"](),),
        )
        units.append(unit)
        bound_ids = unit.bind_families(
            widgets_config=widgets,
            shadow_values=require_canonical_default("widgets.shadows"),
            # The live RUN always supplies a ThreadManager. An inert token is
            # sufficient here because both external providers are excluded;
            # without it the binder intentionally skips phase-2 activation.
            thread_manager=object(),
            committed_rect_resolver=lambda widget_id: resolve_quick_committed_geometry(
                widgets, screen, widget_id,
            ),
        )
        assert family in bound_ids, (family, bound_ids)
        retained = unit.presenter.presentation_for_widget_id(family)
        assert retained is not None
        # This gate owns Save/promotion/retirement, not provider admission.
        # Offline adapters have deliberately no production Steam/Weather service;
        # explicitly activate their REAL retained-family port, which is
        # idempotent if binder phase 2 already activated it. Do not substitute
        # fabricated model fields, and do not assert binder activation here.
        retained.activate(object())
        assert retained.model.is_active, family
        # Feed the existing cached data through the real Weather model if the
        # binder has not started the offline provider. Avoid an asynchronous
        # external-service readiness assumption in a persistence test.
        if family == "weather" and retained.model.viewState != "ready":
            provider = retained.model._runtime_service
            assert isinstance(provider, _CachedWeatherProvider)
            # If the neutral binder did not run the offline fake's start,
            # attach through that fake's public consumer seam before emitting
            # cached state. No external provider or worker is started here.
            provider.attach_consumer(retained.model)
            assert provider.start(immediate_refresh_on_miss=False)
            assert retained.model.viewState == "ready"
        # Steam supplies test data only after the real family activation.
        if family == "achievement_pulse":
            from widgets.steam_achievement_preparation import AchievementPulsePreparedPresentation
            from widgets.steam_card_models import build_mock_steam_view_model
            retained.model.on_achievement_presentation(
                AchievementPulsePreparedPresentation(
                    model=build_mock_steam_view_model("achievement_pulse")
                ),
                animate=False,
            )
            # The offline adapter intentionally has no Steam service to emit
            # the production fade request. Its retained widget starts at
            # fadeOpacity=0, so a role may exist while *nothing paints*.
            # Exercise the real model -> retained presenter reveal signal;
            # never force the Edit proxy ready for a hidden target.
            retained.model.request_achievement_fade()
            assert retained.item.property("fadeOpacity") == pytest.approx(1.0)
        apply_quick_committed_payloads(unit, widgets)
        presentation = unit.presenter.presentation_for_widget_id(family)
        assert presentation is not None, f"{family}: retained presenter not admitted"
        return unit, presentation, screen

    try:
        unit, initial, screen = generation(settings.widgets, 3250)
        old_root, original_model = initial.item, initial.model
        descriptor = get_widget_runtime_descriptor(family)
        assert descriptor is not None
        sizes = normalize_child_geometry(spec["children"], descriptor.custom_child_roles)
        owner = QuickCustomLayoutOwner(
            settings_manager=settings, participants_provider=lambda: (unit,),
            visualizer_provider=lambda: (None, None), reload_request=reloads.append,
            live_config_commit=lambda _widgets: None,
        )
        owners.append(owner)
        assert owner.start()
        session = owner.session
        assert session is not None
        edit_item = next(v for v in session.items() if v.model_identity == family)
        payload = update_child_geometry_payload(
            edit_item.current_size_payload, descriptor.custom_child_roles, sizes,
        )
        edit_item.current_child_sizes = dict(sizes)
        edited_rect = QRect(edit_item.current_global_rect)
        edited_rect.translate(13, 9)
        edit_item.set_geometry(edited_rect, size_payload=payload)
        session.notify_item_changed(edit_item)
        qt_app.processEvents()
        assert owner.save()
        assert settings.save_calls == 1 and settings.update_calls == 1
        assert reloads == []
        assert unit.presenter.presentation_for_widget_id(family) is initial
        assert initial.item is old_root and initial.model is original_model
        committed = resolve_quick_committed_variant_state(
            settings.widgets, screen, family, geometry_variant="default",
        )
        assert committed is not None
        committed_rect, committed_payload = committed
        assert committed_payload["child_geometry"] == payload["child_geometry"]
        assert old_root.x() == pytest.approx(edited_rect.x() - screen.geometry().x(), abs=1.0)
        assert old_root.y() == pytest.approx(edited_rect.y() - screen.geometry().y(), abs=1.0)
        # The same retained family must carry its painted target after Save.
        qt_app.processEvents()
        before = _mapped_box(_target(old_root, spec["target"]), old_root)
        assert before[2] > 0 and before[3] > 0
        if family == "achievement_pulse":
            assert initial.model.customHeaderAlignment == "right"
            assert initial.model.customArtworkWidthScale == pytest.approx(0.85)
        else:
            assert initial.model.viewState == "ready"
            assert initial.model.customChildGeometry == payload["child_geometry"]
            assert initial.model.extendedForecastAvailable
        saved_widgets = deepcopy(settings.widgets)

        owner.retire()
        unit.retire()
        qt_app.processEvents()
        new_unit, reopened, live_screen = generation(settings.widgets, 3251)
        assert reopened.item is not old_root and reopened.model is not original_model
        after = _mapped_box(_target(reopened.item, spec["target"]), reopened.item)
        assert after == pytest.approx(before, abs=1.0)
        assert reopened.item.x() == pytest.approx(committed_rect.x, abs=1.0)
        assert reopened.item.y() == pytest.approx(committed_rect.y, abs=1.0)
        if family == "achievement_pulse":
            assert reopened.model.customHeaderAlignment == "right"
            assert reopened.model.customArtworkWidthScale == pytest.approx(0.85)
        else:
            assert reopened.model.viewState == "ready"
            assert reopened.model.customChildGeometry == payload["child_geometry"]
            assert reopened.model.extendedForecastAvailable
        assert settings.widgets == saved_widgets
        assert settings.save_calls == 1 and settings.update_calls == 1

        # Open Edit through a new owner, not the retired owner or a cached session.
        reopened_owner = QuickCustomLayoutOwner(
            settings_manager=settings, participants_provider=lambda: (new_unit,),
            visualizer_provider=lambda: (None, None), reload_request=reloads.append,
            live_config_commit=lambda _widgets: None,
        )
        owners.append(reopened_owner)
        assert reopened_owner.start()
        new_session = reopened_owner.session
        assert new_session is not None
        reopened_item = next(v for v in new_session.items() if v.model_identity == family)
        assert reopened_item.current_global_rect == edited_rect
        assert reopened_item.current_child_sizes == sizes
        assert reopened_item.current_size_payload["child_geometry"] == payload["child_geometry"]
        assert reopened_owner.cancel()
        assert _mapped_box(_target(reopened.item, spec["target"]), reopened.item) == pytest.approx(after, abs=1.0)
        assert new_unit.presenter.presentation_for_widget_id(family) is reopened
        assert settings.widgets == saved_widgets
        assert settings.save_calls == 1 and settings.update_calls == 1
        assert reloads == []

        # A second independent CUSTOM transaction must start from the newly
        # committed geometry, not the original family's stale authored/payload
        # projection. Edit another child and move the same retained parent,
        # save again, and reconstruct a THIRD generation from committed data.
        second_owner = QuickCustomLayoutOwner(
            settings_manager=settings, participants_provider=lambda: (new_unit,),
            visualizer_provider=lambda: (None, None), reload_request=reloads.append,
            live_config_commit=lambda _widgets: None,
        )
        owners.append(second_owner)
        assert second_owner.start()
        second_session = second_owner.session
        assert second_session is not None
        second_item = next(v for v in second_session.items() if v.model_identity == family)
        second_children = deepcopy(spec["children"])
        second_role = "artwork" if family == "achievement_pulse" else "location_text"
        second_children[second_role]["x_offset"] = 0.0125
        second_sizes = normalize_child_geometry(second_children, descriptor.custom_child_roles)
        second_payload = update_child_geometry_payload(
            second_item.current_size_payload, descriptor.custom_child_roles, second_sizes,
        )
        second_item.current_child_sizes = dict(second_sizes)
        second_rect = QRect(second_item.current_global_rect)
        second_rect.translate(-7, 5)
        second_item.set_geometry(second_rect, size_payload=second_payload)
        second_session.notify_item_changed(second_item)
        qt_app.processEvents()
        assert second_owner.save()
        assert settings.save_calls == 2 and settings.update_calls == 2
        assert new_unit.presenter.presentation_for_widget_id(family) is reopened
        second_paint = _mapped_box(_target(reopened.item, spec["target"]), reopened.item)
        assert second_paint != pytest.approx(after, abs=0.01)
        second_committed = deepcopy(settings.widgets)
        second_owner.retire()
        new_unit.retire()
        qt_app.processEvents()
        third_unit, third_presentation, third_screen = generation(settings.widgets, 3252)
        assert third_screen is not None and is_valid_qobject(third_screen)
        assert third_presentation is not reopened
        assert third_presentation.model is not original_model
        assert third_presentation.item.x() == pytest.approx(second_rect.x() - third_screen.geometry().x(), abs=1.0)
        assert third_presentation.item.y() == pytest.approx(second_rect.y() - third_screen.geometry().y(), abs=1.0)
        assert _mapped_box(_target(third_presentation.item, spec["target"]), third_presentation.item) == pytest.approx(second_paint, abs=1.0)
        assert settings.widgets == second_committed
        assert settings.save_calls == 2 and settings.update_calls == 2
        assert reloads == []

        # The previous owner gates established committed record and family-paint
        # survival, but never selected the newly restored CHILD EDIT proxy. Reopen
        # on the THIRD real generation: the same retained child must map to the
        # edit rectangle, not merely have a plausible child_geometry dictionary.
        # A native Quick window is required to instantiate the retained Repeater
        # delegates on Qt/Windows; do not bypass a missing delegate by projecting
        # an invented rectangle in Python.
        third_owner = QuickCustomLayoutOwner(
            settings_manager=settings, participants_provider=lambda: (third_unit,),
            visualizer_provider=lambda: (None, None), reload_request=reloads.append,
            live_config_commit=lambda _widgets: None,
        )
        owners.append(third_owner)
        assert third_owner.start()
        third_unit.runtime.window.show()
        qt_app.processEvents()
        painted = _target(third_presentation.item, spec["paint_role"])
        assert painted.isVisible(), (
            family, "real target is not painting after native exposure",
            third_presentation.item.property("fadeOpacity"),
            third_presentation.item.property("startupRevealOpacity"),
            third_presentation.model.viewState,
        )
        # QQuickWindow exposure can finish a family's initially deferred
        # native text/implicit-size layout. Save/reopen above compared two
        # equally *unexposed* generations; selected Edit and Cancel must now
        # preserve the actual exposed paint, not an earlier speculative box.
        exposed_paint = _mapped_box(painted, third_presentation.item)
        assert exposed_paint[2] > 0.0 and exposed_paint[3] > 0.0
        overlay = third_unit.runtime.scene_controller.custom_layout_overlay
        assert overlay.model.selectItem(0)
        qt_app.processEvents()
        edit_scene = third_unit.runtime.scene_controller.scene_root
        frame = _target(edit_scene, f"customLayoutEditFrame-{family}")
        assert frame.setProperty("childEditingLocked", False)
        qt_app.processEvents()
        role = _target(
            edit_scene, f"customLayoutChildRole-{family}-{spec['edit_role']}"
        )
        assert role.property("targetReady") is True, (
            family, "paint is visible but its stable Edit role is not ready",
            exposed_paint, (role.x(), role.y(), role.width(), role.height()),
        )
        assert getCppPointer(role.property("targetItem")) == getCppPointer(painted), (
            family, "selected role maps a different QQuickItem from the painted target",
        )
        assert (role.x(), role.y(), role.width(), role.height()) == pytest.approx(
            _mapped_box(painted, frame), abs=1.0,
        ), f"{family}: restored Edit proxy differs from the actually painted child"
        assert third_owner.cancel()
        qt_app.processEvents()
        assert _mapped_box(painted, third_presentation.item) == pytest.approx(
            exposed_paint, abs=1.0,
        )
        assert settings.widgets == second_committed
        assert settings.save_calls == 2 and settings.update_calls == 2
        assert reloads == []
    finally:
        for owner in reversed(owners):
            owner.retire()
        for unit in reversed(units):
            unit.retire()
        for factory in reversed(factories):
            factory.deleteLater()
        qt_app.processEvents()
        qt_app.setQuitOnLastWindowClosed(old_quit_policy)
