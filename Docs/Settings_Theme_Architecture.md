# Settings Theme Architecture

Last updated: 2026-08-28

Durable contract for the QWidget Settings theme system, native backdrop ownership and theme authoring. This document owns the current Settings-theme architecture. Historical investigation belongs under `Docs/Historical_Bugs/`; temporary theme migration notes do not override this contract.

## Product boundary

Settings remains a frameless QWidget/QDialog surface. The top-level Settings widget uses `WA_TranslucentBackground`; on Windows Qt presents that top-level as a layered HWND. Theme implementation must therefore preserve the composition contract that has been physically validated on this actual window architecture.

The theme stack is deliberately split by responsibility:

```text
SettingsThemeSpec / .srtheme
    -> semantic visual request

ui/settings_theme_runtime.py
    -> one active immutable theme + synchronous live notification

ui/settings_theme.py + component QSS/renderers
    -> Qt semantic surfaces, colours, alpha, geometry-preserving selector rendering

ui/settings_dialog.py
    -> shell lifecycle, forged edge/corner renderer, native-mode transition ownership

core/windows/dwm_blur.py
    -> Windows AccentPolicy mechanics only
```

No renderer may invent a second palette because a particular native material is inconvenient.

## Schema-v5 contract

`ui/settings_theme_spec.py` owns the compiled `DEFAULT_DARK_SETTINGS_THEME` and schema-v5 semantic vocabulary.

A complete `.srtheme` owns:

- `backdrop.mode`: `off`, `acrylic` or `glass`;
- `backdrop.tint`: native Acrylic tint payload; retained in the schema for all modes, but Glass does not use it as a native tint;
- the complete semantic colour-role map;
- the complete semantic Settings shadow-role map;
- the complete semantic gradient-role map.

`ui/settings_theme_io.py` admits a file whole or rejects it whole. Unknown/missing roles, wrong format/schema or invalid values do not partially merge into a theme. Compiled Default Dark remains the unconditional no-file/failure fallback.

The persisted theme selection is resolved and validated before first Settings construction. Persistence must never deliberately flash Default Dark before a valid saved custom theme.

## Proven Windows backdrop mapping

Both translucent native materials use `SetWindowCompositionAttribute` / `WCA_ACCENT_POLICY`. This is intentional: both remain in the same composition family that physically works with the layered Qt Settings HWND.

```text
Off
    -> ACCENT_DISABLED (state 0)

Acrylic
    -> ACCENT_ENABLE_ACRYLICBLURBEHIND (state 4)
    -> theme backdrop.tint is the native tint/strength

Glass
    -> ACCENT_ENABLE_BLURBEHIND (state 3)
    -> fresh zeroed AccentPolicy; no native GradientColor/tint
    -> semantic Qt RGBA surfaces own visible Glass colour and opacity
```

`ACCENT_ENABLE_BLURBEHIND` is the undocumented AccentPolicy state used through `SetWindowCompositionAttribute`. It is **not** the documented `DwmEnableBlurBehindWindow` API. Windows documentation about the latter must not be used to declare AccentPolicy state 3 equivalent, obsolete or unsupported.

### Glass visual ownership

Glass is intentionally untinted at the native layer. A Glass theme obtains its appearance from the semantic Qt layers painted over state-3 blur:

- `window.dialog_glass` controls the outer semantic surface;
- title bar, sidebar, navigation, panels, lists, buttons and other role alpha values compose above it;
- different Glass themes may therefore differ materially in RGB and opacity without changing the native primitive.

Do not make Glass opacity by inventing a hidden native tint or by changing the native primitive per Glass theme.

## Native transition ownership

The native mode is stateful but simple. Avoid compositor churn.

- Glass -> Glass: native no-op; only semantic Qt surfaces refresh.
- Acrylic -> Acrylic: reapply state 4 only when its native tint changes.
- Acrylic <-> Glass: replace the AccentPolicy state directly; do not tear the shared mechanism down first unless a proven platform requirement appears.
- Any material -> Off: state 0 disables the AccentPolicy backdrop.
- Off -> material: install the requested state once.

