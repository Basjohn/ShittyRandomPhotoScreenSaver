# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-29

## Current checkpoint

The documentation is reconciled through independently audited pushed source plus the current test-maintenance worktree:

```text
5f33d300 (True-F closure + Settings/test-suite reconciliation landed on pushed main)
current worktree: final H-profile target isolation / H-vs-J runtime-test classification reconciled
True-F focused gate: 7/7 GREEN
Settings-overhaul focused reconciliation: 154/154 GREEN
H destination profile: 57/57 target-isolated GREEN
Complete G: independently audited and ACCEPTED.
H: ACTIVE. The pre-cutover visualizer destination-edge correction gate is CLOSED.
CURRENT H implementation target: coordinated DisplayManager + engine authority cutover.

Accepted H foundation through this checkpoint:
- one WidgetRuntimeManager per QuickDisplayRuntime generation;
- full seven-family OrdinaryFamilyPresentationBinder;
- capture_qpixmap / immutable image-routing seam;
- option-A outer-geometry mechanism and historical per-family preferred-size policies;
- thin QuickDisplayPresenter;
- authoritative SharedCtrlCoordinator;
- QuickDisplayUnit per-display destination-chain assembly;
- visualizer per-tick logical state owned by VisualizerRuntimeController;
- VisualizerLogicalRuntime advances against controller-owned state without SpotifyVisualizerWidget;
- immutable visualizer render contracts / bridge and Quick render consumers exist;
- QuickDisplayVisualizerOwner exists as a thin display/generation edge and can construct/bind/start a widget-free controller.
- visualizer technical configuration is presentation-neutral: the controller/shared BeatEngine receives resolved technical
  settings without `SpotifyVisualizerWidget`, while technical values consumed by authored evolution live on controller-owned logical state;
- `QuickVisualizerPresentationSync` commits the exact resolved presentation embedded in the published snapshot to the retained
  `VisualizerRenderItem`, and the retained item is proven to consume that snapshot.

Pre-cutover audit disposition — ALL GREEN (`Docs/QtQuick_Migration/H_Pre_Cutover_Visualizer_Edge_Corrections.md`):
- ACCEPT the widget-free logical/source ownership extraction; do not reopen or roll it back.
- GREEN (A): `QuickVisualizerPresentationSync` is the one GUI/Quick synchronization owner - drains the latest logical
  publication, rejects stale generation/engine/activation/mode identity, resolves the complete presentation, composes and
  publishes `VisualizerRenderSnapshot` into the existing bridge. `QuickDisplayVisualizerOwner.sync_present()` drives it.
- GREEN (B): all-five authored-logical config (Spectrum/Oscilloscope/Sine/DevCurve inputs consumed by each mode's
  `*FrameRuntime.resolve` / DevCurve field solve) is owned by `VisualizerLogicalTickState` via the single neutral authority
  `apply_logical_vis_mode_kwargs`. Classification is by actual consumer, not naming.
- GREEN (F): the pure renderer/presentation-only subset is owned by a symmetric neutral `VisualizerPresentationState`, fed by
  the single authority `apply_presentation_vis_mode_kwargs`. The later True-F closure additionally proves canonical technical
  settings resolve without QWidget, apply through the controller-owned shared BeatEngine, authored-logical technical inputs
  reach controller-owned state, bar-count reconfiguration stays coherent, and the retained `VisualizerRenderItem` consumes the
  exact synchronized snapshot/presentation. `tests/test_qtquick_visualizer_true_f_gate.py`: **7/7 GREEN** on the current worktree.
- GREEN (C): `QuickDisplayVisualizerOwner.retire()` is a hard join barrier - a failed stop/join keeps ownership and fails
  retirement (retryable); a stop exception propagates; only a successful join retires.
- GREEN (D): `rendering/quick/visualizer_admission.py` resolves exactly one admitted visualizer display owner from
  participating Quick units (requested-if-participating, else cautious hold, else stable fallback); non-owning units build none.
- GREEN (E): the retained visualizer joins the semantic double-click hit/action admission before the global next-image
  fallback (`rendering/quick/visualizer/double_click_admission.py`; scene controller binds the composed hit test).

Next H boundary:
- perform the coordinated DisplayManager + engine authority cutover, then caller-proven legacy physical-host deletion (below).
```

