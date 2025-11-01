# Theme Styling Guide

This document explains the modern dark and light themes, how to apply them, and how to customize them for your application.

## Table of Contents

1. [Overview](#overview)
2. [Applying Themes](#applying-themes)
3. [Theme Structure](#theme-structure)
4. [Customization](#customization)
5. [Component Styles](#component-styles)
6. [Color Palette](#color-palette)

---

## Overview

The framework includes two production-ready themes:

- **Dark Theme**: High-contrast professional dark theme with 43,43,43 base and white borders
- **Light Theme**: Clean accessible light theme with 212,212,212 base and black borders

Both themes support:
- All standard Qt widgets
- Custom components (buttons, combo boxes, overlays)
- Hover/pressed/disabled states
- High DPI scaling
- Transparency and opacity effects

---

## Applying Themes

### Basic Application

```python
from PySide6.QtWidgets import QApplication
from pathlib import Path

app = QApplication(sys.argv)

# Load theme QSS file
theme_path = Path("themes/dark.qss")
with open(theme_path, "r", encoding="utf-8") as f:
    app.setStyleSheet(f.read())

# Or use the theme manager
from core.theming import ThemeManager

theme_manager = ThemeManager()
theme_manager.apply_theme("dark")  # or "light"
```

### Runtime Theme Switching

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.theme_manager = ThemeManager()
        
        # Create theme toggle button
        toggle_button = QPushButton("Toggle Theme")
        toggle_button.clicked.connect(self.toggle_theme)
        
        # Apply initial theme from settings
        theme = settings.get("appearance.theme", "dark")
        self.theme_manager.apply_theme(theme)
    
    def toggle_theme(self):
        current = self.theme_manager.current_theme()
        new_theme = "light" if current == "dark" else "dark"
        self.theme_manager.apply_theme(new_theme)
        settings.set("appearance.theme", new_theme)
```

### Per-Widget Styling

```python
# Apply theme to specific widget
widget = QWidget()
widget.setStyleSheet("""
    QWidget {
        background-color: rgba(43, 43, 43, 0.8);
        border: 2px solid rgba(255, 255, 255, 1.0);
        border-radius: 8px;
    }
""")

# Or use objectName for selective styling
widget.setObjectName("customWidget")
# Then in QSS:
# QWidget#customWidget { background-color: red; }
```

---

## Theme Structure

Both theme files follow this structure:

### 1. Base Styles

Global styling for the application foundation.

```css
/* Main window container */
QMainWindow {
    background-color: rgba(0, 0, 0, 0);  /* Transparent for overlays */
    border: 2px solid rgba(255, 255, 255, 0.95);
    border-radius: 10px;
    padding: 0;
    margin: 0;
}
```

### 2. Overlay Styling

Specialized styles for overlay windows (see OVERLAY_GUIDE.md for details).

```css
/* Border frame with 5px border */
QFrame#borderOverlay {
    background-color: rgba(43, 43, 43, 0.8);
    border: 5px solid rgba(255, 255, 255, 1.0);
    border-radius: 6px;
}

/* DWM mode - transparent background */
QFrame#borderOverlay[dwm="true"] {
    background-color: transparent;
    border: 5px solid rgba(255, 255, 255, 1.0);
}

/* Backdrop for content */
QFrame#overlayBackdrop {
    background-color: rgba(43, 43, 43, 1.0);
    border: none;
    border-radius: 1px;
}
```

### 3. Title Bar

Custom title bar for frameless windows.

```css
/* Title bar frame */
QFrame#titleBar {
    background-color: rgba(26, 26, 26, 0.9);
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    border-bottom: 2px solid rgba(255, 255, 255, 1.0);
    height: 60px;
}

/* Title icon */
QFrame#titleBar QLabel#titleIcon {
    width: 55px;
    height: 55px;
    margin: 0 8px 0 12px;
}

/* Title text */
QFrame#titleBar QLabel#titleLabel {
    color: rgba(255, 255, 255, 1.0);
    font-weight: bold;
    font-size: 24px;
}

