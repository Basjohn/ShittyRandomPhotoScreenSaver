# SRPSS Guardrails

## Architecture decision

```text
one selected physical display
-> one standalone QQuickWindow
-> threaded Quick scene graph
-> one composed runtime scene
```

Do not reopen broad native/C++ presenter work without new evidence the accepted architecture cannot satisfy production.
Do not use `QQuickWidget`, second accelerated runtime surfaces, or restore/deepen the deleted QRhiWidget/DisplayWidget architecture. The old physical presenter is retired and is not a fallback product or test convenience.

## Retired presentation architecture

The Qt Quick cutover is closed. The deleted QWidget/QRhiWidget/GLCompositor physical presentation path is not fallback architecture, test scaffolding or a continuity layer. Caller-dead residue is deleted outright with its test cascade in the same commit; historical reasoning belongs in `Docs/Historical_Bugs/` or source control. Do not recreate retired presenters merely to satisfy stale tests or prose.

## Priority

1. visualizer fidelity/reactivity;
2. lifecycle/resource safety;
3. frame pacing/perceived smoothness;
4. multi-display correctness;
5. bounded resources;
6. CPU/task efficiency;
7. average FPS;
8. elegance.

Never improve counters by silently reducing authored work/fidelity.

Performance-specific admission, telemetry semantics, load-class evidence and reference envelopes live in `Docs/Guardrails/Performance_Optimization_Contract.md`. Use that checklist before changing cadence, GC policy, scheduling, caching, resource lifetime or presentation for performance.

## Read / scope discipline

```text
exact source
-> Current_Plan.md
-> Spec.md
-> Docs/Contracts.md
-> relevant focused contract/guardrail
-> tests/evidence
```

Preserve unrelated user work. Do not reset/checkout/clean/stash/revert merely to manufacture checkpoint equality.
Historical evidence is not current owner map.

When current source contradicts a durable product contract, do not silently rewrite the contract to match the bug.
Promote the missing behavior into `Current_Plan.md` unless explicit product intent changed it.

### Defaults test-authority guardrail

Mutable product defaults are policy, not test goldens. Tests that validate a user-facing default must derive the expected
value from canonical authority (`core/settings/default_settings.py` / the canonical default contract) or prove generated
artifact parity. Do not copy today’s default literal into unrelated Settings/runtime/UI tests.

A literal expectation may remain only when the **literal itself** is the contract (for example a migration signature, hard
safety/technical bound, protocol/schema constant, or accepted behavior golden). Mark it adjacent to the assertion with
`EXACT-VALUE INVARIANT:` and explain what authoritative contract would have to change before the test should change.
Behavioral tests may intentionally choose non-default values; mark ambiguous cases as `TEST INPUT, NOT A DEFAULT GOLDEN`
and derive downstream expectations from that fixture input. Never “fix” such a test by coupling it to the current product
default.

## Immediate stop conditions

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

## Evidence, validation and fallback guardrails

**Work is to at most be marked `[~] AWAITING VALIDATION` until a log, the operator, or an extremely high-confidence test proves the required behavior.** Authored code, compilation, source inspection or a plausible mechanism is not `[x]` product closure by itself. If acceptance depends on physical Windows/Qt/GL/provider behavior, keep the item awaiting validation until that evidence exists.

Prefer event-owned state and explicit lifecycle edges over polling, debounce timers, periodic probes or speculative safety fallbacks. Polling is a last resort only when the source genuinely exposes no usable event/notification contract; even then it must be low-cadence, bounded, observable, and documented as reconciliation rather than primary truth. Never add a silent fallback that can become the de-facto owner while logs continue to suggest the intended path is healthy. Any mechanism likely to increase `dt_max`, input latency, main-thread stalls, hidden wakeups, poison/stale ownership or cadence contention requires explicit evidence before admission.

Programming defects are not reconciliation policy. A broad ``except Exception`` must never turn ``TypeError``, ``AttributeError``, bad call signatures, or other coding defects into an apparently legitimate teardown/rebuild/fallback. Expected stale/dead/incoherent-owner recovery must use an explicit classified exception/result owned by that seam. Unexpected defects must be surfaced loudly after any required terminal cleanup so they cannot silently train the runtime to depend on expensive recovery.

