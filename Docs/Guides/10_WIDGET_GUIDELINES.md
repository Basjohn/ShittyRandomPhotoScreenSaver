# Ordinary Widget Authoring Guide

Canonical guide for adding or deeply refactoring a **non-Visualizer runtime widget** in the accepted Qt
Quick architecture. This guide is based on the landed retained Quick families: Clock, Weather, Media, Reddit/Reddit2,
Gmail, Achievement Pulse, Abandonment Issues, Friend Pulse and System Stats. It also incorporates the shared colour-only
Widget Theme semantics, smart-stacking, global-CUSTOM architecture, optional shared side-axis `content_extent` reflow and
family-retirement lifetime rules that later slices added across those families.

`Current_Plan.md` owns which family may be changed now.

## 1. Start with ownership, not pixels

Classify the concern first:

```text
application capability
ordinary instance enabled state
provider/backend/runtime state
presentation model/state
retained pixels
```

Family activation/deactivation is application-level. Ordinary `enabled=False` is the casual per-instance
off state inside an activated family. Do not collapse them.

Before adding `FooRuntimeService`, answer:

1. Does meaningful non-pixel lifetime/state need a new owner?
2. Is there already a correct neutral owner?
3. What is the real cardinality: process/shared, runtime-generation shared, per-display or per-instance?
4. What recurring work/provider/cache/action authority exists before and after?
5. What retires it and fences stale completion?

Do not add a service merely for naming symmetry.

### Edit child role and QML paint contract

When adding a semantic Edit child, declare the role independently of provider data and temporary QML visibility. The shared selected Edit mapper follows the actual target through ancestor geometry, nested QML transforms and clip; the role's readiness may toggle without removing its retained delegate. Use a stable descriptor with a selected-Edit-resolved target for Repeater content or two alternate visual positions of the SAME semantic role. Do not silently point a saved role at status/placeholder text. Preserve intentional transparent geometry carriers when they represent painted descendants. Keep real X/Y reflow, flipped semantic alignment, painted containment and authored layout in family QML, not in a family-specific Python observer or repair loop. The existing CUSTOM session alone owns Edit/Save/Undo/slots. A Qt retained scene test must compare actual painted QQuickItem identity and projected/clipped bounds through Save/reopen, not merely role-name existence; test temporary hide/reveal without losing semantic identity.

### Mandatory current Edit, role, and performance checklist

- [ ] **Choose a purposeful editable unit.** System Stats has only header, top separator and one entire painted metric-stack group; it does not expose thin metric-value/accent subhandles. Repeated feeds generally keep authored rows together, with optional **one semantic column order per widget** (as accepted in Reddit/Gmail), not free-position geometry for every row. An OSD exposes only meaningful singleton chrome; Games You Follow exposes stable `header`, `refresh`, `story_tiles` (one grouped role), and `overflow_summary`, never per-story free-placement.
- [ ] **Declare stable role identity.** `customEditableChildRoles` must not depend on live normalization/preferred dimensions, provider contents or temporary visibility: array reallocation retires a selected QML Repeater delegate and can break a gesture. Use existing retained family `normalizationTarget` and named live properties for *selected-only* reads; readiness and alternate painted-target resolution live inside that delegate. Never replace an unavailable saved role with unrelated status text. Do not add off-Edit observers.
- [ ] **Map the actual paint, not the model's guess.** Shared selected mapping projects all four corners through inherited QQuickItem geometry and clips against ancestor paint surfaces. For QML `Scale`/`Translate` applied to a target or ancestor, expose `customEditMappingDependency` from the **applied transform object's properties**, not just the upstream source input. Never enumerate non-bindable `QQuickItem.transform` in an active binding or add a per-pointer scene scan. Transparency of a semantic geometry carrier alone does not make its painted descendants unavailable.
- [ ] **Separate parent and child authority.** Outer handles alone change the parent/custom `content_extent`; child X/Y edits are independent deltas from live family authored rails, not inside-out parent minimums or new persisted layout roots. A child's painted ink must stay inside the actual declared card/accessory surface even when collision is OFF. Test flip and opposite-axis resize in the same unsaved Edit session, Undo/Cancel/Restore/slots/reopen and later display generations.
- [ ] **Retain guide chrome and avoid storms.** Selected child snap guides are one retained item per axis with no-op updates; never recreate one-guide Repeaters from fresh arrays on every pointer sample. The separate outer peer/centre guide path may use multiple lines; only rewrite it on measured evidence of genuine no-op delegate churn. No per-pointer Settings writes, QML warnings, binding loops, normal-runtime Edit probes, provider wakeups or repeated equal model/layout publications. Preserve live effective drag and precise snap rather than throttling away the problem.
- [ ] **Execute real Qt and cost gates.** Test exact painted QQuickItem identity/bounds (including applied transform and clip), retained delegate identity through repeated normalization and visibility changes, correct host teardown and no warning stream. A test fixture may not use unsupported `QQuickTranslate*` Python conversion, inspect a retired QQuickItem, compare clipped paint with unclipped bounds or require a deliberately retired child-driven parent-size object. Measure active Edit versus normal runtime cost separately; syntax/source checks alone do not prove performance neutrality.

