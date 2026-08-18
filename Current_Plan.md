# Current Plan

Last updated: 2026-08-18  
Branch: `main`  
Active phase: Phase 5 — presentation architecture correction, delivery recovery, and monitor hardening

This file contains **unfinished active work and the minimum accepted evidence needed to execute it**.
Stable architecture belongs in `Spec.md`; detailed evidence belongs in phase reports/audits; solved
failures belong in `Docs/Historical_Bugs/`; temporary diagnostic retirement and unrelated debt belong
in `Future_Cleanup.md`.

## Current Authority And Evidence

- Work directly on current `main`.
- Historical commits are negative controls/forensic references only.
- Preserve `ff93461685476bd0657aa88312fc2e35e9037880` as the user-approved Bubble/Spectrum behavioural reference until a later exact commit receives explicit approval.
- `main.py` is the ordinary performance/hostile/soak/evidence authority.
- Diagnostic builds are lifecycle/attribution products, not performance baselines.
- Media Center receives bounded shared route/build coverage.
- `Current_Plan.md` owns active execution order.
- `Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md` owns the accepted 2026-08-16 through 2026-08-18 delivery evidence and should retain the detailed A/B/C/D history.
- `Future_Cleanup.md` owns temporary diagnostic retirement and deferred/test debt; it is not an alternate active plan.
- Do not freeze raw log/ZIP paths into `Index.md` or roadmap navigation.

### Accepted 2026-08-18 Qt architecture audit

This audit **changes the active implementation direction**. It does not declare P2 or P4 solved.

The current per-display compositor and Spotify visualizer surface are both `QOpenGLWidget` based.
Qt 6.9.1 does not present a `QOpenGLWidget` directly. It renders the widget into an offscreen FBO
using the widget's own `QOpenGLContext`, then the top-level QWidget backing-store/QRhi compositor
consumes that texture and presents the complete top-level window. Before composition,
`QOpenGLWidgetPrivate::beginCompose()` makes the child context current and calls
`flushShared()`; on NVIDIA Qt uses `glFlush()` for that shared-context visibility boundary.

The valid P4 stage run localized the severe sampled stalls **after SRPSS compositor paint**:

```text
              outer  core  overlay | paint->compose  compose->swap  paint->swap
Crumble        3.26  0.29     2.94 |        36.04          14.18        50.22
Warp           9.56  6.10     3.44 |        38.08          12.12        50.20
Wipe           3.77  0.12     3.62 |        36.61          13.16        49.77
Slide          3.95  0.07     3.85 |        35.69          12.81        48.50
```

Ordinary sampled end-to-swap values were about `0.4-0.46 ms`. The Python
`aboutToCompose`/`frameSwapped` observer has a GIL-entry caveat, so the table is **not** proof that
Qt itself spends exactly 36-38 ms in one internal call. It is, however, consistent with the
source-audited `QOpenGLWidget` cross-context handoff located in that exact boundary.

Qt 6.9.1 also provides `QRhiWidget`. A `QRhiWidget` uses the **top-level window's QRhi** rather than
creating the additional `QOpenGLWidget` child rendering context. It supports foreign/raw OpenGL
inside a render pass via `QRhiCommandBuffer.beginExternal()` / `endExternal()`. SRPSS is pinned to
PySide6 6.9.1, where the required QRhi family is expected to be available; implementation must
verify the actual Python bindings before mutation.

SRPSS's VSync policy remains intentional and is **not the active defect hypothesis**:

- global `QSurfaceFormat` is configured with `swapInterval(0)` before `QApplication` creation;
- Qt's top-level RHI backing-store swapchain requests `NoVSync` when the top-level window format has interval 0;
- SRPSS remains timer/refresh-cap driven rather than VSync-driven;
- a driver/DWM can still impose presentation behaviour externally, but no current source evidence shows SRPSS accidentally requesting VSync=1.

### Causal status after the audit

**Proven:**

