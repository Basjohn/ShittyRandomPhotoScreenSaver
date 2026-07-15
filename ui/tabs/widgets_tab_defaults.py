"""General widget section for WidgetsTab (internal section id: defaults)."""
from __future__ import annotations

import weakref
from pathlib import Path
from typing import TYPE_CHECKING, Mapping

from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.cache_maintenance import (
    CacheClearResult,
    CacheFamilyDescriptor,
    clear_cache_families,
    get_cache_family_descriptors,
)
from core.logging.logger import get_logger
from core.resources.manager import ResourceManager
from core.threading.manager import ThreadManager
from ui.styled_popup import StyledPopup
from ui.tabs.shared_styles import (
    FORM_ROW_LABEL_STYLE,
    INFO_LABEL_STYLE,
    add_aligned_row,
    build_bucket_toggle,
    style_group_box,
)

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab

logger = get_logger(__name__)

_ACTION_BUTTON_STYLE = """
QPushButton {
    background-color: rgba(255, 255, 255, 18);
    color: white;
    border: 1px solid rgba(255, 255, 255, 92);
    border-radius: 16px;
    padding: 0 16px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: rgba(255, 255, 255, 30);
    border-color: rgba(255, 255, 255, 132);
}
QPushButton:pressed {
    background-color: rgba(255, 255, 255, 42);
}
QPushButton:disabled {
    color: rgba(255, 255, 255, 90);
    background-color: rgba(255, 255, 255, 8);
    border-color: rgba(255, 255, 255, 35);
}
"""


def _finalize_bucket_body(toggle, body: QWidget) -> None:
    expanded = bool(toggle.isChecked())
    if body.isHidden() == expanded:
        body.setVisible(expanded)


def _settings_app_data_dir(tab: WidgetsTab) -> Path | None:
    storage_path = getattr(getattr(tab, "_settings", None), "_storage_path", None)
    if storage_path is None:
        return None
    try:
        return Path(storage_path).resolve().parent
    except (OSError, RuntimeError, TypeError, ValueError):
        return None


def _get_cache_thread_manager(tab: WidgetsTab) -> ThreadManager:
    manager = getattr(tab, "_general_cache_thread_manager", None)
    if manager is not None:
        return manager
    manager = ThreadManager.get_app_shared()
    owns_manager = manager is None
    if manager is None:
        manager = ThreadManager.create_helper_manager(
            resource_manager=ResourceManager.get_app_shared(),
        )
    tab._general_cache_thread_manager = manager
    if owns_manager:
        try:
            tab.destroyed.connect(lambda _obj=None, owned=manager: owned.shutdown(wait=False))
        except Exception:
            pass
    return manager


def _selected_cache_ids(tab: WidgetsTab) -> tuple[str, ...]:
    checks = getattr(tab, "cache_family_checks", {})
    return tuple(
        family_id
        for family_id, checkbox in checks.items()
        if checkbox is not None and checkbox.isChecked()
    )


def _set_cache_status(tab: WidgetsTab, message: str, *, state: str = "info") -> None:
    label = getattr(tab, "cache_clear_status_label", None)
    if label is None:
        return
    color = {
        "success": "#7fe0a3",
        "warning": "#ffbd70",
        "error": "#ff8585",
    }.get(state, "rgba(255, 255, 255, 175)")
    label.setStyleSheet(f"{INFO_LABEL_STYLE} color: {color};")
    label.setText(message)


def _update_cache_clear_button_state(tab: WidgetsTab) -> None:
    button = getattr(tab, "clear_selected_caches_btn", None)
    if button is None:
        return
    running = bool(getattr(tab, "_general_cache_clear_running", False))
    button.setEnabled(bool(_selected_cache_ids(tab)) and not running)


def _format_byte_count(value: int) -> str:
    size = max(0.0, float(value))
    for suffix in ("B", "KB", "MB", "GB"):
        if size < 1024.0 or suffix == "GB":
            return f"{size:.0f} {suffix}" if suffix == "B" else f"{size:.1f} {suffix}"
        size /= 1024.0
    return "0 B"


