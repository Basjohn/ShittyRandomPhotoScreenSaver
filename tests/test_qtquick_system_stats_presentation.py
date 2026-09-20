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


def test_system_stats_sample_edge_invalidates_only_dynamic_metric_properties() -> None:
    service = _RuntimeService()
    model = _model(service)
    model.activate(object())
    sample_edges: list[None] = []
    state_edges: list[None] = []
    model.sampleChanged.connect(lambda: sample_edges.append(None))
    model.stateChanged.connect(lambda: state_edges.append(None))

    model.on_system_stats_runtime_snapshot(
        SimpleNamespace(
            revision=1,
            sample=CpuRamSample(
                "ok", 48.0, "ok", 8 * 1024**3, 16 * 1024**3,
                "ok", 3600.0, "ok", 1024.0, 2048.0,
            ),
        )
    )

    assert sample_edges == [None]
    assert state_edges == []
    # Layout/config mutation still owns the broad state signal, not the sample.
    assert model.set_content_extent(760, 640) is True
    assert state_edges == [None]
    assert sample_edges == [None]
    model.retire()


def test_system_stats_custom_child_geometry_is_constant_semantic_state() -> None:
    model = _model()
    custom_edges: list[None] = []
    state_edges: list[None] = []
    sample_edges: list[None] = []
    model.customGeometryChanged.connect(lambda: custom_edges.append(None))
    model.stateChanged.connect(lambda: state_edges.append(None))
    model.sampleChanged.connect(lambda: sample_edges.append(None))

    assert model.set_custom_child_geometry(
        {
            "metric_panels": {
                "width_scale": 1.2,
                "height_scale": 0.8,
                "x_offset": 0.05,
                "y_offset": 0.04,
            },
            "header_separator": {
                "width_scale": 0.9,
                "height_scale": 1.15,
            },
        }
    ) is True
    assert custom_edges == [None]
    assert state_edges == []
    assert sample_edges == []
    assert set(model.customChildGeometry) == {"metric_panels", "header_separator"}
    assert model.customChildGeometry["metric_panels"]["width_scale"] == pytest.approx(1.2)
    assert model.customChildGeometry["header_separator"]["height_scale"] == pytest.approx(1.15)

    # Resetting to authored state clears the sparse projection without touching
    # Settings, sample state or the enabled-metric identities.
    assert model.set_custom_child_geometry({}) is True
    assert model.customChildGeometry == {}
    assert custom_edges == [None, None]
    assert state_edges == []
    assert sample_edges == []


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


def test_system_stats_family_is_public_and_default_leaves_are_explicit() -> None:
    family = get_widget_family_descriptor("system_stats")
    descriptor = get_widget_runtime_descriptor("system_stats")
    section = get_widget_settings_section_descriptor("system_stats")
    assert family is not None and family.member_widget_ids == ("system_stats",)
    assert descriptor is not None
    assert descriptor.custom_layout_resize_mode == "ordinary_uniform"
    assert descriptor.content_extent_axes == ("horizontal", "vertical")
    assert descriptor.content_extent_minimum_size == (440, 190)
    assert tuple(role.role_id for role in descriptor.custom_child_roles) == (
        "header",
        "header_separator",
        "metric_panels",
    )
    assert not any(
        metric in role.role_id
        for role in descriptor.custom_child_roles
        for metric in ("cpu", "ram", "uptime", "network")
    )
    assert descriptor.service_backed is True
    assert section is not None and section.persisted_widget_keys == (
        "system_stats",
    )
    assert get_runtime_service_spec("system_stats") is not None
    # Product defaults are mutable policy. This presentation/registry test only
    # requires that both activation leaves exist and are typed booleans.
    assert type(require_canonical_default("widgets.family_activation.system_stats")) is bool
    assert type(require_canonical_default("widgets.system_stats.enabled")) is bool


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
    assert "Math.abs(width - systemStatsModel.authoredWidth) > 0.5" in qml
    assert "Math.abs(height - systemStatsModel.authoredHeight) > 0.5" in qml
    assert "Behavior on width" in qml
    assert "customEditableChildRoles" in qml
    assert '"roleId": "metric_panels"' in qml
    assert '"roleId": "metric_values"' not in qml
    assert "systemStatsCustomMetricPanelRoleTarget" in qml


