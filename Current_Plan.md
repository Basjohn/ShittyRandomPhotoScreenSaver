# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-25

## Current checkpoint

Exact main inspected through:

```text
bce5c64d9efae45d1039133687890f5b0ba142ea
Tests: restore Bubble tick cadence harness
```

F1 implementation basis:

```text
09c1a215fe28ffbaee51897e81d22948e15d0be6
F1 retained Quick Clock family seam

652d54f6d0ae772a5e2f617021ec38d092573444
F1 visual acceptance matrix + retained multi-instance/toggle gates

Independent source/architecture audit: GREEN
```

The retained Clock implementation is accepted.

F1 is not yet CLOSED because the family-retirement contract still requires caller proof and deletion of
the old Clock pixel presenter/presentation-only tests after GREEN. That bounded closure step is active.

Source outranks this plan if a later checkpoint has landed.

---

## Immediate work

### F1 caller proof + old Clock pixel retirement — ACTIVE

Do this before F2.

Read only the focused current owners needed for the slice:

- `Docs/QtQuick_Migration/10_Widget_Family_Port_Decomposition.md`
- `Docs/QtQuick_Migration/09_Widget_Quick_Presentation_Bridge.md`
- `Docs/QtQuick_Migration/11_Clock_Analogue_Shadow_Contract.md`
- current Clock caller/runtime source and focused tests

Required closure:

- caller-proof the retained `ClockPresentationModel` / `ClockPresentation.qml` path for Clock,
  Clock2 and Clock3 through the current Quick ordinary-widget host;
- preserve `GlobalClockTicker` as the sole one-second cadence owner;
- preserve settings/config/timezone/formatting and semantic mode-toggle behavior without exposing
  `SettingsManager`, QWidget or persistence objects to QML;
- prove the caller feeds canonical Card/Text shadow settings and Python-resolved direction into the
  retained model/style path;
- prove Clock/Clock2/Clock3 remain independent while sharing the existing process engine/window and
  ticker owner;
- caller-proof every old Clock pixel/presentation-only path before deletion;
- delete the old Clock QWidget pixel presenter and presentation-only tests once no destination behavior
  depends on them;
- do not delete shared neutral/runtime helpers still required by another family;
- do not retain an old Clock selectable/fallback presenter merely for safety.

Validation:

- focused Clock + retained-Quick tests;
- caller/runtime integration tests;
- exact digital -> analogue -> digital geometry round-trip;
- repeated settings/direction/mode mutation without item/model/ticker/engine/window recreation;
- `tools/qtquick_clock_smoke.py` at practical scale/DPR values before old-pixel deletion if that matrix
  has not actually been run on the current implementation;
- eyes-on digital/analogue, card on/off, calendar/timezone, separator, analogue shadow toggles,
  several directions/sizes and busy background;
- compile/import/static checks as relevant;
- caller scans, full diff/status and `git diff --check`.

After a clean post-push self-audit of this bounded retirement checkpoint:

```text
F1 -> CLOSED
F2 Weather -> ACTIVE immediately
```

Do not stop solely to wait for another external reviewer unless this retirement uncovers a real
architecture/lifecycle issue or unresolved YELLOW evidence.

---

## Active phase window

```text
F0    Imgur removal                              CLOSED
F0.5  shadow authority + General controls        CLOSED
F1    Clock / Clock2 / Clock3                    GREEN implementation; retirement ACTIVE
F2    Weather                                    NEXT after F1 caller-proof retirement
F3    Media core
F4    Media controls / volume / mute / progress
F5    Reddit / Reddit2
F6    Gmail
F7    Achievement Pulse
F8    Abandonment Issues
G     CUSTOM/input/auxiliary pixels
H     settings epoch + production cutover + old physical presenter deletion
I     residual debris sweep only
J     final installed/physical validation + docs closure
```

Steam Progress / Steam Journey and Friend Pulse are not migration phases. They are unfinished dev-gated
scaffolds. Do not create Quick parity ports for them. If their scaffold pixels later block shared legacy
cleanup, retire the scaffold rather than manufacturing a destination implementation.

Closed A–E implementation history belongs under `Docs/Historical_Plans/`, not here.

---

## Phase-F execution and audit policy

Normal slice:

```text
inspect exact source
-> implement narrow admitted work
-> focused tests / required eyes-on evidence
-> diff/status
-> commit intended paths
-> push
-> fresh post-push audit of that checkpoint
```

