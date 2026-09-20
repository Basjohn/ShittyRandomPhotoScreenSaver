"""Retained Qt and shared lease regressions for the opt-in system-audio OSD.

No real endpoint or external hardware changes are used by these tests.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

from core.settings.default_contract import require_canonical_default
from core.settings.widget_family_catalog import get_widget_family_descriptor
from rendering.quick.widgets.family_binder import SystemAudioOSDFamilyAdapter
from rendering.quick.widgets.registry import ordinary_widget_family_component
from rendering.quick.widgets.system_audio_osd import (
    SystemAudioOSDConfig, SystemAudioOSDPresentationModel,
)
from rendering.widget_descriptors import (
    get_widget_runtime_descriptor, get_widget_settings_section_descriptor,
)
from rendering.widget_runtime_services import get_runtime_service_spec

pytestmark = pytest.mark.usefixtures("qt_app")
ROOT = Path(__file__).resolve().parents[1]
QML_ROOT = ROOT / "rendering" / "quick" / "qml"


class _Lease:
    def __init__(self):
        self.consumer = None
        self.started = self.stopped = self.detached = 0
        self.manager = None

    def attach_consumer(self, consumer):
        assert self.consumer is None
        self.consumer = consumer

    def set_thread_manager(self, manager):
        self.manager = manager

    def start(self):
        self.started += 1
        self.publish(1, 0, 0.45)
        return True

    def publish(self, revision, endpoint_token, volume, muted=False, available=True):
        assert self.consumer is not None
        self.consumer.on_system_mute_runtime_snapshot(SimpleNamespace(
            revision=revision, endpoint_token=endpoint_token, available=available,
            volume=volume if available else None, muted=muted, source="notification",
        ))

    def stop(self):
        self.stopped += 1

    def detach_consumer(self, consumer):
        assert consumer is self.consumer
        self.consumer = None
        self.detached += 1


def _model(lease=None, **config):
    model = SystemAudioOSDPresentationModel(
        SystemAudioOSDConfig.from_widgets_mapping({"system_audio_osd": config}),
        runtime_generation=783,
    )
    if lease is not None:
        model.set_system_mute_runtime_service(lease)
    return model


def test_osd_default_is_dormant_and_uses_one_shared_source_spec():
    assert require_canonical_default("widgets.system_audio_osd.enabled") is False
    adapter = SystemAudioOSDFamilyAdapter()
    assert adapter.enabled_instance_ids({}) == ()
    assert adapter.enabled_instance_ids({"system_audio_osd": {"enabled": False}}) == ()
    assert adapter.enabled_instance_ids({"system_audio_osd": {"enabled": True}}) == ("system_audio_osd",)
    assert get_widget_family_descriptor("system_audio_osd").required_family_ids == ()
    descriptor = get_widget_runtime_descriptor("system_audio_osd")
    assert descriptor.supports_layout_edit_mode
    assert descriptor.content_extent_axes == ("horizontal", "vertical")
    assert get_widget_settings_section_descriptor("system_audio_osd") is not None
    assert (get_runtime_service_spec("system_audio_osd")
            is get_runtime_service_spec("mute_button"))
    assert ordinary_widget_family_component("system_audio_osd").qml_filename == "SystemAudioOSDPresentation.qml"


def test_one_deadline_burst_and_stale_device_event(qt_app):
    lease = _Lease()
    model = _model(lease)
    assert model.activate(object())
    assert lease.started == 1 and not model.revealed
    timer = model._deadline
    assert timer.isSingleShot() and not timer.isActive()
    assert model.available and model.percentageText == "45%"

    for revision in range(2, 102):
        lease.publish(revision, 0, min(1.0, 0.45 + revision / 1000))
    assert model.revealed and timer.isActive()
    assert model._deadline is timer
    assert model.percentageText == "55%"
    lease.publish(102, 0, 0.552, muted=True)
    assert model.muted and timer.isActive()
    lease.publish(103, 1, 0.0, available=False)
    assert not model.revealed and not timer.isActive()
    lease.publish(104, 1, 0.7)
    assert not model.revealed  # device rebind seeds silently
    lease.publish(105, 1, 0.8)
    assert model.revealed
    model._hide_on_deadline()
    assert not model.revealed
    assert model.activate(object()) and lease.started == 1
    model.retire()
    assert lease.stopped == lease.detached == 1
    assert not timer.isActive()
    lease.consumer = model  # deliberately simulate an already-queued stale callback
    lease.publish(106, 1, 0.9)
    assert not model.revealed
    qt_app.processEvents()


def test_retained_qml_bar_tracks_actual_master_volume_without_recreation(qt_app):
    lease = _Lease()
    model = _model(lease, text_position="inside_bar")
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_ROOT / "SystemAudioOSDPresentation.qml")))
    assert component.status() == QQmlComponent.Status.Ready, [error.toString() for error in component.errors()]
    item = component.createWithInitialProperties({"osdModel": model})
    assert isinstance(item, QQuickItem), [error.toString() for error in component.errors()]
    model.setParent(item)
    item.setWidth(model.authoredWidth)
    item.setHeight(model.authoredHeight)
    try:
        qt_app.processEvents()
        assert model.activate(object()) and not model.revealed
        track = item.findChild(QQuickItem, "systemAudioOSDVolumeTrack")
        fill = item.findChild(QQuickItem, "systemAudioOSDVolumeFill")
        pct = item.findChild(QQuickItem, "systemAudioOSDPercentage")
        assert track is not None and fill is not None and pct is not None
        assert not bool(item.property("customLayoutInputBlocked"))
        lease.publish(2, 0, 0.75)
        qt_app.processEvents()
        assert model.revealed
        assert pct.property("text") == "75%"
        assert fill.width() == pytest.approx(track.width() * 0.75, abs=0.02)
        assert item.findChild(QQuickItem, "systemAudioOSDVolumeTrack") is track
        lease.publish(3, 0, 0.75, muted=True)
        qt_app.processEvents()
        assert model.muted and pct.property("text") == "75%"
        model._hide_on_deadline()
        qt_app.processEvents()
        assert not model.revealed
        # Edit-only reveal is resolved on the same retained item, never by
        # allocating an alternate overlay or audio lease.
        item.setProperty("customLayoutInputBlocked", True)
        qt_app.processEvents()
        assert float(item.property("fadeOpacity")) >= 0.0
        item.setProperty("customLayoutInputBlocked", False)
        qt_app.processEvents()
        assert item.findChild(QQuickItem, "systemAudioOSDVolumeTrack") is track
    finally:
        model.retire()
        item.deleteLater()
        engine.deleteLater()
        qt_app.processEvents()


def test_osd_colour_inheritance_respects_active_widget_theme_and_authored_overrides():
    """OSD must use the same semantic colour owner as other retained widgets."""
    from ui.settings_theme_spec import Rgba
    from ui.widget_theme_spec import WidgetThemeSpec
    from ui.widget_theme_active import get_active_widget_theme, set_active_widget_theme

    original = get_active_widget_theme()
    palette = dict(original.colors)
    palette.update({
        "card.background": Rgba(24, 34, 44, 218),
        "card.border": Rgba(120, 190, 225, 243),
        "card.text": Rgba(233, 240, 249, 250),
        "widget.accent": Rgba(85, 180, 215, 255),
    })
    themed = WidgetThemeSpec(theme_id="osd_test_palette", name="OSD Test Palette", colors=palette)
    try:
        set_active_widget_theme(themed)
        config = SystemAudioOSDConfig.from_widgets_mapping({"system_audio_osd": {}})
        assert config.card_style.background_color == QColor(24, 34, 44, 218)
        assert config.card_style.border_color == QColor(120, 190, 225, 243)
        assert config.text_color == (233, 240, 249, 250)
        assert config.accent_color == (85, 180, 215, 255)
        assert config.track_color == (24, 34, 44, 218)

        authored = SystemAudioOSDConfig.from_widgets_mapping({"system_audio_osd": {
            "bg_color": [20, 30, 40, 255],
            "border_color": [12, 22, 32, 220],
            "color": [120, 130, 140, 250],
            "accent_color": [151, 161, 171, 255],
            "track_color": [44, 55, 66, 210],
        }})
        assert authored.card_style.background_color == QColor(20, 30, 40, 255)
        assert authored.card_style.border_color == QColor(12, 22, 32, 220)
        assert authored.text_color == (120, 130, 140, 250)
        assert authored.accent_color == (151, 161, 171, 255)
        assert authored.track_color == (44, 55, 66, 210)
    finally:
        set_active_widget_theme(original)


@pytest.mark.qt
def test_osd_foreground_host_is_above_visualizer_and_below_context_menu(qt_app):
    """Retained OSD and its shadow share one owner and one pixel-shift space."""
    from PySide6.QtCore import QObject
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost, OverlayWidgetGeometry
    from rendering.quick.widgets.system_audio_osd import RetainedSystemAudioOSDPresentation

    owner = QObject()
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=owner, screen_index=0, runtime_generation=783,
    )
    def locate(name):
        item = root.findChild(QQuickItem, name)
        assert item is not None, name
        return item
    foreground = locate("systemAudioOSDForegroundHost")
    shadow_host = locate("systemAudioOSDShadowHost")
    normal = locate("ordinaryWidgetHost")
    visualizer = locate("visualizerPresentationLoader")
    context_menu = locate("retainedContextMenu")
    assert normal.parentItem() is foreground.parentItem() is visualizer.parentItem()
    assert normal.z() < visualizer.z() < shadow_host.z() < foreground.z()
    assert context_menu.z() > foreground.parentItem().z()
    host = OrdinaryWidgetPresentationHost(
        host_item=normal,
        shadow_host_item=locate("ordinaryWidgetShadowHost"),
        foreground_host_item=foreground,
        foreground_shadow_host_item=shadow_host,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
        create_shadow_item=factory.create_overlay_card_shadow,
        create_family_item=factory.create_ordinary_widget_family,
    )
    model = _model()
    presentation = RetainedSystemAudioOSDPresentation(
        host=host, model=model,
        geometry=OverlayWidgetGeometry(20.0, 30.0, 380.0, 68.0),
    )
    try:
        assert presentation.item.parentItem() is foreground
        assert host.live_count == 1
        retained = host.presentation_for_model_identity("system_audio_osd")
        assert retained is not None and retained.item is presentation.item
        assert retained.shadow_item is not None
        assert retained.shadow_item.parentItem() is shadow_host
        # A display transfer must keep the same retained root and shadow in the
        # destination's foreground lanes. The ordinary owner still holds one
        # identity and retirement path; it must not route OSD back below viz.
        context2, root2 = factory.create_display_root(
            owner=owner, screen_index=1, runtime_generation=784,
        )
        def locate2(name):
            found = root2.findChild(QQuickItem, name)
            assert found is not None, name
            return found
        host2 = OrdinaryWidgetPresentationHost(
            host_item=locate2("ordinaryWidgetHost"),
            shadow_host_item=locate2("ordinaryWidgetShadowHost"),
            foreground_host_item=locate2("systemAudioOSDForegroundHost"),
            foreground_shadow_host_item=locate2("systemAudioOSDShadowHost"),
            context=context2,
            create_overlay_item=factory.create_overlay_widget,
            create_shadow_item=factory.create_overlay_card_shadow,
            create_family_item=factory.create_ordinary_widget_family,
        )
        try:
            original_item = presentation.item
            original_shadow = retained.shadow_item
            assert host.transfer_widget_to(retained, host2)
            assert host.live_count == 0 and host2.live_count == 1
            assert retained.item is original_item and retained.shadow_item is original_shadow
            assert original_item.parentItem() is locate2("systemAudioOSDForegroundHost")
            assert original_shadow.parentItem() is locate2("systemAudioOSDShadowHost")
            assert host2.presentation_for_model_identity("system_audio_osd") is retained
        finally:
            host2.retire_all()
            root2.deleteLater()
    finally:
        host.retire_all()
        root.deleteLater()
        owner.deleteLater()
        qt_app.processEvents()
