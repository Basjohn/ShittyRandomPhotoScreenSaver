# 10 — Qt Quick Ordinary Widget Family Port Decomposition

Status: **Phase-F ACTIVE decomposition; F0 deletion audited GREEN and packaging residue closed here; F0.5 active next**  
Last updated: 2026-08-24  
Source/decomposition basis: `19460a7a8ffe9e5134363267da3d61fe46cc23d4` + this closure reconciliation

This is subordinate to `Current_Plan.md`. Phase E is closed; F0 deletion is source-audited GREEN at `19460a7` and this reconciliation removes its final stale scraping dependency pins. `Current_Plan.md` currently admits F0.5 only: complete Widgets → General canonical shadow controls, then audit before F1 Clock.

Cross-links:

- `Current_Plan.md`
- `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- `Docs/QtQuick_Migration/09_Widget_Quick_Presentation_Bridge.md`
- `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`
- `Docs/QtQuick_Migration/08_Widget_Runtime_Ownership_Threading.md`
- `Docs/10_WIDGET_GUIDELINES.md`
- `Docs/TestSuite.md`

---

# 1. Phase-F mission

Port ordinary runtime **pixels** from QWidget presentation into the one retained Quick scene while
preserving E1's presentation-neutral runtime/provider ownership.

For each family:

```text
existing neutral runtime owner/state
        ↓
stable presentation model
        ↓
retained family QML content
        ↓
E3 OverlayWidget / OverlayCard / ShadowedText / Separator
        ↓
one display QQuickWindow
```

Do not port the Settings GUI to QML merely because runtime pixels move.

Do not delete useful neutral Python behavior merely because it lived next to QWidget code.

---

# 2. Phase-F sequence

Recommended bounded order:

```text
F0    Imgur removal — CLOSED after reconciliation
F0.5  Widgets → General shadow controls — ACTIVE NEXT
F1    Clock / Clock2 / Clock3
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

Why:

- Clock proves the first real family component/model seam with no provider/image/list complexity.
- Weather adds richer structured state and icon identity.
- Media then earns the shared dynamic-artwork mechanism rather than having it guessed in advance.
- Media controls build on the core model/action path.
- Reddit/Gmail exercise bounded lists and stable semantic IDs.
- Steam families come after the bridge is proven across scalar, image, action and list shapes.

If exact current source shows a smaller safer order inside a family, split the slice. Do not rearrange
families merely to dodge an architecture issue discovered by the first family.

---

# 3. F0 — remove deprecated Imgur — CLOSED after reconciliation

Imgur is not a Quick target.

Remove, as applicable to exact current source:

- family/gate/default entries;
- settings controls;
- descriptors/factories;
- runtime/provider implementation;
- CUSTOM entries;
- tests;
- packaging references;
- current-authority docs;
- Foundry metadata.

Do not break historical evidence documents merely to erase the name.

Source audit confirms the current tracked tree has no Imgur path and the family/catalog/default/Settings/
factory/runtime/CUSTOM/input/cache/assets/test surfaces were deleted. The audit also found
`beautifulsoup4`/`soupsieve` left in `requirements.txt` with no current `BeautifulSoup`/`bs4` consumer; this
closure reconciliation removes those stale Imgur-era pins. Test execution evidence remains the implementing
agent's report unless rerun independently. Exit documentation is reconciled in the same pack.

---

# 3.1 Phase-F presentation hard rule — no QWidget effect-carrier/dummy ports

Do not preserve a workaround merely because it is present in legacy pixels.

In particular, the QWidget shadow/fade architecture may contain `ShadowFadeProfile`,
`QGraphicsOpacityEffect`, dummy/effect-carrier widgets and staged widget-vs-shadow attachment/fade
because one QWidget can own only one graphics effect. Qt Quick does not require that structure for the
retained family shell.

Required retained shape:

```text
OverlayWidget root opacity
    -> OverlayCard + cached RectangularShadow
    -> ShadowedText duplicate glyphs
    -> family content
```

One root opacity fades the composition together. Do not add another shadow-fade timeline or a wrapper
whose only job is carrying an effect.

Intermediate Quick Items must have a real responsibility (layout, transform, clipping, z grouping,
input or lifecycle composition). This rule applies to every family, beginning with Clock.

