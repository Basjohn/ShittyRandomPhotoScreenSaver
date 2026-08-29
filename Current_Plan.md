# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-29

## Current checkpoint

The documentation is reconciled through pushed source:

```text
558e99cb1621f99768b81df2a2eab0246f8cb0d7
Complete G: independently audited and ACCEPTED.
H: ADMITTED and in progress.

Landed H work through this checkpoint:
- one WidgetRuntimeManager per QuickDisplayRuntime generation;
- full seven-family OrdinaryFamilyPresentationBinder;
- visualizer render-source + viewport-config bindings;
- capture_qpixmap image bridge;
- option-A outer-geometry mechanism;
- historical per-family preferred-size policies and deterministic regression bars.
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

The family/runtime destination integration named first in the H directive is complete and test-gated:

- `QuickDisplayRuntime` owns **exactly one** `WidgetRuntimeManager` per generation (H §7 cardinality): hostless
  construction, retired once before scene teardown, dropped at window destruction, replacement generations build their own.
- `rendering/quick/widgets/family_binder.py` — thin presentation-neutral `OrdinaryFamilyPresentationBinder` + one small
  adapter per family. It resolves admitted families (capability effectiveness via the single manager; per-instance `enabled`
  distinct), builds the existing `Retained*Presentation` items into the real `OrdinaryWidgetPresentationHost`, owns each
  family's neutral runtime service(s) through the manager (fail-closed on a missing required lease), and retires held items
  exactly once. All seven families wired: Clock, Weather, Media (three leases), Reddit (reddit/reddit2), Gmail, and the two
  Steam cards (Achievement Pulse, Abandonment Issues). Geometry + shadow values are **injected seams**.
- Prior H slices: `bind_visualizer_render_source` (exact identity) and `bind_visualizer_viewport_config` (corrected-G4
  committed/override ownership) at the runtime owner; the `capture_qpixmap` image bridge already exists and is tested.

### H geometry resolution — DECIDED (option A) and BUILT, GREEN, pushed

The ordinary-widget outer-geometry gate is resolved: **option A** (QML reports a size-only preferred content size; Python is
the sole outer-rect/anchor/clamp authority). Per the boundary correction, the deterministic per-family preferred-size
contract is **H work** (built now); only final eyes-on visual parity is J. Landed:

- `rendering/quick/widgets/geometry_resolver.py` — pure `resolve_anchored_geometry` (reproduces the legacy
  `_update_position` content-size + anchor + margin + min-visible clamp, minus QWidget-era padding/pixel-shift artifacts),
  `OverlayGeometryPolicy` + `resolve_overlay_geometry_policy` (persisted `position`/`margin`, optional CUSTOM committed-rect
  override), `OverlayGeometryBinding` (content-size → committed outer rect; identical-effective no-op; committed rect wins;
  re-anchors on display-bounds/topology change), and `connect_overlay_preferred_size` (wires the QML signal; no width
  feedback, no polling/timers/per-frame callbacks).
- QML contract: `OverlayWidget` exposes family-declared `preferredContentWidth/Height` + a size-only
  `preferredContentSizeChanged`; `OverlayCard` exposes `shellInset`. Every production family declares a real preferred size
  from intrinsic/config sources (never its assigned width).
- **Historical size policies are honoured (H, not J)** — intrinsic QML measurement may enlarge a card where content genuinely
  requires it, but never shrinks below the authored/minimum footprint (deterministic bars in
  `tests/test_qtquick_family_size_policy.py`):
  - Weather / Reddit / Media: 600 px minimum width (`BaseOverlayWidget.DEFAULT_CARD_MIN_WIDTH`);
  - Gmail: authored width, default 600, clamped 200–1200;
  - Media: height floor `max(220, artwork_size + 60)`;
  - Clock analogue: authored natural geometry `width = max(160, font*4.5)`, `height = max(width, width*1.3)`;
  - Clock digital: content-driven intrinsic text; Steam cards: authored dimensions.

**Ownership DECIDED — option A:** content anchoring is **default placement only**. Existing CUSTOM committed rects and Clock
per-variant (digital/analogue) committed-rect ownership remain unchanged and override the binding completely (the binding's
`policy.committed_rect` carries the committed rect; when present it wins and suppresses re-anchoring). J later validates/refines
visual parity only.

### H remaining — the DisplayManager production flip

All destination pieces now exist and are GREEN: manager cardinality, the full seven-family `OrdinaryFamilyPresentationBinder`,
visualizer render-source + viewport-config bindings, the `capture_qpixmap` image bridge, and the complete option-A geometry
mechanism + per-family preferred sizes. Remaining flip steps:

1. **Per-display Quick presenter** assembling `QuickDisplayRuntime` + binder + per-widget geometry bindings under option A
   (content-anchoring is default placement only; CUSTOM committed rects and Clock per-variant committed rects override the
   binding and are left owning their geometry unchanged) + visualizer bindings + image/transition routing + outward signal
   fan-in.
2. **DisplayManager rewire** to construct/own the Quick presenter per selected QScreen instead of `DisplayWidget`, mapping
   image/transition/readiness/generation/topology onto the runtime APIs; update the engine test suites off QWidget shapes.
3. **Caller-proven legacy deletion** of `DisplayWidget`/`GLCompositorWidget`/compositor stack (§10), not deferred to I.

H is **admitted and active**. The complete G checkpoint has already passed the required independent audit.

The source may still route normal startup through legacy `DisplayWidget` before the production flip. That is a routing fact,
not a requirement that the partially migrated application remain product-functional. Do not add compatibility work solely to
keep the old runtime alive while migration proceeds.

H is the final owner/orchestration wiring. Follow the reconciled
`Docs/QtQuick_Migration/Remaining_H_Production_Cutover_Decomposition.md`. Do not improvise a compatibility architecture in
the meantime.

Destination shape remains:

```text
selected display
-> one QuickDisplayRuntime
-> one display-owned WidgetRuntimeManager
-> canonical capability + ordinary enabled/instance resolution
-> existing neutral service lease(s)
-> stable presentation model(s)
-> QuickSceneController ordinaryWidgetHost
-> retained family item(s)
```

Do not run legacy and Quick production runtime managers in parallel. Preserve semantic cardinality.
`QuickSceneController` remains sole runtime Quick-item creator/destructor for its display; shared `QQmlEngine` is not a hidden
runtime-generation owner.

Once that destination chain is authoritative, delete the remaining physical-host path: `DisplayWidget`,
QRhiWidget/`GLCompositorWidget`, old compositor scheduling/presentation glue, unsupported software/backend-demotion fallback,
obsolete `hw_accel`/fallback-overlay policy, remaining physical-host transition/visualizer debris, temporary legacy anchors
after destination ownership, and obsolete presentation-setting compatibility.

H does **not** require a seamless live handoff from a fully functioning legacy application. H must prove
owner/lifecycle correctness of the destination and leave only Quick production authority. No production switch back.

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
