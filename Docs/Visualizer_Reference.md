# Visualizer Reference

Last updated: 2026-08-18

Current Spotify visualizer architecture/settings reference.

## 1. Modes

Canonical ids come from `core/settings/visualizer_mode_registry.py`:

- `spectrum`
- `oscilloscope`
- `sine_wave`
- `bubble`
- `devcurve` (user-facing Spline Curve)

Retired Blob identities remain migration/history only.

## 2. Settings / Presets

- model: `core/settings/models/_spotify_visualizer.py`
- normalization: visualizer settings snapshot/contract modules
- preset resolution: `core/settings/visualizer_presets.py`
- mode identity: visualizer mode registry
- one activation consumes one resolved target payload

Curated preset selection, same-mode preset cycling and user setting mutation must remain distinct
from stale/identical settings refresh. Do not globally cache solely by mode id.

## 3. Logical Runtime

Primary owners:

- `widgets/spotify_visualizer_widget.py`
- `widgets/spotify_visualizer/activation_runtime.py`
- `widgets/spotify_visualizer/config_applier.py`
- `widgets/spotify_visualizer/technical_config.py`
- `widgets/spotify_visualizer/runtime_config.py`
- `widgets/spotify_visualizer/tick_pipeline.py`
- `widgets/spotify_visualizer/beat_engine.py`
- `widgets/spotify_visualizer/audio_worker.py`

Logical/source cadence is independent from paint.

Mode activation produces one final current generation/activation. Intermediate stale generation
state cannot reveal.

## 4. `SpotifyBarsGLOverlay` Means Logical Owner, Not Surface

`widgets/spotify_bars_gl_overlay.py` is intentionally still named `SpotifyBarsGLOverlay`, but in
current architecture it subclasses plain `QWidget`, is never shown as a presentation surface and
paints nothing.

It owns/hosts:

- logical render-state handoff and mode state used by renderer;
- visualizer GL resource creation/deletion methods on the compositor borrowed context;
- mode shader/uniform/render helpers;
- geometry anchor used by CUSTOM/runtime ownership.

Do not add surface format/update-behaviour/swap ownership back to this class.

## 5. Presentation

Actual pixels are rendered through:

`rendering/gl_compositor_pkg/visualizer_layer.py`

inside the display's sole `GLCompositorWidget` QRhi/OpenGL surface.

The visualizer card texture and mode shader share one `PresentationGeometry`/equivalent authority:
card rect, display DPR, framebuffer origin/size, viewport/scissor and mask coordinates.

Mode shaders that use framebuffer-space `gl_FragCoord` must explicitly convert to card-local
coordinates under the compositor viewport.

## 6. Card Visual

The authored QWidget/QPainter card appearance may be rasterized/cached on GUI at a known
size/DPR/style revision. The compositor uploads that source to a GL texture on revision change and
reuses the texture for steady presentation.

Do not create a QPainter/QOpenGLPaintDevice bridge every visualizer frame merely to draw an
unchanged card.

## 7. Physical Presentation

The display compositor's one presentation strategy owns physical refresh opportunities while the
visualizer is active. The visualizer logical tick remains separate.

A 60-Hz display may present the freshest of more-frequent logical updates. A high-refresh display
must not be artificially capped to 60 Hz.

No paint acknowledgement, pending-until-paint gate or separate visualizer repaint loop.

## 8. Analysis Freshness

Asynchronous analysis is latest-freshness oriented, not backlog oriented.

The bounded target shape is one in-flight analysis plus at most one newest pending source frame.
Intermediate pending frames may be replaced before compute; valid completed DSP state is committed
before scheduling the newest pending frame. Stale activation/generation work cannot publish.

Source/analysis age and compositor state-to-paint are measured separately.

## 9. Startup / Mode Switch / Playback

- GL/card resources are prepared at fade zero;
- all supported runtime programs required for switching are ready before reveal;
- audio capture STARTING is not immediately treated as stale/unhealthy;
- mode switches apply one target transaction/final generation;
- fresh-frame gating uses that final generation only;
- identical same-activation settings refresh does not replay technical config;
- ordinary play/pause does not destroy GL resources;
- warm resume reuses warm capture;
- cold restart happens once when required.

## 10. Fade

The compositor owns card + visualizer pixels throughout visible fade. One fade scalar/easing applies
to both layers. The logical QWidget may carry lifecycle state but does not own visible opacity via a
competing QGraphicsOpacityEffect presentation path.

## 11. CUSTOM Geometry / Edit

Outside CUSTOM, routing follows the normal visualizer/media contract. In CUSTOM, the visualizer may
own a configured display/rect.

Edit snapshot must come from the compositor-owned visualizer region, not
`SpotifyBarsGLOverlay.grabFramebuffer()`.

Drag/resize is preview-first. Save publishes the committed rect to the rebuilt current runtime;
Cancel restores previous authority. Intentional cross-display edit transfer is separate from P5's
sticky monitor behaviour during temporary sleep/wake absence.

## 12. Validation

Use current replay/goldens for logical fidelity, real-GL single-surface tests for viewport/card
alignment, lifecycle tests for QRhi generation/resource deletion, and installed review for fade,
reactivity, mode switch and high-refresh delivery.
