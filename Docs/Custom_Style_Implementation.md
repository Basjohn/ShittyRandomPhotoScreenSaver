# Custom Style Implementation

Single source of truth for bespoke settings chrome (checkboxes, combos, sliders, inline labels) plus the “parity pass” procedure we used to keep every tab aligned with the Bubble builder baseline. `Spec.md` links here for authoritative recipes.

---

## 1. Assets → QRC → Runtime

1. Author SVGs/fonts under `ui/assets/`.
2. Add each file to `ui/resources/assets.qrc` under `/ui/assets`.
3. Rebuild resources after **any** asset/QRC change:

   ```powershell
   python tools/regen_qrc.py
   ```

4. Import before loading QSS:

   ```python
   from ui import resources
   ```

**Canonical set**

| Category        | Files                                                                  |
|-----------------|-------------------------------------------------------------------------|
| Circle checkbox | `circle_checkbox_unchecked.svg`, `_hover.svg`, `checked.svg`, `checked_hover.svg` |
| Combo shell     | `combobox_closed.svg`, `combobox_closed_hover.svg`                      |
| Fonts           | `fonts/Jost-{Regular,SemiBold,Bold}.ttf`                                |

*Tip:* Illustrator → **Edit → Copy As → SVG Code** preserves clean paths.

---

## 2. Shared Styles & Opt-ins

| Helper / Constant        | Opt-in contract                                       | Notes |
|-------------------------|-------------------------------------------------------|-------|
| `CIRCLE_CHECKBOX_STYLE` | `checkbox.setProperty("circleIndicator", True)`       | 22 px SVG indicator, spacing 12px |
| `COMBOBOX_STYLE`        | Append to tab stylesheet + instantiate `StyledComboBox` | Bold Jost, knob spacing, popup chrome |
| `COMBOBOX_POPUP_VIEW_STYLE` | Applied internally by `StyledComboBox.showPopup()` | 95 % opaque popup w/ white border |
| `SPINBOX_STYLE`         | Append to stylesheet                                   | Rounded inputs for spin/line edits |
| `SLIDER_STYLE`          | Append to stylesheet; use `NoWheelSlider`              | Dark-glass groove, pill handle |
| `SCROLL_AREA_STYLE`     | Append once                                            | Uses safe `QScrollArea > QWidget > QWidget` selector |
| `add_aligned_row*`      | Import from `ui/tabs/shared_styles.py`                  | 8px/12px spacing, wrap-aware labels |
| `add_swatch_label`      | Local `_swatch_row` wrappers call this                 | 28 px label height for swatches |

No tab should define bespoke `_aligned_row` helpers anymore.

---

## 3. Styled Widget Catalogue

| Widget                | Location                              | Purpose |
|----------------------|---------------------------------------|---------|
| `StyledComboBox`     | `ui/widgets/styled_combo_box.py`      | Registers fonts, sets `customCombo=true`, handles popup view |
| `StyledFontComboBox` | `ui/widgets/styled_font_combo_box.py` | Same chrome, keeps font previews |
| `NoWheelSlider`      | `ui/tabs/shared_styles.py`            | Blocks wheel events, ensures consistent offsets |
| `create_inline_label`| `ui/tabs/shared_styles.py`            | Inline “px/%” captions with optional min width |

---

## 4. Parity Pass Checklist

Audits every tab that consumes the shared helpers. Use this as the canonical drift checklist.

### 4.1 Form rows
- Label widths: Widgets 140 px, Visualizers 150 px, Display/Sources/Transitions/Presets/Accessibility 160 px.
- Margins: row `(0,8,0,8)`, inner layout `(0,0,0,0)`, spacing 12px.
- Labels: `FORM_ROW_LABEL_STYLE` (Jost 500) with wrap on by default.
- Inline units: `create_inline_label(minimum_width=60)` placed 12px after the control.

### 4.2 Swatch rows
- Always call `add_swatch_label` (28 px baseline) and leave ≥12px vertical breathing room to avoid drop-shadow clipping.

### 4.3 Sliders
- All sliders use `NoWheelSlider` + `SLIDER_STYLE`.
- Slider column margins `(0,3,0,0)` match the preset slider groove.
- Preset sliders additionally set `objectName="presetModeSlider"` and sit next to `_PresetNotchBar`/`_RatioNotchBar` notch bars.

### 4.4 Checkbox rows
- Circle checkboxes inserted between aligned rows receive `setContentsMargins(0,12,0,12)` to keep drop shadows aligned.

### 4.5 Required special cases
- **Sources → Usage Ratio:** Ratio label lives in the aligned row (`label_width=160`). Local/RSS labels sit inside the slider frame with `.ratioValue { padding-top: 2px; }` so their baseline matches the section label.
- **Starfield nebula tints:** The second tint caption uses `create_inline_label(minimum_width=60)` instead of another `add_section_label`, keeping the dual swatch layout centered.
- **Accessibility tab:** `_aligned_row_widget` delegates to the shared helper; `_add_value_label` keeps value captions at 72 px so dimming/pixel-shift sliders match historical layouts.
- **Visualizer builders (Spectrum/Blob/Sine/Helix/Osc/Starfield):** All advanced + technical rows use `label_width=150` shared helpers; ghost containers keep `(0,0,0,12)` margins.
- **Preset slider:** Helper tooltips + inline labels rely on `FORM_ROW_LABEL_STYLE`, ensuring Presets tab, Sources ratio slider, and visualizer preset slider share the same chrome.