def _on_clear_selected_caches(tab: WidgetsTab) -> None:
    selected_ids = _selected_cache_ids(tab)
    if not selected_ids or bool(getattr(tab, "_general_cache_clear_running", False)):
        _set_cache_status(tab, "Choose one or more cache families first.", state="warning")
        return

    descriptor_map: dict[str, CacheFamilyDescriptor] = getattr(tab, "_cache_family_descriptors", {})
    selected_labels = [descriptor_map[item].label for item in selected_ids if item in descriptor_map]
    confirmed = StyledPopup.question(
        tab,
        "Clear Selected Caches",
        "Clear these caches: " + ", ".join(selected_labels) + "?\n\n"
        "Cached content may be downloaded or rebuilt again when its widget refreshes.",
        yes_text="Clear Caches",
        no_text="Cancel",
        default_to_yes=False,
    )
    if not confirmed:
        return

    tab._general_cache_clear_running = True
    tab.clear_selected_caches_btn.setText("Clearing...")
    _update_cache_clear_button_state(tab)
    _set_cache_status(tab, "Clearing selected caches safely...")
    tab_ref = weakref.ref(tab)
    descriptors = tuple(descriptor_map.values())

    def _clear() -> CacheClearResult:
        return clear_cache_families(selected_ids, descriptors=descriptors)

    def _finished(task_result) -> None:
        def _apply_result() -> None:
            target = tab_ref()
            if target is None:
                return
            try:
                target._general_cache_clear_running = False
                target.clear_selected_caches_btn.setText("Clear Selected Caches")
                _update_cache_clear_button_state(target)
                if not task_result.success or not isinstance(task_result.result, CacheClearResult):
                    _set_cache_status(target, "Cache clearing failed safely.", state="error")
                    return
                result = task_result.result
                if "settings" in result.selected_ids:
                    from ui.settings_dialog_cache import invalidate_settings_dialog_cache

                    invalidate_settings_dialog_cache()
                if result.skipped_files:
                    _set_cache_status(
                        target,
                        f"Cleared {result.removed_files} files; {result.skipped_files} were in use or protected.",
                        state="warning",
                    )
                elif result.removed_files:
                    _set_cache_status(
                        target,
                        f"Cleared {result.removed_files} files ({_format_byte_count(result.removed_bytes)}).",
                        state="success",
                    )
                else:
                    _set_cache_status(target, "The selected caches were already empty.", state="success")
            except RuntimeError:
                return

        ThreadManager.run_on_ui_thread(_apply_result)

    try:
        _get_cache_thread_manager(tab).submit_io_task(
            _clear,
            task_id="general_clear_selected_caches",
            callback=_finished,
        )
    except Exception:
        tab._general_cache_clear_running = False
        tab.clear_selected_caches_btn.setText("Clear Selected Caches")
        _update_cache_clear_button_state(tab)
        _set_cache_status(tab, "Could not start cache clearing.", state="error")
        logger.debug("[GENERAL_TAB] Failed to submit cache-clear task", exc_info=True)


