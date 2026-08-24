# 04 — Runtime Widgets, Retained Quick Presentation, Shadows and Full Customization

Status: **Phase-E/F technical decomposition; E2/E2.7 closed; E1 ACTIVE — Achievement Pulse slice 5 GREEN at `51948dc3`; Abandonment/Weather correction GREEN at `9ab4f47e`; Media audit active**
Last updated: 2026-08-24

Cross-links:

- sequence/work admission: `Current_Plan.md`
- landed capability activation / E2 UI: `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`
- canonical widget authoring guidance: `Docs/10_WIDGET_GUIDELINES.md`
- runtime ownership/cardinality/threading: `Docs/QtQuick_Migration/08_Widget_Runtime_Ownership_Threading.md`
- Quick widget state/model/assets/actions bridge: `Docs/QtQuick_Migration/09_Widget_Quick_Presentation_Bridge.md`
- style history: `Docs/Custom_Style_Implementation.md`
- deletion ledger: `Future_Cleanup.md`
- test retirement/rehome ledger: `Docs/TestSuite.md`

## 1. Core rule

Do not rewrite the widget ecosystem as QML business logic.

Split:

```text
provider / model / settings / refresh / actions
                    from
runtime pixel presentation
```

Keep the first side in Python unless a separate measured reason earns a different owner.

Move runtime pixels into the display's retained Quick scene.

## 2. Current architecture seam — CURRENT-LEGACY

The old widget stack combines responsibilities that must not be recreated as one giant Python Quick
base class.

`WidgetManager` / current widget setup code still mixes some combination of:

- concrete QWidget creation;
- provider/model lifecycle;
- positioning/stacking;
- visibility/fades;
- compositor readiness;
- live settings application;
- family-specific staging and runtime assumptions.

`BaseOverlayWidget` likewise combines QWidget lifecycle, style, geometry, card/shadow painting and
other pixel-era concerns.

Those QWidget runtime-pixel/presentation responsibilities are **CURRENT-LEGACY — WILL BE OBSOLETE in
E1/F/H/I as their callers are rehomed/deleted**. Presentation-neutral provider/model/settings behavior
survives where the destination contracts still require it.

Phase E decomposes ownership; Phase F ports family pixels.

## 3. Landed presentation-neutral family catalog

Phase E has already landed a cheap canonical family catalog in
`core/settings/widget_family_catalog.py`.

`widget_family_catalog.py` is the single, presentation-neutral family-membership authority mapping
stable `family_id` to member runtime widget ids (and family-level dependency metadata such as
`visualizers requires media`). `rendering/widget_descriptors.py` re-exports/consumes it for runtime use
but is **not** the membership source. Current accessors include:

```text
get_widget_family_descriptors()
get_widget_family_descriptor()
get_family_id_for_widget()
get_active_member_widget_ids()
```

Family availability derives from active runtime descriptors/environment gates rather than maintaining
a competing gate list.

The Spotify visualizer **participates in application-level capability activation** through the neutral
family catalog (family `visualizers`, which **requires** the `media` family). Its runtime/render
ownership remains the special Phase-D visualizer subsystem — capability activation does **not** make it
an ordinary Phase-F widget-presentation family and does **not** move it under `WidgetRuntimeManager`.

The current family catalog includes legacy/dev-gated Imgur only while the old runtime surface still
exists. That does **not** authorize a Quick Imgur port; Phase F removes Imgur instead of migrating it.

## 4. Activation is not ordinary enabled state

Phase E also landed application-level family activation:

```text
widgets.family_activation.<family_id>
```

Use terms precisely:

```text
family activated/deactivated
    = may the family capability/runtime ownership resolve at all?

instance enabled/disabled
    = ordinary configuration inside an activated family
```

Do not write “disabled family owns no provider/model/etc.” when the intended state is application-level
**deactivated**. An ordinary `enabled=False` instance is not automatically equivalent to tearing down
an entire capability family.

At the currently landed runtime seam, `_create_factory_widgets` filters a deactivated family before
concrete runtime widget/model/provider creation and before per-instance enabled handling. This proves a
real runtime consequence while all default activation remains inert/all-on.

The broader **E1 `WidgetRuntimeManager` provider/model/resource ownership split is ACTIVE now**. Do not
overstate full family dormancy beyond the owners actually migrated, but do not send E1 work back into
E2 UI either.

Durable destination:

- a deactivated family owns no family-exclusive model/provider/process/poll/timer/Quick component or
  family-specific render resource;
- shared infrastructure remains alive while another activated capability still requires it;
- deactivation preserves detailed saved configuration;
- a fresh process does not import/construct family-heavy implementation solely because the capability
  is catalogued.

See `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`.

## 5. Presentation-neutral widget metadata

Canonical runtime/widget metadata must not depend on constructing a QWidget factory product.

Presentation-neutral descriptors should own stable facts such as:

```text
widget_id
settings key / settings section
family_id
startup stage
default position
monitor-routing keys
CUSTOM participation
base/inheritance keys
service requirements
runtime action/refresh contracts
```

Old factory creation metadata may remain in the old path until its callers are removed. It is
**CURRENT-LEGACY — WILL BE OBSOLETE** as presentation authority.

Quick presentation maps family/runtime identity to retained Quick components through a static registry.
Do not build dynamic third-party plugin discovery, manifests, hot loading or API-version machinery.

## 6. Destination manager split

### 6.1 `WidgetRuntimeManager`

The Phase-E destination owner is presentation-neutral and owns:

- family activation admission;
- model/provider/runtime-data lifetime as those seams migrate;
- per-instance enabled/visible intent;
- monitor participation;
- settings updates;
- stacking inputs;
- action routing;
- runtime generation;
- presentation-model registration.

It does **not** own QWidget instances or runtime pixels.

E1 slice 1 is independently **GREEN** at
`8fcbc57a41c0b402fd4253d9668a0c6548b3100f`: the neutral owner shell was extracted while the
legacy `WidgetManager` shrank.

E1 slice 2 is independently **GREEN** at
`c320887cc27e1b2bace10ba562a36e24ae9307ca`: Reddit/Reddit2 post-provider lifetime now routes through
the neutral runtime-service registry/owner. Production Reddit widgets suppress their standalone default
provider until neutral injection; required service build/injection failure fails closed; standalone
construction retains its compatibility default.

E1 slice 3 is self-audited **GREEN** at `25f6ca4e7cdcaf82409a184c1d2999c01a7283e4`:
Weather provider/network/cache/refresh/retry/request-generation ownership now lives in one neutral
`WeatherRuntimeService` per card/display.

E1 slice 4 is self-audited **GREEN**, with its repeated-setup/reuse seam separately reviewed GREEN, at
`86872ab92a6b0960f2a3746d43dc6056cb013d47`: Steam Abandonment cache/source/rotation/prepared-state
ownership now lives in one neutral `AbandonmentRuntimeService` per card/display while the existing
process-scoped Steam cache/backend/credential/asset authorities remain unchanged.

E1 slice 5 is self-audited **GREEN** at `51948dc3956bc10549eb3e8440b2c3e25857f952`:
Achievement Pulse cache/source/manual-refresh/model/artwork ownership now lives in one neutral
`AchievementPulseRuntimeService` per card/display. It adds no recurring timer and continues to use the
same process-scoped Steam authorities.

Treat the current host edge as transitional:

```text
legacy per-display WidgetManager
        -> WidgetRuntimeManager
```

The destination decomposition still has one widget-runtime owner per display runtime, but that owner
ultimately belongs to the display-runtime boundary rather than a QWidget presentation god-object.

#### Current activation application model

Current production widget-family activation is applied through Settings-owned runtime recreation:

```text
runtime active
-> request Settings
-> complete runtime/display teardown
-> destruction barrier
-> Settings dialog
-> save capability state
-> next runtime generation applies creation admission
```

That lifecycle already retires the old runtime before family activation can be changed through the
normal user path. E1 therefore does **not** require a speculative second generic hot-retirement/hot-
recreation path.

If exact source later gains a true family-activation writer while runtime remains alive, that writer
must satisfy the same ownership contract. The existing E2.7 live Visualizer capability/failover bridge
is special lifecycle machinery for the global Visualizer singleton and must not be generalized into
ordinary family hot-reload.

`is_family_effective()` means **family activated + required families satisfied**. It is the canonical
capability/dependency query; it is not generic shared-provider last-consumer accounting.

The current `handle_capability_change()` lazy bridge into the E2.7 Visualizer failover retirement
remains transitional. Do not turn it into a central family-specific presenter/runtime switchboard.

