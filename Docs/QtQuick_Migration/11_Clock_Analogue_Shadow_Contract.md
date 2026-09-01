# 11 — Clock Analogue Shadow Contract

Status: **landed permanent Clock destination contract; F1 CLOSED**  
Last updated: 2026-08-26

Old Clock runtime pixels are deleted. Git is historical visual reference; this file is current contract.

## Protected composition

```text
ordinary card shadow
+ analogue ring/marker hard shadow
+ Roman numeral special two-shadow composition
+ dynamic hand shadows
+ ordinary footer/day/date/timezone text shadows
```

Do not flatten into one generic effect.

## Outer card

`OverlayCard -> cached RectangularShadow`, canonical Card settings + global direction. Do not recreate old
painted-card cache/profile.

## Ring / markers

Gated by `analog_face_shadow`; hard duplicate geometry/no blur; directional drop baseline ~3 logical px;
shadow ring stroke ~`max(4.4, radius * 0.0462)`; shadow marker ~`max(2.2, radius * 0.01584)`; visible ring
~`max(2, radius * 0.032)`; visible marker width ~`max(2, radius / 60)`; deliberately strong depth/opacity.
These are family relationships, not hidden tuning table.

## Roman numerals

Before visible numeral: main dropped shadow -> close/contact shadow -> visible numeral.
Main drop ~2 px without card / ~3 px with card; contact ~1 px; contact alpha ~84% main; no blur. Do not
flatten to ordinary single-pass ShadowedText. Twelve numerals retained/static across ticks.

## Hands

Gated by `analog_face_shadow`; duplicate shadow line below visible hand; shadow stroke ~1.5× visible;
directional drop baseline ~4 logical px; same rotation/anchor; rounded caps/joins; strong opacity; no blur.
Hand and shadow rotate from same one-second angle state without object rebuild.

## Global direction

All directional analogue shadows use canonical Python resolver:

```text
family-authored baseline magnitude -> ShadowDirection -> signed translation
```

Do not parse direction independently in QML. Direction changes mutate retained translations in place without
rebuilding model/component/numerals/ticker/engine/window.

## General modifiers / analog_face_shadow

Do not invent third analogue tuning bucket. General Card/Text modifiers need not be forced onto special
ring/numeral/hand relationships if fidelity weakens; global direction remains mandatory. Ordinary footer/day/
date/timezone uses ordinary Text path.

`analog_face_shadow` remains real per-Clock feature gating analogue-specific special shadows without changing
mode/geometry/ticker. Clock/Clock2/Clock3 values independent.

## Retained implementation

Static across ticks: ring, markers, numerals+shadow passes, separator, day/date/timezone items where identity
does not require rebuild. Dynamic: hand rotations and time-derived text/state.

No per-tick static face rebuild, old QPixmap face cache solely for parity, MultiEffect/layer capture for hard
shadows, dummy/effect carriers or second shadow timer/fade.

## Permanent regression bar

Preserve `analog_face_shadow`, shared OverlayCard, retained ring/marker geometry, two Roman shadow passes,
contact/main relationship, shared hand rotation+wider shadow stroke, no blur, static face/numeral identity,
global direction mutation in place, ordinary footer/day/date/timezone shadow semantics, and eyes-on card/
numeral/face-shadow/seconds/calendar/timezone/separator combinations across directions/sizes/DPRs/simple+busy
backgrounds.

## Shared calendar separator

The separator is intentionally shared by **both** analogue and digital faces. Current persisted/UI
authority is `show_separator`; `show_digital_separator` is compatibility-read residue only and is queued
for removal in `Future_Cleanup.md`. `separator_thickness` is one 1-8 logical-pixel value consumed by
both faces. The analogue separator uses a 10px separator band (formerly 14px), placing the line roughly
20% closer to the face while leaving face geometry/cadence untouched.
