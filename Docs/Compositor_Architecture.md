# Compositor Architecture

Last updated: 2026-07-22

This document defines the implemented rendering architecture for fullscreen
SRPSS displays and the remaining runtime-promotion contract for the
single-surface compositor overhaul.

## Objective

Each active display owns one realized `QOpenGLWidget`, one current GL context,
and one render scheduler. Wallpaper presentation, shader transitions, dimming,
and GPU visualizer content are composed through that display-owned surface.
Ordinary Qt widgets and temporary CUSTOM edit shells remain separate Qt
widgets above the compositor.

"Single surface" is display-local, not application-global. A two-display run
has two compositor surfaces and two independent presentation targets. The PERF
overlay therefore reports display-local compositor/transition delivery and
`dt_max`; different simultaneous FPS values are expected when refresh, DPR,
resolution, paint coalescing, or OS presentation differs between displays.

The overhaul is intended to recover substantial CPU, presentation, and
multi-display headroom by removing the competing Spotify visualizer child GL
surface. It is not permission to reduce visualizer cadence, smoothing,
reactivity, transition resolution, transition duration, transition cadence,
or authored pixels.

## Non-Negotiable Behavior

- No startup flash, stale visualizer frame, uninitialized GL artifact, black
  frame, green-dot frame, or one-frame full-opacity card.
- No running flicker when a visualizer starts, stops, changes mode, changes
  preset, moves, resizes, enters edit mode, leaves Settings, or crosses a
  transition boundary.
- Accepted visualizer packets remain synchronous scratch storage. Generation,
  activation, required-waveform, and hidden-primer gates run before the packet
  is handed to the renderer.
- Visible transition progress remains paint-time `FrameState` authority.
- The committed CUSTOM rectangle remains the outer visualizer geometry
  authority. Renderer-owned buffers follow it; they do not reinterpret it.
- Display-local DPR, logical size, physical framebuffer size, refresh rate,
  and GL context remain independent. No display may borrow another display's
  viewport, VAO, FBO, timer target, or geometry.
- A slow or externally saturated display may coalesce presentation naturally,
  but producer-side packet drops and quality reductions are not acceptable
  fixes.
- Shader, stencil, card, fade, and first-visible behavior must remain
  pixel-equivalent to the pre-overhaul child-overlay reference.
- Legacy rendering is an emergency boundary, not a recovery strategy. A
  transient readiness miss, renderer/shader failure, or post-reveal failure
  must never create or switch to a second GL surface.

## Implementation Status And Original Pressure

Before this overhaul, the transition compositor and
`SpotifyBarsGLOverlay` were separate realized `QOpenGLWidget` surfaces. Both
consumed UI-thread delivery, Qt composition, GL context switching, and Windows
presentation work. Fresh mixed-refresh profiling showed long presentation
gaps while measured shader/paint work was comparatively small. That evidence
pointed to shared surface delivery pressure, not an individual visualizer mode
or transition shader.

The normal implementation now routes visualizer content through the
display-owned compositor. The old child widget remains only as an explicit
rollback/software-backend adapter and a narrowly authorized pre-reveal escape
for a hard compositor-layer failure. Automated and functional packaged parity
are healthy, but the first performance-promotion matrix did not deliver
repeatable ordinary-background headroom. Phase E is reopened rather than
calling architectural completion a performance success.

## First Packaged Matrix And Promotion Result

Three process lifetimes were preserved separately:

- The ordinary-background mixed `165/60 Hz` Normal run averaged/peaked about
  `93.5/125.5%` app CPU. High-refresh compositor paint windows delivered about
  `104-121.5 FPS` against `165 Hz`, while measured paint duration generally
  remained below `14 ms` and GPU usage stayed modest.
- The fresh-reboot mixed-display run improved materially, with about `82.0%`
  average app CPU and a representative high-refresh Slide paint window near
  `153 FPS`. This proves external/process state affects delivery, but a
  fresh-reboot result is a comparator rather than the deployment assumption.
- The 75-minute single-display MC run held compositor transition delivery near
  `60 Hz`, had no shader/program lifecycle failure, compositor visualizer
  render failure, or FBO churn, and kept ResourceManager GL registrations
  nearly flat. It still averaged `58.0%` app CPU (`83.0%` p95), submitted
  compute work at `93.4/s`, and accumulated `1,710` parser-recognized
  visualizer timing warnings with repeated `80-118 ms` latency while
  transitions were often idle.

These results support the display-owned compositor structure but reject its
performance promotion. The dominant unresolved shape is shared CPU/GIL/Qt
event-delivery pressure, not expensive compositor draw calls or GPU saturation.
Startup/cache/driver growth in short rebuild-heavy runs is not leak proof; a
post-warm slope with quiescent checkpoints remains required.