@pytest.mark.qt
def test_system_stats_shared_metric_geometry_projects_to_every_panel(qt_app) -> None:
    service = _RuntimeService()
    model = _model(service)
    model.activate(object())
    assert model.set_custom_child_geometry(
        {
            "metric_panels": {
                "width_scale": 0.82,
                "height_scale": 0.76,
                "x_offset": 0.03,
                "y_offset": 0.02,
            },
        }
    ) is True
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
        panels = [
            item.findChild(QObject, name)
            for name in (
                "systemStatsCpuPanel",
                "systemStatsRamPanel",
                "systemStatsUptimePanel",
                "systemStatsNetworkPanel",
            )
        ]
        assert all(panel is not None for panel in panels)
        widths = {round(float(panel.property("width")), 3) for panel in panels}
        heights = {round(float(panel.property("height")), 3) for panel in panels}
        xs = {round(float(panel.property("x")), 3) for panel in panels}
        assert len(widths) == len(heights) == len(xs) == 1

        cpu_value = item.findChild(QObject, "systemStatsCpuValue")
        ram_value = item.findChild(QObject, "systemStatsRamValue")
        assert cpu_value is not None and ram_value is not None
        assert float(cpu_value.property("width")) == pytest.approx(
            float(ram_value.property("width"))
        )
        assert int(cpu_value.property("horizontalAlignment")) == int(
            ram_value.property("horizontalAlignment")
        )
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        model.retire()
        qt_app.processEvents()


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


@pytest.mark.qt
def test_system_stats_header_flip_swaps_metric_rails_and_restores_authored_spacing(qt_app) -> None:
    """Header flip is semantic orientation, not blanket mirroring of all text."""
    model = _model()
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
        header = item.findChild(QObject, "systemStatsHeaderFrame")
        label = item.findChild(QObject, "systemStatsCpuLabel")
        value = item.findChild(QObject, "systemStatsCpuValue")
        accent = item.findChild(QObject, "systemStatsCpuAccent")
        assert all(obj is not None for obj in (header, label, value, accent))
        baseline = (header.x(), label.x(), value.x(), accent.x())
        assert label.x() < value.x()
        assert accent.x() == pytest.approx(0.0)
        assert model.set_custom_child_geometry({"header": {"alignment": "right"}})
        qt_app.processEvents()
        assert bool(item.property("headerFlipped"))
        assert header.parentItem().x() > baseline[0]
        assert label.x() > value.x() + value.width() + 1.0
        assert accent.x() > 0.0
        # The flip now owns all repeated metric internals as one semantic layout;
        # no independently movable label/value/track edit roles remain.
        assert int(label.property("horizontalAlignment")) != int(
            item.findChild(QObject, "systemStatsCpuValue").property("horizontalAlignment")
        )
        assert model.set_custom_child_geometry({})
        qt_app.processEvents()
        assert not bool(item.property("headerFlipped"))
        assert (header.x(), label.x(), value.x(), accent.x()) == pytest.approx(baseline)
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
@pytest.mark.parametrize("enabled", (
    ("cpu", "memory", "uptime", "network"),
    ("memory", "uptime"),
    ("network",),
    (),
))
def test_metric_edit_stack_encloses_every_enabled_panel_without_ghost_targets(
    qt_app, enabled: tuple[str, ...],
) -> None:
    """One real editable block, including gaps; no per-card or per-label proxies."""
    config = SystemStatsPresentationConfig.from_widgets_mapping({
        "system_stats": {
            "show_cpu": "cpu" in enabled,
            "show_memory": "memory" in enabled,
            "show_uptime": "uptime" in enabled,
            "show_network": "network" in enabled,
        },
    })
    model = SystemStatsPresentationModel(
        config,
        SystemStatsPresentationStyle.project(
            config, dict(require_canonical_default("widgets.shadows")),
        ),
    )
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(QML_ROOT / "SystemStatsPresentation.qml")),
    )
    item = component.createWithInitialProperties({"systemStatsModel": model})
    assert isinstance(item, QQuickItem), [e.toString() for e in component.errors()]
    item.setWidth(model.authoredWidth)
    item.setHeight(model.authoredHeight)
    target = item.findChild(QQuickItem, "systemStatsCustomMetricPanelRoleTarget")
    assert target is not None
    panel_names = {"cpu": "Cpu", "memory": "Ram", "uptime": "Uptime", "network": "Network"}
    all_panels = {
        key: item.findChild(QQuickItem, "systemStats" + suffix + "Panel")
        for key, suffix in panel_names.items()
    }
    assert all(panel is not None for panel in all_panels.values())
    try:
        for extent in ((model.authoredWidth, model.authoredHeight), (710.0, 525.0)):
            model.set_content_extent(*extent)
            item.setWidth(extent[0]); item.setHeight(extent[1])
            for flipped in (False, True, False):
                model.set_custom_child_geometry({
                    "metric_panels": {
                        "width_scale": 0.94, "height_scale": 1.08,
                        "x_offset": 0.015 if flipped else -0.012,
                        "y_offset": 0.012 if flipped else -0.008,
                    },
                    "header": {"alignment": "right" if flipped else "left"},
                })
                qt_app.processEvents()
                count = int(item.property("paintedMetricCount"))
                assert 0 <= count <= len(enabled)
                painted = enabled[:count]
                assert target.isVisible() == bool(painted)
                active = [all_panels[key] for key in painted]
                for key, panel in all_panels.items():
                    assert panel.isVisible() == (key in painted)
                if not active:
                    continue
                def box(child):
                    corners = [child.mapToItem(item, x, y) for x, y in (
                        (0., 0.), (child.width(), 0.), (0., child.height()),
                        (child.width(), child.height()),
                    )]
                    return (min(p.x() for p in corners), min(p.y() for p in corners),
                            max(p.x() for p in corners), max(p.y() for p in corners))
                boxes = [box(panel) for panel in active]
                expected = (min(b[0] for b in boxes), min(b[1] for b in boxes),
                            max(b[2] for b in boxes), max(b[3] for b in boxes))
                edit_box = box(target)
                assert edit_box[:3] == pytest.approx(expected[:3], abs=0.02)
                # The handle continuously tracks the requested stack until the
                # card bottom, even if a whole trailing panel has to hide.
                assert edit_box[3] >= expected[3] - 0.02
                assert edit_box[3] <= float(item.property("metricPaintBottom")) + 0.02
                if count == len(enabled):
                    assert edit_box == pytest.approx(expected, abs=0.02)
                # The one group edit moves every real card by the same delta,
                # without separately displacing the label/value/accent/track.
                assert all(panel.x() == pytest.approx(active[0].x()) for panel in active)
                for panel in active:
                    label = panel.findChild(QQuickItem, panel.objectName().replace("Panel", "Label"))
                    value = panel.findChild(QQuickItem, panel.objectName().replace("Panel", "Value"))
                    assert label is not None and value is not None
                    assert (label.x() > value.x()) == flipped
        assert model.set_custom_child_geometry({})
        qt_app.processEvents()
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater(); component.deleteLater(); engine.deleteLater()
        model.retire(); qt_app.processEvents()


