# Current Plan

Last updated: 2026-08-18  
Branch: `main`  
Document basis: current `main` after the P2 single-surface closure slices, against the accepted
installed runs that followed `b5ff451efd452780dc4b87dbc1f64d539ff4e6d3`  
Architecture epoch: **OpenGL QRhi, one accelerated presentation surface per physical display**

This file owns **unfinished active work and execution order**. It deliberately does not preserve the
full archaeology of P0-P4. Detailed old evidence stays in phase reports/history; deferred cleanup
stays in `Future_Cleanup.md`.

If `main` has advanced when work resumes, first verify that HEAD is a clean descendant containing
only expected newer work, then execute against exact current source. Do not restore an older owner
because this file names the checkpoint it was written against.

## 1. Authority Order

For active engineering work:

1. current user instruction;
2. exact current `main` source/tests;
3. this file for unfinished order;
4. `Spec.md`, `Docs/Guardrails.md`, focused guardrails and `Docs/Compositor_Architecture.md`;
5. current phase evidence for causal history/limits;
6. `Future_Cleanup.md` for deferred cleanup only;
7. historical reports/bugs as evidence and negative controls, never current owner maps.

`versioning.py` remains user-owned unless a version change is explicitly requested.

## 2. Binding Current Architecture

### 2.1 One physical presentation surface per display

Each `DisplayWidget` owns one accelerated compositor:

```text
DisplayWidget
   └── GLCompositorWidget
          └── ExternalOpenGLRhiWidget / QRhiWidget.Api.OpenGL
```

The compositor renders existing PyOpenGL work inside QRhi `ExternalContent` / external-GL
boundaries. Qt owns the QRhi and its `QOpenGLContext`; SRPSS borrows that context and never owns
`swapBuffers()`, destroys the borrowed context or casually `doneCurrent()`s it.

Hardware acceleration is the supported modern runtime contract. Do not create a CPU visualizer,
QOpenGLWidget compatibility visualizer or second QRhiWidget visualizer to preserve `hw_accel=off`.

### 2.2 The visualizer is a compositor layer, not a second surface

`SpotifyBarsGLOverlay` is retained for:

- logical visualizer state integration/publication;
- mode-owned render/GL resource ownership;
- geometry/CUSTOM anchor;
- shader/uniform helper state.

It is a plain, never-presented QWidget and paints no pixels.

Actual visualizer pixels are owned by
`rendering/gl_compositor_pkg/visualizer_layer.py::CompositorVisualizerLayer` inside the display
compositor. The authored card is prepared only when its canonical pixel identity changes, uploaded
to a compositor-owned GL texture and drawn in the same card-region viewport/scissor/blend boundary
as the visualizer shader.

One authoritative `PresentationGeometry` supplies:

- logical card rect;
- compositor/display DPR;
- framebuffer origin;
- framebuffer size;
- viewport/scissor/mask alignment.

Do not reintroduce separate live-widget size/DPR/presentation authorities.

### 2.3 Physical presentation and logical visualizer cadence are different authorities

The display compositor owns physical presentation opportunities.

The visualizer owns audio/source cadence, logical simulation, dt, events, smoothing and render-state
publication. It never waits for paint and the compositor never becomes its simulation clock.

A compositor presentation strategy may remain live for additive reasons such as transition and
`VISUALIZER_ACTIVE`. Ending one reason must not stop another.

A cross-thread GUI-dispatch guard may coalesce duplicate queued Python callbacks **only until the GUI
callback actually calls `QWidget.update()`**. Paint completion is not an admission token.

## 3. Accepted Evidence / What Is Already Decided

### 3.1 P4 main-compositor QRhi migration is retained

The old no-visualizer severe transition pathology collapsed after the main compositor moved from
QOpenGLWidget to QRhi/OpenGL:

```text
pre-QRhi no-viz:  29 gaps >33 ms, 28 >50 ms, worst ~80.7 ms
QRhi no-viz:       9 gaps >33 ms,  0 >50 ms, worst ~42.1 ms
```

Do not return to QOpenGLWidget compositor ownership or resume microscopic P4 stage attribution.

### 3.2 Sibling QRhi visualizer surface is rejected

Migrating the visualizer to a second QRhiWidget made installed delivery materially worse. Sharing the
top-level QRhi was not enough; a second independently dirtied texture-backed surface remained a bad
architecture.

Do not revive a second visualizer presentation surface, request-pacing experiment or compatibility
surface.

### 3.3 Single-surface visualizer architecture is retained

The visualizer/card now render inside the compositor. The latest installed run materially improved
performance versus the old separate-surface visualizer path.

Accepted measurement state from the run that preceded the closure slices in section 5:

```text
single-display:
  gaps >33 ms: 35
  gaps >50 ms: 4
  worst:       ~55.16 ms

dual-display:
  165-Hz display: ~153.3-153.7 FPS, ~93.18-93.44% request acceptance
  60-Hz display:  ~59.3-59.4 FPS, ~98.91% request acceptance

visualizer compositor state->paint:
  typical p50 roughly 3.4-5.9 ms

visualizer upstream/source age warnings:
  recurring class roughly ~90 ms median

exit GL accounting in both accepted runs:
  zero tracked GL resources / textures / bytes
```

The single-surface architecture is therefore **not** reopened merely because 165 Hz has not yet been
reached.

### 3.4 Corrected mechanisms awaiting installed confirmation

Every installed/user-visible defect from the previous round has a landed correction with a named
mechanism. None of them is confirmed until the acceptance run in section 5.

| Defect | Corrected mechanism |
|---|---|
| fade flashes/slams to full opacity | fade-zero renderer/card readiness gates the reveal; one compositor fade authority replaces the QWidget opacity side-channel |
| startup/stop/resume hitch | just-started capture is STARTING rather than unhealthy, so the immediate wake no longer restarts it; ordinary pause keeps GL, capture and generation intact |
| visualizer feels late | one analysis compute in flight plus one newest pending source frame, replacing the frame that used to be dropped |
| 165 Hz stuck near 153-154 | paint-acknowledged update admission removed; only the queued-GUI-dispatch guard remains |
| CUSTOM edit targets a retired surface | compositor-owned edit snapshot; presentation suspended without destroying generation-owned GL |

Causal evidence for each is recorded in the P05 report. Do **not** start another broad probe
campaign; the next input is one ordinary installed acceptance.

## 4. Non-Negotiable Guardrails For The Active Closure

- Preserve authored Bubble/Spectrum/Sine/Oscilloscope/DevCurve behaviour and all protected goldens.
- Do not lower audio/source cadence, logical visualizer tick rate, transition quality, image quality,
  shader quality or display support to improve counters.
- No second visualizer clock/surface/timer.
- No producer timestamp/display divisor gate.
- No pending-until-paint, paint/swap acknowledgement, repaint rescue or paint self-requeue.
- No catch-up replay/FIFO analysis backlog.
- No `glFinish`, `DwmFlush`, fence waits, sleeps, polling or GUI event pumping as a fix.
- No silent renderer fallback for the visualizer.
- Main-compositor base-image QPainter fallback remains a separate explicit capability and stays loud
  when unexpectedly entered after a healthy retained-shader path.
- Borrowed QRhi context ownership and fail-closed GL deletion remain strict.
- Card texture destruction authority survives hidden/cleared presentation state.
- Qt/QWidget/QPixmap/GL mutation remains on the owning GUI/context thread.
- Do not turn CUSTOM drag/resize into live GL rebuild work on every mouse event.
- Do not make diagnostics part of cadence/admission/control flow.

## 5. Immediate Next Step — One Installed Acceptance

The P2/P4 single-surface closure slices are landed and pushed:

```text
P2-READY-FADE          renderer readiness, one fade authority, audio STARTING health
P2-ACTIVATION-FINAL    one real generation transaction, identical-refresh suppression
P2-ANALYSIS-FRESHNESS  one in flight + one latest pending
P2-165-DELIVERY        paint-acknowledged admission removed
P2-WARM-PAUSE          hide through the fade authority, keep GL and capture warm
P2-CUSTOM-EDIT         compositor-owned edit snapshot and edit lifecycle
```

Remaining order:

```text
one dual-display installed acceptance   <- next
    ↓
P5 monitor topology / physical wake hardening
    ↓
P6 lower-leverage resource / cleanup work
```

P2-SINGLE-SURFACE remains retained and is **not** closed until the acceptance below passes.

## 6. The Acceptance Run

Run one ordinary dual-display acceptance with:

```text
python main.py --perf --gpu-timing
```

Exercise in the same run:

- startup fade;
- Bubble + Spectrum reactivity;
- pause/stop and resume;
- several image transitions;
- CUSTOM enter/move/resize/Cancel;
- CUSTOM enter/move/resize/Save;
- cross-display visualizer move if convenient.

Acceptance:

- fade is smooth from invisible to full with no flash/slam;
- no large startup/stop/resume visualizer hitch;
- visualizer no longer feels materially behind the music;
- 165-Hz path materially exceeds current ~153-154 if the removed admission gate was active;
- 60-Hz path remains effectively refresh-limited;
- no queued-callback backlog growth;
- protected mode behaviour/goldens unchanged;
- state-to-paint remains healthy;
- tracked GL/card resources return to zero at exit;
- CUSTOM preview/save/cancel uses compositor-owned pixels and correct geometry.