Exact later source always outranks this document. **All of G remains complete, independently audited and accepted. The
bounded pre-cutover visualizer destination-edge correction gate is CLOSED, so the DisplayManager production authority cutover is
now the current H implementation target.** Deferred to J installed acceptance: the all-five-mode visualizer eyes-on gate and the physical two-display A->B->A
hardware-ingress matrix.

The pre-cutover test-authority maintenance pass is **complete enough for H**. The large Settings GUI/theme overhaul is now
covered by reconciled current-owner tests (**154/154 GREEN**), and the maintained H destination profile is **57/57 GREEN**
under target-isolated subprocess execution. The earlier whole-tree/chunk noise was traced to stale legacy-owner tests plus
Qt/QQuick cross-test lifecycle contamination; it is not an unresolved H architecture defect. `Docs/TestSuite.md` now owns the
current H-vs-I/J test classification.

Two real-physical-display cells in `tests/test_qtquick_runtime.py` remain intentionally outside the per-commit H destination
profile: exact two-screen identity and three-generation add/remove topology recreation. They remain valuable tests, but they
exercise the operator's actual `QScreen` hardware/topology and therefore belong to the existing **J physical acceptance matrix**.
Do not use those J cells to delay the production authority flip, and do not weaken/delete them merely to manufacture an H pass.

Current phase state:

```text
F0–F8   ordinary-family migration                         CLOSED
G1      neutral CUSTOM session / variants / layout slots CLOSED
G2      retained edit overlay / X / family binding       CLOSED
G3      Save/Cancel + enabled/duplicate persistence      CLOSED
G4      viewport-extent implementation                   DETERMINISTIC COMPLETE; eyes-on deferred (after H)
G5      retained cross-display transfer                  CLOSED
G6      retained input / semantic family actions         CLOSED
G7      retained context + auxiliary pixels              CLOSED (destination sole aux; legacy = H-scaffolding)
G8      MC / focus closure                               DETERMINISTIC CLOSED; physical A->B->A matrix = J debt
G-GATE  independent audit of complete checkpointed G     ACCEPTED
H       production Quick owner/orchestration cutover     ACTIVE; destination gate 57/57 GREEN, DisplayManager cutover CURRENT
I       residue only                                     after H
J       final installed / physical validation            final
```

## G4 post-checkpoint audit corrections — COMPLETE

The bounded correction batch from
`Docs/QtQuick_Migration/G4_Post_Checkpoint_Audit_Corrections_Decomposition.md` is landed, test-gated and pushed:

- **A** committed vs temporary CUSTOM working viewport extent split in the runtime controller (override wins only while
  CUSTOM is active; retiring falls back to committed, never manufactured canonical; ordinary republish cannot erase the
  override); owner-shaped Save/Cancel/precedence tests;
- **B** overlap-retry clamp now uses the actual logical domain (`[-0.25, domain+0.25]`), baseline exactly `[-0.25, 1.25]`;
- **C** contraction retires non-surface off-domain bubbles through the existing pop/death path (surface still exits/drains,
  interior untouched, no rescale/teleport, fires only on an actual contraction);
- **D** specular `spec_ox`/`spec_oy` proven dimensionless local bubble-space offsets (applied as `spec_ox * r` in the shader);
  left unprojected, documented and locked by a payload + shader-source test;
- misleading "baseline density" wording removed.

Baseline stays byte-identical; BTF/replay/cadence/reactivity/transport goldens remain green with no tuning/golden/count
changes. G4 is **deterministic implementation complete, physical acceptance deferred** (see below).

## Deferred G4 physical acceptance

The final all-five-mode baseline/wide/tall eyes-on gate remains required, but is deliberately deferred until the Quick runtime
is production-authoritative enough to inspect honestly.