- P2: the auxiliary visualizer publication -> `SpotifyBarsGLOverlay.update()` stream is a material shared-GUI amplifier under the current `QOpenGLWidget` implementation.
- P3: remaining visualizer-family state/handoff preparation cost is real but too small to explain the large delivery defect; P3 is closed.
- P4: severe no-visualizer stalls can occur with only a few milliseconds of SRPSS compositor GPU work and are localized after compositor paint.
- The current compositor and visualizer surfaces both pay Qt's `QOpenGLWidget` render-to-texture/shared-context composition architecture.

**Strong candidate, not yet proven by production A/B:**

- the `QOpenGLWidget` child-context -> top-level QRhi shared-context handoff is the major P4 architecture owner and may also be the mechanism that makes the P2 auxiliary update stream unusually expensive.

**Decision:**

Stop expanding P4 instrumentation. Test the architecture directly with a bounded
`QOpenGLWidget -> QRhiWidget(OpenGL)` migration, first on the main compositor and, only after that
checkpoint is accepted, on the Spotify visualizer GL surface.

## Checkpoint Policy

A checkpoint is a rollback anchor, not a pause for permission.

- Make a clean narrow commit after each independently risky architecture slice.
- Run the owning focused tests and smallest useful runtime/evidence gate.
- If the gate passes, keep the checkpoint and continue.
- Stop on failed evidence, contradicted causal model, dirty/conflicted repository state, or an affected visual result requiring operator judgement.
- Never carry a failed experiment forward through compensating flags, retries or hidden alternate paths.
- **Do not combine the main-compositor QRhi migration and the Spotify-overlay QRhi migration in one commit.** Their causal owners are different (P4 vs P2), even though they share a substrate.

## Non-Negotiable Guardrails

### Existing fidelity and ownership bars

- Keep `versioning.py` user-owned unless a version change is explicitly requested.
- Preserve Bubble authored-step cadence, dt, source/event sampling, one-in-flight semantics, simulation and ordinary COMPUTE ownership.
- Preserve Spectrum authoritative source/state evolution on the existing visualizer tick.
- No second visualizer clock, paint-local logical-state mutation, source decimation or cadence cap.
- Logical/state-evolution cadence is distinct from presentation opportunity.
- Attack GUI/presentation ownership before moving Bubble/Spectrum timing.
- Do not create one catch-all "third thread".
- Qt/QWidget/QPixmap/GL mutation stays on the correct GUI/context owner.
- Strict GL teardown remains fail-closed and byte-accounted.
- Keep the production CPU image-cache cap at 256 MiB until measured evidence justifies a deliberate change.
- No sleeps, nested event pumping, production `gc.collect()`, working-set trimming, process recycling, timeout extension, ignored owners, hidden runtime fallback paths or cadence hacks.
- Configured visualizer display ownership remains sticky across transient sleep/wake/non-participation.
- Preserve ordinary stable cold-start anti-flash behaviour. `screen.grabWindow(0)` may remain on normal desktop -> screensaver startup; any bypass remains recovery-specific unless separately approved.

### QRhi migration bars

