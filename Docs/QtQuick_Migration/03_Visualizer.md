# 03 — Visualizer Qt Quick Migration

Status: ACTIVE Phase-D technical decomposition  
Last updated: 2026-08-22

Cross-links:

- sequence/permission: `Current_Plan.md`
- presentation guardrail: `Docs/Guardrails/Visualizer_Presentation.md`
- Bubble temporal fidelity: `Docs/Guardrails/Bubble_Temporal_Fidelity.md`
- authored behavior/reference: `Docs/Visualizer_Reference.md`
- CUSTOM/input implementation: `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`
- harness routing: `Docs/Harness_Index.md`
- historical painted-card bleed: `Docs/Historical_Bugs/R-21_Visualizer_Painted_Card_GL_Boundary.md`
- deferred deletion: `Future_Cleanup.md`

Phase D may proceed while Phase-C physical/eyes-on sign-off remains explicitly deferred. A later
failing transition sign-off reopens only the smallest demonstrated Phase-C defect; it does not suspend
unrelated Phase-D work by default.

## 1. Preserve the part that already works

Keep `VisualizerLogicalRuntime`.

It remains:

- the sole mode-general authored visualizer clock;
- independent of GUI/render cadence;
- latest-state oriented;
- generation-owned;
- no catch-up;
- BTF-bound for Bubble.

Do not move logical simulation into:

- QML;
- QSG render thread;
- `FrameAnimation`;
- physical refresh;
- a second mode-specific timer.

Every authored logical step must still occur even when fewer physical frames are presented.

## 2. Current presentation seam that must change

The old compositor presentation can hold a `VisualizerRenderState` whose handle references the live
visualizer owner and mutable/heavy arrays. That was only acceptable while publication and paint were
GUI-thread owned.

It is not a legal Quick render-thread contract.

The Quick render node must not read a live `SpotifyVisualizerWidget`, arbitrary QObject presentation
state, provider objects, or SettingsManager.

The old visualizer also assumes every current mode is inside one painted card and uses a dedicated
rounded stencil to prevent GL pixels escaping through the frame/corners. Preserve the visual result,
not the old ownership assumptions.

The old runtime also owns per-mode card-height/growth controls (`spectrum_growth`, `osc_growth`,
`sine_wave_growth`, `bubble_growth`, `devcurve_growth`). They are legacy presentation customization,
not authored mode behavior, and are deliberately **not** carried into the Quick visualizer contract.

## 3. D1 — presentation-neutral runtime/controller owner

Do not instantiate a hidden QWidget merely to retain:

- playback state;
- presets/settings;
- BeatEngine/source ownership;
- logical runtime;
- mode state;
- CUSTOM identity.

Extract/retain a presentation-neutral owner, conceptually:

```text
VisualizerRuntimeController
    settings/mode/preset activation
    BeatEngine/source ownership
    playback-edge ownership
    VisualizerLogicalRuntime
    latest logical publication

QuickVisualizerPresentation
    immutable snapshot admission
    presentation policy
    geometry/fade/readiness
    optional retained shell chrome
    QSGRenderNode visual content
```

Keep source/provider/business logic in Python. Do not rewrite it into QML.

### 3.1 Mode presentation policy

Extend the existing cheap visualizer mode descriptor with small presentation metadata.

Conceptual shape:

```text
VisualizerModePresentationPolicy
    shell_policy
    clip_policy
    viewport_resize_capable
```

Initial values:

```text
current five modes:
    shell_policy = CARD
    clip_policy  = CARD_INTERIOR

future explicitly frameless mode:
    shell_policy = FRAMELESS
    clip_policy  = VIEWPORT_RECT
```

Do not build a giant mode schema or external plugin SDK.

The point is to prevent `QuickSceneController`/render host from containing a permanent
`if mode == future_blob: don't_draw_card()` special case.

`FRAMELESS` means no visualizer card background, border/frame, or card shadow. It does not create a
new window or presentation surface.

Checkpoint and push the controller/runtime/policy split before renderer complexity.

## 4. D2 — immutable latest snapshot

Define a bounded render-thread-safe snapshot containing only data needed to draw the committed
visualizer state.

Representative fields:

```text
runtime_generation
activation_id
mode
playing
logical_timestamp
fade

presentation:
    shell_policy
    clip_policy
    outer_rect
    content_rect
    dpr
    uniform_visual_scale
    content_viewport_size
    aspect_ratio

common:
    energy bands
    color/style parameters

Spectrum:
    bars / peaks / ghost state

Oscilloscope:
    waveform geometry/state

Sine:
    sine layer state

Bubble:
    positions
    radii/extra data
    trails/tails
    pop/transient/protected-edge state
    ghost state
    authored style

DevCurve:
    enabled layers
    order
    offsets
    alpha
    outline/ghost state
```

Use existing logical state where possible. Do not deep-copy QWidget object graphs.

Use tuples, immutable records, owned numpy buffers, or another explicitly proven immutable payload
shape.

One latest slot per activation/display presentation. Newer committed state supersedes older unread
state; there is no render backlog.

The render thread must not query the mutable mode registry to discover shell/clip policy. Resolve it
before snapshot admission.

Checkpoint and push the immutable bridge separately.

## 5. Synchronization and publication

Preferred seam:

```text
logical publication
    -> latest immutable snapshot
    -> GUI/Quick item marks visual state dirty
    -> updatePaintNode/synchronization boundary
    -> render node receives complete current snapshot
```

The exact PySide seam may vary with the landed Quick item, but the ownership rules may not:

- no render-thread lock waiting on provider/network/GUI work;
- no one-GUI-callback-per-logical-tick requirement;
- latest state wins;
- no FIFO/catch-up replay;
- short-lived authored edges are protected explicitly rather than lost through decimation;
- no paint acknowledgement feeding logical cadence.

## 6. Quick visualizer scene shape

Use one sub-rect custom `QQuickItem`/`QSGRenderNode` inside the owning display `QQuickWindow`.

The visualizer remains inline in the same scene as retained chrome and widgets. No separate native
window and no QPainter fallback.

The render node owns its context-local GL programs/resources.

Selected visual layering:

```text
VisualizerPresentationRoot
    |
    +-- card shadow          [CARD only]
    +-- card background      [CARD only]
    +-- content Quick item
    |       |
    |       +-- QSGRenderNode / direct GL
    |               |
    |               +-- one local SDF/stencil clip host
    +-- frame/border         [CARD only, above content]
```

The root owns final fade/visibility for both carded and frameless modes.

Reuse authored assets/helpers where valid:

- current mode shader sources;
- shared vertex shader/math;
- uniform upload helpers after removing old compositor coupling;
- Bubble logical/output data format and authored math.

Do not use an offscreen QWidget/card screenshot as the final presentation path.

## 7. Clip ownership — preserve the mask contract, improve the owner

### 7.1 Why clipping is still required

Historical R-21 established the real visual contract:

```text
visualizer content
    above card fill
    below border/frame
    unable to escape rounded corners
```

Shrinking the renderer/card rect to hide bleed was incorrect because it changed authored content
geometry, bar widths, amplitudes and curve scale.

That remains true in Quick.

A plain `QQuickItem.clip = true` is only a rectangular item-bounds clip. It does not by itself express
the rounded inner card path.

### 7.2 Scene-graph clip proof result

The exact pinned PySide 6.9.1 `QSGClipNode -> QSGRenderNode` proof is complete and failed its runtime
bar. Rounded cases reported stencil state whose target-buffer contents did not match, while
rectangular cases could report an invalid sentinel scissor. A live Python render node therefore
could not safely consume that clip handoff.

Do not retain or retry that path alongside the selected implementation.

### 7.3 Selected render-node-local clip

Keep the same policy/geometry architecture and use one render-node-local rounded SDF/stencil host. It:

- stays inside the same QQuickWindow/QSGRenderNode architecture;
- derives from the canonical content geometry;
- uses the exact render-target viewport shared by the mode draw;
- respects any incoming scene clip;
- nests temporary stencil contents without clearing the framebuffer;
- restores stencil contents plus scissor/direct-GL state;
- never shrinks or anisotropically scales authored content to simulate clipping.

`VIEWPORT_RECT` uses the same host with zero radius. Do not keep both clipping implementations as
permanent selectable paths.

### 7.4 Do not copy the old mask constants