Historical caution: [R-88](../Historical_Bugs/R-88_QtQuick_Custom_Edit_Paint_Role_Churn_And_False_Test_Oracles.md). Current execution/testing status belongs in `Current_Plan.md`, not in this guide.

### Semantic icons and audio-session ingress

- [ ] Prefer retained wireframe vector icons over emoji for new navigation/chrome: QPainter or the already proven retained vector owner, inheriting the parent control's existing semantic normal/hover/selected/disabled colours. Preserve the existing shadow and interaction owners, no icon-specific timer or polling, and no duplicate theme-state cache. Replace older emoji glyphs only in a bounded, test-backed related pass.
- [ ] When a family cannot paint a complete repeated section at a reduced Y extent, hide whole trailing sections using **only family-owned paint readiness**, without changing the configured data/monitoring subset, shrinking the user's saved CUSTOM block on each visibility edge or feeding visible row count back into preferred parent size. Keep the selected Edit target bounded to the same painted card and retain its identity across hide/reveal.
- [ ] Distinguish Windows endpoint (system master) volume from one selected application's Windows mixer session. Only the shared system owner may register endpoint callbacks for Media/OSD; a separately scoped Media application-session observer exists only with a live Media volume consumer and must retire on source/endpoint change and dormancy. Its callback is read-only, coalesced to one Qt GUI wake, and never attempts to synchronize an unrelated browser tab or remote playback device. Source-only evidence of no polling does not prove the listener has zero GUI admission cost: selected-session `GetAllSessions()` and COM registration currently run synchronously at the source edge on the owning GUI apartment. That source-edge cost is accepted for Media pending concrete stall evidence; do not claim a measured improvement or add instrumentation speculatively. Do not move live COM interfaces across apartments to hide the cost. Use application-owned event context to avoid slider feedback; never introduce a session-volume poll or per-display COM registration.

## 2. Destination chain

```text
canonical capability/settings
-> WidgetRuntimeManager or existing neutral owner
-> coherent accepted runtime state
-> stable presentation model / bounded list model
-> Retained<Family>Presentation wrapper
-> OrdinaryWidgetPresentationHost
-> family QML
-> OverlayWidget / OverlayCard / ShadowedText
-> display's one QQuickWindow
```

The presentation host creates/retires retained items and applies outer geometry, root fade and card style.
It is not a provider, SettingsManager, cache owner or business controller.

No extra accelerated widget window. No `QQuickWidget`.

### Current consumers of this guide

- **System audio OSD:** independent opt-in presentation of the existing shared GUI-apartment Core Audio source; no endpoint poll, per-display callback, alternative window or second source. See [current OSD reference](../Reference/System_Volume_OSD.md).
- **Games You Follow:** linked followed-set membership through the existing Steam credential owner, one generation-shared source/lease/deadline, retained news tiles and four stable grouped CUSTOM roles with independent X/Y and flip. The first complete scan is durable; post-coverage maintenance updates at most eight apps per admitted session. See [current product reference](../Reference/Steam_Games_You_Follow.md).

## 3. Proven ownership patterns

### Clock

```text
GlobalClockTicker
-> stable ClockPresentationModel per logical instance
-> retained ClockPresentation.qml
```

Ticker was already neutral. No Clock runtime service was invented.

### Weather

```text
WidgetRuntimeManager
-> WeatherRuntimeService
-> WeatherPresentationModel
-> retained WeatherPresentation.qml
```

Provider/network/cache/cadence/retry/request generation remain runtime-owned.

### Media

```text
runtime-generation shared Media owner
-> per-display MediaRuntimeService lease
-> one retained MediaPresentationModel/item

separate shared app-volume owner -> narrow lease
separate shared system-mute owner -> narrow lease
```