The first follow-up removes pressure that does not produce pixels:

- `ThreadManager` throughput statistics update a small locked snapshot in the
  submitting/completing threads. They no longer enqueue one UI mutation drain
  per task, and the unused 250 ms UI stats publisher/triple buffer is retired.
- A compositor frame with no dimming, PERF HUD, or active visualizer scene does
  not open a QPainter overlay session. Active visualizer paint order and pixels
  remain unchanged. PERF HUD runs still open the session by design.
- A registered but not-yet-shown staggered display reports
  `pending_compositor` rather than a terminal missing-compositor error. A real
  existing terminal reason remains authoritative and still stops short retries
  until target creation succeeds or the display generation is rebuilt. The
  clean pending state also schedules no 16 ms readiness retry; it waits for the
  existing staggered display lifecycle to realize the compositor.
- `--usage` uses collector-owned process/system CPU-time deltas, reports an
  unprimed value as `na`, and samples only the four hottest process threads at
  the existing 15-second off-UI cadence. The parser partitions sequence resets
  into process lifetimes and sorts dated rotations by full date.

No performance improvement is claimed for these corrections until the same
ordinary-background, fresh-reboot comparator, and long MC matrix is repeated.

## Latest Shared-Path Evidence And Candidate

The `2026-07-18 18:02:00-18:04:02` mixed `165/60 Hz` lifetime removes mode,
transition, provider, and fallback speculation from the next target. It opened
no Settings window, logged no transition refusal/instant commit/request drop,
shader/cache fallback, GL lifecycle error, unexpected legacy surface, or
visualizer FBO/render failure, and contained only sparse provider activity. It
still averaged `116.1%` process CPU (`133.2%` p95, `135.9%` peak) while GPU use
was about `3.9-18.5%`. `MainThread` averaged `62.1%`, and a native process
thread averaged another `15.5%`. Startup UI callback delays occurred before the
first transition. Screen 0 delivered roughly `46-85 FPS` against `165 Hz` and
screen 1 roughly `36-49 FPS` against `60 Hz`, even though ordinary paint-cost
maxima were commonly only `7-12 ms`.

Two shared architectural amplifiers explained that mismatch:

- each per-display render owner continued waking and attempting a Qt handoff
  while the compositor already had a paint outstanding, producing roughly
  `2-3.5x` as many owner wakeups as accepted paints and thousands of pending
  skips; and
- every ready idle paint opened `QPainter` and redrew the complete wallpaper
  before dimming/visualizer/HUD composition, so a small visualizer update paid
  full-scene raster presentation cost.

Adjacent ownership defects increased risk even when they were not the whole CPU
total: prefetch compute workers created GUI-thread-affine `QPixmap`, transition
completion retained a second UI timing authority, and one transient shader
failure could poison the optimized path for the rest of the process.

The current candidate therefore makes these corrections together:

- ready idle wallpaper presentation uses only the already-resident texture and
  one fullscreen GL quad; the paint path performs no upload or conversion;
- each display owner permits one outstanding Qt handoff, sleeps on accepted
  `paintGL()` acknowledgement while producers continue latching their latest
  generation, then resumes at its own next normalized deadline without a
  catch-up burst;
- prefetch workers return/cache `QImage`; the existing UI consumption seam is
  the only place that promotes presentation data to `QPixmap`;
- transition completion is queued only after a successful terminal shader
  paint and is guarded by transition generation; fallback, not-ready, base,
  cancellation, Settings rebuild, and teardown cannot commit it;
- transient shader/texture failure retains the committed frame and retry
  authority instead of disabling later shader work for the session;
- per-paint process-global GC toggles are removed, frame-budget locking is
  diagnostic-only, and fixed-window `[GL PAINT PATH]` telemetry makes optimized
  and QPainter fallback counts explicit per display.

This remains a runtime candidate, not a claimed performance win. The same
ordinary-background, post-reboot comparator, and long single-display MC matrix
must prove material headroom and exact visual/lifecycle parity.

### First Candidate Runtime Result: Safer Handoff, Base Residency Correction Pending Runtime

The `2026-07-18 18:57:32-19:00:27` script-mode mixed `165/60 Hz` run included
the candidate and a Settings-driven display rebuild at `18:59:54`. It confirms
the ownership correction but fails performance promotion:

- render `wakeups == frames` on both displays, `pending_skips=0`, generation
  lag stayed `0-1`, and the rebuilt generation retained the same behavior;