The old path needed a special inset because the QPainter border was a **centred** pen stroke.

Qt Quick `Rectangle` borders are rendered **inside** the rectangle bounds.

Therefore derive the Quick card clip from the actual retained chrome:

```text
outer card path
    minus inside border width
    -> inner content path
```

and derive inner corner radius from that same style geometry.

Do not blindly preserve the old `1px + border_width/2` calculation.

If the new retained card intentionally has an additional content inset, make it an explicit style
value owned by the Quick card contract.

## 8. One authoritative geometry contract

Create one committed presentation-neutral geometry structure feeding retained Quick chrome, clipping and
custom GL.

It must account for:

```text
outer_rect
content_rect
dpr
baseline_viewport_size
baseline_aspect_ratio
uniform_visual_scale
viewport_extent
current_aspect_ratio
framebuffer/Quick-item transform data
CUSTOM edit geometry
shell_policy
clip_policy
```

Card and GL content remain aligned at non-zero display origins and non-1 DPR.

No hidden QWidget remains geometry authority. No visualizer-local stale DPR copy.

### 8.1 One canonical baseline aspect for every current mode

Quick removes the old mode-driven preferred-height model.

The current code's mode-growth family changes preferred height while width remains common/media-relative;
CUSTOM already bypasses that preferred-height path once committed custom geometry owns the visualizer.
That legacy behavior is unwanted in the destination.

For all five current Quick modes:

```text
one canonical baseline viewport size/aspect
        ↓
mode changes do not change outer viewport shape
        ↓
mode presets do not own viewport/card height
```

Do not copy `DEFAULT_GROWTH`, `preferred_height()`, `_apply_preferred_height()`, or the five `*_growth`
settings into the Quick runtime/controller/snapshot.

Do not guess the numeric ratio from one old growth slider. During the D3/D4 geometry checkpoint,
extract/freeze one named canonical baseline aspect from the intended healthy CUSTOM/default visualizer
baseline and prove it is mode-invariant.

If normal placement derives width from another common layout owner such as Media, derive height from the
canonical aspect. If screen bounds force reduction, reduce uniformly so the baseline aspect survives.

### 8.2 Whole-size scale preserves the canonical aspect

Keep one `uniform_visual_scale`.

Scroll resize and corner resize both change this scale. They enlarge/shrink the entire visualizer and
preserve the canonical baseline aspect.

They do not stretch X and Y independently.

### 8.3 Viewport extent is deliberately separate

Keep a separate `viewport_extent`/content viewport size.

Only the explicit Phase-G edge-resize operation changes one viewport axis independently:

```text
left/right edge -> viewport width
 top/bottom edge -> viewport height
```

At constant visual scale this gives a mode more/less world to occupy. It may intentionally create a
wide/tall aspect different from the baseline.

That deliberate operation must not be confused with the retired `*_growth` controls.

### 8.4 Logical modes that depend on spatial bounds

If a logical simulation needs viewport dimensions (Bubble especially), publish a presentation-neutral
`VisualizerViewportMetrics`/equivalent update when committed geometry changes.

This is configuration/geometry input, **not a clock**. It may alter simulation bounds/aspect; it may
not make the render thread advance simulation or introduce a resize-driven logical timer.

## 9. Card chrome, frameless shell and fades

### 9.1 Current modes

All five current modes remain carded and must preserve:

- background opacity;
- border/radius;
- card shadow;
- card/foreground opacity;
- current color/customization;
- geometry;
- fade behavior.

### 9.2 Future explicitly frameless modes

Architecture must allow a future mode to declare `FRAMELESS`.

For that mode:

- no card fill;
- no card border/frame;
- no card shadow;
- same presentation root/lifecycle/fade;
- custom GL remains inside the assigned transparent viewport;
- default clip is `VIEWPORT_RECT`.

This is intended for effects such as a true 3D deformable sphere where drawing a rectangular card
around the object would be visually undesirable.

Do not retrofit frameless behavior onto the current five modes during migration.

### 9.3 Readiness

Keep separate:

```text
presentation_ready
reactive_source_ready
```

For `CARD`, presentation readiness includes required retained shell/chrome and render resources.

For `FRAMELESS`, readiness must not wait for card resources that the mode deliberately does not own.

