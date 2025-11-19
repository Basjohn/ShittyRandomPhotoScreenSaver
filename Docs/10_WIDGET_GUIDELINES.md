# Overlay Widget Design & Implementation Guidelines

This document captures the **canonical design and implementation pattern** for
overlay widgets (clock, weather, Spotify, and future widgets like Reddit or
MusicBee). It is grounded in the final Spotify widget implementation and should
be treated as the primary reference when adding or refactoring widgets.

> **Scope**  
> These guidelines cover: layout, typography, headers/logo alignment,
> artwork placement, interaction gating, Z‑order, and settings
> persistence for overlay widgets.

---

## 1. Core Principles

- **Single source of truth for settings**  
  All widgets read/write from the nested `widgets` map managed by
  `SettingsManager` and documented in `Docs/SPEC.md`.

- **Non-destructive, non-blocking**  
  Widgets must never block the UI thread or cause the screensaver to exit
  unexpectedly. Failures are logged and treated as "no widget".

- **DPI-aware layout & rendering**  
  All sizing/padding decisions are in logical pixels and rely on Qt’s
  device-pixel‑ratio scaling. Any custom painting (logos, artwork, borders)
  must respect `devicePixelRatioF()`.

- **Consistent card visual language**  
  Widgets share a common “card” style:
  - Dark semi‑opaque background
  - Rounded border frame
  - High-contrast text with subtle opacity
  - Generous padding and breathing room around content

- **Interaction opt‑in only**  
  Widgets are display‑only by default and become interactive only under
  explicit user intent (Ctrl‑held or hard‑exit mode), mediated centrally by
  `DisplayWidget`.

---

## 2. Canonical Widget Structure (Spotify-based)

The Spotify widget demonstrates the preferred structure for any card‑style
widget:

1. **Outer Card (QLabel/QWidget)**
   - Subclass `QLabel` or `QWidget` (Spotify uses a `QLabel` subclass
     `MediaWidget`).
   - Store configuration (font family/size, colors, margins, flags) on the
     instance; do *not* derive from settings directly in `paintEvent`.
   - Use `setContentsMargins()` and `setMinimumSize()` to enforce a stable
     footprint so the widget does not jump when content changes.

2. **Header Row**
   - Contains a **brand logo glyph** (painted via `QPainter`) and a
     **wordmark label** rendered via rich text.
   - Both elements are sized and aligned via `QFontMetrics` so the header
     reads visually as `[] -` (glyph, then text on the same horizontal line).

3. **Body / Metadata**
   - Stack one or more text lines with distinct typography:
     - Primary line (e.g. song title): larger and bolder.
     - Secondary line (e.g. artist): slightly smaller with subtle opacity.
   - Use HTML `<div>` fragments for per‑line font size/weight when
     convenient, but keep layout simple and predictable.

4. **Right‑hand Artwork (for media widgets)**
   - Optional album art is rendered on the **right side** of the card inside a
     clipped border frame.
   - The artwork border is slightly thicker than the card border so artwork is
     the primary visual focal point.

5. **Transport / Action Row (optional)**
   - A short row of glyphs (e.g. `←  ▶  →`) rendered as inline spans.
   - Styled to be visually subtle (slightly smaller than metadata text) while
     remaining readable.

---

## 3. Header & Logo Alignment Rules

The Spotify widget defines the canonical header behaviour:

- **Metrics cached from text**  
  In `_update_display`, compute and store:
  - `self._header_font_pt`: header font size in pt.
  - `self._header_logo_size`: logo target size (≈ 1.3× header font).
  - `self._header_logo_margin`: left margin for the wordmark so the text
    starts just to the right of the glyph.

- **Wordmark (rich text)**  
  The header HTML uses:
  - `font-size:{header_font_pt}pt`
  - `font-weight:750` (slightly heavier than normal bold)
  - `letter-spacing:1px`
  - `margin-left:{self._header_logo_margin}px`
  - `color:rgba(255,255,255,255)` (fully opaque white; not affected by
    background opacity)

