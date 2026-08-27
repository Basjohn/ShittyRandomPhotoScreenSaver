# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-27

## Current checkpoint

Exact pushed `main` reviewed through:

```text
b1ed9a91561cf5857b36830b607dc2ec2d1ebad8
Phase F closed; exact G1 geometry/session owners inspected on current main
```

Current phase state:

```text
F0    Imgur removal                              CLOSED
F0.5  canonical shadow authority                 CLOSED / independently GREEN
F1    Clock / Clock2 / Clock3                    CLOSED
F2    Weather                                    CLOSED / independently GREEN
F3    Media core                                 CLOSED / independently GREEN
F4    Media controls / volume / mute / progress  CLOSED / independently GREEN
F5    Reddit / Reddit2                           CLOSED / independently GREEN
F6    Gmail                                      CLOSED
F7    Achievement Pulse                          CLOSED
F8    Abandonment Issues                         CLOSED
G     CUSTOM / input / auxiliary pixels          ACTIVE
H     settings epoch + physical Quick cutover    after G
I     residue only                               after H
J     final installed / physical validation      final
```

Integrated audit: `Docs/audits/QtQuick_Phase_F_F2_F6_Independent_Audit_2026-08-26.md`.
F2–F5 remain independently GREEN. F6–F8 are GREEN after retained owner/host/visual proof and caller-proven
retirement of their old QWidget presentations. Phase F is CLOSED.

Source outranks this plan if a later checkpoint has landed.

---

## Immediate work — G1 session and multi-variant working-state contract

```text
presentation-neutral CustomLayoutSession contract                     ACTIVE
variant-aware committed storage + exact Clock replay                  PENDING
manager/session integration without QWidget pixel ownership           PENDING
```

### G1.1 — neutral session admission (ACTIVE)

- keep exact item identity, source/current display, geometry variant, baseline/current rect and size payload,
  resize scale and working removed/enabled state in `CustomLayoutSession`, with no QWidget dependency;
- replace the version-1 single-entry geometry map with exact variant-aware committed storage; old CUSTOM geometry may
  invalidate rather than gaining compatibility replay;
- cut `CustomLayoutManager` working-state ownership over to the neutral session while the old shell remains only the
  temporary G1/G2 presentation adapter;
- prove Clock digital -> analogue -> digital restores exact committed rects without derivation or drift;
- do not create Quick overlay pixels or retire old edit pixels until the session/storage/manager contract is GREEN.

Use `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`; exact current source outranks stale owner names.

---

## Phase-G execution / audit policy

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

External audit is required for cross-family/process/display architecture changes, engine/window/thread/
resource ownership changes, material runtime lifecycle/shared-resource changes, unresolved YELLOW,
deterministic-vs-visual disagreement, or explicit request. H physical cutover is independently audit-required.

No routine hosted CI or full/Nuitka/installed build during ordinary Phase-G implementation.

---

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

## Family retirement

```text
old family source = temporary visual/behavioral reference
-> retained Quick family
-> deterministic + eyes-on proof
-> GREEN under current audit policy
-> caller proof
-> delete old family pixel presenter/presentation-only tests
-> next family
```

Do not carry completed family pixels to H/I merely as fallback.

---

## F7–F8 — CLOSED

Only substantive Steam widgets are migration ports:

```text
F7 Achievement Pulse
F8 Abandonment Issues
```

Steam Journey/Progress and Friend Pulse remain unfinished dev-gated future-product Settings scaffolds. Their
old QWidget renderer/factory/runtime/CUSTOM pixels are retired; do not manufacture Quick parity ports or
restore compatibility presenters before real future product work is admitted.

---

## G — CUSTOM / input

Suggested sequence remains G1 session/variant contract, G2 retained edit overlay/X, G3 Save/Cancel commit,
G4 resize, G5 cross-monitor transfer, G6 runtime-neutral input/actions, G7 auxiliary pixels/context and G8
MC/focus closure. Do not reorder from local convenience.

Geometry key supports `(widget_id, display_identity, geometry_variant)`; Clock digital/analogue keep
independent committed rects without drift.

Every adjustable edit-mode card gets `X`:

- duplicate -> remove that duplicate from working layout;
- singleton -> ordinary widget OFF, equivalent to its normal Settings checkbox;
- never family/capability deactivation;
- no immediate persistence or committed provider/runtime destruction.

Context-menu Save or Enter commits geometry, duplicate removals and ordinary enabled-state changes.
Cancel restores pre-edit geometry, duplicate set and ordinary enabled state.

G2 retained edit-overlay visual rule: centering guides are red so display/peer-centre alignment is immediately
distinct from ordinary grid and edge guides.

Old QWidget edit/grid pixels retire after G GREEN.

---

## H — production Quick cutover

Normal startup still uses legacy `DisplayWidget` before H.

H must prove:

```text
selected display
-> one QuickDisplayRuntime
-> one display-owned WidgetRuntimeManager
-> canonical capability + ordinary enabled/instance resolution
-> existing neutral service lease(s)
-> stable presentation model(s)
-> QuickSceneController ordinary-widget host
-> retained family item(s)
```

Do not run legacy and Quick production runtime managers in parallel. Preserve semantic owner cardinality.
`QuickSceneController` remains sole runtime Quick-item creator/destructor for its display. Shared
`QQmlEngine` is not a hidden runtime-generation owner.

Then cut `DisplayManager` to `QuickDisplayRuntime` and delete old physical presentation in the same audited
boundary: `DisplayWidget`, QRhiWidget/`GLCompositorWidget`, old compositor scheduling/presentation glue,
unsupported software/backend-demotion fallback, obsolete `hw_accel`/fallback-overlay policy, remaining
physical-host transition/visualizer debris, temporary non-painting Media anchor after destination ownership,
and obsolete presentation-setting compatibility.

No production switch back.

---

## I / J

I is residue only. J owns installed/compiled validation, real multi-display/DPR/topology evidence, physical
continuity, widget/Visualizer eyes-on parity, final performance/tail checks, test-ledger reconciliation and
docs closure.

## Current acceptance debt

- unrelated logging, Reddit-helper and physical two-display midpoint-capture focused-test debt remains in
  `Future_Cleanup.md`.
