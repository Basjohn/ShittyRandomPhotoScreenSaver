from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

from core.settings.default_contract import require_canonical_default
from core.settings.widget_family_catalog import get_widget_family_descriptor
from core.system_stats.source import CpuRamSample
from rendering.quick.widgets.registry import ordinary_widget_family_component
from rendering.quick.widgets.system_stats import (
    SystemStatsPresentationConfig,
    SystemStatsPresentationModel,
    SystemStatsPresentationStyle,
)
from rendering.widget_descriptors import (
    get_widget_runtime_descriptor,
    get_widget_settings_section_descriptor,
)
from rendering.widget_runtime_services import get_runtime_service_spec


pytestmark = pytest.mark.usefixtures("qt_app")
ROOT = Path(__file__).resolve().parents[1]
QML_ROOT = ROOT / "rendering" / "quick" / "qml"


class _RuntimeService:
    def __init__(self) -> None:
        self.consumer = None
        self.started = 0
        self.stopped = 0
        self.detached = 0

    def set_thread_manager(self, manager) -> None:
        self.manager = manager

    def attach_consumer(self, consumer) -> None:
        self.consumer = consumer

    def detach_consumer(self, consumer) -> None:
        assert consumer is self.consumer
        self.detached += 1

    def start(self) -> bool:
        self.started += 1
        return True

    def stop(self) -> None:
        self.stopped += 1


def _model(service: _RuntimeService | None = None) -> SystemStatsPresentationModel:
    config = SystemStatsPresentationConfig.from_widgets_mapping({})
    style = SystemStatsPresentationStyle.project(
        config, dict(require_canonical_default("widgets.shadows"))
    )
    model = SystemStatsPresentationModel(config, style, runtime_generation=81)
    if service is not None:
        model.set_runtime_service(service)
    return model


def test_fixed_metric_capacity_owns_base_geometry_and_values_do_not() -> None:
    config = SystemStatsPresentationConfig.from_widgets_mapping(
        {"system_stats": {"preferred_width": 600, "metric_capacity": 99}}
    )
    assert config.metric_capacity == 4
    assert config.authored_width == 600
    assert config.authored_height == 430

    service = _RuntimeService()
    model = _model(service)
    model.activate(object())
    before = (model.authoredWidth, model.authoredHeight)
    model.on_system_stats_runtime_snapshot(
        SimpleNamespace(
            revision=1,
            sample=CpuRamSample(
                "ok", 47.6, "ok", 8 * 1024**3, 16 * 1024**3,
                "ok", 3 * 86400 + 14 * 3600, "ok", 6.2 * 1024**2, 340 * 1024,
            ),
        )
    )
    assert model.cpuValue == "48%"
    assert model.ramValue == "50%"
    assert "8.0 GB of 16.0 GB" in model.ramDetail
    assert model.uptimeValue == "3d 14h"
    assert model.uptimeDetail == "Since system boot"
    assert model.networkValue.startswith("↓ 6.20 MB/s")
    assert model.networkDetail.startswith("↑ 340 KB/s")
    assert (model.authoredWidth, model.authoredHeight) == before
    model.retire()
    assert service.stopped == service.detached == 1


def test_system_stats_metric_selection_and_custom_extent_are_presentation_only() -> None:
    config = SystemStatsPresentationConfig.from_widgets_mapping(
        {
            "system_stats": {
                "show_cpu": True,
                "show_memory": False,
                "show_uptime": True,
                "show_network": False,
            }
        }
    )
    model = SystemStatsPresentationModel(
        config,
        SystemStatsPresentationStyle.project(
            config, dict(require_canonical_default("widgets.shadows"))
        ),
    )
    assert model.enabledMetricCount == 2
    assert model.showCpu is True
    assert model.showMemory is False
    assert model.showUptime is True
    assert model.showNetwork is False
    before = (model.authoredWidth, model.authoredHeight)
    assert model.set_content_extent(760, 640) is True
    assert (model.authoredWidth, model.authoredHeight) == (760.0, 640.0)
    assert model.clear_content_extent() is True
    assert (model.authoredWidth, model.authoredHeight) == before