Repeated production setup must preserve and revalidate the exact live presenter/service edge. Never
replace the service beneath an already-active presenter with a stopped owner. Retire stale registry
entries; fail a stale/mismatched active edge closed; allow an inactive presenter to rebuild only through
the ordinary activation boundary.

#### Landed ordinary-family owner seam: Weather

Reviewer inspection after Reddit selected Weather as the next bounded E1 migration:

- Clock's shared ticker is already presentation-neutral;
- Gmail's backend is already a neutral singleton and its residual orchestration is a larger later seam;
- Steam Progress and Friend Pulse constructors are provider/task/timer-inert; source inspection found
  real residual QWidget ownership in Achievement Pulse and Abandonment Issues;
- Media has a real QWidget-owned controller but is deliberately deferred to a high-risk dedicated
  checkpoint because of Spotify/Visualizer/transport/shared-state coupling;
- Imgur is removed in F0 rather than migrated;
- before slice 3, Weather coupled provider construction, cache/startup flow, refresh/retry cadence and
  async request-generation ownership directly to `WeatherWidget`.

Slice 3 leaves one coherent presentation-neutral `WeatherRuntimeService`, rather than merely moving the
`OpenMeteoProvider(...)` line.

Destination shape:

```text
WidgetRuntimeManager
    -> Weather runtime service/model
           -> provider/network/cache/refresh/request-generation ownership
           -> prepared current Weather state/events
    -> WeatherWidget (temporary legacy pixel consumer)
```

`WeatherWidget` retains old pixel/layout/icon/fade interaction until Phase F, while production Weather
provider/network/timer ownership no longer exists merely because the QWidget exists.

`widgets.weather_components.WeatherFetcher` is not a production-owner candidate by default: current
production uses the `WeatherWidget` ThreadManager fetch path, and repository search found no separate
production construction caller for `WeatherFetcher`. Do not promote a compatibility/test helper into
destination authority without evidence.

For a genuinely shared future service, preserve/reuse its actual legal owner and lifetime. Add explicit
consumer/lease accounting only when inspection of that concrete seam proves it is necessary. Weather
itself does not justify generic shared-consumer machinery.

#### Landed ordinary-family owner seam: Steam Abandonment

Slice 4 preserves separate Steam-card semantics instead of inventing a generic shared-Steam owner:

```text
WidgetRuntimeManager
    -> AbandonmentRuntimeService (one per Abandonment card/display)
           -> existing core.steam caches/backend/credential/asset helpers
           -> cache-first/source-refresh/cache-only-rotation ownership
           -> recurring cadence, request generations and prepared model/QImage state
    -> AbandonmentIssuesWidget (temporary legacy pixel/transition consumer)
```

The widget retains authored geometry, QPainter pixels, fade/content-transition timing,
transition-only deferral and input routing. Production suppresses the standalone convenience owner,
injects the required registry service before activation and fails closed on build/injection/reuse
failure. Every detached task/callback is runtime-generation tagged; retirement fences late work and
stops the sole recurring rotation timer.

#### Landed ordinary-family owner seam: Steam Achievement Pulse

Slice 5 keeps Achievement separate from Abandonment and from the process-scoped Steam authorities:

```text
WidgetRuntimeManager
    -> AchievementPulseRuntimeService (one per Achievement card/display)
           -> existing core.steam caches/backend/credential/asset helpers
           -> cache-first/source/manual-refresh and request-generation ownership
           -> semantic card model + source-resolution decoded artwork/icon identities
    -> SteamCardWidget (temporary legacy pixel/transition consumer)
           -> DPR-specific scaling/cropping caches, QPainter/layout/fade/input/style
```

The service uses the shared `ThreadManager` and introduces no recurring cadence. Rebinding the current
or future presenter replays accepted model/images without another source/cache/image fetch. Progress and
Friend Pulse remain provider/task/timer-inert and unregistered.

The bounded Abandonment artwork projection and Weather compatibility-proxy corrections are GREEN at
`9ab4f47e`. The dedicated Media owner slice now begins with exact controller/poll/shared-state
cardinality and Visualizer/E2.7 dependency review. Then continue real ownership migrations, prove
closure dormancy and hoist the per-display owner only when its final display-runtime boundary is safe.

### 6.2 Per-display Quick widget presentation host

Owned by each `QuickSceneController`.

It creates/destroys retained Quick components for models assigned to that display and owns:

- `QQuickItem` instance;
- current resolved geometry;
- z order;
- root opacity/fade;
- edit-overlay participation;
- presentation-only resources.