- there was no transition skip/refusal/instant commit/request drop, transition
  QPainter fallback, shader/program/legacy/FBO/render failure, or cache-worker
  fallback;
- process CPU still averaged `108.0%` (`120.1%` p95, `123.9%` peak), Python
  `MainThread` averaged `56.8%`, and GPU peaked at only `18.2%`;
- screen 0 transition paint averaged `98.9 FPS` against `165 Hz`, with average
  window `dt_max` `136.7 ms` and peak `188.8 ms`; screen 1 averaged `51.2 FPS`
  against `60 Hz`, with average window `dt_max` `136.2 ms` and peak `250.2 ms`;
- source visualizer tick delivery remained mode-independent at `84.2 FPS`
  weighted, but source `dt_max` reached `98.4 ms`; Spectrum, Dev Curve, and
  Bubble all showed transition-active and steady-idle compositor microgaps;
- display 1 rendered `2,556/3,308` idle paints (`77.3%`) through QPainter.
  Display 0 also recorded roughly one fallback after each transition, but had
  little continuous idle demand because no visualizer was assigned there.

The fallback pattern identified a mutable presentation-identity seam. A direct
Qt probe then separated two cases: reapplying an unchanged DPR preserves
`QPixmap.cacheKey()`, while a real DPR change detaches storage and changes it.
`DisplayWidget` had discovered display DPR `1.5`, but its `ImagePresenter` was
still constructed with DPR `1.0`. The display pipeline finalized a prepared
pixmap at `1.5`; presenter assignment/completion then changed that same object
back to `1.0` after the transition texture manager had indexed it.

The correction gives initial show, screen-change, target-size, resize, display,
and presenter paths one DPR authority and skips no-op mutation. Terminal
completion and snap-to-new cancellation now promote the already-uploaded
destination texture to a committed residency lease before transition-pair
release. Idle paint reads that lease directly, independent of later mutable Qt
identity, and LRU eviction protects it. A genuinely nonresident base may use
one coalesced hidden-context warmup and one residency-ready presentation update;
GL readiness re-arms a pre-show miss, while teardown invalidates queued work.
Visible paint never uploads, converts, or runs a recovery loop. A rejected
post-paint terminal dispatch pauses on the rendered terminal frame and gets one
managed deferred dispatch rather than a per-paint retry or sudden commit. This
is covered across all transition families, real-QPixmap DPR detachment,
same-geometry DPR changes, eviction, one-pixel-shrink geometry, and the
visualizer locks, but mixed-refresh runtime must still prove persistent fallback
is gone before promotion.

The short resource series is inconclusive rather than clean or leaking. RSS
ended `468.1 MB` above sample 2 while the bounded image cache grew about
`355.9 MB`; private/VMS ended `797.6 MB` higher and VRAM `291.6 MB` higher, with
about `91.2 MB` represented by registered GL texture growth. Threads stayed
flat, task backlog ended at three, and live GL registrations plateaued at `33`.
A long post-warm slope remains required after base residency is corrected.

### Second Candidate Runtime Result: Residency Passed, Terminal And UI-Tail Ownership Reopened

The dual-display `2026-07-18 20:06:17-20:10:53` and latest MC
`2026-07-20 03:25:58-03:34:32` lifetimes validate the committed-residency
correction. Across `43` dual and `50` normal-log paint-path windows, the parser
found zero persistent GL QPainter fallback, transition fallback, shader/program
fallback, unexpected legacy surface, visualizer render failure, or FBO churn.
That closes the previous immediate residency gate. The architecture must not
return to full-wallpaper QPainter presentation or a competing visualizer child
surface.

The runs do not earn performance promotion:

- dual display averaged `92.4%` process CPU (`112.9%` p95, `116.0%` peak),
  with Python `MainThread` at `46.1%`, a native main-process thread at `12.7%`,
  GPU peaking at `16.2%`, five passive pending-paint stalls, ten high-refresh
  under-target windows, two 60 Hz under-target windows, and paint gaps up to
  about `205 ms`;
- the latest MC lifetime averaged `72.1%` (`93.4%` p95, `95.4%` peak), with
  `MainThread` at `34.1%`, compute workers around `8-10%`, GPU peaking at
  `7.4%`, and the merged normal corpus containing nine pending-paint stalls,
  four 60 Hz under-target windows, and paint gaps up to about `161 ms`;
- renderer feed and compositor ownership remained healthy, yet the dual and
  normal corpora still produced `33` and `46` visualizer delivery microgap
  anomalies. Mode identity varied while the shared failure remained, so this
  is presentation/event-loop pressure rather than a mode-specific defect;
