# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-24

## Current reviewed checkpoint

Independent review basis:

```text
3a5626325891ec10343d53b0e88d5fd3c4b6469d
Phase E4 global eight-direction shadow authority + retained shadow normalization — independently audited GREEN; Phase E CLOSED
```

The E4 audit verified the actual pushed source rather than relying on implementation prose. The
canonical `ShadowDirection` resolver owns orientation only, QML consumes signed offsets rather than
settings, `OverlayCard` caches its ordinary static `RectangularShadow`, and `ShadowedText` now matches
the surviving offset-duplicate-glyph semantic with no `MultiEffect`/layer/text-blur path. Direction
updates can mutate an existing retained shell without creating a new engine/window/item. No family was
ported during E4.

Earlier independently closed Phase-E checkpoints remain:

```text
4466c306...  — E1 presentation-neutral widget runtime/model/provider ownership
b787c57a...  — E2 capability activation + SETUP foundation
5b3cbaef...  — E2.7 Visualizer CUSTOM failover/reclaim
1f25a791...  — E3 retained ordinary-widget host + shell primitives
```

Always inspect exact current `main` before acting. Repository state outranks this file if a later
checkpoint has landed.

---

# 1. Authority and workflow

`Current_Plan.md` is the active execution authority. Detailed technical decompositions are subordinate
to it.

Use:

```text
exact current source / pushed diff
        ↓
Current_Plan.md
        ↓
Spec.md + Docs/Compositor_Architecture.md + Docs/Contracts.md
        ↓
Docs/Guardrails.md + relevant focused guardrail
        ↓
ONLY the active Docs/QtQuick_Migration decomposition
        ↓
focused tests / current evidence
```

The local worktree is the mutation authority. Repository connectors/APIs are read/audit tools, not the
normal SRPSS write path. SRPSS does not use hosted CI as the normal migration gate.

Normal low-risk slice:

```text
inspect exact current source
-> implement narrow slice
-> focused gate
-> inspect diff/status
-> commit intended paths only
-> push
-> continue
```

Architecture/lifecycle/settings/cutover/high-risk visual slices add:

```text
-> STOP
-> independent audit of the pushed checkpoint
```

Do not run full/Nuitka/installed builds merely as routine Phase C–G validation. Keep packaging current
and use the smallest environment capable of proving the claim.

---

# 2. Active execution window

| Phase | Current status | Implementation permission |
| --- | --- | --- |
| A — bootstrap/render-node proof | **CLOSED** | Do not reopen without contradictory evidence |
| B — runtime-host decomposition | **CLOSED** | Do not reopen without contradictory evidence |
| C — base image + transitions | **IMPLEMENTATION CLOSED** | Explicit acceptance debt or demonstrated regression only |
| D — visualizer | **IMPLEMENTATION CLOSED** | Demonstrated regression only |
| E — widget presentation + capability setup foundation | **CLOSED / independently GREEN through E4** | Reopen only on contradictory evidence |
| **F — widget families** | **IN PROGRESS: F0 ACTIVE NEXT** | **Normal implementation work belongs in F0 now** |
| G — CUSTOM/input/auxiliary pixels | Waiting for F | Decomposition/reference only |
| H — settings epoch + production cutover | Waiting for A–G implementation | Reference only |
| I — legacy presenter deletion | Waiting for H cutover | Reference only |
| J — tooling/final validation/docs closure | Waiting for migration implementation | Reference only |

Physical/compiled/eyes-on acceptance debt from structurally closed phases remains operator-scheduled
unless current evidence reopens a specific defect.

---

# 3. Destination architecture — unchanged

```text
ScreensaverEngine
    |
    +-- providers / image queue / settings / persistence / media
    |
    +-- DisplayManager
            |
            +-- QuickDisplayRuntime (one per selected physical display)
                    |
                    +-- QuickDisplayWindow : QQuickWindow
                    |
                    +-- QuickSceneController
                    |       |
                    |       +-- background/transition QSGRenderNode item
                    |       +-- visualizer QSGRenderNode item
                    |       +-- retained ordinary-widget host/items
                    |       +-- dimming / halo / edit overlays
                    |
                    +-- RuntimeInputController
                    +-- WidgetRuntimeManager
                    +-- CustomLayoutSession
```

The production migration still targets one presenter:

```text
current QWidget / QRhiWidget runtime presentation
                    ↓
one standalone threaded QQuickWindow per physical display
                    ↓
Qt Quick retained scene + inline custom GL render nodes
```

No `QQuickWidget`, no permanent QRhiWidget fallback, no extra accelerated window per widget, no
screenshot-to-texture QWidget compatibility layer, and no permanent dual presenter.

---

# 4. Closed Phase-E foundations

## E2 / E2.7 — CLOSED

Application-level capability activation remains distinct from ordinary instance enabled state.
Visualizers remains a canonical capability family requiring Media while retaining its special
Phase-D runtime/render ownership.

The E2.7 global Visualizer CUSTOM failover/reclaim lifecycle remains closed and binding. Do not
generalize its singleton failover machinery into ordinary family hot reload.

## E1 — CLOSED / independently GREEN @ `4466c306`

Preserve:

- one legal state/lifetime authority for each provider/controller/timer/poll/action stream;
- shared work shared only where product semantics are shared;
- per-instance/per-display state separate where configuration differs;
- no family-exclusive owner constructed merely because presentation exists;
- fresh-process deactivated-family import dormancy;
- valid repeated setup may replace a presentation edge without rebuilding the neutral owner;
- presentation retirement never becomes provider/runtime retirement by accident.

Do not move runtime ownership back into QML, `QuickSceneController`, or family presentation classes.

## E3 — CLOSED / independently GREEN @ `1f25a791`

Landed substrate:

```text
QuickSceneFactory
    -> one process-level QQmlEngine
    -> compiled DisplayScene.qml
    -> compiled OverlayWidget.qml

QuickSceneController (per display)
    -> DisplayScene.qml root
    -> ordinaryWidgetHost
    -> OrdinaryWidgetPresentationHost
            -> RetainedOverlayWidget
                    -> OverlayWidget.qml
                            -> OverlayCard.qml
                            -> future family content
```

Landed shared QML primitives:

```text
OverlayWidget.qml
OverlayCard.qml
ShadowedText.qml
Separator.qml
```

The E3 architecture is closed. Do not invent more generic primitives before a real family earns them.
The first real family may establish the smallest missing component/model binding seam.

### E3 post-audit correction carried into E4

E3 proved the retained seam; it did not freeze every provisional primitive property forever.

Legacy text-shadow evidence has **no authored text-blur control**. Ordinary text and header shadows are
offset duplicate-text passes with color/alpha and font-size-dependent magnitude. E4 therefore removed
the provisional E3 `ShadowedText.qml` `MultiEffect`/`shadowBlur` path rather than canonizing unearned
behavior.

E3 initially landed `RectangularShadow.cached: false` as a conservative substrate default. E4 corrected
the retained card primitive to `cached: true`, matching the overwhelmingly static SRPSS card-shadow
workload while allowing Qt to invalidate the cache naturally on style/geometry/direction changes.

---

# 5. E4 — global shadow authority + retained shadow normalization — CLOSED / independently GREEN @ `3a562632`

Read together:

- `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- `Docs/QtQuick_Migration/09_Widget_Quick_Presentation_Bridge.md`
- current `rendering/quick/qml/OverlayCard.qml`
- current `rendering/quick/qml/ShadowedText.qml`
- legacy `core/settings/shadow_tuning.py`
- legacy `widgets/shadow_utils.py`
- current settings/defaults tests

This is an architecture/style-authority slice and therefore **audit-required**.

## E4.1 One eight-direction authority

Landed canonical token:

```text
NW  N  NE
 W     E
SW  S  SE
```

Default: `SE`.

Preferred presentation-neutral form:

```text
ShadowDirection.NW
ShadowDirection.N
ShadowDirection.NE
ShadowDirection.W
ShadowDirection.E
ShadowDirection.SW
ShadowDirection.S
ShadowDirection.SE
```

Direction owns orientation only.

For an authored magnitude `(mx, my)`:

```text
NW -> (-mx, -my)
N  -> (  0, -my)
NE -> (+mx, -my)
W  -> (-mx,   0)
E  -> (+mx,   0)
SW -> (-mx, +my)
S  -> (  0, +my)
SE -> (+mx, +my)
```

Axis-only directions zero the perpendicular axis. Do not turn direction into a second magnitude
setting.

## E4.2 Resolve direction before QML

`SettingsManager` must not be exposed to QML.

Preferred flow:

```text
canonical setting
    ↓
