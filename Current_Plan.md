# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-29

## Current checkpoint

The attached documentation snapshot records pushed source through:

```text
29c0586891ab46c97dad2a369c6a63d2f6af3516
Complete G is deterministically GREEN and pushed:
- G4 viewport-extent implementation + post-checkpoint corrections (A committed/override ownership,
  B domain retry clamp, C contraction lifecycle, D specular audit, wording) for all five modes;
- G7 auxiliary/context caller closure (destination sole aux; legacy = H-scaffolding);
- G8 deterministic focus/MC closure (cross-display stuck-Ctrl fixed; MC policy/fallback/generation locked).
```

Exact later source always outranks this document. **All of G is deterministically complete and checkpointed. This is the
single G-completion stop: request one independent audit of the complete checkpointed G state before H.** H must not begin
until that audit is accepted. Deferred to J installed acceptance: the all-five-mode visualizer eyes-on gate and the physical
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
G-GATE  independent audit of complete checkpointed G     READY — all G GREEN, request now before H
H       production Quick owner/orchestration cutover     after G audit
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
changes. G4 is **deterministic implementation complete, physical acceptance deferred** (see below). Resume G7 next.

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

## Independent-audit stop policy for the rest of G

**Independent audit is the G-completion gate, not a per-slice interruption.**

During G4 correction, G7 and G8, use the normal loop:

```text
inspect exact source
-> bounded implementation
-> focused tests
-> diff/status
-> commit/push
-> fresh post-push self-audit
-> continue when GREEN
```

Claude/implementation agents should **not stop merely to request an independent audit between GREEN G slices**, including
architecture-sensitive G work. Continue while the next G task is known, bounded, testable and consistent with the binding
contracts.

A stop before G completion is required only for a real blocker, for example:

- RED or unresolved YELLOW evidence that cannot be resolved from exact source/tests;
- a required product/semantic decision not owned by existing docs;
- a change that would violate a hard destination invariant;
- evidence that the requested correction requires a new clock, new accelerated surface, new persistence authority or other
  prohibited architecture;
- explicit user instruction to stop.

Once **G4 corrections + G7 + G8 are all GREEN**, commit/push the complete G checkpoint, reconcile the immediate G status docs,
then **STOP before H and request one independent audit of the complete checkpointed G state**. H must not begin until that
audit is accepted.

This supersedes older wording that could be read as requiring a separate external-audit pause after every
architecture/lifecycle/shared-owner G slice. Those changes still demand stronger tests and self-audit; they do not by
themselves create a user-attention stop while G is still in progress.

H remains independently audit-sensitive because it is the production owner cutover. Its decomposition has now been
reconciled against the current G contracts, including the visualizer viewport-config seam, but **H is still not admitted**
until the complete checkpointed G state passes the independent audit above.

Do not run routine hosted CI or full/Nuitka/installed builds during ordinary G implementation.

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

### H open decision — ordinary-widget outer-geometry resolution (GATE before the DisplayManager flip)

The DisplayManager production flip is blocked on a genuine unbuilt destination authority, not merely a large slice.

The family binder consumes an **injected** per-widget display-space `OverlayWidgetGeometry`. In the legacy path
(`widgets/base_overlay_widget.py::_update_position`) each ordinary widget's outer rect is resolved from: a **content-driven
size** (`self.size()`/`sizeHint()`, i.e. the widget's rendered content), a named anchor (`position`, e.g. "Top Right"), a
`margin`, pixel-shift/stack offsets, and a min-visible clamp — with the G CUSTOM committed rect as an override. No Quick-era
resolver reproduces this: docs say only that "outer geometry is Python/session-owned" without specifying how the
**content-driven size** is obtained once presentation lives in QML (the content size is known only after the retained item
lays out via QML `implicitWidth`/`implicitHeight`).

This is a real architecture fork the flip cannot proceed past without a decision (guessing silently mislays every widget):

- **A. QML→Python content-size feedback + Python anchor-resolve.** Retained item reports resolved implicit content size;
  Python reproduces `_update_position` anchoring (position/margin/offset/clamp) and re-anchors when content size changes.
  Most faithful to current auto-sizing product behavior; needs a bounded size-feedback seam.
- **B. Fully explicit persisted rects (CUSTOM-owned).** Seed each widget's rect once, then geometry is explicit and only
  CUSTOM edits it. Simplest resolver; changes product behavior (widgets stop auto-resizing to content after settings changes
  unless re-seeded).
- **C. Python computes size from settings/font metrics (no QML feedback).** Approximate; risks mismatch with actual rendered
  content and per-family special cases.

Recommendation: **A** (preserves current content-driven anchoring). This choice is required before building the per-display
Quick presenter + DisplayManager flip + legacy deletion.

H is **not admitted until the complete G checkpoint has passed the independent audit above**.

The source may still route normal startup through legacy `DisplayWidget` before H. That is a routing fact, not a requirement
that the partially migrated application remain product-functional. Do not add compatibility work solely to keep the old
runtime alive while migration proceeds.

H is the final owner/orchestration wiring. Follow the reconciled
`Docs/QtQuick_Migration/Remaining_H_Production_Cutover_Decomposition.md` after the G audit. Do not improvise a compatibility
architecture in the meantime.

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