/* Close button */
QFrame#titleBar QPushButton#closeButton {
    background-color: transparent;
    color: rgba(255, 255, 255, 1.0);
    border: none;
    font-size: 20px;
    min-width: 24px;
    min-height: 24px;
}

QFrame#titleBar QPushButton#closeButton:hover {
    color: rgba(0, 0, 0, 1.0);  /* Inverts on hover */
}
```

### 4. Common Components

Standard Qt widget styling.

```css
/* ComboBox */
QComboBox {
    background-color: rgba(42, 42, 42, 1.0);
    color: rgba(255, 255, 255, 1.0);
    border: 2px solid rgba(255, 255, 255, 1.0);
    border-radius: 16px;
    padding: 6px 15px 6px 30px;
    font-family: 'Segoe UI';
    font-size: 12px;
    font-weight: bold;
}

/* Dropdown arrow */
QComboBox::down-arrow {
    width: 6px;
    height: 6px;
    background: rgba(255, 255, 255, 1.0);
    border-radius: 3px;
}

/* Dropdown menu */
QComboBox QAbstractItemView {
    background-color: rgba(42, 42, 42, 1.0);
    border: 2px solid rgba(102, 102, 102, 1.0);
    border-radius: 8px;
}
```

### 5. Context Menus

Right-click menu styling.

```css
QMenu {
    background-color: rgba(42, 42, 42, 1.0);
    color: rgba(255, 255, 255, 1.0);
    border: 1px solid rgba(68, 68, 68, 1.0);
    padding: 4px;
    border-radius: 4px;
}

QMenu::item {
    padding: 6px 25px 6px 20px;
    border-radius: 2px;
}

QMenu::item:selected {
    background-color: rgba(58, 58, 58, 1.0);
}
```

### 6. Custom Buttons

Application-specific button styles with objectName selectors.

```css
/* Action button - primary actions */
QPushButton#actionButton {
    background-color: rgba(42, 42, 42, 1.0);
    color: rgba(255, 255, 255, 1.0);
    border: 2px solid rgba(255, 255, 255, 1.0);
    border-radius: 20px;
    padding: 5px 15px;
    font-weight: bold;
    font-size: 12px;
    text-transform: uppercase;
}

/* Small select button - toggle states */
QPushButton#QSmolselect {
    background-color: rgba(35, 35, 35, 1.0);
    border: 1px solid rgba(255, 255, 255, 1.0);
    border-radius: 10px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: bold;
}

QPushButton#QSmolselect:checked {
    background-color: rgba(0, 0, 0, 1.0);
}
```

---

## Customization

### Changing Colors

The QSS files use `rgba()` notation for easy color customization:

```css
/* Dark theme base */
background-color: rgba(43, 43, 43, 0.8);  /* R, G, B, Alpha */

/* Light theme base */
background-color: rgba(212, 212, 212, 0.8);
```

**Tip**: Search for `color-picker:` comments in the QSS files to find all customizable colors.

### Custom Color Palette

Create a derived theme:

```python
# custom_dark.qss
@import "dark.qss";

/* Override specific colors */
QMainWindow {
    border-color: rgba(100, 200, 255, 0.95);  /* Custom blue border */
}

QFrame#borderOverlay {
    border-color: rgba(100, 200, 255, 1.0);
}
```

### Adding Custom Components

1. **Give your widget an objectName**:

```python
my_button = QPushButton("Custom")
my_button.setObjectName("myCustomButton")
```

2. **Add QSS styling**:

```css
QPushButton#myCustomButton {
    background-color: rgba(100, 50, 150, 1.0);
    color: rgba(255, 255, 255, 1.0);
    border: 2px solid rgba(150, 100, 200, 1.0);
    border-radius: 8px;
    padding: 8px 16px;
}

QPushButton#myCustomButton:hover {
    background-color: rgba(120, 70, 170, 1.0);
}