- Force the QRhiWidget backend to **OpenGL**. This checkpoint reuses the existing PyOpenGL renderer; it is not a Direct3D/Vulkan rewrite.
- Do not rewrite transition shaders into QRhi pipelines in this checkpoint.
- Do not start a Qt Quick/QML migration in this checkpoint.
- Do not add `DwmFlush`, `glFinish`, fence waits, swap waits, sleeps, polling, or event pumping as a "fix".
- Do not change authored transition duration, display refresh caps, visualizer publication cadence, image quality, shader quality, overlay fidelity, CUSTOM geometry, or display support to improve timing.
- Do not add a silent runtime fallback from QRhiWidget back to QOpenGLWidget. The old commit is the rollback anchor. If QRhi cannot satisfy the contract, fail the checkpoint rather than hiding the failure.
- The top-level `QSurfaceFormat` interval-0 policy remains. Removing `apply_widget_surface_format()` from a QRhiWidget child must **not** remove or weaken the global pre-`QApplication` format configuration that drives Qt's top-level `NoVSync` swapchain request.
- Treat the top-level QRhi/OpenGL context as **borrowed Qt ownership**. SRPSS may use it only through the QRhi lifecycle/foreign-rendering contract; it must not destroy it or casually `doneCurrent()` a context Qt owns.
- `QRhiWidget.rhi()` is lifecycle-scoped. Do not depend on calling it from arbitrary callbacks merely because a pointer happened to work once.
- Preserve the current raw-GL program/texture/geometry ownership model unless a specific object must change owner. One numeric GL resource must still have one deletion owner.
- Preserve the current hidden shared warmup semantics unless an equivalent same-context mechanism is implemented and tested. Do not trade steady delivery for first-use shader/texture stalls.
- Preserve real QPainter-owned fallback/HUD behaviour. If `QPainter(widget)` is not valid inside the QRhi external pass, use an explicitly proven OpenGL paint-device path (for example `QOpenGLPaintDevice`) or another equivalent that renders into the active QRhi target. Do not simply delete the fallback or PERF HUD to make the migration easier.
- Do not manufacture a replacement for `aboutToCompose`/`frameSwapped` merely to keep old P4 diagnostic fields alive. Production architecture outranks obsolete instrumentation.

# Phase 5 — Active Work

## Immediate Priority Queue

This queue is the **execution authority**:

```text
P0  diagnostic-scaffolding cleanup                         CLOSED
P1  production presentation/fidelity contract              CLOSED / LOCKED
P3  visualizer-family handoff/preparation attribution      CLOSED as secondary

P4-RHI-A  main compositor QOpenGLWidget -> QRhiWidget      LANDED
P4-RHI-B  installed no-visualizer acceptance               ACCEPTED
P4-RHI-C  compositor fallback state made explicit          LANDED
P2-RHI-A  SpotifyBarsGLOverlay -> QRhiWidget               LANDED then ROLLED BACK
P2-RHI-B  installed visualizer-on acceptance               REJECTED (5.7x severe-gap regression)
P2-SINGLE-SURFACE  one surface per display                 LANDED (automated bars green)
P2-SINGLE-B  installed visualizer-on acceptance            ACTIVE
REMEASURE equivalent ordinary 165 Hz + 60 Hz scenario
P5  monitor-topology / sleep-wake hardening                MANDATORY NEXT
P6  lower-leverage Phase 5 work                            AFTER P5
```

The old order P2 -> P3 -> P4 is superseded because the Qt-source audit identified a **shared surface
backend mechanism** beneath both P2 and P4. This does not merge their acceptance criteria.

## P1 — CLOSED / LOCKED production presentation and fidelity contract

Keep the existing P1 tests and versioned goldens as architecture-neutral acceptance bars.
In particular:

- every accepted visualizer publication integrates exactly once;
- presentation may consume fewer opportunities but cannot alter logical state evolution;
- Bubble positional/extra/trail payload, transient energy, band state and protected visible edge remain covered;
- Spectrum smoothing/source evolution remains authoritative on the existing tick;
- stale generation/activation snapshots are rejected;
- no visualizer presentation authority moves to `AdaptiveTimerStrategy`;
- the mixed-refresh closed-form model remains a hazard light only, never installed acceptance.

Do not weaken these tests to accommodate QRhi.

## P3 — CLOSED as measured secondary cost

Retain the accepted finding:

- Bubble total callback roughly `285 us`;
- DevCurve roughly `277 us`;
- bar build/clamp roughly `27 us`;
- remaining static/config work is real but not the 33-144 ms delivery owner.

Do not reopen P3 extraction before P4/P2 surface work unless new direct evidence contradicts this.

# P4-RHI — Main compositor surface migration

## P4-RHI-A — LANDED implementation checkpoint

The per-display `GLCompositorWidget` is now a `QRhiWidget` on the OpenGL QRhi backend, rendering
the existing PyOpenGL transition renderers inside an `ExternalContent` render pass. The Spotify
visualizer overlay is untouched and remains P2-RHI-A.

