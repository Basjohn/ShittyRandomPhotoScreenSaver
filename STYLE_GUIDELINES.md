# STYLE_GUIDELINES.md

Canonical styling guidance for ShittyRandomPhotoScreenSaver. Use this as the quick reference for visual decisions across widgets, overlays, and the configuration UI. Architectural behaviour (threading, lifecycles, etc.) remains documented in `Spec.md`; this file focuses purely on look & feel.

---

## 1. Purpose & Scope

- Keep every surface visually consistent with the dark, high-contrast palette defined in `themes/dark.qss`.
- Apply the same card language across overlay widgets (clock, weather, media, Spotify visualizer, Reddit, future widgets) as detailed in `Docs/10_WIDGET_GUIDELINES.md`.
- Ensure auxiliary UI (settings dialog, popovers, tooltips) reuses the same typography, borders, and opacity rules.
- Document the intended opacity stacking so transparency never causes compositing glitches.

---

## 2. Core Palette & Typography

- **Base palette** (all opacities in logical percentages):
  - Charcoal frames/backgrounds: `rgba(43, 43, 43, 0.8)` for cards and dialog shells.
  - Text: fully white `rgba(255, 255, 255, 1.0)` or softer `rgba(255, 255, 255, 0.8)` for secondary copy.
  - Borders: solid white (`rgba(255, 255, 255, 1.0)`) for emphasis; muted `rgba(68, 68, 68, 1.0)` for structural dividers.
  - Accents: subtle greys (`rgba(58, 58, 58, 1.0)`) on hover, `rgba(30, 30, 30, 1.0)` for recessed inputs.@themes/dark.qss#1-200@themes/dark.qss#371-430
- **Typography**:
  - Default font family is **Segoe UI** for all UI and overlay widgets.
  - Title bars/headings use bold 18–24 px sizes; body copy stays at 12–14 px with weight adjustments instead of random fonts.
  - Upper-case text is reserved for buttons/labels intentionally styled that way in `dark.qss`; avoid ad-hoc capitalization.@themes/dark.qss#600-773

---

## 3. Overlay Widget Cards

Overlay widgets must mirror the Spotify-derived card spec:

- **Card shell**: dark semi-opaque background, rounded border, generous padding, and consistent margins so cards never jump when content changes.@Docs/10_WIDGET_GUIDELINES.md#30-87
- **Header row**:
  - Brand glyph + wordmark aligned on the same baseline via cached `QFontMetrics`.
  - Wordmark uses fully opaque white text; logo scaling respects device pixel ratio.
  - Optional header frames are border-only rounded rectangles using the widget’s border colour; never double-fill the header background.@Docs/10_WIDGET_GUIDELINES.md#83-133
- **Body content**:
  - Primary line bold/larger, secondary metadata slightly smaller with reduced alpha.
  - Artwork sits on the right when applicable, inside a border thicker than the card border to draw focus.@Docs/10_WIDGET_GUIDELINES.md#136-164
- **Interaction**:
  - Widgets default to non-interactive (`WA_TransparentForMouseEvents`) and rely on centralized Ctrl/Hard-exit routing to avoid inconsistent hit targets.@Docs/10_WIDGET_GUIDELINES.md#167-200

---

## 4. Settings Dialog & Desktop UI Components

- **Container frames**: `QDialog#settingsDialog`, sub-settings dialogs, and about dialogs all share the same rounded shells, white borders, and inner padding specified in `dark.qss`. Never duplicate these rules inline; use the stylesheet IDs instead.@themes/dark.qss#371-520
- **Scroll areas & lists**: Transparent backgrounds with inset scrollbars to respect rounded corners. No widget should paint opaque fills over the dark shell; verify scrollbars reuse the transparent groove/handle styling already in `dark.qss`.@themes/dark.qss#434-490
- **Controls**:
  - Combo boxes, buttons, sliders reuse the named selectors (`QSmolselect`, `QBasicBitchButton`, etc.). Matching these selectors keeps corners, weights, and hover states consistent across the app.
  - Inputs (`QLineEdit`, `QKeySequenceEdit`) always use the same 4 px radius, grey border, and blue selection color defined in the theme file.@themes/dark.qss#635-773
- **Titles & buttons**: Use the provided `#titleBar`, `#closeButton`, `#settingsTitle`, etc., selectors. Do not restyle them per-dialog; that leads to the “multiple title bars” bug history shows.

---

## 5. Transparency, Shadows & Layering

- **ShadowFadeProfile** drives every overlay fade-in to keep opacity + drop shadow timing identical. Widgets must register a starter callback with `DisplayWidget.request_overlay_fade_sync(...)` and delegate to `ShadowFadeProfile.start_fade_in(...)`.@Docs/10_WIDGET_GUIDELINES.md#197-276
- **Z-order enforcement**: After transitions, `DisplayWidget._ensure_overlay_stack` re-raises all widgets so cards stay above GL overlays. If you add a new widget (e.g., centerline placements), append it to the canonical raise list and wire it through `WidgetManager` like existing cards.@Docs/10_WIDGET_GUIDELINES.md#203-340
- **Opacity budgeting**:
  - Card backgrounds top out at ~80 % opacity to allow wallpapers to glow through gently.
  - Tooltips and popovers sit around 70 % (`rgba(32, 32, 32, 0.7)`) with crisp white borders so they float above cards without stealing focus.@themes/dark.qss#614-633
- **GL overlays**: GPU elements (Spotify bars, volume slider) fade in **after** their parent cards to avoid popping. Their fade factors are derived from card fade progress; replicate that pattern for any future GPU overlay.

---

## 6. Tooltip & Inline Help Standard

- Tooltips **must** use the global `QToolTip` definition in `dark.qss` (semi-transparent charcoal background, white text, 1 px white border, 4 px radius, 5×10 px padding). Never append widget-specific `QToolTip { ... }` snippets; they instantly diverge from our “Just Make It Work” reference tooltip in the Sources tab.@themes/dark.qss#614-627
- Inline guidance (e.g., suggestion labels) should follow the italicized helper text style already used in the Sources tab rather than inventing new colours.

---

## 7. Implementation Checklist

1. **Lean on theme IDs**: Before styling anything in code, inspect `themes/dark.qss` for an existing selector you can reuse or extend.
2. **Card changes**: Update both `Docs/10_WIDGET_GUIDELINES.md` and this style guide when altering card structure (headers, padding, etc.) so future contributors have a single reference.
3. **Tooltips**: If a new tooltip is needed, call `setToolTip()` only; no extra stylesheet overrides.
4. **Opacity changes**: When adjusting transparency, test against wallpapers with both light and dark regions to ensure legibility remains (70–80 % opacity typically balances well).
5. **Testing**: Visual QA passes should include:
   - Overlay stacking during GL transitions (look for flicker).
   - Settings dialog controls in hover/focus/disabled states.
   - Tooltip rendering over both widgets and dialogs.

---

## 8. Future Work Hooks

- **Centerline positioning**: When new “center” widgets ship, audit `WidgetManager` raise lists and shadow configs so they continue to respect these styling constraints.
- **Dead/legacy module cleanup**: When removing legacy widgets, confirm they leave no stray selectors in `dark.qss`; unused selectors should be culled to keep this guide accurate.