QPushButton#myCustomButton:pressed {
    background-color: rgba(80, 30, 130, 1.0);
}
```

### Dynamic Property Selectors

Use dynamic properties for state-based styling:

```python
# Set dynamic property
widget.setProperty("state", "error")
widget.style().unpolish(widget)
widget.style().polish(widget)
```

```css
/* Style based on property */
QWidget[state="error"] {
    border: 2px solid rgba(255, 0, 0, 1.0);
}

QWidget[state="success"] {
    border: 2px solid rgba(0, 255, 0, 1.0);
}

QWidget[state="warning"] {
    border: 2px solid rgba(255, 255, 0, 1.0);
}
```

---

## Component Styles

### Pre-styled Components

The themes include pre-styled components for common UI patterns:

#### QComboArrow

Narrow button with ">>" for expanding options.

```python
arrow_button = QPushButton(">>")
arrow_button.setObjectName("QComboArrow")
```

#### QBasicBitchButton

General-purpose button, smaller than action buttons.

```python
button = QPushButton("OK")
button.setObjectName("QBasicBitchButton")
```

#### QSmolselect / QSmolselectMini

Toggle buttons for compact selections.

```python
# Regular toggle
toggle = QPushButton("Option")
toggle.setObjectName("QSmolselect")
toggle.setCheckable(True)

# Mini toggle (for numbers)
mini = QPushButton("5")
mini.setObjectName("QSmolselectMini")
mini.setCheckable(True)
```

#### Resize Indicator

Custom widget for resize drag indicator.

```python
class ResizeIndicator(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("resizeIndicator")
```

```css
ResizeIndicator#resizeIndicator {
    qproperty-indicatorColor: rgba(255,255,255,1.0);
    background: transparent;
}
```

---

## Color Palette

### Dark Theme Colors

| Element | Color | RGBA |
|---------|-------|------|
| Base Background | Dark Gray | `rgba(43, 43, 43, 0.8)` |
| Title Bar | Darker Gray | `rgba(26, 26, 26, 0.9)` |
| Primary Border | White | `rgba(255, 255, 255, 1.0)` |
| Text Primary | White | `rgba(255, 255, 255, 1.0)` |
| Text Secondary | Gray | `rgba(255, 255, 255, 0.8)` |
| Hover Background | Lighter Gray | `rgba(58, 58, 58, 1.0)` |
| Pressed Background | Black | `rgba(0, 0, 0, 1.0)` |
| Disabled Text | Dark Gray | `rgba(102, 102, 102, 1.0)` |
| Selection | Medium Gray | `rgba(58, 58, 58, 1.0)` |

### Light Theme Colors

| Element | Color | RGBA |
|---------|-------|------|
| Base Background | Light Gray | `rgba(212, 212, 212, 0.8)` |
| Title Bar | Lighter Gray | `rgba(229, 229, 229, 0.9)` |
| Primary Border | Black | `rgba(26, 26, 26, 1.0)` |
| Text Primary | Black | `rgba(0, 0, 0, 1.0)` |
| Text Secondary | Dark Gray | `rgba(0, 0, 0, 0.8)` |
| Hover Background | Medium Gray | `rgba(197, 197, 197, 1.0)` |
| Pressed Background | White | `rgba(255, 255, 255, 1.0)` |
| Disabled Text | Gray | `rgba(153, 153, 153, 1.0)` |
| Selection | Medium Gray | `rgba(197, 197, 197, 1.0)` |

### Color Extraction

All colors in the QSS files are marked with `/* color-picker: */` comments for easy extraction and modification:

```css
/* color-picker: background-color: #2B2B2B */
background-color: rgba(43, 43, 43, 0.8);

