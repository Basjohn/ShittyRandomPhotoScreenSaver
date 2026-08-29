# Remaining H — Production Quick Cutover Technical Decomposition

Work admission and live checkpoint: `Current_Plan.md`  
Source basis: inspect exact current source before execution; this decomposition owns durable H destination boundaries rather
than transient checkpoint status.

H is final production owner/orchestration wiring plus old physical-host deletion. It is not a second family migration and
not a requirement to restore the half-migrated legacy application before switching.

## 1. Authority rule

`Current_Plan.md` decides whether H is admitted and what slice is next. Do not copy live phase/checkpoint status into this
file. If exact source exposes a missing durable ownership seam, close that seam under the destination contracts before the
production flip rather than inventing compatibility behavior.

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
        -> one VisualizerRuntimeController
            -> controller-owned logical tick state
            -> sole VisualizerLogicalRuntime / mode logical runtime
            -> immutable/latest render publication
        -> ordinaryWidgetHost / visualizer / transition / CUSTOM / auxiliary retained scene
```

No parallel legacy production manager/presenter is permitted.

## 3. Migration source seam

Before production cutover, source may still route through `engine/display_manager.py` -> legacy `DisplayWidget` / old
physical host. Treat that as migration scaffolding, not destination architecture. Inspect exact callers before cutover rather
than preserving a stale private-attribute inventory.

Reuse destination owners that already exist; do not create parallel replacements:

- `rendering/quick/runtime.py` — per-display generation owner;
- `rendering/quick/window.py` — exact physical `QQuickWindow`;
- `rendering/quick/scene_controller.py` — sole retained scene item creator/destructor;
- `rendering/widget_runtime_manager.py` — presentation-neutral capability/lifecycle/service owner;
- migrated family models/presentations and neutral service leases from F;
- retained G CUSTOM/input/auxiliary/context owners;
- visualizer runtime controller + controller-owned logical state/runtime + snapshot bridge + viewport-configuration seam.

H should connect those owners; it should not create replacement versions of them.

## 4. Keep DisplayManager responsibilities; replace presenter assumptions

DisplayManager remains responsible for product-level display orchestration such as:

- QScreen enumeration and allowed-monitor selection;
- topology reconciliation;
- runtime-generation/display collection ownership;
- current-image routing;
- coordinated readiness/reveal/outward engine signals;
- coordinated exit and display replacement.

Replace assumptions that require QWidget/compositor internals with a small semantic DisplayManager/display-unit contract.
Do not make `QuickDisplayRuntime` or `QuickDisplayUnit` emulate arbitrary `DisplayWidget` private attributes, do not create
one-for-one forwarding methods merely to minimize diff size, and do not spread concrete Quick implementation internals across
engine call sites.

## 5. Cutover order

1. **Inventory DisplayManager's exact external product contract.** Separate real engine/display semantics from
   `DisplayWidget` implementation probes.
2. **Prove the visualizer destination owner is self-sufficient before the flip.** A fresh `VisualizerRuntimeController` must
   be constructible/configurable/startable without `SpotifyVisualizerWidget`; its logical step advances against
   controller-owned state, and logical/runtime settings use presentation-neutral configuration authority. Visual-only styling
   stays presentation-owned.
3. **Bind the thin Quick visualizer edge.** Per intended display/generation, bind the existing controller's immutable render
   source and viewport configuration into `QuickDisplayRuntime`; prove generation replacement/retirement with one
   engine/source/logical owner and no hidden widget.
4. **Perform the DisplayManager + engine conversion as one coordinated production cutover.** Move engine callers onto the
   durable semantic DisplayManager/display-unit contract while replacing the collection's concrete presenter type. Do not land
   a half-swapped production state, a throwaway legacy-only decoupling layer or a compatibility facade.
5. **Wire the remaining product semantics exactly once:** outward input/actions, image + transition routing, ordinary family
   admission/services, CUSTOM/context/auxiliary state, readiness and topology/generation replacement.
6. **Prove readiness/lifecycle/generation replacement** with runtime-shaped tests for one and multiple displays.
7. **Delete old physical-host callers and source** once caller proof shows the Quick destination is the only production route.

## 6. Visualizer logical/configuration ownership

The visualizer must not require a live QWidget to perform authored logical work or apply logical/runtime configuration.
Durable split:

```text
canonical settings / resolved activation
-> one presentation-neutral logical/runtime configuration authority
-> VisualizerRuntimeController + controller-owned logical tick state
-> one VisualizerLogicalRuntime