After H, physically check at minimum:

```text
Spectrum      baseline / wide / tall
Oscilloscope  baseline / wide / tall
Sine          baseline / wide / tall
Bubble        baseline / wide / tall / representative shrink
DevCurve      baseline / wide / tall
```

For Bubble specifically verify circles, apparent size, speed, distribution, trails, collision feel, specular placement and
BTF continuity. Installed/manual evidence can reject deterministic implementation if the result looks materially wrong.

Do not build legacy compatibility presentation solely to inspect this before H.

## G7 and G8 — CLOSED (deterministic)

**G7 closed.** The retained Quick scene is the sole destination context/dimming/pixel-shift/halo presentation; Python remains
semantic/settings authority (tests forbid QML settings/provider ownership). A caller audit classified every legacy auxiliary
owner (`widgets/context_menu.py`, `widgets/cursor_halo.py`, `rendering/display_context_menu.py`, `widgets/pixel_shift_manager.py`,
DisplayWidget helpers): all are live only through the production legacy `DisplayWidget` path (`engine/display_manager.py`), so
they are **required physical-host scaffolding for H**, not caller-dead debris — there is no dual-run because the Quick runtime
is not yet the production presenter. They retire wholesale at the H cutover. Menu `context_menu_active` suppression is proven to
release on every close path (action / dismiss / retirement).

**G8 deterministically closed.** Fixed a real cross-display stuck-Ctrl defect (the coordinator is now authoritative in
`QuickInputController`, isolated from the legacy `InputHandler`). MC window role/policy (no taskbar/Alt-Tab, topmost, distinct
`QuickWindowRole`) is preserved and test-locked; retained family double-click actions declare fallback admission so the global
next-image fallback stays exclusive; generation replacement rejects stale input; the halo derives from live input state and
follows the (unstuck) Ctrl clear. No forbidden focus mechanism was introduced (no focus-policy tree mutation, focus-shadow
invalidation, top-level halo, or per-family key router).

The **physical two-display A->B->A hardware matrix** (real focus/Ctrl/hardware-key ingress across displays) and the
**all-five-mode visualizer eyes-on gate** are explicitly deferred to J installed acceptance (see below); do not fabricate a
physical-ingress pass from synthetic Qt events.

Route reference: `Docs/QtQuick_Migration/Remaining_G7_G8_Auxiliary_Focus_Decomposition.md`.

## Independent G audit — ACCEPTED

The complete checkpointed G state passed the required independent audit. That gate is satisfied and does not create any
further stop before or during ordinary GREEN H work.

The implementation loop remains:

```text
inspect exact source
-> bounded implementation
-> focused tests
-> diff/status
-> commit/push
-> fresh post-push self-audit
-> continue when GREEN
```

Implementation agents should **not stop merely to request user attention between GREEN slices** while the next task is known,
bounded, testable and consistent with the binding contracts.

A stop is required only for a real blocker, for example:

- RED or unresolved YELLOW evidence that cannot be resolved from exact source/tests;
- a required product/semantic decision not owned by existing docs;
- a change that would violate a hard destination invariant;
- evidence that the requested correction requires a new clock, new accelerated surface, new persistence authority or other
  prohibited architecture;
- explicit user instruction to stop.

H remains independently audit-sensitive because it is the production owner cutover, but **H is admitted**. Architecture-
sensitive H work still demands stronger tests and self-audit; it does not by itself create a user-attention stop.

Do not run routine hosted CI or full/Nuitka/installed builds during ordinary migration implementation.

## Destination invariants

```text
one selected physical display
-> one QuickDisplayRuntime
-> one standalone threaded QQuickWindow
-> one retained Quick scene
-> inline QSGRenderNode custom GL where required
```

Hard:

