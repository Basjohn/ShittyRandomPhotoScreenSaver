# Custom Style Implementation

Reference guide for any bespoke control skinning (checkboxes, comboboxes, fonts).
Every prototype follows the same rules: SVGs and fonts live under `ui/assets/`,
they are baked into `ui/resources/assets.qrc`, and widgets opt-in through a
dynamic property so we can roll styles out gradually.

## Asset Inventory

### Circle checkbox (Display → Hard Exit)

- `circle_checkbox_unchecked.svg`
- `circle_checkbox_unchecked_hover.svg`
- `circle_checkbox_checked.svg`
- `circle_checkbox_checked_hover.svg`

### Cursor Halo Shape combobox prototype

- `combobox_closed.svg`
- `combobox_closed_hover.svg`

### Fonts

- `fonts/Jost-Regular.ttf`
- `fonts/Jost-SemiBold.ttf`
- `fonts/Jost-Bold.ttf`

> Tip: tweak any SVG in Illustrator with **Edit → Copy As → SVG Code…** and
> replace the file contents verbatim so paths stay clean.

## QRC Packaging and Compilation

Qt stylesheets resolve assets via the `:/` pseudo filesystem. Keep everything
under `/ui/assets` inside `ui/resources/assets.qrc`:

```xml
<RCC>
    <qresource prefix="/ui/assets">
        <file alias="circle_checkbox_unchecked.svg">../assets/circle_checkbox_unchecked.svg</file>
        <file alias="circle_checkbox_checked.svg">../assets/circle_checkbox_checked.svg</file>
        <file alias="circle_checkbox_unchecked_hover.svg">../assets/circle_checkbox_unchecked_hover.svg</file>
        <file alias="circle_checkbox_checked_hover.svg">../assets/circle_checkbox_checked_hover.svg</file>
        <file alias="fonts/Jost-Regular.ttf">../assets/fonts/Jost-Regular.ttf</file>
        <file alias="fonts/Jost-SemiBold.ttf">../assets/fonts/Jost-SemiBold.ttf</file>
        <file alias="fonts/Jost-Bold.ttf">../assets/fonts/Jost-Bold.ttf</file>
        <file alias="combobox_closed.svg">../assets/combobox_closed.svg</file>
        <file alias="combobox_closed_hover.svg">../assets/combobox_closed_hover.svg</file>
    </qresource>
</RCC>
```

Recompile whenever **any** SVG/font/QRC entry changes:

```powershell
python tools/regen_qrc.py
```

The helper wraps `pyside6-rcc`, falls back to `python -m PySide6.scripts.rcc`,
and auto-closes its success/error dialog after five seconds. Import the compiled
module early so resources register before QSS loads:

```python
from ui import resources  # pulls in assets_rc
```

## Circle Checkbox Styling

`ui/tabs/shared_styles.py` exposes `CIRCLE_CHECKBOX_STYLE`. Any checkbox that
sets `setProperty("circleIndicator", True)` inherits the SVG-backed indicator
and the revised padding that prevents text clipping in tight layouts.

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

QCheckBox[circleIndicator='true']::indicator:unchecked:hover {
    image: url(:/ui/assets/circle_checkbox_unchecked_hover.svg);
}

QCheckBox[circleIndicator='true']::indicator:checked {
    image: url(:/ui/assets/circle_checkbox_checked.svg);
}

QCheckBox[circleIndicator='true']::indicator:checked:hover {
    image: url(:/ui/assets/circle_checkbox_checked_hover.svg);
}
```

The Display tab’s "Hard Exit (ESC only)" checkbox was the pilot; all widgets
tabs now opt-in so the padding fix benefits every toggle.

## Styled ComboBox Subclass

`ui/widgets/styled_combo_box.py` contains `StyledComboBox`, a thin wrapper
around `QComboBox` that wires up the entire skin automatically:

- Calls `shared_styles.ensure_custom_fonts()` so the Jost family bundled in the
  QRC is registered. The widget sets a bold Jost font and falls back to
  Segoe UI → Arial → generic Sans Serif if Jost ever fails to load.
- Forces the `customCombo` dynamic property used by `COMBOBOX_STYLE`.
- Overrides `showPopup()` to restyle the popup view each time Qt recreates it.
- Tags the popup view/viewport, enables `WA_StyledBackground`, and applies
  `COMBOBOX_POPUP_VIEW_STYLE` directly so the dropdown becomes a single
  95 % opaque panel with a crisp white border.

Usage pattern:

```python
from ui.widgets import StyledComboBox

