# H Pre-Cutover Visualizer Destination-Edge Corrections

Status: **CLOSED audit/correction evidence — not current work admission**  
Status authority: `Current_Plan.md`  
Durable H boundary: `Remaining_H_Production_Cutover_Decomposition.md`  
Post-audit True-F closure record: `H_True_F_Technical_Closure.md`  
Audit source basis: `b2a8cd8527c18bc4a8137717d8eb5f891140bd0d`  
Audit date: 2026-08-29

The `[RED]` labels below describe findings **at the audited source basis**. They are preserved as evidence and must not be read
as current phase status. Findings A–E were closed, and the first claimed F closure was later independently strengthened by the
True-F technical/retained-consumer correction. Live gate status belongs only to `Current_Plan.md` / `Docs/TestSuite.md`.

This is the bounded correction record discovered **before** the DisplayManager production authority flip. It does not reopen
accepted G, Phase D rendering work, Bubble tuning or the widget-free visualizer logical-owner extraction. Its purpose is to
close the last product-owner/synchronization seams so the atomic cutover does not strand a thread, bind an empty render bridge,
duplicate the visualizer across displays or silently lose authored per-mode configuration.

## 1. Accepted foundation — do not reopen

The audit accepts these source facts as useful destination foundation:

- `VisualizerRuntimeController` owns controller-scoped logical state, engine/source identity, the sole authored
  `VisualizerLogicalRuntime`, mode logical runtimes, latest logical mailbox and immutable render bridge.
- `VisualizerLogicalRuntime` can advance `logical_tick(controller.logical_tick_state)` without constructing
  `SpotifyVisualizerWidget`.
- immutable `VisualizerLogicalFrame`, `ResolvedVisualizerPresentation`, `VisualizerRenderSnapshot` and
  `VisualizerSnapshotBridge` contracts already exist.
- Quick visualizer render items/nodes consume the immutable render snapshot contract.
- `QuickDisplayRuntime` exposes explicit render-source and viewport-configuration bindings.
- `QuickDisplayVisualizerOwner` exists as a thin display/generation edge and proves useful construction/configuration/bind/
  start/retire component seams.

The correction must reuse these owners. Do not replace them with a new visualizer subsystem, second clock, second bridge,
parallel presenter or QWidget compatibility facade.

## 2. Finding A — render bridge is bound but the destination publication edge is incomplete [RED]

The authored logical step publishes `VisualizerLogicalFrame` into the controller's latest-state mailbox. Quick rendering,
however, consumes `VisualizerRenderSnapshot` from `VisualizerSnapshotBridge`. At the audited checkpoint the thin Quick owner
binds the bridge into the runtime, but the production destination path does not yet perform the required middle operation:

```text
freshest VisualizerLogicalFrame
+ current resolved presentation state
-> VisualizerRenderSnapshot
-> VisualizerSnapshotBridge
-> retained Quick visualizer item/node
```

A bridge object being connected is therefore **not** a completion bar. The destination requires one synchronization owner
that:

1. runs on the legal GUI/Quick synchronization side, never the authored logical worker or render thread;
2. takes/coalesces the freshest logical publication with existing latest-wins semantics;
3. rejects stale runtime generation, engine generation, activation and mode identity;
4. resolves complete presentation facts (geometry, DPR, shell/clip policy, committed/CUSTOM viewport, uniform scale,
   one-authority fade-derived layer values, border/style facts required by the render contract);
5. composes the canonical immutable `VisualizerRenderSnapshot`;
6. publishes through the existing bridge and marks/requests retained Quick presentation;
7. never waits for paint, creates a FIFO/catch-up queue, invents another timer/cadence or makes presentation acknowledgement
   part of logical admission.

Legacy `present_tick()` may remain scaffolding before cutover, but the Quick path must not call it: it owns QWidget validity,
legacy mode reveal, compositor push and widget repaint consequences.

## 3. Finding B — configuration ownership was split by naming, not by actual consumer [RED]

The earlier narrow split correctly moved Bubble physics and a few shared logical values off the widget, but the audit found
additional authored logical/frame-runtime consumers still reading values classified as "presentation" merely because they
historically lived on `SpotifyVisualizerWidget`.

The durable classification rule is now:

