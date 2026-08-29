# 03 — Visualizer Qt Quick Migration

Last updated: 2026-08-29

Cross-links:

- current sequence/permission: `Current_Plan.md`
- presentation guardrail: `Docs/Guardrails/Visualizer_Presentation.md`
- Bubble temporal fidelity: `Docs/Guardrails/Bubble_Temporal_Fidelity.md`
- authored behavior/reference: `Docs/Visualizer_Reference.md`
- CUSTOM/input implementation: `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`
- harness routing: `Docs/Harness_Index.md`
- historical painted-card bleed: `Docs/Historical_Bugs/R-21_Visualizer_Painted_Card_GL_Boundary.md`
- deferred deletion: `Future_Cleanup.md`

Phase D is **complete** and its render/logical architecture remains closed. This file is the durable visualizer
logical/render/geometry contract; `Current_Plan.md` owns live migration status and phase sequencing. Later ownership/cutover
work may finish removing migration scaffolding without reopening D1–D9.

Installed Bubble cadence, eyes-on parity and mixed-refresh checks remain physical acceptance concerns. They are not permission
to change authored behavior or weaken deterministic contracts.

## 1. Preserved authored-time owner

`VisualizerLogicalRuntime` remains:

- the sole mode-general authored visualizer clock;
- independent of GUI/render cadence;
- latest-state oriented;
- generation-owned;
- no catch-up;
- BTF-bound for Bubble.

Logical simulation does **not** move into:

- QML;
- the QSG render thread;
- `FrameAnimation`;
- physical refresh;
- a second mode-specific timer.

Every authored logical step integrates even when fewer physical frames are ultimately presented.
Presentation may sample the freshest completed state; it may not redefine authored time.

## 2. Landed presentation-neutral ownership split

The old compositor could carry `VisualizerRenderState` whose handle referred back to the live
visualizer owner and mutable/heavy arrays. That is not a legal Quick render-thread contract and is not
the Phase-D destination.

The landed shape is conceptually:

```text
VisualizerRuntimeController
    settings/mode/preset activation identity
    BeatEngine/source ownership
    playback-edge ownership
    controller-owned VisualizerLogicalTickState
    sole VisualizerLogicalRuntime
    mode-owned logical frame runtime
    latest logical publication

Quick visualizer presentation
    one GUI/Quick synchronization owner
    latest logical mailbox take/coalescing
    generation/engine-generation/activation/mode fencing
    resolved presentation policy + geometry/fade/readiness/style
    complete VisualizerRenderSnapshot publication into existing bridge
    optional retained shell chrome
    QSGRenderNode visual content
```

No hidden QWidget is required to retain logical/source ownership. The authored logical step advances against the
controller-owned logical state rather than a live `SpotifyVisualizerWidget`.

Configuration follows the same ownership split, but **the owning consumer decides the boundary**. Canonical
settings/activation resolution must feed presentation-neutral resolved configuration for every value consumed by authored
logical evolution or a mode-owned logical frame runtime across Spectrum, Oscilloscope, Sine, Bubble and DevCurve. Pure
renderer/style/chrome values stay on the presentation side. Do not classify a value by where it lived on
`SpotifyVisualizerWidget` or by the Settings subsection that produced it.

The canonical resolved technical cache therefore has multiple legitimate consumers:

```text
DSP/capture technical values
-> controller-owned shared BeatEngine / audio-worker boundary

technical-origin authored-logical values
-> controller-owned VisualizerLogicalTickState

presentation-only style/chrome
-> VisualizerPresentationState / resolved presentation
```

Bar-count reconfiguration must update controller authority, the shared engine through its existing generation/reconfigure
contract, and the controller-owned logical display-bar mirror/freshness state together. Legacy overlay-only technical mirrors
do not get recreated in Quick without an exact destination consumer. This split does **not** create another settings resolver,
engine, controller or cadence owner.

The Quick render node does not read a live `SpotifyVisualizerWidget`, arbitrary QObject presentation
state, provider objects or `SettingsManager`.

Provider/source/business logic remains Python-owned; the migration changed the presentation boundary,
not the application into a QML business-logic rewrite.

## 3. Landed presentation policy

The cheap canonical visualizer mode descriptor may carry small presentation metadata:

```text
VisualizerModePresentationPolicy
    shell_policy
    clip_policy
    viewport_resize_capable
```

All five current production modes use:

```text
shell_policy = CARD
clip_policy  = CARD_INTERIOR
```

