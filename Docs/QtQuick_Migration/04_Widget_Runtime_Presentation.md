# 04 — Runtime Widgets, Retained Quick Presentation, Shadows and Full Customization

Status: **Phase-E CLOSED; F0 closed by source audit + reconciliation; Phase-F technical authority / F0.5 active next**  
Last updated: 2026-08-24  
Reviewed source basis: `19460a7a8ffe9e5134363267da3d61fe46cc23d4` + F0 closure reconciliation

Cross-links:

- sequence/work admission: `Current_Plan.md`
- capability activation / Settings: `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`
- runtime ownership/threading: `Docs/QtQuick_Migration/08_Widget_Runtime_Ownership_Threading.md`
- Quick model/assets/actions bridge: `Docs/QtQuick_Migration/09_Widget_Quick_Presentation_Bridge.md`
- detailed family ports: `Docs/QtQuick_Migration/10_Widget_Family_Port_Decomposition.md`
- CUSTOM/input: `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`
- canonical widget authoring guidance: `Docs/10_WIDGET_GUIDELINES.md`
- tests/retirement ledger: `Docs/TestSuite.md`

This is a technical decomposition, not a competing migration plan. `Current_Plan.md` owns sequence.

---

## 1. Core rule

Do not rewrite the widget ecosystem as QML business logic.

```text
provider / runtime / model / settings / semantic actions
                         ↓
                  presentation state
                         ↓
             retained Qt Quick pixels
```

Keep provider/network/cache/auth/persistence/refresh/action ownership in presentation-neutral Python
owners. Move runtime pixels into the display's retained Quick scene.

---

## 2. Landed Phase-E ownership

### E1 — provider/model/runtime ownership CLOSED

The neutral `WidgetRuntimeManager` and family-specific registered owners preserve actual cardinality:

- Clock uses the already-neutral shared ticker rather than an invented Clock service;
- Reddit/Reddit2 post-provider ownership is neutral;
- Weather provider/cache/refresh/request-generation ownership is neutral;
- Steam family owners preserve their actual per-card/shared semantics;
- Media uses one runtime-generation shared owner with display leases;
- Gmail uses the existing shared backend behind a runtime-generation neutral owner;
- Media volume and system mute have narrow shared owners;
- deactivated families remain import/resource dormant at the migrated seams.

Presentation creation/destruction must not become provider/service lifetime.

### E2 / E2.7 — capability foundation CLOSED

Application-level family activation remains separate from ordinary per-instance enabled state.

The Visualizer participates in capability activation but remains the special Phase-D subsystem, not an
ordinary Phase-F widget.

### E3 — retained ordinary-widget substrate CLOSED @ `1f25a791`

Actual landed topology:

```text
QuickSceneFactory
    -> process-level QQmlEngine
    -> DisplayScene component
    -> OverlayWidget component cache

QuickSceneController (per display)
    -> DisplayScene root
    -> ordinaryWidgetHost
    -> OrdinaryWidgetPresentationHost
          -> RetainedOverlayWidget
                -> OverlayWidget.qml
                     -> OverlayCard.qml
                     -> family content
```

Landed primitives:

```text
OverlayWidget.qml
OverlayCard.qml
ShadowedText.qml
Separator.qml
```

`ordinaryWidgetHost` is retained in the existing display scene. It is above the background and below
the visualizer. It is not another window/surface.

The Python host is presentation-only and has no provider/model/settings/QWidget dependency.

Do not add more generic primitives speculatively. Phase F adds a shared primitive only when a real family
needs it and the second use is plausible.

---

## 3. Per-display Quick presentation host contract

Owned by each `QuickSceneController`.

It owns:

- retained `QQuickItem` presentation instances;
- display-space outer rect application;
- root fade opacity;
- shell/card presentation state;
- family content item attachment;
- presentation-only resources;
- presentation retirement for the display generation.

It does not own:

- provider lifecycle;
- runtime-service lifecycle;
- SettingsManager;
- persistence;
- network work;
- worker threads;
- global stacking persistence;
- family business actions.

Presentation retirement order must remain compatible with the Quick scene destruction barrier:
ordinary retained items retire before the QML scene root/context is released.

---

## 4. Component/model boundary for Phase F

The first real family establishes the smallest missing family-content seam.

Preferred shape:

```text
static family presentation descriptor
       -> family id / component path / expected model type
       -> process-level component compilation/cache

per-display OrdinaryWidgetPresentationHost
       -> retained OverlayWidget shell
       -> family content item under shell content area
       -> stable presentation model binding
```

The static descriptor/registry may choose a family QML component. `DisplayScene.qml`,
`QuickSceneController` and `WidgetRuntimeManager` must not become family `if/elif` dispatchers.

Do not expose arbitrary Python business objects to QML. Bind a stable presentation model or a small
explicit property projection.

A family content item may emit semantic presentation actions. The Python action owner executes them.

---

## 5. Geometry ownership

Global geometry stays outside family QML.

Python/runtime geometry resolves:

- owning display;
- outer rect;
- stacking;
- z order;
- pixel shift;
- default/anchored placement;
- CUSTOM override;
- display/DPR projection.

Family QML owns layout inside its assigned rect.

A family with multiple substantially different presentation shapes may define **geometry variants**.
The geometry subsystem, not QML, owns the exact remembered rect for each variant.

Clock is the first known required case:

```text
clock + display
    digital -> rect A
    analog  -> rect B
```

Switching mode restores the target variant. It must not repeatedly derive B from A and then A from the
new B.

See `05_Custom_Layout_Input_Interaction.md` and `10_Widget_Family_Port_Decomposition.md`.

---

## 6. Style model

Keep explicit presentation style capable of representing the surviving authored controls:

```text
font family / size / weight as applicable
text color + alpha
show background/card
background color + alpha
border width
border color + alpha
corner radius
padding/margin
card shadow enable/color/alpha/blur/spread/magnitude
ordinary text shadow enable/color/alpha/magnitude
header shadow enable/color/alpha/magnitude where distinct
overall root fade opacity
global shadow direction
```

Important distinction after exact legacy inspection:

- **card shadows are blurred/spread shadows**;
- **ordinary text/header shadows are offset duplicate-text shadows**;
- no current authored ordinary-text blur control exists.

Do not preserve an accidental E3 `shadowBlur` property as a product feature.

---

## 7. Card shadow destination

Use retained Quick `RectangularShadow`.

Rules:

- `cached: true` by default for ordinary static cards;
- cache invalidates naturally when geometry/style/direction changes;
- root fade does not animate card blur/spread/direction;
- signed offsets are supported and must stay unclipped;
- background/card alpha, border alpha, shadow alpha and root fade remain separate;
- do not recreate old Python/QPixmap shadow caching around the Quick effect.

If a later effect intentionally animates shadow properties continuously, it may explicitly opt out of
caching after measurement.

The shared default QML values are fallback construction values, not final family visual authority.
Family/style resolution must supply canonical authored values.

---

## 8. Ordinary text/header shadow destination

Exact legacy source shows text shadow state is:

```text
enabled
color / alpha
offset x/y magnitude
font-size-dependent tuning/scaling
```

The legacy helpers paint a second text pass at an offset and then paint the real glyph.

Destination:

```text
ShadowedText
    -> retained shadow Text at signed offset
    -> retained main Text
```

No MultiEffect/layer capture/blur is required for current ordinary text parity.

E4 removed from `ShadowedText.qml`:

```text
import QtQuick.Effects
shadowBlur
layer.enabled
layer.effect: MultiEffect
```

The landed primitive is the retained duplicate-glyph offset pass. A later feature may reintroduce an
effect only when exact current product requirements deliberately earn it.

Do not interpret this as a ban on all future MultiEffect use. It is a requirement not to pay for or
canonize a feature SRPSS does not currently author.

---

## 9. E4 — one global eight-direction shadow authority — LANDED / CLOSED

Canonical token:

```text
NW  N  NE
 W     E
SW  S  SE
```

Default `SE`.

Direction controls signs/axis selection only. Magnitudes remain class-specific.

For `(mx, my)`:

| Direction | X | Y |
| --- | ---: | ---: |
| NW | `-mx` | `-my` |
| N  | `0`   | `-my` |
| NE | `+mx` | `-my` |
| W  | `-mx` | `0` |
| E  | `+mx` | `0` |
| SW | `-mx` | `+my` |
| S  | `0` | `+my` |
| SE | `+mx` | `+my` |

Resolve in presentation-neutral Python before QML.

F0.5 removes the old ineffective `widgets.shadows.offset` pair outright. It has no current runtime
consumer and must not survive as a second magnitude authority or be migrated into the new Extra Offset
fields.

## 9.1 F0.5 global user modifiers over authored class baselines

F0.5 adds Settings controls; it does **not** replace the class-specific style model established above.
Resolve them in Python as a small user layer over the authored/base class values:

```text
canonical class/base style
    + global user bucket (card or text)
    + global direction
        ↓
presentation-neutral style projection
        ↓
final signed retained QML properties
```

Canonical user-facing fields:

```text
card: frame_opacity, blur_radius, frame_extra_offset
text: text_opacity, text_extra_offset
direction: one shared widgets.shadows.direction
```

`frame_extra_offset` and `text_extra_offset` are non-negative logical-pixel scalars, default `0`. Add the
applicable scalar to the authored X/Y magnitude before `ShadowDirection` resolves signs/axis. Axis-only
directions still zero the perpendicular axis.

There is no text blur. Card/non-text blur updates the retained `RectangularShadow` or earned non-text
shadow primitive; text remains duplicate glyphs. Ordinary/header/large text all consume the same Text
opacity/extra-offset bucket. Do not recreate sidecar-era per-header alpha profiles. Very large text may
use deterministic destination font-size distance scaling if visual validation earns it, but it is not a
separate settings authority.

Do not restore retired Intense modes. F0.5 deletes the painter `shadowtuning.json` loader/sidecar/path
tests and removes its current runtime imports; do not copy those numbers into Quick UI or a replacement
compatibility module. The old `widgets.shadows.offset` pair is retired at the same boundary and is not
migrated into either Extra Offset field.

