# R-09 — 2026-03-05 — Settings Spinbox/LineEdit Fill Regression (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- Every `QSpinBox` and `QLineEdit` inside the settings dialog rendered with the container gray instead of the intended `#282828` fill.
- `SPINBOX_STYLE` QSS was attached to `WidgetsTab`, yet the widgets never showed the correct background.

**Root Cause**
CSS specificity conflict. Every tab's `QScrollArea` had this inline rule (also centralized in `SCROLL_AREA_STYLE`):
```css
QScrollArea QWidget { background: transparent; }
```
This descendant selector has **specificity 002** (two type selectors), which beats the `SPINBOX_STYLE` rules like `QSpinBox { background-color: #282828; }` at **specificity 001**. Because `QSpinBox` IS-A `QWidget`, the transparent background was always winning. The same rule also existed in `dark.qss` line 380 for `#subsettingsDialog`.

**Failed attempts (all reverted)**
1. Global stylesheet append in `settings_theme.load_theme` — no effect (specificity still lost).
2. Palette forcing in `apply_shadows_to_inputs` — bypassed by QSS.
3. Stack stylesheet sync + STYLE_PROBE hooks — confirmed styles existed but didn't help.
4. Dialog-level palette override — palette changed but QSS still won.

**Fix**
- Removed `QScrollArea QWidget { background: transparent; }` from `SCROLL_AREA_STYLE` in `shared_styles.py`.
- Replaced all inline scroll area stylesheets in `widgets_tab.py`, `transitions_tab.py`, `sources_tab.py`, `display_tab.py` with centralized `SCROLL_AREA_STYLE` import.
- `accessibility_tab.py` already used the import — no change needed.
- Fixed `dark.qss` `#subsettingsDialog QScrollArea QWidget` → `#subsettingsDialog QScrollArea > QWidget > QWidget`.
- The remaining rules (`QScrollArea { ... }` and `QScrollArea > QWidget > QWidget { ... }`) use direct-child combinators, so they only target the viewport and content widget — not all descendants.

**Cleanup**
- Removed all STYLE_PROBE diagnostic code from `settings_dialog.py` (`_log_stylesheet`, `_install_stylesheet_hooks`, `_log_tab_styles`, `_sync_stack_stylesheet`, `_log_palette_snapshot`, `_style_probe_enabled`).
- Removed `_SpinboxProbeFilter`, `_style_probe_enabled()`, `_format_color_hex()`, `_log_input_styles()`, `_install_spinbox_probes()` from `widgets_tab.py`.
- Removed unused `os`, `QPalette` imports from `settings_dialog.py`.

**Status**
- ✅ **Resolved** — Visually confirmed `#282828` fill on all spinboxes, entry boxes, and line edits.

## Record Provenance

This standalone file preserves the complete former inline `R-09` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