```text
if authored logical evolution or a mode-owned logical frame runtime reads it
    -> presentation-neutral resolved logical/runtime configuration
elif only Quick shell/chrome/render presentation reads it
    -> presentation-owned resolved presentation state
```

Representative audited logical/frame-runtime consumers include:

- **Spectrum:** smoothing, ghosting/persistence and animation-related inputs used while resolving authored Spectrum frame state;
- **Oscilloscope:** speed, ghosting/decay, sensitivity/amplitude and transient-width inputs used by the mode frame runtime;
- **Sine:** speed, travel directions, per-line shifts, heartbeat, width reaction, sensitivity and ghosting inputs used by the
  mode frame runtime;
- **Bubble:** existing physics/cadence/spatial settings already moved toward neutral ownership remain there; renderer-only
  gradient/outline/specular/card styling stays presentation-owned;
- **DevCurve:** motion/idle/smoothness plus layer enable/order/power/offset/shape and related authored field inputs consumed by
  the DevCurve logical advance.

This is **not** permission to move all legacy widget attributes into `VisualizerRuntimeController`. Prefer resolved immutable
or controller-owned per-mode configuration records/state that expose exactly what the logical consumer needs, while pure
colour/glow/card/chrome/render style remains on the presentation side. Preserve existing defaults, preset semantics and
technical BeatEngine configuration; do not retune authored behavior during ownership migration.

## 4. Finding C — retirement may report success after a failed authored-runtime join [RED]

`VisualizerLogicalRuntime` is non-daemon authored work. A failed stop/join is an unresolved generation, not a best-effort
cleanup detail.

Required retirement order for the admitted visualizer owner:

```text
close visualizer publication/admission
-> stop + join sole VisualizerLogicalRuntime
-> if join fails: keep ownership and FAIL retirement barrier
-> invalidate activation/generation
-> detach Quick render admission / retire visualizer item resources
-> only then allow owning Quick display runtime/window retirement
```

`QuickDisplayVisualizerOwner.retire()` (or its durable successor at the same ownership edge) must not close the render source,
return success or permit the owning `QuickDisplayUnit`/`QuickDisplayRuntime` to continue terminal teardown while the logical
runtime remains owned. Repeated retirement remains idempotent after a real successful barrier.

Tests must exercise a deliberately failed join, prove the owner remains unresolved, then prove later successful join allows
retirement. Do not weaken the logical runtime's existing hard-join behavior to make teardown easier.

## 5. Finding D — visualizer display admission is product semantics, not per-display default construction [RED]

The current product has one admitted visualizer instance whose requested monitor may be unavailable/non-participating. Legacy
routing therefore resolves a participating display owner and fallback rather than constructing a visualizer on every display.

The Quick destination must preserve that semantic before owner construction:

```text
canonical visualizer enabled/activation + requested monitor
+ currently selected/participating QuickDisplayUnits
+ committed/CUSTOM display-scoped geometry
-> exactly one admitted visualizer display owner
-> QuickDisplayVisualizerOwner / VisualizerRuntimeController
```

Rules:

- non-owning displays construct **no duplicate visualizer controller, logical runtime or source owner**;
- requested participating display wins;
- if the requested display exists but is not ready/participating yet, preserve the existing cautious ownership/fallback
  semantics rather than freelancing onto arbitrary geometry;
- if fallback is required, choose from actual participating Quick units using stable product ordering;
- CUSTOM/committed geometry and display identity must follow the existing transfer/rehydration contracts;
- topology/generation replacement must never leave two live visualizer owners for one product instance.

`Docs/Historical_Bugs/R-26_Visualizer_Custom_Display_Participation.md` remains useful historical evidence for the product
behavior; destination ownership must be implemented with Quick display participants, not legacy `_widget_manager` probes.

## 6. Finding E — retained visualizer double-click semantic action is missing [RED]

Product semantics distinguish:

```text
double-click visualizer -> cycle visualizer mode
unhandled display double-click -> next image
```

The Quick window already gives retained ordinary-family semantic hit regions first refusal, then falls back to the neutral
runtime input owner's global next-image action. The visualizer must join that retained semantic hit/action admission before the
fallback. QML/Quick may identify the visualizer hit region, but Python remains mode-cycle/business authority.