- **Logo painting (QPainter)**  
  In `_paint_header_logo`:
  - Scale the logo pixmap using `devicePixelRatioF()` and call
    `scaled.setDevicePixelRatio(dpr)` so it stays crisp on high‑DPI screens.
  - Use `QFontMetrics` on `self._header_font_pt` to compute the first line’s
    height and vertical centre; derive the logo `y` from this centre so the
    glyph and wordmark sit on the same visual baseline.
  - Apply **small logical‑pixel nudges only** (e.g. ±2–4 px) to fine‑tune the
    perceived alignment—it should reliably look like `[] -` across DPI.

- **Header sub‑frame (optional)**  
  When `show_header_frame` is enabled:
  - Compute frame width/height using the same `QFontMetrics` and cached logo
    size so the frame comfortably wraps the glyph + wordmark.
  - Draw a rounded rect **border only** using `painter.setBrush(Qt.NoBrush)`
    and the widget’s border colour/opacity.
  - Do **not** fill the header frame; the card background already provides the
    tone, and a second fill would darken the SPOTIFY text.
  - Small offsets of the frame rect (few pixels left/down) can be used to
    visually centre the glyph + wordmark within the frame without moving the
    header content itself.

Any future widget with a brand/logo header (e.g. Reddit, MusicBee) should
follow this pattern, substituting its own logo asset and wordmark.

---

## 4. Artwork Placement & Border

For media‑style widgets that show artwork:

- **Placement**
  - Artwork is drawn on the **right side** of the card, inside the widget’s
    contents margins.
  - The left side is reserved for header + text.

- **Sizing**
  - Use a logical `artwork_size` setting in `widgets.<name>.artwork_size`.
  - Clamp final size using the widget height (e.g. `height - 60` for
    top/bottom padding) to avoid clipping on smaller cards.
  - Scale a cached pixmap in device pixels (`size * dpr`) and set its DPR.

- **Border & Clipping**
  - Compute a logical `border_rect` that leaves comfortable padding between
    artwork and card edges.
  - Use a `QPainterPath` to clip the artwork to this rect:
    - Rounded rect when `rounded_artwork_border` is true.
    - Plain rect otherwise.
  - Draw the border **after** the artwork using the widget border colour, with
    width slightly larger than the card (
    e.g. `bg_border_width + 2`) so artwork stands out.

- **Transitions**
  - Apply a short `QVariantAnimation` to the artwork’s opacity for fade‑in on
    first load or track change, without affecting the text.

---

## 5. Interaction & Input Gating

Interaction is centralized in `DisplayWidget.mousePressEvent` and guarded by
settings + Ctrl state:

- **Default: non‑interactive**  
  Widgets set `WA_TransparentForMouseEvents` so they are ignored by Qt’s
  hit‑testing. All clicks normally exit the screensaver.

- **Hard‑exit / Ctrl‑held interaction mode**
  - When `input.hard_exit` is enabled **or** Ctrl is held, `DisplayWidget`:
    - Suppresses “click to exit”.
    - Routes clicks inside widget geometries to dedicated handlers.
  - For the Spotify widget:
    - Left‑click in the **left third** of the widget → `previous_track()`.
    - Left‑click in the **middle third** → `play_pause()`.
    - Left‑click in the **right third** → `next_track()`.
  - This ensures clicking the left/right arrows or centre play/pause glyph
    does what the icon suggests, while the exact pixel hit‑test remains
    layout‑agnostic.

- **Targeting Spotify only**  
  The shared `WindowsGlobalMediaController`:
  - Uses `_select_spotify_session()` for **both reads and control actions**.
  - Other media players (VLC, browsers, etc.) are treated as "no media" for
    this widget; they will not receive play/pause/next/previous commands.

Any future media widget must either:
- Reuse this controller/selection logic (for Spotify), or
- Provide its own controller that explicitly targets the right player/app.

---

## 6. Z‑Order & Overlay Behaviour

