# 11 — Clock Analogue Shadow Reference and Destination Contract

Status: **Phase-F Clock reference; read before F0.5 removes legacy shadow-tuning consumers and before F1 ports Clock**  
Last updated: 2026-08-24  
Source reference basis: current pre-F1 `widgets/clock_widget.py` at the F0-closure line

This document is subordinate to `Current_Plan.md` and
`Docs/QtQuick_Migration/10_Widget_Family_Port_Decomposition.md`.

Its purpose is narrow: preserve the **authored analogue Clock shadow personality** while the unrelated
`shadowtuning.json` sidecar is retired, and decompose that personality far enough that the F1 agent does
not flatten it into a generic card/text shadow.

---

# 1. F0.5 protection rule

F0.5 removes the hidden `shadowtuning.json` / `core.settings.shadow_tuning` authority and shadow
branches whose behavior exists only because of that sidecar.

That permission does **not** authorize deletion or simplification of family-authored visual behavior
that is still the reference for a not-yet-ported family.

In particular, before F1 is independently GREEN, preserve the current Clock analogue reference logic
for:

- face/ring shadow;
- hour-marker shadow;
- Roman-numeral shadow;
- hour/minute/second-hand shadow;
- `analog_face_shadow` behavior and setting semantics.

Those are not merely `shadowtuning.json` compatibility debris. They are bespoke Clock presentation
behavior that took substantial tuning and must remain inspectable until the retained Clock replacement
has proven the intended look.

F0.5 may remove the Clock's dependency on sidecar-driven **card/frame** shadow tuning. The analogue
Clock's ordinary outer/background card is destination `OverlayCard` behavior and does not justify
preserving the old painted-frame sidecar.

Do not delete the analogue face/numeral/hand reference merely because the half-migrated QWidget Clock
would no longer be a supported product surface.

---

# 2. Shadow classes inside analogue Clock

Do not treat “analogue Clock shadow” as one generic effect.

The current visual is composed from several different retained concepts:

```text
ordinary widget card shadow
    +
analogue face/ring + marker shadow
    +
Roman numeral shadow
    +
dynamic hand shadows
    +
ordinary footer/calendar/timezone text shadows
```

The destination should preserve that separation.

## 2.1 Outer/background card

When the Clock has a background/card, its destination shadow is the normal shared:

```text
OverlayCard
    -> RectangularShadow
```

It uses the canonical Widget/Card user bucket:

- enabled;
- Darkness / `frame_opacity`;
- Blur / `blur_radius`;
- Extra Offset / `frame_extra_offset`;
- global direction.

Do not reproduce the old painted-frame shadow cache or `PAINTED_FRAME_SHADOW_TUNING`.

## 2.2 Face ring and hour markers

The current analogue face shadow is a **hard duplicate geometry pass**, not a blurred generic drop
shadow.

Current source behavior to use as visual/reference evidence:

- the face shadow is gated by `analog_face_shadow`;
- the visible ring is an outlined ellipse;
- the 12 hour markers are line geometry;
- shadow geometry is drawn beneath both as widened/stroked paths;
- the shadow ring and marker paths are translated together by a drop offset;
- current reference drop offset is `3` logical pixels toward the legacy SE direction;
- current shadow ring stroke uses approximately
  `max(4.4, radius * 0.0462)`;
- current shadow marker stroke uses approximately
  `max(2.2, radius * 0.01584)`;
- the visible ring itself is approximately
  `max(2, radius * 0.032)`;
- the visible marker width is approximately
  `max(2, radius / 60)`;
- the static-face shadow uses a deliberately strong opacity relationship
  (`shadow_scale ~= 1.8`, legacy opacity scaling ~= 3.0);
- there is no authored blur pass.

These numbers are the starting reference for fidelity, not permission to build a new persistent tuning
table. If Qt Quick geometry/stroke rasterization differs, tune against the current appearance rather than
copying painter implementation mechanics blindly.

Destination shape:

```text
retained ring shadow geometry
retained marker shadow geometry
    below
retained visible ring/markers
```

The entire static face tree remains retained between ticks.

## 2.3 Roman numerals — preserve the unusual two-stage shadow

The numerals are the most important non-generic shadow behavior.

