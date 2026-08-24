# 09 — Ordinary Widget Qt Quick Presentation State Bridge

Status: **cross-cutting E3/F technical decomposition; sequence owned by `Current_Plan.md`**
Last updated: 2026-08-24

Cross-links:

- active sequence/work admission: `Current_Plan.md`
- widget/runtime architecture: `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- runtime ownership/threading: `Docs/QtQuick_Migration/08_Widget_Runtime_Ownership_Threading.md`
- host/scene lifecycle: `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md`
- CUSTOM/input: `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`
- build/QML validation: `Docs/QtQuick_Migration/06_Build_Tooling_Validation.md`
- runtime efficiency: `Docs/Guardrails/Runtime_Efficiency.md`
- tests/retirement ledger: `Docs/TestSuite.md`

This document is **not a new Phase-F plan**. It defines the technical boundary used when ordinary
widget pixels move from QWidget presentation into the retained Qt Quick scene.

---

## 1. Core destination

For ordinary widget families:

```text
provider/backend/runtime owner
        ↓
normalized current family state
        ↓
stable presentation model
        ↓
retained Quick component
        ↓
shared Quick primitives + family-specific visual
```

The Quick component consumes presentation state and emits semantic actions.

It does not own:

- network/provider logic;
- SettingsManager;
- refresh cadence;
- account/session ownership;
- business cache;
- general runtime generation;
- background worker lifecycle.

Do not reproduce `BaseOverlayWidget` as one giant QML/Python Quick base object.

---

## 2. Stable model boundary

Do not expose arbitrary Python object graphs directly to QML.

Choose a model shape that matches the presentation.

### 2.1 Scalar/card-style family state

For a compact card such as Clock/Weather/Media summary state, prefer a stable presentation object with
explicit, typed/normalized properties.

Conceptually:

```text
WeatherPresentationModel
    location_text
    temperature_text/value
    condition
    icon_identity
    forecast rows/model
    missing_location
    refresh/error presentation state
    style
