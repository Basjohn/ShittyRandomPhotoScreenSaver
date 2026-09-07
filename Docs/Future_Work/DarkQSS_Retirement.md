# dark.qss Retirement — ThemeSpec becomes the sole Settings-dialog authority

Live checklist. Delete items as they land; this is not a changelog. Owner-linked
from `Current_Plan.md`.

## Why
`themes/dark.qss` (989 lines) is a **second styling authority** for the Qt Widgets
settings dialog, competing with `SettingsThemeSpec`. It is applied first and the
ThemeSpec-driven `_build_custom_styles` is merely appended:
`widget.setStyleSheet(dark_qss + custom_styles)` (`ui/settings_theme.py:463-467`).
Because the appended custom styles only cover the selectors they explicitly
target, dark.qss's hardcoded values win everywhere else. Two consequences:

- **Themes don't fully apply** — dark.qss hardcodes **~240 color declarations**;
  a non-dark/custom theme comes out partially dark wherever ThemeSpec's overrides
  don't reach (the "themes don't work properly" symptom).
- **Structure lives only in dark.qss** — it also owns geometry/borders/radii/
  spacing/typography for **89 selectors that ThemeSpec does not cover**, so a naive
  file deletion shifts layout, drops borders and loses shapes.

Goal: ThemeSpec/Themes provide **every** detail (colour **and** structure) so
`themes/dark.qss` can be deleted with **zero** dark-theme regression and full
theming everywhere.

## Ground-truth scope (measured 2026-09-07)
- dark.qss: 98 selectors; `_build_custom_styles` covers 34 → **89 dark-only
  selectors** to port (About dialog, subsettings dialog, every button —
  start/select/settings/about/action/QSmolselect/QBasicBitchButton/QComboArrow,
  QMenu, scrollbars, title bars, borders, ResizeIndicator, `*`, QMainWindow…).
- **47 distinct colour literals**. Against ThemeSpec's 189 dark tokens:
  **24 value-match an existing token**, **23 need a new token**
  (e.g. `#2B2B2B`, `#444444`, close-button red `#E81123`, error reds
  `#FF5757`/`#F1707A`, several white/black/grey alphas).
- **Alpha-format hazard:** dark.qss uses **float** alphas (`rgba(…,1.0)`,
  `rgba(…,0.8)`) while the ThemeSpec renderer emits **int** alphas and its own
  comment warns Qt truncates float alpha to 0. Normalising float→int (1.0→255,
  0.8→204) is visually identical and removes a latent truncation bug — do it as a
  standalone step so it can be eyeballed on its own.
- Regenerating the map: extract every colour literal from dark.qss, normalise
  float→int alpha, and reverse-match against `_DEFAULT_DARK_COLORS`
  (`ui/settings_theme_spec.py`) — value hit = candidate reuse, miss = new token.
  (Was prototyped as a throwaway read-only script; fold into a real tool only if
  Phase 1 wants it committed.)

## Safety net (the whole migration hangs on this)
A byte-identity guard: render the tokenised base with the **dark** theme's token
values and assert it equals the current (alpha-normalised) dark.qss. If identity
holds, the dark theme cannot regress; only non-dark themes change (which is the
point). This is the substitute for eyes-on verification we otherwise lack.

## Phase 0 — Foundation
- [ ] Normalise float alphas → int in `themes/dark.qss` (`rgba(r,g,b,1.0)`→`,255`;
  `,0.8`→`,204`; etc.). Standalone commit; visually a no-op; fixes the latent
  float-truncation bug. Eyeball the settings dialog once.
- [ ] Add a regression harness that renders a base with the dark token map and
  asserts byte-identity vs the alpha-normalised dark.qss (fails loudly on drift).

## Phase 1 — Token vocabulary (ThemeSpec owns every Settings colour)
- [ ] For the 24 value-matches, **semantic-review each** — reuse the existing token
  only when the roles truly move together; otherwise add a dedicated token
  (do NOT tie a button's black to `swatch.pressed_mix` just because the value
  matches). Record the final literal→token map.
- [ ] Add the ~23 new tokens to `_DEFAULT_DARK_COLORS` with dark values = the exact
  dark.qss colours. Name semantically (`window.close.hover` = `#E81123`,
  `feedback.error.text` = `#FF5757`, …); fall back to `settings.<role>` when a
  role is genuinely generic.
- [ ] Extend the theme schema/catalog/IO (`settings_theme_catalog.py`,
  `settings_theme_io.py`, `settings_theme_spec.py`) so a theme file can set every
  new token; a theme omitting one inherits the dark default.

## Phase 2 — Relocate structure into the renderer
- [ ] Move dark.qss's content into a Python-rendered base
  (`_build_base_structural_styles(theme)` in `ui/settings_theme.py` or a new
  `ui/settings_base_qss.py`), colours replaced by `%(token)s`, **all structure
  verbatim** (geometry/borders/radii/spacing/fonts unchanged).
- [ ] `_load_base_stylesheet()` returns the rendered base for the active theme
  instead of reading the file. Application order preserved
  (`base + _build_custom_styles`), or fold custom into the base.
- [ ] Byte-identity harness passes for the dark theme.

## Phase 3 — Delete the file + prove theming
- [ ] Delete `themes/dark.qss`.
- [ ] Dark theme: byte-identical (harness). Non-dark theme: spot-check the 89
  selectors re-colour fully with **no** bleed-through (About dialog, subsettings,
  every button family, QMenu, scrollbars, title bar, borders, ResizeIndicator).
- [ ] Installer: `scripts/*.iss` copy `themes/*` to `{commonappdata}\SRPSS\themes`
  — confirm removing dark.qss doesn't break a shipped-theme assumption; update the
  packaged theme set if needed. Remove `tools/flicker_test.py`'s dark.qss path.

## Phase 4 — Lock it
- [ ] Remove the `_load_base_stylesheet` file-read + fallback log.
- [ ] Add a guard (mirror `defaults_authority_audit`): **no hardcoded colour
  literals in the Settings base QSS** — every colour must be a ThemeSpec token, so
  a future edit can't reintroduce a shadow colour authority.

## Risks / watch-outs
- Gradients / multi-stop borders in dark.qss must tokenise per-stop.
- The 24 value-matches are hints, not truth — semantic review is mandatory.
- No eyes-on CI: byte-identity for dark is the guard; non-dark themes need a manual
  spot-check pass.
- `styled_popup.py` and `settings_theme_spec.py` already reference "legacy dark.qss"
  margins/geometry — grep for `dark.qss` after Phase 3 and retire stale comments.