Detailed binding/lifecycle evidence lives in
`Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md` under "P4-RHI-A".

**This checkpoint does not close P4.** No installed runtime evidence exists yet.

### What landed

- `rendering/gl_rhi_surface.py`: narrow external-OpenGL QRhi substrate — generation-fenced
  borrowed-context handle, exception-safe `ExternalContent` pass/`beginExternal` bracketing, a
  `QOpenGLPaintDevice` painter for the QRhi target, and the `Api.OpenGL`-selecting base widget.
  Reusable by P2-RHI-A; deliberately not a rendering framework.
- Compositor lifecycle translated: `initializeGL`->`gl_initialize`, `paintGL`->`gl_render`, plus a
  real `releaseResources` path. Child-only `setFormat()`/`setUpdateBehavior()` are gone; the global
  pre-`QApplication` interval-0 `QSurfaceFormat` policy is untouched and covered by a test.
- Context ownership: SRPSS borrows the Qt-owned QRhi OpenGL context and never destroys or
  `doneCurrent()`s it. Hidden shared warmup context is created from it and generation-fenced.
- QPainter fallback and PERF HUD now render into the QRhi target via `QOpenGLPaintDevice`; neither
  was deleted or resized.
- Dead `makeCurrent`-only warmup wrappers and dead `QPainter(widget)` overlay wrappers removed.

### Automated bars passed

`tests/test_p4_rhi_compositor_surface.py` (32 bars) plus the migrated owning suites:

- OpenGL API selected in the constructor and never silently Direct3D (structural + runtime);
- render pass declares `ExternalContent` and brackets raw GL exactly once;
- body / `beginExternal` / `beginPass` failures never strand an open external block or pass, and a
  render exception never propagates into the Qt virtual override;
- borrowed context exposes no release/destroy API and is never `doneCurrent()`-ed;
- generation changes only on real QRhi replacement, not on resize;
- resize re-initialize does not rebuild immutable resources;
- strict cleanup fails closed with no usable context and retains ownership;
- hidden warmup context retired on share-group death;
- fallback/HUD paint into the QRhi target in one painter session;
- no application-side `swapBuffers`; transition dispatch table and `update()` ownership unchanged;
- raw WGL probe refuses to run without a live borrowed drawable.

Gate result: 264 passed / 25 skipped across the compositor, transition, stage and P4 suites;
`test_frame_timing_workload` shows dt_max parity with the QOpenGLWidget baseline
(16.97 vs 17.11 ms). Every changed file compile-checked.

Pre-existing failures confirmed identical on a clean stash of `main` and therefore not caused by
this checkpoint: `test_slide_transition::test_slide_position_calculation`,
`test_slide_jitter` (2), `test_block_puzzle_flip::test_block_puzzle_set_flip_duration`, and the
known native test-process exit in the combined lifecycle run.

### Construction ordering is now a production contract

Qt derives the top-level backing-store QRhi configuration at window creation. A `QRhiWidget` added
to an already-created window **never renders**. Production previously showed the DisplayWidget
before creating the compositor, so a naive inheritance swap would have produced silently black
displays. `rendering/display_setup.py` now creates the compositor before `show()`; the remaining
lazy path logs an error instead of failing silently. Both are covered by tests.

## P4-RHI-B — ACCEPTED installed acceptance gate

Accepted on 2026-08-18. Evidence preserved at
`logs/evidence_chest/08_18_qrhibaselinenoviz_10_26` — do not overwrite, rename, move or clean it.

Single 60 Hz display, QRhi main compositor, no visualizer, ordinary runtime:

```text
                         >33 ms gaps   >50 ms gaps   worst
P4 pathology (pre-QRhi)      29            28        ~80.7 ms   (median ~58.5 ms)
QRhi compositor               9             0        ~42.1 ms
```

The recurring severe `>50 ms` class collapsed to zero and normal transition delivery is
approximately refresh-limited. **P4-RHI-A is retained.**