Dynamic artwork uses one process-engine image provider with stable runtime-owned identity and bounded
retention. Presentation does not become playback/controller truth.

### Reddit / Reddit2

Each configured member keeps independent feed/config/runtime identity through a per-member
`RedditRuntimeService` and stable retained model. Shared family rate-limit/policy infrastructure remains
shared; Reddit2 is not a second provider architecture.

### Gmail

The runtime-generation shared Gmail owner and process `GmailBackend.instance()` remain the backend/cache/
cadence/action/notification/sound authority. The retained port projects that owner; do not create another
backend abstraction.

### Steam cards

Use current neutral Steam models/runtime/cache/privacy/provenance seams. Friend Pulse is a retained public card;
do not resurrect the retired Steam Journey scaffold as a parallel widget; `steam_progress` is the implemented Games You Follow identity.

### System Stats

System Stats demonstrates the bounded sampled-value exception: one runtime-generation shared sampler exists only while a
real retained consumer lease exists. CPU/Memory/Uptime/Network selection may skip unused observations **inside that one
owner**; it does not create per-metric timers or services. Product sampling stays isolated from diagnostic `--usage`.

## 4. Import dormancy is architecture

Forbidden:

```text
import common Quick scene/host
-> import every family presentation module
-> import inactive family runtime/backend/provider tree
```

Rules:

- common `rendering.quick.widgets` infrastructure stays light;
- family implementation imports at actual family caller/activation boundary;
- static presentation-only family metadata may remain in a light registry;
- annotation-only runtime types use `TYPE_CHECKING` where appropriate;
- importing common Quick host constructs/bootstraps no provider/controller/runtime/backend singleton.

Fresh-process dormancy tests cover the destination Quick host, not only legacy QWidget imports.

## 5. Presentation model design

Prefer stable explicit Python models:

- immutable/bounded config record;
- immutable/bounded style record;
- coherent accepted runtime revision;
- explicit scalar properties;
- stable `QAbstractListModel` for rows;
- stable semantic row/item IDs;
- stable image identities;
- explicit action capability flags.

Do not expose to QML: `SettingsManager`, QWidget, business provider/backend objects, arbitrary mutable backend
dicts, raw CUSTOM persistence, or provider refresh timers.

Identical effective state should be a no-op where practical. Normal setting/style/state changes mutate the
existing retained item/model/list model instead of recreating item/model/runtime/engine/window.

## 6. Coherent state / stale fencing

Publish one coherent accepted revision. Avoid mixed state such as new metadata with old artwork or new
provider with old capability flags.

A worker completion is legal only if relevant identities still match, e.g. runtime generation, owner/service
generation, request generation, account/location/feed/provider identity, activation identity.

Stale work may physically finish; it becomes a fenced no-op. Model retirement makes later callbacks harmless.

### Last-good cache policy

When a family has a durable provider cache, do not treat its freshness window as a TTL. Cache-first presentation may use a
coherent successful record regardless of age; age decides whether refresh is due and whether the UI marks it cached/stale.
Failure/private/rate-limit/malformed responses never overwrite or delete the last-good record. Explicit
user/account/cache reset, schema rejection/corruption, or a proven identity change are the deletion boundaries. Never blank
useful stale data merely to look fresh, and never substitute a different semantic source (for example owned games for a
followed-games feature).

## 7. Lists

Reddit/Gmail/Steam-style rows use bounded stable semantic IDs and coherent update transactions. A simple
bounded reset is fine when correct; do not invent a universal diff engine without need.

Delegate index is presentation position, not semantic identity. Transient popup/menu UI is not row geometry
authority.

## 8. Actions

```text
QML semantic signal
-> Python presentation/action admission
-> neutral runtime/business owner
-> side effect
-> accepted current state
-> presentation update
```

QML does not directly persist settings, own auth, perform network I/O, decide cache policy, call backend
APIs as business authority, or mutate accepted playback/message/provider truth.

Purely visual press/flash/menu-open state may be QML-owned. Interaction admission is shared runtime input policy, not separately invented per family.

### Tooltips / transient explanatory UI

Tooltips are acceptable retained UI when they are event-driven. A hidden tooltip must not create polling, a worker or continuous animation. Qt/Quick hover delivery for the handful of visible delegates is cheap; an optional show-delay timer is allowed only while an actual hover candidate exists. Prefer constructing/showing the tooltip only when needed (for example, a Reddit title is actually elided).

