"""Settings surface for the durable general Feeds family.

F2 intentionally exposes only CUSTOM 1.  Additional bounded custom slots and
NEWS categories are already reserved by neutral family identity but remain
fully dormant until their later slices are implemented.

Network work is explicit only: editing a URL never probes it.  TEST FEED runs
the production bounded transport/parser off the GUI thread and does not mutate
the runtime cache.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Any
import weakref

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import Shiboken

from core.logging.logger import get_logger
from core.resources.manager import ResourceManager
from core.threading.manager import ThreadManager
from rendering.widget_descriptors import get_widget_position_option_labels
from ui.tabs.shared_styles import (
    STATUS_LABEL_STYLE,
    add_aligned_row,
    build_bucket_toggle,
    finalize_bucket_body,
    style_group_box,
)
from ui.widgets import StyledComboBox, StyledFontComboBox

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab

logger = get_logger(__name__)
_LABEL_WIDTH = 150
_VIEW_TO_LABEL = {"list": "List", "grid": "Grid", "compact": "Compact Headlines"}
_LABEL_TO_VIEW = {label: value for value, label in _VIEW_TO_LABEL.items()}


def _get_feed_thread_manager(tab: "WidgetsTab") -> ThreadManager:
    manager = getattr(tab, "_feeds_thread_manager", None)
    if manager is None:
        manager = ThreadManager.get_app_shared()
        owns_manager = manager is None
        if manager is None:
            manager = ThreadManager.create_helper_manager(
                resource_manager=ResourceManager.get_app_shared(),
            )
        tab._feeds_thread_manager = manager
        if owns_manager:
            try:
                tab.destroyed.connect(lambda _obj=None, m=manager: m.shutdown(wait=False))
            except Exception as exc:
                logger.debug("[FEEDS_TAB] Failed to attach helper cleanup: %s", exc)
    return manager


def _set_controls_visible(tab: "WidgetsTab") -> None:
    container = getattr(tab, "_feeds_custom1_controls_container", None)
    checkbox = getattr(tab, "feeds_custom1_enabled", None)
    if container is not None:
        container.setVisible(bool(checkbox is not None and checkbox.isChecked()))


def _opacity_percent(tab: "WidgetsTab", values: Mapping[str, Any], key: str) -> int:
    canonical = float(tab._widget_default("feeds_custom_1", key))
    raw = values.get(key, canonical)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = canonical
    return max(0, min(100, int(round(value * 100.0))))


def _set_view_combo(tab: "WidgetsTab", value: object) -> None:
    normalized = str(value or "").strip().casefold()
    label = _VIEW_TO_LABEL.get(normalized)
    if label is None:
        canonical = tab._default_str("feeds_custom_1", "view_mode").strip().casefold()
        label = _VIEW_TO_LABEL[canonical]
    tab._set_combo_text(tab.feeds_custom1_view_mode, label)


def _probe_summary(result: object) -> tuple[bool, str]:
    ok = bool(getattr(result, "ok", False))
    if not ok:
        failure = str(getattr(result, "failure", "") or "Feed could not be validated")
        return False, f"FAILED · {failure[:180]}"
    fmt = str(getattr(result, "format", "feed") or "feed").upper()
    count = int(getattr(result, "item_count", 0) or 0)
    actionable = int(getattr(result, "actionable_count", 0) or 0)
    images = int(getattr(result, "image_count", 0) or 0)
    newest = getattr(result, "newest_unix", None)
    newest_text = ""
    if newest:
        try:
            newest_text = " · newest " + datetime.fromtimestamp(int(newest)).strftime("%Y-%m-%d %H:%M")
        except Exception:
            newest_text = ""
    return True, f"OK · {fmt} · {count} items · {actionable} links · {images} with images{newest_text}"


def _test_feed(tab: "WidgetsTab") -> None:
    url = str(tab.feeds_custom1_url.text() or "").strip()
    if not url:
        tab.feeds_custom1_test_status.setText("Enter a feed URL first.")
        return
    generation = int(getattr(tab, "_feeds_probe_generation", 0)) + 1
    tab._feeds_probe_generation = generation
    tab.feeds_custom1_test_button.setEnabled(False)
    tab.feeds_custom1_test_status.setText("Testing with bounded production parser…")
    tab_ref = weakref.ref(tab)

    def _work():
        from core.feeds.probe import probe_feed_url
        return probe_feed_url(url)

    def _finished(task_result: object) -> None:
        def _apply() -> None:
            owner = tab_ref()
            if owner is None or not Shiboken.isValid(owner):
                return
            if getattr(owner, "_feeds_probe_generation", None) != generation:
                return
            owner.feeds_custom1_test_button.setEnabled(True)
            if bool(getattr(task_result, "success", False)):
                ok, text = _probe_summary(getattr(task_result, "result", None))
            else:
                ok, text = False, "FAILED · feed test task failed"
            owner.feeds_custom1_test_status.setText(text)
            owner.feeds_custom1_test_status.setProperty("feedProbeOk", bool(ok))

        ThreadManager.run_on_ui_thread(_apply)

    try:
        _get_feed_thread_manager(tab).submit_io_task(
            _work,
            task_id=f"feeds_custom1_probe_{generation}",
            callback=_finished,
        )
    except Exception as exc:
        logger.warning("[FEEDS_TAB] Failed to submit explicit feed probe: %s", exc)
        tab.feeds_custom1_test_button.setEnabled(True)
        tab.feeds_custom1_test_status.setText("FAILED · feed test could not start")


def build_feeds_ui(tab: "WidgetsTab", layout: QVBoxLayout) -> QWidget:
    group = QGroupBox("Feeds")
    style_group_box(group)
    root = QVBoxLayout(group)
    root.setContentsMargins(16, 18, 16, 16)
    root.setSpacing(14)

    intro = QLabel(
        "CUSTOM feeds accept RSS or Atom. Runtime is cache-first and preserves the last good "
        "snapshot across temporary source failures. URL testing is explicit and never runs while typing."
    )
    intro.setWordWrap(True)
    root.addWidget(intro)

    tab.feeds_custom1_enabled = QCheckBox("Enable Custom 1")
    tab.feeds_custom1_enabled.setProperty("circleIndicator", True)
    tab.feeds_custom1_enabled.setChecked(tab._default_bool("feeds_custom_1", "enabled"))
    tab.feeds_custom1_enabled.stateChanged.connect(tab._save_settings)
    tab.feeds_custom1_enabled.stateChanged.connect(tab._update_stack_status)
    root.addWidget(tab.feeds_custom1_enabled)

    tab._feeds_custom1_controls_container = QWidget()
    controls = QVBoxLayout(tab._feeds_custom1_controls_container)
    controls.setContentsMargins(0, 0, 0, 8)
    controls.setSpacing(12)

    source_toggle, source_body, source_layout = build_bucket_toggle(
        controls,
        "Source",
        expanded=tab.get_widget_bucket_state("feeds", "custom1_source"),
        on_toggle=lambda checked: tab.set_widget_bucket_state("feeds", "custom1_source", checked),
        defer_initial_visibility=True,
    )

    row, _ = add_aligned_row(source_layout, "Name:", label_width=_LABEL_WIDTH)
    tab.feeds_custom1_name = QLineEdit()
    tab.feeds_custom1_name.setMaxLength(80)
    tab.feeds_custom1_name.setText(tab._default_str("feeds_custom_1", "name"))
    tab.feeds_custom1_name.editingFinished.connect(tab._save_settings)
    row.addWidget(tab.feeds_custom1_name, 1)

    row, _ = add_aligned_row(source_layout, "Feed URL:", label_width=_LABEL_WIDTH)
    tab.feeds_custom1_url = QLineEdit()
    tab.feeds_custom1_url.setMaxLength(8192)
    tab.feeds_custom1_url.setPlaceholderText("https://example.com/feed.xml")
    tab.feeds_custom1_url.setText(tab._default_str("feeds_custom_1", "feed_url"))
    tab.feeds_custom1_url.editingFinished.connect(tab._save_settings)
    row.addWidget(tab.feeds_custom1_url, 1)

    probe_row = QHBoxLayout()
    probe_row.setContentsMargins(_LABEL_WIDTH + 12, 0, 0, 0)
    tab.feeds_custom1_test_button = QPushButton("TEST FEED")
    tab.feeds_custom1_test_button.clicked.connect(lambda: _test_feed(tab))
    probe_row.addWidget(tab.feeds_custom1_test_button)
    tab.feeds_custom1_test_status = QLabel("Not tested in this Settings session.")
    tab.feeds_custom1_test_status.setWordWrap(True)
    probe_row.addWidget(tab.feeds_custom1_test_status, 1)
    source_layout.addLayout(probe_row)
    finalize_bucket_body(source_toggle, source_body)

    content_toggle, content_body, content_layout = build_bucket_toggle(
        controls,
        "Content & Refresh",
        expanded=tab.get_widget_bucket_state("feeds", "custom1_content"),
        on_toggle=lambda checked: tab.set_widget_bucket_state("feeds", "custom1_content", checked),
        defer_initial_visibility=True,
    )
    row, _ = add_aligned_row(content_layout, "Display Type:", label_width=_LABEL_WIDTH)
    tab.feeds_custom1_view_mode = StyledComboBox()
    tab.feeds_custom1_view_mode.addItems(list(_VIEW_TO_LABEL.values()))
    _set_view_combo(tab, tab._default_str("feeds_custom_1", "view_mode"))
    tab.feeds_custom1_view_mode.currentTextChanged.connect(tab._save_settings)
    row.addWidget(tab.feeds_custom1_view_mode)
    row.addStretch()

    row, _ = add_aligned_row(content_layout, "Max Items:", label_width=_LABEL_WIDTH)
    tab.feeds_custom1_item_limit = QSpinBox()
    tab.feeds_custom1_item_limit.setRange(3, 40)
    tab.feeds_custom1_item_limit.setValue(tab._default_int("feeds_custom_1", "item_limit"))
    tab.feeds_custom1_item_limit.valueChanged.connect(tab._save_settings)
    tab.feeds_custom1_item_limit.valueChanged.connect(tab._update_stack_status)
    row.addWidget(tab.feeds_custom1_item_limit)
    row.addStretch()

    row, _ = add_aligned_row(content_layout, "Refresh:", label_width=_LABEL_WIDTH)
    tab.feeds_custom1_refresh_minutes = QSpinBox()
    tab.feeds_custom1_refresh_minutes.setRange(5, 1440)
    tab.feeds_custom1_refresh_minutes.setSuffix(" min")
    tab.feeds_custom1_refresh_minutes.setValue(tab._default_int("feeds_custom_1", "refresh_minutes"))
    tab.feeds_custom1_refresh_minutes.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.feeds_custom1_refresh_minutes)
    row.addStretch()

    tab.feeds_custom1_show_images = QCheckBox("Show Locally Cached Article Images")
    tab.feeds_custom1_show_images.setProperty("circleIndicator", True)
    tab.feeds_custom1_show_images.setChecked(tab._default_bool("feeds_custom_1", "show_images"))
    tab.feeds_custom1_show_images.stateChanged.connect(tab._save_settings)
    content_layout.addWidget(tab.feeds_custom1_show_images)

    tab.feeds_custom1_show_subtitle = QCheckBox("Show Feed Subtitle")
    tab.feeds_custom1_show_subtitle.setProperty("circleIndicator", True)
    tab.feeds_custom1_show_subtitle.setChecked(tab._default_bool("feeds_custom_1", "show_subtitle"))
    tab.feeds_custom1_show_subtitle.setToolTip(
        "Show the feed/publisher title as small metadata below the branded header when it differs from the configured name."
    )
    tab.feeds_custom1_show_subtitle.stateChanged.connect(tab._save_settings)
    content_layout.addWidget(tab.feeds_custom1_show_subtitle)
    finalize_bucket_body(content_toggle, content_body)

    layout_toggle, layout_body, layout_controls = build_bucket_toggle(
        controls,
        "Layout & Typography",
        expanded=tab.get_widget_bucket_state("feeds", "custom1_layout"),
        on_toggle=lambda checked: tab.set_widget_bucket_state("feeds", "custom1_layout", checked),
        defer_initial_visibility=True,
    )

    row, _ = add_aligned_row(layout_controls, "Position:", label_width=_LABEL_WIDTH)
    tab.feeds_custom1_position = StyledComboBox()
    tab.feeds_custom1_position.addItems(list(get_widget_position_option_labels("feeds_custom_1")))
    tab._set_combo_text(tab.feeds_custom1_position, tab._default_str("feeds_custom_1", "position"))
    tab.feeds_custom1_position.currentTextChanged.connect(tab._save_settings)
    tab.feeds_custom1_position.currentTextChanged.connect(tab._update_stack_status)
    row.addWidget(tab.feeds_custom1_position)
    tab.feeds_custom1_stack_status = QLabel("")
    tab.feeds_custom1_stack_status.setStyleSheet(STATUS_LABEL_STYLE)
    row.addWidget(tab.feeds_custom1_stack_status)
    row.addStretch()

    row, _ = add_aligned_row(layout_controls, "Display:", label_width=_LABEL_WIDTH)
    tab.feeds_custom1_monitor_combo = StyledComboBox(size_variant="compact")
    tab.feeds_custom1_monitor_combo.addItems(["ALL", "1", "2", "3"])
    tab._set_combo_text(tab.feeds_custom1_monitor_combo, str(tab._widget_default("feeds_custom_1", "monitor")))
    tab.feeds_custom1_monitor_combo.currentTextChanged.connect(tab._save_settings)
    tab.feeds_custom1_monitor_combo.currentTextChanged.connect(tab._update_stack_status)
    row.addWidget(tab.feeds_custom1_monitor_combo)
    row.addStretch()

    row, _ = add_aligned_row(layout_controls, "Margin:", label_width=_LABEL_WIDTH)
    tab.feeds_custom1_margin = QSpinBox()
    tab.feeds_custom1_margin.setRange(0, 300)
    tab.feeds_custom1_margin.setSuffix(" px")
    tab.feeds_custom1_margin.setValue(tab._default_int("feeds_custom_1", "margin"))
    tab.feeds_custom1_margin.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.feeds_custom1_margin)
    row.addStretch()

    row, _ = add_aligned_row(layout_controls, "Font:", label_width=_LABEL_WIDTH)
    tab.feeds_custom1_font_combo = StyledFontComboBox(size_variant="hero")
    tab.feeds_custom1_font_combo.setCurrentFont(QFont(tab._default_str("feeds_custom_1", "font_family")))
    tab.feeds_custom1_font_combo.currentFontChanged.connect(tab._save_settings)
    row.addWidget(tab.feeds_custom1_font_combo)
    row.addStretch()

    row, _ = add_aligned_row(layout_controls, "Font Size:", label_width=_LABEL_WIDTH)
    tab.feeds_custom1_font_size = QSpinBox()
    tab.feeds_custom1_font_size.setRange(8, 48)
    tab.feeds_custom1_font_size.setValue(tab._default_int("feeds_custom_1", "font_size"))
    tab.feeds_custom1_font_size.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.feeds_custom1_font_size)
    row.addStretch()

    row, _ = add_aligned_row(layout_controls, "Authored Width:", label_width=_LABEL_WIDTH)
    tab.feeds_custom1_preferred_width = QSpinBox()
    tab.feeds_custom1_preferred_width.setRange(320, 1600)
    tab.feeds_custom1_preferred_width.setSuffix(" px")
    tab.feeds_custom1_preferred_width.setValue(tab._default_int("feeds_custom_1", "preferred_width"))
    tab.feeds_custom1_preferred_width.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.feeds_custom1_preferred_width)
    row.addStretch()

    row, _ = add_aligned_row(layout_controls, "Authored Height:", label_width=_LABEL_WIDTH)
    tab.feeds_custom1_preferred_height = QSpinBox()
    tab.feeds_custom1_preferred_height.setRange(180, 1800)
    tab.feeds_custom1_preferred_height.setSuffix(" px")
    tab.feeds_custom1_preferred_height.setValue(tab._default_int("feeds_custom_1", "preferred_height"))
    tab.feeds_custom1_preferred_height.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.feeds_custom1_preferred_height)
    row.addStretch()
    finalize_bucket_body(layout_toggle, layout_body)

    appearance_toggle, appearance_body, appearance_layout = build_bucket_toggle(
        controls,
        "Appearance",
        expanded=tab.get_widget_bucket_state("feeds", "custom1_appearance"),
        on_toggle=lambda checked: tab.set_widget_bucket_state("feeds", "custom1_appearance", checked),
        defer_initial_visibility=True,
    )
    tab.feeds_custom1_show_background = QCheckBox("Show Card Background")
    tab.feeds_custom1_show_background.setProperty("circleIndicator", True)
    tab.feeds_custom1_show_background.setChecked(tab._default_bool("feeds_custom_1", "show_background"))
    tab.feeds_custom1_show_background.stateChanged.connect(tab._save_settings)
    appearance_layout.addWidget(tab.feeds_custom1_show_background)

    row, _ = add_aligned_row(appearance_layout, "Background Opacity:", label_width=_LABEL_WIDTH)
    tab.feeds_custom1_bg_opacity = QSpinBox()
    tab.feeds_custom1_bg_opacity.setRange(0, 100)
    tab.feeds_custom1_bg_opacity.setSuffix(" %")
    tab.feeds_custom1_bg_opacity.setValue(int(round(float(tab._widget_default("feeds_custom_1", "bg_opacity")) * 100.0)))
    tab.feeds_custom1_bg_opacity.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.feeds_custom1_bg_opacity)
    row.addStretch()

    row, _ = add_aligned_row(appearance_layout, "Border Opacity:", label_width=_LABEL_WIDTH)
    tab.feeds_custom1_border_opacity = QSpinBox()
    tab.feeds_custom1_border_opacity.setRange(0, 100)
    tab.feeds_custom1_border_opacity.setSuffix(" %")
    tab.feeds_custom1_border_opacity.setValue(int(round(float(tab._widget_default("feeds_custom_1", "border_opacity")) * 100.0)))
    tab.feeds_custom1_border_opacity.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.feeds_custom1_border_opacity)
    row.addStretch()
    finalize_bucket_body(appearance_toggle, appearance_body)

    controls.addStretch()
    root.addWidget(tab._feeds_custom1_controls_container)
    tab.feeds_custom1_enabled.stateChanged.connect(lambda: _set_controls_visible(tab))
    _set_controls_visible(tab)

    note = QLabel("CUSTOM 2–4 and NEWS categories are reserved but deliberately dormant until later Feeds gates land.")
    note.setWordWrap(True)
    root.addWidget(note)

    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 20, 0, 0)
    container_layout.addWidget(group)
    return container


def load_feeds_settings(tab: "WidgetsTab", widgets: Mapping[str, Any]) -> None:
    values = widgets.get("feeds_custom_1", {})
    if not isinstance(values, Mapping):
        values = {}
    tab.feeds_custom1_enabled.setChecked(tab._config_bool("feeds_custom_1", values, "enabled"))
    tab.feeds_custom1_name.setText(tab._config_str("feeds_custom_1", values, "name"))
    tab.feeds_custom1_url.setText(tab._config_str("feeds_custom_1", values, "feed_url"))
    _set_view_combo(tab, values.get("view_mode", tab._widget_default("feeds_custom_1", "view_mode")))
    tab.feeds_custom1_item_limit.setValue(tab._config_int("feeds_custom_1", values, "item_limit"))
    tab.feeds_custom1_refresh_minutes.setValue(tab._config_int("feeds_custom_1", values, "refresh_minutes"))
    tab.feeds_custom1_show_images.setChecked(tab._config_bool("feeds_custom_1", values, "show_images"))
    tab.feeds_custom1_show_subtitle.setChecked(tab._config_bool("feeds_custom_1", values, "show_subtitle"))
    tab._set_combo_text(tab.feeds_custom1_position, tab._config_str("feeds_custom_1", values, "position"))
    tab._set_combo_text(
        tab.feeds_custom1_monitor_combo,
        str(values.get("monitor", tab._widget_default("feeds_custom_1", "monitor"))),
    )
    tab.feeds_custom1_margin.setValue(tab._config_int("feeds_custom_1", values, "margin"))
    tab.feeds_custom1_font_combo.setCurrentFont(QFont(tab._config_str("feeds_custom_1", values, "font_family")))
    tab.feeds_custom1_font_size.setValue(tab._config_int("feeds_custom_1", values, "font_size"))
    tab.feeds_custom1_preferred_width.setValue(tab._config_int("feeds_custom_1", values, "preferred_width"))
    tab.feeds_custom1_preferred_height.setValue(tab._config_int("feeds_custom_1", values, "preferred_height"))
    tab.feeds_custom1_show_background.setChecked(tab._config_bool("feeds_custom_1", values, "show_background"))
    tab.feeds_custom1_bg_opacity.setValue(_opacity_percent(tab, values, "bg_opacity"))
    tab.feeds_custom1_border_opacity.setValue(_opacity_percent(tab, values, "border_opacity"))
    tab.feeds_custom1_test_status.setText("Not tested in this Settings session.")
    _set_controls_visible(tab)


def save_feeds_settings(tab: "WidgetsTab") -> dict[str, Any]:
    defaults = tab._widget_defaults.get("feeds_custom_1")
    if not isinstance(defaults, Mapping):
        raise KeyError("Canonical widget defaults are missing widgets.feeds_custom_1")
    payload = dict(defaults)
    view_mode = _LABEL_TO_VIEW.get(tab.feeds_custom1_view_mode.currentText())
    if view_mode is None:
        view_mode = str(defaults["view_mode"])
    payload.update(
        {
            "enabled": bool(tab.feeds_custom1_enabled.isChecked()),
            "name": str(tab.feeds_custom1_name.text() or "").strip()[:80] or str(defaults["name"]),
            "feed_url": str(tab.feeds_custom1_url.text() or "").strip()[:8192],
            "view_mode": view_mode,
            "item_limit": int(tab.feeds_custom1_item_limit.value()),
            "refresh_minutes": int(tab.feeds_custom1_refresh_minutes.value()),
            "show_images": bool(tab.feeds_custom1_show_images.isChecked()),
            "show_subtitle": bool(tab.feeds_custom1_show_subtitle.isChecked()),
            "position": tab.feeds_custom1_position.currentText(),
            "monitor": tab._monitor_value_from_combo("feeds_custom_1", tab.feeds_custom1_monitor_combo),
            "margin": int(tab.feeds_custom1_margin.value()),
            "font_family": tab.feeds_custom1_font_combo.currentFont().family(),
            "font_size": int(tab.feeds_custom1_font_size.value()),
            "preferred_width": int(tab.feeds_custom1_preferred_width.value()),
            "preferred_height": int(tab.feeds_custom1_preferred_height.value()),
            "show_background": bool(tab.feeds_custom1_show_background.isChecked()),
            "bg_opacity": float(tab.feeds_custom1_bg_opacity.value()) / 100.0,
            "border_opacity": float(tab.feeds_custom1_border_opacity.value()) / 100.0,
        }
    )
    return payload


__all__ = ["build_feeds_ui", "load_feeds_settings", "save_feeds_settings"]
