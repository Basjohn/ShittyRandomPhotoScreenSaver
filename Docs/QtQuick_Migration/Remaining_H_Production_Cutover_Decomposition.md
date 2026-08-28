# Remaining H — Production Quick Cutover Technical Decomposition

Status: **execute only after complete G is GREEN, pushed and independently audited/accepted**  
Source basis: inspect exact current tree at H admission; this decomposition defines owners/invariants rather than a frozen commit hash.  
Work admission: `Current_Plan.md`

H is final production owner/orchestration wiring plus old physical-host deletion. It is not a second family migration and
not a requirement to restore the half-migrated legacy application before switching.

## 1. Admission gate

Do not begin H because G7 or G8 individually looks done. Required entry state:

```text
G4 post-checkpoint corrections GREEN
+ G7 caller-proof auxiliary/context closure GREEN
+ G8 focus/MC closure GREEN
-> complete G checkpoint pushed
-> independent audit accepted
-> H admitted
```

The accepted G checkpoint is source truth. If exact source after the audit differs from owner names below, update this
decomposition before coding rather than inventing compatibility behavior.

## 2. Destination chain

Exactly one production chain per selected display:

```text
DisplayManager / engine display orchestration
    -> QuickDisplayRuntime
        -> QuickDisplayWindow
        -> QuickSceneController
        -> one display-owned WidgetRuntimeManager
            -> canonical capability + ordinary enabled/instance admission
            -> existing neutral runtime services/models
        -> ordinaryWidgetHost / visualizer / transition / CUSTOM / auxiliary retained scene
```

No parallel legacy production manager/presenter is permitted.

## 3. Pre-H source seam

Before H, normal startup may still route through `engine/display_manager.py` -> legacy `DisplayWidget` / old physical host.
Treat that as a routing fact, not destination architecture. Inspect exact callers at H admission rather than preserving a
stale private-attribute inventory from an older checkpoint.

The destination pieces are already real and must be connected, not recreated:

- `rendering/quick/runtime.py` — per-display generation owner;
- `rendering/quick/window.py` — exact physical `QQuickWindow`;
- `rendering/quick/scene_controller.py` — sole retained scene item creator/destructor;
- `rendering/widget_runtime_manager.py` — presentation-neutral capability/lifecycle/service owner;
- migrated family models/presentations and neutral service leases from F;
- retained G CUSTOM/input/auxiliary/context owners;
- visualizer logical/runtime controller + snapshot bridge + landed viewport-configuration seam.

H should connect those pieces; it should not create replacement versions of them.

## 4. Keep DisplayManager responsibilities; replace presenter assumptions

DisplayManager remains responsible for product-level display orchestration such as:

- QScreen enumeration and allowed-monitor selection;
- topology reconciliation;
- runtime-generation/display collection ownership;
- current-image routing;
- coordinated readiness/reveal/outward engine signals;
- coordinated exit and display replacement.

Replace assumptions that require QWidget/compositor internals with narrow `QuickDisplayRuntime` APIs/signals. Do not make
`QuickDisplayRuntime` emulate arbitrary `DisplayWidget` private attributes just to minimize diff size.

## 5. Suggested cutover order

1. **Inventory DisplayManager's exact current external contract.** List methods/signals consumed by engine/tests. Separate
   product orchestration from `DisplayWidget` implementation probes.
2. **Make the runtime collection presenter-neutral.** Own `QuickDisplayRuntime` instances without lying about them as QWidget
   objects.
3. **Construct one shared/process Quick scene factory at the proper owner boundary** and one `QuickDisplayRuntime` per selected
   QScreen/generation.
4. **Wire outward input/action signals** from each Quick runtime to the same product-level DisplayManager/engine actions.
5. **Wire base image + transition routing** through explicit Quick APIs; remove compositor/private-widget pokes.
6. **Attach exactly one display-owned `WidgetRuntimeManager`.** Reuse neutral capability/service ownership; never instantiate
   a legacy manager in parallel.
7. **Resolve ordinary family admission once** from capability effectiveness + ordinary ON/OFF/instances, then bind stable
   presentation models into `QuickSceneController`/`ordinaryWidgetHost`.
8. **Bind G owners exactly once:** CUSTOM session/actions/layout slots, context/auxiliary/input state and visualizer
   viewport-configuration ownership through their existing explicit runtime APIs.
9. **Prove readiness/lifecycle/generation replacement** with runtime-shaped tests.
10. **Delete old physical-host callers and source** once the destination is the only production route.

Do not perform step 10 by leaving dead compatibility shims that merely forward dozens of `DisplayWidget` private names.

## 6. Visualizer viewport-configuration binding

H must explicitly preserve the corrected G4 ownership model. Do not depend on incidental ordering between render-snapshot
publication and CUSTOM-session callbacks. Conceptually there are two configuration levels:

```text
committed viewport extent          # ordinary runtime truth
optional CUSTOM working override   # temporary while editing

effective extent = working override if present else committed extent
```

Bind the existing presentation-neutral visualizer controller/config seam once from the display/runtime owner. Requirements:

- ordinary runtime with a saved wide/tall layout consumes that committed non-baseline extent;
- entering CUSTOM seeds/uses current committed truth;
- live edge drag updates only the temporary working override and does not create a Bubble tick;
- Save commits the new extent and retirement of the override leaves that new committed extent active;
- Cancel retires the override and restores the pre-edit committed extent;
- canonical committed extent remains canonical without a redundant persistence key;
- layout-slot replay updates committed viewport truth through the same owner;
- generation recreation rehydrates the committed extent before authored Bubble work is considered ready;
- ordinary presentation publication must not overwrite a live CUSTOM working override;
- CUSTOM becoming inactive must not be translated to `None -> canonical` unless canonical is actually the committed value.

No QQuickItem/QML/QScreen/render-thread object enters Bubble logical state. No second configuration map, queue, timer or
clock is introduced.

## 7. WidgetRuntimeManager cardinality

`WidgetRuntimeManager` is presentation-neutral and may retain provider/model service ownership while presenter bindings
change. H must preserve exactly one intended runtime owner per display/generation.

Rules:

- no legacy `WidgetManager` + Quick host each creating their own neutral manager;
- no duplicate provider/controller/service construction because both old/new presenters briefly exist;
- activation and dependency satisfaction remain distinct from ordinary instance `enabled` state;
- service build/injection failures continue to fail closed; do not fall back to a QWidget-owned provider;
- retirement detaches/retires services exactly once according to existing neutral contracts.

If a Quick presentation host needs a small registry/host adapter for `WidgetRuntimeManager`, make it explicit and
presentation-neutral. Do not make the neutral manager own QML items.

## 8. Generation/lifecycle order

Preserve the landed lifecycle principle:

```text
close old admission
-> invalidate/advance generation
-> quiesce generation-owned logical work
-> stop/pause display presentation cadence
-> close input/context/auxiliary/transition admission
-> retire scene/render resources on legal owner
-> close root/window through queued render-safe path
-> destruction barrier
-> construct replacement generation
-> rehydrate committed runtime/configuration state
-> publish intentional initial content
-> reveal when explicit readiness is true
```

`QuickDisplayRuntime.close_runtime()` already encodes important ordering and queues window/resource retirement to avoid
blocking Python against the threaded render loop. Do not replace it with direct GUI-thread GL/resource destruction.

A topology change rebuilds a generation on the target QScreen; do not move live render resources between windows.

## 9. Readiness

Do not translate old compositor flags into arbitrary sleeps.

Use explicit Quick readiness facts already exposed by runtime/scene as applicable:

- QML root created;
- scene graph initialized;
- background renderer ready;
- intentional base frame ready;
- required runtime/configuration bindings established;
- admission open;
- no scene graph invalidation/error.

DisplayManager may aggregate those facts across selected displays. A fixed delay, black placeholder, stale previous texture
or "window exists" alone is not readiness.

## 10. Physical-host deletion boundary

After the Quick production route is proven, delete caller-dead old physical presentation, including as applicable:

- `DisplayWidget`;
- QRhiWidget/`GLCompositorWidget` physical presentation;
- old compositor scheduling/presentation glue;
- unsupported software/backend-demotion presenter fallback;
- obsolete `hw_accel`/fallback-overlay policy;
- remaining old physical-host transition/visualizer pixels/glue;
- temporary legacy anchors whose destination ownership now exists;
- presentation-only tests/tools/private probes with no destination meaning.

Do not carry these to I merely because deletion feels risky. I is residue, not a second cutover phase.

## 11. H proof bar vs J

H must prove enough to safely establish sole Quick production authority:

- 1 and 2+ runtime construction with exact QScreen identity;
- one `QuickDisplayRuntime` / one `QQuickWindow` per selected display;
- one intended `WidgetRuntimeManager`/service owner chain;
- image + transition routing through Quick APIs;
- retained ordinary families admitted once;
- G input/CUSTOM/auxiliary/context attached once;
- visualizer viewport config: committed baseline + committed nonbaseline + live CUSTOM override + Save + Cancel + slot replay;
- generation 0 and replacement generation behavior, including viewport rehydration before use;
- repeated construct/close without stale callbacks or duplicate owners;
- topology-loss path quiesces old generation;
- caller proof permits old-host deletion.

J still owns comprehensive compiled/installed physical acceptance: mixed refresh/DPR, off/wake, real Winlogon/MC, full
eyes-on parity, the deferred all-five-mode baseline/wide/tall visualizer viewport matrix, performance tails and clean
installed shutdown.

## 12. Rejected H shortcuts

Do not:

- run old and Quick production presenters in parallel "temporarily";
- add a `DisplayWidget` compatibility facade around `QuickDisplayRuntime`;
- keep an old software/compositor fallback after cutover;
- create a second `WidgetRuntimeManager` because the Quick host needs a registry;
- move provider/business logic into QML;
- preserve caller-dead QWidget pixels to keep pre-H startup working;
- use sleeps instead of readiness;
- move live GL/render resources across QQuickWindows on topology changes;
- make shared `QQmlEngine` retain per-generation runtime models/items;
- directly block Python on threaded render-loop destruction;
- treat `CUSTOM inactive` as synonymous with `viewport extent = canonical`;
- let ordinary presentation publication silently overwrite a live CUSTOM viewport override.

## 13. GREEN definition

H is GREEN when normal production orchestration creates only the Quick runtime chain, semantic owner cardinality is correct,
all corrected G configuration/input/auxiliary owners are bound once, generation/lifecycle tests are clean, committed and
CUSTOM-overridden viewport configuration survives its lifecycle matrix, and the remaining old physical presenter is deleted
with caller proof.