A tooltip is presentation state only. It must not become geometry authority, provider cadence or a reason to keep inactive rows/families alive.

## 9. Dynamic images

Proven Media pattern:

```text
runtime owns decoded QImage + stable key
-> process-engine MediaArtworkImageProvider
-> image:// stable identity
-> retained Image
```

No QPixmap worker transport, base64 churn, tempfile per update, unchanged-image reupload, or unearned
per-widget provider duplication. Static packaged icons can use stable packaged file identities.

Changing artwork surfaces use the shared retained `ArtworkFadeImage` unless a deliberately superior common primitive is
approved. The old displayed texture remains visible until the incoming image is ready; the incoming buffer then fades over
it for 520 ms with `InOutSine`, after which the old texture is released. An explicit empty source fades out over 280 ms.
This is event-driven animation/frame demand only, with the inactive source cleared at idle. Family QML may own mask,
clipping, aspect and directional shadow geometry, but not a second artwork-swap timer/cadence. Media metadata crossfade is
likewise presentation-only: source truth changes immediately and the text layer must preserve deterministic alignment and
layout ownership while animating.

Asset lane is deliberate:

- Settings GUI micro-assets/fonts in `ui/resources/assets.qrc` are embedded and addressed through `:/ui/assets/...`;
- runtime/branded widget imagery remains raw `images/` data and is resolved as packaged filesystem/file URLs;
- adding a runtime logo to QRC does not remove the requirement to package raw `images/` when the runtime loader expects it.

Do not silently move a family between lanes. When `assets.qrc` changes, regenerate `assets_rc.py`; when a raw branded asset changes, keep the Nuitka/installer raw-image packaging contract intact.

## 10. Geometry / dynamic height / ordinary stacking

Outer geometry is Python/session-owned. QML lays out inside assigned rect. A family presentation must report a stable preferred/natural outer size when content materially changes; it must not become its own placement solver.

Materially different shapes may have stable variants:

```text
(widget_id, display_identity, geometry_variant)
```

Clock digital/analogue is the first proven case. Never repeatedly derive one saved variant from the other and accumulate drift.
The active face is separate persisted state: the shared `display_mode` baseline plus per-display
`display_mode_overrides` select which independently stored geometry variant is live. A layout slot that restores Clock
geometry must restore that face-selection state in the same transaction; never smuggle behavior back into the geometry
payload merely to make replay convenient.

Content-driven natural height may derive from accepted state. Keep it separate from transient overlays. Opening Gmail's three-dot menu must not rewrite Gmail's committed CUSTOM height.

### Whole-card CUSTOM resize (default)

New ordinary widgets use one shared transform. Author a truthful **outer** baseline
per axis; check whether model dimensions already include shell inset before adding
padding. Do not introduce a local content scale or resize-driven Settings updates.

```qml
OverlayWidget {
    required property var cardModel
    uniformScaleTransform: true
    preferredContentWidth: cardModel.authoredOuterWidth
    preferredContentHeight: cardModel.authoredOuterHeight
    // Authored children use this baseline coordinate space.
}
```

Set the runtime descriptor's `custom_layout_resize_mode="ordinary_uniform"` and
`supports_layout_resize_edit=True`. That mode already belongs to the shared
`UNIFORM_TRANSFORM_RESIZE_MODES`; no new capture/scale branch, payload handler,
minimum-value entry or product Settings key is needed. Geometry carries the scale;
centred letterboxing, transformed shadow/glow bounds and the shared absolute 40%
floor follow the same retained root. Use `scaleAwareStrokeWidthForScale(width,
presentationScale)` for thin strokes. Prove stale payload replay, Save/Cancel and
reconstruction keep the authored baseline stable, then visually inspect the
[permanent capture matrix](Ordinary_Widget_Resize_Capture.md) and live hit targets.

Clock's variant-aware `clock_font` and Visualizer's `visualizer_rect` are explicit
exceptions. The descriptor regression bar rejects new per-value families without
a deliberate contract change. Genuine family font/artwork Settings remain active;
CUSTOM geometry is not their authority.

### Optional side-axis content reflow

Uniform whole-card resizing remains the default. Opt into `content_extent_axes` only when horizontal/vertical
playroom has a clear presentation benefit. All current resizable ordinary non-Clock families now use the shared path:
Weather, Media, Reddit/Reddit2, Gmail, Achievement Pulse, Abandonment Issues, Friend Pulse and System Stats. Reuse
the shared session/owner/payload path; do not create a family-local resize mode or Settings-backed width/height. Clock
remains the explicit variant-aware sizing exception; Visualizer owns its separate viewport contract.

