# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-29

## Current checkpoint

The documentation is reconciled through pushed source:

```text
be7c64e4cea48fee2c3b3ab9a6bded022bdfc2cc
Complete G: independently audited and ACCEPTED.
H: ADMITTED and in progress.

Landed H work through this checkpoint:
- one WidgetRuntimeManager per QuickDisplayRuntime generation;
- full seven-family OrdinaryFamilyPresentationBinder;
- visualizer render-source + viewport-config bindings;
- capture_qpixmap / immutable image-routing seam;
- option-A outer-geometry mechanism and historical per-family preferred-size policies;
- thin QuickDisplayPresenter;
- authoritative SharedCtrlCoordinator;
- QuickDisplayUnit per-display destination-chain assembly.

Current source-backed H prerequisite before the production flip:
- the visualizer's VisualizerLogicalRuntime thread is controller-owned, but the production
  per-tick logical computation still executes logical_tick(widget) against legacy widget state;
- migrate that per-tick state/computation to presentation-neutral VisualizerRuntimeController
  ownership (or a controller-owned state object) before the Quick visualizer ownership edge
  and atomic DisplayManager cutover.
```

Exact later source always outranks this document. **All of G is complete, independently audited and accepted. H is admitted and
is the active phase.** Deferred to J installed acceptance: the all-five-mode visualizer eyes-on gate and the physical
two-display A->B->A hardware-ingress matrix.

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
H       production Quick owner/orchestration cutover     ACTIVE
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

### H visualizer runtime ownership correction — NEXT REQUIRED SLICE

A pre-flip source audit found one real missing destination ownership boundary.

The existing `VisualizerRuntimeController` is already the intended presentation-neutral owner for visualizer mode/settings,
source/engine identity, `VisualizerLogicalRuntime`, the latest-state mailbox, render bridge, viewport configuration and
generation/activation fencing. **Do not create a second controller or replacement visualizer subsystem.**

However, production cadence currently starts the controller-owned logical runtime with a step equivalent to:

```text
logical_tick(widget)
```

and `widgets/spotify_visualizer/tick_pipeline.py` still reads/writes substantial live legacy-widget state during each authored
logical step (enabled/playing state, dt/perf accounting, engine/source freshness, mode-transition readiness, mode dispatch,
logical publication and related state).

Therefore the Quick production owner cannot yet start the authored logical runtime without retaining a live legacy widget.
That is a deterministic H ownership defect and must be closed **before** the atomic production flip; it is not J debt and is
not permission to retain a hidden QWidget after cutover.

Required bounded correction:

1. Move the state required by the authored per-tick logical computation off `spotify_visualizer_widget` and into the existing
   `VisualizerRuntimeController` or a controller-owned presentation-neutral state object.
2. Refactor the production logical step so `VisualizerLogicalRuntime` can advance using that destination state without a
   `QWidget`/legacy presenter argument.
3. Preserve existing authored algorithms, timing and state semantics. This is an ownership migration, **not a visualizer
   retune/rewrite**.
4. Preserve the existing shared BeatEngine/source cardinality and exactly one intended authored logical runtime per active
   visualizer owner/generation; do not duplicate engine/source/tick owners.
5. Keep generation/activation fencing, latest-state/coalescing semantics, source freshness, mode teardown/readiness,
   viewport-extent ownership and render-bridge publication intact.
6. Preserve BTF/replay/cadence/reactivity/transport goldens and do not alter authored Bubble counts/physics merely to ease
   the ownership move.
7. No QML/QQuickItem/QScreen/render-thread object enters the logical state.
8. During this preparatory slice the old `DisplayWidget` remains the production caller only because the production cutover has
   not happened yet. Do **not** run a second Quick visualizer logical owner in parallel normal production and do not add a
   legacy fallback contract.
9. Once this slice is GREEN, bind the existing controller through the Quick destination chain and proceed directly to the
   atomic production cutover.

### H remaining — visualizer owner closure, then atomic DisplayManager production flip

The next sequence is:

1. **Visualizer logical-state/step ownership migration** described above, with focused owner-shaped regression bars.
2. **Thin Quick visualizer ownership edge**: construct/configure/start the existing `VisualizerRuntimeController` at the
   intended destination owner, bind its existing render source + viewport configuration into `QuickDisplayRuntime`, and prove
   generation replacement/retirement without a hidden widget.
3. **Atomic DisplayManager + engine cutover.** `DisplayManager` remains the durable product-level orchestration boundary.
   Replace the engine's direct dependence on concrete `.displays[i]` implementation internals with a small semantic
   DisplayManager contract covering only real product operations (image routing, target size/query where genuinely needed,
   readiness, outward semantic signals/actions, display mode, generation/topology lifecycle and retirement/close).
   - Do not create 51 one-for-one forwarding methods.
   - Do not make `QuickDisplayUnit` or `QuickDisplayRuntime` emulate `DisplayWidget` private attributes.
   - Do not first build a throwaway legacy-only decoupling layer.
   - Do not spread `QuickDisplayUnit` implementation knowledge across engine call sites.
   The DisplayManager rewrite + engine call-site conversion + production Quick construction must land as one coordinated
   cutover because a half-swap is not a valid runtime state.
4. **Runtime-shaped production proof** for one/multiple selected displays, image/transition routing, ordinary families,
   visualizer ownership, corrected-G owners, readiness, generation replacement, topology replacement and clean retirement.
5. **Caller-proven legacy deletion in H**: delete `DisplayWidget`, QRhiWidget/`GLCompositorWidget`, the legacy visualizer host,
   old compositor scheduling/presentation glue, unsupported software/backend-demotion presenter fallback, obsolete
   `hw_accel`/fallback-overlay policy and remaining old physical-host transition/visualizer glue once caller proof is clean.

H is **admitted and active**. This visualizer correction is a discovered H prerequisite, not a new phase and not a reason to
reopen accepted G.

The source may still route normal startup through legacy `DisplayWidget` before the production flip. That is a routing fact,
not a requirement that the partially migrated application remain product-functional. Do not add compatibility work solely to
keep the old runtime alive while migration proceeds.

H is the final owner/orchestration wiring. Follow the reconciled
`Docs/QtQuick_Migration/Remaining_H_Production_Cutover_Decomposition.md`, with this source-backed visualizer correction taking
precedence where the older decomposition assumed all destination runtime ownership was already presentation-neutral.

Destination shape remains:

```text
selected display
-> one QuickDisplayRuntime / QuickDisplayUnit
-> retained Quick scene
-> one display-owned WidgetRuntimeManager for ordinary families
-> existing presentation-neutral VisualizerRuntimeController for visualizer logical/source ownership
-> Quick render-source / viewport bindings
```

Do not run legacy and Quick production runtime managers or visualizer logical owners in parallel. Preserve semantic
cardinality. `QuickSceneController` remains sole runtime Quick-item creator/destructor for its display; shared `QQmlEngine` is
not a hidden runtime-generation owner.

Once the destination chain is authoritative, delete the remaining physical-host path rather than carrying it into I.

H does **not** require a seamless live handoff from a fully functioning legacy application. H must prove owner/lifecycle
correctness of the destination and leave only Quick production authority. No production switch back.

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

## Current unrelated acceptance debt

`Future_Cleanup.md` is authoritative for unrelated cleanup/test debt. Do not resurrect already-closed logging or retired
global Presets debt in this plan.
