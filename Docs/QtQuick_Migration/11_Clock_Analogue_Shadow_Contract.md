# 11 — Clock Analogue Shadow Reference and Destination Contract

Status: **MANDATORY F1 reference**  
Last updated: 2026-08-24

Purpose: preserve the analogue Clock's authored shadow personality without carrying obsolete generic
QWidget/sidecar mechanics into Quick.

## What is protected

Until F1 is independently GREEN, preserve current Clock analogue reference behavior for:

- face/ring shadow;
- hour-marker shadow;
- Roman-numeral shadow;
- hour/minute/second-hand shadow;
- `analog_face_shadow` semantics.

These are family-authored because Clock independently owns their bespoke geometry/relationships.

The ordinary card/frame sidecar profile is **not** protected.

## Shadow composition

```text
ordinary card shadow
+
analogue ring/marker hard shadow
+
Roman numeral special shadow
+
dynamic hand shadows
+
ordinary footer/day/date/timezone text shadows
```

Do not flatten these into one generic effect.

## Outer card

Destination:

```text
OverlayCard
-> RectangularShadow
```

Uses canonical Card settings + global direction.

Do not reproduce old painted-card cache/profile.

## Ring + hour markers

Reference behavior:

- gated by `analog_face_shadow`;
- hard duplicate geometry, no authored blur;
- shadow ring/marker geometry below visible geometry;
- current legacy directional drop ≈ 3 logical px SE;
- shadow ring stroke ≈ `max(4.4, radius * 0.0462)`;
- shadow marker stroke ≈ `max(2.2, radius * 0.01584)`;
- visible ring ≈ `max(2, radius * 0.032)`;
- visible marker width ≈ `max(2, radius / 60)`;
- deliberately strong depth/opacity relationship.

These are visual-reference relationships, not a persistent tuning table.

Tune Quick geometry against the intended appearance if rasterization differs.

## Roman numerals — critical two-pass character

Before the visible numeral:

1. main dropped shadow;
2. close/contact shadow;
3. visible numeral.

Reference:

- main drop ≈ 2 px without card, ≈ 3 px with card;
- close/contact pass ≈ 1 px;
- close/contact alpha ≈ 84% of main shadow alpha;
- no blur.

Do **not** flatten Roman numerals to one ordinary `ShadowedText` pass.

Preferred retained shape:

```text
contact-shadow Text
main-drop-shadow Text
visible Text
```

Twelve numerals remain retained/static across ticks.

## Hands

Reference:

- gated by `analog_face_shadow`;
- duplicate shadow line beneath each visible hand;
- shadow stroke ≈ 1.5× visible stroke;
- legacy directional drop ≈ 4 logical px SE;
- same rotation/anchor as hand;
- rounded caps/joins;
- deliberately strong opacity;
- no blur.

Destination hand + shadow rotate from the same one-second angle state without rebuilding objects.

## Global direction

The global 8-way direction is mandatory for every directional analogue shadow.

Replace fixed SE signs with the canonical Python resolver:

```text
family-authored baseline
-> applicable simple modifier if deliberately chosen
-> ShadowDirection resolver
-> signed translation
```

Do not parse direction independently in QML.

Direction change updates retained translations in place and does not rebuild model/component/numerals/
ticker/engine/window.

## General Card/Text modifiers

Do not invent a third analogue-shadow tuning bucket.

The optional General Text/Card modifiers do not have to be forced onto the special ring/numeral/hand
system if that weakens fidelity or creates awkward semantics.

Global direction remains mandatory.

Roman numeral two-pass relationship remains family policy.

Ordinary footer/day/date/timezone do use the ordinary Text bucket.

## `analog_face_shadow`

This remains a real per-Clock feature, not retired Intense-shadow debris.

It gates the analogue-specific ring/marker/numeral/hand shadow personality.

Clock/Clock2/Clock3 retain independent setting values.

## Retained implementation

Prefer retained Shape/Text/geometry items.

Static:

- ring;
- markers;
- numerals + their shadow passes;
- separator;
- day/date/timezone.

Dynamic once per second:

- hand rotations;
- time-derived text.

No per-tick static face rebuild.
No old QPixmap face cache solely to mimic QWidget.
No MultiEffect/layer capture for these hard shadows.
No dummy/effect carriers.
No second shadow timer/fade.

## F1 proof

Prove:

- `analog_face_shadow` survives model/settings;
- card shadow uses shared OverlayCard;
- ring/markers have retained shadow geometry;
- numerals retain two shadow passes + visible glyph;
- contact shadow remains close and not a second user magnitude authority;
- hand shadows share hand rotation with larger stroke;
- no analogue blur effect;
- no MultiEffect/layer capture solely for analogue shadows;
- static face/numeral identity survives repeated ticks;
- global direction mutates all directional analogue shadows in place;
- ordinary day/date/timezone use ordinary Text shadow path;
- disabling `analog_face_shadow` suppresses analogue-specific shadows without changing mode/geometry/
  ticker ownership.

Eyes-on:

- card on/off;
- numerals on/off;
- face shadow on/off;
- seconds on/off;
- day/date + timezone;
- separator where applicable;
- SE/NW/N/E direction;
- simple and busy backgrounds;
- multiple sizes/DPRs.

After F1 independent GREEN + caller proof, delete old Clock runtime pixels. Git is the historical
reference afterward.
