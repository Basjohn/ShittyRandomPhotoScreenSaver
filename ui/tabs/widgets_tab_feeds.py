"""Settings surface for the durable general Feeds family.

Four CUSTOM slots and five NEWS categories share one card builder: every card
has the same content, layout and appearance controls and the same save/load
shape, named ``<stem>_*`` on the tab (``feeds_custom2_*``, ``feeds_news_world_*``).
Only the Source bucket differs. A CUSTOM slot has a name, an address and TEST
FEED; a NEWS card has its category's publisher checkboxes and TEST SOURCES.
A card's controls fold away while it is disabled, so dormant cards cost one row.

Network work is explicit only: editing a URL or a publisher choice never probes
it. Both tests run the production bounded transport/parser/discovery off the
GUI thread and do not mutate the runtime cache. A site address is kept as
typed: the runtime resolves it to the site's feed itself and can find it again
if it moves.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
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

from core.feeds.config import CUSTOM_FEED_WIDGET_IDS, FEED_WIDGET_IDS
from core.feeds.news import NEWS_WIDGET_IDS, news_category, news_providers_for
from core.feeds.normalization import redacted_url_for_log
from core.logging.logger import get_logger
from core.resources.manager import ResourceManager
from core.threading.manager import ThreadManager
from rendering.widget_descriptors import feed_settings_attr_stem, get_widget_position_option_labels
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
FEED_SLOT_NUMBERS: tuple[int, ...] = tuple(range(1, len(CUSTOM_FEED_WIDGET_IDS) + 1))
_NOT_TESTED = "Not tested in this Settings session."


def feed_slot_widget_id(slot: int) -> str:
    return CUSTOM_FEED_WIDGET_IDS[int(slot) - 1]


def feed_attr(widget_id: str, name: str) -> str:
    """Tab attribute of one card's control, e.g. ``feeds_news_world_view_mode``."""

    return f"{feed_settings_attr_stem(widget_id)}_{name}"


def feed_slot_attr(slot: int, name: str) -> str:
    """Tab attribute of one CUSTOM slot's control, e.g. ``feeds_custom2_url``."""

    return feed_attr(feed_slot_widget_id(slot), name)


def news_provider_attr(widget_id: str, provider_id: str) -> str:
    return feed_attr(widget_id, f"provider_{provider_id}")


def _bucket_key(widget_id: str, name: str) -> str:
    """Persisted bucket state key: ``custom2_source``, ``news_world_layout``."""

    return f"{feed_settings_attr_stem(widget_id).removeprefix('feeds_')}_{name}"


def _control(tab: "WidgetsTab", widget_id: str, name: str) -> Any:
    return getattr(tab, feed_attr(widget_id, name))


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


def _set_controls_visible(tab: "WidgetsTab", widget_id: str) -> None:
    container = getattr(tab, f"_{feed_settings_attr_stem(widget_id)}_controls_container", None)
    checkbox = getattr(tab, feed_attr(widget_id, "enabled"), None)
    if container is not None:
        container.setVisible(bool(checkbox is not None and checkbox.isChecked()))


def _opacity_percent(tab: "WidgetsTab", widget_id: str, values: Mapping[str, Any], key: str) -> int:
    canonical = float(tab._widget_default(widget_id, key))
    raw = values.get(key, canonical)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = canonical
    return max(0, min(100, int(round(value * 100.0))))


def _set_view_combo(tab: "WidgetsTab", widget_id: str, value: object) -> None:
    normalized = str(value or "").strip().casefold()
    label = _VIEW_TO_LABEL.get(normalized)
    if label is None:
        canonical = tab._default_str(widget_id, "view_mode").strip().casefold()
        label = _VIEW_TO_LABEL[canonical]
    tab._set_combo_text(_control(tab, widget_id, "view_mode"), label)


_PROBE_FAILURE_TEXT = {
    "FeedDiscoveryError": "no feed found at this address",
    "FeedEmptyError": "the feed has no items right now",
    "FeedTransportError": "the address could not be reached",
    "ValueError": "not a valid http(s) address",
}


