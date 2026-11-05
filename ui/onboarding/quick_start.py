"""Permanent lazy Settings entry point to Guided Setup; arranging widgets lives on the Layout tab."""
from PySide6.QtCore import Qt

from ui.onboarding.common import Page, action, silence_check, text_label, SILENCE_TEXT
from ui.onboarding.state import current_setup_summary


class QuickStartPage(Page):
    def __init__(self, settings, launch_wizard, parent=None):
        super().__init__(settings, parent, scrollable=True)
        self.body.addWidget(text_label("QUICK START", heading=True))
        self.body.addWidget(text_label("Start here for the essentials; arrange widgets and save layouts on the Layout tab."))
        self.summary = text_label(""); self.body.addWidget(self.summary)
        launch = action("Run Guided Setup Again", launch_wizard)
        launch.setMinimumWidth(240)
        self.body.addWidget(launch, alignment=Qt.AlignmentFlag.AlignLeft)
        # Quick Start is not Guided Setup itself, so name what the box hides.
        self.body.addWidget(silence_check(settings, "Hide Guided Setup From Now On"))
        self.body.addWidget(text_label(SILENCE_TEXT))
        self.body.addStretch()
        self.refresh()

    def refresh(self):
        summary = current_setup_summary(self.settings)
        self.summary.setText(f"{'Image sources ready' if summary['sources'] else 'Image sources needed'} · {summary['families']} widget families selected · {summary['transitions']} transitions")

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
