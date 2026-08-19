# Compositor Architecture

Last updated: 2026-08-19

Current accelerated presentation architecture for `main`.

## 1. Non-negotiable surface shape

Each physical display owns one accelerated Qt presentation surface:

```text
DisplayWidget
   └── GLCompositorWidget
          └── OpenGL QRhi surface
```

The visualizer is not a second surface.

Do not add a visualizer QOpenGLWidget/QRhiWidget/CPU compatibility renderer.

## 2. QRhi / raw OpenGL boundary

- QRhi backend is OpenGL.
- Qt owns QRhi and its QOpenGLContext.
- SRPSS borrows that context.
- PyOpenGL draw code runs inside legal QRhi external-content boundaries.
- SRPSS does not own `swapBuffers()`.
- top-level no-vsync policy remains intentional.

Resize alone is not resource-lifetime reset.

## 3. Scene ownership

The compositor owns display-local draw order:

1. retained base image / active transition;
2. compositor-owned card/visual layers;
3. visualizer shader layer;
4. later explicitly compositor-owned GL layers.

Ordinary QWidget overlays remain separate UI where appropriate.

## 4. Visualizer integration

Current flow:

```text
BeatEngine / source analysis
        ↓
VisualizerLogicalRuntime
        ↓ latest plain-data publication
GUI presentation handoff
        ↓
CompositorVisualizerLayer
        ↓
display compositor framebuffer
```

`SpotifyBarsGLOverlay` remains historically named state/GL-resource host code. It is not a
presented surface.

The logical runtime never mutates compositor/GL state.

The compositor never advances visualizer simulation.

## 5. Card

The authored card may be prepared with QPainter/QPixmap at state/geometry/style invalidation
boundaries.

Steady presentation uses a retained compositor-owned GL texture.

Card texture and visualizer shader use one authoritative presentation geometry:

- logical rect;
- compositor/display DPR;
- framebuffer origin/size;
- viewport/scissor/mask alignment.

## 6. Presentation liveness

One display presentation strategy owns physical frame opportunities.

Active reasons are additive. Transition end cannot stop presentation while another compositor-owned
animation still needs frames.

There is no second visualizer presentation timer.

There is no compositor-owned visualizer simulation clock.

## 7. Admission

Cross-thread callback coalescing may keep one queued GUI callback outstanding.

That guard ends when the callback executes.

Paint completion is not an admission token.

No:

- pending-until-paint;
- paint acknowledgement;
- render self-requeue;
- repaint rescue;
- producer/display divisor gate.

## 8. Visualizer readiness / fade

Visible presentation requires the current compositor/card/geometry/resources to be ready.

Do **not** universally require real audio/source identity before every visible scene.

At minimum distinguish:

```text
presentation_ready
reactive_source_ready
```

A presentation-owned idle scene may reveal while reactive source remains unavailable.

Paused Spectrum is the canonical case.

The compositor owns card + visualizer pixels for the entire fade. One fade authority applies to both.

## 9. GL resource ownership

- Qt-owned context is borrowed;
- one numeric handle has one deletion owner;
- visualizer programs/VBO/VAO/mask/card texture are tied to compositor QRhi generation;
- hidden/no-published visualizer state does not erase destruction authority;
- runtime cleanup and QRhi resource release converge on one owner contract;
- failed deletion retains ownership and fails closed;
- ResourceManager accounting releases only after deletion succeeds.

## 10. QPainter fallback

Main compositor may use its explicit base-image QPainter fallback where acceleration is unavailable
for that base path.

This does not generalize to visualizer rendering.

## 11. Transition model

Transition progress is display-local monotonic elapsed time with exactly-once completion.

A bad transition window does not automatically prove transition-shader cost. Shared GUI/dispatch
starvation must be excluded before per-transition optimization.

The 165 Hz non-visualizer display is a useful shared-presentation control.

## 12. CUSTOM / Edit

Visualizer pixels belong to the compositor while logical geometry/editor anchor may remain
QWidget-based.

Edit preview comes from compositor-owned scene state, not an obsolete visualizer framebuffer.

Drag/resize may use preview state. Save publishes one new authoritative rect; Cancel restores/resumes
the prior owner.

## 13. P5 boundary

Presentation architecture does not replace monitor topology lifecycle.

P5 still owns settled topology authority, immutable transaction snapshot, retire/barrier/rebuild/
reveal and sticky configured-monitor semantics.

The visualizer logical runtime is another generation-owned producer that must quiesce/join during
runtime retirement.
