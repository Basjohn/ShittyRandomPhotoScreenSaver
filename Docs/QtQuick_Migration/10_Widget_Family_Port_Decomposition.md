# 10 — Ordinary Widget Family Port Decomposition

Status: **Phase F ACTIVE — F1 CLOSED; F2 Weather ACTIVE**
Last updated: 2026-08-25

This file begins at current/future Phase-F work. Completed F0/F0.5 implementation history does not live
here.

## Phase-F mission

Move ordinary runtime pixels into the one retained Quick scene while preserving presentation-neutral
runtime/provider ownership.

```text
neutral runtime/model
-> presentation model
-> retained family QML
-> OverlayWidget / shared primitives
-> one display QQuickWindow
```

## Sequence

```text
F0.5              closed
F1                Clock / Clock2 / Clock3 — CLOSED
F2                Weather — ACTIVE
F3                Media core
F4                Media controls / volume / mute / progress
F5                Reddit / Reddit2
F6                Gmail
F7                Achievement Pulse
F8                Abandonment Issues
```

Do not reorder merely to dodge an architecture issue. Exact source may justify smaller sub-slices.

## Family retirement

For F1–F8:

```text
inspect old family reference
-> extract/reuse neutral logic
-> build retained Quick family
-> focused tests + eyes-on as required
-> independent GREEN
-> caller proof
-> delete old family pixel presenter/presentation-only tests
-> next family
```

Do not carry completed old family pixels to I.

## No old effect architecture

Do not port:

- `ShadowFadeProfile`;
- QGraphicsOpacityEffect choreography;
- dummy/effect carriers;
- separate shadow fade.

Whole-widget fade = retained root opacity.

## Family-authored visual reference

Preserve family-specific content/layout/animation/interaction/geometry while its Quick replacement is
unproven.

A value is family-authored only if the family itself owned the visual relationship independently.

The retired global `shadowtuning.json` card/text/header/icon/control/volume-slider numbers are not
family-authored reference.

Clock analogue hard-shadow geometry is.

---

# F1 — Clock

Mandatory:

- `11_Clock_Analogue_Shadow_Contract.md`
- `09_Widget_Quick_Presentation_Bridge.md`
- current Clock source as visual/behavior reference

## Runtime/model

Keep `GlobalClockTicker` as shared one-second cadence authority.

Python owns timezone/formatting/angles/settings.

Use one stable presentation model per logical Clock instance.

No new Clock service merely for symmetry.

## First generic family seam

Establish the smallest static family component/model binding mechanism using the existing Quick engine
and ordinary-widget host.

No provider/settings/QWidget in QML.

No family-specific branching in display scene/controller.

## Digital Clock product changes

Required:

- separator = 2 logical px;
- target width ≈ 0.77 inner width, eyes-on range ~0.75–0.80;
- no old 240 px cap defeating widening;
- one symmetric separator gap above/below;
- separator also appears in analogue mode when enabled and calendar content exists;
- day/date shadow matches ordinary timezone secondary-text semantics;
- no text blur.

Legacy `show_digital_separator` may feed semantic `showSeparator` until H settings epoch.

## Shadow wiring

F1 is first real end-to-end proof:

```text
canonical widgets.shadows
-> Python style projection
-> deliberate Quick class base magnitude
-> user Extra Offset
-> canonical ShadowDirection resolver
-> signed retained properties
```

Direction/style change does not recreate Clock item/model/ticker/engine/window.

Do not use sidecar-derived baseline numbers.

Analogue special shadows follow `11_Clock_Analogue_Shadow_Contract.md`.

## Geometry variants

```text
Clock + display
  digital -> rect A
  analog  -> rect B
```

First target with no saved geometry:

1. current visual center;
2. target natural size;
3. center;
4. clamp once;
5. establish target baseline.

After both exist:

```text
A -> B -> A exactly
```

No cumulative derivation/drift.

F1 establishes semantic interface; G owns final CUSTOM Save/Cancel persistence.

## Completion

Deterministic:

- model mapping;
- one-second angles/ticker ownership;
- existing engine/window;
- item recreate without ticker recreate;
- root fade only;
- no text blur/MultiEffect;
- real canonical shadow settings/direction wiring;
- separator contract;
- day/date/timezone shadow semantic;
- geometry round-trip;
- static analogue decoration retained.