```

The exact class names are source-owned; the contract is explicit presentation state, not raw backend
objects.

A stable model object is preferable to replacing the entire QObject tree on every update.

### 2.2 Repeating rows/cards

For Reddit, Gmail, Steam lists/rows or similar repeating content, use stable row identity and a bounded
list-model contract.

`QAbstractListModel` or an equivalent proven PySide/QML model is appropriate where it makes the
boundary simpler.

Do not blindly rebuild a deep QML object tree from arbitrary Python dictionaries on every refresh.

Incremental row diffing is **not mandatory** when lists are small/infrequent. A bounded model reset may
be the simpler correct implementation. Choose the least machinery that keeps update cost and behavior
healthy.

Required regardless of update strategy:

- deterministic row identity;
- no stale row action targets;
- bounded item count;
- current-generation ownership;
- consistent state after one update transaction.

---

## 3. State publication and atomicity

A runtime owner prepares one coherent next presentation state.

Apply related changes on the GUI/presentation owner in one bounded update turn.

Avoid visible half-state such as:

```text
new title
old artwork
old provider identity
new progress
```

when those fields represent one committed media/widget update.

Possible techniques include:

- one immutable state object applied into a stable model;
- batched property update followed by one revision/changed signal;
- list reset/diff under the model's normal update transaction.

Do not add a heavyweight transaction framework merely for ordinary property changes.

Identical state should be a no-op wherever practical.

---

## 4. Latest state vs events

Ordinary widget presentation is generally **current-state oriented**.

Examples:

```text
current clock text
current weather
current Reddit rows
current Gmail rows
current media metadata/progress
current Steam card
```

Newer current state may replace older unread presentation state.

Do not turn presentation updates into an unbounded FIFO.

One-shot business events are different.

Examples:

- notification sound;
- provider-side action completion;
- exactly-once external side effect.

Those belong to the Python runtime/business owner and must not depend on whether QML sampled a state
revision.

Presentation may show the resulting current state or a bounded authored visual consequence.

---

## 5. Action boundary

Quick emits **semantic actions**, not provider calls.

Examples:

```text
refresh
open_item(item_id)
open_settings
media_previous
media_play_pause
media_next
set_volume(value)
toggle_mute
archive_message(message_id)
open_message(message_id)
```

Routing:

```text
Quick item
-> semantic action signal/router
-> presentation-neutral runtime/business owner
-> provider/backend/action execution
-> new current state
-> presentation model
```

Do not place network/auth/cache logic in QML JavaScript handlers.

Do not pass a live provider/controller object into QML merely so a button can call it.

Action targets use stable semantic IDs, not references to retired row QObjects.

---

## 6. Dynamic images and artwork

Image handling is a cross-family seam: Weather icons, Media artwork, Reddit imagery where supported,
Gmail icons, Steam artwork.

### 6.1 Static packaged assets

Static product assets should use the chosen QML/package resource path and packaging contract.

Do not create Python pixmaps merely to load a static icon that Quick can own directly.

### 6.2 Dynamic/provider images

Preferred conceptual boundary:

```text
worker/provider
-> bytes / decoded QImage + stable image identity
-> presentation image broker/model
-> one proven Quick image-delivery mechanism
-> retained Quick image item
```

Use a stable identity/cache key so unchanged artwork does not decode/upload again.

`QImage` may be prepared off the GUI thread when the operation is thread-safe.

Do not move `QPixmap` ownership into general workers or render callbacks.

### 6.3 One shared delivery mechanism

When the first dynamic-artwork family establishes the pinned-PySide Quick image mechanism, prefer one
shared, tested application mechanism for later families rather than inventing:

```text
Media image bridge
Reddit image bridge
Steam image bridge
Gmail image bridge
```

with incompatible lifetime/cache semantics.

Possible implementation choices must be proved in the pinned runtime before becoming contract. The
architecture requirement is one bounded Quick-compatible image-delivery seam, stable identity, legal
thread ownership and explicit cache/lifetime.

Avoid:

- base64/data-URI rebuilding every update;
- tempfile-per-frame/per-refresh churn;
- repeated QImage→QPixmap→QImage conversion;
- texture upload when image identity is unchanged;
- exposing provider filesystem/cache internals directly as the QML API.

---

## 7. Geometry ownership

Keep global placement authority outside family QML.

Python/runtime geometry resolves:

- owning display;
- outer rect;
- stacking;
- z order;
- pixel-shift offset;
- CUSTOM override;
- display/DPR-dependent projection.

Family QML owns layout **inside** its assigned presentation rect.

Do not recreate global stacking in QML anchors.

Do not use a family QML component as a second CUSTOM persistence authority.

Cross-monitor transfer moves/recreates presentation ownership while preserving the logical runtime
owner/model unless product semantics explicitly require otherwise.

---

## 8. Style boundary

Shared authored style semantics belong in a presentation-neutral style/model structure and retained
Quick primitives.

Common state may include:

```text
font
text color/alpha
background/card
border
corner radius
padding/margin
card shadow
text/header shadow
overall authored opacity
global shadow direction
```

Family-specific style remains family-specific.

Prefer composition:

```text
OverlayCard
+ HeaderRow
+ Artwork
+ rows/content
+ controls
```

over one giant inheritance-style `QuickBaseOverlayWidget`.

Do not remove a currently-supported style switch because it is awkward in Quick unless the migration
plan explicitly retires it.

---

## 9. Update-cost rules

Retained Quick widgets should be mostly event-driven.

Forbidden patterns unless explicitly earned:

- Python callback every physical frame for static widget content;
- QML `Timer` used for provider/network refresh;
- always-running hidden animations;
- rebuilding the component tree for unchanged data;
- rebinding large mutable maps on every tick;
- large `ShaderEffectSource`/layer capture merely to reproduce a simple card;
- changing image source when image identity is unchanged;
- a static widget keeping the custom-GL presentation pacer alive.

Ordinary visual animation such as fade/hover/progress interpolation may use Quick-native animation.

Presentation animation never becomes provider/simulation clock authority.

When an item becomes hidden/deactivated/retired, presentation-only continuous animation should stop
unless it has an explicit reason to continue.

---

## 10. Presentation lifecycle is not service lifecycle

Creating/destroying a Quick component must not implicitly create/destroy the backend unless that
backend is genuinely per-presentation by contract.

Required separation:

```text
runtime/model may remain valid
        ↓
Quick item destroyed/recreated
        ↓
