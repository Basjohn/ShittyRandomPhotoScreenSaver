# Spotify Beat Visualizer – Design & Implementation Plan

Status: DRAFT (implementation not started)

## 1. Scope & Goals

- **Widget name:** Spotify Beat Visualizer
- **Location:** Media section (same family as Spotify/Media widget)
- **Mode:** *Spotify-only* (no generic "All Sound" mode for now)
- **Purpose:** Visualize the audio output associated with Spotify as a set of animated vertical bar columns, synced to audio energy.
- **Constraints:**
  - Integrated with existing overlay widget systems: settings, DisplayWidget wiring, ResourceManager, ThreadManager, AnimationManager, shadow/fade sync.
  - No drop shadow on individual bars; the widget card itself uses the shared shadow system like other widgets.
  - No heading or text; purely a contained visualization.
  - Must fail soft: if audio capture or FFT fails, widget quietly hides or renders idle state without impacting screensaver stability.

## 2. High-Level Behaviour

- **Creation & placement**
  - Owned by `DisplayWidget` alongside the main Spotify media widget.
  - Always **horizontally aligned** to the Spotify widget width.
  - Vertically positioned **a fixed gap above the Spotify widget** (e.g. 20px logical gap) when both are visible on the same monitor.
  - If the Spotify widget is disabled for the monitor, the visualizer is treated as disabled (no separate position UI in this first version).

- **Appearance**
  - Low-profile bar strip roughly as tall as the Spotify logo frame height.
  - Background card and border: inherits **Spotify widget card settings** (background color, opacity, border color/width, margin) so the two feel like a single cohesive unit.
  - Inside the card, a configurable number of vertical bars (24–48 selectable) filling the width.
  - Each bar has configurable:
    - **Fill color** (base RGBA)
    - **Border color** and **border opacity** (thin border around each bar)
  - No text labels or headings.

- **Audio behaviour**
  - Audio loopback from the system output that carries Spotify audio.
  - Implementation target: **sounddevice** WASAPI loopback as the primary path, with room to swap to miniaudio later if required.
  - Worker thread collects blocks of audio samples, computes FFT (rFFT) and aggregates into N bar magnitudes.
  - Worker emits periodic `barsUpdated(list[float])` signal into the Qt UI thread.
  - Widget maps bar magnitudes into logical heights within its available drawing rect and animates smoothly (per-frame easing / lerp).

- **Animation behaviour**
  - Uses a small internal timer / animation curve (via `QVariantAnimation` or per-frame lerp) to smooth bar height transitions between FFT updates.
  - Integrated with **overlay fade synchronisation**:
    - Uses `DisplayWidget.request_overlay_fade_sync("spotify_visualizer", starter)` to start its initial card fade-in.
    - Drop shadow attached via `ShadowFadeProfile` / `apply_widget_shadow` like other widgets.

## 3. Architecture & Modules

### 3.1 New widget class

File: `widgets/spotify_visualizer_widget.py`

- **Base class:** `QWidget` (custom `paintEvent` for bars, no text).
- **Key fields:**
  - Layout/appearance
    - `_margin: int`
    - `_show_background: bool`
    - `_bg_opacity: float`
    - `_bg_color: QColor`
    - `_bg_border_width: int`
    - `_bg_border_color: QColor`
    - `_bar_count: int` (24–48; default 32)
    - `_bar_fill_color: QColor`
    - `_bar_border_color: QColor`
    - `_bar_border_opacity: float`
  - Behaviour
    - `_enabled: bool`
    - `_thread_manager: Optional[ThreadManager]`
    - `_audio_worker: Optional[SpotifyVisualizerAudioWorker]`
    - `_shadow_config`: shared widget shadow settings
    - `_current_bar_values: list[float]` (0–1 normalized per bar)
    - `_target_bar_values: list[float]`
    - `_smoothing_anim: Optional[QVariantAnimation]` or a simple QTimer-based lerp
  - Placement
    - `_anchor_rect: Optional[QRect]` – latest Spotify widget geometry to follow.