- rare phase breakdowns placed `90-109 ms` inside the shared visualizer
  `gpu_push` handoff in dual display and `98.4 ms` inside opt-in perf accounting
  in MC. These broad labels require finer lock/update/accounting attribution;
  diagnostic bookkeeping itself may not consume a visible frame budget;
- dual/MC RSS peaked around `1.66/1.59 GB`. Most short-run growth tracked the
  decoded ImageCache, but private memory, VRAM, and rebuild plateaus remain too
  high to call pristine without post-warm slopes.

The dual CUSTOM-save boundary also proves that transition state is not yet one
authority. At `20:09:39`, both display wrappers reported an active Rain Drops
transition while their compositor state had no current transition, no frame
state, and no terminal completion due. This matches the user-visible PERF HUD
remaining stuck on display 0 after a transition. In the MC run at `03:29:32`,
runtime teardown began while a newly admitted Particle transition was only
about `10 ms` old and `terminal_due=True`. Both MC and dual runs then produced
the raw Qt failure `Cannot make QOpenGLContext current in a different thread`
after edit/runtime teardown.

The 2026-07-22 candidate closes that implementation boundary:

1. Terminal paint, queued completion, display busy state, resident-base commit,
   PERF HUD state, and post-transition publication are one generation-scoped
   transaction. The terminal frame may be held while completion is queued, but
   no later transition or teardown observes a half-completed mix of owners.
2. Edit/Settings/topology teardown first closes transition admission and the
   compositor shutdown barrier, reconciles/cancels the terminal transaction
   into one committed base, then destroys GL resources on each Qt object's
   affinity thread. Reusable runtime pause keeps the render owner paused and
   reopens a fresh nested admission generation before first-image publication.
   Permanent teardown marks acknowledgement pending before requesting owner
   retirement without blocking Qt, so a fast worker callback cannot be
   overwritten by stale request-return state. Manager ownership remains until
   worker-finally acknowledgement, whose request-to-ack latency is emitted
   through `--perf`. Hidden warmup
   contexts and surfaces are generation-owned and cannot survive into a rebuilt
   display.
3. Static visualizer card chrome is a style/geometry/DPR-keyed CPU raster and
   context texture uploaded outside visible paint, then composed natively with
   premultiplied alpha. Ordinary visualizer-only compositor frames no longer
   enter QPainter. A partial native presentation suppresses QPainter double
   blending and retains the last-good path for the next accepted frame.
4. Image workers publish exact-format immutable upload payloads. One verified
   Qt share-group registry leases each immutable image texture across displays,
   uses producer fence plus GPU-side consumer wait, and deletes only after the
   final manager lease. Same-owner CUSTOM geometry uses a partial rebuild;
   topology/backend/context ownership changes remain fully quiesced rebuilds.
5. Dev Curve's pure spline solve runs as one epoch-tagged COMPUTE task with a
   latest-result handoff and hidden-until-ready first frame. Normal diagnostics
   avoid per-frame clocks/containers, and slow GPU publication plus worker time
   now have bounded parser-visible subphase evidence.

Promotion targets and the live checklist are owned by `Current_Plan.md`.
Nothing in this ordering authorizes lower visualizer source/render cadence,
FFT fidelity, smoothing, transition duration/pixels, image resolution, or
reactivity.

## Implemented Ownership

### `SpotifyVisualizerWidget`

Remains the authority for:

- enabled/visible lifecycle;
- media relationship and input handling;
- settings and preset application;
- accepted frame production;
- startup and mode-transition gates;
- authored and CUSTOM outer geometry;
- card colors, border, opacity, painted shadow, and fade state;
- edit-shell participation.

When compositor ownership is active, the widget becomes a transparent
coordinator and input/layout shell. It must not retain a painted backing-store
card beneath compositor-owned pixels.

### Context-Agnostic Visualizer Renderer

Owns:

- mode-local state copied from accepted frame packets;
- current shader programs and uniform locations;
- mode reset and first-frame handoff state;
- waveform, ghost, peak, Bubble, and Dev Curve renderer state;
- rounded-card stencil rendering;
- visualizer GL resource cleanup.

The renderer must not require a `QOpenGLWidget`. It renders into whichever
framebuffer the owning surface has made current. A legacy child-widget adapter
may host the same renderer during rollback; the renderer implementation itself
must not be duplicated.

### Display-Owned Visualizer Layer

`GLCompositorWidget` owns one visualizer layer with:

- one renderer instance;
- steady-state front/back card-sized RGBA8 textures and framebuffer objects,
  each with a stencil-only renderbuffer, resized only when logical geometry or
  DPR changes; at most one prior front slot may remain temporarily presentable
  until a resized generation publishes;
