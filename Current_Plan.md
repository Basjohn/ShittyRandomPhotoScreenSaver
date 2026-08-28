# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-29

## Current checkpoint

The attached documentation snapshot records pushed source through:

```text
9baea1f6df9301430ed7da9d6ae780f5e502352e
G4 core viewport-extent implementation is landed for all five modes,
including Bubble logical reflow and the policy flip.
```

The user reports the completed G4 checkpoint and its golden/regression bars are pushed. Exact later source always outranks
this document.

An independent post-checkpoint audit found a **bounded G4 correction batch** that must be completed before G4 is finally
closed. This does not invalidate the landed scale/extent architecture and is not permission to redesign CUSTOM or Bubble.

Current phase state:

```text
F0–F8   ordinary-family migration                         CLOSED
G1      neutral CUSTOM session / variants / layout slots CLOSED
G2      retained edit overlay / X / family binding       CLOSED
G3      Save/Cancel + enabled/duplicate persistence      CLOSED
G4      viewport-extent implementation                   AUDIT CORRECTIONS PRIORITY
G5      retained cross-display transfer                  CLOSED
G6      retained input / semantic family actions         CLOSED
G7      retained context + auxiliary pixels              NEAR CLOSURE
G8      MC / focus closure                               PENDING
G-GATE  independent audit of complete checkpointed G     REQUIRED BEFORE H
H       production Quick owner/orchestration cutover     after G audit
I       residue only                                     after H
J       final installed / physical validation            final
```

## Immediate priority — G4 post-checkpoint audit corrections

Do this before resuming G7.

Use:

`Docs/QtQuick_Migration/G4_Post_Checkpoint_Audit_Corrections_Decomposition.md`

as the technical playbook. The existing G4 decomposition remains the binding scale/extent architecture contract:

`Docs/QtQuick_Migration/Remaining_G4_Visualizer_Viewport_Resize_Decomposition.md`

The correction batch is deliberately narrow. It contains four source-level issues plus wording/test cleanup:

1. **Viewport configuration ownership/lifecycle** — active CUSTOM working extent must temporarily override ordinary committed
   extent, while Save/Cancel/end-CUSTOM return to the correct committed value rather than unconditionally resetting Bubble to
   canonical `(420,280)`. The ordinary committed presentation path and CUSTOM working path must not fight each other.
2. **Missed Bubble unit-square retry clamp** — `_spawn_bubble_at()` still bounds overlap-retry jitter to `[-0.25, 1.25]` on
   both axes. Preserve that exact baseline behavior, but non-baseline domains must use the actual logical domain plus the same
   off-world allowance.
3. **Shrink reconciliation for non-surface bubbles** — explicitly handle/test bubbles which become outside the contracted
   domain while `reaches_surface=False`; do not let invisible off-domain particles consume authored population indefinitely,
   and do not percentage-rescale/teleport the field.
4. **Specular mutation coordinate audit** — trace `spec_ox`/`spec_oy` through the Quick Bubble shader. If they are positional
   viewport-space offsets, project them consistently for non-baseline domains; if they are dimensionless local bubble-space
   values, leave them unchanged and prove/document that contract. Baseline must remain exact either way.

Also remove the misleading phrase **“baseline density”** from Bubble reflow comments/tests/docs. Authored bubble counts remain
unchanged, therefore a larger viewport is intentionally less dense unless a future explicit product decision says otherwise.

### G4 correction hard bars

- canonical `(420,280)` remains the exact accepted Bubble path;
- do not regenerate or weaken BTF/replay/golden expectations to bless drift;
- no Bubble speed/collision/bounce/drift/elasticity/pulse/trail/overdrive/cadence retuning;
- no particle-count scaling with viewport area;
- no pointer-driven Bubble tick, geometry timer, second logical clock or QML-owned simulation math;
- no second persistence/geometry authority;
- scale and extent remain independent;
- Save/Cancel/ordinary-runtime viewport ownership is deterministic;
- wide/tall/shrink behavior stays latest spatial configuration consumed by the authored Bubble step;
- retained scene/item/render ownership does not change because an extent changes.

When these corrections and their focused regression bars are GREEN, mark G4 **deterministic implementation complete, physical
acceptance deferred** and continue directly into G7.

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

## Then finish G7 and G8

Already landed in the retained Quick scene:

- dimming and shared pixel-shift transform;
- cursor halo and inactivity behavior;
- retained context-menu model/QML and semantic action admission.

After G4 correction closure, continue G7 closure/caller proof: inspect exact current legacy
context/halo/dimming/pixel-shift callers, retire superseded QWidget/top-level auxiliary pixel ownership that no longer has a
live caller, preserve Python semantic command/settings authority, and prove same-window generation/focus/input behavior. Do
not rebuild a compatibility presenter merely to keep the half-migrated screensaver runnable.

Then perform G8 MC/focus closure. For G7 deletion/caller proof and G8 focus/input sequencing, follow:

`Docs/QtQuick_Migration/Remaining_G7_G8_Auxiliary_Focus_Decomposition.md`

Do not lose already-identified G7/G8 work while correcting G4.

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