visual-only styling/chrome/layout
-> Quick presentation state/model/render contract
```

Rules:

- the logical runtime step advances against controller-owned state, not `logical_tick(widget)`;
- controller-owned state may delegate engine/source/generation identity back to the controller, but it is not a second owner;
- one BeatEngine/source/logical runtime/mailbox/render bridge cardinality remains binding;
- technical/runtime configuration may live with controller/runtime ownership; visual colours, glow, borders, card/layout/fade
  presentation do not migrate into logical state merely because legacy code stored them on the same widget;
- legacy widget adapters may temporarily delegate to neutral state/configuration before cutover, but are not a fallback and
  retire with the widget;
- no QML/QQuickItem/QScreen/render-thread object enters logical state/configuration.

## 7. Visualizer viewport-configuration binding

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

## 8. WidgetRuntimeManager cardinality

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

## 9. Generation/lifecycle order

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

## 10. Readiness

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

## 11. Physical-host deletion boundary

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

## 12. H proof bar vs J

H must prove enough to safely establish sole Quick production authority:

- 1 and 2+ runtime construction with exact QScreen identity;
- one `QuickDisplayRuntime` / one `QQuickWindow` per selected display;
- one intended `WidgetRuntimeManager`/service owner chain;
- image + transition routing through Quick APIs;
- retained ordinary families admitted once;
- G input/CUSTOM/auxiliary/context attached once;
- visualizer controller constructs/configures/starts/advances without a QWidget host and binds exactly once to Quick;
- visualizer viewport config: committed baseline + committed nonbaseline + live CUSTOM override + Save + Cancel + slot replay;
- generation 0 and replacement generation behavior, including viewport rehydration before use;
- repeated construct/close without stale callbacks or duplicate owners;
- topology-loss path quiesces old generation;
- caller proof permits old-host deletion.

J still owns comprehensive compiled/installed physical acceptance: mixed refresh/DPR, off/wake, real Winlogon/MC, full
eyes-on parity, the deferred all-five-mode baseline/wide/tall visualizer viewport matrix, performance tails and clean
installed shutdown.

## 13. Rejected H shortcuts

Do not:

- run old and Quick production presenters in parallel "temporarily";
- add a `DisplayWidget` compatibility facade around `QuickDisplayRuntime`;
- keep an old software/compositor fallback after cutover;
- create a second `WidgetRuntimeManager` because the Quick host needs a registry;
- move visual-only visualizer settings/chrome/layout into `VisualizerRuntimeController` logical state;
- move provider/business logic into QML;
- preserve caller-dead QWidget pixels to keep pre-H startup working;
- use sleeps instead of readiness;
- move live GL/render resources across QQuickWindows on topology changes;
- make shared `QQmlEngine` retain per-generation runtime models/items;
- directly block Python on threaded render-loop destruction;
- treat `CUSTOM inactive` as synonymous with `viewport extent = canonical`;
- let ordinary presentation publication silently overwrite a live CUSTOM viewport override.

## 14. GREEN definition

H is GREEN when normal production orchestration creates only the Quick runtime chain, semantic owner cardinality is correct,
the visualizer logical/configuration owner is widget-free and bound once, all corrected G configuration/input/auxiliary owners
are bound once, generation/lifecycle tests are clean, committed and
CUSTOM-overridden viewport configuration survives its lifecycle matrix, and the remaining old physical presenter is deleted
with caller proof.