- **Public methods:**
  - `set_thread_manager(thread_manager)` – for background audio worker.
  - `set_shadow_config(config)` – for shadow fade integration.
  - `set_card_style_from_media(media_widget)` – copies background/border/text opacity settings from `MediaWidget`.
  - `set_bar_count(count: int)` – clamps and resets internal arrays.
  - `set_bar_fill_color(color: QColor)`.
  - `set_bar_border(color: QColor, opacity: float)`.
  - `set_anchor_rect(rect: QRect)` – used by `DisplayWidget` to keep the visualizer 20px above Spotify while matching width.
  - `start()` / `stop()` / `cleanup()` – lifecycle similar to other widgets.

- **Signals:**
  - None externally – widget only consumes audio worker signal.

### 3.2 Audio worker

File: `widgets/spotify_visualizer_audio.py` (or nested inside widget module initially if very small).

- **Class:** `SpotifyVisualizerAudioWorker(QObject)`
- **Responsibilities:**
  - Configure and manage a sounddevice `InputStream` using WASAPI loopback on the primary output.
  - Receive blocks (e.g. 1024 samples at 48 kHz, stereo) in a background thread.
  - Compute magnitude spectrum using `numpy.rfft`.
  - Aggregate into N bars (matching widget `_bar_count`) by slicing/averaging frequency bins per band.
  - Normalise and apply basic dynamic range compression (log or power curve) to keep bar motion readable.
  - Emit `barsUpdated(list[float])` with values in [0, 1].

- **Key fields:**
  - `_running: bool`
  - `_bar_count: int`
  - `_stream: Optional[sd.InputStream]`
  - `_device_index: Optional[int]` – chosen WASAPI loopback device.

- **Signals:**
  - `bars_updated = Signal(list)` – to be connected to the widget’s update slot on UI thread.

- **Thread & safety:**
  - Use `ThreadManager` to start the worker and manage lifetime.
  - `InputStream` callback runs on sounddevice’s own thread; it should push results to a thread-safe queue or accumulate and downsample to ~30–60 updates/sec.
  - Worker uses `emit` from its QObject to cross to the UI thread.

### 3.3 Display & settings integration

**Settings schema (first pass, Spotify-only):**

- Under `widgets.media` (or a new `widgets.spotify_visualizer` block, but for now keep under media for cohesion):
  - `widgets.spotify_visualizer.enabled: bool`
  - `widgets.spotify_visualizer.bar_count: int` (24–48)
  - `widgets.spotify_visualizer.bar_fill_color: str` (e.g. `"#00FF00"` or RGBA tuple)
  - `widgets.spotify_visualizer.bar_border_color: str`
  - `widgets.spotify_visualizer.bar_border_opacity: float`

Card visual settings (bg color, opacity, border, margin) will be **inherited** at runtime from the main Spotify media widget rather than stored separately, to keep them visually locked.

**WidgetsTab integration:**

- In `ui/tabs/widgets_tab.py`, under Media section:
  - Add a new `QGroupBox` or subsection **"Spotify Beat Visualizer"**.
  - Controls:
    - Checkbox: `Enabled`
    - Spin box: `Bar count` (24–48)
    - Color pickers: `Bar fill color`, `Bar border color`
    - Slider/spin: `Bar border opacity`
  - No position controls; position is derived from Spotify widget.

**DisplayWidget wiring:**

- In `rendering/display_widget.py`:
  - Extend `_setup_widgets()`:
    - If Spotify media widget is created for this monitor and `widgets.spotify_visualizer.enabled` is true, create `SpotifyVisualizerWidget` instance.
    - Inject `ThreadManager` and shadow config.
    - Call `set_card_style_from_media(media_widget)`.
    - After media widget has a settled geometry (post fade-in / sizeHint), compute an anchor rect for the visualizer:
      - x: same as media widget left.
      - width: same as media widget width.
      - y: `media_rect.top() - gap - visualizer_height` (with clamping to screen bounds).
    - Hook into existing overlay fade sync using `request_overlay_fade_sync` with an appropriate key.
  - Ensure `cleanup()` and `hide_all()`/`clear_all()` stop and delete the visualizer.

- In `transitions/overlay_manager.raise_overlay()`:
  - Add the visualizer to the list of widgets that are re-raised after transitions.

## 4. Rendering Details