- no `QQuickWidget` runtime presenter;
- no second accelerated widget/visualizer/effect window;
- no permanent QWidget/QRhi fallback presenter;
- no QWidget screenshot-to-texture compatibility architecture;
- providers/backends/persistence/cadence/business logic remain Python-owned;
- QML consumes bounded presentation state and emits semantic actions;
- common Quick imports do not eagerly activate inactive family backend/runtime trees;
- ordinary fade = one retained root opacity;
- ordinary text shadow = retained duplicate glyph + signed offset, no blur;
- ordinary card shadow = retained `OverlayCard` / cached `RectangularShadow`;
- global shadow direction resolves in Python;
- Visualizer authored logical cadence remains independent of presentation cadence;
- real provider/cache/network/transition/Visualizer resilience survives.

## CUSTOM contracts already landed and still binding

Geometry key supports `(widget_id, display_identity, geometry_variant)`; Clock digital/analogue have independent committed
rects without drift.

Visualizer geometry has two independent authored operations:

```text
wheel/corners -> uniform_visual_scale
edges         -> viewport_extent
```

Neither operation may silently mutate the other.

Every adjustable edit-mode card gets `X`:

- duplicate -> remove that duplicate from working layout;
- singleton -> ordinary widget OFF, equivalent to its normal Settings checkbox;
- never family/capability deactivation;
- no immediate persistence or committed provider/runtime destruction.

Save/Enter commits; Cancel restores pre-edit geometry, duplicate set and ordinary enabled state.

Layout slots are ordinary visible-layout snapshots: `Shift+1`..`Shift+0` save and `1`..`0` load geometry/size plus ordinary
ON/OFF. Slot load may turn an effective family member ordinarily ON/OFF, but never activates a fully deactivated
family/capability and never overwrites provider/account/source settings.

Centering guides are red so display/peer-centre alignment is distinct from ordinary grid/edge guides.

## H — final production owner cutover

### H progress (landed, GREEN, pushed)

The family/runtime destination integration already landed and test-gated includes:

- `QuickDisplayRuntime` owns **exactly one** `WidgetRuntimeManager` per generation (H §7 cardinality): hostless
  construction, retired once before scene teardown, dropped at window destruction, replacement generations build their own.
- `rendering/quick/widgets/family_binder.py` — thin presentation-neutral `OrdinaryFamilyPresentationBinder` + one small
  adapter per family. It resolves admitted families (capability effectiveness via the single manager; per-instance `enabled`
  distinct), builds the existing `Retained*Presentation` items into the real `OrdinaryWidgetPresentationHost`, owns each
  family's neutral runtime service(s) through the manager (fail-closed on a missing required lease), and retires held items
  exactly once. All seven families are wired: Clock, Weather, Media, Reddit, Gmail, Achievement Pulse and Abandonment Issues.
  Geometry + shadow values are **injected seams**.
- `bind_visualizer_render_source` and `bind_visualizer_viewport_config` exist at the Quick runtime owner; corrected-G4
  committed/override viewport ownership remains binding.
- `capture_qpixmap` plus `rendering/quick/display_image_route.py` provide GUI-thread processed-pixmap -> immutable
  `PresentationImage` routing without passing live `QPixmap` state into the render thread.
- `rendering/quick/display_presenter.py` is the thin per-display ordinary-family + option-A geometry presenter. It owns no
  provider, cadence, window or persistence authority.
- `rendering/quick/ctrl_coordinator.py` provides one authoritative cross-display Ctrl truth and forgets retired display
  contributions.
- `rendering/quick/display_unit.py` assembles one display's destination chain from `QuickDisplayRuntime` +
  `QuickDisplayPresenter` + shared Ctrl coordination and exposes clean display operations rather than legacy-widget emulation.
- The first coordinated-cutover caller slice is landed: `DisplayManager.snapshot_processing_descriptors()` publishes ordered,
  immutable screen-identity/target-size/logical-size/mode/DPR inputs through the existing
  `rendering/quick/display_processing.py` authority; the image pipeline no longer retains/indexes concrete presenter objects
  for processing, prefetch or async publication and routes completed images through the manager/unit semantic API by actual
  screen identity. This is a durable destination contract, not a `DisplayWidget` facade.
