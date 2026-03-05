"""Specialized QComboBox used by the Cursor Halo prototype.

The widget centralizes all the styling boilerplate required to make the
closed control and popup view reuse the SVG skin.  Keeping this logic in
one place avoids copy/paste in every tab and guarantees the popup is always
re-styled when Qt recreates its internal view.
"""
from __future__ import annotations

from typing import Literal, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QComboBox

from ui.tabs import shared_styles
from ui.widgets.combo_knob_overlay import ComboKnobController
from ui.widgets.control_shadow import attach_control_shadow


SizeVariant = Literal["regular", "compact", "mini", "hero"]


class StyledComboBox(QComboBox):
    """ComboBox that preloads the Jost font and styles its popup view."""

    def __init__(
        self,
        parent: Optional[object] = None,
        *,
        popup_stylesheet: Optional[str] = None,
        size_variant: SizeVariant = "regular",
    ) -> None:
        super().__init__(parent)
        shared_styles.ensure_custom_fonts()
        self._size_variant: SizeVariant = size_variant
        self._popup_stylesheet = popup_stylesheet or shared_styles.COMBOBOX_POPUP_VIEW_STYLE
        self._apply_base_properties()
        self._style_popup_view()
        # Dedicated overlay renders the right-hand knob at runtime so it never blurs when scaled.
        self._knob_overlay = ComboKnobController(self)
        attach_control_shadow(self)

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------
    def showPopup(self) -> None:  # type: ignore[override]
        """Ensure the popup picks up our stylesheet every time it opens."""
        self._style_popup_view()
        super().showPopup()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _apply_base_properties(self) -> None:
        font = QFont("Jost", 14)
        font.setBold(True)
        font.setFamilies(["Jost", "Segoe UI", "Arial", "Sans Serif"])
        self.setFont(font)
        self.setProperty("customCombo", True)
        self.setProperty("comboFlavor", "default")
        self.setProperty("comboSize", self._size_variant)

    def _style_popup_view(self) -> None:
        popup_view = self.view()
        if popup_view is None:
            return
        popup_view.setProperty("customComboPopup", True)
        popup_view.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        if self._popup_stylesheet:
            popup_view.setStyleSheet(self._popup_stylesheet)