To ensure widgets remain visible over transitions and compositors:

- `transitions.overlay_manager.raise_overlay()` must **always** re‑raise all
  overlay widgets (clock(s), weather, Spotify, future widgets) after creating
  or raising transition overlays.

- `DisplayWidget` must:
  - Call `raise_()` on each widget immediately after creation.
  - Re‑raise the widgets after transitions and GL compositor operations.

- Widgets should never create their own top‑level windows or overlays; they
  live entirely inside `DisplayWidget`.

---

## 7. Settings & Persistence Checklist

When adding a new widget (or extending an existing one):

1. **Settings schema**
   - Add a new entry under `widgets` in `SettingsManager._set_defaults()` and
     update the schema in `Docs/SPEC.md`.
   - Follow the existing media block as a template:
     - `enabled`, `monitor`, `position`, `font_family`, `font_size`, `margin`
     - `show_background`, `bg_opacity`, `bg_color`, `border_color`,
       `border_opacity`
     - Widget‑specific keys (e.g. `artwork_size`, `show_controls`,
       `show_header_frame`, `rounded_artwork_border`).

2. **WidgetsTab integration**
   - Introduce a dedicated `QGroupBox` under the appropriate subtab (e.g.
     Clocks / Weather / Media) with an **accurate name** ("Spotify Widget",
     not "Media Widget").
   - Use the `_loading` flag and `blockSignals(True/False)` around `_load_settings`
     to avoid writing partial defaults back to QSettings during UI
     construction.
   - Read and write only the nested `widgets` map; do not introduce new flat
     keys.

3. **DisplayWidget wiring**
   - In `_setup_widgets()`, gate widget creation on:
     - `widgets.<name>.enabled` and
     - per‑monitor selection (`'ALL'` or `screen_index + 1`).
   - Apply font, margin, background and colour settings via explicit setter
     methods on the widget.
   - If the widget has optional features (artwork, controls, header frame),
     expose `set_*` methods and plumb settings through `DisplayWidget`.

4. **Cleanup & lifecycle**
   - Ensure the widget exposes a `cleanup()` method that stops timers and
     hides the widget.
   - `DisplayWidget.cleanup()` and the shared `ResourceManager` must be able
     to tear down the widget deterministically.

---

## 8. Generic Overlay Widget Scaffold

When creating a new overlay widget, follow this scaffold:

1. **Class & fields**
   - Subclass `QLabel` or `QWidget` in `widgets/<name>_widget.py`.
   - Store: `_position`, `_font_family`, `_font_size`, colors, `_margin`,
     `_show_background`, `_bg_opacity`, `_bg_color`, `_bg_border_width`,
     `_bg_border_color`, and any header/artwork flags.

2. **UI setup**
   - In `_setup_ui()`:
     - Set alignment (typically top‑left for cards).
     - Mark widget transparent for mouse events.
     - Set default contents margins and minimum sizes.
     - Call a helper to apply stylesheet based on current colours/flags.
     - Optionally install a `QGraphicsOpacityEffect` for whole‑widget fade‑in.

3. **Settings setters**
   - Provide small, focused setters (`set_font_family`, `set_font_size`,
     `set_margin`, `set_show_background`, `set_background_color`, etc.) that:
     - Update the backing field.
     - Refresh position or stylesheet when the widget is already running.

4. **Painting**
   - Prefer text via QLabel (rich text) and logos/artwork via `QPainter`.
   - Use `devicePixelRatioF()` and `QFontMetrics` for all manual drawing.
   - Avoid per‑paint logging.

5. **Integration**
   - Wire into `DisplayWidget._setup_widgets()` and
     `overlay_manager.raise_overlay()` following the Spotify widget as the
     template.
   - Document any deviations in `Docs/10_WIDGET_GUIDELINES.md`.

By following this scaffold and the Spotify‑derived details above, future
widgets should drop cleanly into the existing architecture, look consistent,
behave correctly under GL/software backends, and avoid the persistence and
alignment issues already solved for the Spotify widget.
