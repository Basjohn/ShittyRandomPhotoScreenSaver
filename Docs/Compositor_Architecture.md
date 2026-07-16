# Compositor Architecture

Last updated: 2026-07-16

This document defines the implemented rendering architecture for fullscreen
SRPSS displays and the remaining runtime-promotion contract for the
single-surface compositor overhaul.

## Objective

Each active display owns one realized `QOpenGLWidget`, one current GL context,
and one render scheduler. Wallpaper presentation, shader transitions, dimming,
and GPU visualizer content are composed through that display-owned surface.
Ordinary Qt widgets and temporary CUSTOM edit shells remain separate Qt
widgets above the compositor.

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
for a hard compositor-layer failure. Automated parity is implemented; packaged
mixed-display runtime promotion remains open.

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

1. Current wallpaper or active transition shader.
2. One post-image QPainter scene session.
3. Dimming overlay inside that session.
4. Visualizer card shadow, fill, and border through the existing card-paint
   contract.
5. Visualizer front-FBO texture through bounded native GL painting inside the
   same compositor frame.
6. PERF/debug HUD.
7. Ordinary Qt widget siblings and temporary edit shells, composited by Qt
   above the display surface.

The visualizer shader continues to use the rounded-card stencil inset and may
not paint over the centered card border. Card opacity follows the shared
`ShadowFadeProfile`; bar opacity retains its existing delayed GPU fade.

## Frame And Repaint Flow

1. The dedicated visualizer tick produces one accepted reusable frame packet.
2. `DisplayWidget` resolves the authoritative outer card rectangle.
3. The display-owned layer copies/clamps state synchronously.
4. The layer requests one compositor update. It does not run another timer,
   queue a mutable packet, or self-schedule from paint.
5. On the next compositor paint, the layer renders into its local FBO and
   blends that texture into the display framebuffer.
6. Qt may coalesce update requests naturally. The application must not
   producer-throttle accepted packets to improve counters.

Animated visualizer modes continue to receive packet-driven repaint requests
at the accepted visualizer cadence. Transition rendering and visualizer
rendering share the compositor presentation request rather than competing
through separate GL widgets.

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

The overhaul does not alter transition state, duration, easing, texture
preparation, admission, deferral, or completion. A transition that cannot
start still defers before visible progress; it never skips into a sudden image
commit because visualizer composition is busy.

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
- compositor paint gap by transition context.

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

### Phase E: Packaged Runtime Promotion - Open

- Automated parity is complete; packaged runtime A/B remains required.
- Compare ordinary and externally saturated evidence separately.
- Promote only with meaningful paint-gap, update-wait, CPU, and `dt_max`
  headroom while preserving accepted pixels and cadence.
- Retire the legacy adapter only after the rollback gate has served a stable
  bake period.

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
- no FBO resize churn after warmup except real size/DPR changes;
- zero compositor visualizer render failures in a healthy run;
- FBO renders following accepted generations while texture reuse grows across
  higher-frequency compositor paints;
- no visualizer safeguards, transition skips, request drops, repaint rescues,
  shader/swap/cache fallbacks, or GL lifecycle errors.

Automated checks are necessary but not sufficient. Final visual, startup,
mixed-refresh, and multi-display acceptance requires a packaged Windows
runtime.
