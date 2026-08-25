# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-25

## Current checkpoint

Reviewed pushed implementation basis:

```text
8c9fd46871738cb66707467d19782a18f6e9e748
final F0.5 sidecar-only shadow behavior correction pushed
Independent audit: YELLOW — correction checkpoint awaiting audit
```

F0.5's canonical Settings/model/direction-picker/save work remains intact. The bounded implementation
correction is complete at the pushed checkpoint above. Do not begin F1 until independent audit marks
F0.5 GREEN.

Source outranks this plan if a later checkpoint has landed.

## Immediate work

### F0.5 independent audit — ACTIVE

Do only this before F1.

Read:

- `Docs/Custom_Style_Implementation.md` — F0.5 shadow authority;
- `Docs/QtQuick_Migration/10_Widget_Family_Port_Decomposition.md` — phase order;
- `Docs/QtQuick_Migration/11_Clock_Analogue_Shadow_Contract.md` — protected family-authored behavior.

Audit checklist:

- [ ] inspect exact pushed source at `8c9fd46871738cb66707467d19782a18f6e9e748`;
- [ ] confirm canonical Settings/model/default/direction-picker/save behavior remains intact;
- [ ] confirm no loader/file/local constants retain retired `card`, `text`, `text_large`, `header`,
  `icon`, `control`, or `volume_slider` numeric/style authority;
- [ ] confirm no replacement compatibility tuning or hidden/shared profile exists;
- [ ] confirm generic shadow-only tests were retired without weakening content/runtime/interaction
  coverage;
- [ ] confirm Clock analogue ring/marker, Roman-numeral, hand and `analog_face_shadow` behavior remains
  independently authored and unchanged;
- [ ] record any precise blocker, or mark F0.5 GREEN.

Do not modify or begin F1 as part of this checkpoint. STOP after the independent audit decision.

After GREEN: **F1 Clock becomes active immediately.**

---

## Active phase window

```text
F0    Imgur removal                              CLOSED
F0.5  shadow authority + General controls        YELLOW — independent audit pending
F1    Clock / Clock2 / Clock3                    NEXT
F2    Weather
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

Steam Progress / Steam Journey and Friend Pulse are **not migration phases**. Current source describes
them as unfinished dev-gated scaffolds. Do not create Quick ports for placeholder widgets. Their actual
product implementation is deferred outside the migration; leave the dev-gated stubs alone unless they
block a shared cleanup boundary.

Closed A–E implementation history does not belong in this file. See
`Docs/Historical_Plans/QtQuick_Migration_Phase_E_Closure_2026-08-24.md` only when historical closure
context is actually needed.

---

## Execution routing

```text
exact current source
    -> Current_Plan.md
    -> relevant focused current contract/decomposition only
    -> focused tests/current evidence
```

For Phase F:

- `Docs/QtQuick_Migration/10_Widget_Family_Port_Decomposition.md`
- `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- `Docs/QtQuick_Migration/09_Widget_Quick_Presentation_Bridge.md`
- for Clock: `Docs/QtQuick_Migration/11_Clock_Analogue_Shadow_Contract.md`
- `Docs/10_WIDGET_GUIDELINES.md`
- `Docs/TestSuite.md`

Do not read all historical plans/reports by default.

Normal slice:

```text
inspect exact source
-> implement narrow admitted work
-> focused tests
-> diff/status
-> commit intended paths
-> push
```

Architecture/settings/lifecycle/cutover/high-risk visual checkpoints then STOP for independent audit.

No routine hosted CI. No routine full/Nuitka/installed build during ordinary Phase-F implementation.

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
- real product resilience survives (network/cache/provider recovery, transition recovery, Visualizer
  display failover/reclaim).

---

## Legacy/reference retirement policy

Keep old code only while it is useful evidence for an unproven destination owner.

For each substantive ordinary family admitted above:

```text
old family pixels/source = temporary visual/behavioral reference
-> build retained Quick family
-> focused + eyes-on proof
-> independent GREEN
-> caller proof
-> delete old family pixel presenter/presentation-only tests
-> next family
```

Do not carry completed family presenters to H/I merely as fallbacks. Git becomes the historical pixel
reference after deletion.

Shared legacy helpers remain only while a still-unported family genuinely requires them.

Temporary migration adapters are allowed only when they detach already-proven logical/authored state into
the destination contract, do not preserve old pixels/selectable presenters, and have an explicit
retirement owner.