F0.5 leaves no hidden runtime magnitude/tuning provider behind. F1 Clock establishes the first deliberate
destination card/text baseline magnitudes in the Quick presentation style seam; later ordinary families
reuse that destination policy. E4's resolver remains capable of distinct magnitudes, but historical
painter dictionaries are not their authority.

When real retained families arrive, changing direction/darkness/blur/extra-offset mutates existing retained
style properties. It must not recreate provider/model/item/engine/window merely because a shadow style
value changed. Card blur/style mutation invalidates the Qt cache naturally; root fade remains independent.

### E4 mutation boundary

A direction change should update signed retained properties without recreating:

- display window;
- scene root;
- ordinary host;
- family runtime owner;
- provider/model;
- ordinary widget shell unless another unrelated contract requires recreation.

---

## 10. F family presentation state

### Clock

Stable scalar/current state. No new provider infrastructure.

Model may expose:

```text
time text / date-calendar text
timezone text
display mode
hand angles
show seconds
show numerals
show separator
calendar layout
style
geometry variant identity
```

Ticker/timezone computation stays Python-owned.

### Weather

Consume prepared neutral Weather state:

```text
location
condition
temperature
forecast
condition/icon identity
error/missing-location presentation state
style
```

No provider/network/cache ownership in QML.

### Media

Use one coherent revision for metadata/artwork/provider/playback/progress/control state. Transport and
volume actions return to Python. The first real dynamic-artwork consumer establishes one shared
Quick-compatible image delivery seam.

### Reddit / Gmail / Steam

Use normalized bounded row/card state and stable semantic IDs. QML does not own account/auth/provider
logic.

---

## 11. Update-cost rules

Retained ordinary widgets are event/state driven.

Do not introduce:

- Python callback every physical frame for static content;
- QML provider/network refresh timers;
- always-running hidden animations;
- component-tree rebuild for unchanged data;
- large mutable dictionaries rebound every tick;
- layer capture merely to imitate a simple offset text shadow;
- image decode/upload when identity is unchanged;
- a static widget keeping custom-GL presentation pacing alive.

A one-second Clock ticker update is authored product state, not a license for per-frame Python work.

---

## 12. Fade and effect-carrier retirement

One authored whole-widget fade maps to the retained outer root opacity.

The current QWidget path needs `ShadowFadeProfile`/`QGraphicsOpacityEffect` staging and related shadow
attachment workarounds because QWidget graphics effects compete for one effect slot. That is
**CURRENT-LEGACY**, not a parity requirement.

Do not port a dummy/effect-carrier hierarchy or a separate shadow fade into Quick.

Destination:

```text
OverlayWidget.fadeOpacity
    -> root Item.opacity
    -> complete retained subtree composites together
       (card + cached card shadow + text-shadow glyphs + text/artwork/controls)
```

Do not animate:

- card blur;
- card spread;
- shadow direction;
- card-shadow alpha merely to imitate root fade;
- text-shadow offsets/alpha merely to imitate root fade;
- provider/model state

to implement whole-widget fade.

Independent card/text/background/border alpha settings remain authored style controls. They are not
additional fade stages.

An intermediate Quick `Item` is allowed only when it owns a genuine layout/transform/clip/z/input/
lifecycle role. Do not create one solely to carry another effect or to reproduce the old
one-graphics-effect-per-QWidget limitation.

---

## 13. Family-port completion bar

A Phase-F family is not complete because its QML loads.

Prove as applicable:

- current runtime state maps correctly into stable presentation state;
- unchanged state is a no-op where practical;
- no stale generation updates replacement presentation;
- no provider/runtime owner is recreated merely because the item is recreated;
- family activation and instance enabled semantics remain distinct;
- no QWidget/provider/SettingsManager is required by final QML;
- semantic actions target the correct current runtime owner;
- geometry/stacking/monitor routing are authoritative outside family QML;
- shared card/text-shadow semantics are preserved;
- no QWidget-era dummy/effect carrier or staged shadow fade was reproduced;
- one whole-widget fade is the retained root opacity;
- display recreation rebinds current state;
- static presentation does not create recurring work;
- visual parity/improvements are covered by deterministic or eyes-on evidence;
- old direct QWidget pixel tests are rehomed before retirement.

See `10_Widget_Family_Port_Decomposition.md` for the family sequence and detailed Clock contract.

---

## 14. Anti-patterns

Do not land:

```text
QML directly calling providers/backends
SettingsManager exposed to QML
provider QObject passed into QML controls
one QML engine per widget
family if/elif dispatch in DisplayScene/QuickSceneController
Python frame callback for static retained content
QML provider-refresh Timer
generic mutable business dict as permanent QML API
per-family bespoke image bridge when a shared seam exists
old QWidget screenshot as final presentation
one giant QuickBaseOverlayWidget replacement
global stacking duplicated in QML
text MultiEffect merely because the primitive can support it
uncached static card shadows by default
```
