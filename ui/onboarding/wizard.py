"""Lazy Guided Setup panel. Settings remains the sole persistence authority.

Saving is explicit: pages edit a :class:`SettingsDraft`, and only Finish (or a
"Save" answer when leaving early) commits it to the user's settings.

The panel is hosted inside the Settings window (it replaces the sidebar and
tab area while it runs), so it shares Settings' native backdrop, theme,
title bar and window lifetime instead of owning a second top-level surface.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from core.sources.readiness import has_image_sources
from ui.onboarding.common import action, text_label
from ui.tabs import shared_styles


class GuidedSetupPanel(QWidget):
    """Guided Setup steps; emits ``finished(completed)`` when the user leaves."""

    finished = Signal(bool)

    STEPS = (
        ("welcome", "Welcome"), ("sources", "Sources"), ("displays", "Displays"),
        ("theme", "Theme"), ("interaction", "Interaction"), ("widgets", "Widgets"),
        ("setup", "Widget Setup"), ("visualizer", "Visualizer"),
        ("transitions", "Transitions"), ("arrange", "Arrange"), ("ready", "Ready"),
    )

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        from ui.onboarding.draft import SettingsDraft
        self.settings = SettingsDraft(settings)
        self._closed = False
        # Styled exactly like the Settings tab area it replaces (theme QSS and
        # shell shadow both key on this object name).
        self.setObjectName("contentArea")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.pages = {}
        self.current_key = "welcome"
        layout = QVBoxLayout(self); layout.setContentsMargins(18, 16, 18, 16); layout.setSpacing(12)
        top = QHBoxLayout()
        top.addWidget(text_label("GUIDED SETUP", heading=True))
        top.addStretch()
        self.skip = action("Skip", self.request_close, secondary=True)
        self.skip.setToolTip("Leave Guided Setup now. Everything you have already chosen is kept; nothing else changes.")
        top.addWidget(self.skip)
        layout.addLayout(top)
        self.progress = text_label("")
        layout.addWidget(self.progress)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        footer = QHBoxLayout()
        self.back = action("Back", self.go_back, secondary=True)
        self.next = action("Next", self.go_next)
        self.next.setMinimumWidth(120)
        self.next.setDefault(True)
        footer.addWidget(self.back); footer.addStretch(); footer.addWidget(self.next)
        layout.addLayout(footer)
        shared_styles.bind_shared_styles(self, "CIRCLE_CHECKBOX_STYLE")
        self.show_page("welcome")

    def paintEvent(self, event):
        """Seam-free border plus a readability veil for Glass on bright desktops."""
        from ui.widgets.continuous_border import paint_content_frame
        super().paintEvent(event)
        paint_content_frame(self, veil=True)

    def _build_page(self, key):
        if key in {"welcome", "sources", "displays", "interaction"}:
            from ui.onboarding import basic_pages
            cls = getattr(basic_pages, {"welcome": "WelcomePage", "sources": "SourcesPage", "displays": "DisplaysPage", "interaction": "InteractionPage"}[key])
        elif key == "arrange":
            from ui.onboarding.arrange import ArrangePage
            cls = ArrangePage
        elif key == "setup":
            from ui.onboarding.setup_page import SetupPage
            cls = SetupPage
        else:
            from ui.onboarding import selection_pages
            cls = getattr(selection_pages, {"theme": "ThemePage", "widgets": "WidgetsPage", "visualizer": "VisualizerPage", "transitions": "TransitionsPage", "ready": "ReadyPage"}[key])
        page = cls(self.settings, self.stack)
        if key in {"sources", "displays"}:
            page.readinessChanged.connect(self._refresh_navigation)
        if key == "sources":
            page.finishRequested.connect(self.finish)
        if key == "welcome":
            page.importCompleted.connect(self._imported)
        scroll = QScrollArea(self.stack)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(shared_styles.SCROLL_AREA_STYLE)
        scroll.setWidget(page)
        self.stack.addWidget(scroll)
        self.pages[key] = (page, scroll)
        return page, scroll

    def step_keys(self):
        from ui.onboarding.state import selected_setup_dependencies
        return [key for key, _ in self.STEPS if key != "setup" or self.current_key == "setup" or selected_setup_dependencies(self.settings)]

    def show_page(self, key):
        # Account inputs/typed lookup workers exist only on their visible step.
        if self.current_key == "setup" and key != "setup" and "setup" in self.pages:
            page, scroll = self.pages.pop("setup")
            page.retire()
            self.stack.removeWidget(scroll)
            scroll.deleteLater()
        self.current_key = key
        page, scroll = self.pages.get(key) or self._build_page(key)
        page.refresh()
        # A scrollbar people notice, in the current theme (Theme may have changed).
        from ui.onboarding.selection_pages import _prominent_scrollbar_style
        scroll.verticalScrollBar().setStyleSheet(_prominent_scrollbar_style())
        self.stack.setCurrentWidget(scroll)
        scroll.verticalScrollBar().setValue(0)
        self._refresh_navigation()

    def _refresh_navigation(self):
        if self.current_key not in self.pages:
            return
        keys = self.step_keys()
        index = keys.index(self.current_key)
        self.progress.setText(f"STEP {index+1} OF {len(keys)}  ·  {dict(self.STEPS)[self.current_key].upper()}")
        self.back.setEnabled(index > 0)
        self.next.setText("Finish" if self.current_key == "ready" else "Next")
        self.next.setEnabled(self.pages[self.current_key][0].can_continue())

    def go_back(self):
        keys = self.step_keys(); index = keys.index(self.current_key)
        if index:
            self.show_page(keys[index-1])

    def go_next(self):
        page = self.pages[self.current_key][0]
        if not page.can_continue() or not page.leave():
            return
        if self.current_key == "ready":
            self.finish()
            return
        keys = self.step_keys()
        self.show_page(keys[keys.index(self.current_key)+1])

    def _arrange_pending(self):
        arrange = self.pages.get("arrange", (None,))[0]
        return arrange if arrange is not None and arrange.model is not None and arrange.model.pending else None

    def has_unsaved_changes(self) -> bool:
        return self.settings.pending or self._arrange_pending() is not None

    def _save(self) -> None:
        arrange = self._arrange_pending()
        if arrange is not None:
            arrange.apply()
        self.settings.commit()

    def _imported(self):
        """A successful import replaces the setup: drop the draft and finish."""
        self.settings.discard()
        self.close_setup(True)

    def finish(self):
        """Finish is the explicit save."""
        if has_image_sources(self.settings):
            self._save()
            self.close_setup(True)

    def request_close(self) -> None:
        """Skip (or closing Settings): ask before saving anything chosen so far."""
        if self.has_unsaved_changes():
            from ui.styled_popup import StyledPopup
            if StyledPopup.question(self, "Guided Setup", "Save The Changes You Made In Guided Setup?",
                                    yes_text="Save", no_text="Discard", default_to_yes=False):
                self._save()
        self.close_setup(False)

    def close_setup(self, completed: bool) -> None:
        """Retire account inputs and any Arrange draft, then hand back to Settings."""
        if self._closed:
            return
        self._closed = True
        if "setup" in self.pages:
            self.pages["setup"][0].retire()
        if "arrange" in self.pages:
            self.pages["arrange"][0].discard()
        # Anything not committed by now was declined: drop it and the live theme preview.
        self.settings.discard()
        self.finished.emit(bool(completed))