---

## F1 Clock minimum bar

Read:

- `Docs/QtQuick_Migration/10_Widget_Family_Port_Decomposition.md`
- `Docs/QtQuick_Migration/11_Clock_Analogue_Shadow_Contract.md`
- `Docs/QtQuick_Migration/09_Widget_Quick_Presentation_Bridge.md`

F1 proves the first real ordinary-family presentation seam:

- existing `GlobalClockTicker` stays the one-second time owner;
- stable presentation-oriented state/model;
- existing process Quick engine/window reused;
- no provider/settings/business object exposed to QML;
- canonical Card/Text shadow settings + global direction project through Python into retained properties;
- style/direction changes update the existing Clock without recreating item/model/ticker/engine/window;
- one retained-root fade; no dummy/effect carriers;
- digital and analogue are distinct geometry variants with exact round-trip restoration;
- static analogue face/numerals are retained across ticks;
- bespoke analogue ring/marker/two-pass numeral/hand shadow personality is preserved;
- ordinary day/date/timezone use ordinary Text shadow semantics;
- separator improvements in the family decomposition land deliberately.

After F1 GREEN, caller-proof and retire old Clock pixels before F2 unless deletion crosses a shared
architecture boundary requiring its own audit.

---

## Early cleanup already admitted

These are cleanup opportunities, not automatic reasons to interrupt the active F0.5/F1 sequence.

### Old transition pixels

All 12 canonical transitions already have Quick implementations and Phase C is closed.

Old `TransitionFactory` + `transitions/gl_compositor_*_transition.py` pixels are **not**
reference-protected like an unported widget family.

Caller-proven old transition renderers may be deleted before H. Preserve:

- canonical transition registry/settings identity;
- transition request/run semantics;
- authored shader/math genuinely reused by Quick;
- direction/easing/parameter semantics used by Quick;
- deterministic transition recovery product behavior.

If final removal is deeply entangled with `DisplayWidget`, leave that physical-host seam to H rather
than inventing compatibility architecture.

### Old visualizer pixels

Do not delete the entire old visualizer tree by name.

Preserve destination-used:

- `VisualizerLogicalRuntime`;
- mode frame runtimes/authored algorithms;
- BeatEngine/source ownership;
- immutable render state;
- snapshot bridge/adapters currently feeding Quick;
- shaders/math genuinely reused by Quick.

Caller-proven old compositor-only visualizer card/overlay/pixel owners may retire before H.
Do not rebuild proven logical behavior merely to remove a file named `legacy`.

---

## G — CUSTOM/input

Destination geometry key must support:

```text
(widget_id, display_identity, geometry_variant)
```

Clock digital/analogue have separate committed geometry.

Save/Cancel/edit affects only the active variant; recreate/restart preserves both; topology/DPR clamping
must not create cumulative drift.

Old QWidget edit/grid pixels retire after G GREEN.

---

## H — production cutover

H cuts production to the single Quick physical presenter and deletes the caller-proven old physical
presentation stack in the same architecture boundary:

- `DisplayWidget`;
- QRhiWidget / `GLCompositorWidget`;
- old compositor scheduling/presentation glue;
- unsupported software-renderer fallback;
- `display.render_backend_mode` demotion/selection used only by that fallback;
- obsolete `hw_accel`/fallback-overlay presentation policy;
- old transition/visualizer physical-host debris not already safely removed;
- obsolete presentation-setting compatibility for the Quick settings epoch.

No production switch back to the old presenter.

H is audit-required.

---

## I — residue only

I is not bulk presenter deletion.

By I, ordinary family pixels should be gone after F, old CUSTOM pixels after G, and old physical
presentation after H.

I removes only caller-proven leftovers such as expired migration adapters, compatibility aliases,
obsolete tests/tools/comments and missed utilities.

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

Independent review here inspected exact pushed source/contracts but did not rerun Claude's Windows
commands.

Claude reported at `a586801d`:

- F0.5 focused file: 9 passed;
- fast settings/model/default/direction gate: 202 passed;
- relevant Qt widget batch otherwise green;
- one Clock footer test failed once in a mixed batch but passes isolation/full Clock module and baseline,
  consistent with existing cross-test pollution.

New General shadow controls still need normal eyes-on UI confirmation.

`Docs/TestSuite.md` remains the canonical 359-module inventory. Its phase-status prose does not override
this plan's sequencing.