def _newest_text(result: object) -> str:
    newest = getattr(result, "newest_unix", None)
    if not newest:
        return ""
    try:
        return " · newest " + datetime.fromtimestamp(int(newest)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def _probe_summary(result: object) -> tuple[bool, str]:
    ok = bool(getattr(result, "ok", False))
    if not ok:
        failure = str(getattr(result, "failure", "") or "Feed could not be validated")
        return False, f"FAILED · {_PROBE_FAILURE_TEXT.get(failure, failure)[:180]}"
    fmt = str(getattr(result, "format", "feed") or "feed").upper()
    count = int(getattr(result, "item_count", 0) or 0)
    actionable = int(getattr(result, "actionable_count", 0) or 0)
    images = int(getattr(result, "image_count", 0) or 0)
    found_text = ""
    if bool(getattr(result, "discovered", False)):
        found_text = " · feed found at " + redacted_url_for_log(str(getattr(result, "feed_url", "") or ""))
    return True, (
        f"OK · {fmt} · {count} items · {actionable} links · {images} with images"
        f"{_newest_text(result)}{found_text}"
    )


def _news_probe_summary(results: object) -> tuple[bool, str]:
    """One line per publisher; OK only when every selected publisher passed."""

    lines = []
    all_ok = True
    for name, result in results if isinstance(results, (list, tuple)) else ():
        if bool(getattr(result, "ok", False)):
            count = int(getattr(result, "item_count", 0) or 0)
            lines.append(f"{name}: OK · {count} items{_newest_text(result)}")
        else:
            all_ok = False
            failure = str(getattr(result, "failure", "") or "could not be validated")
            lines.append(f"{name}: FAILED · {_PROBE_FAILURE_TEXT.get(failure, failure)[:120]}")
    if not lines:
        return False, "FAILED · no publisher selected"
    return all_ok, "\n".join(lines)


def _run_probe(
    tab: "WidgetsTab",
    widget_id: str,
    work: Callable[[], object],
    summarize: Callable[[object], tuple[bool, str]],
    *,
    running_text: str,
) -> None:
    """One explicit, generation-fenced source test off the GUI thread."""

    stem = feed_settings_attr_stem(widget_id)
    button = _control(tab, widget_id, "test_button")
    status = _control(tab, widget_id, "test_status")
    generation_attr = f"_{stem}_probe_generation"
    generation = int(getattr(tab, generation_attr, 0)) + 1
    setattr(tab, generation_attr, generation)
    button.setEnabled(False)
    status.setText(running_text)
    tab_ref = weakref.ref(tab)

    def _finished(task_result: object) -> None:
        def _apply() -> None:
            owner = tab_ref()
            if owner is None or not Shiboken.isValid(owner):
                return
            if getattr(owner, generation_attr, None) != generation:
                return
            _control(owner, widget_id, "test_button").setEnabled(True)
            if bool(getattr(task_result, "success", False)):
                ok, text = summarize(getattr(task_result, "result", None))
            else:
                ok, text = False, "FAILED · feed test task failed"
            owner_status = _control(owner, widget_id, "test_status")
            owner_status.setText(text)
            owner_status.setProperty("feedProbeOk", bool(ok))

        ThreadManager.run_on_ui_thread(_apply)

    try:
        _get_feed_thread_manager(tab).submit_io_task(
            work,
            task_id=f"{stem}_probe_{generation}",
            callback=_finished,
        )
    except Exception as exc:
        logger.warning("[FEEDS_TAB] Failed to submit explicit feed probe: %s", exc)
        button.setEnabled(True)
        status.setText("FAILED · feed test could not start")


def _test_feed(tab: "WidgetsTab", slot: int = 1) -> None:
    widget_id = feed_slot_widget_id(slot)
    url = str(_control(tab, widget_id, "url").text() or "").strip()
    if not url:
        _control(tab, widget_id, "test_status").setText("Enter a feed or website address first.")
        return

    def _work():
        from core.feeds.probe import probe_feed_url
        return probe_feed_url(url)

    _run_probe(tab, widget_id, _work, _probe_summary,
               running_text="Testing (finding the site's feed if needed)…")


def _selected_news_providers(tab: "WidgetsTab", widget_id: str) -> list[str]:
    return [
        provider.provider_id
        for provider in news_providers_for(widget_id)
        if getattr(tab, news_provider_attr(widget_id, provider.provider_id)).isChecked()
    ]


def _test_news_sources(tab: "WidgetsTab", widget_id: str) -> None:
    selected = set(_selected_news_providers(tab, widget_id))
    providers = [(p.display_name, p.url) for p in news_providers_for(widget_id) if p.provider_id in selected]
    if not providers:
        _control(tab, widget_id, "test_status").setText("Select at least one publisher first.")
        return

    def _work():
        from core.feeds.probe import probe_feed_url
        return [(name, probe_feed_url(url)) for name, url in providers]

    _run_probe(tab, widget_id, _work, _news_probe_summary, running_text="Testing each publisher…")


def _build_custom_source(tab: "WidgetsTab", widget_id: str, layout: QVBoxLayout, put) -> None:
    slot = CUSTOM_FEED_WIDGET_IDS.index(widget_id) + 1
    row, _ = add_aligned_row(layout, "Name:", label_width=_LABEL_WIDTH)
    name = put("name", QLineEdit())
    name.setMaxLength(80)
    name.setText(tab._default_str(widget_id, "name"))
    name.editingFinished.connect(tab._save_settings)
    row.addWidget(name, 1)

    row, _ = add_aligned_row(layout, "Feed URL:", label_width=_LABEL_WIDTH)
    url = put("url", QLineEdit())
    url.setMaxLength(8192)
    url.setPlaceholderText("https://example.com or https://example.com/feed.xml")
    url.setText(tab._default_str(widget_id, "feed_url"))
    url.editingFinished.connect(tab._save_settings)
    row.addWidget(url, 1)

    probe_row = QHBoxLayout()
    probe_row.setContentsMargins(_LABEL_WIDTH + 12, 0, 0, 0)
    test_button = put("test_button", QPushButton("TEST FEED"))
    test_button.clicked.connect(lambda _checked=False, n=slot: _test_feed(tab, n))
    probe_row.addWidget(test_button)
    test_status = put("test_status", QLabel(_NOT_TESTED))
    test_status.setWordWrap(True)
    probe_row.addWidget(test_status, 1)
    layout.addLayout(probe_row)


def _build_news_source(tab: "WidgetsTab", widget_id: str, layout: QVBoxLayout, put) -> None:
    selected = set(tab._widget_default(widget_id, "providers"))
    note = QLabel(
        "Official publisher feeds, merged newest first. Each story names its publisher; "
        "SRPSS does not rank, score or filter stories."
    )
    note.setWordWrap(True)
    layout.addWidget(note)
    for provider in news_providers_for(widget_id):
        checkbox = QCheckBox(provider.display_name)
        setattr(tab, news_provider_attr(widget_id, provider.provider_id), checkbox)
        checkbox.setProperty("circleIndicator", True)
        checkbox.setChecked(provider.provider_id in selected)
        checkbox.setToolTip(f"{provider.url}\nFeed directory: {provider.directory_url}")
        checkbox.stateChanged.connect(tab._save_settings)
        layout.addWidget(checkbox)

    probe_row = QHBoxLayout()
    probe_row.setContentsMargins(0, 0, 0, 0)
    test_button = put("test_button", QPushButton("TEST SOURCES"))
    test_button.clicked.connect(lambda _checked=False, w=widget_id: _test_news_sources(tab, w))
    probe_row.addWidget(test_button)
    test_status = put("test_status", QLabel(_NOT_TESTED))
    test_status.setWordWrap(True)
    probe_row.addWidget(test_status, 1)
    layout.addLayout(probe_row)


def _build_card(tab: "WidgetsTab", root: QVBoxLayout, widget_id: str, enable_label: str) -> None:
    """Build one Feed card's controls as ``<stem>_*`` on the tab."""

    def put(name: str, control: Any) -> Any:
        setattr(tab, feed_attr(widget_id, name), control)
        return control

    def bucket(key: str) -> str:
        return _bucket_key(widget_id, key)

    enabled = put("enabled", QCheckBox(enable_label))
    enabled.setProperty("circleIndicator", True)
    enabled.setChecked(tab._default_bool(widget_id, "enabled"))
    enabled.stateChanged.connect(tab._save_settings)
    enabled.stateChanged.connect(tab._update_stack_status)
    root.addWidget(enabled)

    container = QWidget()
    setattr(tab, f"_{feed_settings_attr_stem(widget_id)}_controls_container", container)
    controls = QVBoxLayout(container)
    controls.setContentsMargins(0, 0, 0, 8)
    controls.setSpacing(12)

    source_toggle, source_body, source_layout = build_bucket_toggle(
        controls,
        "Sources" if widget_id in NEWS_WIDGET_IDS else "Source",
        expanded=tab.get_widget_bucket_state("feeds", bucket("source")),
        on_toggle=lambda checked, k=bucket("source"): tab.set_widget_bucket_state("feeds", k, checked),
        defer_initial_visibility=True,
    )
    if widget_id in NEWS_WIDGET_IDS:
        _build_news_source(tab, widget_id, source_layout, put)
    else:
        _build_custom_source(tab, widget_id, source_layout, put)
    finalize_bucket_body(source_toggle, source_body)

    content_toggle, content_body, content_layout = build_bucket_toggle(
        controls,
        "Content & Refresh",
        expanded=tab.get_widget_bucket_state("feeds", bucket("content")),
        on_toggle=lambda checked, k=bucket("content"): tab.set_widget_bucket_state("feeds", k, checked),
        defer_initial_visibility=True,
    )
    row, _ = add_aligned_row(content_layout, "Display Type:", label_width=_LABEL_WIDTH)
    view_mode = put("view_mode", StyledComboBox())
    view_mode.addItems(list(_VIEW_TO_LABEL.values()))
    _set_view_combo(tab, widget_id, tab._default_str(widget_id, "view_mode"))
    view_mode.currentTextChanged.connect(tab._save_settings)
    row.addWidget(view_mode)
    row.addStretch()

    row, _ = add_aligned_row(content_layout, "Max Items:", label_width=_LABEL_WIDTH)
    item_limit = put("item_limit", QSpinBox())
    item_limit.setRange(3, 40)
    item_limit.setValue(tab._default_int(widget_id, "item_limit"))
    item_limit.valueChanged.connect(tab._save_settings)
    item_limit.valueChanged.connect(tab._update_stack_status)
    row.addWidget(item_limit)
    row.addStretch()

    row, _ = add_aligned_row(content_layout, "Refresh:", label_width=_LABEL_WIDTH)
    refresh = put("refresh_minutes", QSpinBox())
    refresh.setRange(5, 1440)
    refresh.setSuffix(" min")
    refresh.setValue(tab._default_int(widget_id, "refresh_minutes"))
    refresh.valueChanged.connect(tab._save_settings)
    row.addWidget(refresh)
    row.addStretch()

    show_images = put("show_images", QCheckBox("Show Locally Cached Article Images"))
    show_images.setProperty("circleIndicator", True)
    show_images.setChecked(tab._default_bool(widget_id, "show_images"))
    show_images.stateChanged.connect(tab._save_settings)
    content_layout.addWidget(show_images)

    show_subtitle = put("show_subtitle", QCheckBox("Show Feed Subtitle"))
    show_subtitle.setProperty("circleIndicator", True)
    show_subtitle.setChecked(tab._default_bool(widget_id, "show_subtitle"))
    show_subtitle.setToolTip(
        "Show the feed/publisher title as small metadata below the branded header when it differs from the configured name."
    )
    show_subtitle.stateChanged.connect(tab._save_settings)
    content_layout.addWidget(show_subtitle)
    finalize_bucket_body(content_toggle, content_body)

    layout_toggle, layout_body, layout_controls = build_bucket_toggle(
        controls,
        "Layout & Typography",
        expanded=tab.get_widget_bucket_state("feeds", bucket("layout")),
        on_toggle=lambda checked, k=bucket("layout"): tab.set_widget_bucket_state("feeds", k, checked),
        defer_initial_visibility=True,
    )

    row, _ = add_aligned_row(layout_controls, "Position:", label_width=_LABEL_WIDTH)
    position = put("position", StyledComboBox())
    position.addItems(list(get_widget_position_option_labels(widget_id)))
    tab._set_combo_text(position, tab._default_str(widget_id, "position"))
    position.currentTextChanged.connect(tab._save_settings)
    position.currentTextChanged.connect(tab._update_stack_status)
    row.addWidget(position)
    stack_status = put("stack_status", QLabel(""))
    stack_status.setStyleSheet(STATUS_LABEL_STYLE)
    row.addWidget(stack_status)
    row.addStretch()

    row, _ = add_aligned_row(layout_controls, "Display:", label_width=_LABEL_WIDTH)
    monitor = put("monitor_combo", StyledComboBox(size_variant="compact"))
    monitor.addItems(["ALL", "1", "2", "3"])
    tab._set_combo_text(monitor, str(tab._widget_default(widget_id, "monitor")))
    monitor.currentTextChanged.connect(tab._save_settings)
    monitor.currentTextChanged.connect(tab._update_stack_status)
    row.addWidget(monitor)
    row.addStretch()

    row, _ = add_aligned_row(layout_controls, "Margin:", label_width=_LABEL_WIDTH)
    margin = put("margin", QSpinBox())
    margin.setRange(0, 300)
    margin.setSuffix(" px")
    margin.setValue(tab._default_int(widget_id, "margin"))
    margin.valueChanged.connect(tab._save_settings)
    row.addWidget(margin)
    row.addStretch()

    row, _ = add_aligned_row(layout_controls, "Font:", label_width=_LABEL_WIDTH)
    font_combo = put("font_combo", StyledFontComboBox(size_variant="hero"))
    font_combo.setCurrentFont(QFont(tab._default_str(widget_id, "font_family")))
    font_combo.currentFontChanged.connect(tab._save_settings)
    row.addWidget(font_combo)
    row.addStretch()

    row, _ = add_aligned_row(layout_controls, "Font Size:", label_width=_LABEL_WIDTH)
    font_size = put("font_size", QSpinBox())
    font_size.setRange(8, 48)
    font_size.setValue(tab._default_int(widget_id, "font_size"))
    font_size.valueChanged.connect(tab._save_settings)
    row.addWidget(font_size)
    row.addStretch()

    row, _ = add_aligned_row(layout_controls, "Authored Width:", label_width=_LABEL_WIDTH)
    preferred_width = put("preferred_width", QSpinBox())
    preferred_width.setRange(320, 1600)
    preferred_width.setSuffix(" px")
    preferred_width.setValue(tab._default_int(widget_id, "preferred_width"))
    preferred_width.valueChanged.connect(tab._save_settings)
    row.addWidget(preferred_width)
    row.addStretch()

    row, _ = add_aligned_row(layout_controls, "Authored Height:", label_width=_LABEL_WIDTH)
    preferred_height = put("preferred_height", QSpinBox())
    preferred_height.setRange(180, 1800)
    preferred_height.setSuffix(" px")
    preferred_height.setValue(tab._default_int(widget_id, "preferred_height"))
    preferred_height.valueChanged.connect(tab._save_settings)
    row.addWidget(preferred_height)
    row.addStretch()
    finalize_bucket_body(layout_toggle, layout_body)

    appearance_toggle, appearance_body, appearance_layout = build_bucket_toggle(
        controls,
        "Appearance",
        expanded=tab.get_widget_bucket_state("feeds", bucket("appearance")),
        on_toggle=lambda checked, k=bucket("appearance"): tab.set_widget_bucket_state("feeds", k, checked),
        defer_initial_visibility=True,
    )
    show_background = put("show_background", QCheckBox("Show Card Background"))
    show_background.setProperty("circleIndicator", True)
    show_background.setChecked(tab._default_bool(widget_id, "show_background"))
    show_background.stateChanged.connect(tab._save_settings)
    appearance_layout.addWidget(show_background)

    row, _ = add_aligned_row(appearance_layout, "Background Opacity:", label_width=_LABEL_WIDTH)
    bg_opacity = put("bg_opacity", QSpinBox())
    bg_opacity.setRange(0, 100)
    bg_opacity.setSuffix(" %")
    bg_opacity.setValue(int(round(float(tab._widget_default(widget_id, "bg_opacity")) * 100.0)))
    bg_opacity.valueChanged.connect(tab._save_settings)
    row.addWidget(bg_opacity)
    row.addStretch()

    row, _ = add_aligned_row(appearance_layout, "Border Opacity:", label_width=_LABEL_WIDTH)
    border_opacity = put("border_opacity", QSpinBox())
    border_opacity.setRange(0, 100)
    border_opacity.setSuffix(" %")
    border_opacity.setValue(int(round(float(tab._widget_default(widget_id, "border_opacity")) * 100.0)))
    border_opacity.valueChanged.connect(tab._save_settings)
    row.addWidget(border_opacity)
    row.addStretch()
    finalize_bucket_body(appearance_toggle, appearance_body)

    controls.addStretch()
    root.addWidget(container)
    enabled.stateChanged.connect(lambda _state=0, w=widget_id: _set_controls_visible(tab, w))
    _set_controls_visible(tab, widget_id)


def _group(title: str, intro_text: str) -> tuple[QGroupBox, QVBoxLayout]:
    group = QGroupBox(title)
    style_group_box(group)
    root = QVBoxLayout(group)
    root.setContentsMargins(16, 18, 16, 16)
    root.setSpacing(14)
    intro = QLabel(intro_text)
    intro.setWordWrap(True)
    root.addWidget(intro)
    return group, root


def build_feeds_ui(tab: "WidgetsTab", layout: QVBoxLayout) -> QWidget:
    custom_group, custom_root = _group(
        "Feeds",
        "Up to four CUSTOM feeds, each an RSS, Atom or JSON Feed address or a website address whose "
        "feed is found automatically. Runtime is cache-first and preserves the last good snapshot "
        "across temporary source failures. The same address in two slots is fetched once. URL "
        "testing is explicit and never runs while typing.",
    )
    for slot in FEED_SLOT_NUMBERS:
        _build_card(tab, custom_root, feed_slot_widget_id(slot), f"Enable Custom {slot}")

    news_group, news_root = _group(
        "News",
        "Built-in news categories from official publisher feeds that need no account. Stories from "
        "the selected publishers are merged newest first and each names its publisher. One "
        "publisher failing keeps its last good stories and never blanks the others.",
    )
    for widget_id in NEWS_WIDGET_IDS:
        _build_card(tab, news_root, widget_id, f"Enable {news_category(widget_id).label}")

    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 20, 0, 0)
    container_layout.setSpacing(20)
    container_layout.addWidget(custom_group)
    container_layout.addWidget(news_group)
    return container


