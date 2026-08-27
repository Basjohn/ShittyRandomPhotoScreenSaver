# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-27

## Current checkpoint

Exact pushed `main` reviewed through:

```text
aca1087813d15b38dc9fa1c4ed2f8e0bd6567000
Phase F7 Achievement Pulse retirement is caller-proven and self-audited on current main
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
F8    Abandonment Issues                         ACTIVE
G     CUSTOM / input / auxiliary pixels          after F
H     settings epoch + physical Quick cutover    after G
I     residue only                               after H
J     final installed / physical validation      final
```

Integrated audit: `Docs/audits/QtQuick_Phase_F_F2_F6_Independent_Audit_2026-08-26.md`.
F2–F5 remain independently GREEN. F6 is GREEN after retained owner/host/visual proof and caller-proven
retirement of the old Gmail QWidget presentation.

Source outranks this plan if a later checkpoint has landed.

---

## Immediate work — F8 Abandonment Issues

```text
exact runtime/data/cache/rotation/action/presentation ownership audit  GREEN
stable retained config/model/image projection                         ACTIVE
retained QML card + interaction fidelity                               PENDING
registry + real owner injection + runtime-shaped gates                PENDING
effective-DPR eyes-on matrix at 1.0 / 1.5 / 2.25                      PENDING
caller proof + old Abandonment pixel/cache/input retirement           PENDING
```

### F8.2 — stable retained model and image projection (ACTIVE)

- project the existing normalized selection, shelf visibility, artwork/desaturation and shared Steam settings
  into one immutable retained config;
- consume `AbandonmentPreparedPresentation` directly; keep accepted card/artwork identity and rotation state in
  one stable presentation model without provider, cache or cadence work;
- reuse a presentation-neutral retained Steam field-list model and image-source projection rather than cloning
  the Achievement Pulse technique; keep archive/ledger policy and geometry Abandonment-specific;
- preserve double-click manual refresh, cache-only rotation admission, fade completion and settings actions as
  capability-gated semantic calls;
- prove stable object/list identity, runtime attach/retire behavior, honest unavailable states and no work before
  activation before admitting QML pixels.

Do not port Steam Journey/Progress or Friend Pulse scaffolds as part of F8.

---

## Phase-F execution / audit policy

Normal family slice:

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

No routine hosted CI or full/Nuitka/installed build during ordinary Phase-F implementation.

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

## F7–F8

Only substantive Steam widgets are migration ports:

```text
F7 Achievement Pulse
F8 Abandonment Issues
```

Steam Journey/Progress and Friend Pulse remain unfinished dev-gated future-product scaffolds. Do not
manufacture Quick parity ports. Retire scaffold pixels later if they obstruct shared cleanup.

---

## G — CUSTOM / input

Geometry key supports `(widget_id, display_identity, geometry_variant)`; Clock digital/analogue keep
independent committed rects without drift.

Every adjustable edit-mode card gets `X`:

- duplicate -> remove that duplicate from working layout;
- singleton -> ordinary widget OFF, equivalent to its normal Settings checkbox;
- never family/capability deactivation;
- no immediate persistence or committed provider/runtime destruction.

Context-menu Save or Enter commits geometry, duplicate removals and ordinary enabled-state changes.
Cancel restores pre-edit geometry, duplicate set and ordinary enabled state.

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

- unrelated logging and Reddit-helper focused-test debt remains in `Future_Cleanup.md`.
