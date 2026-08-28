# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-28

## Current checkpoint

Exact pushed `main` reviewed through:

```text
9baea1f6df9301430ed7da9d6ae780f5e502352e
G4 deterministic viewport-extent implementation is complete for all five modes,
including Bubble logical reflow, the live config route and the canonical-reset persistence fix.
Only the deferred all-five-mode installed/eyes-on viewport gate remains (after H).
```

Later source always outranks this plan.

Current phase state:

```text
F0–F8   ordinary-family migration                         CLOSED
G1      neutral CUSTOM session / variants / layout slots CLOSED
G2      retained edit overlay / X / family binding       CLOSED
G3      Save/Cancel + enabled/duplicate persistence      CLOSED
G4      viewport-extent implementation                   DETERMINISTIC COMPLETE; eyes-on deferred (after H)
G5      retained cross-display transfer                  CLOSED
G6      retained input / semantic family actions         CLOSED
G7      retained context + auxiliary pixels              NEAR CLOSURE
G8      MC / focus closure                               PENDING
H       production Quick owner/orchestration cutover     after G
I       residue only                                     after H
J       final installed / physical validation            final
```

## G4 deterministic implementation — complete

The G4 viewport-extent implementation is deterministically complete and pushed for all five modes. Landed and test-gated:
retained edge handles + session scale/extent working state, presentation-geometry projection, scene-controller preview
projection, the manager viewport-edge adapter, persistence (including the canonical-reset drop of a stale extent), the live
`presentation_viewport_extent` config route from a CUSTOM edge drag into the next authored Bubble step, Bubble's
baseline-relative logical-domain reflow (canonical `(420,280)` is a strict byte-identical no-op; wide/tall expand the world,
shrink reconciles through the canonical exit/cull path, authored counts/personality untouched, render seam normalizes so the
shader keeps circles round), and the `viewport_resize_capable=True` policy flip for all five modes.

Only the deferred all-five-mode installed/eyes-on viewport gate remains, and it is correctly blocked on H (see below). Do not
reopen the deterministic work or invent compatibility presentation work to inspect it before H.

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

For Bubble specifically verify circles, apparent size, speed, distribution, trails, collision feel and BTF continuity.
Installed/manual evidence can reject deterministic implementation if the result looks materially wrong.

This deferred physical gate is acceptance debt, not permission to leave Bubble `viewport_resize_capable=False` after the
deterministic implementation is complete.

## Resume G7 closure after deterministic G4 completion

Already landed in the retained Quick scene:

- dimming and shared pixel-shift transform;
- cursor halo and inactivity behavior;
- retained context-menu model/QML and semantic action admission.

G7 remaining work is closure/caller proof: inspect exact current legacy context/halo/dimming/pixel-shift callers, retire
superseded QWidget/top-level auxiliary pixel ownership that no longer has a live caller, preserve Python semantic
command/settings authority, and prove same-window generation/focus/input behavior. Do not rebuild a compatibility presenter
merely to keep the half-migrated screensaver runnable.

Then perform G8 MC/focus closure. For G7 deletion/caller proof and G8 focus/input sequencing, follow
`Docs/QtQuick_Migration/Remaining_G7_G8_Auxiliary_Focus_Decomposition.md`.

## Migration execution policy

Normal bounded slice:

```text
inspect exact source
-> bounded implementation
-> focused tests
-> diff/status
-> commit/push
-> fresh post-push self-audit
-> continue when GREEN
```

Use an explicit deferred-physical-acceptance marker where the current production routing makes a real Quick eyes-on gate
impossible. Do not fabricate visual acceptance and do not block destination implementation on a legacy compatibility detour.

External audit is required for cross-family/process/display architecture changes, engine/window/thread/resource ownership
changes, material runtime lifecycle/shared-resource changes, unresolved YELLOW, deterministic-vs-visual disagreement, or
explicit request. H owner cutover remains independently audit-required.

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

The source still routes normal startup through legacy `DisplayWidget` before H. **That is a routing fact, not a requirement
that the partially migrated application remain product-functional.** Do not add compatibility work solely to keep the old
runtime alive while migration proceeds.

H is the final owner/orchestration wiring. Follow
`Docs/QtQuick_Migration/Remaining_H_Production_Cutover_Decomposition.md`; do not improvise a compatibility architecture:

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
migration spikes.

J owns comprehensive installed/compiled and physical acceptance: real 1/2/N-display, DPR/topology/off-wake, continuity,
widget/Visualizer eyes-on parity, the deferred G4 all-mode viewport gate, performance/tail checks, clean shutdown,
test-ledger reconciliation and documentation closure.

## Current unrelated acceptance debt

`Future_Cleanup.md` is authoritative for unrelated cleanup/test debt. Current known focused debt includes the Reddit helper
tests and the physical two-display Quick midpoint-capture smoke cases. Do not resurrect already-closed logging or retired
global Presets debt in this plan.
