"""Source-level contracts for the bounded 2026-09-02 theme completion slice."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_abandonment_backlog_accent_inherits_widget_accent_with_explicit_override() -> None:
    roles = _text("ui/widget_visual_roles.py")
    abandonment = _text("rendering/quick/widgets/abandonment_issues.py")

    assert '"abandonment_issues.accent": "widget.accent"' in roles
    assert 'resolve_rgba_role(\n            "abandonment_issues.accent"' in abandonment
    assert "explicit=accent_override" in abandonment

    presentation = _text("rendering/quick/qml/AbandonmentIssuesPresentation.qml")
    # The archive/BACKLOG block owns the accent. The label must remain on the
    # ordinary theme text semantic so accent-on-accent themes stay readable.
    assert "fillColor: Qt.rgba(" in presentation
    assert "abandonmentRoot.abandonmentModel.accentColor.r" in presentation
    assert "color: abandonmentRoot.abandonmentModel.textColor" in presentation


def test_reddit_age_column_aligns_first_value_digit_and_fixed_ago_suffix() -> None:
    reddit = _text("rendering/quick/qml/RedditPresentation.qml")

    assert 'objectName: "redditPostAgeValue_" + postRow.index' in reddit
    assert 'objectName: "redditPostAgeAgo_" + postRow.index' in reddit
    assert 'text: "AGO"' in reddit
    assert "horizontalAlignment: Text.AlignLeft" in reddit
    assert "horizontalAlignment: Text.AlignRight" in reddit
    assert "anchors.left: parent.left" in reddit
    assert "anchors.right: parent.right" in reddit
    # Keep the AGO suffixes mutually aligned while nudging the whole suffix
    # column three pixels left from the age-field edge.
    assert "anchors.rightMargin: 3.0" in reddit
    assert "anchors.leftMargin: 4.0" in reddit


def test_context_submenu_has_event_driven_pointer_corridor_without_timer_owner() -> None:
    menu = _text("rendering/quick/qml/ContextMenu.qml")

    assert "id: submenuPointerCorridor" in menu
    assert "id: submenuCorridorHover" in menu
    assert "!submenuCorridorHover.hovered" in menu
    assert "Qt.callLater(function()" in menu
    assert "Timer {" not in menu


def test_foundry_widget_export_uses_shared_counterpart_authority() -> None:
    foundry = _text("tools/theme_foundry.py")
    generator = _text("tools/generate_widget_theme_mirrors.py")

    assert 'QPushButton("Save Widget Counterpart…")' in foundry
    assert "def save_widget_counterpart(self) -> None:" in foundry
    assert "widget_counterpart_for_settings_theme(" in foundry
    assert "save_widget_theme_file(widget_theme, path)" in foundry
    assert "load_widget_theme_file(path)" in foundry
    assert "def widget_counterpart_for_settings_theme(" in generator
    assert generator.count("widget_counterpart_for_settings_theme(") >= 3


def test_widget_counterparts_materialize_mature_media_and_backlog_roles() -> None:
    generator = _text("tools/generate_widget_theme_mirrors.py")
    for role in (
        "media.transport.surface",
        "media.transport.border",
        "media.transport.separator",
        "media.transport.icon",
        "media.mute.surface",
        "media.mute.border",
        "media.mute.inner_border",
        "media.mute.icon",
        "media.mute.muted_icon",
        "media.volume.track",
        "media.volume.fill",
        "media.volume.outline",
        "media.progress.track",
        "media.progress.fill",
        "media.progress.glow",
        "media.progress.shadow",
        "abandonment_issues.accent",
    ):
        assert f'"{role}"' in generator


def test_settings_theme_switch_has_event_driven_listener_timing_diagnostics() -> None:
    source = _text(ROOT / "ui" / "settings_theme_runtime.py")
    assert "perf_counter_ns" in source
    assert '"[PERF][SETTINGS_THEME] theme=%s total=%.2fms listeners=[%s]"' in source
    assert "for listener in listeners:" in source
    assert "QTimer" not in source
    assert "threading.Timer" not in source


def test_theme_selection_handler_has_bounded_transaction_timing() -> None:
    source = _text(ROOT / "ui" / "tabs" / "themes_tab.py")
    assert "perf_counter_ns" in source
    assert '"[PERF][THEME_SELECT] source=settings theme=%s linked=%s total=%.2fms"' in source
    assert '"[PERF][THEME_SELECT] source=widget theme=%s linked=True total=%.2fms"' in source
    assert '"[PERF][THEME_SELECT] source=widget theme=%s linked=False total=%.2fms"' in source