presentation-neutral shadow resolver
    ↓
resolved signed card/text/header/control offsets
    ↓
stable presentation style/model
    ↓
retained QML properties
```

QML consumes signed offsets only. It does not parse persistence, query settings, or independently map
the direction token.

## E4.3 Card shadows: cache by default

For retained ordinary cards:

- `RectangularShadow.cached` is **true by default**;
- a style/geometry/direction change invalidates/rebuilds the Qt shadow cache naturally;
- whole-widget fade changes root opacity and must not animate/rebuild blur/spread/direction;
- do not animate card blur/spread merely to reproduce fade;
- if a future effect intentionally animates its shadow continuously, that effect may explicitly opt out
  of caching rather than making the shared primitive uncached.

Do not create a second Python pixmap/texture cache around `RectangularShadow`.

## E4.4 Text/header shadows: no MultiEffect unless a real authored feature earns it

Current SRPSS text-shadow source authority uses:

```text
enabled
color/alpha
offset magnitude
font-size-dependent magnitude selection/scaling
```

It does **not** expose authored ordinary-text blur.

Destination ordinary `ShadowedText` therefore uses:

```text
main retained Text
+
duplicate retained shadow Text at signed offset
```

No `MultiEffect`, no `layer.effect`, no `shadowBlur` destination property merely because E3 temporarily
proved that the effect could load.

This is not a permanent ban on every future MultiEffect use. A later feature may introduce one only
when:

1. surviving/current product behavior genuinely requires that visual; or
2. a deliberate new product feature explicitly authors it; and
3. the performance/lifetime cost is accepted.

Header shadows may retain separate alpha/magnitude from ordinary text, but consume the same global
direction authority.

## E4.5 Preserve alpha/fade distinctions

Do not collapse:

```text
root widget fade opacity
card/background alpha
border alpha
card shadow alpha
text color alpha
text shadow alpha
header shadow alpha
```

A global direction change must not alter any magnitude/blur/spread/alpha/color setting.

## E4.6 Required E4 tests

At minimum prove:

- all eight direction mappings;
- axis-only perpendicular zeroing;
- default `SE`;
- malformed/unknown persisted token resolves through the documented deterministic policy;
- card/text/header magnitudes remain distinct;
- signed negative offsets remain unclipped;
- `OverlayCard` shadow caching is enabled;
- root fade does not rewrite shadow properties;
- changing direction changes retained properties without recreating the widget/engine/window;
- `ShadowedText.qml` uses no `MultiEffect`, layer capture or text blur;
- ordinary text-shadow result remains the legacy offset-pass semantic;
- settings/default/persistence plumbing is canonical and not duplicated in QML;
- existing E3 host/lifecycle/card-alpha tests remain green.

Do not port a widget family during E4.

### E4 closure evidence

Independent source audit at `3a562632` is **GREEN**.

Verified structural result:

- canonical eight-direction `ShadowDirection`, default `SE`, deterministic malformed-token fallback;
- direction changes signs/axis only and cannot overwrite per-class authored magnitude;
- canonical settings/default/model persistence path exists; QML contains no direction/settings parser;
- `OverlayCard` ordinary static shadow is `cached: true`;
- `ShadowedText` is retained duplicate glyph + signed offset only;
- root fade leaves shadow magnitude/blur/spread/direction properties untouched;
- retained direction/style update keeps the same shell item, engine and top-level window;
- E3 host/lifecycle/signed-offset invariants remain intact.

The retained direction test necessarily supplies already-resolved offsets because no real family exists
yet. This is not unfinished E4 work. F1 Clock is the first required end-to-end proof that a family
style projection reads the canonical direction, resolves it in Python and publishes signed card/text
offsets to retained QML.

---

# 6. Phase-E closure review — CLOSED

Phase E is **CLOSED** at `3a562632`. Independent review found no current evidence contradicting
E1/E2/E2.7/E3/E4.

Closure invariants:

- capability activation still gates implementation/runtime ownership before family-heavy resolution;
- runtime/model/provider owners remain presentation-neutral;
- one Quick ordinary-widget host exists per display scene;
- the shared shell has one root-fade authority and one card-shadow implementation;
- one canonical shadow direction maps to signed presentation offsets;
- ordinary text shadows retain their actual offset-pass semantics without unearned blur machinery;
- no widget family has been prematurely moved into QML business logic;
- no extra top-level presentation surface exists;
- QWidget-era dummy/effect-carrier objects and staged shadow-fade workarounds are not destination
  architecture: Quick whole-widget fade is one outer retained-root opacity applied to the complete
  composition, including its cached card shadow and text-shadow glyphs.

Physical visual tuning remains explicit acceptance debt until real retained families exist. It does not
reopen Phase E by itself.

---

# 7. Phase F — ordinary widget families — ACTIVE / F0 NEXT

Detailed family-port decomposition:

`Docs/QtQuick_Migration/10_Widget_Family_Port_Decomposition.md`

High-level sequence:

```text
F0  remove deprecated Imgur
F1  Clock / Clock2 / Clock3
F2  Weather
F3  Media core
F4  Media volume / mute / progress / controls
F5  Reddit / Reddit2
F6  Gmail
F7  Steam Progress
F8  Achievement Pulse
F9  Abandonment Issues
F10 Friend Pulse
```

The order may be narrowed by exact-source evidence, but do not jump to a complex family merely to avoid
finishing the first generic family binding seam.

## Phase-F hard rule — do not port QWidget effect-carrier/dummy architecture

The first real family must start from the retained Quick composition model, not mechanically reproduce
QWidget/QGraphicsEffect workarounds.

Forbidden destination pattern:

```text
real widget/content
    -> dummy/wrapper only to own opacity/effect
        -> dummy/wrapper only to own shadow/effect