Known co-change, recorded so no one invents a split later: effective interval-0 enforcement moved
onto the real presenting context at the same time as the child-context handoff was removed. Both
plausibly contribute; no percentage attribution between them is claimed. Detail lives in the P05
phase report.

No further P4 stage/DWM/no-HUD attribution work precedes P2.

## P4-RHI-C — LANDED compositor fallback visibility

Steady retained-base rendering could drop to the QPainter base-image path with no record while
active-transition failure was already loud. It is now a bounded STATE-CHANGE record: ordinary
startup states stay silent, an established compositor entering fallback emits one error naming the
reason, repeated frames never spam, and recovery emits one info record and clears the latch.
Rendering behaviour, cadence, dispatch, scheduling and GL ownership are unchanged; no CLI flag and
no timing measurement were added.

# P2-RHI — sibling QRhi visualizer surface — REJECTED

## P2-RHI-A — LANDED experiment, then rolled back

Landed as `9e98755d`, rolled back in `723bcfc8`. The commit history is intact;
history was not rewritten.

## P2-RHI-B — REJECTED installed

Reason: **severe delivery regression.** Single 60 Hz display, visualizer on:

```text
                                     >33 ms   >50 ms   median      max
QRhi compositor, no visualizer            9        0        --   ~42.1 ms
QRhi compositor + QOpenGLWidget vis      23        4   ~45.23 ms  151.27 ms
QRhi compositor + QRhiWidget vis         49       29   ~54.76 ms  ~125.07 ms
```

Severe-gap frequency regressed roughly **5.7x** versus the architecture it
replaced. Transition examples: BlockSpin 57.3 FPS / dt_max 125.77 ms; BlockSpin
55.6 FPS / dt_max 107.56 ms; Burn 58.2 FPS / dt_max 71.71 ms; RainDrops
57.1 FPS / dt_max 78.44 ms.

The decisive detail: the visualizer shader got **cheaper on the GPU** while
delivery got **worse**.

```text
sampled GPU median   old QOpenGLWidget   QRhiWidget
Spectrum                    ~0.044 ms      ~0.018 ms
Bubble                      ~1.69 ms       ~0.78 ms

surface CPU paint p50
Spectrum                    ~0.48 ms       ~0.90 ms
Bubble                      ~0.49 ms       ~0.86 ms
```

The high-rate independent presentation stream also survived the migration:
Bubble and Spectrum still issued roughly one surface update per publication,
commonly ~85-100 Hz on a 60 Hz display.

## What the experiment proved

This was not wasted work. It falsified the remaining cheap hypothesis:

> Sharing the top-level QRhi is **not** sufficient. A second independently
> dirtied texture-backed presentation surface remains materially harmful on its
> own, even with no separate context, no separate swapchain, and a cheaper
> shader.

That result is what promotes the one-surface-per-display architecture, and it
closes off tuning, rate-capping, coalescing, admission and pacing of a second
surface as answers. None of those are to be revisited.

## Forbidden follow-ups

- Do not tune the sibling QRhiWidget.
- Do not cap its update rate or add coalescing.
- Do not make AdaptiveTimer the authority of a second visualizer surface.
- Do not re-test the sibling surface on dual display.

## The fallback error in that run was not the owner

The run recorded one `[GL PAINT][FALLBACK] reason=texture_cache_miss` followed in
the same second by recovery with `fallback_frames=1`, then nothing. Zero later
fallback entries, zero QRhi render failures, zero visualizer shader failures,
zero surface initialization failures, clean GL teardown. It was first-frame
texture cache establishment and is now classified as such (see P4-RHI-C below).
It is not under investigation as a performance owner.


# P2-SINGLE-SURFACE — ACTIVE

One accelerated Qt presentation surface per physical display. The visualizer
ceases to be an independently presented QWidget/QRhiWidget/QOpenGLWidget surface
and becomes a layer inside the display compositor. It must not be replaced by
another independently dirtied native/texture-backed surface under a new name.

The hardware-acceleration contract for this architecture is recorded in
`Docs/Compositor_Architecture.md` section 0.