self.halo_shape_combo = StyledComboBox(self)
self.halo_shape_combo.setFixedWidth(192)
self.halo_shape_combo.setFixedHeight(42)
self.halo_shape_combo.addItems([
    "Circle", "Ring", "Crosshair", "Diamond",
    "Dot", "Cursor Pointer (Light)", "Cursor Pointer (Dark)",
])
```

Apply `COMBOBOX_STYLE` once at the dialog level (see `DisplayTab` for a working
example). As of Mar 3 2026 the Widgets tab now imports the same stylesheet so
every clock/weather/media/reddit dropdown inherits the skin without duplicating
QSS. Future tabs should follow the same pattern: import `COMBOBOX_STYLE`, append
it when finalizing the dialog stylesheet, and rely exclusively on
`StyledComboBox` for dropdowns.

### Key QSS selectors

```css
QComboBox[customCombo='true'] {
    min-width: 188px;
    max-width: 200px;
    min-height: 42px;
    max-height: 42px;
    padding: 4px 48px 4px 16px;
    font-family: 'Jost';
    font-weight: 700;
    font-size: 14px;
    letter-spacing: 0.4px;
    color: #ffffff;
    border: none;
    background: transparent;
    border-image: url(:/ui/assets/combobox_closed.svg) 0 0 0 0 stretch stretch;
}

QComboBox[customCombo='true']:hover,
QComboBox[customCombo='true']:focus,
QComboBox[customCombo='true']:on {
    border-image: url(:/ui/assets/combobox_closed_hover.svg) 0 0 0 0 stretch stretch;
    outline: none;
}

QComboBox[customCombo='true']::drop-down,
QComboBox[customCombo='true']::down-arrow {
    width: 0px;
    border: none;
    background: transparent;
    image: none;
}

QListView[customComboPopup='true'],
QListWidget[customComboPopup='true'] {
    background-color: rgba(18, 18, 18, 0.95);
    border: 2px solid #ffffff;
    border-radius: 14px;
    padding: 8px 8px 12px 8px;
    selection-background-color: rgba(255, 255, 255, 0.22);
    selection-color: #ffffff;
    color: #ffffff;
    font-family: 'Jost';
    font-weight: 600;
    font-size: 14px;
    letter-spacing: 0.4px;
}

QListView[customComboPopup='true']::item,
QListWidget[customComboPopup='true']::item {
    padding: 4px 6px;
    min-height: 22px;
    margin: 0px 2px;
    border-radius: 8px;
    background: transparent;
}
```

The Display tab’s "Cursor Halo Shape" control is the pilot implementation.
Widgets tab sections (Clock/Weather/Media/Reddit/Imgur) now share the same
hookup, so any newly added widgets only need to instantiate `StyledComboBox`—no
tab-local stylesheet work is required. Font pickers use the sibling subclass
`StyledFontComboBox`, which preserves the native font preview while inheriting
the same chrome.

### Styled Font ComboBox

`ui/widgets/styled_font_combo_box.py` subclasses `QFontComboBox`, applies the
`customCombo/comboFlavor='font'` properties, and reuses the popup styling logic.
Usage mirrors the standard combo box:

```python
from ui.widgets import StyledFontComboBox

self.weather_font_combo = StyledFontComboBox(size_variant="hero")
self.weather_font_combo.setCurrentFont(QFont("Segoe UI"))
```

### Rollout tracking

`Current_Plan.md` contains a live, auto-generated checklist of every checkbox
and combobox across the settings UI. Treat it as the canonical inventory during
rollouts: when introducing a new widget, add the corresponding row to the plan
before implementation and mark it ✅ only after verifying the runtime styling.

## SpinBox / LineEdit Styling

Rounded borders and hover states for `QSpinBox`, `QDoubleSpinBox`, and
`QLineEdit` now live in `SPINBOX_STYLE` (`ui/tabs/shared_styles.py`). The key
selectors keep all numeric inputs visually consistent with the combobox chrome:

```css
QSpinBox, QDoubleSpinBox, QLineEdit, QAbstractSpinBox {
    background-color: #282828;
    color: #ffffff;
    border: 2px solid #ffffff;
    border-radius: 18px;
    padding: 4px 48px 4px 16px;
}