Contract:

- side handle -> one logical content axis at the current uniform scale;
- selected-parent lighter-blue diagonal corner -> both admitted logical content axes together;
- existing square corner/wheel -> whole retained presentation scales uniformly;
- family model/QML reflows only presentation (columns, rows, spacing, metadata, artwork, etc.);
- family may provide bounded **logical side-drag floors** through the shared policy, but those floors do not replace the
  generic uniform whole-card floor; dense authored cards may request the shared owner to resolve that logical floor
  against the live authored reference at edit admission so persistence, handles and QML never disagree about a smaller
  content box;
- `content_extent` is CUSTOM state, not a product preference/default;
- Save/slot persistence use the shared CUSTOM payload; Cancel restores the prior committed extent;
- Restore Size clears the extent and returns to canonical authored size while preserving X/Y/display and remaining in
  CUSTOM;
- side-resize updates may not redefine authored geometry, invoke stacking/auto-fit, or schedule timers/debounce/polling;
- richer content revealed by a larger extent must remain presentation-driven and reuse existing provider/runtime cadence.
  Weather's five-day expansion is the current example: the existing Weather request carries today + five future daily rows,
  while QML reveals the extra band only when the CUSTOM vertical extent actually has enough room.

A new family should not copy Media/Friend Pulse arithmetic as infrastructure. It should declare axes/minima and consume
the common logical extent; family-local code owns only its own internal reflow. This keeps normalization extensible without
creating a second geometry architecture.

### Child editing, live rails, and parent containment

Child editing is an adjustment **inside** an already sized parent, not an
inside-out parent resize. Only the outer side/corner/wheel handles change the
parent's CUSTOM rectangle or logical content extent. Do not derive its minimum,
preferred size, or persisted `content_extent` from live child occupancy; do not
publish a child-required size or queue a correction on child paint/role changes.
Authoring mode still supplies the baseline and Restore Size reference.

Every admitted child move and resize must contain the **actual occupied paint**
inside its declared surface, regardless of the peer-collision toggle. The usual
surface is the card's real content boundary, not an invented padding margin;
Media's independent volume accessory has its own legal surface inside the outer
widget. Collision OFF means peers may overlap; it never permits an escape from
the containing surface. A legal drag stops at the boundary and does not change
parent geometry. Handle clamping and magnetic guides must agree, including when
the child starts in an old, invalid saved position. Reconcile existing malformed
records without silent outer growth or repetitive geometry publication.

**Flow on each untouched axis.** Saved `child_geometry` placement values are
independent local deltas from *live family-authored* X/Y rails, not absolute
coordinates in the once-authored canvas. Editing X alone must not detach Y from
its Column/row, and editing Y alone must not detach X/semantic alignment.
Resizing content must not freeze its siblings' authored layout. An explicit
free-position edit can change a relationship on the *edited axis only*; the
opposite axis remains family-authored. Never infer full two-axis detachment from
`x_offset != 0 || y_offset != 0`, subtract later ancestor motion to cancel a
Column's Y reflow, or let a child dimension set the enclosing Column's height.
The family remains responsible for actual internal layout, while the shared
Edit owner is responsible for admission, containment, Save/Cancel and geometry.

Flipped presentation exchanges semantic placement, not glyph or bitmap pixels.
Use the corresponding left/right transform origin when text scales under compact
Y. Validate the exact interaction sequences: flip before a Y-only resize; Reset
Size -> Flip -> Save -> re-enter Edit -> Y-only resize; X-only child edit ->
parent Y resize, and the reciprocal. Measure **mapped painted rectangles** and
selected Edit proxies, including right-edge alignment, seek/transport and
visible controls at the minimum admitted height. An unchanged `visible: true`
flag or a test of pristine `child_geometry` is not proof of those outcomes.
Never manufacture tests that bypass production QML, normalize away a bad saved
record, or force an external provider state to mask a geometry defect.

Changes to any shared gesture/containment/normalization policy require relevant
non-child/parent pointer no-churn and Save/Cancel/Undo/reopen guards as well as
family-specific scene tests. Do not add pollers, frame callbacks, off-Edit role
scans, extra geometry/persistence owners or per-pointer Settings writes.