Frosted/backdrop-glass cards are explicitly deferred to `Future_Work.md`. Do not add shared backdrop
capture, blur layers or glass customization while migrating ordinary family pixels; first prove the
plain retained card/fade/shadow architecture across real families.

---

# 4. F0.5 — Widgets → General canonical shadow controls — ACTIVE NEXT

F0.5 is a bounded QWidget Settings slice. It does not create a runtime family component. The existing
Widgets → General → Appearance page already owns the three shadow enable toggles; extend that existing
owner rather than adding another page/model.

Detailed UI/style contract: `Docs/Custom_Style_Implementation.md`.

## F0.5.1 Mandatory global direction picker

```text
┌─────────────┐
│ ↖   ↑   ↗  │
│ ←       →  │
│ ↙   ↓   ↘  │
└─────────────┘
```

- canonical tokens `NW/N/NE/W/E/SW/S/SE`; default/fallback `SE`;
- center inert; no ninth semantic;
- existing `widgets.shadows.direction` only;
- no UI-local resolver and no QML Settings reader.

## F0.5.2 Two user tuning buckets

Widget/Card:

```text
enabled             existing
frame_opacity       Darkness
blur_radius         Blur
frame_extra_offset  Extra Offset (new, >=0 logical px, default 0)
header_enabled      existing header toggle
```

Text:

```text
text_enabled        existing
text_opacity        Darkness
text_extra_offset   Extra Offset (new, >=0 logical px, default 0)
```

No Text Blur. No per-family editor. No third Header tuning panel. Header may retain authored internal
baseline alpha/magnitude but consumes the shared direction/Text modifier path.

`Extra Offset` is additive to class/base magnitude before the canonical direction resolver. Do not
repurpose legacy `widgets.shadows.offset`; do not add signed X/Y user controls.

## F0.5.3 Retired Intense semantics stay retired

Do not reintroduce `intense_shadow`, `analog_shadow_intense`, `digital_shadow_intense`, an Intense
checkbox, or an Intense preset/profile. The destination is one shadow system. Old painter tuning numbers
are reference evidence only and are not Quick UI slider values.

## F0.5.4 Mandatory persistence repair

Exact current source has a dangerous partial-section pattern: `save_defaults_settings()` emits only the
three enable booleans under `shadows`, while `apply_widget_section_save_results()` assigns the returned
section mapping wholesale. This can erase E4's `direction` and other shadow values on an unrelated
General save.

Fix the owner, not the symptom: merge edited values into the existing canonical `widgets.shadows`
mapping or otherwise preserve every unedited/unknown key. Do not create a second shadow persistence
store. Add a regression that saves an unrelated General field and proves arbitrary sentinel shadow keys
survive.

## F0.5.5 Focused gate

Prove:

- all eight directions, inert center, SE reset/default/fallback;
- existing three enable toggles still round-trip;
- Card Darkness/Blur/Extra Offset and Text Darkness/Extra Offset round-trip and clamp;
- Extra Offset cannot become negative;
- unedited/unknown shadow keys survive every General save path;
- `ShadowSettings`, canonical defaults and generated defaults/SST artifacts stay in parity;
- no Intense key/UI and no text-blur property/effect;
- Settings lazy-page/save behavior remains intact;
- no runtime family/provider is constructed merely by opening/saving General.

Push and stop for independent audit. **Do not begin Clock in this checkpoint.**

---

# 5. F1 — Clock family

Clock is the first real family port and the first proof of the generic family-content seam.

## F1.0 Current owner inventory

Preserve:

- `GlobalClockTicker` as the shared one-second runtime cadence authority;
- timezone parsing/normalization in Python;
- formatted clock/calendar/timezone state in presentation-neutral Python;
- exact one-second analogue hand-angle semantics;
- settings persistence in existing settings owners;
- activation/instance-enabled semantics.

Retire/rehome as presentation:

- `ClockWidget` QLabel/QPainter pixels;
- `PaintedShadowLabel` use for Clock pixels;
- QPixmap analogue face/frame buffers as final presentation;
- painter card/separator/text shadows;
- QWidget geometry mutation as final Quick geometry authority.

Do not create a `ClockService` merely for structural symmetry.

---

## F1.1 First generic family component seam