QSpinBox > QLineEdit, QDoubleSpinBox > QLineEdit {
    background-color: #282828;
    border: none;
}
```

Append `SPINBOX_STYLE` to each tab/dialog stylesheet alongside
`COMBOBOX_STYLE` so text inputs and spinners share the same rounded border
language across the UI. The circular stepper buttons (white 10px dots) sit
inside the right padding zone; hover/pressed states dim to `#4d4d4d`/`#2d2d2d`.

### Specificity warning (Historical Bug 2026-03-05)

Never use an unqualified `QScrollArea QWidget { background: transparent; }`
rule. Its CSS specificity (002) beats type-only selectors like
`QSpinBox { background-color: #282828; }` (001) because QSpinBox IS-A QWidget.
Use direct-child combinators instead:

```css
/* SAFE — targets only viewport + content widget */
QScrollArea > QWidget > QWidget { background: transparent; }

/* UNSAFE — nukes ALL descendant backgrounds including inputs */
QScrollArea QWidget { background: transparent; }
```

The centralized `SCROLL_AREA_STYLE` in `shared_styles.py` uses the safe form.
All tabs import it rather than duplicating inline rules.

## Section Heading Typography

Two sources contribute to section heading font weight in the settings dialog:

- **`SECTION_HEADING_STYLE`** (`ui/tabs/shared_styles.py`) — Inline `QLabel` headings used
  as visual dividers within tab content. Font-weight **700** (Bold), Jost family,
  `letter-spacing: 0.3px`. Applied via `setStyleSheet()` on individual labels.

- **`QGroupBox::title`** (`ui/settings_theme.py`) — The pseudo-element styling for
  `QGroupBox` title text. Also font-weight **700**. Inherited from the dialog-level
  theme stylesheet rather than per-widget rules.

Both sources now use identical weight (700) for visual consistency. When adding new
section headings, use `SECTION_HEADING_STYLE` for standalone labels and rely on
`style_group_box()` + the theme cascade for `QGroupBox` titles.

### Color Swatch Label Alignment

Rows that host `ColorSwatchButton` controls sit taller because of their drop shadows,
so standard 34 px labels look low next to the chips. `ui/tabs/shared_styles.py`
exports `add_swatch_label()` / `SWATCH_LABEL_STYLE` (28 px height, positive top
margin) to keep those labels vertically centered. Each tab should create a local
`_swatch_row()` helper that mirrors `_aligned_row()` but calls `add_swatch_label()`
instead of `add_section_label()`. Tabs adopting the new helper: Media visualizer
builders, Widgets → Media/Weather/Clock/Reddit, and Transitions → Burn.

## Shadow Clearance (`margin-bottom`)

All input controls with `QGraphicsDropShadowEffect` need bottom margin to prevent
shadow clipping by parent layouts:

| Control | Source | Margin |
|---------|--------|--------|
| `QComboBox[customCombo]` | `COMBOBOX_STYLE` in `shared_styles.py` | 6px |
| `QSpinBox`, `QDoubleSpinBox`, `QLineEdit`, `QAbstractSpinBox` | `SPINBOX_STYLE` in `shared_styles.py` | 6px |
| `ColorSwatchButton` | Inline stylesheet in `ui/styled_popup.py` | 6px |

The shadow effect uses `offset: QPointF(4.5, 7.5)` and `blur_radius: 26.0`, extending
~20px below the widget. The 6px margin provides sufficient clearance for typical
layout scenarios. See `ui/widgets/control_shadow.py` for the shadow configuration.

## QGroupBox Border Seam Fix (`style_group_box()`)

`ui/tabs/shared_styles.py` exports `style_group_box(group_box)` — a helper that
applies both the body border rules and the `QGroupBox::title` subcontrol rules
as a single stylesheet. This eliminates corner seam artefacts caused by the
`::title` subcontrol disrupting `border-radius` arcs.

