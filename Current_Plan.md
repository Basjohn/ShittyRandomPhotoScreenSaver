# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-25

## Current checkpoint

Exact main inspected through:

```text
a7bfd8a5e26fb4a692945f8f06d3fe53bddf2b40
Phase F5 Reddit / Reddit2 closure and legacy-presentation retirement
```

F1 implementation basis:

```text
09c1a215fe28ffbaee51897e81d22948e15d0be6
F1 retained Quick Clock family seam

652d54f6d0ae772a5e2f617021ec38d092573444
F1 visual acceptance matrix + retained multi-instance/toggle gates

Independent source/architecture audit: GREEN
```

The retained Clock, Weather, complete Media and Reddit family implementations, caller proofs and bounded
old pixel retirements are complete. F1 through F5 are CLOSED.

Source outranks this plan if a later checkpoint has landed.

---

## Immediate work

### F6 Gmail — ACTIVE

Read only the focused current owners needed for the slice:

- `Docs/QtQuick_Migration/10_Widget_Family_Port_Decomposition.md`
- `Docs/QtQuick_Migration/09_Widget_Quick_Presentation_Bridge.md`
- `widgets/gmail_runtime.py`, `core/gmail/gmail_preparation.py` and current backend/runtime-service injection
- `widgets/gmail_widget.py` / `widgets/gmail_components.py` as temporary behavior and visual reference
- current Gmail factory, refresh, input, action-menu, sound/notification and CUSTOM-height callers
- focused runtime, preparation, retiring-runtime, settings, action, cache and presentation tests

Required implementation:

- inspect and separate Gmail backend/preparation/cache/cadence/notification ownership from QWidget
  presentation and action-menu state before moving pixels;
- introduce one retained Gmail component and stable presentation model with bounded, stable message
  identities and coherent loading/ready/cached/error state;
- preserve backend selection, account-slot/settings semantics, sender/subject cleanup and grouping,
  startup cache, stale-generation safety, notification detection and sound under Python ownership;
- emit semantic open-message/manual-refresh/action-menu requests from QML; QML must not own URLs,
  backend work, mutation authority, persistence, cadence or notification side effects;
- preserve configured capacity, dynamic content height, header/row/boundary styling and ordinary
  interaction gating without porting QWidget pixmap caches or effect choreography;
- mutate retained rows/model/style in place without item/runtime/engine/window/backend recreation;
- after GREEN and caller proof, delete the old Gmail QWidget pixels and presentation-only tests while
  preserving neutral runtime/preparation/settings/notification contracts.

Validation:

- focused retained Gmail model/state/action/identity tests;
- backend/preparation/cache/grouping/notification/sound and stale-generation gates;
- account-slot/backend/settings behavior and stable message identity;
- interaction gating, open-link/manual-refresh/action-menu routing and CUSTOM-height behavior;
- repeated feed/settings mutation without item/model/runtime/engine/window/backend recreation;
- practical multi-DPR eyes-on matrix for loading/ready/cached/error, grouped messages, long text and
  configured row capacities;
- compile/import/static checks as relevant;
- caller scans, full diff/status and `git diff --check`.

Current F6 sequence:

```text
neutral Gmail runtime/preparation/notification ownership audit     -> GREEN
retained config/style + stable message projection model            -> implementation GREEN
static QML + semantic pointer/action presentation                  -> NEXT
real owner injection + runtime-shaped state/action/geometry gates  -> pending
caller proof + old Gmail QWidget pixel/cache/input retirement      -> pending
```

The existing `GmailRuntimeService` and shared runtime owner remain the presentation-neutral owners for
backend selection, startup cache, accepted immutable state, cadence, request generations, actions,
notification detection and sound. The first retained checkpoint adds bounded config/style projection,
stable message/thread identities and in-place row reprojection over that accepted state. QML and real
host caller proof remain the next live work; no second runtime service was introduced.

F5 closure evidence:

```text
one retained RedditPresentationModel/RedditPresentation.qml for Reddit + Reddit2: GREEN
independent manager-owned RedditRuntimeService leases and accepted feed identity: GREEN
cached-first/live-refresh/open/manual-refresh/geometry/style/no-recreation caller proof: GREEN
effective DPR 1.0, 1.5 and 2.25 threaded-OpenGL eyes-on matrix: GREEN
old Reddit QWidget factory/pixels/caches/hit routing/hover and presentation tests: deleted
provider/preparation/cache/rate-limit/helper/deferred-URL contracts: retained
post-implementation ownership/lifecycle self-audit: GREEN
```

