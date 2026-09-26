"""Permanent lazy Settings entry point; Arrange is built only on demand."""
from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout

from core.settings.layout_slots import VALID_LAYOUT_SLOT_IDS, get_layout_slot_payload, save_layout_slot
from ui.onboarding.common import Page, action, silence_check, text_label, SILENCE_TEXT
from ui.onboarding.state import current_setup_summary
from ui.styled_popup import StyledPopup
from ui.tabs.shared_styles import build_bucket_toggle
from ui.widgets.styled_combo_box import StyledComboBox


class QuickStartPage(Page):
    def __init__(self, settings, launch_wizard, parent=None):
        super().__init__(settings, parent, scrollable=True)
        self.arrange = None
        self.body.addWidget(text_label("QUICK START", heading=True))
        self.body.addWidget(text_label("Start here for the essentials, or return to arrange your widgets and save a layout."))
        self.summary = text_label(""); self.body.addWidget(self.summary)
        launch = action("Run Guided Setup Again", launch_wizard)
        launch.setMinimumWidth(240)
        self.body.addWidget(launch, alignment=Qt.AlignmentFlag.AlignLeft)
        self.arrange_toggle, _, self.arrange_layout = build_bucket_toggle(self.body, "Arrange Widgets", on_toggle=self._open_arrange)
        _, _, slots = build_bucket_toggle(self.body, "Layout Slots")
        slots.addWidget(text_label("Slots include fonts, positions, monitors, Clock modes and widget visibility. Load into the editor to review before applying."))
        self.slots = StyledComboBox(); slots.addWidget(self.slots)
        row = QHBoxLayout()
        row.addWidget(action("Load into editor", self.load_slot, secondary=True))
        self.save_slot_button = action("Save to slot", self.save_slot, secondary=True)
        row.addWidget(self.save_slot_button); row.addStretch(); slots.addLayout(row)
        self.slot_status = text_label(""); slots.addWidget(self.slot_status)
        slots.addWidget(text_label("On the saver, 1–9 and 0 load a slot; Shift with the same key saves to it."))
        _, _, reset = build_bucket_toggle(self.body, "Reset Widget Layouts")
        reset.addWidget(text_label("Restore authored parent positions and monitor routes and clear CUSTOM placements. Widget content settings, accounts and saved layout slots are kept."))
        reset.addWidget(action("Reset Widget Layouts", self.reset_layouts, secondary=True))
        self.body.addWidget(silence_check(settings))
        self.body.addWidget(text_label(SILENCE_TEXT))
        self.body.addStretch()
        self.refresh()

    def _open_arrange(self, checked):
        if checked and self.arrange is None:
            from ui.onboarding.arrange import ArrangePage
            self.arrange = ArrangePage(self.settings, self, show_slots=False)
            self.arrange.pendingChanged.connect(self._pending_changed)
            self.arrange_layout.addWidget(self.arrange)
        if checked:
            self.arrange.refresh()

    def _pending_changed(self, pending):
        self.save_slot_button.setEnabled(not pending)
        self.slot_status.setText("Apply or discard your Arrange draft before saving a slot." if pending else "")

    def refresh(self):
        summary = current_setup_summary(self.settings)
        self.summary.setText(f"{'Image sources ready' if summary['sources'] else 'Image sources needed'} · {summary['families']} widget families selected · {summary['transitions']} transitions")
        widgets = self.settings.get("widgets")
        selected = self.slots.currentData()
        self.slots.clear()
        for slot_id in VALID_LAYOUT_SLOT_IDS:
            payload = get_layout_slot_payload(widgets, slot_id)
            if payload is None:
                description = "empty"
            else:
                sections = payload.get("widgets", {})
                enabled = [key.replace('_', ' ').title() for key, section in sections.items() if section.get("enabled")]
                displays = sorted({str(section["monitor"]) for section in sections.values() if "monitor" in section and section.get("enabled")})
                description = ", ".join(enabled[:3]) + (f" +{len(enabled)-3}" if len(enabled)>3 else "") if enabled else "saved layout"
                if displays: description += " · displays " + ", ".join(displays)
            self.slots.addItem(f"{slot_id} — {description}", slot_id)
        if selected is not None:
            self.slots.setCurrentIndex(self.slots.findData(selected))
        if self.arrange is not None:
            self.arrange.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def load_slot(self):
        slot_id = self.slots.currentData()
        if get_layout_slot_payload(self.settings.get("widgets"), slot_id) is None:
            self.slot_status.setText("This slot is empty. Arrange a layout and save it here first."); return
        self.arrange_toggle.setChecked(True)
        self._open_arrange(True)
        self.arrange.load_slot(slot_id)

    def save_slot(self):
        if self.arrange is not None and self.arrange.model.pending:
            self._pending_changed(True); return
        slot_id = self.slots.currentData()
        widgets = deepcopy(self.settings.get("widgets"))
        if get_layout_slot_payload(widgets, slot_id) is not None and not StyledPopup.question(self, "Replace layout slot", f"Replace saved slot {slot_id}?", yes_text="Replace", no_text="Cancel", default_to_yes=False):
            return
        if save_layout_slot(widgets, slot_id):
            self.settings.set("widgets", widgets)
            self.refresh()
            self.slot_status.setText(f"Saved slot {slot_id}.")

    def reset_layouts(self):
        if not StyledPopup.question(self, "Reset Widget Layouts", "Restore authored parent positions and monitor routes and clear CUSTOM placements? Content settings, accounts and saved layout slots are kept.", yes_text="Reset", no_text="Cancel", default_to_yes=False):
            return
        from rendering.widget_descriptors import restore_all_custom_layouts_to_authored_layout
        widgets = deepcopy(self.settings.get("widgets"))
        if restore_all_custom_layouts_to_authored_layout(widgets):
            self.settings.set("widgets", widgets)
        if self.arrange is not None:
            self.arrange.discard()
        self.refresh()
