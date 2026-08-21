# 03 — Visualizer Qt Quick Migration

Status: ACTIVE Phase-D technical decomposition
Last updated: 2026-08-21

Cross-links:

- sequence/permission: `Current_Plan.md`
- presentation guardrail: `Docs/Guardrails/Visualizer_Presentation.md`
- Bubble temporal fidelity: `Docs/Guardrails/Bubble_Temporal_Fidelity.md`
- authored behavior/reference: `Docs/Visualizer_Reference.md`
- harness routing: `Docs/Harness_Index.md`
- deferred deletion: `Future_Cleanup.md`

Phase D may proceed while Phase-C physical/eyes-on sign-off remains explicitly deferred. A later failing transition sign-off reopens only the smallest demonstrated Phase-C defect; it does not suspend unrelated Phase-D work by default.

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

The old compositor presentation can hold a `VisualizerRenderState` whose handle references the live visualizer owner and mutable/heavy arrays. That was only acceptable while publication and paint were GUI-thread owned.

It is not a legal Quick render-thread contract.

The Quick render node must not read a live `SpotifyVisualizerWidget`, arbitrary QObject presentation state, provider objects, or SettingsManager.

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
    geometry/fade/readiness
    retained card chrome
    QSGRenderNode visual content
```

Keep source/provider/business logic in Python. Do not rewrite it into QML.

Checkpoint and push the controller/runtime split before beginning renderer complexity.

## 4. D2 — immutable latest snapshot

Define a bounded render-thread-safe snapshot containing only data needed to draw the committed visualizer state.

Representative fields:

```text
runtime_generation
activation_id
mode
playing
logical_timestamp
fade
card/presentation geometry
DPR/render identity

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

Use tuples, immutable records, owned numpy buffers, or another explicitly proven immutable payload shape.

One latest slot per activation/display presentation. Newer committed state supersedes older unread state; there is no render backlog.

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

## 6. Quick visualizer render item/node

Use a sub-rect custom `QQuickItem`/`QSGRenderNode` inside the owning display `QQuickWindow`.

The visualizer remains inline in the same scene as retained card chrome and widgets. No separate native window and no QPainter fallback.

The render node owns its context-local GL programs/resources.

Reuse authored assets/helpers where valid:

- current mode shader sources;
- shared vertex shader/math;
- uniform upload helpers after removing old compositor coupling;
- Bubble logical/output data format and authored math;
- mask/stencil behavior after converting window-space assumptions to explicit Quick geometry.

Do not use an offscreen QWidget/card screenshot as the final presentation path.

## 7. One authoritative geometry contract

Create one committed presentation geometry structure that feeds both retained Quick chrome and custom GL content.

It must account for:

- item x/y/width/height;
- card/background/border/radius;
- GL viewport/scissor;
- shader logical resolution;
- framebuffer origin where required;
- DPR from the owning QQuickWindow/QScreen;
- CUSTOM edit geometry.

No hidden QWidget remains geometry authority. No visualizer-local stale DPR copy.

Card and GL content must remain aligned at non-zero display origins and non-1 DPR.

## 8. Card chrome and fades

Port visualizer/card chrome into retained Quick presentation while preserving current product capabilities:

- background opacity;
- border/radius;
- card shadow;
- header/text where applicable;
- card/foreground opacity;
- current color/customization;
- geometry;
- fade behavior.

Keep separate concepts:

```text
presentation_ready
reactive_source_ready
```

Presentation may become intentionally visible before a live reactive source exists where the current product does so (for example paused Spectrum idle bars).

Prefer one parent/presentation opacity authority for fade. Do not animate by repeatedly enabling/disabling a shadow/effect topology.

## 9. Sole authored-clock guardrail

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

A display may present fewer samples than the logical runtime authors. That does not authorize dropping logical updates before the latest-state publication boundary.

## 10. Spectrum contract

Preserve:

- current bar/peak behavior;
- ghosting/persistence;
- borders/masks/style;
- paused idle bars perceptibly visible;
- source identity absent until a real source is available;
- Play replacing idle state in place rather than recreating presentation ownership.

No mode-specific presentation clock.

## 11. Oscilloscope contract

Preserve the authored waveform shape, line count/persistence/ghosting, idle behavior, borders/masks/style, and current logical cadence.

Do not turn physical render cadence into waveform sampling cadence.

## 12. Sine contract

Preserve authored idle motion, layers/line persistence, reactive behavior, ghosting, and mode tuning.

No separate Sine timer is introduced because Quick can animate.

## 13. Bubble contract — dedicated high-risk checkpoint

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

Do not retune Bubble to compensate for presentation problems. Do not discard authored logical steps to reduce callbacks/GPU use.

The existing observation that unrelated active widgets can materially alter measured Bubble-era GPU load is reason to preserve true feature dormancy and shared-scene efficiency; it is not evidence that Bubble collision/simulation should be individually simplified.

## 14. DevCurve contract

Preserve every active layer's:

- enabled state;
- order;
- alpha;
- offsets;
- outline;
- ghosting;
- tuning.

Do not flatten DevCurve into a generic line visualizer during porting.

## 15. Pause / Play

Ordinary Pause/Play keeps the same runtime ownership:

- no window/item recreation;
- no source debounce invented by Quick;
- warm-source policy preserved;
- visible state changes promptly;
- existing expected-state confirmation behavior preserved;
- Quick visibility/activation is not a second playback authority.

## 16. CUSTOM participation

The visualizer becomes an ordinary participant in the later Quick edit scene.

During Phase D, keep the presentation-neutral geometry/state seam suitable for Phase G without implementing Phase-G CUSTOM prematurely.

Final edit behavior will use the real retained Quick item, not a QWidget screenshot shell.

## 17. Lifecycle

Retirement order conceptually:

```text
close visualizer publication
-> stop/join VisualizerLogicalRuntime
-> invalidate activation/generation
-> Quick item loses snapshot admission
-> render-node GL resources destroy on render owner
-> item/controller roots destroy
```

Visibility is not destruction authority.

No non-daemon/background owner may survive retirement and prevent process/test shutdown.

## 18. Permanent tests/gates

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
- render resource creation/release;
- Settings recreation where presentation state is involved;
- physical cadence/eyes-on only on suitable hardware.

Run deterministic Phase-D tests on a capable Windows checkout and run Quick/OpenGL/physical-display gates only in the environment appropriate to those claims. Do not substitute a broad unrelated suite result for the focused Phase-D evidence assigned to the current checkpoint.

## 19. Checkpoint cadence

Prefer these pushed/audited checkpoints:

1. presentation-neutral runtime/controller split;
2. immutable latest-state snapshot bridge;
3. Quick visualizer item/node + authoritative geometry/card foundation;
4. Spectrum;
5. Oscilloscope;
6. Sine;
7. Bubble + BTF dedicated checkpoint;
8. DevCurve;
9. all-five-mode lifecycle/source/pause audit;
10. Phase-D documentation closure.

A successful checkpoint is committed, branch-reachable, pushed, and independently diff-audited. Connector-created blobs/trees that are not reachable from the branch are not checkpoints.

## 20. Phase-D exit

Phase D implementation exits when all five modes use the Quick visualizer boundary with the authored logical runtime intact, immutable latest-state publication, correct lifecycle, and no old compositor/QWidget presentation dependency inside the new renderer.

Physical/eyes-on acceptance may be tracked separately where the evidence requires the operator's actual display/GPU environment, but all commands and unresolved acceptance items must be explicit before promotion to Phase E.

After Phase D implementation closure, update `Docs/Visualizer_Reference.md` and related authoring/preset guidance to the landed Quick boundary.
