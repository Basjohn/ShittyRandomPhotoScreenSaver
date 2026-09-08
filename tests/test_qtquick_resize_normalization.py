"""Migrated cards preserve Settings-authored baselines under stale payload replay."""
import pytest
from PySide6.QtCore import QObject, QRect
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickItem

from rendering.quick.custom_layout_size import capture_quick_size_payload, scale_quick_size_payload
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost
from rendering.widget_descriptors import get_widget_runtime_descriptor
from tools.ordinary_widget_resize_capture import build_card


@pytest.mark.parametrize("family", ["abandonment_issues", "achievement_pulse", "weather"])
def test_stale_payload_and_repeated_geometry_never_reauthor_baseline(qt_app, family, tmp_path):
    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(owner=owner, screen_index=0, runtime_generation=9)
    host = OrdinaryWidgetPresentationHost(host_item=root.findChild(QQuickItem, "ordinaryWidgetHost"),
        context=context, create_overlay_item=factory.create_overlay_widget,
        create_family_item=factory.create_ordinary_widget_family)
    artwork = QImage(20, 30, QImage.Format.Format_ARGB32)
    artwork.fill(0xff336699)
    path = tmp_path / "art.png"
    assert artwork.save(str(path))
    card = build_card(family, "base", host, path, artwork)
    try:
        qt_app.processEvents()
        item = card.item
        config = card.model.config
        baseline = tuple(float(item.property(key)) for key in ("preferredContentWidth", "preferredContentHeight"))
        descriptor = get_widget_runtime_descriptor(family)
        assert capture_quick_size_payload(descriptor, card, QRect(0, 0, 600, 400)) == {}
        assert scale_quick_size_payload(descriptor, {}, .4) == {}
        retained = host.presentation_for_model_identity(family)
        for factor in (.4, .75, 2., .4, 1.):
            # Same host entry point used by committed hydration and live replay.
            retained.apply_custom_layout_size_payload({"font_size": 89, "artwork_size": 900,
                "square_artwork_size": 900, "capsule_font_size": 88, "icon_size": 99, "detail_icon_size": 66})
            item.setWidth(baseline[0] * factor)
            item.setHeight(baseline[1] * factor)
            qt_app.processEvents()
            assert card.model.config == config
            assert tuple(float(item.property(key)) for key in ("preferredContentWidth", "preferredContentHeight")) == baseline
            assert float(item.property("presentationScale")) == pytest.approx(factor)
    finally:
        card.retire()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.parametrize("family", ["abandonment_issues", "achievement_pulse", "weather"])