F4 closure evidence:

```text
one retained Media model/item for core + controls + progress + app volume + system mute: GREEN
capability-gated semantic seek with accepted playback state remaining truth: GREEN
cached bounded soft progress glow; no visible seek handle: GREEN
neutral Media/app-volume/system-mute owners and Visualizer relationship preserved: GREEN
effective DPR 1.0, 1.5 and 2.25 threaded-OpenGL eyes-on matrix: GREEN
old Media controls/progress/volume/mute QWidget pixels, hit routing and presentation tests: deleted
temporary MediaWidget narrowed to a transparent runtime/Visualizer anchor until H: GREEN
post-implementation ownership/lifecycle self-audit: GREEN
```

F3 closure evidence:

```text
stable MediaPresentationModel + static MediaPresentation.qml: GREEN
one process-engine MediaArtworkImageProvider with stable identity/bounded cache: GREEN
real WidgetRuntimeManager lease -> ordinary-widget host activation/retirement: GREEN
focused Media/runtime/host gate + two-DPR threaded-OpenGL eyes-on matrix: GREEN
old QWidget header/metadata/artwork painters, caches, lifecycle and presentation-only tests: deleted
at F3, temporary QWidget anchor narrowed to F4-only pixels (subsequently retired): GREEN
post-implementation ownership/lifecycle self-audit: GREEN
```

F2 closure evidence:

```text
retained Weather model/QML + real runtime-owner injection: GREEN
old Weather QWidget factory/pixels/presentation-only tests: deleted
neutral provider/cache/cadence/request-generation owner: retained
```

---

## Active phase window

```text
F0    Imgur removal                              CLOSED
F0.5  shadow authority + General controls        CLOSED
F1    Clock / Clock2 / Clock3                    CLOSED
F2    Weather                                    CLOSED
F3    Media core                                 CLOSED
F4    Media controls / volume / mute / progress  CLOSED
F5    Reddit / Reddit2                           CLOSED
F6    Gmail                                      ACTIVE
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

Caller proof now crosses the current `QuickSceneController` ordinary-widget host with Clock/Clock2/
Clock3 settings projection, canonical shadow direction/style input, independent models and the shared
engine/ticker. The old `ClockWidgetFactory`, factory descriptors, QWidget presenter and its
presentation-only tests are deleted. Neutral settings, `GlobalClockTicker` and current CUSTOM metadata
remain for their destination owners. F1 is CLOSED.

## F2 Weather audit result

The retained Weather family now uses one stable `WeatherPresentationModel` injected with the existing
`WidgetRuntimeManager`-owned `WeatherRuntimeService` and created through the current ordinary-widget
host. Provider, startup cache, persistence, cadence, retry and request/location generation authority
remain in the neutral runtime owner. Loading, ready, cached-error, missing-location, packaged icons,
settings navigation and manual double-click refresh are destination-covered; canonical card/text style
and Python-resolved direction mutate in place. The old `WeatherWidgetFactory`, factory descriptor,
QWidget presenter/components and presentation-only tests are deleted. Runtime/cache/provider tests were
rehomed under `tests/test_weather_runtime.py`. F2 is CLOSED.

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

F1 independent review is GREEN. The caller-proof retirement checkpoint executed the focused retained
Clock/Quick gates and the affected legacy-owner suite. The real-OpenGL threaded
`qtquick_clock_smoke.py` matrix passed at Qt scale factors 1 and 1.5 (effective DPR 1.5 and 2.25), and
the generated digital/analogue, card/no-card and busy-background cases were visually accepted before
old Clock pixel deletion.

The unrelated Bubble cadence harness debt from the visualizer card-surface cleanup was repaired at
`bce5c64d` using the real `VisualizerRuntimeController`/Bubble runtime fixture and removed from
`Future_Cleanup.md`.

Settings-GUI shadow polish is separate from runtime widget shadow authority and is not a migration
sequencing blocker.

`Docs/TestSuite.md` remains the canonical 354-module inventory. Its phase-status prose does not override
this plan's sequencing.