```

Do not port `ShadowFadeProfile`/`QGraphicsOpacityEffect`-style staged fade/shadow attachment, dummy
shadow carriers, or equivalent wrapper choreography into Quick families merely because current QWidget
code needs it.

Destination whole-widget fade is:

```text
OverlayWidget.fadeOpacity
    -> outer retained root opacity
    -> card + cached card shadow + text-shadow glyphs + content fade coherently as one subtree
```

Card-shadow alpha, text-shadow alpha, background alpha and border alpha remain independent authored
style controls. They are **not separate fade stages**.

An intermediate Quick `Item` is valid when it owns a real responsibility such as layout, transform,
clipping, z grouping, input or lifecycle composition. It is not justified solely to work around the
old one-graphics-effect-per-QWidget limitation.

Every Phase-F family audit must explicitly check that no legacy effect-carrier/dummy/staged-shadow-fade
structure was copied into the retained presentation.

Frosted/backdrop-glass card customization is deliberately **not** Phase-F migration work. Its future
shared-per-display/lazy backdrop architecture is recorded in `Future_Work.md`; do not introduce backdrop
capture, blur layers or glass-specific effect machinery while proving the ordinary retained families.

## F0 — remove Imgur instead of porting it

Remove the live gate/defaults/settings controls/descriptor/runtime/provider/CUSTOM/tests/package/current
authority references that exist solely for deprecated Imgur. Do not create an Imgur Quick component.

## F1 — Clock family: first retained family seam

Clock is deliberately first because its ticker/timezone computation is already presentation-neutral and
it does not require provider I/O, dynamic artwork or repeating list models.

F1 establishes the smallest real family component/model binding mechanism on top of E3.

### Clock required product changes during the port

These are intentional improvements, not accidental parity drift:

1. **Separator thickness:** 2 logical px.
2. **Separator width:** target approximately 40% wider than the legacy 0.55 ratio, i.e. about `0.77` of
   available inner Clock width. Do not retain a legacy pixel ceiling that defeats the intended widening
   on large clocks; final eyes-on tuning may adjust the ratio in roughly the `0.75–0.80` range.
3. **Separator spacing:** one symmetric gap authority above and below the separator. Do not preserve the
   legacy `8 px above / 6 px below` asymmetry.
4. **Analogue parity:** when the separator option is enabled and calendar/day/date content exists, the
   analogue presentation also renders the separator between the face and calendar content.
5. **Calendar/day/date text shadow:** use the same resolved ordinary-text shadow semantics as the
   timezone text unless a demonstrated authored exception exists. The timezone appearance is the
   reference; do not preserve an independently over-offset day/date shadow.
6. **No text blur:** Clock text, calendar and timezone shadows are offset duplicate glyphs under E4.
7. **No legacy fade carrier:** Clock whole-widget fade uses the retained `OverlayWidget` root opacity;
   do not create a separate shadow fade, dummy carrier or staged effect attachment.
8. **First real E4 wiring proof:** Clock style projection reads the canonical global direction in
   Python, resolves the Clock card/ordinary-text/large-text magnitudes to signed offsets, and publishes
   those offsets to the retained item. A direction change must update the existing Clock presentation
   without recreating its item/model/ticker/engine/window.

The legacy persisted key may remain `show_digital_separator` as migration input until the H0 settings
epoch. The presentation model should expose a semantic property such as `showSeparator`; do not let the
old key name dictate the final visual contract.

### Clock geometry-variant contract

`digital` and `analog` are distinct presentation geometry variants.

CUSTOM semantics must eventually be:

```text
Clock instance + physical display
    ├── digital  -> exact last committed digital rect/size payload
    └── analog   -> exact last committed analogue rect/size payload
