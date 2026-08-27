# Remaining H — Production Quick Cutover Technical Decomposition

Status: **execute after G is GREEN**  
Checkpoint basis: `59f4a3c98235215a9ff89fc09e4cc979d1831e89`  
Work admission: `Current_Plan.md`

H is final production owner/orchestration wiring plus old physical-host deletion. It is not a second family migration and
not a requirement to restore the half-migrated legacy application before switching.

## 1. Destination chain

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

## 2. Current source seam

At the checkpoint, `engine/display_manager.py` still imports/creates `DisplayWidget` and stores `self.displays` as legacy
widgets. That is the primary H routing seam.

The destination runtime is already real:

- `rendering/quick/runtime.py` — per-display generation owner;
- `rendering/quick/window.py` — exact physical QQuickWindow;
- `rendering/quick/scene_controller.py` — sole retained scene item creator/destructor;
- `rendering/widget_runtime_manager.py` — presentation-neutral capability/lifecycle/service owner;
- migrated family models/presentations and neutral service leases from F;
- retained G CUSTOM/input/auxiliary/context owners.

H should connect those pieces; it should not create replacement versions of them.

## 3. Keep DisplayManager responsibilities, replace presenter assumptions

DisplayManager remains responsible for product-level display orchestration such as:

- QScreen enumeration and allowed-monitor selection;
- topology reconciliation;
- runtime-generation/display collection ownership;
- current-image routing;
- coordinated readiness/reveal/outward engine signals;
- coordinated exit and display replacement.

Replace assumptions that require QWidget/compositor internals with narrow `QuickDisplayRuntime` APIs/signals. Do not make
`QuickDisplayRuntime` emulate arbitrary `DisplayWidget` private attributes just to minimize diff size.

## 4. Suggested cutover order

1. **Inventory DisplayManager's actual external contract.** List methods/signals consumed by the engine/tests. Separate
   product orchestration from `DisplayWidget` implementation probes.
2. **Make the runtime collection presenter-neutral.** It should be able to own `QuickDisplayRuntime` instances without
   lying about them as QWidget objects.
3. **Construct one shared/process Quick scene factory at the proper owner boundary** and one `QuickDisplayRuntime` per
   selected QScreen/generation.
4. **Wire outward input/action signals** from each Quick runtime to the same product-level DisplayManager/engine actions.
5. **Wire base image + transition routing** through explicit Quick APIs; remove compositor/private-widget pokes.
6. **Attach exactly one display-owned `WidgetRuntimeManager`.** Reuse the neutral capability/service ownership already
   migrated in E/F; do not instantiate a legacy manager in parallel.
7. **Resolve ordinary family admission once** from capability effectiveness + ordinary ON/OFF/instances, then bind stable
   presentation models into `QuickSceneController`/`ordinaryWidgetHost`.
8. **Bind G owners**: CUSTOM session/actions, layout slots, context/auxiliary/input state through their existing explicit
   runtime APIs.
9. **Prove readiness/lifecycle/generation replacement** with runtime-shaped tests.
10. **Delete old physical-host callers and source** once the destination is the only production route.

Do not perform step 10 by leaving dead compatibility shims that merely forward dozens of `DisplayWidget` private names.

## 5. WidgetRuntimeManager cardinality

`WidgetRuntimeManager` is presentation-neutral and may retain provider/model service ownership while presenter bindings
change. H must preserve exactly one intended runtime owner per display/generation.

Rules:

- no legacy `WidgetManager` + Quick host each creating their own neutral manager;
- no duplicate provider/controller/service construction because both old/new presenters briefly exist;
- activation and dependency satisfaction remain distinct from ordinary instance `enabled` state;
- service build/injection failures continue to fail closed; do not fall back to a QWidget-owned provider;
- retirement detaches/retire services exactly once according to existing neutral contracts.

If a Quick presentation host needs a small registry/host adapter for `WidgetRuntimeManager`, make it explicit and
presentation-neutral. Do not make the neutral manager own QML items.

## 6. Generation/lifecycle order

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
-> publish intentional initial content
-> reveal when explicit readiness is true
```

`QuickDisplayRuntime.close_runtime()` already encodes important ordering and queues window/resource retirement to avoid
blocking Python against the threaded render loop. Do not replace it with direct GUI-thread GL/resource destruction.

A topology change rebuilds a generation on the target QScreen; do not move live render resources between windows.

## 7. Readiness

Do not translate old compositor flags into arbitrary sleeps.

Use explicit Quick readiness facts already exposed by runtime/scene:

- QML root created;
- scene graph initialized;
- background renderer ready;
- intentional base frame ready;
- admission open;
- no scene graph invalidation/error.

DisplayManager may aggregate those facts across selected displays. A fixed delay, black placeholder, stale previous
texture or "window exists" alone is not readiness.

## 8. Physical-host deletion boundary

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

## 9. H proof bar vs J

H must prove enough to safely establish sole Quick production authority:

- 1 and 2+ runtime construction with exact QScreen identity;
- one QuickDisplayRuntime / one QQuickWindow per selected display;
- one intended WidgetRuntimeManager/service owner chain;
- image + transition routing through Quick APIs;
- retained ordinary families admitted once;
- G input/CUSTOM/auxiliary/context attached once;
- generation 0 and replacement generation behavior;
- repeated construct/close without stale callbacks or duplicate owners;
- topology-loss path quiesces old generation;
- caller proof permits old-host deletion.

J still owns comprehensive compiled/installed physical acceptance: mixed refresh/DPR, off/wake, real Winlogon/MC,
full eyes-on parity, performance tails and clean installed shutdown.

## 10. Rejected H shortcuts

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
- directly block Python on threaded render-loop destruction.

## 11. GREEN definition

H is GREEN when normal production orchestration creates only the Quick runtime chain, semantic owner cardinality is
correct, generation/lifecycle tests are clean, and the remaining old physical presenter is deleted with caller proof.