**Repeated-list column order is semantic, not child free placement.** If a
feed wants drag-swappable columns, declare one list-wide semantic role per
column, present an Edit-only vertical rail/grip, and commit one stable ordered
permutation for the widget. Do not persist geometry per row, allocate one
handle per delegate, make age/AGO reorder depend on independent accidental
child offsets, or detach repeated text from compact-height/flip reflow. The
shared CUSTOM session and owner must own Undo/Save/Cancel/Reset/slot replay;
ordinary QML projects the order across every retained delegate without
provider refresh or Repeater recreation. Reddit's `01HR` and `AGO` are separate
semantic columns for this feature even though the current presentation groups
them in one age cell. Gmail sender/subject/timestamp likewise keep one
widget-wide order. Reddit/Gmail semantic column-rail editing is implemented; changes to it require
a retained Qt acceptance gate, not a source-only role assertion.

### Non-CUSTOM authored stacking

Ordinary placement is owned by the display presentation/orchestration layer, not by family QML. When global CUSTOM is inactive, the smart stacker may project a family away from its authored slot to avoid collisions. A new widget therefore needs:

- a correct base authored rectangle / preferred outer size;
- deterministic size-change notification at real event boundaries;
- no private overlap avoidance, screen-slot search or periodic geometry timer.

Do not persist the stacker's projected collision-avoidance position as new authored user geometry. The authored slot remains the base policy.

This shared path is the **preferred implementation for every new ordinary card**.
The `ordinary_uniform` descriptor plus `uniformScaleTransform: true` opts the card
into both CUSTOM whole-card sizing and non-CUSTOM auto-fit; do not add a second
family-specific scaling implementation. Declare the adapter/binding's authored
preferred outer size accurately and emit size changes only when that size changes.
Provider text/artwork refreshes with unchanged dimensions must not request layout.

The display presenter first stacks at full size. Only unresolved placement admits
bounded shrink/re-stack trials, using the shared 40% whole-card limit and preserving
10px outer-rectangle clearance. It grows cards back toward authored size when space
allows. Clock and the fixed Media/Visualizer relationship remain explicit exceptions.
A new card must not add itself to those exceptions for convenience. Global CUSTOM
turns this machinery off; Edit captures visible geometry, while Save/Cancel use the
existing shared absolute-scale/session contract without rewriting product Settings.

Keep geometry computation event-owned: no resize timer, debounce, poller or per-frame
layout callback. The presenter reuses its last identical solve and skips identical
geometry writes; do not add per-family caches or schedulers. Changed crowded layouts
still incur synchronous solve work, so measure those event tails as well as startup.

Use `tests/test_widget_auto_shrink.py` for packing contracts and the real presenter /
Edit test in `tests/test_qtquick_resize_normalization.py` as the integration pattern.
Extend the retained capture harness with the new family's fixed snapshots; inspect
normal, reduced, crowded and restored appearances plus actual hit/shadow/glow bounds.
The harness's bounded settle/deadline timers are offline tooling only, not a runtime
implementation template.


### Global CUSTOM hard boundary

CUSTOM is a **global layout mode**, not a per-widget exception list. Authored stacking and Media↔Visualizer adjacency are completely dormant when any of these is true:

1. persisted/effective CUSTOM exists;
2. live Edit Layout begins;
3. a number-key saved-layout load begins its fenced rebuild.

A new ordinary widget must not register itself as a stacking obstacle/participant while that subsystem is dormant. Family code must not try to compensate locally.

## 11. Shared edit-mode X

Every adjustable card gets X in edit mode. This is shared CUSTOM/session behavior, not a family business
command:

- duplicate -> remove duplicate from working layout;
- singleton -> ordinary widget OFF, same meaning as its normal Settings checkbox;
- never map X to family/capability deactivation;
- do not persist or destroy committed provider/runtime state on click.

Context-menu Save or Enter commits. Cancel restores geometry, duplicate set and ordinary enabled state.
Family QML does not persist this itself.

## 12. Card / text / header style / Widget Theme semantics

Ordinary card:

```text
OverlayCard
-> shared ordinary shadow projection
-> ordinary semantic RGBA surface/border
```

Ordinary text:

```text
shadow glyph at signed offset
+ visible glyph
```

No ordinary text blur or private MultiEffect/layer capture for parity. Canonical direction resolves in Python. Current ordinary base distances live in the retained widget host. Card/frame **Extra Offset grows only the selected far edge(s)** while preserving opposite-edge coverage; Text Extra Offset remains glyph displacement.

### Widget Theme ownership

