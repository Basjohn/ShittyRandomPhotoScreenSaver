# Custom Style Implementation

Single source of truth for the settings dialog's visual styling, including the acrylic transparency system, button conventions, layout architecture, and lessons learned from failed approaches. `Spec.md` links here for authoritative recipes.

---

## 1. Dialog Architecture — Acrylic Transparency

The settings dialog uses **Windows DWM acrylic blur-behind** for its translucent background. This requires a specific widget attribute chain that must not be broken.

### Critical Requirements

| Requirement | Implementation |
|---|---|
| Translucent background | `WA_TranslucentBackground` on `SettingsDialog` plus Windows acrylic blur via `enable_acrylic_blur()` on first show |
| DWM blur | `core/windows/dwm_blur.py` → `enable_acrylic_blur()` with tint `rgba(24,24,24,80)` |
| No `QGraphicsDropShadowEffect` on dialog | Breaks per-pixel alpha chain — see §6 |
| Frameless window | `FramelessWindowHint` with custom title bar (`CustomTitleBar`) |

### Key Files

| File | Purpose |
|---|---|
| `ui/settings_dialog.py` | Dialog class, paintEvent, layout, tab buttons |
| `ui/settings_theme.py` | QSS styles loaded at theme time |
| `ui/tabs/shared_styles.py` | Shared QSS constants (group boxes, checkboxes, sliders, etc.) |
| `core/windows/dwm_blur.py` | Windows DWM acrylic API wrapper |

### Container Layout

```
QDialog (transparent, frameless, margins 0,0,0,0)
 └─ #dialogContainer (rgba(0,0,0,10), no border-radius)
     ├─ #customTitleBar (rgba(12,12,12,209))
     └─ content_layout (10px margins, 10px spacing)
         ├─ #sidebar (rgba(60,60,60,115), 1px white border, radius 8)
         │   └─ #tabButton × 7 (1px white border, drop shadow effect)
         └─ #contentArea (transparent, 1px white border, radius 8)
```

### Outer Border

The dialog has a **square** 2.5px white border painted in `paintEvent`. The border is square (no `border-radius`) which eliminates corner bleed permanently.

---

## 2. Button Styling Convention — Flat 2D

**All buttons use flat 2D styling.** This means:

- Uniform `border: 1px solid #ffffff` on all sides
- No 3D effect (no different top/left vs bottom/right borders)
- No `margin-top: 1px; margin-left: 1px` press shift
- Pressed state: slightly dimmed border `rgba(200,200,200,200)`

### Global QPushButton (settings_theme.py)

```css
QPushButton {
    background-color: rgba(45, 45, 45, 215);
    color: #ffffff;
    border-radius: 8px;
    padding: 7px 18px;
    font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';
    font-weight: 500;
    font-size: 12px;
    border: 1px solid #ffffff;
}
QPushButton:hover { background-color: rgba(60, 60, 60, 220); }
QPushButton:pressed {
    background-color: rgba(35, 35, 35, 220);
    border: 1px solid rgba(200, 200, 200, 200);
}
```

### Tab Buttons (#tabButton)

```css
#tabButton {
    background-color: rgba(43, 43, 43, 90);
    border: 1px solid #ffffff;
    border-radius: 6px;
    /* ... font and padding ... */
}
```

Each tab button also has a `QGraphicsDropShadowEffect` (blur=6, offset=1,2, color=rgba(0,0,0,120)) applied in code for a subtle drop shadow.

### Title Bar Buttons

Title bar buttons (`#titleBarButton`, `#titleBarCloseButton`) explicitly reset `padding: 0px`, `margin: 0px`, `border-radius: 4px` to prevent the global QPushButton style from leaking in.

### Locations That Define Button Styles

| Location | Buttons |
|---|---|
| `ui/settings_theme.py` | Global `QPushButton`, `#tabButton`, `#titleBarButton`, `#titleBarCloseButton` |
| `ui/tabs/sources_tab.py` | `_toggle_button_style()` — folder/RSS action buttons |
| `ui/tabs/widgets_tab.py` | `button_style` — Clocks/Weather/Media/etc. nav buttons |
| `ui/settings_about_tab.py` | `_make_link_button()` — PayPal/Goodreads/Amazon/GitHub links |

**All must use flat 2D style.** Do not introduce 3D borders anywhere.

---

## 3. Assets → QRC → Runtime

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

---

## 4. Shared Styles & Opt-ins