For ordinary F2–F8 family work, a fresh post-push **self-audit is sufficient** to continue when the
family's deterministic tests, required eyes-on evidence, caller proof and retirement checks are GREEN.

Do not stop after every ordinary family merely because an external independent reviewer is unavailable.

Stop for independent review when any of these is true:

- the slice creates or changes a cross-family/process/display architecture boundary;
- engine/window/thread/resource ownership changes;
- provider/runtime lifecycle ownership changes materially;
- a new shared asset/resource seam is introduced, e.g. Media dynamic-image delivery;
- deterministic and eyes-on evidence disagree;
- a blocker/YELLOW cannot be resolved confidently;
- the user explicitly requests independent audit.

H production cutover remains independently audit-required.

A holistic independent Phase-F audit may be requested after F8/before G when practical; it does not force
every normal family checkpoint to wait.

No routine hosted CI.
No routine full/Nuitka/installed build during ordinary Phase-F implementation.

---

## Destination invariants

```text
one selected physical display
    -> one QuickDisplayRuntime
    -> one standalone threaded QQuickWindow
    -> one retained Quick scene
    -> inline QSGRenderNode custom GL where required
```

Hard rules:

- no `QQuickWidget` runtime presenter;
- no extra accelerated top-level widget/visualizer/effect windows;
- no permanent QWidget/QRhi fallback presenter;
- no screenshot-to-texture QWidget compatibility architecture;
- providers/models/persistence/business logic remain Python-owned;
- QML receives explicit presentation state and emits semantic actions;
- QML does not own `SettingsManager`, providers, refresh cadence or business side effects;
- transition and visualizer custom GL remain inline in the one Quick scene;
- Visualizer authored logical cadence remains independent of presentation cadence;
- ordinary widget fade is one retained root opacity;
- no QWidget dummy/effect-carrier/`QGraphicsEffect` choreography in Quick;
- ordinary text shadow is duplicate retained glyph + offset, no blur;
- ordinary card shadow uses retained `OverlayCard` / cached `RectangularShadow`;
- shadow direction is resolved in Python before QML;
- real product resilience survives: network/cache/provider recovery, transition recovery and Visualizer
  display failover/reclaim.

---

## Family retirement policy

For each substantive F1–F8 family:

```text
old family source = temporary visual/behavioral reference
-> build retained Quick family
-> focused + eyes-on proof
-> family GREEN
-> caller proof
-> delete old family pixel presenter/presentation-only tests
-> next family
```

Family GREEN may come from independent review where required or a fresh post-push self-audit under the
policy above.

Do not carry completed old family pixels to H/I merely as fallbacks. Git becomes historical pixel
reference after deletion.

Shared legacy helpers remain only while a still-unported family genuinely requires them.

Temporary migration adapters are allowed only when they detach already-proven authored/logical state
into the destination contract, do not preserve old pixels/selectable presenters, and have an explicit
retirement owner.

---

## F1 Clock audit result

Independent source/architecture review found the retained implementation GREEN:

- one stable `ClockPresentationModel` per logical Clock instance;
- existing `GlobalClockTicker` remains the shared one-second cadence owner;
- one `clocks` family registry entry rather than duplicate Clock2/Clock3 component types;
- family components use the existing process `QQmlEngine` and per-display
  `OrdinaryWidgetPresentationHost`;
- canonical Card/Text shadow settings and global direction are projected in Python;
- direction/style/feature changes mutate retained state in place;
- root opacity remains the sole whole-widget fade;
- digital and analogue use exact stored geometry variants;
- separator is 2 logical px at ~0.77 of inner width and is available in analogue when applicable;
- calendar/day/date and timezone use the same ordinary retained Text-shadow semantics;
- analogue ring/markers, Roman-numeral main+contact passes, hand shadows and `analog_face_shadow`
  gating match the protected family contract;
- static analogue face/numeral identity survives ticks;
- three differently configured Clock instances are explicitly gated for independent state while sharing
  the engine/ticker owner;
- Clock QML introduces no Timer, MultiEffect, layer capture, QWidget, SettingsManager or
  QGraphicsEffect choreography.

Remaining F1 work is caller proof + legacy pixel retirement, not reimplementation of the accepted
retained Clock family.

---

## Early cleanup already admitted