new Quick item binds current model state
```

Examples:

- display scene recreation;
- temporary presentation transfer;
- CUSTOM transfer;
- Quick component replacement during migration/harness work.

Likewise, retiring the family runtime owner must close presentation admission and detach/destroy its
Quick presentation; a surviving item cannot keep a retired provider alive through an accidental
reference.

---

## 11. QML engine/context lifetime

Follow `01_Runtime_Host_Lifecycle.md`:

```text
one application-level component/cache owner where useful
+
generation/display-scoped contexts/root items
```

Do not create one QML engine per widget.

Do not register runtime family models as process-global QML singletons.

A shared engine/cache must not become a hidden owner of retired display/runtime model references.

---

## 12. Family-port decomposition template

Before coding a Phase-F family, write down the current family inventory under these headings.

### 12.1 Runtime/business

- provider/backend;
- cache;
- cadence/timers;
- async request identity;
- account/source/filter state;
- actions;
- shared state;
- notification/business side effects.

These should already be neutral or explicitly rehomed.

### 12.2 Presentation state

List every piece of state actually required by pixels.

Do not expose whole backend/config objects when the visual needs six fields.

### 12.3 Presentation features

List:

- card/background/border/shadows;
- fonts/colors;
- artwork/icons;
- rows;
- progress/controls;
- visibility/fade;
- family-specific decoration;
- hover/interaction;
- sizing;
- CUSTOM behavior.

### 12.4 Actions

Map every current click/control route to a semantic action.

### 12.5 Assets

Classify each as:

```text
static packaged asset
dynamic provider image
generated presentation image
custom GL content
```

Choose the existing shared delivery seam where one exists.

### 12.6 Geometry

Identify:

- canonical default placement;
- stack footprint;
- CUSTOM size/position semantics;
- min/max/aspect rules;
- monitor routing;
- DPR-sensitive behavior.

### 12.7 Final owner map

For every old QWidget responsibility, assign one destination owner.

Nothing should remain “temporarily in QML because it was easy” without an explicit migration reason.

---

## 13. Feature-parity mapping table

Before calling a family port complete, maintain a bounded implementation/test table conceptually like:

| Existing behavior/setting | Destination owner | Presentation property/action | Quick primitive/component | Test/evidence | Status |
|---|---|---|---|---|---|
| font size | style/model | `fontSize` | text primitive | mapping + gallery | preserve |
| provider refresh | runtime service | none | none | owner tests | preserve |
| click open item | action owner | `open_item(id)` | pointer handler | action test | preserve |
| old QGraphics shadow cache | none | authored shadow style only | Quick shadow primitive | visual/regression | implementation retired |

Do not require this exact Markdown table in every commit. The contract is that every currently-supported
feature has an explicit destination or an explicit plan-authorized retirement.

This is the primary guard against accidental feature loss during “clean” rewrites.

---

## 14. Family-specific guidance

### Clock

Likely model-heavy only:

- formatted strings/angles;
- timezone/calendar state;
- style;
- analog/digital presentation mode.

Do not invent provider infrastructure around the already-neutral ticker.

### Weather

Quick should consume prepared current Weather state. Network/cache/refresh ownership remains Python
runtime-side.

Weather icons should use stable asset/image identity rather than rebuilding pixmaps through the old
QWidget path.

### Media

Use a stable coherent state revision for metadata/artwork/provider/playback/progress where visual
consistency matters.

Transport and volume actions route back to the Python controller owner.

Dynamic artwork is the likely family to establish the shared dynamic Quick image-delivery seam if a
simpler family has not already done so.

The landed E1 Media owner already supplies one source-resolution `QImage` plus stable identity and one
coherent revision to every display lease. Phase F must consume that state without recreating a
controller, poll loop or decode path; the Quick presenter owns its logical/DPR texture projection.

### Reddit / Reddit2

Use stable row IDs and normalized row data.

The neutral post-provider remains Python-owned after the QWidget disappears.

Reddit2 inheritance belongs in model/config resolution, not duplicated QML inheritance logic.

### Gmail

Use stable message IDs for rows/actions.

Notification sound/business detection stays Python-owned.

QML does not own Gmail backend/session/auth.

The landed E1 owner at `4f7dc869` publishes one shared raw-email/unread/error/action runtime stream over
the existing `GmailBackend` singleton. Quick retains row grouping/formatting/layout and dispatches
stable message IDs back to that owner; it never captures a retired presenter in an action worker.

### Steam

Preserve the existing provider/cache/model strengths. The landed Achievement owner publishes a prepared
card model plus source-resolution decoded `QImage` artwork/icon state with stable identities. Its current
QWidget presenter owns DPR-specific scaling/cropping caches; the future Quick presenter must own its own
equivalent projection. The bounded Abandonment correction at `9ab4f47e` established the same boundary
without duplicating its decode/fetch path.

Quick consumes normalized card/view-model state; do not move ranking/cache/security/product logic into
QML merely because the visual is being replaced. Rebinding or recreating a Quick item must replay the
service's current prepared state without starting another provider, cache load, timer or image fetch.

---

## 15. Testing obligations

A Phase-F family is not migrated merely because its QML file loads.

Prove as applicable:

- presentation model maps current runtime state correctly;
- stable list IDs/actions target correct current rows;
- stale generation/model cannot update replacement scene;
- static state does not cause recurring presentation work;
- hidden/retired item stops presentation-only continuous work;
- image identity prevents unnecessary decode/upload;
- dynamic image path uses legal thread ownership;
- action routing reaches the correct Python owner;
- Settings/detail configuration maps to the same authored visual features;
- stacking/CUSTOM/monitor routing remain correct;
- item recreation rebinds current model without provider recreation;
- no QWidget/provider object is required by the final Quick component;
- shared primitives preserve family visual semantics;
- feature-parity mapping has no unexplained omissions.

Use offline/synthetic models in the Quick widget gallery wherever network/provider access is irrelevant
to pixel validation.

---

## 16. Anti-patterns

Do not land:

```text
QML directly imports/calls business/provider logic
raw SettingsManager exposed to QML
provider QObject passed into button handlers
one QML engine per widget
Python frame callback for static retained content
QML provider-refresh Timer
arbitrary mutable dict tree as the permanent family API
QPixmap moving through worker threads
per-family bespoke image bridge without need
recreated Quick component for every data refresh
global stacking duplicated in QML
old QWidget screenshot texture as final presentation
one giant QuickBaseOverlayWidget replacement
```

A family may legitimately need a special presentation primitive. Special visual behavior is not a
reason to duplicate runtime ownership.
