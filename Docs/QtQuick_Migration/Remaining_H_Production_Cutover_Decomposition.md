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
        -> ordinaryWidgetHost / transition / CUSTOM / auxiliary retained scene
        -> zero-or-one admitted visualizer edge for this display
            -> exactly one product-level visualizer owner across participating displays
            -> VisualizerRuntimeController + controller-owned logical tick state/config
            -> sole VisualizerLogicalRuntime / mode logical runtime
            -> immutable latest logical publication
            -> GUI/Quick presentation synchronization owner
            -> complete VisualizerRenderSnapshot -> existing bridge -> retained visualizer item
```

No parallel legacy production manager/presenter is permitted.

## 3. Migration source seam

The production `engine/display_manager.py` collection constructor routes selected `QScreen` identities to
`QuickDisplayUnit`; it must not regain a legacy constructor branch. Caller-dead `DisplayWidget` / old physical-host cleanup,
tests and source may remain only as deletion scaffolding until step 6 proves they are unreachable. Inspect exact callers rather
than preserving a stale private-attribute inventory or turning that scaffold into a compatibility surface.

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
- one accepted-image-batch transition selection shared across selected displays, with per-display immutable image values;
- coordinated readiness/reveal/outward engine signals;
- coordinated exit and display replacement.

Replace assumptions that require QWidget/compositor internals with a small semantic DisplayManager/display-unit contract.
Do not make `QuickDisplayRuntime` or `QuickDisplayUnit` emulate arbitrary `DisplayWidget` private attributes, do not create
one-for-one forwarding methods merely to minimize diff size, and do not spread concrete Quick implementation internals across
engine call sites.

Transition settings are resolved once by the display orchestrator after engine Random admission. That resolved value is not a
second factory or presenter: each display unit combines it only with its own immutable current/destination images and starts
the existing retained `QuickTransitionController`. Accepted-image/current-image truth changes at destination finalization,
not request construction or transition start; an inadmissible Random choice publishes no substitute transition.

## 5. Cutover order

The bounded visualizer pre-cutover gate is a **closed prerequisite**, not an active step in this decomposition. Its audit trail
remains in `H_Pre_Cutover_Visualizer_Edge_Corrections.md` and `H_True_F_Technical_Closure.md`; do not reopen it without exact
regression evidence.

1. **Inventory DisplayManager's exact external product contract.** Separate real engine/display semantics from
   `DisplayWidget` implementation probes.
2. **Convert the semantic DisplayManager/engine caller surface in bounded checkpoints.** Move callers away from concrete
   QWidget/compositor assumptions toward the durable display-unit contract.
3. **Commit the production authority topology to Quick.** Replace the collection's concrete presenter type without a parallel
   production presenter, throwaway legacy-only decoupling architecture or `DisplayWidget` compatibility facade.
4. **Wire the remaining product semantics exactly once:** outward input/actions, image + transition routing, ordinary family
   admission/services, CUSTOM/context/auxiliary state, the single admitted visualizer, readiness and topology/generation
   replacement.
5. **Prove readiness/lifecycle/generation replacement** with deterministic/runtime-shaped one- and multi-display tests owned by
   the current H destination profile.
6. **Delete old physical-host callers and source** once caller proof shows the Quick destination is the only production route.

"Coordinated" or "atomic" cutover describes the **finished authority topology**, not the size of one coding session or commit.
The conversion may span as many explicit checkpoints as needed, including intentionally non-runnable intermediate migration
states, provided no checkpoint invents two legitimate production authorities or a fake legacy compatibility presenter.

## 6. Visualizer logical/configuration + synchronization ownership

The visualizer must not require a live QWidget to perform authored logical work, apply any configuration consumed by authored
logical/frame-runtime evolution, or deliver a completed immutable frame to Quick.

Durable split:

```text
canonical settings / resolved activation / preset
-> resolved technical cache
   -> engine/DSP inputs -> controller-owned shared BeatEngine/audio-worker boundary
   -> authored-logical technical-origin inputs -> controller-owned VisualizerLogicalTickState
-> other consumer-driven resolved logical/runtime configuration
-> VisualizerRuntimeController + controller-owned logical tick state
-> one VisualizerLogicalRuntime
-> latest immutable VisualizerLogicalFrame

