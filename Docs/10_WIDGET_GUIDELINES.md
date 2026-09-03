# Ordinary Widget Authoring Guide

Last updated: 2026-09-02

Canonical guide for adding or deeply refactoring a **non-Visualizer runtime widget** in the accepted Qt
Quick architecture. This guide is based on the landed retained Quick families: Clock, Weather, Media, Reddit/Reddit2, Gmail, Achievement Pulse and Abandonment Issues. It also incorporates the shared colour-only Widget Theme semantics, smart-stacking and global-CUSTOM architecture that later slices added across those families.

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

Use current neutral Steam models/runtime/cache/privacy/provenance seams. Do not manufacture Quick ports for
unfinished Steam Journey/Progress or Friend Pulse scaffolds.

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

Content-driven natural height may derive from accepted state. Keep it separate from transient overlays. Opening Gmail's three-dot menu must not rewrite Gmail's committed CUSTOM height.

### Non-CUSTOM authored stacking

Ordinary placement is owned by the display presentation/orchestration layer, not by family QML. When global CUSTOM is inactive, the smart stacker may project a family away from its authored slot to avoid collisions. A new widget therefore needs:

- a correct base authored rectangle / preferred outer size;
- deterministic size-change notification at real event boundaries;
- no private overlap avoidance, screen-slot search or periodic geometry timer.

Do not persist the stacker's projected collision-avoidance position as new authored user geometry. The authored slot remains the base policy.

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

Migration preserves working family-specific product behavior unless a deliberate product change is requested.
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