- The follow-on engine-caller slice is landed: startup first-image admission, Media idle wake and lifecycle diagnostics now
  use semantic `DisplayManager` queries/operations. Engine handlers no longer inspect `current_image_path`, `media_widget`,
  `_ctrl_cursor_hint` or concrete display collections; generation teardown remains the sole auxiliary-pixel retirement owner.
- The destruction barrier now consumes an explicit `DisplayManager`/display-unit retirement-root contract. Quick units expose
  their runtime/window and plain-Python generation owners directly, and queue runtime-object deletion only after legal
  render-safe window retirement; the barrier no longer scrapes physical-presenter internals.
- `QuickDisplayUnit` now accepts only the one visualizer owner admitted upstream by `DisplayManager`; it never constructs one
  per display. The chosen unit includes that owner in its generation roots and hard-blocks runtime/window retirement until
  the authored logical runtime joins successfully.

### H geometry resolution — DECIDED (option A) and BUILT, GREEN, pushed

The ordinary-widget outer-geometry gate is resolved: **option A** (QML reports a size-only preferred content size; Python is
the sole outer-rect/anchor/clamp authority). Per the boundary correction, the deterministic per-family preferred-size
contract is **H work**; only final eyes-on visual parity is J. Landed:

- `rendering/quick/widgets/geometry_resolver.py` — pure `resolve_anchored_geometry` (reproduces the legacy
  `_update_position` content-size + anchor + margin + min-visible clamp, minus QWidget-era padding/pixel-shift artifacts),
  `OverlayGeometryPolicy` + `resolve_overlay_geometry_policy` (persisted `position`/`margin`, optional CUSTOM committed-rect
  override), `OverlayGeometryBinding` (content-size -> committed outer rect; identical-effective no-op; committed rect wins;
  re-anchors on display-bounds/topology change), and `connect_overlay_preferred_size` (wires the QML signal; no width
  feedback, no polling/timers/per-frame callbacks).
- QML contract: `OverlayWidget` exposes family-declared `preferredContentWidth/Height` + a size-only
  `preferredContentSizeChanged`; `OverlayCard` exposes `shellInset`. Every production family declares a real preferred size
  from intrinsic/config sources (never its assigned width).
- Historical size policies are honoured:
  - Weather / Reddit / Media: 600 px minimum width (`BaseOverlayWidget.DEFAULT_CARD_MIN_WIDTH`);
  - Gmail: authored width, default 600, clamped 200-1200;
  - Media: height floor `max(220, artwork_size + 60)`;
  - Clock analogue: authored natural geometry `width = max(160, font*4.5)`, `height = max(width, width*1.3)`;
  - Clock digital: content-driven intrinsic text; Steam cards: authored dimensions.

**Ownership DECIDED — option A:** content anchoring is **default placement only**. Existing CUSTOM committed rects and Clock
per-variant (digital/analogue) committed-rect ownership remain unchanged and override the binding completely. J later
validates/refines visual parity only.

### H visualizer widget-free destination ownership — ACCEPTED; correction gate CLOSED

The discovered logical-host prerequisite is genuinely closed and must **not** be reopened:

```text
VisualizerRuntimeController
-> controller-owned VisualizerLogicalTickState
-> VisualizerLogicalRuntime(step = logical_tick(controller-owned state))
-> mode logical runtime / immutable latest logical publication
```

That extraction preserved one authored logical clock, one engine/source authority and generation/activation fencing. The
legacy widget may delegate to controller-owned state while it remains pre-cutover scaffolding, but the authored logical step
no longer requires `SpotifyVisualizerWidget`.

The later pre-cutover audit found that this was only the **logical half** of destination completion. The following stronger
rules now supersede the earlier broad "visualizer runtime ownership correction complete" wording:

- logical/runtime configuration means **every setting consumed by authored logical evolution or a mode-owned logical frame
  runtime**, not only Bubble physics. The all-five consumer graph is authoritative.