- one private texture-composite program that reuses the renderer's
  context-local quad VAO/VBO;
- the latest accepted geometry and visibility state;
- generation-based render reuse so compositor paints do not rerender an
  unchanged accepted packet;
- bounded render-failure diagnostics;
- edit-mode snapshot support;
- exact cleanup before the compositor context is destroyed.

The offscreen FBO preserves the visualizer shaders' existing local
`gl_FragCoord`, logical-resolution, DPR, and stencil assumptions. The final
texture is alpha-composited into the display framebuffer at the authoritative
card rectangle.

### Legacy Adapter

The old child `QOpenGLWidget` is a thin adapter around the same
context-agnostic renderer. It is retained temporarily for:

- the explicit `SRPSS_SINGLE_SURFACE_VISUALIZER=0` rollback gate;
- a deliberately selected non-OpenGL/software display backend;
- a hard compositor-owned composite-program, framebuffer, compositor-error,
  or context-loss failure detected before first reveal.

It is not authorized for a shared renderer/shader failure, missing transient
readiness, an unexpectedly absent normal compositor, or any failure after the
compositor visualizer has become visible. Those are loud defects, not
permission to restore the competing child surface.

`SRPSS_SINGLE_SURFACE_VISUALIZER=0` forces the legacy adapter for controlled
A/B comparison and emergency rollback. The normal path is compositor-owned by
default.

Unexpected normal-path creation or interface failures publish a
display-generation terminal reason. Startup remains hidden and stops its short
readiness retry rather than repeatedly rebuilding or substituting a legacy
surface. A later production call may clear the reason only by successfully
establishing a valid renderer target; otherwise display rebuild is the clean
recovery boundary.

## Paint Order

The display compositor uses this order:

1. Current wallpaper from its resident texture through one fullscreen GL quad,
   or the active transition shader.
2. A conditional QPainter session for dimming when dimming is active.
3. Visualizer card shadow, fill, and border from the cached card texture through
   native premultiplied GL; visible paint never rasterizes or uploads it.
4. Visualizer front-FBO texture through bounded native GL painting in the same
   compositor frame.
5. A conditional QPainter session for PERF/debug HUD or a pre-presentation card
   fallback. If any native card pixels were presented before failure, fallback
   is suppressed so the frame cannot double blend.
7. Ordinary Qt widget siblings and temporary edit shells, composited by Qt
   above the display surface.

The visualizer shader continues to use the rounded-card stencil inset and may
not paint over the centered card border. Card opacity follows the shared
`ShadowFadeProfile`; bar opacity retains its existing delayed GPU fade.
`QPainter` is the first-image safety fallback when a valid resident base texture
does not yet exist, not the steady wallpaper renderer. Paint may look up a
resident texture but may not upload or convert one.

## Frame And Repaint Flow

1. The dedicated visualizer tick produces one accepted reusable frame packet.
2. `DisplayWidget` resolves the authoritative outer card rectangle.
3. The display-owned layer applies state synchronously and replaces its latest
   dirty generation. Revision-tokened static fields are skipped when unchanged;
   worker-owned Dev Curve arrays retain identity through immediate consumption.
4. The display render owner requests at most one Qt presentation handoff. While
   that handoff remains outstanding, producers continue replacing the latched
   generation but the owner does not enqueue another handoff.
5. On the next compositor paint, the layer renders the newest accepted
   generation into its local FBO and blends that texture into the display
   framebuffer.
6. The `paintGL()` exit path acknowledges the display owner even when the paint
   did not authorize transition completion. The owner resumes at that display's
   next normalized deadline, never a catch-up burst.
7. Qt may still coalesce ordinary update requests naturally. The application
   must not producer-throttle accepted packets or source state to improve
   counters.

Animated visualizer modes continue to receive packet-driven repaint requests
at the accepted visualizer cadence. Transition rendering and visualizer
rendering share the compositor presentation request rather than competing
through separate GL widgets.

## Terminal And Teardown Transaction

- `TransitionController` owns one generation and publishes one terminal state
  sequence: terminal shader paint, completion queued, completion applied, and
  display idle. `DisplayWidget`, compositor `FrameState`, resident destination,
  PERF HUD, and image-pipeline completion consume that same sequence.
- A terminal frame may remain on screen while its one post-paint callback is
  queued. During that interval transition admission is closed. Stale/cancelled
  callbacks cannot publish a destination or clear a newer generation.
- Runtime pause first blocks new image/transition admission, invalidates
  deferred generation work, pauses the adaptive render owner, and reconciles
  the terminal transaction into one committed base. A reused display reopens
  compositor/controller/display admission transactionally before the engine
  publishes its next first image.
