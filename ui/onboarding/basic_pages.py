"""Welcome, sources, display selection and interaction: cheap Settings-only UI."""
from PySide6.QtCore import QRectF, QSignalBlocker, Signal, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QFileDialog, QHBoxLayout, QListWidget, QPushButton,
    QVBoxLayout, QWidget,
)

from core.sources.readiness import has_image_sources
from sources.rss.curated import apply_curated_wallpaper_feeds
from ui.onboarding.common import Page, ImagePanel, action, asset_path, checkbox, CheckList, silence_check, text_label, SILENCE_TEXT
from ui.settings_theme_runtime import get_active_settings_theme
from ui.styled_popup import StyledPopup


class WelcomePage(Page):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        row = QHBoxLayout()
        self.art = ImagePanel(asset_path("SRPSSWitch.png"))
        row.addWidget(self.art, 2)
        copy = QVBoxLayout()
        title = text_label("You're Inside A Wizard Harry!", heading=True)
        font = title.font(); font.setBold(True); font.setUnderline(True); title.setFont(font)
        copy.addStretch()
        copy.addWidget(title)
        copy.addWidget(text_label(
            "Your first time inside someone is special and confusing.\n"
            "The Wizard can help pick the right settings for you while you squirm inside without consent."
        ))
        copy.addStretch()
        row.addLayout(copy, 3)
        self.body.addLayout(row, 1)
        self.body.addWidget(silence_check(settings))
        self.body.addWidget(text_label(SILENCE_TEXT))


class SourcesPage(Page):
    readinessChanged = Signal()
    finishRequested = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.body.addWidget(text_label(
            "You put on your robe and wizard hat.\n"
            "Sources matter the most. Where do you want your wallpapers from?", heading=True
        ))
        self.body.addWidget(text_label("Folders on this computer"))
        self.folders = QListWidget()
        self.folders.setMinimumHeight(90)
        self.body.addWidget(self.folders, 1)
        row = QHBoxLayout()
        row.addWidget(action("Add folder…", self.add_folder))
        row.addWidget(action("Remove selected", self.remove_folder, secondary=True))
        row.addStretch()
        self.body.addLayout(row)
        self.feeds_enabled = checkbox("Wallpaper Feeds")
        self.feeds_enabled.toggled.connect(self.toggle_feeds)
        self.body.addWidget(self.feeds_enabled)
        self.feeds = CheckList()
        self.feeds.setMinimumHeight(100)
        self.feeds.itemChanged.connect(self.change_feed)
        self.body.addWidget(self.feeds, 1)
        self.reason = text_label("")
        self.body.addWidget(self.reason)
        shortcuts = QHBoxLayout()
        shortcuts.addWidget(action("Just Make It Work", self.make_it_work, secondary=True))
        self.skip = action("Skip", self.finishRequested.emit, secondary=True)
        shortcuts.addWidget(self.skip)
        shortcuts.addStretch()
        self.body.addLayout(shortcuts)
        self.body.addWidget(text_label("Skip finishes now and leaves every other setting as it is."))
        self.refresh()

    def refresh(self):
        from sources.rss.constants import DEFAULT_RSS_FEEDS
        from PySide6.QtWidgets import QListWidgetItem
        self.folders.clear()
        self.folders.addItems(list(self.settings.get("sources.folders") or []))
        current = list(self.settings.get("sources.rss_feeds") or [])
        with QSignalBlocker(self.feeds_enabled):
            self.feeds_enabled.setChecked(bool(current))
        with QSignalBlocker(self.feeds):
            self.feeds.clear()
            names = {url: name for name, url in DEFAULT_RSS_FEEDS.items()}
            for url in dict.fromkeys([*DEFAULT_RSS_FEEDS.values(), *current]):
                item = QListWidgetItem(names.get(url, url))
                item.setData(Qt.ItemDataRole.UserRole, url)
                item.setToolTip(url)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if url in current else Qt.CheckState.Unchecked)
                self.feeds.addItem(item)
        ready = self.can_continue()
        self.reason.setText("Ready to continue." if ready else "Add a folder or turn on a wallpaper feed to continue.")
        self.skip.setEnabled(ready)
        self.readinessChanged.emit()

    def can_continue(self):
        return has_image_sources(self.settings)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose wallpaper folder")
        if folder:
            folders = list(self.settings.get("sources.folders") or [])
            if folder not in folders:
                self.settings.set("sources.folders", [*folders, folder])
            self.refresh()

    def remove_folder(self):
        selected = self.folders.currentItem()
        if selected:
            self.settings.set("sources.folders", [x for x in self.settings.get("sources.folders") if x != selected.text()])
            self.refresh()

    def toggle_feeds(self, enabled):
        if enabled:
            apply_curated_wallpaper_feeds(self.settings)
        else:
            self.settings.set("sources.rss_feeds", [])
        self.refresh()

    def change_feed(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        feeds = list(self.settings.get("sources.rss_feeds") or [])
        if item.checkState() == Qt.CheckState.Checked and url not in feeds:
            feeds.append(url)
        elif item.checkState() != Qt.CheckState.Checked:
            feeds = [value for value in feeds if value != url]
        self.settings.set("sources.rss_feeds", feeds)
        self.refresh()

    def make_it_work(self):
        apply_curated_wallpaper_feeds(self.settings)
        self.refresh()
        popup = StyledPopup(self, "Guided Setup", "You're lazy and so am I! Skip the rest?",
                            buttons=[("No, I can do it!", "continue"), ("Skip", "skip")], default_button_index=0)
        popup.exec()
        if popup.result_value == "skip":
            self.finishRequested.emit()


class DisplayDiagram(QWidget):
    def __init__(self, screens, parent=None):
        super().__init__(parent)
        self.screens = screens
        self.setMinimumHeight(160)

    def paintEvent(self, event):
        if not self.screens:
            return
        theme = get_active_settings_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = QRectF(self.screens[0].geometry())
        for screen in self.screens[1:]:
            bounds = bounds.united(QRectF(screen.geometry()))
        scale = min((self.width()-24) / bounds.width(), (self.height()-24) / bounds.height())
        painter.setPen(QPen(QColor(*theme.color("chrome.outer_border").as_tuple()), 2))
        for index, screen in enumerate(self.screens, 1):
            g = screen.geometry()
            rect = QRectF(12+(g.x()-bounds.x())*scale, 12+(g.y()-bounds.y())*scale, g.width()*scale, g.height()*scale)
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 5, 5)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(index))