| Helper / Constant        | Opt-in contract                                       | Notes |
|-------------------------|-------------------------------------------------------|-------|
| `CIRCLE_CHECKBOX_STYLE` | `checkbox.setProperty("circleIndicator", True)`       | 22 px SVG indicator, spacing 12px |
| `COMBOBOX_STYLE`        | Append to tab stylesheet + instantiate `StyledComboBox` | Bold Jost, knob spacing, popup chrome |
| `COMBOBOX_POPUP_VIEW_STYLE` | Applied internally by `StyledComboBox.showPopup()` | 95 % opaque popup w/ white border |
| `SPINBOX_STYLE`         | Append to stylesheet                                   | Rounded inputs for spin/line edits |
| `SLIDER_STYLE`          | Append to stylesheet; use `NoWheelSlider`              | Dark-glass groove, pill handle |
| `SCROLL_AREA_STYLE`     | Append once                                            | Uses safe `QScrollArea > QWidget > QWidget` selector |
| `add_aligned_row*`      | Import from `ui/tabs/shared_styles.py`                  | 8px/12px spacing, wrap-aware labels |
| `SUBSECTION_DIVIDER_STYLE` | `style_group_box(group)` in shared_styles          | rgba(60,60,60,115), 1px white, radius 18 |

No tab should define bespoke `_aligned_row` helpers anymore.

---

## 5. QSS Alpha Value Rules

**Qt QSS `rgba()` alpha values MUST be integers 0–255.**

Float values (e.g., `0.8`) are silently truncated to `0`, making elements invisible. This was a source of multiple bugs during the styling work.

```css
/* WRONG — alpha truncated to 0, element invisible */
border: 1px solid rgba(110, 110, 110, 0.8);

/* CORRECT — alpha is integer 0-255 */
border: 1px solid rgba(110, 110, 110, 204);
```

---

## 6. Lessons Learned & Failed Approaches

### ❌ QBitmap Mask for Corner Clipping

**Goal**: Clip child widgets to rounded corners using a `QBitmap` mask on the container.

**What happened**: `QBitmap.fill(QColor(0,0,0))` + `QPainter.drawRoundedRect` on PySide6/Qt6 Windows produced an all-masked bitmap. The entire dialog went blank.

**Root cause**: PySide6's `QBitmap` 1-bit painting path doesn't reliably produce the expected color0/color1 output on Windows.

**Resolution**: Abandoned rounded outer border. Switched to **square outer border** which eliminates corner bleed by definition.

### ❌ Polygon Mask for Corner Clipping

**Goal**: Same as above, using `QPainterPath.toFillPolygon().toPolygon()`.

**What happened**: Polygon conversion loses sub-pixel precision at corners, producing visible jagged bleed.

**Resolution**: Same — square border.

### ❌ QGraphicsDropShadowEffect on Dialog

**Goal**: Apply a drop shadow effect for depth.

**What happened**: `QGraphicsDropShadowEffect` renders the entire widget tree to an intermediate pixmap, which breaks the per-pixel alpha chain required for DWM acrylic blur-behind. The acrylic effect disappears entirely.

**Resolution**: Do not apply `QGraphicsDropShadowEffect` to the dialog. It is safe on **small child widgets** (tab buttons, labels) but must never be applied to the dialog itself.

### ❌ Custom paintEvent Drop Shadow (with and without clipping)

**Goal**: Paint shadow rectangles in a margin area on the bottom-right of the dialog.

**What happened**: Without clipping, the shadow darkened all acrylic content. With `QPainterPath` clipping to exclude the container, the shadow only appeared in the margin strips but caused rendering artifacts when the dialog was maximized or on multi-monitor setups (extra pixels drawn outside the visible area).

**Root cause**: Any asymmetric margin on a frameless transparent dialog creates visible artefacts because the OS composites those margin pixels onto the desktop. The DWM acrylic layer doesn't cleanly separate from painted regions.

**Resolution**: Abandoned dialog drop shadow entirely. The white border alone provides sufficient visual separation.

### ❌ 3D Button Borders

**Goal**: Create depth with lighter top/left and darker bottom/right borders.

**What happened**: Inconsistent with flat 2D styling of comboboxes, checkboxes, and group boxes. Mixed visual language.

**Resolution**: All buttons use uniform `border: 1px solid #ffffff`. Depth is achieved via `QGraphicsDropShadowEffect` on individual child widgets only (tab buttons).

### ✅ Square Outer Border

The only reliable way to prevent corner bleed in Qt's QSS system is to use **no border-radius on the outer container**. This works because there are no sub-pixel edges to expose.

### ❌ Hidden Render / Offscreen Validation As Sign-off

**Goal**: Prove a rounded outer-shell experiment is safe by rendering the dialog offscreen and checking corner pixels.

**What happened**: The hidden-render path appeared clean, but live Windows runtime immediately showed all four corners bleeding and the custom title-bar/top segment visibly broken.