Paused Spectrum may reveal presentation-owned idle state while source identity remains absent.

Prefer one parent/presentation opacity authority for fade. Do not animate by repeatedly enabling or
disabling clip/shadow topology.

## 10. Baseline-aspect and future viewport-extent compatibility

During Phase D, every current mode must render correctly using the same canonical baseline aspect at
more than one uniform scale.

Also exercise controlled wide/tall viewport extents so the renderer is not secretly hard-coded to one
card shape. Those wide/tall cases prepare Phase G; they do not make freeform edge-resize a Phase-D
shipping requirement.

Expected semantics at constant visual scale:

### Spectrum

- bar distribution/layout recomputes from viewport width;
- maximum vertical extent follows content height;
- no stretched pre-rendered Spectrum image.

### Bubble

- spatial domain/aspect changes;
- circles remain circles;
- radii, velocity units, trajectories and BTF stay coherent;
- no arbitrary X/Y scaling to fill a rectangle.

### Oscilloscope / Sine / DevCurve

- horizontal domain/layout and available vertical space adapt;
- authored stroke thickness and uniform scale remain stable.

### Future 3D sphere

- camera/projection uses current viewport aspect;
- the sphere remains round in wide/tall viewports.

If a current mode cannot support free viewport extent without substantial retuning, mark it
`viewport_resize_capable = false` for Phase G and preserve ordinary whole-size scale. Do not compromise
migration fidelity to force this optional QoL.

## 11. Sole authored-clock guardrail

`VisualizerLogicalRuntime` remains the only authored mode-general logical clock.

Non-negotiable:

- preserve every authored logical step;
- latest-state semantics;
- no FIFO/catch-up replay;
- no paint acknowledgement;
- no producer/display divisor;
- no source/event decimation;
- no display-refresh logical cap;
- render cadence does not become simulation cadence;
- nonblocking media/GSMTC interaction;
- generation fencing/stale rejection;
- clean worker join.

A display may present fewer samples than the logical runtime authors. That does not authorize dropping
logical updates before the latest-state publication boundary.

## 12. Spectrum contract

Preserve:

- current bar/peak behavior;
- ghosting/persistence;
- borders/masks/style;
- paused idle bars perceptibly visible;
- source identity absent until a real source is available;
- Play replacing idle state in place rather than recreating presentation ownership.

No mode-specific presentation clock.

The renderer must consume dynamic viewport geometry instead of assuming the historical fixed card
width/height forever.

## 13. Oscilloscope contract

Preserve authored waveform shape, line count/persistence/ghosting, idle behavior, borders/masks/style,
and current logical cadence. The old `osc_growth` card-height control is not part of this contract.

Do not turn physical render cadence into waveform sampling cadence.

Consume current viewport geometry without post-render anisotropic stretching.

## 14. Sine contract

Preserve authored idle motion, layers/line persistence, reactive behavior, ghosting, and mode tuning. The old `sine_wave_growth` card-height control is not part of this contract.

No separate Sine timer is introduced because Quick can animate.

Consume current viewport geometry without changing the authored clock or stretching line pixels.

## 15. Bubble contract — dedicated high-risk checkpoint

Bubble is the highest-risk Phase-D mode and receives its own checkpoint/audit.

`Docs/Guardrails/Bubble_Temporal_Fidelity.md` is mandatory.

Preserve:

- continuous positional evolution;
- trajectories;
- collision/elastic feel;
- trails/tails;
- ghost/pop/transients;
- protected short-lived edges;
- source freshness;
- authored logical Hz;
- mode style and reactive personality.

Do not retune Bubble to compensate for presentation problems. Do not discard authored logical steps
to reduce callbacks/GPU use.

If viewport dimensions later change, change the Bubble spatial domain through presentation-neutral
viewport metrics; preserve isotropic circle geometry and authored motion units.

The existing observation that unrelated active widgets can materially alter measured Bubble-era GPU
load is reason to preserve true feature dormancy and shared-scene efficiency; it is not evidence that
Bubble collision/simulation should be individually simplified.

## 16. DevCurve contract

Preserve every active layer's:

- enabled state;
- order;
- alpha;
- offsets;
- outline;
- ghosting;
- tuning.

