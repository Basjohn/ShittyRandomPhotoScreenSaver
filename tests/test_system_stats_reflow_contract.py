from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_system_stats_defaults_and_settings_expose_metric_selection() -> None:
    defaults = json.loads(_text("core/settings/defaults_snapshot.json"))["widgets"]["system_stats"]
    assert {
        "show_cpu": True,
        "show_memory": True,
        "show_uptime": True,
        "show_network": True,
    }.items() <= defaults.items()
    settings = _text("ui/tabs/widgets_tab_system_stats.py")
    for attr in (
        "system_stats_show_cpu",
        "system_stats_show_memory",
        "system_stats_show_uptime",
        "system_stats_show_network",
    ):
        assert attr in settings


def test_system_stats_uses_shared_content_extent_reflow_contract() -> None:
    descriptors = _text("rendering/widget_descriptors.py")
    start = descriptors.index('widget_id="system_stats"')
    block = descriptors[start:descriptors.index('WidgetRuntimeDescriptor(', start + 20)]
    assert 'content_extent_axes=("horizontal", "vertical")' in block

    model = _text("rendering/quick/widgets/system_stats.py")
    assert "def set_content_extent(" in model
    assert 'payload.get("content_extent")' in model
    assert "set_custom_layout_size_payload_handler" in model

    qml = _text("rendering/quick/qml/SystemStatsPresentation.qml")
    assert "visibleMetricCount" in qml
    assert "metricPanelHeight" in qml
    assert "valueLaneWidth" in qml
    assert "systemStatsModel.showCpu" in qml
    assert "systemStatsModel.showMemory" in qml
    assert "systemStatsModel.showUptime" in qml
    assert "systemStatsModel.showNetwork" in qml
    assert "border.width: statsRoot.scaleAwareStrokeWidth(1.25)" in qml


def test_widgets_nav_pills_reserve_full_label_width() -> None:
    widgets_tab = _text("ui/tabs/widgets_tab.py")
    assert "horizontalAdvance(descriptor.button_label)" in widgets_tab
    assert "button.setMinimumWidth(max(70, label_width + 40))" in widgets_tab


def test_system_stats_metric_selection_skips_disabled_source_reads() -> None:
    source = _text("core/system_stats/source.py")
    services = _text("rendering/widget_runtime_services.py")
    assert "sample_cpu: bool = True" in source
    assert 'else ("disabled", None)' in source
    assert '"sample_network": selected("show_network")' in services
    assert "WholeSystemCpuRamSource(**metric_selection)" in services
