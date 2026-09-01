# Phase H Closure — Qt Quick Production Runtime

Date: 2026-09-01  
Status: **CLOSED — Phase I admitted**

## Purpose

This is the durable closure record for Phase H. It preserves the acceptance boundary so `Current_Plan.md` can stop carrying hundreds of completed H checklist lines.

H's job was to make the accepted Qt Quick destination the real production owner, delete the old physical presenter/backend authority, then close the functional/runtime/performance defects exposed by real source-mode use. H is now closed. Later regressions reopen their smallest owner/incident, not Phase H as a whole.

## Accepted owner chain

```text
selected physical display
-> one standalone QQuickWindow
-> threaded Quick scene graph
-> one composed runtime scene
-> retained ordinary families / retained Visualizer / transitions / overlays
```

The deleted `DisplayWidget` / QRhiWidget / `GLCompositorWidget` physical path is not rollback architecture or a test convenience fallback.

## Accepted H gates

- H1a — Settings/CUSTOM runtime reconstruction and dual-display recreation: accepted.
- H1b — generation retirement, retained model lifetime, Settings event-filter teardown and terminal destruction: accepted.
- H2 — Media artwork provider identity: accepted physically.
- H3 — Reddit production opener: accepted physically.
- H3b — Clock runtime mode toggle + CUSTOM recreation: accepted physically.
- H4 — Media Play/Pause/seek provider-result semantics: accepted physically.
- H5a — CUSTOM Visualizer routing independence from Media: accepted physically.
- H5b — all-five visualizer topology/configuration ownership: accepted physically.
- H5c — final Visualizer reactivity/performance boundary: accepted for H; golden scaling/reactivity rules below are permanent.
- H6 — Media CUSTOM Settings control-lock semantics: accepted.
- H7 — visible Exit response/retirement: accepted physically.
- H8 — same-mode preset cycling + Custom round-trip/recreation: accepted physically.
- H9 — ordinary-family uniform resize / absolute floor / replay: accepted; Gmail belongs to the uniform-transform family.

## H5c final heavy-load performance evidence

The operator intentionally ran SRPSS under reasonably heavy system load because that is a realistic deployment condition.

Final representative run:

```text
Visualizer logical publication        ~89-90 Hz when active
Typical retained snapshot age         ~18-22 ms
Audio-analysis mean execution         ~1.86 ms
Audio callback work                   ~0.067 ms
Persistent lane accepted/completed    16,944-class, no generic Future fallback
Final gen-0 collection rate           ~9.8 / second
Final gen-2 rate                      ~0.39 / minute
Observed deep gen-2 pauses            ~130-146 ms
```

The two large architectural allocation fixes were:

1. retire per-audio-frame generic task/Future/callback allocation in favor of the existing persistent serial compute lane;
2. retain detached DSP state across ordinary frames instead of deep-reconstructing NumPy/history/transient state each analysis step.

The final run had the lowest normalized GC frequency measured during this investigation despite deliberate heavy load. Rare deep collections remain visible debt, but no further H change had a comparably clear allocation source with sufficiently low reactivity/freshness risk.

**Decision:** close H performance. Carry rare deep-GC/latency optimization to late J. Do not tune counters by weakening the Visualizer.

Historical record: `Docs/Historical_Bugs/R-71_Visualizer_Audio_Per_Frame_Task_And_DSP_State_Allocation.md`.

## Visualizer golden lesson

`R-69` is binding across future Visualizer work.

Bubble proved that a presentation correction can leave DSP/cadence telemetry healthy while destroying the visible musical delta. In wide/tall CUSTOM shapes, globally multiplying the head radius or already-normalized Ghost history by another viewport-dependent compression made Bubble appear almost dead even though the logical simulation remained strongly active.

Permanent rules:

- Bubble renderer-facing radius remains the authored fraction of current card height.
- Ghost consumes already-normalized history once.
- R4/R5 compact ripple-wake projection is effect-specific; do not generalize it to head/Ghost state.
- No second `baseline/current` or `1 / viewport_extent` compression of already-projected musical state.
- If an extreme visual tail is objectionable, repair only that proven tail; never flatten the full response curve.
- Apply the same principle to every Visualizer mode: geometry/smoothing adaptation must not silently reduce authored reactivity.
- Reactivity/freshness/cadence outrank average performance counters.

Permanent tests now include the R-69 source guard in `tests/test_visualizer_viewport_scaling_contracts.py`.

## R6 native Cursor Halo

The retained-QML cursor-following Halo architecture was physically rejected because passive pointer motion created scene pressure. Native cursor presentation through `QuickCursorController`/`QCursor` produced a major physical performance improvement.

