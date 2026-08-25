# Custom Style Implementation

Last updated: 2026-08-25

Current Settings/runtime-style guidance during the Quick migration.

## Settings UI

Settings remains QWidget-based.

Do not rewrite Settings in QML because runtime pixels migrate.

## F0.5 shadow controls — LANDED, YELLOW independent audit pending

Widgets → General → Appearance owns:

```text
Widget/Card
  Enable Widget Drop Shadows
  Darkness      -> frame_opacity
  Blur          -> blur_radius
  Extra Offset  -> frame_extra_offset

Text
  Enable Text Shadows
  Darkness      -> text_opacity
  Extra Offset  -> text_extra_offset

Header
  Enable Widget Header Drop Shadows

All
  Shadow Direction -> NW/N/NE/W/E/SW/S/SE
```

Direction picker is compact 3×3; center is inert; default/fallback `SE`.

No Text Blur.
No Intense mode.
No old `widgets.shadows.offset`.

General save must merge into the existing `widgets.shadows` mapping so unrelated/future keys survive.

## F0.5 audit correction

`shadowtuning.json` is retired and must not survive by relocation.

The old generic painted-card profile and the remaining known production relocations have been removed
or simplified at pushed checkpoint `8c9fd468`:

```text
widgets/shadow_utils.py          -> text / text_large / header / icon
rendering/quick/widgets/weather.py -> packaged icon identity
widgets/media/painting.py        -> control
widgets/mute_button_widget.py    -> control
widgets/spotify_volume_widget.py -> volume_slider
```

Independent audit must confirm those profiles remain absent before F1 becomes active.

It is acceptable for the temporary QWidget presenter to lose those generic sidecar-driven shadows.
Preserve the real content/interaction/layout and independently-authored family behavior; do not create a
compatibility tuning layer.

`shadowtuning.json` is retired and must not survive by relocation.

Do not copy its generic sections into another module/file/local constant profile:

```text
card
text
text_large
header
icon
control
volume_slider
```

### Family-authored definition

A visual rule is family-authored only if that family owned the relationship independently of the global
sidecar.

Clock's bespoke analogue ring/marker/numeral/hand shadow relationships qualify.

A sidecar card/text/icon/control number does not become family-authored because it was copied into a
family file.

## Quick destination shadows

Ordinary card:

```text
OverlayCard
-> cached RectangularShadow
```

Ordinary text:

```text
shadow Text at signed offset
+ visible Text
```

No ordinary text blur/MultiEffect.

Whole-widget fade is ancestor/root opacity; do not stage shadow/effect carriers.

## Global modifiers

`frame_extra_offset` / `text_extra_offset` are non-negative logical-pixel additions to a deliberate
destination base magnitude before global direction resolves signs/axes.

F1 Clock establishes the first deliberate destination ordinary card/text baseline. It is not derived
mechanically from the retired sidecar.

## Analogue Clock exception

Read `Docs/QtQuick_Migration/11_Clock_Analogue_Shadow_Contract.md`.

Global direction is mandatory for special analogue directional shadows.

Do not flatten the face's bespoke hard-shadow geometry into the ordinary card/text recipes merely for
uniformity.

## Change process

For shared runtime style:

1. identify current product/style contract;
2. reject obsolete implementation mechanics;
3. update destination retained owner;
4. update focused tests;
5. use eyes-on comparison where fidelity is subjective;
6. reconcile test ownership if a test/module changes;
7. commit/push the bounded slice.

No fidelity downgrade as a performance shortcut.
