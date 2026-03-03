"""Styled QFontComboBox that reuses the custom combobox chrome."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFontComboBox

from ui.tabs import shared_styles
from ui.widgets.styled_combo_box import SizeVariant


class StyledFontComboBox(QFontComboBox):
    """Font picker that matches StyledComboBox visuals."""

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

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------
    def showPopup(self) -> None:  # type: ignore[override]
        """Ensure the popup keeps the themed background each time."""
        self._style_popup_view()
        super().showPopup()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _apply_base_properties(self) -> None:
        self.setProperty("customCombo", True)
        self.setProperty("comboFlavor", "font")
        self.setProperty("comboSize", self._size_variant)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Filter out non-scalable bitmap fonts (e.g., "Small Fonts", "System") that
        # trigger DirectWrite CreateFontFaceFromHDC warnings on Windows.
        self.setFontFilters(QFontComboBox.FontFilter.ScalableFonts)
        # QFontComboBox defaults to editable; once we hide the drop-down arrow in QSS
        # there is no obvious click target to open the popup. Keep it non-editable so
        # the entire control behaves like a button and the popup can open normally.
        self.setEditable(False)

    def _style_popup_view(self) -> None:
        popup_view = self.view()
        if popup_view is None:
            return
        popup_view.setProperty("customComboPopup", True)
        popup_view.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        if self._popup_stylesheet:
            popup_view.setStyleSheet(self._popup_stylesheet)