The display scene must not become a per-widget `if/elif` dispatcher.

### 6.3 Static family extensibility boundary

`WidgetRuntimeManager` operates generically through descriptor/family/model contracts.

Family-specific behavior stays in isolated family implementation modules selected by stable static
registry metadata. A new optional built-in family should not require rewriting central scene/runtime
owners.

This is internal modularity, not an external plugin SDK.

### 6.4 Owner scope, service cardinality and threads

`WidgetRuntimeManager` being one-per-display does **not** mean every provider/backend must also become
one-per-display.

Choose the narrowest correct lifetime/cardinality for the actual behavior:

```text
process/shared backend
family/shared runtime owner
per-display runtime state
per-instance runtime owner
presentation-only Quick item
render-thread-only resource
```

Do not manufacture a `FooRuntimeService` simply because a family exists. A family whose useful runtime
logic is already presentation-neutral may need only a presentation model/projection; a pure retained
visual may need no new service object at all.

A runtime service is also **not a thread**. Prefer the existing `ThreadManager` / legal shared execution
owners for detached I/O or computation. E1 must move timers/providers/workers, not multiply them.

For every owner migration, compare the expensive-owner cardinality before and after:

```text
provider/controller instances
timers/poll loops
threads/workers
subscriptions
processes
```

Unexpected increases require a concrete reason and regression coverage.

See `08_Widget_Runtime_Ownership_Threading.md` for the complete lifetime, threading, stale-result,
standalone-compatibility and shared-owner contract.

## 7. Widget model contract

Each family exposes only the state required for its visual and actions.

The destination boundary is not merely “some Python object exposed to QML.” Use a stable,
presentation-oriented model shape appropriate to the data:

```text
scalar/card state
    -> stable explicit presentation properties

repeating rows/cards
    -> stable row identity + bounded list-model semantics

dynamic image/artwork
    -> detached image identity/payload through one proven Quick image-delivery seam

user interaction
    -> semantic action back to the Python runtime owner
```

Do not expose `SettingsManager`, providers/backends, QWidget objects, or arbitrary mutable business
objects directly to QML.

Presentation updates are event/state driven. Static retained widgets do not earn a Python callback or
QML timer every physical frame. Repeated state identical to the current presentation state should be a
no-op.

See `09_Widget_Quick_Presentation_Bridge.md` for the full Phase-E3/F state/list/image/action/update
decomposition and per-family port checklist.

### Clock family

Presentation state may include:

```text
formatted time/date strings
analog hand angles if applicable
timezone label
display mode
style/config
```

Keep shared ticker/timezone computation in Python.

### Weather

Presentation state may include:

```text
location label
condition
temperature
forecast rows
icon/condition identity
style/config
```

Keep weather retrieval/cache/provider ownership in Python.

### Media

Presentation state may include:

```text
title / artist / album
artwork
playback state
progress
volume / mute
control availability
provider identity
style/config
```

Keep GSMTC/provider/control command logic in Python.

### Reddit / Gmail / Steam

Expose normalized rows/cards/actions and compact state. Keep retrieval/filter/cache/ranking/service logic
out of QML/render callbacks.

The old Steam implementation plan contains useful provider/security/product decisions, but its
QWidget/painter/factory presentation mapping is migration-epoch source only and must be rehomed rather
than copied into Quick.

## 8. Shared retained Quick visual primitives — Phase E3

Build small components rather than a base-god-object.

Candidate reusable primitives:

```text
OverlayRoot.qml
OverlayCard.qml
CardShadow.qml
ShadowedText.qml
HeaderRow.qml
Artwork.qml
Separator.qml
ProgressBar.qml
IconButton.qml
```

Use actual names from landed source; the list above describes the intended decomposition, not a required
filename manifest.

Components bind to explicit presentation model/style properties.

E3 remains unfinished until exact source/Current Plan marks it landed. It follows E1.

## 9. Full style state

Keep a presentation-neutral common style structure capable of representing current authored controls,
including as applicable:

```text
font family
font size
text color/alpha
show background
background color/alpha
border width
border color/alpha
corner radius
margin/padding
card shadow enable/color/opacity/blur/offset/spread
text shadow enable/color/opacity/blur/offset
header shadow if distinct
overall widget opacity/fade
global shadow direction
```

Family-specific style remains family-specific.

