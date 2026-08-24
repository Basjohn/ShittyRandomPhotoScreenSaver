# Custom Style Implementation

Last updated: 2026-08-24

Guidance for SRPSS Settings UI and runtime visual styling during the Qt Quick migration.

## 1. Goals

- preserve SRPSS custom chrome and dark settings language;
- preserve runtime customization unless the migration explicitly retires a presentation-era control;
- keep shared style decisions in shared owners;
- fix focus/startup/visibility/render bugs at their owner rather than deleting visuals;
- distinguish QWidget Settings styling from runtime-pixel styling that is migrating to Quick.

## 2. Settings UI sources — PRESERVE

Settings remains QWidget-based unless a separate product decision changes that.

Current Settings style sources remain:

- `ui/settings_dialog.py`
- `ui/settings_theme.py`
- `ui/tabs/shared_styles.py`
- `ui/styled_popup.py`
- `ui/widgets/`

These are **LANDED / PRESERVE** for Settings UI. Do not rewrite them merely because runtime
presentation migrates to Quick.

## 3. Runtime presentation architecture

Runtime widget pixels migrate to the display's retained Qt Quick scene.

Read:

- `Current_Plan.md`
- `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- `Docs/Contracts.md`

Keep provider/model/settings authority in Python.

### 3.1 Current-legacy runtime style owners

The following may still have real callers while their replacement owner is unproven, but are
**CURRENT-LEGACY — WILL BE OBSOLETE / REHOMED during F/G/H as their owner lands**:

- `BaseOverlayWidget` runtime card/pixel ownership;
- QWidget/QPainter runtime card drawing;
- painted-frame/shadow caches used only by runtime widgets;
- QWidget runtime `QGraphicsEffect` opacity/shadow machinery;
- old compositor/overlay fade/style application that exists only for the pre-Quick presenter.

Do not expand those paths because they still run today. Preserve the **visual/style contract** while it
is still needed as migration evidence, move that contract to retained Quick owners, then delete the
caller-proven old pixel machinery promptly after the replacement family/owner is independently GREEN.
Do not carry completed family presenters to I merely as a fallback.

Transient QWidget control styling for Settings/context controls is not automatically obsolete merely
because a similarly named runtime helper is.

## 4. Runtime style contract — PRESERVE / REHOME

Quick runtime must preserve, as applicable:

- font family/size;
- text color/opacity;
- background show/color/opacity;
- border width/color/opacity;
- corner radius;
- margin/padding;
- card shadows;
- text/header shadows;
- per-widget/global opacity/fade;
- artwork/progress/special family styling;
- one global eight-direction shadow orientation in General, defaulting to SE.

The direction setting rotates each shadow type's existing authored magnitude rather than replacing its
blur/spread/opacity/color or forcing every shadow to the same offset.

Do not remove a user-facing visual control merely because its QWidget implementation disappears,
unless `Current_Plan.md` explicitly retires that **control/behavior itself**. The known exception is
presentation-era state deliberately retired by the migration, such as the old per-mode visualizer
card-height/growth controls.

### 4.1 Widgets → General shadow controls — REQUIRED F0.5 UI

E4 landed canonical shadow direction/settings authority but intentionally did not add the complete
user-facing editor. F0.5 completes it in the existing **Widgets → General → Appearance** section.
Settings remains QWidget. This is not a runtime-family/QML slice.

The existing General page already owns:

- Enable Widget Drop Shadows;
- Enable Text Shadows;
- Enable Widget Header Drop Shadows.

Keep those controls and place the new controls beside them as one coherent Shadow group.

#### Direction — mandatory

Use a compact custom-styled 3×3 arrow picker:

```text
┌─────────────┐
│ ↖   ↑   ↗  │
│ ←       →  │
│ ↙   ↓   ↘  │
└─────────────┘
```

The eight cells map to `NW/N/NE/W/E/SW/S/SE`. The center cell is empty/inert. There is no ninth
`center`, `none`, `automatic` or zero-offset direction. Fresh/Reset-to-Defaults selects `SE`; malformed
persisted input displays the canonical E4 fallback `SE`.

Style/UX:

- match existing SRPSS dark custom Settings chrome and spacing;
- arrows/icons are primary, not raw token text;
- selected state is visible without focus; normal hover/pressed/focus states remain clear;
- expose tooltip/accessibility names (`North West`, `North`, etc.);
- remain compact enough to live naturally in General → Appearance.

#### Widget / Card Shadows

```text
Enable Widget Drop Shadows
Darkness
Blur
Extra Offset
Enable Widget Header Drop Shadows
```

Canonical settings:

- `enabled` — existing toggle;
- `frame_opacity` — user-facing **Darkness** (0–100% UI mapped to normalized opacity);
- `blur_radius` — user-facing **Blur**, bounded logical-pixel value;
- `frame_extra_offset` — new non-negative logical-pixel scalar, default `0`;
- `header_enabled` — existing header-shadow toggle.

Card blur affects the retained card/drop shadow only. A later retained-family style update changes the
existing `RectangularShadow` property and lets Qt invalidate its cache naturally; it does not create a
second cache/effect carrier.

#### Text Shadows

```text
Enable Text Shadows
Darkness
Extra Offset
```

Canonical settings:

- `text_enabled` — existing toggle;
- `text_opacity` — user-facing **Darkness** (0–100% UI mapped to normalized opacity);
- `text_extra_offset` — new non-negative logical-pixel scalar, default `0`.

**There is no Text Blur control or text-blur destination property.** Ordinary, large and header text
shadows stay duplicate retained glyphs and share the same Text enable/darkness/extra-offset user bucket.
Do not preserve the old sidecar's separate header alpha as a hidden third tuning system. If very large
text later needs deterministic distance scaling for legibility, that belongs to the destination style
policy and remains subordinate to the same Text controls.

#### Extra Offset semantics

Extra Offset augments the authored/class baseline before E4 direction resolution:

```text
authored/base magnitude + user Extra Offset
        ↓