def _load_card(tab: "WidgetsTab", widget_id: str, widgets: Mapping[str, Any]) -> None:
    values = widgets.get(widget_id, {})
    if not isinstance(values, Mapping):
        values = {}
    _control(tab, widget_id, "enabled").setChecked(tab._config_bool(widget_id, values, "enabled"))
    if widget_id in NEWS_WIDGET_IDS:
        selected = values.get("providers", tab._widget_default(widget_id, "providers"))
        if not isinstance(selected, (list, tuple)):
            selected = tab._widget_default(widget_id, "providers")
        chosen = {str(entry) for entry in selected}
        for provider in news_providers_for(widget_id):
            getattr(tab, news_provider_attr(widget_id, provider.provider_id)).setChecked(
                provider.provider_id in chosen)
    else:
        _control(tab, widget_id, "name").setText(tab._config_str(widget_id, values, "name"))
        _control(tab, widget_id, "url").setText(tab._config_str(widget_id, values, "feed_url"))
    _set_view_combo(tab, widget_id, values.get("view_mode", tab._widget_default(widget_id, "view_mode")))
    _control(tab, widget_id, "item_limit").setValue(tab._config_int(widget_id, values, "item_limit"))
    _control(tab, widget_id, "refresh_minutes").setValue(tab._config_int(widget_id, values, "refresh_minutes"))
    _control(tab, widget_id, "show_images").setChecked(tab._config_bool(widget_id, values, "show_images"))
    _control(tab, widget_id, "show_subtitle").setChecked(tab._config_bool(widget_id, values, "show_subtitle"))
    tab._set_combo_text(_control(tab, widget_id, "position"), tab._config_str(widget_id, values, "position"))
    tab._set_combo_text(
        _control(tab, widget_id, "monitor_combo"),
        str(values.get("monitor", tab._widget_default(widget_id, "monitor"))),
    )
    _control(tab, widget_id, "margin").setValue(tab._config_int(widget_id, values, "margin"))
    _control(tab, widget_id, "font_combo").setCurrentFont(QFont(tab._config_str(widget_id, values, "font_family")))
    _control(tab, widget_id, "font_size").setValue(tab._config_int(widget_id, values, "font_size"))
    _control(tab, widget_id, "preferred_width").setValue(tab._config_int(widget_id, values, "preferred_width"))
    _control(tab, widget_id, "preferred_height").setValue(tab._config_int(widget_id, values, "preferred_height"))
    _control(tab, widget_id, "show_background").setChecked(tab._config_bool(widget_id, values, "show_background"))
    _control(tab, widget_id, "bg_opacity").setValue(_opacity_percent(tab, widget_id, values, "bg_opacity"))
    _control(tab, widget_id, "border_opacity").setValue(_opacity_percent(tab, widget_id, values, "border_opacity"))
    _control(tab, widget_id, "test_status").setText(_NOT_TESTED)
    _set_controls_visible(tab, widget_id)