@pytest.mark.qt
def test_system_stats_y_compaction_hides_complete_panels_without_republishing_geometry(qt_app) -> None:
    """Only painted full panels are admitted; the retained Edit target never leaves the card."""
    model = _model()
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(engine, QUrl.fromLocalFile(
        str(QML_ROOT / "SystemStatsPresentation.qml")
    ))
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    item = component.createWithInitialProperties({"systemStatsModel": model})
    assert isinstance(item, QQuickItem)
    item.setWidth(model.authoredWidth)
    item.setHeight(model.authoredHeight)
    panels = [item.findChild(QQuickItem, "systemStats" + suffix + "Panel")
              for suffix in ("Cpu", "Ram", "Uptime", "Network")]
    target = item.findChild(QQuickItem, "systemStatsCustomMetricPanelRoleTarget")
    assert all(panel is not None for panel in panels) and target is not None
    try:
        qt_app.processEvents()
        assert int(item.property("paintedMetricCount")) == 4
        assert all(panel.isVisible() for panel in panels)
        before = dict(model.customChildGeometry)
        observed_counts = []
        for height in (350., 280., 240., 190., 240., 280., 350., 430.):
            assert model.set_content_extent(float(model.authoredWidth), height)
            item.setHeight(height)
            qt_app.processEvents()
            count = int(item.property("paintedMetricCount"))
            observed_counts.append(count)
            assert 0 <= count <= 4
            assert target.isVisible() == (count > 0)
            assert [panel.isVisible() for panel in panels] == [i < count for i in range(4)]
            if count:
                bottom = float(item.property("metricPaintBottom"))
                assert target.y() + target.height() <= bottom + 0.02
                for panel in panels[:count]:
                    assert panel.y() + panel.height() <= bottom + 0.02
            assert dict(model.customChildGeometry) == before
            assert item.findChild(QQuickItem, "systemStatsCustomMetricPanelRoleTarget") is target
        assert int(item.property("paintedMetricCount")) == 4
        assert observed_counts[:4] == sorted(observed_counts[:4], reverse=True)
        assert observed_counts[3] < observed_counts[0] - 1  # More than one panel retires.
        assert observed_counts[4:] == [
            observed_counts[2], observed_counts[1], observed_counts[0], 4
        ]
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        model.retire()
        qt_app.processEvents()