canonical ShadowDirection resolver
        ↓
signed X/Y retained properties
```

E/W activate X, N/S activate Y, diagonals add the scalar to both authored axes before signs are applied.
Extra Offset is non-negative; direction owns orientation. Do not create signed offset sliders.

The old `widgets.shadows.offset` pair is retired and removed in F0.5. It is not the E4 magnitude
authority and must not be migrated into either Extra Offset field.

#### No Intense mode

Do not restore an `Intense Shadow` toggle/profile. `intense_shadow`, `analog_shadow_intense` and
`digital_shadow_intense` are already retired settings keys.

The old painter sidecar `shadowtuning.json` is deleted from current authority in F0.5 together with
`core/settings/shadow_tuning.py` and its path/profile tests. Do not copy its `blur_steps`, spread/pass
counts, card-shrink values, alpha tables or font-scaling values into another module or into Quick UI
units. There is no compatibility/fallback tuning source. **Sidecar-driven** QWidget shadow parity is
allowed to disappear rather than earning temporary parity work.

Do not interpret that as permission to erase family-authored shadow reference behavior before its port.
Clock's bespoke analogue ring/marker, two-pass numeral and hand shadows remain reference authority until
F1 is GREEN; see `Docs/QtQuick_Migration/11_Clock_Analogue_Shadow_Contract.md`.

The destination has one normal shadow system with canonical settings plus these direct controls. F1 Clock
establishes the first deliberate Quick card/text baseline magnitudes; later families reuse the destination
style policy rather than reading historical painter numbers.

#### Settings authority / save safety

- read/write the existing canonical `widgets.shadows` mapping;
- reuse E4 direction vocabulary/resolver; no UI-local direction semantics;
- extend and normalize `ShadowSettings` rather than creating a second shadow settings/model owner;
- remove the unused legacy `offset` pair and make model missing-key fallbacks agree with canonical
  defaults (`blur_radius=18`, `frame_opacity=0.77`, `text_opacity=0.33`, direction `SE`, extras `0`);
- do not expose `SettingsManager` to runtime QML or poke retained QML items directly from the picker;
- no per-family shadow editor in F0.5;
- preserve normal Settings apply/save/recreate/update ownership.

**Mandatory bug fix:** the current General save helper builds a partial `shadows` dictionary with only
the enable booleans, and the section-save layer assigns that dictionary wholesale. F0.5 must merge into
the existing `widgets.shadows` mapping (or equivalent) so any General save preserves unedited direction,
color, opacity, blur, extra-offset and unknown future keys. Explicitly retired `offset` is removed by
canonical settings cleanup rather than preserved by the merge.

Focused F0.5 tests cover:

- complete deletion of `core/settings/shadow_tuning.py` / `tests/test_shadow_tuning_paths.py` and zero
  current-source sidecar/tuning-dictionary dependencies;
- no replacement compatibility tuning module/table/file;
- retirement of `widgets.shadows.offset` with no migration into Extra Offset;
- `ShadowSettings` fallback/default parity with canonical settings;
- all eight direction choices and inert center;
- selected/hover/pressed/focus/accessibility behavior where deterministic;
- canonical persistence/reload, default/reset `SE`, malformed-token fallback;
- card Darkness/Blur/Extra Offset and Text Darkness/Extra Offset round-trip/defaults/clamping;
- non-negative Extra Offset;
- **save-preservation:** changing Border Width or one shadow toggle cannot erase another shadow key;
- no Intense UI/keys and no text-blur setting/property/effect;
- generated defaults/SST parity after adding the two new scalar defaults;
- normal Widgets → General lazy-page/save behavior.

F0.5 does not port Clock or another runtime widget family.

## 5. Shadow history and Phase E4 destination

Historical multi-monitor shadow corruption involved QWidget `QGraphicsEffect`/effect-cache behaviour.

Relevant records:

- `Docs/Historical_Bugs/U-06_MC_Shadow_Cache_Corruption.md`
- `Docs/Historical_Bugs/R-24_Retired_Overlay_Effect_Cache_Busting.md`

Painter-owned shadows were a QWidget-era correction, not the final Quick implementation.

Qt Quick runtime must **not** reintroduce `QGraphicsDropShadowEffect`/broad QWidget effect-cache
ownership.

For the Quick runtime:

- use one canonical `ShadowDirection` (`NW/N/NE/W/E/SW/S/SE`) and signed-offset resolver;
- preserve each surface's authored shadow magnitude;
- reserve four-sided visual padding so top/left directions cannot clip;
- prefer retained bounded mathematical/shader card shadows for rounded cards;
- use bounded Quick effects only where an arbitrary-shaped source genuinely requires them;
- do not use broad focus/menu/display cache-busting;
- do not toggle effect topology to animate fade;
- stress multi-monitor focus/context/hide/recreate.

E4 owns the global direction authority. Old runtime shadow implementations remain only until their
family/presenter callers are removed.

## 6. Settings styling safety

Continue to avoid:

- broad visibility/focus recursion;
- constructing every settings section at startup;
- styling work that triggers provider/network activity;
- changing Settings chrome as a workaround for runtime rendering issues;
- coupling family activation to eager page construction.

## 7. Change process

Shared runtime style change:

1. identify the surviving style contract and current owner;
2. if the owner is current-legacy, update/rehome the destination owner rather than deepening it;
3. update affected retained Quick components;
4. update `Docs/TestSuite.md` when test ownership/retirement changes;
5. run shared style/shadow gallery tests;
6. run focused family tests;
7. check focus/context/Settings/CUSTOM;
8. commit + push the landed slice.

No visual-fidelity downgrade as a performance fix.