- **Canvas:** `QWidget` subclass with custom `paintEvent` using `QPainter`.
- **Card drawing:**
  - If `_show_background` (inherited from media card):
    - Draw rounded rect background with `_bg_color`.
    - Draw border using `_bg_border_color` and `_bg_border_width`.
  - Else, transparent background.

- **Bar layout:**
  - Compute inner rect = widget rect minus `_margin` and a small padding from card border.
  - Divide inner rect width into `_bar_count` columns with small gutter between bars.
  - For each bar index i:
    - Height fraction = `_current_bar_values[i]` in [0, 1].
    - Map to logical bar height = `inner_height * height_fraction`.
    - Align base of bars to the bottom of the inner rect.
  - Bars drawn as filled rounded rects or plain rects:
    - Fill: `_bar_fill_color`.
    - Border: `_bar_border_color` with alpha derived from `_bar_border_opacity`.

- **Smoothing:**
  - When a new `bars_updated` list arrives:
    - Set `_target_bar_values`.
    - Use a short `QVariantAnimation` or single-step lerp per frame:
      - e.g. `current = current + (target - current) * 0.35` at 60 Hz via QTimer.
    - Trigger `update()` in the widget to repaint.

## 5. Audio Capture Strategy

### 5.1 Backend choice

- Primary: **sounddevice**
  - Pros: simple Python API, supports WASAPI loopback, already common in Python ecosystems.
  - Cons: needs careful device selection for WASAPI loopback.

- Alternatives (for later):
  - **miniaudio**: very fast and low-level, good fallback if sounddevice is problematic.
  - **pyaudiowpatch**: has dedicated WASAPI loopback; keep as a future option, not first choice.

### 5.2 Device selection

- At startup of the audio worker:
  - Query sounddevice devices.
  - Prefer WASAPI loopback device associated with the default output (Speakers/Headphones), documented in comments.
  - If no loopback device is found, log and disable the visualizer (widget hides gracefully).

### 5.3 FFT & band mapping

- Use mono mix from left/right channels (average or take left only).
- Compute `fft = abs(rfft(windowed_samples))`.
- Ignore DC and very low bins below a configurable low cutoff (e.g. 60 Hz).
- Map remaining frequencies to `_bar_count` bands:
  - Either linear frequency bins or pseudo-log spacing for better perceptual spread.
  - For each band: average magnitude over its assigned bins.
- Normalise by a rolling maximum or RMS to keep bars moving even at moderate volumes.

## 6. Future Enhancements (Feasibility Hooks)

- **Two-tone mode:**
  - Allow separate colors for low/mid/high bands.
  - Implementation hook: keep `bar_fill_color` as either a single QColor or a small list mapped by band index.

- **Rainbow mode:**
  - Slow hue shift left-to-right or over time.
  - Implementation hook: maintain a `base_hue` float and compute each bar’s color via HSV to QColor conversion on each paint.

- **Beat-driven effects:**
  - Global pulse when peak energy crosses a threshold.
  - Slight card scale/opacity modulation on strong beats.

The initial implementation will include fields and structure that make these modes easy to add later without refactoring the core drawing or audio pipeline.

## 7. Live Checklist

- [ ] Add settings schema for `widgets.spotify_visualizer` in `SettingsManager._set_defaults()` and document in `Docs/SPEC.md`.
- [ ] Extend `ui/tabs/widgets_tab.py` with a Media → Spotify Beat Visualizer section (enabled, bar count, colors, opacity).
- [ ] Implement `SpotifyVisualizerAudioWorker` using sounddevice WASAPI loopback and FFT → bar aggregation.
- [ ] Implement `SpotifyVisualizerWidget` (card background, bar drawing, smoothing, no text; inherits card style from `MediaWidget`).
- [ ] Wire widget into `DisplayWidget._setup_widgets()` with monitor selection, Spotify anchor placement, thread manager, shadow config, and fade sync.
- [ ] Integrate with `overlay_manager.raise_overlay()` so the visualizer stays above transitions.
- [ ] Ensure `cleanup()` and display manager teardown stop the audio worker and timers safely.
- [ ] Add at least one test or manual-test entry in `Docs/TestSuite.md` for visualizer behaviour (Spotify playing vs idle, enabling/disabling widget, basic performance sanity).
- [ ] Verify behaviour on multi-monitor setups with Spotify on/off and different widget monitor settings.