Current source does **two hard shadow glyph passes** before the visible numeral:

1. a main dropped numeral shadow;
2. a close/contact shadow at approximately `(1, 1)`;
3. then the visible Roman numeral.

Current source reference:

- main numeral shadow is deliberately strong;
- the main drop is approximately `2` logical px without a card/background and `3` with it;
- the close/contact pass is offset approximately `1` logical px;
- the close/contact pass is approximately `84%` of the main shadow alpha;
- no blur/MultiEffect is involved.

Do not flatten this into one generic `ShadowedText` pass merely because ordinary text uses one pass.

Preferred retained destination:

```text
Numeral item
    -> contact-shadow Text
    -> main-drop-shadow Text
    -> visible Text
```

or an equivalent retained structure with the same visual responsibilities.

The twelve numerals are static presentation items. Do not recreate them every second.

### Numeral relationship to global shadow controls

Roman numerals are textual glyphs, but their shadow is part of the authored **analogue-face personality**
and currently follows the per-Clock `analog_face_shadow` feature rather than the ordinary footer-label
shadow path.

Mandatory:

- global shadow direction controls orientation;
- `analog_face_shadow` remains the family gate;
- the two-pass numeral shape/baseline relationship remains family presentation policy;
- no separate “Analogue Numeral Darkness” user panel is introduced.

The optional General Text Darkness/Extra Offset controls do **not** have to be forced onto Roman numerals
if doing so weakens the painstaking authored face look or creates awkward cross-class semantics. F1 may
apply them as bounded modifiers only if eyes-on fidelity remains good and the mapping stays simple. If
that does not hold, leave numeral strength/distance family-authored and use only the mandatory global
direction. The optional controls were never permission to flatten the special analogue system.

The close/contact pass remains close to the glyph and must never become another freely drifting user
magnitude authority.

## 2.4 Dynamic hand shadows

Hour/minute/second hands use their own hard geometry shadow.

Current source reference:

- gated by `analog_face_shadow`;
- each hand shadow is a duplicate line beneath the visible hand;
- the shadow line has a thicker stroke than the visible hand;
- current dynamic shadow width scale is approximately `1.5x`;
- current legacy hand offset resolves to approximately `4` logical px toward SE;
- caps and joins are rounded;
- hand shadow opacity is deliberately strong (`legacy opacity scale ~= 2.0`);
- no blur is authored.

Destination:

```text
hand shadow line
    + same rotation/anchor as hand
    + signed global-direction translation

visible hand line
    + same authored rotation/anchor
```

The shadow and its hand must rotate from the same angle state in the same retained item tree. One
one-second model update changes rotation; it does not rebuild the line objects.

The optional General Text/Card tuning controls do **not** need to grow a third “face geometry” tuning
bucket merely for ring/markers/hands. Their internal baseline remains Clock-family presentation policy.
Do not force Card Blur/Darkness or Text Darkness/Extra Offset onto these special hard-geometry shadows
unless a simple modifier survives eyes-on fidelity. The mandatory global direction applies to them.

## 2.5 Footer / day / date / timezone

Do **not** apply the analogue face-shadow recipe to ordinary footer text.

Destination calendar/day/date and timezone use the same ordinary retained Text shadow style, as already
required by the F1 family decomposition:

- same ordinary Text user bucket;
- same global direction;
- same ordinary base magnitude;
- no separate day/date offset;
- no text blur;
- timezone is the visual reference for day/date.

The separator is a normal retained separator, not part of the analogue face-shadow geometry.

---

# 3. Global direction applies to every directional analogue shadow

The product-level 8-way direction is mandatory for all directional shadows.

For the analogue face classes, replace the legacy fixed positive-SE translation with:

```text
family baseline magnitude
    + applicable user Extra Offset
    -> canonical Python ShadowDirection resolver
    -> signed x/y translation
```

Axis-only directions zero the perpendicular component.

Examples:

```text
ring/markers baseline 3:
    E  -> (+3, 0)
    N  -> (0, -3)
    NW -> (-3, -3)

hand baseline ~4:
    E  -> (+4, 0)
    N  -> (0, -4)
    NW -> (-4, -4)
```