@pytest.mark.qt
def test_system_stats_selected_edit_exposes_one_live_metric_stack_and_no_ghost_roles(qt_app) -> None:
    """Real selected CUSTOM scene, not only stand-in QML representative equality.

    All four painted panels must move with the SAME retained group Edit proxy,
    while the header and separator remain separately editable. Flipping or
    changing group geometry must not recreate the three Edit delegates.
    """
    from PySide6.QtCore import QPoint, QRect, qInstallMessageHandler
    from PySide6.QtQuick import QQuickWindow
    from rendering.custom_layout_session import (
        CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem,
    )
    from rendering.quick.custom_layout_overlay import RetainedCustomLayoutOverlay
    from rendering.quick.scene_controller import QuickSceneFactory
    from rendering.quick.widgets.host import (
        OrdinaryWidgetPresentationHost, OverlayWidgetGeometry,
    )
    from rendering.quick.widgets.system_stats import RetainedSystemStatsPresentation

    def visual(root: QQuickItem, name: str) -> QQuickItem | None:
        if root.objectName() == name:
            return root
        for child in root.childItems():
            found = visual(child, name)
            if found is not None:
                return found
        return None

    window = QQuickWindow()
    window.setGeometry(0, 0, 1000, 800)
    factory = QuickSceneFactory()
    context, root = factory.create_display_root(
        owner=window, screen_index=0, runtime_generation=41,
    )
    root.setParent(window.contentItem())
    root.setParentItem(window.contentItem())
    root.setWidth(1000.0); root.setHeight(800.0)
    host_item = visual(root, "ordinaryWidgetHost")
    assert host_item is not None
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item, context=context,
        create_overlay_item=factory.create_overlay_widget,
        create_family_item=factory.create_ordinary_widget_family,
    )
    model = _model()
    geometry = OverlayWidgetGeometry(90.0, 65.0, 600.0, 500.0)
    presentation = RetainedSystemStatsPresentation(host=host, model=model, geometry=geometry)
    edit_root = visual(root, "customLayoutOverlay")
    assert edit_root is not None
    overlay = RetainedCustomLayoutOverlay(edit_root)
    bounds = QRect(90, 65, 600, 500)
    session = CustomLayoutSession()
    descriptor = get_widget_runtime_descriptor("system_stats")
    assert descriptor is not None
    session.add_item(CustomLayoutSessionItem(
        source_key=CustomLayoutKey("system_stats", "display:stats-three-roles"),
        model_identity="system_stats", baseline_global_rect=bounds,
        current_global_rect=bounds, baseline_size_payload={},
        current_size_payload={}, baseline_enabled=True, current_enabled=True,
        custom_child_roles=descriptor.custom_child_roles,
    ))
    messages: list[str] = []
    prior_handler = qInstallMessageHandler(
        lambda _level, _context, message: messages.append(str(message))
    )
    try:
        overlay.bind_session(
            session, display_identity="display:stats-three-roles",
            display_origin=QPoint(0, 0),
            presentation_item_resolver=lambda _item: presentation.item,
        )
        window.show()
        assert overlay.model.selectItem(0)
        qt_app.processEvents()
        frame = visual(edit_root, "customLayoutEditFrame-system_stats")
        assert frame is not None
        assert frame.setProperty("childEditingLocked", False)
        qt_app.processEvents()
        retained = {
            role: visual(edit_root, "customLayoutChildRole-system_stats-" + role)
            for role in ("header", "header_separator", "metric_panels")
        }
        assert all(role is not None for role in retained.values())
        # No old overlap handles can shadow the one useful group edit.
        for retired in ("metric_accents", "metric_labels", "metric_details",
                        "metric_values", "metric_tracks"):
            assert visual(edit_root, "customLayoutChildRole-system_stats-" + retired) is None
        group = retained["metric_panels"]
        target = visual(presentation.item, "systemStatsCustomMetricPanelRoleTarget")
        assert target is not None and group.property("targetItem") == target
        panels = [visual(presentation.item, "systemStats" + suffix + "Panel")
                  for suffix in ("Cpu", "Ram", "Uptime", "Network")]
        assert all(panel is not None for panel in panels)
        first_rects = [(panel.x(), panel.y()) for panel in panels]
        for index in range(16):
            flipped = index % 2 == 1
            assert model.set_custom_child_geometry({
                "header": {"alignment": "right" if flipped else "left"},
                "metric_panels": {
                    "width_scale": 0.95, "height_scale": 0.96,
                    "x_offset": 0.008 + index * 0.0003,
                    "y_offset": 0.006 + index * 0.0002,
                },
            })
            qt_app.processEvents()
            for role_id, role in retained.items():
                assert visual(edit_root, "customLayoutChildRole-system_stats-" + role_id) is role, role_id
            assert group.property("targetItem") == target
            assert group.property("targetReady") is True
            points = [target.mapToItem(frame, x, y) for x, y in (
                (0., 0.), (target.width(), 0.), (0., target.height()),
                (target.width(), target.height()),
            )]
            rect = (min(p.x() for p in points), min(p.y() for p in points),
                    max(p.x() for p in points), max(p.y() for p in points))
            assert (group.x(), group.y(), group.width(), group.height()) == pytest.approx(
                (rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]), abs=0.02
            )
            assert [panel.x() for panel in panels] == pytest.approx([target.x()] * 4)
            assert panels[0].y() == pytest.approx(target.y())
            assert panels[-1].y() + panels[-1].height() == pytest.approx(
                target.y() + target.height()
            )
        assert panels[0].x() != pytest.approx(first_rects[0][0])
        assert panels[0].y() != pytest.approx(first_rects[0][1])
        overlay.clear_session()
        qt_app.processEvents()
        assert visual(edit_root, "customLayoutChildRole-system_stats-metric_panels") is None
        assert not [msg for msg in messages if "CustomLayoutOverlay.qml" in msg and (
            "Binding loop" in msg or "non-bindable" in msg
        )], messages[:8]
    finally:
        qInstallMessageHandler(prior_handler)
        overlay.clear_session()
        host.retire_all()
        window.hide()
        root.setParentItem(None); root.setParent(None); root.deleteLater()
        context.deleteLater(); factory.deleteLater(); window.deleteLater()
        qt_app.processEvents()