```python
from ui.tabs.shared_styles import style_group_box

group = QGroupBox("Transition Type")
style_group_box(group)
```

The helper uses one constant:
- **`SUBSECTION_DIVIDER_STYLE`** — body border, radius 18px, 1px solid white

All other QGroupBox properties (background, padding, margins, `::title` font/color)
are inherited from the dialog-level stylesheet in `settings_theme.py`. Keeping the
per-widget rule minimal avoids overriding the theme's cascade.

All 12 tab files (`transitions_tab.py`, `display_tab.py`, `accessibility_tab.py`,
`sources_tab.py`, `presets_tab.py`, `widgets_tab.py`, `widgets_tab_clock.py`,
`widgets_tab_weather.py`, `widgets_tab_media.py`, `widgets_tab_reddit.py`,
`widgets_tab_imgur.py`) now use `style_group_box()` instead of inline
`setStyleSheet` calls. New QGroupBox instances should always call this helper.

**Important:** `PresetDescriptionBox` is NOT a QGroupBox — it uses `#objectName`
selectors and must NOT use `style_group_box()`.

## Slider Styling

`SLIDER_STYLE` (`ui/tabs/shared_styles.py`) provides a dark glass indented
groove with a pill-shaped notch handle. Applied at the tab level alongside
other shared styles so all `NoWheelSlider` / `QSlider` instances inherit it.

```css
QSlider::groove:horizontal {
    height: 4px;
    background: qlineargradient(/* dark recessed glass gradient */);
    border: 1px solid rgba(12, 12, 12, 0.9);
    border-radius: 2px;
}

QSlider::handle:horizontal {
    width: 16px; height: 10px;
    margin: -4px 0; border-radius: 5px;
    background: qlineargradient(stop:0 #2e2e2e, stop:1 #1a1a1a);
    border: 1px solid #444444;
}
```

Includes hover, pressed, and disabled states. The `add-page` is transparent so
the unfilled portion blends with the container. `NoWheelSlider` (same module)
blocks mouse wheel events on all sliders to prevent accidental changes.

## Sidebar Tab Typography

Navigation buttons in `settings_dialog.py` now request Jost DemiBold by default
and receive Semi-Bold/Bold weights via `settings_theme.py` (Semi-Bold when idle,
Bold when selected). This piggybacks on the shared constants (`NAV_TAB_FONT_STYLE`
and `NAV_TAB_FONT_STYLE_ACTIVE`) defined in `ui/tabs/shared_styles.py`, keeping
sidebar typography consistent with the rest of the dialog.

## Context Menu Refresh

`widgets/context_menu.py` was updated to match the styled-controls rollout:

- Borders are fully opaque (3px solid white) with larger radii.
- Menu/submenu fonts now use Jost Semi-Bold/Bold at 14px/13px.
- Checkable items reuse the `circle_checkbox_*` SVGs so toggles visually align
  with the rest of the UI.

Any future menu additions should continue using these helpers—if a menu needs a
different palette, add a dedicated stylesheet constant next to the existing
`MENU_STYLE`/`SUBMENU_STYLE` definitions.

## Rebuild Checklist

Whenever artwork, fonts, or the QRC changes:

1. Update the source files in `ui/assets/` (ensure LF endings, strip demo text).
2. Run `python tools/regen_qrc.py` to regenerate `ui/resources/assets_rc.py`.
3. Commit the SVGs, fonts if changed, the `.qrc`, and the regenerated `.py`.
4. Launch the settings dialog to verify there are no `qt.svg` load errors and
   that the pilot controls still render as expected.

## Future Considerations

- **Rollout strategy:** Toggle `circleIndicator` / `customCombo` (or future
  properties) per widget so we can A/B designs before global adoption.
- **Theme variants:** For light themes, create alternate SVG sets or switch the
  assets to use `currentColor` fills where possible.
- **Additional controls:** Spinboxes/sliders can follow the same pattern—SVG in
  `ui/assets/`, alias via `assets.qrc`, gate via a dynamic property, document the
  selectors here.
- **Tests:** Add smoke tests that instantiate the styled controls to ensure
  resource lookups never regress, especially after relocating assets.