class DisplaysPage(Page):
    readinessChanged = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.body.addWidget(text_label("Where should the screensaver appear?", heading=True))
        self.body.addWidget(text_label("Choose the displays you want to use. The diagram follows their arrangement in Windows."))
        self.screens = QGuiApplication.screens()
        self.body.addWidget(DisplayDiagram(self.screens))
        self.all = checkbox("All displays, including displays connected later")
        self.body.addWidget(self.all)
        self.checks = []
        for index, screen in enumerate(self.screens, 1):
            g = screen.geometry()
            check = checkbox(f"{index} · {screen.name()} · {g.width()} × {g.height()} logical pixels")
            check.toggled.connect(self.save_selection)
            self.body.addWidget(check)
            self.checks.append(check)
        self.all.toggled.connect(self.save_selection)
        self.reason = text_label("")
        self.body.addWidget(self.reason)
        self.body.addStretch()
        self.refresh()

    def refresh(self):
        selected = self.settings.get("display.show_on_monitors")
        with QSignalBlocker(self.all):
            self.all.setChecked(selected == "ALL")
        for index, check in enumerate(self.checks, 1):
            with QSignalBlocker(check):
                check.setChecked(selected == "ALL" or index in (selected if isinstance(selected, list) else []))
                check.setEnabled(selected != "ALL")
        self.reason.setText("" if self.can_continue() else "Select at least one connected display to continue.")
        self.readinessChanged.emit()

    def can_continue(self):
        return self.all.isChecked() or any(check.isChecked() for check in self.checks)

    def save_selection(self):
        selected = [i for i, check in enumerate(self.checks, 1) if check.isChecked()]
        if not self.all.isChecked() and not selected:
            self.refresh()
            return
        self.settings.set("display.show_on_monitors", "ALL" if self.all.isChecked() else selected)
        self.refresh()