If 165 Hz still sits near ~153 after the paint-ack admission gate is actually gone, then perform one
bounded current-architecture scheduler/Qt/DWM attribution pass. Do not resurrect the old P4
instrumentation campaign or another visualizer surface.

## 7. P5 — Monitor Topology / Physical Sleep-Wake Hardening — MANDATORY

This block remains required even if P2/P4 performance becomes excellent.

Observed failure class: both physical displays can be off while the saver remains active; wake can
leave one frozen SRPSS display, the other blank, ordinary clock/input/Escape/context menu dead, and
Ctrl+Alt+Delete is required to disturb Windows enough to recover.

### P5-A — one topology decision authority

`DisplayManager` / one equivalent engine-level owner decides:

- no-op;
- re-anchor/local update;
- full runtime replacement.

Native Windows events, Qt screen events and per-window callbacks are invalidation/report inputs, not
competing mutation authorities.

### P5-B — trailing-edge settle + frozen snapshot

Every relevant topology event restarts a quiet-period settlement. A bounded maximum settle window
prevents indefinite postponement.

After settlement freeze one immutable transaction snapshot containing at least:

- screen count/order/identity;
- geometry/work area as required;
- DPR;
- configured visualizer display identity;
- transaction/topology generation.

Once destructive replacement begins, it uses that snapshot. A later event becomes the next
transaction rather than mutating the one already in progress.

### P5-C — transactional runtime replacement/readiness

Use:

```text
Notify -> Settle -> Snapshot -> Retire -> Rebuild -> Reveal
```

- stop old-runtime topology mutation;
- invalidate old runtime generation;
- retire once;
- strict borrowed-context/owned-resource GL cleanup;
- destruction barrier reaches zero retired ownership;
- construct/register all replacement displays against frozen snapshot;
- replay generic committed CUSTOM state;
- reveal only after current runtime/display/compositor readiness.

Do not weaken fail-closed teardown, extend timeouts, add retry loops or reintroduce hide/reuse.

### P5-D — generic CUSTOM replay

The old wake failure passed through CUSTOM reconstruction. Do not hard-code one Media/visualizer
special case. Reapply committed display-local CUSTOM geometry generically after replacement and
prove stale pre-rebuild widget geometry cannot overwrite it.

### P5-E — sticky configured visualizer display

Temporary participation/readiness loss is not monitor absence.

If the configured visualizer monitor still exists in settled authoritative topology, keep ownership
sticky and park/hide/defer presentation until that display is ready.

Only genuine settled-topology absence may arm one coarse, generation-owned approximately 60-second
confirmation. If still absent at that single check, fallback may occur once. No polling thread or
periodic monitor timer.

If the configured monitor later returns, authoritative topology + normal display readiness transfers
the visualizer home once. Return-home is event-driven.

### P5-F — recovery-specific desktop capture boundary

Preserve `screen.grabWindow(0)` for stable ordinary desktop -> screensaver cold-start anti-flash.

Do not make synchronous desktop capture a prerequisite of physical-wake/topology reconstruction.
Use retained SRPSS imagery/replay state or wait for a real first frame.

### P5-G — installed physical gate

Exercise repeated ordinary installed runs including:

- both displays off -> long idle -> wake;
- simultaneous wake;
- D0 then D1;
- D1 then D0;
- temporary one-monitor topology during wake;
- genuine configured-monitor absence > grace;
- return before grace;
- return after legitimate fallback;
- overnight-equivalent idle.

Pass requires both displays and normal input to recover without Ctrl+Alt+Delete, no eager visualizer
migration, no stale old-generation owners/resources and no monitor polling architecture.

## 8. P6 — Lower-Leverage Work After P5

Only after P5:

- long-run RAM/private-commit/VRAM attribution and leak slopes;
- remaining resource/cache efficiency with quality unchanged;
- diagnostic retirement listed in `Future_Cleanup.md`;
- harness/test flake cleanup;
- obsolete non-accelerated-path/toggle retirement;
- documentation and repository debris cleanup;
- unrelated provider/media experiments only in their own causal slices.

## 9. Long-Term Fallback Boundary

Do not use this unless the current QRhi/single-surface architecture fails a fundamental lifecycle or
fidelity contract that cannot be corrected within its ownership model.

The next architectural escape hatch is a full per-display `QQuickWindow`/Qt Quick scene owning base,
transitions, visualizer card/visualizer and other compositor-bound overlays. A partial `QQuickWidget`
or another embedded/native child surface is not preferred because it recreates multiple presentation
owners/stacking problems.

This is not active work while the current architecture is producing large measured gains.
