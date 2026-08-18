# Compositor Architecture

Last updated: 2026-08-18

Current accelerated presentation architecture for `main`.

## 1. Non-Negotiable Shape

Each physical display owns **one** accelerated Qt presentation surface:

```text
DisplayWidget
   └── GLCompositorWidget
          └── ExternalOpenGLRhiWidget / QRhiWidget.Api.OpenGL
```

The visualizer is not a second surface.

Hardware acceleration is required for the modern compositor/visualizer runtime. Do not add a
QOpenGLWidget/QRhiWidget/CPU visualizer compatibility surface when acceleration is disabled.

## 2. QRhi / Raw OpenGL Boundary

`rendering/gl_rhi_surface.py` owns the shared QRhi/OpenGL substrate.

- QRhi backend is OpenGL.
- Qt owns the QRhi and its `QOpenGLContext`.
- SRPSS borrows that context.
- existing PyOpenGL draw code executes inside QRhi ExternalContent / beginExternal-endExternal
  boundaries.
- SRPSS does not own `swapBuffers()`.
- top-level no-vsync policy remains intentional.

`releaseResources()` handles QRhi-generation/resource retirement. Resize alone is not a resource
lifetime reset.

## 3. Scene Ownership

The compositor owns display-local draw order and presentation:

1. retained base image / active transition;
2. compositor-owned visual layers such as the visualizer card;
3. visualizer shader layer;
4. any later explicitly compositor-owned GL layers.

Ordinary QWidget overlays remain separate UI where appropriate.

## 4. Visualizer Single-Surface Integration

`widgets/spotify_bars_gl_overlay.py::SpotifyBarsGLOverlay` is retained for:

- logical visualizer render-state integration;
- mode-owned state/GL resource owner methods;
- geometry anchor used by runtime/CUSTOM;
- shader uniform/render helpers.

It is a plain QWidget that is never a presented surface and paints nothing.

`rendering/gl_compositor_pkg/visualizer_layer.py::CompositorVisualizerLayer` consumes the current
visualizer state and renders it inside the compositor framebuffer.

### Card

The authored card may still be prepared with QPainter/QPixmap at state/geometry/style invalidation
boundaries. Steady presentation uses a compositor-owned GL texture and textured quad. Upload occurs
only when canonical card-pixel cache identity changes.

Card texture and visualizer shader use the same authoritative presentation geometry:

- logical rect;
- compositor/display DPR;
- framebuffer origin;
- framebuffer size;
- viewport/scissor/mask alignment.

## 5. Presentation Liveness

One display presentation strategy owns physical frame opportunities.

Its active reasons are additive. A transition ending cannot stop presentation while the
visualizer remains active; visualizer hide cannot stop an active transition.

When no animated reason remains, return to existing idle retained behaviour.

There is no second visualizer timer.

## 6. Admission

Cross-thread callback coalescing may keep one queued GUI callback outstanding. That guard ends when
the GUI callback calls `QWidget.update()`.

Paint completion is not an admission token. Repeated `update()` requests may be coalesced by Qt.

No:

- pending-until-paint;
- paint acknowledgement;
- render self-requeue;
- repaint rescue;
- producer/display divisor gate.

## 7. Visualizer Readiness / Fade

The single-surface visualizer is prepared while visually at fade zero. Current-generation
renderer/card/audio/fresh-frame readiness must exist before visible fade begins.

The compositor owns card+visualizer pixels for the entire fade. One scalar/easing profile applies
to both. A hidden QWidget opacity effect cannot hand presentation ownership to the compositor
halfway through the animation.

## 8. GL Resource Ownership

- Qt-owned context is borrowed, never destroyed/doneCurrent by SRPSS;
- one numeric handle has one deletion owner;
- visualizer programs/VBO/VAO/mask/card texture are associated with compositor QRhi generation;
- hidden/no-current-published visualizer state does not erase destruction authority;
- explicit runtime cleanup and QRhi `releaseResources()` converge on one deletion implementation;
- failed deletion retains ownership and fails closed;
- ResourceManager accounting is released only after deletion succeeds.

## 9. QPainter Fallback

The main compositor may use its explicit base-image QPainter fallback when accelerated retained-base
shader drawing is unavailable. Unexpected fallback after an established healthy shader path is
state-loud and bounded.

This fallback does not generalize to the visualizer. Visualizer shader failure clears/omits that
layer and logs a bounded loud error.

## 10. Transition Model

Transition progress is display-local monotonic elapsed time. Completion is exactly once:
destination becomes base, source/temp ownership releases and transition becomes inactive.

Transition shader cost is not automatically blamed for a delivery gap; current P05 evidence owns
causal claims.

## 11. CUSTOM / Edit Boundary

The visualizer's pixels now belong to the compositor, while its logical geometry/editor anchor may
remain QWidget-based.

Edit preview must capture the compositor-owned visualizer region rather than an obsolete visualizer
framebuffer. Drag/resize may scale/move a preview; it does not require live GPU resize on every
mouse event. Save/rebuild publishes the new authoritative rect to the correct display compositor;
Cancel restores the previous state once.

## 12. P5 Boundary

Presentation architecture does not replace monitor topology lifecycle work. P5 still owns one
settled topology authority, frozen transaction snapshot, retire/rebuild/reveal, sticky configured
visualizer monitor semantics and physical off/wake acceptance.