- Permanent teardown sets the shutdown barrier before requesting adaptive-owner
  retirement. The Qt thread never waits for that worker. Once the barrier is
  set, the worker cannot enqueue Qt work or touch GL; its `finally` path releases
  timer metadata and ResourceManager registration exactly once, then publishes
  the primitive stop acknowledgement. The compositor marks that acknowledgement
  pending before signalling the worker and never writes stale pending state
  after the request returns. `[PERF][ADAPTIVE_TIMER] asynchronous_stop_ack`
  reports request-to-ack `latency_ms`; the parser's `250 ms` anomaly threshold is
  observational and never blocks Qt or authorizes forced retirement. GL cleanup
  may therefore continue on the owning Qt affinity thread without abandoning
  worker ownership.
- Every reusable context/surface records Qt affinity and display generation.
  `makeCurrent()`, `doneCurrent()`, surface destruction, and context deletion
  assert/marshal ownership before Qt is called. Invalid-context abandonment
  updates ResourceManager metadata without pretending native deletion occurred.

## Prepared Images And Shared Textures

1. Decode/prescale workers produce the presentation `QImage` plus an immutable
   contiguous ARGB32 `ImageUploadPayload`; only the UI publication seam creates
   or updates `QPixmap`.
2. The compositor texture manager keys immutable payloads by content identity,
   width, height, stride, and format. With a current verified share group it
   acquires a registry lease; otherwise it uses its bounded context-local cache.
3. The producer uploads once, inserts `glFenceSync`, and flushes. Another
   sharing context issues GPU-side `glWaitSync`; the UI never performs a client
   wait or `glFinish()`.
4. Each manager releases only its lease. The final valid release deletes the
   texture/fence and unregisters metadata once. Context-loss abandonment makes
   no GL calls and cannot mark the entry dead while another manager still owns
   it.
5. Paint is lookup/draw only. Conversion, `QPixmap.toImage()`, upload, and card
   texture creation are forbidden from visible paint.

## Visualizer Compute Handoff

- Bubble and Dev Curve use bounded COMPUTE ownership; Dev Curve is explicitly
  one in flight with an epoch-tagged result slot. A mode/reset boundary advances
  the epoch and rejects an old callback without starting overlapping work.
- The GUI tick snapshots current energy and revision-cached authored settings,
  publishes at most one complete result, and submits at most one next solve. It
  never waits for completion. Published curve arrays are not mutated by the
  next solve and retain identity through synchronous renderer consumption.
- Dev Curve's first compositor frame is withheld until the first valid worker
  result exists. This is a readiness gate, not a timer or reduced-cadence path.
- `[PERF] [SPOTIFY_VIS][DEVCURVE]` records the latest worker cost/backlog in the
  existing bounded diagnostics summary. A worker exceeding one 60 Hz frame is
  parser-visible evidence for vectorized/native GIL-releasing work, not license
  to reduce visualizer quality or cadence.

## Startup And Flicker Prevention

- Shader source preload may happen before a GL context exists.
- The compositor compiles every supported visualizer mode plus the required
  rounded-card mask while its surface is hidden or at zero visualizer opacity.
- A compositor mode program may never be compiled from the visible paint path.
  A missing program remains absent and logs once rather than stalling a frame.
- The explicit legacy adapter retains incremental mode warmup only to keep the
  emergency rollback path bounded.
- The visualizer card and content remain absent until the existing fresh-frame
  and centralized secondary-stage gates allow reveal.
- A zero-fade hidden primer may populate renderer state and FBO resources, but
  it may not expose the card or texture.
- A transient hidden readiness miss keeps compositor ownership and retries
  through existing startup staging; it does not instantiate legacy.
- Terminal compositor, renderer, source-preload, target-creation, or target
  interface state records a diagnostic reason and stops the short reveal retry
  rather than spinning a 16ms loop indefinitely.
- Runtime prepare retries use no timer and no repaint rescue. Actual attempts
  use bounded exponential backoff from 100ms to 2s while ordinary compositor
  paints may reuse the last complete texture.
- Runtime failure retains the last good compositor frame while recovery is
  attempted; it must not blank or expose a different surface.

## Geometry, DPR, And Display Topology

- All public geometry remains logical display-local `QRect`.
- FBO dimensions are `round(logical_size * compositor_dpr)` and at least
  `1x1`.
- FBO reallocation is keyed by logical width, logical height, and effective
  DPR. Position-only changes do not rebuild GPU storage.
- Buffer replacement is transactional. A failed resize/DPR allocation keeps
  the prior complete front/back pair alive. After successful allocation, the
  prior front texture remains retained and scaled to the current logical
  rectangle until the first new-size generation publishes successfully.