### Old transition pixels

All canonical transitions already have Quick implementations.

Caller-proven old `TransitionFactory` / `gl_compositor_*_transition.py` renderers may retire before H.
Preserve canonical registry/settings identity, request/run semantics, destination-used authored
shader/math, direction/easing semantics and deterministic transition recovery.

If final removal is deeply entangled with `DisplayWidget`, leave that physical-host seam to H.

### Old visualizer pixels

Do not delete the visualizer tree by name.

Preserve destination-used:

- `VisualizerLogicalRuntime`;
- mode frame runtimes/authored algorithms;
- BeatEngine/source ownership;
- immutable render state;
- snapshot bridge/adapters feeding Quick;
- shaders/math reused by Quick.

Caller-proven old compositor-only card/overlay/pixel owners may retire early.

---

## G — CUSTOM/input

Destination geometry key:

```text
(widget_id, display_identity, geometry_variant)
```

Clock digital/analogue have separate committed geometry.

Save/Cancel/edit affects only the active variant; recreate/restart preserves both; topology/DPR clamping
must not create cumulative drift.

### Edit-mode X close affordance

Every adjustable card shown in CUSTOM edit mode must have an `X` close affordance.

The `X` mutates only the **working edit session** until Save:

- duplicate instance -> remove that duplicate instance from the working layout;
- single/non-duplicate widget -> set its working enabled state to the same ordinary/casual OFF state as
  unchecking that widget in its own Settings area;
- this is **not** family/capability deactivation and must not invoke the stronger special-control-system
  disable semantics;
- clicking `X` must not immediately persist settings, destroy provider/runtime ownership, or alter the
  committed layout.

Save/Cancel semantics:

- existing context-menu Save and Enter commit working geometry, duplicate removals and ordinary
  widget-enabled changes together;
- Cancel restores pre-edit geometry, duplicate-instance set and ordinary enabled state;
- closing a single widget and cancelling therefore makes it reappear exactly as before;
- cross-monitor/variant geometry edits remain scoped to the active
  `(widget_id, display_identity, geometry_variant)` target unless the action is explicitly an
  instance-level enabled/removal action.

Old QWidget edit/grid pixels retire after G GREEN.

---

## H — production cutover

H cuts production to the single Quick physical presenter and deletes the caller-proven old physical
presentation stack in the same architecture boundary:

- `DisplayWidget`;
- QRhiWidget / `GLCompositorWidget`;
- old compositor scheduling/presentation glue;
- unsupported software-renderer fallback;
- old render-backend demotion/selection used only by that fallback;
- obsolete `hw_accel`/fallback-overlay presentation policy;
- remaining old transition/visualizer physical-host debris;
- obsolete presentation-setting compatibility for the Quick settings epoch.

No production switch back to the old presenter.

H is audit-required.

---

## I — residue only

By I:

- ordinary family pixels are gone after F;
- old CUSTOM pixels are gone after G;
- old physical presentation is gone after H.

I removes only caller-proven leftovers: expired adapters, compatibility aliases, obsolete tests/tools,
comments and missed utilities.

---

## J — final closure

- installed/compiled validation;
- real multi-display/DPR/topology matrix;
- physical continuity/presentation evidence;
- widget/Visualizer eyes-on parity;
- final performance/tail checks;
- test inventory reconciliation;
- docs closure;
- migration-only harness/archive cleanup.

---

## Current evidence / acceptance debt

Independent review inspected exact pushed F1 source, QML, focused tests, current contracts and main
through `bce5c64d`.

The reviewer did **not** execute the Windows/PySide Qt suite or independently view generated
`qtquick_clock_smoke.py` PNGs in this environment. Runtime/test/eyes-on execution results from the
implementation agent remain attributed to that agent.

Before old Clock pixel deletion, ensure the real Quick smoke matrix has actually been run on the current
implementation at practical scale/DPR values and visually accepted.

The unrelated Bubble cadence harness debt from the visualizer card-surface cleanup was repaired at
`bce5c64d` using the real `VisualizerRuntimeController`/Bubble runtime fixture and removed from
`Future_Cleanup.md`.

Settings-GUI shadow polish is separate from runtime widget shadow authority and is not a migration
sequencing blocker.

`Docs/TestSuite.md` remains the canonical 359-module inventory. Its phase-status prose does not override
this plan's sequencing.