def build_defaults_ui(tab: WidgetsTab, layout: QVBoxLayout) -> QWidget:
    """Build the user-facing General section and attach controls to the tab instance."""

    label_width = 150

    group = QGroupBox("General Widget Settings")
    style_group_box(group)
    content_layout = QVBoxLayout(group)
    content_layout.setContentsMargins(18, 16, 18, 16)
    content_layout.setSpacing(12)

    appearance_toggle, appearance_body, appearance_layout = build_bucket_toggle(
        content_layout,
        "Appearance",
        expanded=tab.get_widget_bucket_state("defaults", "appearance", default=True),
        on_toggle=lambda checked: tab.set_widget_bucket_state("defaults", "appearance", checked),
        defer_initial_visibility=True,
    )
    layout_toggle, layout_body, layout_settings_layout = build_bucket_toggle(
        content_layout,
        "Layout",
        expanded=tab.get_widget_bucket_state("defaults", "layout", default=True),
        on_toggle=lambda checked: tab.set_widget_bucket_state("defaults", "layout", checked),
        defer_initial_visibility=True,
    )
    cache_toggle, cache_body, cache_layout = build_bucket_toggle(
        content_layout,
        "Cache Maintenance",
        expanded=tab.get_widget_bucket_state("defaults", "cache", default=False),
        on_toggle=lambda checked: tab.set_widget_bucket_state("defaults", "cache", checked),
        defer_initial_visibility=True,
    )
    tab._general_appearance_toggle = appearance_toggle
    tab._general_layout_toggle = layout_toggle
    tab._general_cache_toggle = cache_toggle

    row = QHBoxLayout()
    row.setContentsMargins(0, 8, 0, 8)
    row.setSpacing(12)
    tab.widget_shadows_enabled = QCheckBox("Enable Widget Drop Shadows")
    tab.widget_shadows_enabled.setProperty("circleIndicator", True)
    tab.widget_shadows_enabled.setToolTip(
        "Applies a subtle drop shadow to every widget card when enabled."
    )
    tab.widget_shadows_enabled.setChecked(tab._default_bool("shadows", "enabled", True))
    tab.widget_shadows_enabled.stateChanged.connect(tab._save_settings)
    row.addWidget(tab.widget_shadows_enabled)
    row.addStretch()
    appearance_layout.addLayout(row)

    row = QHBoxLayout()
    row.setContentsMargins(0, 8, 0, 8)
    row.setSpacing(12)
    tab.widget_text_shadows_enabled = QCheckBox("Enable Widget Text Shadows")
    tab.widget_text_shadows_enabled.setProperty("circleIndicator", True)
    tab.widget_text_shadows_enabled.setToolTip(
        "Paints widget text shadows without Qt graphics effects."
    )
    tab.widget_text_shadows_enabled.setChecked(tab._default_bool("shadows", "text_enabled", True))
    tab.widget_text_shadows_enabled.stateChanged.connect(tab._save_settings)
    row.addWidget(tab.widget_text_shadows_enabled)
    row.addStretch()
    appearance_layout.addLayout(row)

    row = QHBoxLayout()
    row.setContentsMargins(0, 8, 0, 8)
    row.setSpacing(12)
    tab.widget_header_shadows_enabled = QCheckBox("Enable Widget Header Drop Shadows")
    tab.widget_header_shadows_enabled.setProperty("circleIndicator", True)
    tab.widget_header_shadows_enabled.setToolTip(
        "Paints header-frame drop shadows without Qt graphics effects."
    )
    tab.widget_header_shadows_enabled.setChecked(tab._default_bool("shadows", "header_enabled", True))
    tab.widget_header_shadows_enabled.stateChanged.connect(tab._save_settings)
    row.addWidget(tab.widget_header_shadows_enabled)
    row.addStretch()
    appearance_layout.addLayout(row)

    row = QHBoxLayout()
    row.setContentsMargins(0, 8, 0, 8)
    row.setSpacing(12)
    tab.widget_stacking_enabled = QCheckBox("Enable Authored Widget Stacking")
    tab.widget_stacking_enabled.setProperty("circleIndicator", True)
    tab.widget_stacking_enabled.setToolTip(
        "Opt-in only. When enabled, non-Custom authored widgets may be packed to reduce overlap, "
        "but this can shift them away from their exact authored spacing."
    )
    tab.widget_stacking_enabled.setChecked(tab._default_bool("global", "stacking_enabled", False))
    tab.widget_stacking_enabled.stateChanged.connect(tab._save_settings)
    tab.widget_stacking_enabled.stateChanged.connect(tab._update_stack_status)
    row.addWidget(tab.widget_stacking_enabled)
    row.addStretch()
    layout_settings_layout.addLayout(row)

    border_row, _ = add_aligned_row(
        appearance_layout,
        "Card Border Width:",
        label_width=label_width,
        wrap=False,
    )
    tab.card_border_width_spin = QSpinBox()
    tab.card_border_width_spin.setRange(0, 12)
    tab.card_border_width_spin.setValue(tab._global_card_border_width)
    tab.card_border_width_spin.valueChanged.connect(tab._on_global_border_width_changed)
    border_row.addWidget(tab.card_border_width_spin)

    px_label = QLabel("px")
    px_label.setStyleSheet(FORM_ROW_LABEL_STYLE)
    px_label.setMinimumWidth(24)
    border_row.addWidget(px_label)
    border_row.addStretch()

    button_row = QHBoxLayout()
    button_row.setContentsMargins(0, 6, 0, 0)
    button_row.setSpacing(12)
    button_row.addStretch()

    tab.reset_widget_positions_btn = QPushButton("Reset Widget Positions")
    tab.reset_widget_positions_btn.setFixedHeight(32)
    tab.reset_widget_positions_btn.setToolTip(
        "Restore all widget positions and monitor routes to the application defaults for this profile."
    )
    tab.reset_widget_positions_btn.setStyleSheet(_ACTION_BUTTON_STYLE)
    tab.reset_widget_positions_btn.clicked.connect(tab._on_reset_widget_positions_to_defaults_clicked)
    button_row.addWidget(tab.reset_widget_positions_btn)
    layout_settings_layout.addLayout(button_row)

    cache_intro = QLabel(
        "Choose only the cached content you want removed. Settings, credentials, layouts, and defaults are never included."
    )
    cache_intro.setWordWrap(True)
    cache_intro.setStyleSheet(INFO_LABEL_STYLE)
    cache_layout.addWidget(cache_intro)

    app_data_dir = _settings_app_data_dir(tab)
    descriptors = get_cache_family_descriptors(app_data_dir=app_data_dir)
    tab._cache_family_descriptors = {descriptor.family_id: descriptor for descriptor in descriptors}
    tab.cache_family_checks = {}
    cache_grid = QGridLayout()
    cache_grid.setContentsMargins(0, 4, 0, 4)
    cache_grid.setHorizontalSpacing(18)
    cache_grid.setVerticalSpacing(10)
    for index, descriptor in enumerate(descriptors):
        checkbox = QCheckBox(descriptor.label)
        checkbox.setProperty("circleIndicator", True)
        checkbox.setToolTip(descriptor.description)
        checkbox.toggled.connect(lambda _checked, owner=tab: _update_cache_clear_button_state(owner))
        tab.cache_family_checks[descriptor.family_id] = checkbox
        cache_grid.addWidget(checkbox, index // 2, index % 2)
    cache_layout.addLayout(cache_grid)

    cache_button_row = QHBoxLayout()
    cache_button_row.setContentsMargins(0, 6, 0, 0)
    cache_button_row.setSpacing(12)
    tab.cache_clear_status_label = QLabel("Choose one or more cache families.")
    tab.cache_clear_status_label.setWordWrap(True)
    tab.cache_clear_status_label.setStyleSheet(INFO_LABEL_STYLE)
    cache_button_row.addWidget(tab.cache_clear_status_label, 1)
    tab.clear_selected_caches_btn = QPushButton("Clear Selected Caches")
    tab.clear_selected_caches_btn.setFixedHeight(32)
    tab.clear_selected_caches_btn.setStyleSheet(_ACTION_BUTTON_STYLE)
    tab.clear_selected_caches_btn.clicked.connect(lambda: _on_clear_selected_caches(tab))
    cache_button_row.addWidget(tab.clear_selected_caches_btn)
    cache_layout.addLayout(cache_button_row)
    _update_cache_clear_button_state(tab)

    for toggle, body in (
        (appearance_toggle, appearance_body),
        (layout_toggle, layout_body),
        (cache_toggle, cache_body),
    ):
        _finalize_bucket_body(toggle, body)

    return group


def load_defaults_settings(tab: WidgetsTab, widgets_config: Mapping[str, object]) -> None:
    """Load General-section controls from the widgets config mapping."""

    shadows_config = widgets_config.get("shadows", {}) if isinstance(widgets_config, Mapping) else {}
    if isinstance(shadows_config, Mapping):
        tab.widget_shadows_enabled.setChecked(tab._config_bool("shadows", shadows_config, "enabled", True))
        tab.widget_text_shadows_enabled.setChecked(tab._config_bool("shadows", shadows_config, "text_enabled", True))
        tab.widget_header_shadows_enabled.setChecked(tab._config_bool("shadows", shadows_config, "header_enabled", True))
    else:
        tab.widget_shadows_enabled.setChecked(True)
        tab.widget_text_shadows_enabled.setChecked(True)
        tab.widget_header_shadows_enabled.setChecked(True)

    global_cfg = widgets_config.get("global", {}) if isinstance(widgets_config, Mapping) else {}
    border_width = tab._config_int("global", global_cfg, "card_border_width_px", 3)
    border_width = max(0, min(12, border_width))
    stacking_enabled = tab._config_bool("global", global_cfg, "stacking_enabled", False)
    tab._global_card_border_width = border_width
    tab.widget_stacking_enabled.setChecked(stacking_enabled)
    if hasattr(tab, "card_border_width_spin"):
        tab.card_border_width_spin.setValue(border_width)


def save_defaults_settings(tab: WidgetsTab) -> tuple[dict[str, object], dict[str, object]]:
    """Build General-section persistence payloads for shadows/global settings."""

    shadows_config = {
        "enabled": tab.widget_shadows_enabled.isChecked(),
        "text_enabled": tab.widget_text_shadows_enabled.isChecked(),
        "header_enabled": tab.widget_header_shadows_enabled.isChecked(),
    }
    border_width = getattr(tab, "_global_card_border_width", tab._widget_default("global", "card_border_width_px", 3))
    global_config = {
        "card_border_width_px": int(border_width),
        "stacking_enabled": tab.widget_stacking_enabled.isChecked(),
    }
    return shadows_config, global_config