class _PracticeStoryCard(QWidget):
    """A painted mock story row (D9): no network, browser, handoff or feed widget."""

    clicked = Signal(bool)  # True when Ctrl was held

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(96)
        self.setMaximumWidth(620)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        from PySide6.QtGui import QPixmap
        self._art = QPixmap(str(asset_path("onboarding/transition_destination.png")))
        self._pressed = False

    def paintEvent(self, _event):
        theme = get_active_settings_theme()
        color = lambda token: QColor(*theme.color(token).as_tuple())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        painter.setPen(QPen(color("panel.border"), 2.5 if self.underMouse() else 2.0))
        painter.setBrush(color("panel.subsection.surface"))
        painter.drawRoundedRect(rect, 10.0, 10.0)
        art = QRectF(rect.left() + 12, rect.top() + 12, (rect.height() - 24) * 16 / 9, rect.height() - 24)
        if not self._art.isNull():
            from PySide6.QtGui import QPainterPath
            clip = QPainterPath(); clip.addRoundedRect(art, 6.0, 6.0)
            painter.save(); painter.setClipPath(clip)
            painter.drawPixmap(art, self._art, QRectF(self._art.rect()))
            painter.restore()
        text = QRectF(art.right() + 14, rect.top() + 14, rect.right() - art.right() - 26, rect.height() - 28)
        font = self.font(); font.setBold(True); font.setPointSizeF(font.pointSizeF() + 1.5)
        painter.setFont(font); painter.setPen(color("panel.group.text"))
        painter.drawText(text, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                         "A practice story: the lighthouse keeper's last night")
        font.setBold(False); font.setPointSizeF(font.pointSizeF() - 2.5); painter.setFont(font)
        painter.setPen(color("control.button.text"))
        painter.drawText(text, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, "PRACTICE WIRE  ·  2H AGO")

    def enterEvent(self, event):
        super().enterEvent(event); self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event); self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))
            event.accept()
            return
        super().mousePressEvent(event)


class InteractionPage(Page):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self.body.addWidget(text_label("Look, or interact?", heading=True))
        self.body.addWidget(text_label("Use widgets to open stories and control media. On the screensaver, external links use SRPSS's secure handoff and may close the saver. Hold Ctrl for temporary interaction when it is off."))
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for enabled, title, detail in (
            (False, "Let it be a screensaver", "Hold Ctrl when you want to interact."),
            (True, "Keep interaction on", "Use widgets without holding Ctrl."),
        ):
            choice = checkbox(f"{title}\n{detail}")
            choice.setMinimumHeight(64)
            choice.toggled.connect(lambda checked, value=enabled: checked and self.settings.set("input.interaction_mode", value))
            self.group.addButton(choice, int(enabled))
            self.body.addWidget(choice)
        self.body.addSpacing(8)
        self.body.addWidget(text_label("Try it on a practice story", heading=False))
        self.card = _PracticeStoryCard()
        self.card.clicked.connect(self.demonstrate)
        self.body.addWidget(self.card)
        self.demo = text_label("Click the card, with and without Ctrl. Nothing opens and the screensaver is not running.")
        self.body.addWidget(self.demo)
        self.body.addStretch()
        self.refresh()

    def refresh(self):
        button = self.group.button(int(bool(self.settings.get("input.interaction_mode"))))
        with QSignalBlocker(button):
            button.setChecked(True)

    def demonstrate(self, ctrl_held: bool = False):
        if self.settings.get("input.interaction_mode") or ctrl_held:
            self.demo.setText("On the saver, this click would open the story in your browser through the secure link handoff.")
        else:
            self.demo.setText("Nothing happens: the saver treats a plain click as 'wake up'. Hold Ctrl while clicking to open the story.")