New widgets consume the one shared semantic resolver. Do **not** create a family-local theme cascade. Effective visual intent follows the current precedence model:

```text
intentional family/widget override
-> exact Widget Theme semantic role
-> shared semantic parent role
-> local/current semantic context (`local.*`, never serialized)
-> preserved current fallback pixel
```

`Widgets -> General -> Style Overrides` owns the shared **Card Surface**, **Card Border**, **Header Fill**, **Reset All Colours to Theme** and **Card Border Width** once for ordinary widget families. Surface/Border/Header Fill edits fork a named Widget Theme into persisted `Custom`; the reset is explicit profile cleanup back to theme authority; Border Width is global styling rather than Widget Theme schema. Do not add duplicate card/header palette controls to each family.

Existing/high-value **specialized** family swatches remain valid only when they represent a durable family contract (for example Media Seek/Volume), and then act as explicit family overrides. Canonical/default-valued persisted family fields are effectively Inherit where the current semantic adapter defines that behavior. Branded header colours are not a valid reason to add a family swatch: use shared `header.*` semantics instead. Editing a surviving family override must not create Widget Theme `Custom`; editing a Widget-Theme-owned shared value may.

Semantic roles should represent product meaning, not every literal. Editor chrome, diagnostics, legibility scrims, retained rendering primitives and context-only `local.*` values remain local unless a real cross-theme requirement proves otherwise. Never serialize `local.*`.

Legibility-sensitive text may legitimately remain close to neutral across related named themes while still being semantic. Clock is the current example: when its family colour is canonical it consumes shared `card.text`. Dark themes commonly keep that role near-neutral/near-white, while light themes deliberately switch it to dark typography over a stronger light card floor. Do not infer "unthemed" solely from a subtle colour delta, and do not repurpose `widget.accent` for primary time/numeral text just to create visual movement. Specialized product accents should inherit explicitly rather than bypassing the graph; Abandonment Issues uses `abandonment_issues.accent -> widget.accent`, while its existing authored family accent remains the higher-precedence override.

Theme-link UI is not a widget-family responsibility. Settings Themes and Widget Themes share one persisted bidirectional link state resolved by stable IDs. A new widget must never introduce its own theme-link toggle or attempt name-based theme pairing.

### Header reuse

Use the shared branded-header/component vocabulary when the family fits it. Header geometry/logo identity remains family-authored content, while semantic colours/opacity/shadows come from shared style/theme authority. Do not copy Media/Steam-specific layout merely to reuse the header.

### Plain card surface contract

Runtime widget cards use the ordinary retained Qt Quick RGBA surface/border/shadow path only. Widget Themes provide semantic colours; explicit family overrides remain higher precedence. The abandoned runtime Glass/Acrylic backdrop experiments must not leave a `ShaderEffectSource`, `MultiEffect`, layer-backed background, material mask tree, capture FBO, material Loader, cadence callback, worker, timer or poller in the screensaver scene. The wallpaper/transition render node remains directly composited by the healthy pre-material path.

Settings-window Glass/Acrylic is a separate native QWidget/HWND theme facility and does not authorize a corresponding runtime-card material path. If runtime materials are reconsidered in future, they require a broader independently justified renderer architecture and a fresh acceptance plan rather than reviving the rejected card-only experiments.

A family owns a visual exception only if it independently authored that relationship. Retired `shadowtuning.json` card/text/header/icon/control/volume values are not family-authored because a widget once consumed them.

## 13. Fade / animation

Whole ordinary-widget fade:

```text
OverlayWidget.fadeOpacity -> root Item.opacity -> whole subtree
```

Do not port `ShadowFadeProfile`, `QGraphicsOpacityEffect` choreography, dummy/effect carriers or separate
shadow fade timelines.

A retained intermediate `Item` needs a real layout/transform/clip/z/input/lifecycle purpose.
Presentation-only animation may be retained Quick animation but must not become provider cadence or logical
simulation authority.

## 14. Family fidelity rule

Architecture/refactor work preserves working family-specific product behavior unless a deliberate product change is requested.
Preserve content hierarchy, meaningful layout relationships, interaction/menu/action semantics, family-specific
geometry, authored animation and independently-authored visual relationships.

Do not preserve obsolete QPainter caches, QWidget hit rectangles, QGraphics effects or retired global tuning
merely for mechanical parity. A retained replacement is not an excuse for unrelated UI redesign.

## 15. Lifecycle / retirement