No post-show retries, zero-delay timers, stylesheet replay, event-loop pumping or repeated native calls are part of this contract.

## Rejected backdrop architectures for the current Settings HWND

The following were investigated and are **not** current implementation options:

- `DWMWA_SYSTEMBACKDROP_TYPE` / `DWMSBT_TRANSIENTWINDOW` as Settings Glass;
- `DWMWA_REDIRECTIONBITMAP_ALPHA` as a bridge between Qt alpha and the Glass backdrop;
- a QWindow Expose callback/reassertion;
- a post-show native retry;
- native-then-QSS replay ordering;
- near-clear state-4 Acrylic as a fake Glass underlay.

The system-backdrop path accepted DWM writes/readbacks but failed to compose reliably on first startup. The near-clear state-4 experiment produced an opaque black Settings surface. The physically accepted solution is state-3 Glass on the same AccentPolicy family as Acrylic.

A future move to DWM system backdrops is an **architecture change**, not a theme tweak. It requires a deliberate non-layered/native-host presentation design and fresh physical proof before this contract changes.

## Semantic QSS ownership

`ui/settings_theme_qss.py` is the central colour serializer. Opaque semantic values may render as compact hex; translucent values must retain integer 0-255 alpha in Qt `rgba(...)` syntax.

`ui/settings_theme.py`, `ui/tabs/shared_styles.py` and component renderers own selector/geometry application while ThemeSpec owns visual values. Typography, spacing, radii, dimensions and behavior stay renderer-owned unless deliberately promoted into the schema.

The forged Settings outer edge/corner remains renderer-owned in `ui/settings_dialog.py`. Its geometry is fragile and is **not** theme data. Camouflage colour follows the adjacent semantic shell surface; do not independently theme it.

Settings shadows remain under `ui/widgets/control_shadow.py`; ThemeSpec supplies their semantic visual parameters. Runtime screensaver widget shadow authority is separate.

## `dark.qss` status

`themes/dark.qss` is legacy stylesheet debris, not theme authority. It currently remains a base stylesheet dependency and must be removed only through the audited retirement recorded in `Future_Cleanup.md`.

Do not delete it casually and do not preserve it by copying its old colours back into Python. Retirement means:

1. enumerate every live loader and selector actually depended upon;
2. classify surviving rules into structural/geometry/resource behavior versus obsolete visual literals;
3. relocate only required structural behavior to the permanent renderer/component that owns it;
4. keep colour/opacity/shadow authority in ThemeSpec;
5. prove Settings and the tray/menu consumers with the file physically absent;
6. then delete the loader dependency and file together.

Native backdrop code and forged edge geometry are outside that cleanup unless an independently proven defect requires change.

## Theme Foundry authoring contract

Theme Foundry must consume the current `SettingsThemeSpec` and `ui.settings_theme_io` APIs directly. It may not maintain a private old schema.

Required backdrop authoring semantics:

- expose `Off`, `Acrylic` and `Glass` as supported schema-v5 modes;
- Acrylic tint controls are meaningful only for Acrylic and Acrylic alpha must remain non-zero;
- Glass must be described as untinted AccentPolicy state-3 blur whose visible colour/opacity comes from semantic Qt surfaces;
- Glass must never be authored as a pale/clear Acrylic recipe;
- unavailable Mica/system-backdrop experiments are not selectable theme modes;
- save only complete themes that strict runtime loading can round-trip.

Foundry previews are authoring aids, not runtime authorities. The actual Settings window remains the final visual oracle for layered composition.

## Change guardrail

For any future Settings visual/backdrop change:

```text
inspect exact current source
-> identify semantic owner vs renderer/native mechanism
-> make one bounded ownership change
-> strict theme round-trip/focused tests
-> physical Default Dark + Acrylic + Glass smoke
-> update this contract only when the proven architecture changes
```

Do not fix a native-material problem by perturbing stylesheet order, and do not fix a QSS-role problem by changing the native compositor.