A future explicitly authored mode may use:

```text
shell_policy = FRAMELESS
clip_policy  = VIEWPORT_RECT
```

`FRAMELESS` means no visualizer card background, frame/border or card shadow. It does not create a
second window, a second accelerated surface, another logical clock or display-global drawing authority.

This policy exists so scene/controller code does not accumulate mode-specific special cases such as
`if mode == future_blob: do_not_draw_card()`.

## 4. Immutable latest-state bridge

Phase D landed a bounded immutable render boundary. Representative committed state includes:

```text
runtime_generation
engine_generation / activation identity
mode
playing
logical timestamp

presentation:
    shell_policy
    clip_policy
    outer_rect
    content_rect
    dpr
    baseline viewport/aspect
    uniform_visual_scale
    viewport_extent
    current aspect
    derived fade values

mode-specific renderer-visible state:
    Spectrum bars / peaks / ghosts
    Oscilloscope waveform / ghosts
    Sine layers / ghosts
    Bubble positions / radii / extras / trails / pop/transient consequences
    DevCurve layer curves / order / ghosts / specular/tuning state
```

The exact records are source-owned. The durable rules are:

- render-thread state is detached/immutable;
- current generation + engine generation + activation/mode identity fence admission;
- one latest slot, not a render backlog;
- newer committed state may supersede older unread state;
- no producer wait for paint/present;
- no paint acknowledgement;
- no FIFO/catch-up replay;
- no requirement for one GUI callback per logical tick.

Short-lived authored consequences must survive coalescing semantically. For Bubble, the current
same-kind protected-result design is valid only while each protected renderer-visible consequence is
forward-carried into the next result. `Docs/Guardrails/Bubble_Temporal_Fidelity.md` owns that invariant.
If a future Bubble consequence becomes genuinely single-frame-only and is not forward-carried, revise
the coalescing rule rather than weakening the BTF test.

## 5. Synchronization boundary

The durable destination flow is:

```text
source / engine
    -> sole VisualizerLogicalRuntime
    -> mode-owned logical frame runtime
    -> immutable latest logical publication
    -> GUI/Quick synchronization owner
        -> take/coalesce freshest logical publication
        -> resolve current presentation state
        -> compose VisualizerRenderSnapshot
        -> publish existing VisualizerSnapshotBridge
    -> Quick take-for-render
    -> one QSGRenderNode / lazy mode renderer
    -> render-node-local SDF/stencil clip
    -> retained Quick shell/chrome
    -> owning display's standalone QQuickWindow
```

The individual logical, bridge and render components may be landed before production cutover; the chain is **not complete**
until the synchronization owner actually composes and publishes a current snapshot **and the retained visualizer item admits
it for the exact identity**. Merely binding the bridge object to the Quick scene, or calling the bridge's take method directly
from a test, is not destination proof. The resolved presentation used for snapshot composition is committed to the retained
item at the same synchronization boundary rather than independently re-resolved.

The synchronization boundary may mark visual state dirty and transfer a complete current snapshot. It
may not:

- wait on provider/network/GUI work from the render thread;
- turn coalescing into source/event decimation;
- hold logical producer admission until paint;
- build an unbounded queue;
- allow stale generation state into a replacement scene.

## 6. Quick scene shape

The visualizer is one sub-rect custom Quick item/render node inside the owning display
`QQuickWindow`.

Selected layering:

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

No separate native visualizer window. No QPainter presentation fallback. No `QQuickWidget`.

Context-local GL programs/resources are owned by the legal render owner and retire there.

Authored shader/math assets may be reused when they are genuinely presentation-neutral. Old compositor
ownership is not preserved merely because an asset originated there.

## 7. Clip ownership

### 7.1 Visual contract

Historical R-21 established the real requirement for carded modes:

```text
visualizer content
    above card fill
    below border/frame
    unable to escape rounded corners
```

Shrinking the renderer/card rect to hide bleed is incorrect because it changes authored content
geometry, bar widths, amplitudes and curve scale.

A plain rectangular `QQuickItem.clip` does not by itself express the rounded inner card path required
here.

### 7.2 Failed QSGClipNode handoff

The exact pinned PySide 6.9.1 `QSGClipNode -> QSGRenderNode` proof failed its runtime bar:

- rounded cases could expose stencil metadata whose claimed target state did not match framebuffer
  contents;
- rectangular cases could expose an invalid/sentinel scissor.