## LANDED so far

### Presentation liveness reasons (`41915576`)

The compositor previously presented only while a transition ran. One render
strategy instance per display now owns presentation through an explicit reason
set:

```text
TRANSITION_ACTIVE   held for the duration of a transition
VISUALIZER_ACTIVE   held while a visualizer is visibly active on this display
```

Presentation starts on the first reason and pauses only when the last releases,
so transition completion cannot stop an active visualizer and a visualizer
hiding cannot stop an active transition. This is **not** a second visualizer
clock: one presentation owner, targeting the display's configured refresh rate,
with logical visualizer cadence untouched and independent.

A structural bar asserts only the reason model may start/pause the render timer,
so a second presentation owner cannot be reintroduced quietly.

16 bars in `tests/test_compositor_presentation_liveness.py`.

## LANDED — visualizer renders inside the compositor (`cb041ba6`)

`SpotifyBarsGLOverlay` is no longer a presented surface. It is a plain,
never-shown `QWidget` that paints nothing, retaining the authored logical state
integration and the card geometry anchor. Presentation moved to
`rendering/gl_compositor_pkg/visualizer_layer.py`, drawn inside the compositor's
existing external GL render pass.

Scene order:

```text
base image -> transition -> visualizer card visual -> visualizer shader layer -> HUD
```

### Publication seam

Each accepted publication publishes latest-wins render state to the owning
display compositor, carrying runtime generation and activation identity. A
publication from a retired generation is rejected rather than drawn. Nothing is
queued, nothing is acknowledged, there is no pending-until-paint latch and no
catch-up replay. The old one-update-per-publication surface stream is removed
rather than redirected to another QWidget.

### Coordinates

The mode shaders draw a fullscreen quad, so the card rect becomes a
`glViewport`/`glScissor` in display pixels with the GL y-flip, while the shaders
still receive a card-sized local rect so authored geometry is unchanged. The
stencil mask reads `gl_FragCoord` (window space), so its rect uniform now
carries the card's display-space origin explicitly. Scissor bounds every write
the layer makes, including the stencil clear, and the layer never clears the
colour buffer.

### Card visual

The card QWidget is a sibling **above** the compositor, so leaving it painting
its own background would cover the bars. It now yields only its pixels - reusing
its existing cached pixmap, so border width, radius, shadow and fade are
unchanged - and keeps geometry, CUSTOM movement, saved layout, visibility/fade
authority and edit interaction. Ownership is handed back when the layer clears
or tears down.

### Lifecycle

Visualizer GL resources live on the compositor's borrowed QRhi OpenGL context.
Creation is idempotent so a render-target resize does not rebuild immutable
programs/VAO/VBO; deferred warmup borrows through the QRhi seam and is
generation-fenced; strict deletion runs with that context current through the
existing fail-closed owner; compositor teardown drives it. There is no
independent visualizer surface lifecycle left to race display teardown.

### Failure policy

Visualizer failure clears the layer and reports once, boundedly. There is no
CPU/QPainter substitute renderer, per the hardware-acceleration contract in
`Docs/Compositor_Architecture.md` section 0.

### Bars

36 in `tests/test_p2_single_surface.py`: one accelerated surface per display and
no reacquired surface class; publication contract including stale-generation
rejection and no admission/pacing; non-zero CUSTOM offset and DPR coordinate
conversion; mask origin in display space; scene safety and scissor containment;
card ownership and release; bounded failure with no CPU substitute; and
`publications == integrations` across 60/165-style presentation schedules.

The P1 presentation-contract bars were re-pointed at the publication seam
instead of a surface repaint, because `publications == paints` is no longer the
architecture. Their logical-equality assertions are unchanged.

Two real-GL compositor cleanup tests that had silently skipped since P4-RHI-A
(they called the retired `makeCurrent()`) now borrow the QRhi context and
exercise strict cleanup again.

## P2-SINGLE-B — ACTIVE installed acceptance