def test_system_stats_family_is_public_but_member_defaults_dormant() -> None:
    family = get_widget_family_descriptor("system_stats")
    descriptor = get_widget_runtime_descriptor("system_stats")
    section = get_widget_settings_section_descriptor("system_stats")
    assert family is not None and family.member_widget_ids == ("system_stats",)
    assert descriptor is not None
    assert descriptor.custom_layout_resize_mode == "ordinary_uniform"
    assert descriptor.content_extent_axes == ("horizontal", "vertical")
    assert descriptor.service_backed is True
    assert section is not None and section.persisted_widget_keys == (
        "system_stats",
    )
    assert get_runtime_service_spec("system_stats") is not None
    assert require_canonical_default("widgets.family_activation.system_stats") is True
    assert require_canonical_default("widgets.system_stats.enabled") is False


def test_system_stats_registry_icon_and_qml_are_presentation_only() -> None:
    descriptor = ordinary_widget_family_component("system_stats")
    assert descriptor.qml_filename == "SystemStatsPresentation.qml"
    assert (ROOT / "images" / "system_stats_tools.svg").is_file()
    qml = (QML_ROOT / descriptor.qml_filename).read_text(encoding="utf-8")
    for forbidden in (
        "Timer {",
        "psutil",
        "usage_sampler",
        "Process",
        "SystemStatsRuntimeService",
        "SettingsManager",
        "QWidget",
        "QPainter",
        "http://",
        "https://",
    ):
        assert forbidden not in qml
    assert "uniformScaleTransform: true" in qml
    assert "Behavior on width" in qml


@pytest.mark.qt
def test_system_stats_qml_reflows_four_enabled_metric_panels(qt_app) -> None:
    service = _RuntimeService()
    model = _model(service)
    model.activate(object())
    model.on_system_stats_runtime_snapshot(
        SimpleNamespace(
            revision=1,
            sample=CpuRamSample(
                "ok", 36.0, "ok", 5 * 1024**3, 16 * 1024**3,
                "ok", 3600.0, "ok", 1024.0, 2048.0,
            ),
        )
    )
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(QML_ROOT / "SystemStatsPresentation.qml"))
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    item = component.createWithInitialProperties({"systemStatsModel": model})
    assert isinstance(item, QQuickItem), [
        error.toString() for error in component.errors()
    ]
    item.setWidth(model.authoredWidth)
    item.setHeight(model.authoredHeight)
    try:
        qt_app.processEvents()
        cpu = item.findChild(QObject, "systemStatsCpuPanel")
        ram = item.findChild(QObject, "systemStatsRamPanel")
        uptime = item.findChild(QObject, "systemStatsUptimePanel")
        network = item.findChild(QObject, "systemStatsNetworkPanel")
        assert cpu is not None and ram is not None and uptime is not None and network is not None
        heights = {round(float(panel.property("height")), 2) for panel in (cpu, ram, uptime, network)}
        assert len(heights) == 1
        assert next(iter(heights)) > 72.0
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        model.retire()
        qt_app.processEvents()


@pytest.mark.qt
def test_system_stats_minimum_width_keeps_detail_clear_of_value(qt_app) -> None:
    config = SystemStatsPresentationConfig.from_widgets_mapping(
        {"system_stats": {"preferred_width": 440}}
    )
    model = SystemStatsPresentationModel(
        config,
        SystemStatsPresentationStyle.project(
            config,
            dict(require_canonical_default("widgets.shadows")),
        ),
    )
    service = _RuntimeService()
    model.set_runtime_service(service)
    model.activate(object())
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(QML_ROOT / "SystemStatsPresentation.qml"))
    )
    item = component.createWithInitialProperties({"systemStatsModel": model})
    assert isinstance(item, QQuickItem), [
        error.toString() for error in component.errors()
    ]
    item.setWidth(model.authoredWidth)
    item.setHeight(model.authoredHeight)
    try:
        qt_app.processEvents()
        detail = item.findChild(QObject, "systemStatsCpuDetail")
        value = item.findChild(QObject, "systemStatsCpuValue")
        assert detail is not None and value is not None
        assert detail.x() + detail.width() <= value.x()
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        model.retire()
        qt_app.processEvents()