- Explicit renderer clear/reset releases any retained pre-resize frame so
  recovery pixels cannot survive a stopped or reset visualizer.
- The final blend rectangle is computed from the current logical compositor
  size, so mixed resolution and mixed DPR displays remain independent.
- Screen changes invalidate cached viewport/FBO sizing and repaint once after
  valid geometry is available.
- CUSTOM replay, settings restart, display recreation, monitor removal, and
  monitor return use the same geometry synchronization seam.
- The visualizer layer does not register with `PixelShiftManager`; it follows
  the already-shifted authoritative card rectangle exactly once.

## CUSTOM Edit Mode

The edit shell must represent the complete current visualizer, not only the
transparent coordinator widget or only the GL texture.

The display-owned layer therefore exposes a bounded snapshot API that:

- paints the current card/shadow into a transparent image;
- reads the card-sized visualizer FBO only on explicit edit capture;
- composites both at the current logical size and DPR;
- performs no recurring readback and no runtime telemetry readback.

Live shell movement and resize continue to update the coordinator widget and
layer geometry. Save remains the only persistence authority. Cancel restores
the pre-session committed rectangle. Reset Visualizer remains a session-local
recovery action.

When a save changes geometry/style under the same display/compositor owner,
the custom-layout classifier applies a partial generation rebuild and retains
the current compositor, resident wallpaper, program cache, and visualizer GL
layer. A monitor-owner, display-topology, backend, or context-format change is
not eligible and follows the full quiesced recreation transaction. The partial
path still owns pointer suppression, authoritative rect replay, per-display
Clock variants, and the normal reveal/no-flicker order.

## Transition Integration

Every compositor transition family routes through the same post-transition
overlay composition step. The visualizer layer must therefore be exercised
with:

- Crossfade;
- Slide;
- Wipe;
- Block Puzzle Flip;
- Block Spin;
- Blinds;
- Diffuse;
- Warp;
- Raindrops;
- Crumble;
- Particle;
- Burn;
- idle/base-image painting;
- loud shader fallback.

Transition state, duration, easing, texture preparation, admission, and
deferral remain unchanged. Completion is now made explicitly paint-authoritative:
paint-time `FrameState` determines visible progress, and only a successfully
rendered terminal transition shader frame may queue the generation-guarded
post-paint completion callback. A not-ready, base-only, idle, or QPainter
fallback paint cannot commit the destination. Cancellation, Settings rebuild,
and teardown invalidate queued completion. A transition that cannot start or
cannot yet render therefore retains the committed frame and defers/retries; it
never skips into a sudden image commit.

## Failure And Rollback Policy

- Explicit rollback or a deliberately non-OpenGL backend may create legacy
  directly and must log the surface reason.
- Before first reveal only, a hard compositor-owned composite-program,
  framebuffer, compositor-error, or context-loss failure may retire the
  hidden layer and create legacy. The parser still reports this as anomaly
  evidence rather than normal success.
- A shared renderer/shader failure is common to both hosts and therefore never
  justifies legacy.
- A transient prewarm/readiness miss keeps compositor ownership and the
  visualizer hidden.
- Render failure after a good compositor frame retains the last-good FBO
  texture, logs bounded diagnostics, and retries only through accepted
  compositor work with bounded prepare backoff.
- A failure before any good frame leaves the visualizer absent rather than
  showing an unmasked, simplified, stale, or lower-fidelity substitute.
- No post-reveal runtime switch to legacy is permitted. Recovery that requires
  a surface change must happen through an explicit display/runtime rebuild.
- The environment rollback gate remains until multi-display runtime validation
  passes and the child adapter is deliberately retired.

## Resource Lifetime

- The compositor visualizer layer is initialized and cleaned in the same
  current context as its owning compositor.
- The steady front/back FBOs, textures, stencil renderbuffers, any temporarily
  retained prior front slot, the composite program, renderer VAO/VBO,
  visualizer programs, and stencil program are released exactly once.
- Context-local handles are never reused across displays.
- ResourceManager registrations use compositor-layer descriptions rather than
  retaining misleading child-overlay ownership labels.
- Invalid-context teardown abandons registrations without attempting unsafe GL
  deletion, matching existing compositor lifecycle policy.
- No timer, worker, audio engine, or accepted packet is owned by the layer.

## Instrumentation

The compositor path retains bounded `--perf` delivery attribution:

- accepted packet count;
- compositor update request count;
- visualizer render count;
- card FBO resize count;
- unchanged-generation texture reuse count;
- last-good-frame retention count;
- compositor render-failure count;
- accepted-update-to-compositor-paint wait by transition context;
- compositor paint gap by transition context;
- adaptive-owner paint-wait count/time/timeout and pending-skip counts;
- fixed ten-second idle/transition GL and QPainter fallback paint-path counts,
  duration averages, and maxima.

Instrumentation adds no GL query, framebuffer readback, timer, retry loop,
packet allocation, or repaint. The health parser must distinguish legacy and
single-surface samples during A/B runs.

## Implementation Phases

### Phase A: Renderer Extraction - Implemented

- `SpotifyVisualizerGLRenderer` is independent of a widget host.
- `SpotifyBarsGLOverlay` is a thin legacy adapter over that renderer.
- Shared state, shader, stencil, diagnostics, and cleanup behavior are not
  duplicated.

### Phase B: Compositor Layer - Implemented

- Double-buffered card FBO allocation, local shader rendering, and alpha
  texture blend are compositor-owned.
- Existing card-paint, stencil, fade, and frame-packet contracts are reused.
- Cleanup, last-good retention, transactional resize, and bounded failure
  state are covered by focused automation.

### Phase C: Runtime Routing - Implemented

- Compositor ownership is the default normal path.
- Prewarm, frame push, clear, reset, diagnostics, geometry, visibility, and
  teardown route through one renderer-target interface.
- Legacy creation follows the strict decision tree above.

### Phase D: CUSTOM And Lifecycle - Implemented

- Explicit compositor snapshot capture replaces the child-framebuffer
  assumption for the normal path while preserving legacy capture compatibility.
- Automated CUSTOM, display rebuild, geometry, cleanup, and exactly-once
  lifecycle bars are green.

### Phase E: Packaged Runtime Promotion - Candidate Rebuilt, Runtime Gate Open

- Automated parity and first packaged functional parity are complete.
- The first packaged performance matrix did not provide meaningful,
  repeatable ordinary-background headroom and therefore failed promotion.
- The rebuilt candidate now includes one terminal transaction, owner quiesce
  and GL affinity assertions, immutable upload payloads, share-group texture
  leases, native static visualizer card composition, same-owner CUSTOM partial
  rebuild, and worker-owned Dev Curve generation. Focused reactivity,
  single-surface, broader ownership, and the combined `688`-test changed-surface
  integration suite are green; packaged runtime promotion remains pending.
- Repeat the same scenarios after each named pressure correction; compare
  ordinary, post-reboot, settings/rebuild, long-idle, and deliberately
  externally saturated evidence separately.
- Promote only with material CPU-distribution, paint-gap, visualizer-wait,
  high-refresh delivery, and `dt_max` improvement while preserving accepted
  pixels, cadence, smoothing, reactivity, and transition behavior.
- The legacy adapter is diagnostic rollback only. It may not hide a runtime
  promotion failure or become the steady normal path.

## Acceptance Matrix

Automated and runtime validation must cover:

- every supported visualizer mode, curated preset, and Custom settings;
- playing, paused, unavailable audio, and playback-state changes;
- cold startup, settings return, mode hot-swap, preset hot-swap, and teardown;
- all compositor transition families and idle painting;
- one, two, and reduced-topology display lifetimes;
- mixed refresh such as `165/60 Hz`;
- representative `100%`, `125%`, `150%`, and `200%` DPR;
- landscape, portrait, and mixed resolutions;
- authored layout and CUSTOM move/resize/save/cancel/reset;
- interaction mode and edit shell input;
- pixel shift on and off;
- dimming on and off;
- painted frame shadow on and off;
- environment-forced legacy rollback;
- no legacy surface in a healthy normal compositor run;
- no visible-path visualizer shader compilation;
- steady idle `[GL PAINT PATH]` is `idle_gl`; one first-image QPainter fallback
  is tolerable, three or at least 5% of a ten-second idle window is failure, and
  any transition QPainter fallback is failure evidence;
- render-owner wakeups converge near accepted handoffs, intentional paint waits
  replace pending-skip amplification, and ordinary `paint_wait_timeouts` remain
  zero;
- terminal completion follows one successful terminal shader paint and never a
  fallback/not-ready/base-only paint;
- no FBO resize churn after warmup except real size/DPR changes;
- zero compositor visualizer render failures in a healthy run;
- FBO renders following accepted generations while texture reuse grows across
  higher-frequency compositor paints;
- no visualizer safeguards, transition skips, request drops, repaint rescues,
  shader/swap/cache fallbacks, or GL lifecycle errors.

Automated checks are necessary but not sufficient. Final visual, startup,
mixed-refresh, and multi-display acceptance requires a packaged Windows
runtime.