@pytest.mark.qt
def test_system_stats_y_only_reflow_preserves_panel_size_and_corner_uniform_scale(qt_app) -> None:
    """An outer Y-side handle must not become a uniform resize or reflow feedback loop."""
    model = _model()
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(QML_ROOT / "SystemStatsPresentation.qml"))
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    item = component.createWithInitialProperties({"systemStatsModel": model})
    assert isinstance(item, QQuickItem)
    width, height = float(model.authoredWidth), float(model.authoredHeight)
    item.setWidth(width)
    item.setHeight(height)
    cpu = item.findChild(QQuickItem, "systemStatsCpuPanel")
    assert cpu is not None
    try:
        qt_app.processEvents()
        baseline = (cpu.width(), cpu.height())
        assert not bool(item.property("uniformScaleTransform"))
        for logical_height in (350., 280., 240., 190., 280., height):
            if logical_height != height:
                assert model.set_content_extent(width, logical_height)
            else:
                assert model.clear_content_extent()
            item.setHeight(logical_height)
            qt_app.processEvents()
            assert not bool(item.property("uniformScaleTransform"))
            assert float(item.property("presentationScale")) == pytest.approx(1.0)
            assert (cpu.width(), cpu.height()) == pytest.approx(baseline, abs=0.02)
            assert item.width() == pytest.approx(width)
            assert float(model.authoredHeight) == pytest.approx(logical_height)
        # Corner/wheel scale retains the existing single authored-scene scale.
        model.set_content_extent(width, 280.)
        item.setHeight(280.)
        item.setWidth(width * 1.25)
        item.setHeight(350.)
        qt_app.processEvents()
        assert bool(item.property("uniformScaleTransform"))
        assert float(item.property("presentationScale")) == pytest.approx(1.25, abs=0.002)
        assert (cpu.width(), cpu.height()) == pytest.approx(baseline, abs=0.02)
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        model.retire()
        qt_app.processEvents()