Do not create a new generic `Expected_Behaviour.md` ledger by default. When a suspicious behavior is **proven expected**, record that fact at the nearest durable owner: the relevant historical-bug closeout, focused contract/guide, performance guardrail, or regression test. This prevents future agents from reopening already-cleared smells without adding another broad document that will drift.

### Qt Quick presentation-clock guardrail

Do not infer a Qt Quick surface/pacing policy from documentation or pre-Quick history alone. SRPSS owns multiple top-level Quick windows and may run mixed refresh rates; a 2026-09-14 installed two-display A/B **rejected forcing ``swapInterval=1``** because pacing, FPS/headroom and interaction smoothness became materially worse. The production Quick bootstrap therefore retains the known-good release-era ``swapInterval=0`` policy until a better architecture is proven on installed multi-display hardware. Never reintroduce VSync=1 as a generic "Quick-native" cleanup without that evidence.

Likewise, do not tune a GUI ``QTimer`` as a bandage. Qt Quick frame-pacing work must distinguish **logical work cadence**, **scene invalidation/update demand**, and **physical presentation**, and must be A/B tested against the known-good 5.0.0/5.0.1 Quick baseline. Never reduce Visualizer logical freshness/reactivity to make a display-pacing graph look cleaner. Any future removal/replacement of ``QuickFramePacer`` is a separate architecture change and stays ``[~] AWAITING VALIDATION`` until installed evidence proves equivalent transition/widget-animation liveness and improved frame spacing across single- and mixed-refresh multi-display cases.

Qt Quick hot paths are scarce budget: never add dormant per-frame Python/logging/telemetry on ``frameSwapped``/sync/render edges, hidden ``Repeater`` delegate forests, or always-live effect/layer work without measured need. Keep deep render-loop timing behind an explicit diagnostic sidecar with zero normal-runtime cost. Judge smoothness by frame-spacing tails **and fresh-state age**, not average FPS alone; CUSTOM Edit FPS is a different demand regime, not a steady-runtime target. `ThreadManager` ``TaskPriority`` is currently metadata on a FIFO ``ThreadPoolExecutor``; never treat ``LOW`` as Qt/Windows scheduling priority. Best-effort CPU speculation must not use a heavyweight helper process or normal-priority shared COMPUTE lane by assumption: use the ThreadManager background lane only when semantics tolerate delay, keep it one-thread/bounded/QImage-only, and fail closed on Windows if native demotion is unavailable.

## Visualizer preset / technical-settings authority guardrail

Technical settings are ordinary Visualizer settings with shared usefulness, **not** a higher-priority authority above presets.
A curated preset may author any mode-owned technical setting; Custom preserves the user's authored technical state. Resolution
order is preset/custom-authored value first, then canonical product default only for a genuinely missing field. Runtime/DSP/tick
consumers must consume the already-resolved technical mapping and must not carry their own numeric fallback tuning. Retired
shared/global technical literals may remain only as explicit migration signatures and must never be refreshed to today's defaults
or fed back into live runtime. Never flatten authored preset technical values into baseline defaults to simplify plumbing.

## Visualizer geometry guardrail

Keep these distinct:

```text
uniform_visual_scale   # wheel/corner whole-size scaling
viewport_extent        # independent world/playroom width/height
```

All six registered modes are viewport-resize-capable through their declared presentation policy. The five established carded technical modes share the card geometry path; experimental Sphere uses FRAMELESS + VIEWPORT_RECT. Edge viewport resize is configuration, not a clock. Bubble
must receive changed spatial bounds without deforming circles or compromising BTF. Ordinary committed viewport extent
remains truth outside CUSTOM; a working CUSTOM extent is a temporary override only. Leaving CUSTOM must not reset a saved
non-baseline layout to canonical by confusing "no override" with "baseline".

**R-69 golden rule:** viewport adaptation must not globally compress Bubble head/radius response, already-normalized Ghost/history displacement, or another Visualizer mode's authored musical response/freshness. Never add a second `baseline/current` or `1 / viewport_extent` compensation to state that is already projected into renderer content coordinates. If an extreme visual tail is too large, fix only that proven tail.


## Ordinary widget extension guardrails