**Root cause**: Offscreen Qt rendering did not reproduce the real compositor/DWM behavior for the translucent frameless acrylic dialog. The path was useful only as a limited paint sanity check, not as a trustworthy live-window validation method.

**Resolution**: Treat live runtime inspection as the primary validation path for any future outer-shell experiment. Hidden render/offscreen captures are advisory only.

### ❌ True Outer-Window Rounding Without A New Architecture

**Goal**: Add a subtle radius directly to the settings dialog's true outer shell.

**What happened**: Even a very light-radius attempt broke the top/title-bar segment and bled at the corners in live runtime.

**Root cause**: This dialog is a frameless translucent acrylic window with a custom title bar and custom-painted outer border. Qt's parent-background propagation plus Windows compositor behavior make the true outer shell the worst possible seam for a casual radius tweak.

**Resolution**: Keep the outer shell square unless a future approach can clearly justify why the documented historical failures no longer apply. If rounded polish is revisited, prefer investigating an inner framed-card illusion or a Windows-native system-corner opt-in first, and only after validating that the dialog architecture actually qualifies for those paths.

### ✅ Acrylic Widget Background Assessment

Frosted glass effect for in-engine overlay widgets was assessed and determined not viable due to transition artifacts and architectural complexity. See `Docs/Acrylic_Widget_Background_Assessment.md` for the full analysis.

---

## 7. Color Reference

| Element | Color | Alpha |
|---|---|---|
| Acrylic tint | `rgba(24, 24, 24, 80)` | 80/255 |
| Dialog container | `rgba(0, 0, 0, 10)` | 10/255 |
| Title bar | `rgba(12, 12, 12, 209)` | 209/255 |
| Sidebar | `rgba(60, 60, 60, 115)` | 115/255 |
| Group boxes | `rgba(60, 60, 60, 115)` | 115/255 |
| Tab button normal | `rgba(43, 43, 43, 90)` | 90/255 |
| Tab button hover | `rgba(62, 62, 62, 120)` | 120/255 |
| Tab button checked | `rgba(62, 62, 62, 140)` | 140/255 |
| QPushButton normal | `rgba(45, 45, 45, 215)` | 215/255 |
| QPushButton hover | `rgba(60, 60, 60, 220)` | 220/255 |
| About card | `rgba(31, 31, 31, 200)` | 200/255 |
| White border | `#ffffff` (2.5px outer, 1px elements) | 255 |

---

## 8. Parity Pass Checklist

### 8.1 Form rows

- Label widths: Widgets 140 px, Visualizers 150 px, Display/Sources/Transitions/Presets/Accessibility 160 px.
- Margins: row `(0,8,0,8)`, inner layout `(0,0,0,0)`, spacing 12px.
- Labels: `FORM_ROW_LABEL_STYLE` (Jost 500) with wrap on by default.

### 8.2 Swatch rows

- Always call `add_swatch_label` (28 px baseline) with ≥12px vertical breathing room.

### 8.3 Sliders

- All sliders use `NoWheelSlider` + `SLIDER_STYLE`.

### 8.4 Checkbox rows

- Circle checkboxes: `setContentsMargins(0,12,0,12)`.

### 8.5 Re-running the pass

1. Walk `Docs/Propagation_Inventory.md` top to bottom.
2. Confirm helper usage, label widths, slider chrome, StyledComboBox usage.
3. Capture screenshots & verify in the running settings dialog.

---

## 9. Specificity & Shadow Clearance

- Never use `QScrollArea QWidget { ... }`; always use the direct-child selector in `SCROLL_AREA_STYLE`.
- Styled combos, spinboxes, and `ColorSwatchButton` keep a 6px bottom margin for drop-shadow clearance.

---

## 10. Text Rendering

The dialog sets `PreferNoHinting` + `PreferAntialias | PreferQuality` font style strategy on the dialog font for smoother text rendering against the translucent background.

---

## 11. Documentation Links

- `Docs/Propagation_Inventory.md` — per-file status.
- `Docs/Acrylic_Widget_Background_Assessment.md` — assessment of frosted glass for in-engine widgets (not viable).
- `Current_Plan.md` — record of active remediation work.
- `Spec.md` (UI Component Specifications) — references this document.

---

## 12. Automation

- `tools/check_ui_parity.py` statically scans `ui/tabs/**` and flags raw `QSlider`, `QComboBox`, or `QFontComboBox` usage.
- Usage:

  ```powershell
  python tools/check_ui_parity.py
  python tools/check_ui_parity.py ui/tabs/widgets_tab_weather.py
  ```

- Extend `BANNED_CALLS` / `BANNED_BASES` when the styling contract grows.
