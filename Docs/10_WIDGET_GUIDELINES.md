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

## 6. Z‑Order, GL Compositor & Fade/Shadow Behaviour

This section is the **canonical recipe** for making sure overlay widgets never
vanish or flicker under GL transitions (including the shared `GLCompositorWidget`).

If a widget (Spotify visualizer, media, weather, Reddit, clocks) ever
disappears during a transition, debug **only these integration points** first.

### 6.1 Where widgets live

- All overlay widgets are **direct children of `DisplayWidget`**.
- Widgets **never** create their own `QOpenGLWidget` overlays or top‑level
  windows.
- GL transitions and the compositor render **behind** widgets; Z‑order is
  maintained explicitly by `DisplayWidget` and `overlay_manager`.

### 6.2 Creation & basic wiring (`DisplayWidget._setup_widgets`)

For every overlay widget (clock / weather / media / Spotify visualizer /
Reddit / future widgets), `DisplayWidget._setup_widgets` must:

1. **Gate on settings**
   - Check `widgets.<name>.enabled` and per‑monitor selection before creating.

2. **Create and configure**
   - Instantiate the widget as a child of `DisplayWidget`.
   - Apply font, margin, background and colour settings via setters
     (`set_font_family`, `set_font_size`, `set_margin`, `set_show_background`,
     `set_background_color`, `set_background_opacity`, `set_background_border`).
   - Pass the global shadow config:
     - Prefer `widget.set_shadow_config(shadows_config)`.
     - Fallback: `apply_widget_shadow(widget, shadows_config, has_background_frame=...)`.

3. **Start + initial raise**
   - Call `widget.raise_()` **immediately** after configuration.
   - Call `widget.start()` to begin timers / polling.

The Spotify media card + Spotify Beat Visualizer wiring in
`rendering/display_widget.py::_setup_widgets` is the reference example.

### 6.3 Coordinated fade + shadow (`request_overlay_fade_sync` + `ShadowFadeProfile`)

All widgets that fade in (Weather, Media, Reddit, clocks, Spotify visualizer)
follow the same pattern:

1. In the widget’s `start()` method, register a starter callback with the
   parent `DisplayWidget`:

   - `parent.request_overlay_fade_sync("media", starter)`
   - `parent.request_overlay_fade_sync("weather", starter)`
   - `parent.request_overlay_fade_sync("reddit", starter)`
   - `parent.request_overlay_fade_sync("spotify_visualizer", starter)`
   - `parent.request_overlay_fade_sync("clock"/"clock2"/"clock3", starter)`

2. In `starter`, call the widget’s fade helper, which must delegate to the
   shared `ShadowFadeProfile`:

   - Media: `MediaWidget._start_widget_fade_in()` →
     `ShadowFadeProfile.start_fade_in(self, self._shadow_config, has_background_frame=self._show_background)`.
   - Weather: `WeatherWidget._fade_in()` → `ShadowFadeProfile.start_fade_in(...)`.
   - Reddit: `RedditWidget._start_widget_fade_in()` → `ShadowFadeProfile.start_fade_in(...)`.
   - Clocks: `ClockWidget._start_widget_fade_in()` → `ShadowFadeProfile.start_fade_in(...)`.
   - Spotify Visualizer: `SpotifyVisualizerWidget._start_widget_fade_in()` →
     `ShadowFadeProfile.start_fade_in(...)`.

3. `ShadowFadeProfile.start_fade_in` performs a **two‑stage animation**:
   - Card opacity fade 0.0 → 1.0 using a temporary `QGraphicsOpacityEffect`.
   - Shadow fade 0 → target alpha using a shared `QGraphicsDropShadowEffect`
     configured from `widgets.shadows.*`.

This guarantees that all widgets on a display fade in together and receive
their drop shadows with identical timing.

### 6.4 Overlay manager (`transitions.overlay_manager.raise_overlay`)

For legacy GL overlays (Crossfade/Slide/Wipe/Diffuse/BlockFlip/Blinds),
`transitions.overlay_manager.raise_overlay(display, overlay)` is responsible
for:

- Creating or reusing the GL overlay widget via `get_or_create_overlay`.
- Setting its geometry via `set_overlay_geometry(display, overlay)`.
- Calling `overlay.raise_()` to move the GL overlay above the base image.
- **Re‑raising overlay widgets afterwards** so they remain on top of the GL
  overlay.