### 4.6 Re-running the pass
1. Walk `Docs/Propagation_Inventory.md` top to bottom.
2. For each entry confirm helper usage, label widths, swatch rows, slider chrome, StyledComboBox/SPINBOX usage.
3. Capture screenshots & mark `[x]` only after verifying in the running settings dialog.

---

## 5. Control Recipes

### Circle checkbox
```css
QCheckBox[circleIndicator='true'] {
    spacing: 12px;
    padding: 2px 10px 2px 4px;
    min-height: 28px;
}
QCheckBox[circleIndicator='true']::indicator {
    width: 22px;
    height: 22px;
    border-radius: 11px;
    margin: 2px 8px 2px 2px;
}
QCheckBox[circleIndicator='true']::indicator:unchecked {
    image: url(:/ui/assets/circle_checkbox_unchecked.svg);
}
/* `_hover` and checked variants use the other SVGs */
```

### Combo boxes
```css
QComboBox[customCombo='true'] {
    min-width: 188px;
    min-height: 42px;
    padding: 4px 48px 4px 16px;
    font-family: 'Jost';
    font-weight: 700;
    letter-spacing: 0.4px;
    border-image: url(:/ui/assets/combobox_closed.svg) 0 0 0 0 stretch stretch;
}
QComboBox[customCombo='true']:hover,
QComboBox[customCombo='true']:focus {
    border-image: url(:/ui/assets/combobox_closed_hover.svg) 0 0 0 0 stretch stretch;
}
QComboBox[customCombo='true']::drop-down,
QComboBox[customCombo='true']::down-arrow {
    width: 0px;
    image: none;
}
```

### Spinboxes / Line edits
```css
QSpinBox, QDoubleSpinBox, QLineEdit, QAbstractSpinBox {
    background-color: #282828;
    color: #ffffff;
    border: 2px solid #ffffff;
    border-radius: 18px;
    padding: 4px 48px 4px 16px;
}
QSpinBox > QLineEdit { border: none; }
```

### Sliders
```css
QSlider::groove:horizontal {
    height: 4px;
    background: qlineargradient(stop:0 #1b1b1b, stop:1 #303030);
    border: 1px solid rgba(12,12,12,0.9);
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 16px;
    height: 10px;
    margin: -4px 0;
    border-radius: 5px;
    background: qlineargradient(stop:0 #2e2e2e, stop:1 #1a1a1a);
    border: 1px solid #444444;
}
```

### QGroupBox seam fix
```python
from ui.tabs.shared_styles import style_group_box

group = QGroupBox("Transition Type")
style_group_box(group)
```
Applies `SUBSECTION_DIVIDER_STYLE` (radius 18px, 1px solid white) and synchronized `QGroupBox::title` rules so borders stay continuous. Do **not** use on `PresetDescriptionBox` (not a QGroupBox).

---

## 6. Specificity & Shadow Clearance

- Never use `QScrollArea QWidget { ... }`; always use the direct-child selector provided in `SCROLL_AREA_STYLE`.
- Styled combos, spinboxes/line edits, and `ColorSwatchButton` keep a 6px bottom margin to prevent clipping the shared `QGraphicsDropShadowEffect` (offset `QPointF(4.5, 7.5)`, blur 26).

---

## 7. Documentation Links

- `Docs/Propagation_Inventory.md` – per-file status.
- `Current_Plan.md` – record of active remediation work.
- `Spec.md` (UI Component Specifications) – references this document for implementation details.

---

## 8. Future Work

- Light-theme SVG variants keyed off a future `appTheme` property.
- Screenshot/pixel-diff parity tooling for automated regression detection.
- Smoke tests that instantiate each styled control to ensure resources load after refactors.
- New shared recipes for toggles/radio buttons following the same asset/QRC/property pattern.

---

## 9. Automation

- `tools/check_ui_parity.py` statically scans `ui/tabs/**` (or any paths you pass) and flags raw `QSlider`, `QComboBox`, or `QFontComboBox` usage, plus direct subclassing of those widgets. This keeps future contributors from bypassing `NoWheelSlider`, `StyledComboBox`, or `StyledFontComboBox`.
- Usage:

  ```powershell
  python tools/check_ui_parity.py  # scans ui/tabs by default
  python tools/check_ui_parity.py ui/tabs/widgets_tab_weather.py
  python tools/check_ui_parity.py --skip ui/tabs/dev_only.py
  ```

- Extend `BANNED_CALLS` / `BANNED_BASES` inside the script whenever the styling contract grows (e.g., to enforce future toggle helpers). The script exits non-zero and prints `path:line:column` diagnostics naming every violating element.