Ordinary widgets share one normalization/session geometry system. Whole-card uniform scaling remains the default. A family may opt into shared CUSTOM `content_extent` axes only when presentation reflow is genuinely useful; that is an extension of the same CUSTOM session, not permission for family-local geometry persistence, timers, alternate normalization, or Settings mutation. Side gestures may use family-owned logical floors through the shared policy seam; an admitted diagonal content corner may change both logical axes through that same owner, while **square** corner/wheel resize remains uniform. Restore Size must use separately retained authored geometry and must never learn its target from a committed CUSTOM extent.

Lazy family Settings/runtime teardown is an ownership boundary. Invalidate queued/coalesced UI work, close admission, clear retained child references before Qt deletion, and reject stale wrappers/completions. A future widget should extend the generic family lifetime contract rather than grow a widget-name unload exception.

## CUSTOM child and semantic-flip admission

A child Edit gesture is not permission to change outer parent dimensions or
persist an inferred `content_extent`. Child motion/resize is hard-contained to
its actual painted/card or separately declared accessory surface, whether peer
collision is enabled or not. Only explicit **outer handles** can change parent
size; authored dimensions remain Restore's baseline, not a second live child
minimum. Clamp snap results after snapping and commit unchanged results without
churn. Never turn a child overflow request into another Settings or geometry
owner, even as a temporary selected-Edit requirement.

Family-authored reflow remains live per axis after independent child edits.
An X-only edit does not detach Y; a Y-only edit does not detach X. Avoid scalar
`x+y` change detection, offset-dependent all-axis `onAuthoredRail` gates and
subtraction of subsequent parent Column displacement. Flip exchanges placement,
not pixels; choose a semantic text scaling origin in either orientation.
Admission requires a real retained-scene/paint test of **saved customized** child
records under Y-only/X-only resize, plus Reset -> Flip -> Save -> Edit -> shrink,
checking painted bounds rather than model visibility. When a test passes but a
physical flipped widget fails, its gate is insufficient and must be revised.
Look for matching off-rail/clip/churn failure in other families, but do not apply
a universal QML rewrite without family-level paint and owner-lifecycle proof.

### Repeated list-column edit boundary

A semantic rail swap must reorder **all rows of one retained list** using one
widget-scoped order in the existing CUSTOM owner and payload. Reddit's age
value, title and AGO are distinct semantic columns;
Gmail has sender, subject and timestamp. Do not simulate swaps with per-row
child positions, a second persisted column map, repeated-delegate rebuilds or
new runtime observers. Commit one discrete reorder action, preserve both flip
orientations and untouched-axis reflow, and prove Undo/Save/Reset/layout slots
and fresh-generation paint before accepting it. The rail UI is Edit-only;
ordinary runtime must not construct rail targets or watch their geometry.

## Last-good cache guardrail

A successful cache record does **not** expire merely because it becomes stale. Freshness controls refresh admission and stale labeling; it is not deletion permission. On source failure, keep rendering last-good intended data indefinitely unless an explicit account/cache reset, schema rejection/corruption, or proven identity change invalidates it. Never improve apparent freshness by blanking stale-but-valid data or substituting semantically different data.

## Capability state

Ordinary ON/OFF is not family/capability activation. CUSTOM X and layout slots may change ordinary ON/OFF only.
A deactivated family remains deactivated even if a saved layout contained it.

## Lifecycle

Close admission before retirement. Fence stale generation/request state. Destroy custom GL on the legal render/context
owner. Do not repair cadence with `glFinish()`, `DwmFlush()`, GUI sleeps or nested event loops.

**System-audio dormancy.** The Core Audio endpoint (`core/media/system_mute.py`) and the mute/system-volume runtime are
admitted only behind the mute-button setting, on the UI thread. Do not acquire the endpoint, register callbacks or run that
runtime while the feature is disabled; the End/PgUp/PgDown system-audio keys are gated by that same admission by design.

The operator-authorized Bubble equal-area response correction is documented in `Docs/Reference/Visualizer_Reference.md` and protected by BTF/R-69. It supersedes height-only product mapping; it does not authorize viewport-dependent performance caps, DSP attenuation, temporal smoothing changes or compression of already projected Ghost/history.