- pure renderer/chrome/style values remain presentation-owned; do not dump all widget fields into the controller.
- a bound `VisualizerSnapshotBridge` is not proof of presentation delivery. One GUI/Quick synchronization owner must consume
  the freshest logical publication, apply current generation/activation/mode fencing, resolve complete presentation state,
  compose `VisualizerRenderSnapshot`, publish it to the bridge, and dirty/request the retained Quick visualizer item without
  adding another authored clock, FIFO or paint acknowledgement.
- current product semantics admit **one visualizer instance**. Exactly one participating Quick display owns its
  `QuickDisplayVisualizerOwner`/controller for the admitted activation; non-owning displays must not create duplicate
  visualizer controllers/engines merely because they have a `QuickDisplayUnit`.
- failed stop/join of the sole authored `VisualizerLogicalRuntime` blocks owner/generation retirement and therefore blocks
  Quick display retirement/replacement. Do not report success and continue teardown while that runtime remains owned.
- visualizer mode-cycle remains a semantic Python action reached through retained Quick hit admission; unhandled display
  double-click remains the global next-image fallback only after family/visualizer semantic regions decline the event.

**True-F closure is now accepted.** The post-gate audit found two final destination seams that the earlier all-five proof had
not actually exercised: widget-free technical engine application and retained-item consumption of the synchronized snapshot.
Those are now implemented by the neutral controller/shared-engine technical apply path plus exact-presentation commit at the
Quick synchronization edge. The focused regression gate `tests/test_qtquick_visualizer_true_f_gate.py` moved from the expected
2-pass/5-fail diagnostic state to **7/7 GREEN** without weakening the assertions. Do not reopen this boundary absent exact source
regression evidence.

### H PRE-CUTOVER correction gate — CLOSED; DisplayManager cutover CURRENT

The bounded correction route `Docs/QtQuick_Migration/H_Pre_Cutover_Visualizer_Edge_Corrections.md` is closed: steps 1–7
below are landed and test-gated (Findings A–F GREEN; see the checkpoint disposition above). The reconciled H destination
regression profile is also GREEN (**57/57 targets**). Steps 8–9 — the coordinated production-authority cutover and
caller-proven deletion — are therefore the remaining H work and are **CURRENT NOW**. The completed route and remaining order are:

1. **Correct all-five configuration ownership.** Inventory actual logical/frame-runtime consumers. Move only those consumed
   values behind presentation-neutral resolved configuration/state; keep renderer-only colour/glow/card/chrome values on the
   presentation side. Preserve existing authored values and semantics.
2. **Build the one Quick presentation synchronization edge.** It must drain/take the latest immutable logical publication,
   reject stale generation/engine-generation/activation/mode identity, resolve current presentation geometry/policy/fade/
   style, compose the complete `VisualizerRenderSnapshot`, publish it through the existing bridge and request retained Quick
   presentation. Reuse existing latest-state/bridge/render contracts; no second timer, cadence, queue or presenter.
3. **Replace QWidget-only reveal/presentation consequences.** Readiness/reveal and fade/layout consequences needed by the
   destination must execute against Quick presentation owners. Do not call legacy `present_tick()`, QWidget shadow/layout
   functions or compositor push code from the Quick path.
4. **Resolve single visualizer display admission before construction.** Preserve requested monitor, participating-display
   fallback and CUSTOM/committed geometry semantics. The chosen `QuickDisplayUnit` owns the visualizer edge; other units own
   none. Preserve one source/logical owner and existing transfer semantics.
5. **Wire visualizer semantic mode-cycle hit admission.** A double-click on the retained visualizer cycles visualizer mode;
   only an unhandled display double-click reaches the global next-image fallback.
6. **Make retirement a hard barrier.** Selected display/unit retirement must retire the visualizer edge first; failure to
   stop/join the authored logical runtime leaves the generation unresolved and prevents runtime/window retirement from being
   reported successful.