/* color-picker: border: #FFFFFF */
border: 2px solid rgba(255, 255, 255, 1.0);
```

---

## Best Practices

### 1. Use Object Names

Always use `setObjectName()` for custom components:

```python
my_widget.setObjectName("myCustomWidget")
```

Then style with:

```css
QWidget#myCustomWidget { ... }
```

### 2. Maintain State Styles

Always define hover, pressed, disabled, and checked states:

```css
QPushButton#myButton { ... }
QPushButton#myButton:hover { ... }
QPushButton#myButton:pressed { ... }
QPushButton#myButton:disabled { ... }
QPushButton#myButton:checked { ... }
```

### 3. Use Consistent Spacing

Keep padding/margin consistent with theme defaults:

```css
padding: 6px 12px;  /* vertical horizontal */
margin: 8px;
border-radius: 8px;
```

### 4. Respect Opacity Patterns

The theme uses specific opacity values:

- **Windows**: 0.8 for base, 0.9 for title bars
- **Overlays**: 0.8 for backgrounds, 1.0 for borders
- **Disabled**: 0.6 for content
- **Hover**: Full opacity (1.0)

### 5. Test Both Themes

Always test your customizations in both dark and light themes to ensure readability.

### 6. Use RGBA, Not Hex

RGBA allows opacity control:

```css
/* Good - allows opacity */
background-color: rgba(43, 43, 43, 0.8);

/* Avoid - no opacity control */
background-color: #2B2B2B;
```

### 7. Layer Borders Properly

For complex borders (like overlays), use multiple frames:

```python
# Outer border frame
border_frame = QFrame()
border_frame.setObjectName("borderOverlay")

# Inner content
content_frame = QFrame()
content_frame.setObjectName("overlayBackdrop")
border_frame_layout.addWidget(content_frame)
```

### 8. Use Theme Manager for Switching

Don't manually reload QSS - use the theme manager for proper cache management:

```python
# Good
theme_manager.apply_theme("dark")

# Avoid
app.setStyleSheet(open("dark.qss").read())
```

---

## Advanced Techniques

### Gradient Backgrounds

```css
QWidget {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(43, 43, 43, 1.0),
        stop:1 rgba(26, 26, 26, 1.0)
    );
}
```

### Multiple Borders

```css
QWidget {
    border: 2px solid rgba(255, 255, 255, 1.0);
    border-bottom: 4px solid rgba(100, 200, 255, 1.0);
}
```

### Pseudo-elements

```css
/* Style scroll bar components */
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.35);
    border-radius: 4px;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}
```

### Subcontrol Positioning

```css
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: right center;
    width: 24px;
}
```

---

## Troubleshooting

### Style Not Applying

1. **Check object name**: Verify `setObjectName()` is called
2. **Force style refresh**:
   ```python
   widget.style().unpolish(widget)
   widget.style().polish(widget)
   widget.update()
   ```

### Inheritance Issues

QSS uses inheritance - more specific selectors override general ones:

```css
/* General - applied to all QWidgets */
QWidget { background: red; }

/* Specific - overrides for #myWidget */
QWidget#myWidget { background: blue; }

/* More specific - overrides for #myWidget in QMainWindow */
QMainWindow QWidget#myWidget { background: green; }
```

### Transparency Not Working

1. **Set window flags**:
   ```python
   window.setAttribute(Qt.WA_TranslucentBackground)
   window.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
   ```

2. **Ensure parent transparency**:
   ```python
   window.setStyleSheet("background: transparent;")
   ```

### Border Radius Not Clipping

Add:

```python
widget.setAttribute(Qt.WA_TranslucentBackground)
```

Or use `QGraphicsEffect`:

```python
from PySide6.QtWidgets import QGraphicsOpacityEffect
effect = QGraphicsOpacityEffect(widget)
effect.setOpacity(0.95)
widget.setGraphicsEffect(effect)
```

---

## Migration from Other Themes

### From Default Qt Theme

1. Add object names to custom components
2. Remove hard-coded colors from Python code
3. Move styling to QSS file
4. Test in both dark and light modes

### From Stylesheet Strings

Convert inline styles to QSS file:

```python
# Before
widget.setStyleSheet("""
    QWidget {
        background-color: #2B2B2B;
        border: 2px solid white;
    }
""")

# After
widget.setObjectName("myWidget")
# In QSS file:
# QWidget#myWidget {
#     background-color: rgba(43, 43, 43, 0.8);
#     border: 2px solid rgba(255, 255, 255, 1.0);
# }
```

---

This completes the theme styling guide. For overlay-specific patterns, see [OVERLAY_GUIDE.md](./OVERLAY_GUIDE.md).