Any changes to overlay types or GL transition wiring must update
`overlay_manager` so that, after an overlay is raised, the widgets are raised
again in a deterministic order.

### 6.5 Canonical Z‑order fix (`DisplayWidget._ensure_overlay_stack`)

The final piece that prevents widgets from vanishing under the **shared GL
compositor** is `DisplayWidget._ensure_overlay_stack(stage)`. This helper is
called at key moments:

- On screen change / resize.
- At transition start (`stage="transition_start"`).
- After display updates and transition finish.

It must do **two things**:

1. **Maintain GL/SW overlay geometry and stacking**

   ```python
   for attr_name in GL_OVERLAY_KEYS + SW_OVERLAY_KEYS:
       overlay = getattr(self, attr_name, None)
       if not overlay:
           continue
       set_overlay_geometry(self, overlay)
       if overlay.isVisible():
           schedule_raise_when_ready(self, overlay, stage=f"{stage}_{attr_name}")
       else:
           raise_overlay(self, overlay)
   ```

2. **Re‑raise real overlay widgets over the compositor**

   After the loop above, `_ensure_overlay_stack` must explicitly re‑raise the
   card widgets so they sit above both the GL compositor and any legacy
   overlays for the entire duration of a transition:

   ```python
   for attr_name in (
       "clock_widget", "clock2_widget", "clock3_widget",
       "weather_widget", "media_widget",
       "spotify_visualizer_widget", "reddit_widget",
   ):
       w = getattr(self, attr_name, None)
       if w is not None and w.isVisible():
           w.raise_()
   ```

This pattern – especially the explicit re‑raise of `media_widget` and
`spotify_visualizer_widget` – is the **exact fix** for the historical bug
where the Spotify Beat Visualizer (and sometimes the media card) vanished or
only reappeared late in a GL transition.

Any new overlay widget must be added to this re‑raise list once it participates
in the shared overlay fade/shadow system.

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

---

## 9. Spotify Beat Visualizer specifics (GPU bar overlay & ghosting)

The Spotify Beat Visualizer follows the same card/overlay patterns as the
media widget but adds a dedicated GPU bar overlay and a configurable ghosting
trail:

- **Split responsibilities**  
  The QWidget (`SpotifyVisualizerWidget`) owns the Spotify-style card, fade,
  drop shadow and bar smoothing. A dedicated `SpotifyBarsGLOverlay`
  `QOpenGLWidget` child of `DisplayWidget` renders the actual bar field on the
  GPU when the OpenGL backend is active, with a QWidget/QPainter bar path used
  only as a fallback when `software_visualizer_enabled` is true or GL is
  unavailable.

- **1-segment idle floor**  
  The GPU overlay maintains a per-bar peak envelope with a guaranteed
  1-segment floor so the visualiser never collapses to a blank card. Even when
  playback is paused or starting, the bars show at least a single illuminated
  segment per column, matching the intended "always-alive" visual language.

- **Ghosting trail behaviour**  
  Above each live bar, the overlay can draw a short ghost trail using the bar
  border colour. This trail is driven by the decaying peak envelope (not by
  residual FBO contents) and fades out with a **vertical alpha falloff** so
  segments closest to the live bar are brightest and the highest segments fade
  fastest. Ghosting is controlled by `widgets.spotify_visualizer.*` settings:
  - `ghosting_enabled`: global on/off for the trail.
  - `ghost_alpha`: overall opacity multiplier for ghost segments (0.0–1.0).
  - `ghost_decay`: decay rate for the peak envelope; larger values shorten the
    visible trail while smaller values stretch it out.

- **UI wiring and defaults**  
  The Widgets tab exposes a dedicated Spotify visualiser group:
  - A checkbox to enable/disable the visualiser and a **FORCE Software
    Visualizer** checkbox on the same row for the QWidget-only path.
  - A checkbox to enable/disable ghosting.
  - A **Ghost Opacity** slider mapped to `ghost_alpha` (0–100%).
  - A **Ghost Decay Speed** slider mapped to `ghost_decay` (~0.10x–1.00x).
  Defaults are defined centrally in `SettingsManager._set_defaults()` and
  mirrored in `Docs/SPEC.md`; UI code must treat those as the single source of
  truth.

These behaviours are canonical for any future beat-style visualisers: keep the
card/overlay split, guarantee a minimal idle floor, and route any ghosting or
trailing effects through explicit, documented settings rather than implicit
framebuffer residue.