That handoff is not a selectable production implementation and is not retained as a fallback. Do not
reopen it merely because historical planning described it as preferable before the proof ran.

### 7.3 Selected local SDF/stencil host

The selected implementation is one render-node-local SDF/stencil host inside the same
`QQuickWindow`/`QSGRenderNode` architecture.

It:

- derives from canonical committed content geometry;
- uses the same render-target viewport as the mode draw;
- uses rounded geometry for `CARD_INTERIOR` and zero-radius rectangular geometry for
  `VIEWPORT_RECT`;
- can compose with **valid inherited scissor/stencil state that genuinely corresponds to real
  framebuffer contents**;
- nests temporary stencil contents without clearing/repurposing the framebuffer as though it owned a
  blank stencil buffer;
- restores temporary stencil contents and every touched direct-GL/scissor/stencil state before
  returning to Qt;
- never shrinks or anisotropically scales authored content to simulate clipping.

The nested real-GL smoke proves that narrower compose-with-valid-state property. It does **not** prove
that arbitrary real PySide `QSGClipNode` metadata is trustworthy.

### 7.4 Quick border semantics

Do not copy the old centred-QPainter mask formula.

The historical path compensated for a centred pen stroke. Qt Quick `Rectangle` borders render inside
the rectangle bounds. The Quick inner clip derives from the actual retained chrome:

```text
outer card path
    minus inside border width
    -> inner content path / inner corner radius
```

Any further inset must be an explicit Quick presentation-style value, not a copied
`1px + border_width/2` rule.

## 8. Authoritative geometry

One committed presentation-neutral geometry record feeds retained shell/chrome, clipping, custom GL,
DPR and later CUSTOM/Edit.