Do not parse direction in QML and do not build a second analogue-only direction mapping.

A direction change updates retained translations in place. It does not rebuild:

- Clock presentation model;
- Clock QML component;
- numerals;
- ring/markers;
- ticker;
- Quick engine;
- top-level window.

---

# 4. `analog_face_shadow` remains a real Clock feature

The current Settings control:

```text
Analogue Face Shadow
widgets.clock*.analog_face_shadow
```

is not an old “Intense Shadow” compatibility mode.

Preserve it through F1 unless exact product instruction changes it.

It controls the analogue-specific face presentation:

- ring/marker shadow;
- numeral analogue shadow personality;
- hand shadows.

It does not become another global shadow profile and does not override the mandatory global direction.

Clock/Clock2/Clock3 retain independent `analog_face_shadow` values as ordinary per-instance settings.

---

# 5. Retained implementation guidance

Prefer ordinary retained Qt Quick geometry/items.

Static:

```text
ring
markers
Roman numerals
their shadow geometry
separator
calendar/day/date
timezone
```

Dynamic once per authored second:

```text
hour hand rotation
minute hand rotation
second hand rotation
time-derived text state
```

Do not recreate the static face tree each physical frame or each second.

Do not recreate the old QPixmap face/frame buffer simply to mimic QWidget.

Do not introduce:

- `MultiEffect` for the hard face/numeral/hand shadows;
- `layer.enabled` merely to obtain these shadows;
- per-tick offscreen capture;
- painter pixmap shadow caches;
- dummy/effect-carrier Items;
- a second shadow timer/fade.

If a normal retained Shape/Text/geometry implementation can reproduce the authored result, prefer it.
A custom render node for an ordinary one-second Clock requires proof of a real fidelity/performance need.

---

# 6. F1 proof bar for analogue shadows

Structural/unit gates should prove at minimum:

- `analog_face_shadow` survives the presentation model/settings path;
- card shadow uses shared `OverlayCard`, not old sidecar/painter machinery;
- ring/marker shadow geometry is retained and has a separate shadow pass;
- numerals retain two shadow passes plus visible glyph;
- numeral contact shadow remains a close pass rather than another user-controlled offset authority;
- hand shadows use duplicate geometry with the same hand rotation and a larger stroke;
- no analogue face/numeral/hand blur effect is introduced;
- no MultiEffect/layer capture is introduced solely for these shadows;
- static face/numeral item identity survives repeated one-second ticks;
- changing global shadow direction mutates all directional analogue shadow translations in place;
- if F1 elects to apply General Text modifiers to Roman numerals, those modifiers update retained
  numeral shadow projection without reconstructing the Clock; otherwise the documented family-authored
  numeral baseline remains intentional;
- ordinary day/date/timezone still use the ordinary Text shadow path;
- `analog_face_shadow=false` suppresses analogue-specific face/numeral/hand shadows without changing
  Clock mode/geometry/ticker ownership.

Eyes-on comparison must include:

```text
Analogue:
- background/card ON
- background/card OFF
- numerals ON
- numerals OFF
- analogue face shadow ON/OFF
- seconds hand ON/OFF
- day/date + timezone
- separator ON where calendar exists
- SE, NW, N and E global directions
- bright/simple photo background
- busy/high-contrast photo background
- multiple Clock sizes / DPRs
```

The acceptance question is not “does Qt Quick draw a shadow?” It is whether the migrated Clock retains
the current analogue depth/readability/personality without reintroducing the old painter/effect
architecture.

---

# 7. Reference-retirement timing

Keep the pre-F1 Clock presentation source available while implementing and auditing F1.

After the retained Clock family has:

1. extracted/reused all surviving presentation-neutral Clock logic;
2. documented any intentionally changed visuals;
3. passed focused behavioral tests;
4. passed required analogue/digital eyes-on parity;
5. passed independent F1 audit;

the old Clock pixel implementation no longer needs to remain live merely as a fallback. Git history
remains the historical source after that point.

The global migration cleanup timing for per-family old presenters should be reconciled in
`Current_Plan.md` / `Future_Cleanup.md` at the next cohesive phase-doc closure rather than inventing a
Clock-only exception here.
