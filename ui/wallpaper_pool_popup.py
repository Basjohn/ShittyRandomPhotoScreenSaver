"""One staged, themed pool selector shared by Settings and Guided Setup."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from sources.rss.pools import (
    DISCOVERY_ORDERS, WALLPAPER_POOLS, WallpaperPoolSelection,
    read_pool_selection, write_pool_selection,
)
from ui.styled_popup import StyledPopup
from ui.tabs import shared_styles
from ui.widgets import StyledComboBox


class WallpaperPoolPopup(StyledPopup):
    def __init__(self, parent, selection: WallpaperPoolSelection):
        content = QWidget()
        shared_styles.bind_shared_styles(content, "CIRCLE_CHECKBOX_STYLE", "COMBOBOX_STYLE", base_style="")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        row = QHBoxLayout()
        row.addWidget(QLabel("Order"))
        self.order = StyledComboBox(size_variant="compact")
        self.order.setToolTip("Order used to find new wallpapers. Providers use their normal order where a choice is unsupported.")
        for key, label in DISCOVERY_ORDERS:
            self.order.addItem(label, key)
            self.order.setItemData(self.order.count()-1,
                                  "Wallhaven supports every order. Konachan supports Latest and Popular. Other providers keep their normal order.",
                                  Qt.ItemDataRole.ToolTipRole)
        self.order.setCurrentIndex(self.order.findData(selection.discovery_order))
        row.addWidget(self.order, 1)
        layout.addLayout(row)
        nav = QHBoxLayout()
        nav.setSpacing(8)
        self._navigation = QButtonGroup(content)
        self._navigation.setExclusive(True)
        self.pages = QStackedWidget()
        self.pages.setAutoFillBackground(False)
        groups = (("Wallhaven", {"wallhaven"}, "Choose wallpaper themes from Wallhaven."),
                  ("Space & Daily", {"nasa", "bing"}, "NASA Space and Bing Image of the Day."),
                  ("Image Boards", {"konachan", "safebooru", "yandere"},
                   "Optional anime image sources with Safe or General ratings."))
        tooltips = {
            "nasa": "Sun, Mars, Solar System and Universe images from NASA.",
            "bing": "Recent Bing Image of the Day photographs.",
            "konachan": "Anime wallpapers marked Safe by Konachan. Popular uses score.",
            "safebooru": "Anime illustrations marked General by Safebooru.",
            "yandere": "Anime illustrations marked Safe by Yande.re.",
        }
        short_labels = {"nasa.space": "NASA Space", "bing.daily": "Bing Daily",
                        "konachan.safe": "Konachan.net", "safebooru.general": "Safebooru.org",
                        "yandere.safe": "Yande.re"}
        self.checkboxes = {}
        self._group_checks = []
        for index, (title, providers, tooltip) in enumerate(groups):
            button = QPushButton()
            button.setCheckable(True)
            button.setToolTip(tooltip)
            shared_styles.bind_shared_styles(button, "NAV_PILL_STYLE", base_style="")
            self._navigation.addButton(button, index)
            nav.addWidget(button)
            body = QWidget()
            body.setAutoFillBackground(False)
            choices = QGridLayout(body)
            choices.setContentsMargins(0, 4, 0, 4)
            choices.setHorizontalSpacing(18)
            checks = []
            for pool in (pool for pool in WALLPAPER_POOLS if pool.provider in providers):
                label = short_labels.get(pool.pool_id, pool.label)
                check = QCheckBox(label.replace("&", "&&"))
                check.setProperty("circleIndicator", True)
                check.setChecked(pool.pool_id in selection.selected)
                check.setObjectName("wallpaperPool-" + pool.pool_id)
                check.setToolTip("SFW Wallhaven search: " + pool.query if pool.provider == "wallhaven" else tooltips[pool.provider])
                position = len(checks)
                choices.addWidget(check, position // 2 if index == 0 else position, position % 2 if index == 0 else 0)
                checks.append(check)
                self.checkboxes[pool.pool_id] = check
            choices.setRowStretch(choices.rowCount(), 1)
            self._group_checks.append((button, title, checks))
            self.pages.addWidget(body)
            button.clicked.connect(lambda _checked=False, page=index: self.pages.setCurrentIndex(page))
        layout.addLayout(nav)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(shared_styles.SCROLL_AREA_STYLE)
        scroll.viewport().setAutoFillBackground(False)
        scroll.setMinimumHeight(260)
        scroll.setWidget(self.pages)
        layout.addWidget(scroll)
        for check in self.checkboxes.values():
            check.toggled.connect(self._update_group_counts)
        self._update_group_counts()
        first = next((index for index, (_, _, checks) in enumerate(self._group_checks)
                      if any(check.isChecked() for check in checks)), 0)
        self._navigation.button(first).setChecked(True)
        self.pages.setCurrentIndex(first)
        super().__init__(parent, "Just Make It Work Pools", "",
                         buttons=[("Apply Pools", "apply"), ("Cancel", "cancel")],
                         default_button_index=1, content=content)
        self.setMinimumWidth(620)
        self.setMaximumHeight(760)

    def _update_group_counts(self, *_args):
        for button, title, checks in self._group_checks:
            selected = sum(check.isChecked() for check in checks)
            button.setText(title.replace("&", "&&") + (f" · {selected}" if selected else ""))

    def selection(self) -> WallpaperPoolSelection:
        selected = tuple(key for key, check in self.checkboxes.items() if check.isChecked())
        return WallpaperPoolSelection(bool(selected), selected, self.order.currentData())


def choose_wallpaper_pools(parent, settings) -> bool:
    """Cancel has no writes. Draft.save is a no-op until Guided Setup Finish."""
    popup = WallpaperPoolPopup(parent, read_pool_selection(settings))
    try:
        popup.exec()
        if popup.result_value != "apply":
            return False
        write_pool_selection(settings, popup.selection())
        return True
    finally:
        popup.deleteLater()