One installed run, single 60 Hz display, visualizer on, Bubble and Spectrum,
broad transitions, ordinary runtime:

```bash
python main.py --perf --gpu-timing
```

No extra P4 diagnostics. Compare against
`logs/evidence_chest/08_18_qrhibaselinenoviz_10_26` and the pre-P2 visualizer-on
baseline. If delivery returns close to the accepted no-visualizer QRhi baseline
with healthy fidelity and state-to-paint, proceed immediately to the
165 Hz + 60 Hz combined acceptance.

P5 physical monitor topology / wake hardening remains mandatory after the P2/P4
presentation architecture closes.


# Equivalent dual-display remeasurement after P4/P2-RHI

After the accepted QRhi checkpoints, repeat the ordinary production scenario equivalent to the
2026-08-16 baseline:

- 165 Hz + 60 Hz;
- broad transitions;
- Bubble and Spectrum separately;
- no visualizer control;
- Media/GSMTC still enabled where it was enabled in the accepted control;
- ordinary `main.py` is the authority.

Record:

- compositor delivered/target FPS per display;
- visualizer logical publication, state handoff, update request and paint rates;
- Bubble state-to-paint p50/p95/max and protected-edge receipt;
- transition vs steady windows;
- severe frame-gap and request-age tails;
- GPU timing only as supporting attribution, not as the success metric.

Do not claim P2/P4 closure from tests alone.

# P5 — Mandatory monitor-topology and physical sleep/wake hardening

P5 remains mandatory immediately after the presentation architecture gates. The QRhi migration
must not be used to erase or defer the installed wake failure.

## Accepted wake signature

```text
~19:58:51  topology churn: MSI present, LG temporarily absent
            reconcile already pending and not re-armed
            transient one-display snapshot accepted
            full teardown/rebuild begins

~19:58:55  LG returns
            second two-display snapshot accepted
            second full teardown/rebuild begins
```

Observed consequences included stale/deleted display events, temporary visualizer ownership
fallback, two serial full-runtime replacements, and a final last-entered/not-returned boundary in
D1 CUSTOM Media replay. GL teardown itself completed far enough in that capture to be demoted as
the leading terminal owner for that incident, not globally exonerated.

## P5-A — one authoritative monitor-topology owner

- [ ] Make one engine-level manager the sole authority that decides no-op, re-anchor or full runtime replacement.
- [ ] Reduce native/Qt per-window display callbacks to topology-invalidated notifications plus local bookkeeping.
- [ ] One accepted topology generation drives one replacement decision.
- [ ] Duplicate native + Qt storms must not race stale-widget mutation against engine replacement.

## P5-B — true trailing-edge topology settling

- [ ] Every relevant topology event restarts the quiet-period timer.
- [ ] Add a bounded maximum settle deadline; reaching it yields one explicit best-known snapshot, not retries/event pumping.
- [ ] Freeze count/order/identity/geometry/DPR into one immutable accepted snapshot/generation before destructive replacement.
- [ ] Newer topology invalidates/queues a later transaction rather than mutating the one already rebuilding.
- [ ] Deterministically reproduce the captured temporary-one-display -> final-two-display churn and prove one final rebuild.

## P5-C1 — transactional replacement and explicit readiness commit

```text
settle topology
  -> freeze snapshot/generation
  -> stop old-runtime topology mutation
  -> retire old runtime once
  -> pass destruction barrier
  -> construct/register complete replacement
  -> stage per-display reveal/widget readiness
  -> commit only at the defined all-displays-ready boundary
```

- [ ] Generation-fence delayed reveal/readiness callbacks.
- [ ] Do not report/act fully RUNNING merely because DisplayWidget objects exist unless every pre-ready owner is proven safe.
- [ ] Do not weaken strict GL/QRhi resource teardown or extend destruction timeouts as a shortcut.

## P5-C2 — generic per-widget CUSTOM replay boundary