Do not solve this with a second global mouse router or by changing the global fallback meaning.

## 7. Finding F — existing fresh-owner tests are component proof, not destination-chain proof [RED at audit basis]

**Closure note:** the first follow-up proof still stopped short of canonical technical application and real retained-item
consumption. `H_True_F_Technical_Closure.md` records that final bounded correction. Keep this section as the original finding,
not as the current gate.

The current fresh-owner test usefully proves construction/configuration/bind/start/retire shape with a small fake engine and a
bounded Bubble-oriented configuration. It does not prove the whole product route. Before atomic cutover add at least one
owner-shaped destination test matrix that begins from canonical settings/resolved preset state and reaches the retained Quick
consumer without `SpotifyVisualizerWidget`.

Minimum deterministic proof:

- all five modes;
- canonical settings + resolved preset/custom values feed the correct logical/runtime and presentation owners;
- technical engine configuration remains singular;
- logical step publishes current-generation immutable logical state;
- synchronization owner composes/publishes a complete `VisualizerRenderSnapshot` into the existing bridge;
- retained Quick item admits/takes the snapshot for the correct generation/engine-generation/activation/mode;
- paused Spectrum presentation readiness remains distinct from reactive source readiness;
- Pause/Play retains intended runtime identity/warm-source behavior;
- mode switch/reveal completes without QWidget reveal/shadow/layout calls;
- requested-monitor and fallback ownership produce exactly one visualizer owner;
- retained visualizer double-click cycles mode and does not fall through to next-image;
- generation `0`, replacement, stale callback/snapshot rejection and successful retirement;
- failed logical-runtime join blocks retirement.

Existing BTF/golden/render-node/geometry/component tests remain binding and should stay unchanged unless exact source proves a
real contract correction. Do not rewrite goldens to bless migration drift.

## 8. Historical implementation order used to admit the DisplayManager flip

Recommended bounded order:

1. consumer-driven all-five configuration ownership correction;
2. presentation synchronization owner over existing mailbox + render contracts;
3. Quick-owned reveal/fade/presentation consequences needed by that synchronization path;
4. single visualizer display admission + committed/CUSTOM geometry binding;
5. retained semantic visualizer double-click mode-cycle admission;
6. hard join-barrier retirement and display-unit retirement order;
7. all-five owner-shaped destination-chain proof;
8. fresh post-push audit.

Only after these are GREEN does `Current_Plan.md` admit the already-selected atomic DisplayManager + engine cutover.

## 9. Rejected shortcuts

Do not:

- start the DisplayManager cutover while this correction gate is RED;
- restore `logical_tick(widget)` as the destination logical owner;
- call legacy `present_tick()` from Quick;
- bind an empty bridge and call the visualizer complete;
- create a second publication timer, presentation cadence, FIFO or paint acknowledgement;
- put every visualizer setting into the logical controller;
- construct a visualizer controller once per display by default;
- preserve legacy `_widget_manager` participation probes in destination code;
- hide failed logical-runtime join and continue display teardown;
- change global double-click fallback semantics to compensate for a missing visualizer hit region;
- keep `SpotifyVisualizerWidget` or compositor pixels as a post-cutover fallback;
- retune Bubble or rewrite deterministic goldens to make the correction pass.

## 10. GREEN exit bar

This correction gate is GREEN only when exact current source proves:

```text
canonical visualizer settings / preset / activation
-> one product-level admitted visualizer display owner
-> one VisualizerRuntimeController + controller-owned all-five logical/runtime config
-> sole VisualizerLogicalRuntime
-> latest immutable VisualizerLogicalFrame
-> one GUI/Quick synchronization owner
-> complete ResolvedVisualizerPresentation
-> VisualizerRenderSnapshot
-> existing VisualizerSnapshotBridge
-> retained Quick visualizer item / QSGRenderNode
```

with semantic mode-cycle input, committed/CUSTOM viewport ownership, generation/activation fencing and hard successful join
retirement all proven without constructing `SpotifyVisualizerWidget`.

Once the correction gate closed, execution returned to the durable H cutover route. Do not reopen this audit merely because
its preserved finding headings say `[RED]`; inspect current source/tests and `Current_Plan.md` instead.