```text
construct inert model/wrapper
-> inject real neutral service/lease
-> activate after admission
-> consume current accepted state
-> retire presentation
-> detach/stop lease according to real cardinality
-> fence stale completion
```

Lazy Settings-family retirement is part of the same contract. Invalidate queued/coalesced UI work admitted under the
old body generation, clear retained labels/combos/anchors/control references before `deleteLater()`, and make generic
follow-up refresh code validate the C++ QObject before dereference. Never keep a hidden section alive or add a timer/retry
loop to mask a stale-wrapper bug.

Presentation destruction does not automatically mean backend destruction. Shared owners retire only when
real consumer set is empty.

After family GREEN under current audit policy + caller proof, delete old QWidget/QPainter pixels and
presentation-only tests. Do not keep an old selectable/fallback presenter for safety.

## 16. Performance / resource rules

Static retained widgets must not create Python callbacks per physical frame, run provider refresh through QML `Timer`, rebuild stable trees for unchanged state, keep hidden continuous animation alive, multiply provider/controller/timer/thread/subscription cardinality, keep custom-GL frame demand active merely by existing, or load inactive family backends through common imports.

Shared features remain plugin-like: an inactive family should not import/construct its heavy provider tree; global CUSTOM should be able to make authored stacking dormant. New cross-family infrastructure should have a similarly explicit inactive state instead of a permanent polling owner.

Measure whole-scene cost with several real widgets, not only isolated component cost. Do not add an accelerated/offscreen surface for cosmetic card treatment without a broader measured architectural benefit.

## 17. Validation checklist

Deterministic/model as applicable:
- config/default/style projection;
- stable IDs/list model;
- coherent revision/state mapping;
- stale rejection;
- semantic action admission;
- no-op mutation.

Ownership/runtime:
- real `WidgetRuntimeManager` or existing neutral owner injection;
- cardinality preserved/reduced;
- activation vs ordinary enabled distinction;
- one consumer retirement does not kill surviving shared consumers;
- stale async fenced;
- capability/common-import dormancy.

Retained Quick:
- one existing process engine/window path;
- stable item/model/list-model identity;
- geometry/fade/style changes in place;
- no QWidget/effect/business object in QML;
- no extra accelerated surface.

Eyes-on:
- normal/empty/loading/error/cached states where relevant;
- card on/off;
- realistic long/short content;
- practical DPRs/sizes;
- interactions/transient menus/controls/tooltips;
- busy background where readability/shadows matter;
- non-CUSTOM collision placement with several families;
- global CUSTOM entry/exit without authored stacking leakage;
- at least Default Dark plus a deliberately contrasting Widget Theme;
- family explicit override precedence;
- Card Surface/Card Border/Header Fill theme inheritance, explicit Reset-All-Colours behavior, and only genuinely specialized family override precedence.

Theme coverage should not rely solely on eyeballing: use a static literal/semantic-role inventory and, when useful, a non-shipping diagnostic Widget Theme with deliberately distinct role colours to expose unowned presentation pixels. Human review still decides whether an unchanged pixel is intentionally local.

Then caller-proof and retire old pixels.

## 18. Visualizer exception

Spotify Visualizer is not an ordinary widget-family presentation. Its authored logical runtime and inline
custom-GL render-node contracts are governed by visualizer docs/guardrails. Do not force it through ordinary
widget abstractions merely for consistency.

## Repeated list semantic rails

For repeated-list widgets, keep column reordering separate from free child
movement. Reddit/Reddit2 (`age`, `ago`, `title`) and Gmail (`timestamp`, `sender`,
`subject`) declare their stable semantic columns in `rendering/quick/column_rails.py`.
The family model projects the validated widget-wide `size_payload.column_rails`
from the existing CUSTOM owner through a dedicated discrete column-order signal,
not through a per-child-geometry notification, and every retained QML row derives column X
and width from that same order. When the key is absent, the existing header-flip
orientation supplies the default. Do not persist row identities, one X offset per
entry, or provider-derived data in CUSTOM, and do not let an X-only swap detach Y
flow or rebuild the list model. The selected/unlocked Edit overlay alone loads
vertical guides and grip hit-zones; a release calls the shared discrete swap
slot once, with the ordinary three-action Undo/Save/Cancel/Restore/lifecycle
authority. Wheel/outer resize must carry the *current* order, not resurrect a
baseline permutation after Restore. Test the actual painted rows, not just the
model list, in both orientations and after Save/reopen and slot hydration. Qt
and physical acceptance are separate from pure schema/source tests.