Introduce the smallest static family-presentation registry/component cache needed to create Clock
content inside the E3 retained shell.

Required properties:

- process-level family QML component compilation using the existing engine;
- per-display instance creation using the existing context;
- stable model binding;
- no provider/settings/QWidget passed into QML;
- no per-family branch in `DisplayScene.qml` or `QuickSceneController`;
- host retirement also retires family child content;
- family item recreation rebinds current Clock model without rebuilding the shared ticker.

A plausible destination:

```text
WidgetPresentationDescriptor(
    widget_id/family,
    qml_component,
    presentation_model_type
)

QuickSceneFactory
    -> cache ClockContent.qml component

OrdinaryWidgetPresentationHost
    -> create shell
    -> create ClockContent child in shell content area
    -> bind ClockPresentationModel
```

Exact names may differ. Keep machinery proportional to the problem.

Audit checkpoint recommended after the first real family-binding seam if it changes factory/host
lifecycle architecture.

---

## F1.2 Clock presentation model

Use one stable presentation-oriented model per logical Clock instance.

Candidate state:

```text
timeText
calendarLines / calendarText
timezoneText
displayMode            # digital | analog
hourAngle
minuteAngle
secondAngle
showSeconds
showNumerals
showSeparator
calendarLayout
font/style state
separator style
geometryVariant
```

Do not expose:

- Clock QWidget;
- SettingsManager;
- ticker QObject merely so QML can subscribe itself;
- parent display widget;
- raw CUSTOM persistence map.

Ticker update occurs once per authored second and publishes the current scalar state/angles.

---

## F1.3 Digital visual

Preserve/implement:

- main time;
- 12/24-hour formatting;
- seconds option;
- tabular/stable numeral layout where current Qt Quick font behavior supports the intended result;
- calendar/day/date;
- shared/two-line calendar formatting;
- timezone;
- card/background/border;
- one retained-root whole-widget fade (no dummy/effect carrier or separate shadow fade);
- ordinary offset text shadows;
- separator when enabled;
- font fitting inside assigned rect without rewriting outer committed geometry.

A content reflow caused by changing time text must not move the outer widget.

---

## F1.4 Separator product improvement — REQUIRED

The current legacy digital separator is 1 px, ~55% width and asymmetrically spaced.

New Clock separator contract:

### Thickness

```text
2 logical px
```

### Width

Target:

```text
~0.77 × available inner Clock width
```

This is approximately 40% wider than the legacy `0.55` ratio.

Do not keep an old absolute pixel maximum if it prevents the separator from becoming visibly wider on a
large Clock. Final eyes-on tuning may move the ratio modestly, approximately `0.75–0.80`.

### Spacing

Use one symmetric gap:

```text
primary content
      ↓ separatorGap
separator
      ↓ separatorGap
calendar/day/date
```

Do not copy the legacy independent `DIGITAL_FOOTER_GAP=8` and
`DIGITAL_SEPARATOR_CALENDAR_GAP=6` asymmetry as two authorities.

### Analogue

When `showSeparator` is enabled and calendar/day/date exists:

```text
analogue face/numerals
      ↓ separatorGap
separator
      ↓ separatorGap
calendar/day/date
      ↓ ordinary row gap
timezone (if enabled)
```

The setting is a Clock separator behavior, not a digital-only visual accident.

During migration the old persisted `show_digital_separator` key may feed `showSeparator`. A final
persistence rename belongs to the H0 settings epoch unless separately authorized.

---

## F1.5 Clock text shadows — REQUIRED

Exact legacy text-shadow architecture is offset-only.

For Clock secondary text:

```text
calendar/day/date
timezone
```

use the **same resolved ordinary-text shadow style**:

- same magnitude class;
- same global direction;
- same alpha/color semantics;
- no separate calendar offset;
- no MultiEffect/text blur.

The current timezone appearance is the visual reference for the day/date shadow. Do not preserve an
over-separated day/date shadow if the old modes diverge accidentally.

Digital and analogue must agree on this semantic.

F1 must also prove the real E4 wiring path:

```text
widgets.shadows.direction
    -> canonical Python ShadowDirection resolver
    -> Clock card / ordinary-text / large-text authored magnitudes
    -> signed offsets in Clock presentation style
    -> existing retained Clock shell/content properties
```

