# 08 — CPU, Threading, and Workload Architecture

Last reconciled: 2026-08-19  
Status: **stable architecture/reference only; `Current_Plan.md` owns execution**

This optional audit reference has been reconciled to the landed single-surface + dedicated visualizer
logical-runtime architecture.

## 1. Goal

Make SRPSS cheap by removing waste while preserving:

- authored visualizer reaction/fidelity;
- transition fidelity;
- source freshness;
- multi-display support;
- lifecycle/resource ownership.

Do not improve efficiency by reducing cadence, refresh opportunity, source/event rate or quality.

## 2. Core model

Prefer:

```text
Prepare -> Commit -> Present
```

Prepare:

- network/file IO;
- parsing/filtering/sorting;
- QImage/plain-data work;
- bounded worker-safe computation;
- immutable result assembly.

Commit:

- generation/staleness validation;
- narrow QWidget/QPixmap/GL mutation on legal owner;
- cache/revision publication.

Present:

- compositor consumes current prepared state;
- no hidden simulation clock;
- no disk/network/model construction.

## 3. GUI thread

Keep only work that truly requires GUI/context ownership:

- QObject/QWidget lifetime;
- geometry/visibility/input;
- QPixmap promotion/mutation;
- QRhi/GL create/delete/render;
- narrow current-generation commits;
- compositor presentation scheduling callback;
- visualizer reveal/card/presentation commit.

Remove/avoid:

- sync network/file IO;
- duplicate static raster/cache work;
- unchanged shadow/card regeneration;
- broad pure-data preparation;
- per-frame diagnostic formatting;
- whole-parent repaint for tiny child feedback;
- useless physical repaint of unchanged state.

The GUI thread is no longer the visualizer logical clock.

## 4. Visualizer logical runtime — current, landed

Current owner:

`widgets/spotify_visualizer/logical_runtime.py::VisualizerLogicalRuntime`

Current shape:

```text
audio / analysis snapshot
        ↓
dedicated mode-general logical runtime
        ↓
single-slot latest logical publication
        ↓
GUI presentation consumer
```

Protect:

- one authoritative logical cadence;
- authored dt/events/transients;
- mode-specific history/state;
- no GUI/GL mutation on worker;
- generation-owned join;
- latest-state/no-FIFO semantics;
- valid generation zero;
- scheduler actual-cadence gate.

Do not reintroduce:

- GUI-QTimer simulation;
- AnimationManager simulation;
- per-mode logical thread/timer;
- timed coarse wait reproducing the old ~64 Hz plateau.

## 5. Audio / analysis

BeatEngine/audio worker remains separate from the logical clock.

Capture lifetime and visual playback target are separate concerns.

One-in-flight/latest-pending analysis is bounded and freshness-oriented.

Do not make capture keepalive a visualizer presentation debounce.

## 6. Bubble compute

Bubble's current compute lane remains bounded.

Current installed evidence no longer supports Bubble as the shared system bottleneck.

Do not:

- lower Bubble cadence;
- add Bubble-specific logical clock;
- resurrect rejected persistent scheduler semantics;
- retune Bubble physics to hide presentation gaps.

BTF owns Bubble temporal fidelity.

## 7. Shared GUI availability

After logical cadence extraction, GUI starvation primarily damages:

- physical presentation;
- reveal/fade/layout;
- widgets/feedback;
- Settings/Edit;
- legal card/QPixmap/GL commits;
- lifecycle/recreation.

It no longer directly defines visualizer simulation dt.

Still measure process/GIL contention separately because a Python worker can be delayed by broader CPU
contention even without Qt event-loop dependence.

## 8. Small animation ownership

A small animated visual affordance should use the smallest practical owner.

The current Pause/Play Media feedback investigation is the motivating example: repeatedly repainting
a large stable parent card for one small control acknowledgement is shared-GUI waste.

Preserve the visual effect while narrowing paint/presentation ownership.

## 9. Physical presentation

Each display compositor owns one physical presentation strategy.

It may be adaptive and target refresh rate.

It is not logical simulation.

The 165 Hz display without a visualizer is a useful shared-presentation control.

If it degrades, do not blame the visualizer.

## 10. ThreadManager

ThreadManager remains general async work/task infrastructure.

It is not:

- the visualizer logical clock;
- the physical display clock;
- a reason to put every calculation into a pool.

Use generation ownership for runtime-scoped tasks.

## 11. Future workload changes

A future thread/process/native change is justified only when:

- current source/evidence names a remaining owner/cost;
- the new mechanism replaces an unsuitable owner;
- behavioural contracts are locked;
- lifecycle is explicit;
- no duplicate clock/queue/state machine remains.

One successful worker migration does not authorize indiscriminate thread extraction.

## 12. Evidence

Use:

```text
source
-> existing evidence
-> production-shaped gate
-> bounded correction
```

Do not return to probe-heavy investigation when current source already identifies the bounded waste.

This audit is reference only. Exact current `main`, `Current_Plan.md`, `Docs/Contracts.md` and focused
guardrails outrank it.
