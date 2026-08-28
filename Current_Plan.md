# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-28

## Current checkpoint

Exact pushed `main` reviewed through:

```text
59f4a3c98235215a9ff89fc09e4cc979d1831e89
G1–G6 landed; G7 retained dimming/pixel shift, cursor halo and context menu are landed; G7 is near closure.
```

The latest migration-relevant G7 commit in that checkpoint is `a8b2426e` (retained context menu).
Later source always outranks this plan.

Current phase state:

```text
F0–F8   ordinary-family migration                         CLOSED
G1      neutral CUSTOM session / variants / layout slots CLOSED
G2      retained edit overlay / X / family binding       CLOSED
G3      Save/Cancel + enabled/duplicate persistence      CLOSED
G4      retained uniform + viewport-extent resize     LANDED; Bubble logical reflow remaining
G5      retained cross-display transfer                  CLOSED
G6      retained input / semantic family actions         CLOSED
G7      retained context + auxiliary pixels              NEAR CLOSURE
G8      MC / focus closure                               PENDING
H       production Quick owner/orchestration cutover     after G
I       residue only                                     after H
J       final installed / physical validation            final
```

## Remaining G4 blocker — Bubble logical viewport reflow

The retained viewport-extent (edge) resize operation is landed and gated by tests for the geometry projection,
session working state, overlay/QML edge handles, scene-controller preview projection, the manager edge adapter and
the persistence round-trip. The four proven modes (Spectrum, Oscilloscope, Sine, DevCurve) reflow because their
Quick renderers already recompute their domain from committed geometry and the shader keeps circles round.

One piece remains before G4 closes: **Bubble logical viewport reflow**.

Bubble's simulation runs in a unit square `[0,1]^2`; the shader maps that to the card and keeps circles round via
aspect correction. The accepted **baseline (1.5) look is a BTF golden and must stay byte-identical**. The reflow
must be a strict no-op at the baseline aspect and expand the logical domain only for a wide/tall committed extent
(baseline-relative domain extension), never anisotropically stretching finished pixels, and never retuning Bubble
speed/collision/elasticity/personality or adding a second clock. The committed viewport extent is already available
at the runtime-controller boundary (`presentation_viewport_extent`); Bubble must consume it as latest spatial
configuration.

Remaining proof:

- wire the committed viewport extent into the Bubble simulation as latest spatial configuration (no pointer/geometry
  clock); domain defaults to the baseline square so BTF goldens stay byte-identical;
- a wide/tall extent expands the Bubble logical domain (bubbles fill the extra space at baseline density) rather than
  texture-stretching positions; circles/radii/velocity/collision stay coherent and BTF-clean;
- flip Bubble's `viewport_resize_capable` mode policy to `True` (and update the two policy tests) once the reflow
  lands, so all five modes are destination-capable;
- all-five-mode eyes-on gate at baseline, wide and tall extents (this piece needs installed/manual visual
  acceptance — deterministic tests alone do not close Bubble visual/timing fidelity).

Because this modifies BTF-binding simulation code and needs eyes-on acceptance, it is an audit/eyes-on boundary.

Use `Docs/QtQuick_Migration/Remaining_G4_Visualizer_Viewport_Resize_Decomposition.md` section 7 as the route, with
`Docs/Guardrails/Visualizer_Presentation.md` (§9, §14), `Docs/Guardrails/Bubble_Temporal_Fidelity.md` and
`Docs/QtQuick_Migration/03_Visualizer.md` as binding destination contracts.

## Resume G7 closure after the G4 correction

Already landed in the retained Quick scene:

- dimming and shared pixel-shift transform;
- cursor halo and inactivity behavior;
- retained context-menu model/QML and semantic action admission.

G7 remaining work is closure/caller proof: inspect exact current legacy context/halo/dimming/pixel-shift callers,
retire superseded QWidget/top-level auxiliary pixel ownership that no longer has a live caller, preserve Python
semantic command/settings authority, and prove same-window generation/focus/input behavior. Do not rebuild a
compatibility presenter merely to keep the half-migrated screensaver runnable.

Then perform G8 MC/focus closure. For G7 deletion/caller proof and G8 focus/input sequencing, follow
`Docs/QtQuick_Migration/Remaining_G7_G8_Auxiliary_Focus_Decomposition.md`.

## Migration execution policy

Normal bounded slice:

```text
inspect exact source
-> bounded implementation
-> focused tests + required eyes-on evidence
-> diff/status
-> commit/push
-> fresh post-push self-audit
-> continue when GREEN
```

External audit is required for cross-family/process/display architecture changes, engine/window/thread/resource
ownership changes, material runtime lifecycle/shared-resource changes, unresolved YELLOW, deterministic-vs-visual
disagreement, or explicit request. H owner cutover remains independently audit-required.

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

Geometry key supports `(widget_id, display_identity, geometry_variant)`; Clock digital/analogue have independent
committed rects without drift.

Every adjustable edit-mode card gets `X`:

- duplicate -> remove that duplicate from working layout;
- singleton -> ordinary widget OFF, equivalent to its normal Settings checkbox;
- never family/capability deactivation;
- no immediate persistence or committed provider/runtime destruction.

Save/Enter commits; Cancel restores pre-edit geometry, duplicate set and ordinary enabled state.

Layout slots are ordinary visible-layout snapshots: `Shift+1`..`Shift+0` save and `1`..`0` load geometry/size plus
ordinary ON/OFF. Slot load may turn an effective family member ordinarily ON/OFF, but never activates a fully
deactivated family/capability and never overwrites provider/account/source settings.

Centering guides are red so display/peer-centre alignment is distinct from ordinary grid/edge guides.

## H — final production owner cutover

The source still routes normal startup through legacy `DisplayWidget` before H. **That is a routing fact, not a
requirement that the partially migrated application remain product-functional.** Do not add compatibility work solely
to keep the old runtime alive while migration proceeds.

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
`QuickSceneController` remains sole runtime Quick-item creator/destructor for its display; shared `QQmlEngine` is not
a hidden runtime-generation owner.

Once that destination chain is authoritative, delete the remaining physical-host path: `DisplayWidget`,
QRhiWidget/`GLCompositorWidget`, old compositor scheduling/presentation glue, unsupported software/backend-demotion
fallback, obsolete `hw_accel`/fallback-overlay policy, remaining physical-host transition/visualizer debris,
temporary legacy anchors after destination ownership, and obsolete presentation-setting compatibility.

H does **not** require a seamless live handoff from a fully functioning legacy application. H must prove owner/lifecycle
correctness of the destination and leave only Quick production authority. No production switch back.

## I / J

I is residue only: expired adapters/aliases, caller-dead old-presenter utilities, obsolete tests/tools/comments and
abandoned migration spikes.

J owns comprehensive installed/compiled and physical acceptance: real 1/2/N-display, DPR/topology/off-wake,
continuity, widget/Visualizer eyes-on parity, performance/tail checks, clean shutdown, test-ledger reconciliation and
documentation closure.

## Current acceptance debt

Unrelated logging, Reddit-helper and physical two-display midpoint-capture focused-test debt remains in
`Future_Cleanup.md` and must not be mistaken for the visualizer viewport-resize blocker above.