def test_two_live_saves_and_cancel_preserve_scale_and_identity(qt_app, family, tmp_path):
    from tests.test_qtquick_custom_layout_owner import _Settings
    from rendering.quick.custom_layout_owner import QuickCustomLayoutOwner
    from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
    from rendering.quick.display_unit import create_quick_display_unit
    from rendering.quick.state import QuickWindowPolicy
    from core.settings.default_contract import require_canonical_default

    artwork = QImage(20, 30, QImage.Format.Format_ARGB32)
    artwork.fill(0xff336699)
    path = tmp_path / "art.png"
    assert artwork.save(str(path))

    class SnapshotAdapter:
        family_id = family

        def enabled_instance_ids(self, widgets_config):
            return (family,)

        def build(self, *, host, geometry, **kwargs):
            card = build_card(family, "base", host, path, artwork)
            card.set_geometry(geometry)
            return card

    widgets = {family: {"enabled": True, "monitor": "ALL", "position": "Top Left"}}
    settings = _Settings(widgets)
    factory = QuickSceneFactory()
    unit = create_quick_display_unit(screen=qt_app.primaryScreen(), screen_index=0,
        runtime_generation=71, scene_factory=factory, adapters=(SnapshotAdapter(),),
        ctrl_coordinator=SharedCtrlCoordinator(),
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False))
    reloads = []
    owner = QuickCustomLayoutOwner(settings_manager=settings, participants_provider=lambda: (unit,),
        visualizer_provider=lambda: (None, None), reload_request=reloads.append)
    try:
        assert unit.bind_families(widgets_config=widgets,
            shadow_values=require_canonical_default("widgets.shadows")) == (family,)
        card = unit.presenter.presentation_for_widget_id(family)
        identity, config = card.item, card.model.config
        assert owner.start()
        item = owner.session.items()[0]
        rect = item.current_global_rect
        target = QRect(rect.x(), rect.y(), round(rect.width() * .4), round(rect.height() * .4))
        item.set_geometry(target, size_payload={}, resize_scale=.4)
        owner.session.notify_item_changed(item)
        assert owner.save()
        saved = unit.presenter.geometry_for(family)
        assert owner.start()
        assert owner.save()
        assert unit.presenter.geometry_for(family) == saved
        assert owner.start()
        item = owner.session.items()[0]
        moved = QRect(item.current_global_rect)
        moved.translate(70, 40)
        item.set_geometry(moved, size_payload={}, resize_scale=.4)
        owner.session.notify_item_changed(item)
        assert owner.cancel()
        assert unit.presenter.geometry_for(family) == saved
        assert card.item is identity
        assert card.model.config == config
        assert reloads == []
        assert settings.save_calls == 2

        # Serialize a current-format older save, then cross real hydration,
        # untouched Save, runtime reconstruction and number-slot replay seams.
        from rendering.custom_layout_contract import (
            load_custom_layout_map, write_custom_layout_map,
            get_screen_layout_entries_for_screen,
        )
        from rendering.quick.custom_layout_hydration import (
            apply_quick_committed_payloads, resolve_quick_committed_geometry,
        )
        from core.settings.layout_slots import save_layout_slot, apply_layout_slot

        layout = load_custom_layout_map(settings.widgets)
        signature, entries = get_screen_layout_entries_for_screen(layout, qt_app.primaryScreen())
        assert signature is not None
        layout["displays"][signature][family]["default"]["size_payload"] = {
            "font_size": 89, "artwork_size": 900, "square_artwork_size": 900,
            "capsule_font_size": 88, "icon_size": 99, "detail_icon_size": 66,
            "_custom_resize_scale": .4,
        }
        write_custom_layout_map(settings.widgets, layout)
        assert save_layout_slot(settings.widgets, "1")
        for generation in (72, 73, 74):
            owner.retire()
            unit.retire()
            qt_app.processEvents()
            if generation == 74:
                assert apply_layout_slot(settings.widgets, "1")
            unit = create_quick_display_unit(screen=qt_app.primaryScreen(), screen_index=0,
                runtime_generation=generation, scene_factory=factory, adapters=(SnapshotAdapter(),),
                ctrl_coordinator=SharedCtrlCoordinator(),
                window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False))
            assert unit.bind_families(widgets_config=settings.widgets,
                shadow_values=require_canonical_default("widgets.shadows"),
                committed_rect_resolver=lambda widget_id: resolve_quick_committed_geometry(
                    settings.widgets, qt_app.primaryScreen(), widget_id)) == (family,)
            apply_quick_committed_payloads(unit, settings.widgets)
            card = unit.presenter.presentation_for_widget_id(family)
            assert card.model.config == config
            assert unit.presenter.geometry_for(family) == saved
            assert float(card.item.property("presentationScale")) == pytest.approx(.4, abs=.003)
            owner = QuickCustomLayoutOwner(settings_manager=settings,
                participants_provider=lambda: (unit,), visualizer_provider=lambda: (None, None),
                reload_request=reloads.append)
            assert owner.start()
            assert owner.save()
            assert card.model.config == config
            assert unit.presenter.geometry_for(family) == saved
        assert reloads == []
    finally:
        owner.retire()
        unit.retire()
        factory.deleteLater()
        qt_app.processEvents()
