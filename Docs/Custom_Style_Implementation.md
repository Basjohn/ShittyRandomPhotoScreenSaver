# Custom Style Implementation

Last updated: 2026-08-26

## Settings UI

Settings remains QWidget-based. Settings-window shadows under `ui/widgets/control_shadow.py` are Settings
styling, separate from runtime widget shadow authority.

## Canonical runtime shadow controls — F0.5 CLOSED / independently GREEN

Widgets → General → Appearance owns:

```text
Widget/Card: enabled, frame_opacity, blur_radius, frame_extra_offset
Text:        text_enabled, text_opacity, text_extra_offset
Header:      header_enabled
All:         direction = NW/N/NE/W/E/SW/S/SE
```

Direction picker is compact 3×3, center inert, default/fallback SE. No Text Blur, Intense mode or old
`widgets.shadows.offset`.

General save merges edits onto the existing `widgets.shadows` mapping so unrelated/future keys survive.

## Retired tuning authority

`shadowtuning.json` / `core.settings.shadow_tuning` is retired and must not return by relocation. Do not
reconstruct hidden card/text/text_large/header/icon/control/volume_slider profiles.

A visual rule is family-authored only if the family independently owns it. Clock analogue ring/marker/
numeral/hand relationships qualify; retired sidecar values do not become family-authored because they were
copied into a family file.

## Quick destination

Ordinary card: `OverlayCard -> cached RectangularShadow`.
Ordinary text: duplicate shadow glyph at signed offset + visible glyph.
No ordinary text blur/MultiEffect/layer capture. Whole-widget fade is ancestor/root opacity; no staged
shadow/effect carriers.

Current deliberate ordinary base magnitudes live in retained widget host. User Extra Offset adds before
`ShadowDirection` resolves axes/signs.

## Header styling

`header_enabled` gates destination header-shadow semantic where applicable. Family header frames/logo
geometry remain family content. Do not substitute an unrelated style value because it is convenient: a
header border derives from proper card/header border authority, not a low-alpha row separator colour.

## Clock analogue

`Docs/QtQuick_Migration/11_Clock_Analogue_Shadow_Contract.md` is permanent landed contract. Global direction
applies to directional special analogue shadows. Do not flatten them into generic card/text recipes.

## Change process

Identify current product/style contract -> reject obsolete QWidget/shared-tuning mechanics -> update retained
destination owner -> focused tests -> eyes-on where subjective -> reconcile test/docs ownership -> commit.
No fidelity downgrade as performance shortcut.