7. **Owner-shaped all-five proof.** From canonical settings/preset resolution, prove every mode can configure, start, advance,
   publish a complete Quick render snapshot, survive pause/play and mode change, and retire without constructing
   `SpotifyVisualizerWidget`. Include stale identity rejection, generation 0, requested/fallback display ownership and failed
   join behavior. Existing component/golden tests remain binding but are not a substitute for this chain proof.
8. **CURRENT: coordinated DisplayManager + engine authority cutover.** `DisplayManager` remains the durable product-level
   orchestration boundary. Replace the engine's concrete `.displays[i]` assumptions with the smallest real semantic display
   contract while moving authority to Quick units. This work may be checkpointed across as many commits/sessions as needed;
   intermediate migration commits are allowed to remain intentionally non-runnable. What must remain atomic is the finished
   ownership topology: do not add a `DisplayWidget` compatibility facade, throwaway legacy-only decoupling layer, or parallel
   legitimate production presenter merely to make intermediate checkpoints runnable.
9. **Runtime-shaped production proof and caller-proven deletion.** Prove one/multiple selected displays, image/transition
   routing, ordinary families, the single admitted visualizer, corrected-G owners, readiness, generation/topology replacement
   and clean retirement; then delete `DisplayWidget`, QRhiWidget/`GLCompositorWidget`, legacy visualizer host/compositor glue,
   unsupported fallback policy and caller-dead physical-host code in H.

One additional lifecycle regression bar is required around shared Ctrl coordination: current coordinator contributions are
screen-index keyed. If exact cutover implementation permits old/new generations for the same screen to overlap even briefly,
prove stale retirement cannot clear the replacement generation's Ctrl contribution or generation-qualify the contribution
identity. If the destruction barrier proves no overlap is possible, keep the simpler implementation and lock that invariant
with a test rather than inventing work.

H remains active; this is a bounded H correction gate, not a new phase and not permission to reopen accepted G or the
widget-free visualizer logical extraction. The legacy `DisplayWidget` production route may remain temporarily while the gate
is corrected, but no compatibility work should be added solely to improve the half-migrated legacy product.

The correction gate is CLOSED. H now proceeds through the DisplayManager/engine cutover in bounded, testable checkpoints.
"Coordinated" describes the final ownership result, **not** a requirement for one uninterrupted agent session or one giant commit.
Once destination ownership is authoritative, delete the remaining physical-host path rather than carrying it into I.

## I / J

I is residue only: expired adapters/aliases, caller-dead old-presenter utilities, obsolete tests/tools/comments and abandoned
migration spikes. **I intentionally has no standing prewritten decomposition.** Its exact deletion list must be derived from
the post-H caller graph so a speculative pre-cutover checklist cannot become a stale authority. Use exact source,
`Docs/TestSuite.md`, `Future_Cleanup.md` and caller proof. If I unexpectedly exposes a cross-owner architectural problem rather
than residue, write a bounded source-specific decomposition at that point.

J owns comprehensive installed/compiled and physical acceptance. Follow:

`Docs/QtQuick_Migration/Remaining_J_Final_Installed_Acceptance_Decomposition.md`

It covers build/frozen packaging, real 1/2/N-display refresh/DPR/topology/off-wake, lifecycle/recreation, MC/screensaver input,
widget/Visualizer eyes-on parity, the deferred G4 all-mode viewport gate, physical cadence/performance tails, long-soak resource
stability, clean shutdown, test/debt reconciliation and final documentation closure. J is acceptance/sign-off, not another
presentation migration.

The physical runtime smoke cells retained for J include the two-display identity and topology-recreation tests currently housed
in `tests/test_qtquick_runtime.py`. Their presence in the repository is intentional. H retains the deterministic/runtime-shaped
owner, generation-recreation and coordinated-exit tests from that module; J owns the hardware-dependent cells after H/I.

## Current unrelated acceptance debt

`Future_Cleanup.md` is authoritative for unrelated cleanup/test debt. Do not resurrect already-closed logging or retired
global Presets debt in this plan.