- [ ] Retain low-frequency before/after breadcrumbs around generic CUSTOM replay stages.
- [ ] Split payload, offset reset, `update_position()`, committed `setGeometry()` and final boundaries.
- [ ] Start analysis with Media because the captured run ended there, but do not hard-code Media as root cause.
- [ ] Keep screen/runtime/topology generation identity explicit in each calculation.
- [ ] No retries, sleeps, event pumping or timeout recovery around geometry calls.

## P5-D — sticky visualizer display ownership

- [ ] Temporary asleep/rebuilding/non-participating configured monitor != absent monitor.
- [ ] No eager cross-display transfer during transient wake topology.
- [ ] Cross-display fallback begins only after an authoritative settled topology proves genuine absence, followed by one intentionally coarse approximately 60-second confirmation opportunity.
- [ ] Any newer topology generation invalidates the absence candidate.
- [ ] Return-home is event-driven and timer-free when configured display returns and becomes ready.
- [ ] Preserve CUSTOM geometry/aspect authority across fallback/return.

## P5-E — recovery-specific desktop capture bypass

- [ ] Keep `screen.grabWindow(0)` on ordinary stable cold startup for anti-flash polish.
- [ ] Do not synchronously require a waking-desktop screenshot during topology replacement/recovery.
- [ ] Prefer retained SRPSS state or wait for first real SRPSS image without event pumping.

## P5-F — installed physical-off/wake acceptance

- [ ] repeated ordinary installed cycles with both displays physically off before/during saver activation;
- [ ] meaningful long-idle/overnight-equivalent where practical;
- [ ] simultaneous and opposite sequential wake orders;
- [ ] temporary one-monitor churn before sibling stabilizes;
- [ ] configured visualizer target returns before grace, remains truly absent beyond grace, and later returns after fallback;
- [ ] both displays recover/reveal, clocks advance, Escape/context menu/input remain responsive;
- [ ] one settled topology generation causes one replacement transaction;
- [ ] Ctrl+Alt+Delete is never required.

# P6 — Lower-leverage Phase 5 work after P5

Resume only after P4/P2-RHI and P5 gates:

- media-provider runtime validation (Firefox first, then Chromium);
- compact clock/date and media-progress installed validation;
- stronger visualizer source-to-state/source-to-visible goldens;
- remaining proven GUI service/cache extraction;
- canonical evidence-parser repair;
- absolute RAM/private-commit/VRAM/cache attribution;
- compatibility/fallback debris removal;
- low-priority presentation polish.

## Canonical parser debt that remains active in P6

`tools/recovery_evidence_parser.py` 1.21 currently claims to wrap a base parser while importing its
own canonical module name, creating a circular/self-import seam. Repair the canonical parser before
treating 1.21 as authoritative. Preserve old-format, fancy-main, sidecar, rotation and exact-source
coverage.

# Phase 5 Exit Gate

- [ ] Bubble and Spectrum are separately approved equal or better than `ff934616`; other modes retain current behaviour.
- [ ] Main compositor presentation no longer has the recurring severe P4 tail, or the surviving owner is explicitly named after the bounded QRhi candidate failed and a deliberate replacement architecture is selected.
- [ ] P2 auxiliary visualizer presentation is no longer a material shared-GUI amplifier, or the one-surface visualizer/card architecture is explicitly promoted with retained evidence.
- [ ] No cadence, source, fidelity, display-support or quality degradation was used to obtain the improvement.
- [ ] QRhi/GL resource ownership is strict through Settings recreation, display replacement and final shutdown.
- [ ] Equivalent 165 Hz + 60 Hz ordinary production delivery is remeasured after the architecture correction.
- [ ] Physical monitor-off -> screensaver -> wake recovery passes repeated dual-display installed cycles without frozen UI/blank sibling display, eager visualizer migration, weakened teardown, or cold-start anti-flash regression.
- [ ] Proven remaining GUI service/cache work is either corrected or explicitly attributed.
- [ ] Absolute RAM/private-commit/VRAM excess is reduced or explicitly attributed in an approved decision record.
- [ ] Canonical evidence parser/logging tests match current format/retention contracts.