Changing direction must not recreate the Clock item, its presentation model, `GlobalClockTicker`,
engine or top-level window.

Main time/numerals may resolve through canonical large-text tuning if the font-size resolver calls for
it; that does not authorize a separate arbitrary mode offset.

Required eyes-on comparison:

- digital day/date vs timezone;
- analogue day/date vs timezone;
- direction changes in at least SE/NW/N/E;
- light and busy photographic backgrounds.

---

## F1.6 Analogue retained visual

Prefer retained Quick primitives/items over a QWidget-style frame-buffer loop.

Static retained elements:

- face/ring;
- hour markers;
- numerals;
- separator;
- calendar/date;
- timezone.

Dynamic once per second:

- hour/minute/second hand rotations;
- time-derived strings when required.

Do not redraw/recreate the static face tree every physical frame.

Analogue face/hand shadow personality may remain family-specific where current authored visuals differ
from ordinary text/card shadow classes. It still consumes the global E4 direction authority where that
shadow class participates in the global direction product feature.

If a custom scene-graph item is actually needed for fidelity/performance, prove that need first. A
normal retained QML implementation is preferred for an ordinary one-second clock.

---

## F1.7 Geometry variants — REQUIRED BEFORE CLOCK CLOSURE

Clock's modes are different geometry variants:

```text
digital
analog
```

F1 must expose a presentation/geometry contract capable of asking for the target variant's rect.

For ordinary non-CUSTOM default positioning, keep stable anchor/margin intent and resolve each mode's
natural footprint without cumulative mutation.

For CUSTOM:

```text
digital -> A
analog  -> B
```

Round trip must restore exact A/B.

First-ever target mode may initialize once from current visual center + target natural size + clamp.
Thereafter switches restore saved target geometry.

Do not carry the legacy recursive center-derived switch behavior forward as the destination.

F1 tests the semantic adapter even if final persistent edit-session storage is completed in G.

### Required F1 geometry tests

- 50+ live digital↔analogue switches produce exactly two stable rects;
- custom digital manual resize changes only digital variant;
- custom analogue manual resize changes only analogue variant;
- font/calendar/timezone updates do not silently alter inactive variant;
- mode switch does not alter shared ticker/provider identity;
- two Clock instances maintain independent variant state;
- Clock2/Clock3 inherit the same variant semantics.

Phase G adds Save/Cancel/restart/cross-monitor persistence tests.

---

## F1.8 Clock completion gate

Deterministic:

- model/state mapping;
- one-second ticker cadence/angles;
- family component uses existing engine/window;
- item recreate without ticker recreate;
- one root fade with no staged/dummy shadow fade;
- card alpha/border/shadow;
- text shadow no MultiEffect;
- canonical direction setting resolves through Python into real Clock card/text signed offsets;
- direction changes update the existing Clock item/model/ticker topology in place;
- separator thickness/ratio/symmetric geometry;
- separator visible in digital and analogue when enabled;
- day/date shadow == timezone shadow semantic;
- geometry round-trip no drift;
- no QWidget required by Quick Clock content;
- static analogue decoration not rebuilt per physical frame.

Eyes-on:

- digital default;
- analogue default;
- card on/off;
- calendar one/two line;
- timezone combinations;
- separator on/off;
- multi-DPR;
- several shadow directions;
- repeated live mode switching;
- 3 simultaneous clocks with different configs.

---

# 6. F2 — Weather

## Preserve owner

Use the E1-neutral Weather runtime service/model for:

- provider;
- cache;
- startup state;
- refresh/retry cadence;
- async request generation;
- current normalized state.

## Presentation model

Likely:

```text
location
condition text
temperature
forecast rows
condition/icon identity
loading/error/missing-location state
style
```

## Image seam

Prefer packaged/static icon identity when the current visual can map to packaged assets. Do not create
the full dynamic provider-artwork transport merely because Weather has icons.

If Weather genuinely consumes dynamic provider images in current product behavior, establish the
smallest shared image identity seam and document why Media does not need to be first.

## Gate

Prove offline synthetic states including successful current conditions, stale/cache state, missing
location and provider error. No network is needed for pixel tests.

---

# 7. F3 — Media core