Eyes-on:

- digital/analogue;
- card on/off;
- calendar/timezone combinations;
- separator on/off;
- several directions;
- multiple DPR/sizes;
- repeated mode switching;
- multiple differently configured clocks.

F1 is independently GREEN and caller-proven through the current ordinary-widget host. The old Clock
factory/descriptors, QWidget pixel presenter and presentation-only tests are deleted; neutral settings,
geometry metadata and `GlobalClockTicker` remain with their destination owners.

---

# F2 — Weather

Use neutral Weather runtime/provider/cache/refresh/request-generation ownership.

Presentation model covers location, condition, temperature, forecast, icon identity, loading/error/missing
location and style.

Prefer packaged/static icon identities where current behavior permits.

Do not create full provider-artwork infrastructure merely for icons.

Use offline synthetic pixel/model states.

After GREEN, delete old Weather pixels.

---

# F3 — Media core

Higher risk due shared controller, artwork, playback/progress and Visualizer relationship.

Reuse shared Media runtime owner.

Publish one coherent revision of provider/track/artwork/playback/progress/control availability/style.

Media is preferred first serious dynamic-artwork consumer. Earn one shared image-delivery seam with
stable identity, legal threading, bounded cache/lifetime and no unchanged upload.

Audit separately if asset delivery changes process/display resource ownership.

---

# F4 — Media controls

Build on F3.

Preserve narrow volume/system-mute owners.

QML emits semantic actions.

Quick progress interpolation may be visual only; it does not become playback truth.

No cardinality increase per display/item.

---

# F5 — Reddit / Reddit2

Use neutral post-provider ownership.

Use bounded stable post IDs and semantic actions.

Differences belong in configuration/model resolution, not duplicate providers/deep QML inheritance.

Reuse shared image seam if compatible.

---

# F6 — Gmail

Reuse shared Gmail backend/runtime owner.

Stable message IDs; bounded rows; sender/subject/snippet/time/status; semantic actions.

Notification detection/sound remains Python/business-owned.

---

# F7–F8 — substantive Steam family

Use current neutral Steam models/runtime and:
`Docs/SRPSS_Steam_Widget_Family_Implementation_Plan.md`.

Current source reality:

```text
Achievement Pulse   -> substantive implemented runtime/widget
Abandonment Issues  -> substantive implemented runtime/widget

Steam Journey       -> unfinished dev-gated scaffold
Friend Pulse        -> unfinished dev-gated scaffold
```

Only the first two are migration ports.

Do not parse the historical 123 KB pre-Quick plan as current presentation architecture.

Do not build Quick components for Steam Journey/Progress or Friend Pulse merely because scaffold ids,
settings, mock tests or descriptors exist.

### F7 Achievement Pulse

Current source already has strong neutral foundations:

- immutable `SteamCardViewModel`;
- dedicated Achievement resolution;
- dedicated runtime/preparation path.

This should be predominantly presentation mapping/visual fidelity once shared family seams exist.

Preserve existing cache/privacy/provenance behavior and do not duplicate Steam data ownership.

After GREEN, caller-proof and delete old Achievement Pulse runtime pixels.

### F8 Abandonment Issues

Use the existing substantive Abandonment runtime/data path.

Preserve current privacy/provenance/selection semantics. Unknown/private data remains explicit.

Do not duplicate Steam provider/cache ownership per component.

After GREEN, caller-proof and delete old Abandonment Issues runtime pixels.

### Deferred Steam stubs

Steam Journey/Progress and Friend Pulse are future product work, not migration slices.

During migration:

- do not invent their missing product/data behavior;
- do not port scaffold/mock pixels;
- leave them dev-gated if harmless;
- if their scaffold presenter blocks shared old-pixel deletion later, retire the scaffold rather than
  manufacturing a Quick parity implementation.

---

# Shared primitive admission

Add a reusable QML primitive only when the active family needs it now and its API is naturally
presentation-only.

Likely later candidates:

- Artwork;
- ProgressBar;
- transport/icon control;
- bounded row/card shell.

Do not prebuild a universal widget framework.