It distinguishes:

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
shell_policy
clip_policy
```

No hidden QWidget remains geometry authority. No stale visualizer-local DPR copy becomes a second
owner.

### 8.1 Canonical default aspect vs internal reference size

All five current Quick modes share one canonical **default/baseline aspect ratio: 1.5**.

Mode changes and built-in visualizer preset changes do not resize that baseline shape. Presets tune
authored visual behavior rather than viewport/card dimensions.

The literal:

```text
CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE = 420 x 280
```

is an internal reference coordinate extent corresponding to 1.5. It arose from layout history and is
**not** a sacred or required visible/runtime size. It remains useful for normalization and authored
stroke/radius scaling where the implementation needs a stable reference coordinate system.

Normal non-CUSTOM runtime size is layout-resolved: an appropriate width comes from the common
widget/media/free-space owner and height derives from the 1.5 baseline aspect; screen-fit reduction is
uniform.

Do not freeze runtime visualizers to 420x280 and do not reintroduce mode-specific card shapes as an
alternate authority.

### 8.2 Retired per-mode growth controls

The pre-Quick presentation controls:

```text
spectrum_growth
osc_growth
sine_wave_growth
bubble_growth
devcurve_growth
```

are not authored mode behavior and are not part of the Quick controller, immutable render state, mode
presentation descriptor, retained shell geometry or new preset authoring.

Any remaining legacy presentation-setting callers are migration scaffolding only. Caller-dead growth controls may be
removed before H; do not preserve them merely to keep the half-migrated old presenter runnable.

### 8.3 Uniform whole-size scale

`uniform_visual_scale` changes the whole visualizer coherently and preserves the baseline aspect.

```text
scroll-wheel resize -> uniform scale
corner-handle resize -> uniform scale
```

This is not an X/Y stretch.

### 8.4 Viewport extent

`viewport_extent` is separate from whole-size scale. The required retained CUSTOM edge operation changes one axis
while keeping visual scale constant:

```text
left/right edge -> viewport width only
top/bottom edge -> viewport height only
```

That intentionally changes available world/layout playroom and may produce a wide/tall aspect other than 1.5. Modes
reflow/adapt; final rendered pixels are not anisotropically stretched.

All five current production modes must be viewport-resize-capable, including Bubble. That policy flip and the core Bubble
reflow are landed; do not re-gate Bubble to avoid fixing a viewport defect. Focused G proof must preserve Bubble spatial/BTF
semantics and the canonical baseline path.

### 8.5 Spatial logical modes

When Bubble or another logical mode needs viewport bounds, presentation-neutral viewport configuration enters the logical
side as state. Ordinary committed extent is the baseline runtime truth; while CUSTOM is active its working extent may
temporarily override that value. Save commits the new value, Cancel restores the old committed value, and ending CUSTOM
must remove the override without assuming canonical `(420,280)`.

Geometry changes are never another authored clock and mouse-move/render frequency never becomes
simulation cadence.

## 9. Fade and readiness authority

One authored presentation fade authority owns the visualizer as a whole.

The landed resolver may derive more than one **layer value** from that one authority, currently
including:

- `scene_fade` for the retained presentation root/card;
- `content_fade` for GL content where required by the authored content-stagger/fade behavior.

These are derived outputs of one authored transition. `content_fade` must never become a second timer,
second fade lifecycle or independently advancing temporal authority.

Do not animate fade by repeatedly enabling/disabling clip/shadow topology.

Readiness remains split:

```text
presentation_ready
reactive_source_ready
```

A presentation-owned idle scene may reveal without fabricating reactive source identity. Paused
Spectrum is the canonical case.

Readiness depends only on resources required by the resolved shell policy; a future frameless mode does
not wait for card resources it deliberately does not own.

## 10. Baseline/wide/tall renderer compatibility

Phase D proved renderer geometry at the canonical baseline aspect at multiple uniform scales and with
controlled wide/tall extents so the modes are not secretly hard-coded to one old card shape.

Expected semantics at constant visual scale remain:

### Spectrum

- bar distribution/layout recomputes from viewport width;
- vertical extent follows content height;
- no stretched pre-rendered image.

### Bubble

- spatial domain/aspect may change;
- circles remain circles;
- radii, velocity units, trajectories and BTF stay coherent;
- no arbitrary X/Y scaling.

### Oscilloscope / Sine / DevCurve

- domain/placement adapts to available width/height;
- authored stroke thickness and visual scale remain stable.

### Future 3D modes

- camera/projection uses current viewport aspect;
- round geometry remains round.

These compatibility probes established that wide/tall rendering is viable. Interactive edge resizing is a G CUSTOM
requirement and must now expose that geometry seam for every current mode.

## 11. Mode contracts

### Spectrum

Preserve:

- authored bar/peak behavior;
- ghosting/persistence;
- border/mask/style;
- paused idle bars perceptibly visible;
- source identity absent until a real source is authoritative;
- Play replacing idle state in place rather than recreating presentation ownership.

No mode-specific presentation clock.

### Oscilloscope

Preserve authored waveform shape, line count/persistence/ghosting, idle behavior, style and logical
cadence. `osc_growth` is not part of the Quick behavior contract.

Physical render cadence does not become waveform sampling cadence.

### Sine

Preserve authored idle motion, layers/line persistence, reactive behavior, ghosting and tuning.
`Sine` does not gain a separate timer merely because Quick has animation primitives.

`sin_wave_growth`/`sine_wave_growth` legacy presentation sizing is not authored mode behavior.

### Bubble

Bubble remains the timing/fidelity canary. `Docs/Guardrails/Bubble_Temporal_Fidelity.md` is mandatory.

Preserve:

- continuous positional evolution;
- trajectories;
- collision/elastic feel;
- trails/tails;
- ghosts/pop/transients;
- protected renderer-visible consequences;
- source freshness;
- authored logical Hz;
- authored mode style/reactive personality.

Do not retune Bubble to compensate for presentation defects and do not discard authored logical steps
to reduce callbacks/GPU use.

The historical observation that disabling unrelated widgets materially changed measured Bubble-era GPU
load is evidence to investigate shared presentation/runtime cost and true dormancy. It is not evidence
that Bubble collision/simulation should be individually simplified.

### DevCurve

Preserve each active layer's:

- enabled state;
- order;
- alpha;
- offsets;
- outline;
- ghosting;
- tuning/specular behavior.

Do not flatten DevCurve into a generic line visualizer.

## 12. Pause / Play

Ordinary Pause/Play keeps runtime ownership warm:

- no window/item recreation;
- no source debounce invented by Quick;
- warm-source policy preserved;
- visible authored state changes promptly;
- expected-state confirmation behavior preserved;
- Quick visibility/activation is not a second playback authority.

Shell policy does not become playback authority.

## 13. CUSTOM participation

The visualizer participates in the retained Quick edit scene through the same committed geometry authority.

CUSTOM edit handles/session behavior use the real retained Quick presentation, never a permanent QWidget screenshot
shell.

Persist/restore whole-size scale and viewport extent as separate values. Edge resize is required for all five current
modes; no current production mode is a destination opt-out.

## 13A. Product display admission and semantic mode-cycle action

The current product admits one visualizer instance. Before construction, Python product orchestration resolves the requested
monitor against participating Quick display units and committed/CUSTOM display geometry. Exactly one participating display
owns the visualizer controller/edge for that activation; other displays do not create duplicate source/logical owners.
Fallback/transfer behavior must preserve the existing product contract when the requested display is temporarily unavailable or
non-participating.

A double-click inside the retained visualizer is a semantic **cycle visualizer mode** action. The visualizer hit region gets
first refusal before the display-level unhandled-double-click fallback (`next image`). Quick/QML may report the hit; Python
remains mode-cycle authority.

## 14. Lifecycle

Retirement conceptually remains:

```text
close visualizer publication
-> stop/join VisualizerLogicalRuntime
-> invalidate activation/generation
-> Quick item loses snapshot admission
-> render-node GL resources destroy on legal render owner
-> clip/shell nodes retire
-> item/controller roots destroy
```

Visibility is not destruction authority.

Stopping/joining the sole authored logical runtime is a **hard retirement barrier**. If join fails, the visualizer generation
remains owned and the owning display must not report terminal retirement or continue window teardown as though it succeeded.

A non-daemon/background owner that survives retirement and prevents process/test shutdown is a defect.

Generation `0` remains valid identity.

## 15. Permanent gates

Keep focused proof for:

- sole authored logical clock;
- every authored logical step integrated before presentation coalescing;
- generation `0`;
- all five modes;
- source freshness;
- protected Bubble consequences and BTF;
- Pause/Play identity;
- Spectrum idle;
- mode switches;
- stale activation/generation rejection;
- logical runtime join;
- distinct Quick render-thread ownership;
- immutable render boundary;
- no live QWidget/provider/settings reads from renderer;
- logical step + every all-five logical/frame-runtime configuration consumer require no live QWidget host;
- canonical technical cache routes engine-owned values to the one shared BeatEngine/audio-worker boundary and authored-logical
  technical-origin values to controller-owned logical state, with bar-count controller/engine/logical-mirror coherence;
- latest logical publication + resolved presentation state compose a complete `VisualizerRenderSnapshot`, populate the
  existing bridge and are consumed through the real retained Quick item/render-node synchronization path;
- exactly one product-level visualizer display owner is admitted; no per-display duplicate controller/source owner;
- retained visualizer double-click mode-cycle precedes the global next-image fallback;
- failed authored-runtime join blocks generation/display retirement;
- non-zero-origin/non-1-DPR geometry;
- card/shader alignment;
- `CARD` rounded inner clipping;
- `FRAMELESS` policy scene proof without requiring a production frameless mode;
- local clip host compose/restore with valid inherited framebuffer state;
- no claim that arbitrary QSGClipNode metadata is trustworthy;
- one 1.5 baseline aspect shared by all current modes;
- no Quick authority for the retired five `*_growth` controls;
- baseline aspect preserved by uniform whole-size scaling;
- default/wide/tall geometry without anisotropic distortion;
- render resource creation/release;
- Settings/recreation where presentation state is involved.

Physical cadence/eyes-on claims require the operator's corresponding installed Windows/display/GPU
environment and remain separate acceptance evidence.

## 16. Landed Phase-D checkpoint record

Phase D was intentionally split/audited around:

1. presentation-neutral runtime/controller + mode policy;
2. immutable latest-state bridge;
3. Quick visualizer item/node + clip/shell/geometry foundation;
4. Spectrum;
5. Oscilloscope;
6. Sine;
7. Bubble + BTF;
8. DevCurve;
9. all-five lifecycle/source/pause/aspect closure;
10. documentation closure.

That list is historical migration rationale, **not a to-do list**.

## 17. Phase-D closure

Phase D is complete because all five modes use the Quick visualizer boundary with:

- authored logical runtime intact;
- mode-owned logical frame runtimes;
- immutable latest-state publication;
- generation-fenced lifecycle/resources;
- `CARD + CARD_INTERIOR` fidelity for the current five;
- no old compositor/QWidget dependency inside the new renderer;
- no assumption that every future mode must draw a card;
- geometry that separates default aspect, uniform scale and viewport extent;
- one authored fade authority;
- selected local SDF/stencil clip ownership.

Do not restart D1–D9 from this document. Current work admission comes from `Current_Plan.md`.