Media is a higher-risk family due to shared controller/provider ownership, artwork, progress, playback
state and Visualizer relationship.

## Runtime owner

Reuse E1's shared Media owner. Presentation does not acquire controller lifetime.

## Coherent presentation state

One revision should coherently represent, as applicable:

```text
provider identity
track/title/artist/album
artwork identity
playback state
progress/duration
control availability
style
```

Avoid mixed old/new track state.

## Dynamic artwork seam

Media is the preferred first serious dynamic-artwork consumer.

Establish one shared Quick-compatible application seam with:

- stable image identity/cache key;
- legal thread ownership;
- no QPixmap worker transport;
- no base64/tempfile churn;
- no upload when identity is unchanged;
- bounded cache/lifetime;
- replacement-scene fencing.

Audit this seam separately if it changes process/display resource ownership.

---

# 8. F4 — Media controls / volume / mute / progress

Build on Media core state/action routing.

Preserve the narrow E1 volume and system-mute owners.

Quick controls emit semantic actions only.

Prove:

- click/drag actions route to correct owner;
- disabled/unavailable controls visually and semantically fail closed;
- progress interpolation, if Quick-native, does not become playback truth;
- hidden controls do not run needless animation;
- volume/mute polling cardinality does not increase per display/item.

---

# 9. F5 — Reddit / Reddit2

Use E1-neutral post-provider ownership.

Presentation:

- bounded row/card model;
- stable post IDs;
- current title/subreddit/metadata/images as supported;
- semantic open/refresh actions.

Reddit2 differences belong in config/model resolution, not a duplicated provider or deep QML
inheritance tree.

Any dynamic imagery should reuse the shared image seam already established if compatible.

---

# 10. F6 — Gmail

Reuse the shared Gmail backend/runtime owner.

Presentation:

- stable message IDs;
- sender;
- subject/snippet;
- timestamp/status;
- bounded unread rows;
- semantic open/archive/etc. actions where current product supports them.

Notification detection/sound stays Python/business-owned and cannot depend on QML visibility.

---

# 11. F7–F10 — Steam family

Order:

```text
F7 Steam Progress
F8 Achievement Pulse
F9 Abandonment Issues
F10 Friend Pulse
```

Preserve current provider/cache/privacy/security/product behavior. Rehome only pixels and presentation
state.

Use stable card identity and the existing neutral runtime owners. Do not duplicate Steam data sources
because four Quick components exist.

Old Steam QWidget/painter implementation plans are migration reference for authored behavior only, not
destination ownership authority.

---

# 12. Shared primitive admission rule during F

Do not pre-build a library of hypothetical widgets.

A new shared QML primitive is justified when:

- the active family needs it now; and
- its API is naturally presentation-only; and
- another family or repeated use makes sharing real rather than speculative.

Likely earned later:

```text
Artwork
ProgressBar
IconButton / transport control
bounded row shell
```

Do not add a generic `HeaderRow`/`UniversalWidgetContent` merely to make file names look symmetric.

---

# 13. Family checkpoint policy

A low-risk family may be sliced:

```text
model/state seam
-> retained pixels
-> action/geometry integration
-> focused gate
-> diff/status
-> commit/push
```

Stop for independent audit when a slice introduces:

- a new generic lifecycle/engine/component owner;
- dynamic image/texture ownership;
- high-impact interactive routing;
- cross-display ownership;
- major geometry persistence;
- a broad family cutover/deletion;
- another architecture boundary identified by current evidence.

Clock's first family binding seam should receive an audit because it defines the pattern every later
family may copy.

---

# 14. Phase-F closure criteria

Before F closes:

- every supported ordinary family has retained Quick pixels or an explicit removal decision;
- no family Quick component owns providers/settings/persistence;
- no ordinary family requires QWidget runtime pixels;
- one static family/component registry exists, not central if/elif dispatch;
- one shared dynamic-image seam exists if required;
- semantic actions return to the correct Python owner;
- Clock geometry variants are preserved for G;
- all surviving visual customization maps to a Quick owner;
- direct QWidget presentation tests have replacement destination coverage before retirement;
- Imgur is gone;
- no extra accelerated top-level surface exists.

Phase G then owns final CUSTOM edit/input/auxiliary presentation.