Never restore moving QML cursor coordinates or a mouse-rate scene invalidation loop to regain visual parity. Remaining Halo visual polish is J-only and must stay native/event-cached.

Historical record: `R-64`.

## R7 transitions / image admission

Transactional image admission, generation/token fencing and prefetch wake are accepted. Timer/natural and manual/double-click transition admission occupy the same observed timing class; there is no separate slow natural-transition population requiring a second architecture.

The old bare-snap/stranded-prefetch failure is preserved in `R-65`.

## R-63 black flash and the one-pixel seam

PresentMon established the binding mechanism: exact-cover borderless top-level windows can be promoted into `Hardware: Legacy Flip`, and transitions into/out of that presentation mode create black/stale frames. Coverage-preserving overscan prevents exact-cover promotion.

Later mixed-DPR native geometry telemetry explained the residual seam pixel. On the operator's pair, an intended exterior/top logical overscan rounded into a `2561`-device-pixel Display-0 window over a `2560`-pixel monitor, overlapping Display 1 by one device pixel.

H acceptance policy is therefore:

```text
recurring black/stale flash = 0        mandatory
bounded shared-edge overshoot <= 1px  acceptable residual
```

Do not trade the first invariant for the second. Any J refinement must derive native/device geometry generically from actual monitor rectangles/DPR and work across different resolutions, coordinates, monitor ordering and common fractional/integer DPRs. No hard-coded `2560`, `1440`, `1.5`, display index or exact-cover correction.

## H9 ordinary uniform resize

Ordinary CUSTOM size has one absolute persisted scale against stable authored/preferred geometry with a shared 40% floor. Re-entering CUSTOM cannot rebase an already-scaled rectangle to 100% and compound shrink.

Reddit/Reddit2, Media and Gmail use whole-card retained uniform presentation scaling. Gmail's preferred width is already outer width; its row-derived preferred height receives shell inset. Visualizer remains separate because whole visual scale and viewport extent are independent product intents.

Historical records: `R-67` and `R-70`.

## Media event migration

Native GSMTC manager/session/timeline/playback observation is the primary owner. The previous fast idle polling ladder stays retired. Slow reconciliation/watchdog exists only as bounded safety/recovery and degraded observation must remain loud.

Observed H runs repeatedly showed prompt reactions with `stale_rejected=0`, `missed=0`, `degraded=False` at lifecycle summaries. Historical record: `R-66`.

## Test-suite reconciliation at closure

The complete supplied test tree was audited. Current production contracts were repaired where tests still described retired H architecture, notably:

- R6 native Halo ownership;
- persistent serial Visualizer audio-analysis lane / no Future fallback;
- retained DSP state and config/reset fencing;
- R-68 CUSTOM Visualizer presentation-authority rebase;
- R-69 Bubble head/Ghost viewport golden contract;
- large-width/height Spectrum presentation smoothing without a new cadence;
- Gmail membership in the uniform-transform family and truthful preferred width/height;
- R-63 no-hardcoded-display geometry guard;
- current image-origin signature.

The maintained profile is renamed `destination`; `h-destination` is a temporary alias.

### Environment qualification

The closure environment lacked PySide6 and PyOpenGL. Because `tests/conftest.py` imports PySide6 unconditionally, pytest collection cannot be completed here. No aggregate GREEN count is invented.

What was verified here:

- every changed test file compiles syntactically;
- the pure source-only Bubble/viewport scaling suite executes successfully (`17` tests);
- the source-only performance-policy module executes its available contracts except the parser case whose `tools/image_change_perf_parser.py` support file is intentionally absent from the supplied GOD artifact;
- all `destination` profile target files exist in the supplied complete test tree;
- profile contains no duplicate target entries.

The first Phase-I step is the real-environment `destination` run.

## Residuals deliberately carried beyond H

These are not H blockers:

- rare ~100ms-class/deeper GC/event-loop stalls under heavy system load -> late J performance work with no reactivity sacrifice;
- old timestamp crossing runtime recreation inflating some latency telemetry -> J diagnostics cleanup;
- optional generic device-space refinement of the <=1px R-63 seam -> J only if black=0 cannot regress;
- extreme Bubble full-expansion visual size, if still aesthetically excessive -> J visual-tail-only solution under R-69;
- family visual parity, context-menu theme parity, alignment/snap guides and other presentation work -> J;
- caller-dead tests/tools/adapters/aliases/source residue -> I.

## Phase transition

Phase I is now admitted. Its job is to delete/rehome caller-dead residue and make broad tree/test ownership truthful. It must not recreate the old app to make stale tests collect.