def load_feeds_settings(tab: "WidgetsTab", widgets: Mapping[str, Any]) -> None:
    for widget_id in FEED_WIDGET_IDS:
        _load_card(tab, widget_id, widgets)


def _save_card(tab: "WidgetsTab", widget_id: str) -> dict[str, Any]:
    defaults = tab._widget_defaults.get(widget_id)
    if not isinstance(defaults, Mapping):
        raise KeyError(f"Canonical widget defaults are missing widgets.{widget_id}")
    payload = dict(defaults)
    view_mode = _LABEL_TO_VIEW.get(_control(tab, widget_id, "view_mode").currentText())
    if view_mode is None:
        view_mode = str(defaults["view_mode"])
    if widget_id in NEWS_WIDGET_IDS:
        payload["providers"] = _selected_news_providers(tab, widget_id)
    else:
        payload.update({
            "name": str(_control(tab, widget_id, "name").text() or "").strip()[:80] or str(defaults["name"]),
            "feed_url": str(_control(tab, widget_id, "url").text() or "").strip()[:8192],
        })
    payload.update(
        {
            "enabled": bool(_control(tab, widget_id, "enabled").isChecked()),
            "view_mode": view_mode,
            "item_limit": int(_control(tab, widget_id, "item_limit").value()),
            "refresh_minutes": int(_control(tab, widget_id, "refresh_minutes").value()),
            "show_images": bool(_control(tab, widget_id, "show_images").isChecked()),
            "show_subtitle": bool(_control(tab, widget_id, "show_subtitle").isChecked()),
            "position": _control(tab, widget_id, "position").currentText(),
            "monitor": tab._monitor_value_from_combo(widget_id, _control(tab, widget_id, "monitor_combo")),
            "margin": int(_control(tab, widget_id, "margin").value()),
            "font_family": _control(tab, widget_id, "font_combo").currentFont().family(),
            "font_size": int(_control(tab, widget_id, "font_size").value()),
            "preferred_width": int(_control(tab, widget_id, "preferred_width").value()),
            "preferred_height": int(_control(tab, widget_id, "preferred_height").value()),
            "show_background": bool(_control(tab, widget_id, "show_background").isChecked()),
            "bg_opacity": float(_control(tab, widget_id, "bg_opacity").value()) / 100.0,
            "border_opacity": float(_control(tab, widget_id, "border_opacity").value()) / 100.0,
        }
    )
    return payload


def save_feeds_settings(tab: "WidgetsTab") -> tuple[dict[str, Any], ...]:
    """One payload per Feed card, in ``FEED_WIDGET_IDS`` order."""

    return tuple(_save_card(tab, widget_id) for widget_id in FEED_WIDGET_IDS)


__all__ = [
    "FEED_SLOT_NUMBERS",
    "build_feeds_ui",
    "feed_attr",
    "feed_slot_attr",
    "feed_slot_widget_id",
    "load_feeds_settings",
    "news_provider_attr",
    "save_feeds_settings",
]