Do not flatten DevCurve into a generic line visualizer during porting.

Consume viewport geometry explicitly rather than relying on hidden QWidget/card dimensions.

## 17. Pause / Play

Ordinary Pause/Play keeps the same runtime ownership:

- no window/item recreation;
- no source debounce invented by Quick;
- warm-source policy preserved;
- visible state changes promptly;
- existing expected-state confirmation behavior preserved;
- Quick visibility/activation is not a second playback authority.

Shell policy does not become playback authority.

## 18. CUSTOM participation

The visualizer becomes an ordinary participant in the later Quick edit scene.

During Phase D:

- keep the presentation-neutral scale/viewport geometry seam suitable for Phase G;
- do not implement the Phase-G resize handles prematurely;
- do not persist a second QML-only geometry model.

Final edit behavior will use the real retained Quick item, not a QWidget screenshot shell.

## 19. Lifecycle

Retirement order conceptually:

```text
close visualizer publication
-> stop/join VisualizerLogicalRuntime
-> invalidate activation/generation
-> Quick item loses snapshot admission
-> render-node GL resources destroy on render owner
-> clip/shell nodes retire
-> item/controller roots destroy
```

Visibility is not destruction authority.

No non-daemon/background owner may survive retirement and prevent process/test shutdown.

## 20. Permanent tests/gates

Permanent contract coverage should include:

- sole logical clock;
- generation 0;
- all five modes;
- source freshness;
- protected edges;
- BTF;
- Pause/Play;
- Spectrum idle;
- mode switches;
- stale activation/generation rejection;
- logical runtime join.

Quick-specific coverage should include:

- distinct render-thread ownership;
- immutable snapshot boundary;
- no live QWidget/QObject reads from renderer;
- non-zero origin/non-1 DPR geometry;
- card/shader alignment;
- `CARD` shell and rounded inner clip alignment;
- `FRAMELESS` policy unit/scene proof without requiring a production frameless mode;
- render node honoring incoming scene-graph scissor/stencil clip state;
- no old QPainter border-mask constants copied into Quick geometry;
- one canonical baseline aspect shared by all five modes;
- Quick snapshots/renderers contain no `spectrum_growth` / `osc_growth` / `sine_wave_growth` / `bubble_growth` / `devcurve_growth` geometry authority;
- corner + scroll resize preserve baseline aspect;
- default/wide/tall viewport geometry for each current mode;
- no anisotropic Bubble/sphere-like geometry distortion;
- render resource creation/release;
- Settings recreation where presentation state is involved;
- physical cadence/eyes-on only on suitable hardware.

Run deterministic Phase-D tests in the capable Windows worktree and Quick/OpenGL/physical-display gates
only in the environment appropriate to those claims.

Do not substitute a broad unrelated suite result for focused Phase-D evidence.

## 21. Checkpoint cadence

Prefer these pushed/audited checkpoints:

1. presentation-neutral runtime/controller + mode presentation-policy split;
2. immutable latest-state snapshot bridge;
3. Quick visualizer item/node + clip/shell/authoritative geometry foundation;
4. Spectrum;
5. Oscilloscope;
6. Sine;
7. Bubble + BTF dedicated checkpoint;
8. DevCurve;
9. all-five-mode lifecycle/source/pause + non-default-aspect audit;
10. Phase-D documentation closure.

A successful audit-required checkpoint is committed, pushed, then independently diff-audited before
continuation.

## 22. Phase-D exit

Phase D implementation exits when all five current modes use the Quick visualizer boundary with:

- authored logical runtime intact;
- immutable latest-state publication;
- correct lifecycle/resources;
- `CARD + CARD_INTERIOR` fidelity;
- no old compositor/QWidget presentation dependency inside the new renderer;
- no architectural assumption that every future visualizer must draw a card;
- a geometry contract that cleanly separates scale from viewport extent.

Phase D does **not** need to ship freeform edit-mode viewport resizing.

Physical/eyes-on acceptance may be tracked separately where evidence requires the operator's actual
display/GPU environment, but all unresolved items must be explicit before promotion to Phase E.

After Phase D implementation closure, update `Docs/Visualizer_Reference.md` and related
authoring/preset guidance to the landed Quick boundary.
