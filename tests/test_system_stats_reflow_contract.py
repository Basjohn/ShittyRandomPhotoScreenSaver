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
    assert 'content_extent_minimum_size=(440, 190)' in block

    model = _text("rendering/quick/widgets/system_stats.py")
    assert "resolved_height = max(190, min(3000, resolved_height))" in model
    assert "def set_content_extent(" in model
    assert 'payload.get("content_extent")' in model
    assert "set_custom_layout_size_payload_handler" in model

    qml = _text("rendering/quick/qml/SystemStatsPresentation.qml")
    assert "visibleMetricCount" in qml
    assert "metricPanelHeight" in qml
    assert "Math.max(statsRoot.systemStatsModel.baseAuthoredHeight," in qml
    # Reuse the canonical shared content-root transform, never guess gesture
    # type from asynchronous outer/logical width and height snapshots.
    assert "uniformScaleTransform: true" in qml
    assert "Math.abs(width - systemStatsModel.authoredWidth) > 0.5" not in qml
    assert "contentExtentChanged = Signal()" in model
    assert "@Property(float, notify=contentExtentChanged)" in model
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


def test_system_stats_metrics_are_one_editable_stack_with_authored_flipped_children() -> None:
    """No ghost targets, per-metric handles, timer or alternate geometry authority."""
    qml = _text("rendering/quick/qml/SystemStatsPresentation.qml")
    descriptor = _text("rendering/widget_descriptors.py")
    stats = descriptor.split('widget_id="system_stats"', 1)[1].split(
        'WidgetRuntimeDescriptor(', 1
    )[0]
    assert stats.count('freeform_layout_block_child_role(') == 2
    for id_ in ("header", "header_separator", "metric_panels"):
        assert f'"roleId": "{id_}"' in qml
    for id_ in ("metric_accents", "metric_labels", "metric_details",
                "metric_values", "metric_tracks"):
        assert f'"roleId": "{id_}"' not in qml
        assert f'"{id_}",' not in stats
        for helper in ("childOffsetX", "childOffsetY", "childWidthScale",
                       "childHeightScale", "childAlignment"):
            assert f'{helper}("{id_}")' not in qml
    assert qml.count('objectName: "systemStatsCustomMetricPanelRoleTarget"') == 1
    assert 'metricGap: canonicalMetricGap * childHeightScale("metric_panels")' in qml
    assert "visibleMetricCount * metricPanelHeight" in qml
    assert "visibleMetricCount - 1) * metricGap" in qml
    assert "paintedMetricCount" in qml
    assert "metricPaintBottom" in qml
    # The shared OverlayCard puts family children inside its padded content.
    # Root-space paint bounds must be translated into content-local bounds
    # before panel admission and the single group Edit target are evaluated.
    assert "metricContentPaintBottom" in qml
    assert "metricPaintBottom - statsRoot.cardPadding" in qml
    assert "bottom > metricContentPaintBottom + 0.01" in qml
    assert "authoredMetricStackHeight, metricContentPaintBottom - representativePanelY" in qml
    assert "height: statsRoot.visibleMetricStackHeight" in qml
    assert qml.count("function metricRoleX(roleId, panelWidth, roleWidth)") == 1
    # Every real metric still shares the same QML flip rails, with no extra
    # delegate for its label, value, accent, detail or track.
    for id_ in ("metric_accents", "metric_labels", "metric_details",
                "metric_values", "metric_tracks"):
        assert qml.count(f'statsRoot.metricRoleX("{id_}", panel.width, width)') == 1
    for forbidden in ("Timer {", "Connections {", "Qt.callLater", "SettingsManager"):
        assert forbidden not in qml, forbidden