Do not collapse existing authored controls merely because one Quick property is more convenient,
**except controls explicitly retired by `Current_Plan.md`/`Spec.md`**. The pre-Quick visualizer
per-mode growth/card-height controls are the current named exception.

## 10. Global eight-direction shadow authority — Phase E4

The abandoned 4.6.9 direction feature is restored through one canonical direction token:

```text
NW  N  NE
 W     E
SW  S  SE
```

Default: `SE`.

Preferred state shape:

```text
ShadowDirection.NW / N / NE / W / E / SW / S / SE
```

Direction controls orientation only. Each shadow class keeps its own authored magnitude/blur/spread/
opacity/color.

Conceptually:

```text
resolved_x = direction.x_sign * authored_x_magnitude
resolved_y = direction.y_sign * authored_y_magnitude
```

Axis-only directions zero the perpendicular component.

Do not retain the old ineffective `widgets.shadows.offset` as a second user-facing magnitude authority.

All shared shadow primitives must be signed-offset safe and reserve visual padding on the affected
side(s), not right/bottom only.

### 10.1 Settings UI

After runtime support exists, add the intended inset 3x3 selector to the existing General/Appearance
bucket:

- eight selectable outer cells;
- selected direction visually inset/pressed;
- center inert;
- default `SE`;
- canonical settings save/preview path;
- no new Settings backend architecture.

A direction-only change must not alter widget geometry, font sizing, content layout, blur/spread,
opacity or per-shadow magnitude.

E4 is future Phase-E work until exact source says it has landed.

## 11. Shadow history and Quick rule

Relevant historical bug evidence includes:

```text
Docs/Historical_Bugs/U-06_MC_Shadow_Cache_Corruption.md
Docs/Historical_Bugs/R-24_Retired_Overlay_Effect_Cache_Busting.md
```

Those failures involved QWidget `QGraphicsEffect`/cache/focus behavior. Qt Quick does not use that
architecture, but migration must still avoid expensive/general effect churn.

The old QWidget painted-frame/cache/effect implementation is **CURRENT-LEGACY — WILL BE OBSOLETE in
E3/E4/F/I** after parity/caller proof. Do not port the cache-busting architecture itself.

### Card shadows

Prefer a dedicated retained mathematical/shader representation for rounded rectangular cards when it
matches appearance and cost better than a general full-source blur.

Properties should cover radius, blur, spread, signed offset, color and opacity. Draw behind the card;
do not toggle effect topology during fades.

### Arbitrary-shape shadows

Use a general effect such as `MultiEffect` only when genuinely required by an arbitrary-shaped visual.
Keep source bounds tight, blur bounds explicit and hidden rendering dormant.

### Text/header shadows

Use the smallest representation that preserves current appearance: retained shadow text or a bounded
effect source where blur is actually required.

No QWidget-style global cache-busting mechanism should reappear.

## 12. Old-corruption regression gate

The Quick widget gallery/installed validation must repeatedly exercise the old stress class, including:

```text
two displays
MC/interaction mode where available
focus display A -> B -> A
context menu open/close
widget click
hide/show
Settings open/recreate
CUSTOM enter/cancel/save
monitor topology recreate
```

Inspect card/text/header shadows, opacity, clipping, stale textures, disappeared shadows and corrupted
blur.

A failure blocks the affected shared primitive/owner, not the selected Qt Quick presenter as a whole.

## 13. Opacity and fades

Distinguish:

- content/background alpha;
- border alpha;
- shadow alpha;
- whole-widget authored fade opacity.

Use retained/root opacity for the authored widget fade when appropriate.

Do not animate by repeatedly enabling/disabling shadow/effect topology.

## 14. Stacking

Keep canonical stacking policy/math outside QML when it is product-owned in Python.

Quick consumes resolved geometry/z order.

Do not make QML anchors a second stacking algorithm. CUSTOM position overrides authored stack placement
according to the existing contract.

## 15. Pixel shift

Keep pixel-shift scheduling/intent outside QML if it remains product-owned there.

Apply the resulting offset as a retained transform/property on the appropriate presentation root.

Do not rebuild widget content for a small positional shift.

## 16. Capability dormancy and lazy Settings — E2 LANDED / E1 ACTIVE

E2 Settings already lists capabilities using cheap catalog metadata without constructing family
pages/providers/runtime pixels.

Landed operator-facing behavior:

- `SETUP` is always present;
- only activated families expose their normal settings pill;
- deactivating a family while Settings is open removes that pill **immediately**;
- if the removed family page was selected, navigation returns to `SETUP` immediately;
- reactivating immediately restores its pill;
- detailed family pages remain lazy;
- an unbuilt/deactivated page never overwrites persisted values during Save.

This live navigation decision is UI behavior. **E1 now owns the broader runtime/provider dormancy
implementation** at the safe owner boundary; do not invent teardown directly from navigation-button
callbacks.

## 17. Family migration matrix — Phase F

### 17.1 Clock / Clock2 / Clock3

Preserve:

- digital/analog modes;
- seconds;
- timezone;
- day/date;
- calendar layout;
- analog numerals/face shadow;
- inherited secondary-clock styling;
- monitor-specific display-mode overrides.

This is the first ordinary-widget canary.

### 17.2 Weather

Preserve:

- condition icon/alignment/size;
- forecast/details;
- font/margin;
- card style/shadows.

Weather retrieval/cache remains Python-owned.

### 17.3 Media

Preserve:

- artwork/rounded artwork;
- metadata/header frame;
- controls;
- Spotify volume;
- mute;
- playback progress;
- progress shadow/glow;
- live provider updates;
- click/control actions.

### 17.4 Reddit / Reddit2

Preserve:

- header/logo;
- rows/items;
- separators;
- refresh indication;
- click/exit behavior;
- inherited second-instance style/settings.

A later post-migration QoL may add retained in-scene hover/title presentation; that is not required to
port the existing runtime pixel contract unless Current Plan explicitly admits it.

### 17.5 Gmail

Preserve current configured presentation switches, including sender/subject, envelope/three-dot/
refresh indicators, unread/header, timestamp/date mode, grouping, separators, desaturation,
background/border and current sound behavior. Sound/provider logic remains Python-owned.

### 17.6 Steam family

Preserve each supported card's artwork, selection state, accent, capsules, desaturation, metadata rows
and current dev-gate behavior.

Existing process-scoped Steam caches, backend locks and credential/asset helpers remain shared and must
follow their real consumer lifetime. Per-card orchestration such as landed Abandonment rotation/source
state stays per card/display; do not silently duplicate shared authorities or force distinct cards into
one generic Steam service.

### 17.7 Imgur — remove, do not port

Imgur is deprecated migration debris.

When Phase F reaches it:

- remove its descriptor/settings/runtime/provider/CUSTOM/build/test surface;
- do not create a Quick component;
- do not repair its provider merely to migrate it;
- do not build a QWidget-to-Quick compatibility presenter;
- let canonical settings cleanup/H0 strip or ignore obsolete persisted state according to the active
  plan.

A current dev-gated Imgur entry in legacy descriptors/catalogs is temporary migration source state,
**not** a supported Quick family target.

There is no later contradictory “port it if still canonical” branch in this document.

## 18. No screenshot-wrapper final implementation

A temporary development capture may be used for visual comparison.

Do not ship:

```text
old QWidget -> grab() -> texture -> Quick
```

as the final widget presentation architecture.

## 19. Tests

Per family use the relevant combination of:

- model/provider behavior;
- activation admission vs instance enabled state;
- settings-to-model mapping;
- lazy Settings hydration/save safety;
- style mapping;
- Quick component instantiation;
- geometry/DPR;
- CUSTOM;
- click/action routes;
- hide/show;
- lifecycle/recreation;
- visual capture/golden where robust;
- deactivated fresh-process dormancy after the responsible owner has migrated.

Shared primitives receive stronger regression coverage because every family depends on them.

Do not call a family migrated because legacy Python model tests still pass.

`Docs/TestSuite.md` is the canonical file-level keep/rehome/retirement ledger; update it when an old
QWidget/presenter test changes owner or becomes obsolete.

## 20. Checkpoint cadence

Follow `Current_Plan.md` rather than treating this list as parallel sequencing.

Landed checkpoints:

- presentation-neutral family/catalog work;
- **E2 capability Settings UI/lazy navigation**;
- **E2.7 Visualizer CUSTOM failover/reclaim**.

Current/future bounded checkpoints:

- **E1 manager/model/provider split**;
- E3 common retained style/shadow primitives;
- E4 global shadow direction;
- each Phase-F family port;
- shared visual-regression corrections.

Do not batch every family into one commit. High-risk owner/lifecycle boundaries should be independently
audited after push when Current Plan requires it.
