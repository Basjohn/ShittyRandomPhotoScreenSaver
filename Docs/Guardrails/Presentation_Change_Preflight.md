# Presentation / Cadence Change Preflight

Read before changing physical presentation, visualizer delivery, cadence or render-state ownership.

## Accepted architecture

```text
one display
-> one standalone threaded QQuickWindow
-> one retained scene

VisualizerLogicalRuntime
-> sole authored visualizer cadence
-> latest bounded state
-> Quick presentation
```

Legacy `DisplayWidget`/QRhiWidget/`GLCompositorWidget` physical presentation is retired and absent from production. It is not rollback architecture, a test convenience fallback or a continuity path. Do not rebuild old pixels to satisfy stale harnesses.

## Rejected

- producer display-rate divisor;
- pending-until-paint admission;
- paint/swap acknowledgement;
- catch-up replay;
- source/event decimation;
- per-frame generic Future/task submission for Visualizer audio analysis;
- separate visualizer presentation surface;
- GUI recurring timer as visualizer simulation owner;
- per-mode visualizer logical clocks;
- `QQuickWidget` runtime presenter;
- old compositor/software presenter fallback;
- broad second native/C++ physical-presenter architecture;
- anisotropic stretching in place of visualizer viewport reflow.

## Visualizer geometry preflight

Do not collapse these operations:

```text
wheel / corner handles -> uniform_visual_scale
left/right edge        -> viewport width
 top/bottom edge       -> viewport height
```

Every registered mode must remain viewport-resize-capable through its declared policy. CARD + CARD_INTERIOR modes use the shared card geometry contract; FRAMELESS + VIEWPORT_RECT modes use their frameless viewport policy. Bubble viewport changes are spatial
configuration and remain subordinate to BTF; they are not grounds for algorithm/cadence retuning.

R-69 is a hard preflight veto: do not make wide/tall geometry look tidier by globally shrinking authored response amplitude, Bubble head radius, motion or already-normalized Ghost/history displacement. Apply the same principle to every mode. Extreme-tail polish must target only the proven visual tail.

## Before changing a renderer

Ask:

1. Is the defect renderer cost, scheduling, logical cadence, geometry or resource ownership?
2. Is the current Quick primitive measured as the limiting factor?
3. Can the change remain inside the one `QQuickWindow`?
4. Does it preserve authored fidelity?
5. Does it preserve one logical clock and latest-state semantics?
6. Are you accidentally preserving an old pixel owner that is caller-dead?
7. If source contradicts a durable destination contract, is this actually missing implementation rather than a doc to delete?

## Acceptance

Use the relevant subset:

- deterministic/source contract tests;
- visual fidelity/goldens;
- authored scheduler health;
- source freshness/state age;
- physical p95/p99/max gaps;
- 60 Hz + high-refresh behavior;
- multi-display/DPR;
- startup/reveal;
- Settings/recreate/topology;
- CUSTOM Save/Cancel and scale/viewport round-trip;
- BTF whenever Bubble is affected.

Average FPS alone never closes a presentation gate.

## Additional binding safeguards by subject
These requirements belong to this subsystem. They are not a second global guardrail or a work queue.

### Stop-and-reassess triggers


Stop/reassess when:

- Bubble/Spectrum/another mode loses authored fidelity/reactivity or BTF fails;
- visualizer wide/tall viewport support is replaced by final-pixel anisotropic stretch;
- Bubble is re-gated/exempted from viewport reflow to avoid fixing a viewport ownership or spatial-domain defect;
- source age rises while visuals continue;
- physical p99/max worsens despite prettier averages;
- producer waits for paint/present or second visualizer logical clock appears;
- logical worker mutates GUI/Quick/GPU state;
- valid generation 0 is lost or stale generation/request can publish/reveal;
- resource ownership cannot be explained;
- fallback silently changes presenter/renderer/capability/authored behavior;
- a second accelerated runtime surface appears or `QQuickWidget` is introduced as a presentation shortcut;
- common Quick imports eagerly resolve inactive family backend/runtime trees;
- family port duplicates provider/controller/timer/cache/action authority;
- architecture cleanup casually redesigns working family interaction/visual behavior without product intent.


### Validation and fallback discipline

**Work is to at most be marked `[~] AWAITING VALIDATION` until a log, the operator, or an extremely high-confidence test proves the required behavior.** Authored code, compilation, source inspection or a plausible mechanism is not `[x]` product closure by itself. If acceptance depends on physical Windows/Qt/GL/provider behavior, keep the item awaiting validation until that evidence exists.

Prefer event-owned state and explicit lifecycle edges over polling, debounce timers, periodic probes or speculative safety fallbacks. Polling is a last resort only when the source genuinely exposes no usable event/notification contract; even then it must be low-cadence, bounded, observable, and documented as reconciliation rather than primary truth. Never add a silent fallback that can become the de-facto owner while logs continue to suggest the intended path is healthy. Any mechanism likely to increase `dt_max`, input latency, main-thread stalls, hidden wakeups, poison/stale ownership or cadence contention requires explicit evidence before admission.

Programming defects are not reconciliation policy. A broad ``except Exception`` must never turn ``TypeError``, ``AttributeError``, bad call signatures, or other coding defects into an apparently legitimate teardown/rebuild/fallback. Expected stale/dead/incoherent-owner recovery must use an explicit classified exception/result owned by that seam. Unexpected defects must be surfaced loudly after any required terminal cleanup so they cannot silently train the runtime to depend on expensive recovery.