canonical presentation settings + committed geometry/CUSTOM override + one fade authority
-> GUI/Quick presentation synchronization owner
-> complete ResolvedVisualizerPresentation
-> VisualizerRenderSnapshot
-> existing VisualizerSnapshotBridge
-> retained Quick visualizer item/node
```

Rules:

- the logical runtime step advances against controller-owned state, not `logical_tick(widget)`;
- **configuration ownership is decided by the actual consumer**: if Spectrum/Oscilloscope/Sine/Bubble/DevCurve authored
  evolution or a mode-owned frame runtime reads a value, that value must be available from presentation-neutral resolved
  logical/runtime configuration; renderer-only colours/glow/chrome/card/layout remain presentation-owned;
- do not move all legacy widget fields into the controller merely to eliminate attribute errors; prefer narrow resolved
  per-mode configuration/state;
- the Settings label "technical" is provenance, not ownership: DSP/capture values go to the one shared engine boundary while
  technical-origin values read by authored logical evolution go to controller-owned logical state;
- bar-count technical changes keep controller authority, the shared engine reconfiguration/generation and logical display-bar
  mirror/freshness state coherent; legacy overlay-only mirrors get no destination copy without a real retained consumer;
- one BeatEngine/source/logical runtime/mailbox/render bridge cardinality remains binding;
- binding or directly draining the bridge is not sufficient. One GUI/Quick synchronization owner must take the freshest
  logical publication, fence identity, resolve presentation state once, compose `VisualizerRenderSnapshot`, publish the
  existing bridge, commit that same presentation to the retained item, and request retained presentation without another
  clock/FIFO/paint acknowledgement;
- legacy widget adapters may temporarily delegate to neutral state/configuration before cutover, but are not a fallback and
  retire with the widget;
- no QML/QQuickItem/QScreen/render-thread object enters logical state/configuration;
- the Quick destination must not call legacy `present_tick()` or QWidget-only reveal/shadow/layout/compositor push paths.

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

## 7A. Visualizer product admission and semantic action ownership

Current product semantics admit one visualizer instance routed to one participating display. A `QuickDisplayUnit` therefore
must not construct a visualizer controller merely because that display exists.

Before visualizer owner construction, resolve:

```text
canonical enabled/activation + requested visualizer monitor
+ participating QuickDisplayUnits
+ committed/CUSTOM display-scoped geometry
-> exactly one admitted visualizer display owner
```

Preserve requested-display preference and existing cautious fallback/transfer semantics. Non-owning displays construct no
duplicate visualizer controller/source/logical runtime. The chosen display/unit owns retirement ordering for its visualizer
edge.

Retained semantic input must also preserve:

```text
double-click visualizer -> cycle visualizer mode
unhandled display double-click -> next image
```

Quick/QML may provide the hit region; Python remains semantic mode-cycle authority. Do not add a second global mouse router.

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

For a display that owns the admitted visualizer, visualizer publication closes and the sole authored logical runtime must
stop/join **before** Quick runtime/window terminal retirement proceeds. A failed join is a failed generation-retirement
barrier: retain ownership and fail the transition rather than reporting successful retirement while non-daemon work survives.

`SharedCtrlCoordinator` is currently contribution-keyed by screen identity/index. The cutover must prove old/new generations
for the same screen cannot overlap while contributions are live; if overlap is introduced by the exact implementation,
generation-qualify that contribution or otherwise prove stale retirement cannot clear the replacement contribution. Do not
refactor this speculatively when the destruction barrier already proves non-overlap.

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

- one- and multi-display deterministic/runtime-shaped construction with coherent display identity; exact operator-hardware
  `QScreen` identity/topology cells remain J physical evidence;
- one `QuickDisplayRuntime` / one `QQuickWindow` per selected display;
- one intended `WidgetRuntimeManager`/service owner chain;
- image + transition routing through Quick APIs;
- retained ordinary families admitted once;
- G input/CUSTOM/auxiliary/context attached once;
- exactly one product-level visualizer owner is admitted across participating displays; its controller constructs/configures/
  starts/advances without a QWidget host;
- canonical technical settings reach the one shared BeatEngine or controller-owned authored-logical state according to actual
  consumer, including coherent bar-count reconfiguration;
- all-five logical/runtime settings reach their actual authored consumers without widget-only attributes;
- one GUI/Quick synchronization owner turns latest logical publication + one resolved presentation record into a complete
  `VisualizerRenderSnapshot`, publishes the existing bridge and proves consumption through the retained Quick item/node;
- retained visualizer double-click cycles visualizer mode before the global next-image fallback;
- failed logical-runtime join blocks visualizer/display generation retirement;
- visualizer viewport config: committed baseline + committed nonbaseline + live CUSTOM override + Save + Cancel + slot replay;
- generation 0 and replacement generation behavior, including viewport rehydration before use;
- repeated construct/close without stale callbacks or duplicate owners;
- topology-loss path quiesces old generation;
- caller proof permits old-host deletion.

J still owns comprehensive compiled/installed physical acceptance: exact real-display identity, add/remove/reorder topology,
mixed refresh/DPR, off/wake, real Winlogon/MC, full eyes-on parity, the deferred all-five-mode baseline/wide/tall visualizer
viewport matrix, performance tails and clean installed shutdown. Physical source-mode smoke cells may be useful early evidence,
but they are not the deterministic H authority-flip gate.

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
all corrected G configuration/input/auxiliary owners are bound once, and the single admitted visualizer is fully widget-free
from canonical configuration through logical publication, GUI/Quick snapshot composition and retained Quick consumption. The
visualizer must preserve semantic mode-cycle input, hard successful logical-runtime join retirement, committed/CUSTOM viewport
lifecycle and generation fencing. Generation/lifecycle tests must be clean, and the remaining old physical presenter must be
deleted with caller proof.