```

A live switch restores the target variant's remembered geometry.

It must **not** repeatedly derive the next target rectangle from the current mode's already-derived
rectangle. The current QWidget `handle_double_click()` / `_rebuild_custom_rect_for_mode()` behavior is
migration source only; it must not become the final authority.

For a target variant with no saved geometry:

1. derive one sensible initial rect from the current visual center + target natural size;
2. clamp once to the current display;
3. establish that rect as the target variant's remembered baseline.

After both variants exist:

```text
digital A
-> analog B
-> digital A exactly
-> analog B exactly
```

Repeated round trips must not drift.

F1 establishes/tests the variant semantics and presentation interface. Phase G owns final
`CustomLayoutSession` persistence/edit implementation for exact per-variant committed rectangles.

---

# 8. Phase G — CUSTOM/input/auxiliary pixels — waiting for F

Use `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`.

One important contract is now fixed before G begins: generic CUSTOM persistence must support a widget
with more than one presentation geometry variant. It cannot assume one permanent rectangle per widget
id.

For Clock:

- editing/resizing digital commits only digital geometry;
- editing/resizing analogue commits only analogue geometry;
- switching presentation mode restores the target variant without mutating the inactive variant;
- Save persists the active variant transaction;
- Cancel restores the active variant baseline without damaging the inactive variant;
- recreate/restart preserves both;
- display identity scopes the pair appropriately;
- topology/DPR clamping is explicit and must not create cumulative round-trip drift.

---

# 9. H–J routing

## H — settings epoch + production cutover

Create the new Quick presentation settings epoch, remove obsolete presentation-key compatibility where
planned, cut production to the single Quick presenter, and audit the lifecycle/cutover checkpoint.

## I — legacy presenter deletion

After H cutover, delete old runtime presenter/widget pixel owners and old compatibility paths. Preserve
only presentation-neutral product logic that still has a destination owner.

## J — final validation/docs closure

Run the explicit installed/compiled/multi-display/visual acceptance matrix, reconcile tests/docs, and
archive obsolete migration-only evidence.

---

# 10. Known evidence limits / watch items

- E4 source/architecture is independently audited GREEN at `3a562632`. The reviewer independently
  inspected pushed source/tests/contracts but did not independently rerun Claude's Windows test commands.
- The previously reported real-two-display topology timing flake remains historical/non-blocking evidence
  unless it reproduces against current work.
- Physical widget-shadow visual parity remains an eyes-on gate once real retained family content exists.
- Card-shadow caching is architectural default; measure whole-scene GPU/memory behavior with several real
  retained widgets once Phase F supplies them.
- F1 must prove the real settings/resolver/style-to-QML direction path; E4 intentionally had no family
  consumer to exercise that end-to-end.
- Do not convert performance measurements into permission to remove authored visuals.

---

# 11. Immediate next checkpoint

```text
F0 — remove deprecated Imgur instead of porting it

Scope:
- inspect exact current Imgur family/gate/default/settings/descriptors/runtime/provider/CUSTOM/package refs
- remove only current-authority Imgur product surface and its three Imgur test modules
- preserve historical evidence docs unless they falsely claim Imgur is current
- update canonical family/catalog/default/settings/test inventory after deletion
- prove fresh-process/catalog/settings/package integrity

Do not begin Clock/F1 in the same checkpoint.
Do not alter surviving provider families.
Do not run full/Nuitka/installed builds as routine validation.

commit + push
STOP for independent audit because this is a broad deletion boundary
```

After F0 GREEN, F1 Clock is the first retained family port and must obey the no-effect-carrier/root-fade
rule above.
