CODEX IGNORE THIS DOCUMENT UNLESS TOLD OTHERWISE

# Theme Plan For Now

Temporary working authority for the Settings GUI theme migration. Retire this file once the Themes surface, packaged-theme path and Theme Foundry have landed and durable project documentation owns the remaining rules.

## Non-negotiable safety

- `DEFAULT_DARK_SETTINGS_THEME` is the compiled worst-case fallback and must render the complete Settings GUI with no theme files.
- `themes/Default Dark.srtheme` is a canonical mirror/template, not bootstrap authority. Missing/corrupt/deleted theme files never remove the current Default Dark appearance.
- Resolve and fully validate a persisted custom selection before changing the active runtime ThemeSpec. Never deliberately activate Default Dark and then immediately activate the custom theme.
- A `.srtheme` is admitted whole or rejected whole. Missing/unknown roles, wrong schema/format and invalid visual data fail closed to compiled Default Dark.
- Renderer application is transactional. Persist user selection only after live activation succeeds.
- Do not move/rewrite forged acrylic edge/corner geometry as part of theme work.

## Current architecture

- `ui/settings_theme_spec.py` — semantic ThemeSpec + compiled fallback.
- `ui/settings_theme_runtime.py` — active ThemeSpec + transactional live refresh.
- `ui/settings_theme_io.py` — strict semantic `.srtheme` I/O, safe fallback, atomic writer.
- `ui/settings_theme_catalog.py` — validated catalogue, portable selection id, resolve-before-single-activation startup helper.
- `ui/settings_theme.py` — QWidget/QSS root renderer.
- `ui/tabs/shared_styles.py` — shared semantic QWidget styles/bindings.
- `ui/widgets/control_shadow.py` — semantic shadow renderer.
- `core/windows/dwm_blur.py` — native Windows acrylic mechanics.

## Themes UI surface

Sidebar order: `Sources / Display / Transitions / Widgets / Accessibility / Themes / About`.

Themes has two internal pills:

1. **Setting Themes** — landing page; validated Settings-theme catalogue and immediate live selection.
2. **Widget Themes** — intentionally empty for now. Widget families already have mature custom-colour systems; reusable Widget Themes are later product work.

The new pill style is ThemeSpec-backed/live. Existing Widgets/Transitions pills can be unified later when overlapping migration work is clear.

## Selection persistence

- Built-in id: `builtin:default-dark`.
- File id: `file:<basename>.srtheme`.
- Persist no absolute installation path.
- Missing custom files fall back to compiled Default Dark without erasing the saved choice.
- Persist only after runtime activation succeeds.

## Packaged / frozen themes directory

`ui/settings_theme_paths.py` is a deliberately temporary test seam. Resolution order is:

1. explicit `themes_directory` from the caller;
2. nonblank `THEMES_DIRECTORY_BUILD_REPLACE_BLANK`;
3. repository-local `themes/` for source/dev testing.

Settings resolves that directory and the persisted theme **before** constructing its first QWidget. The
repository fallback is not the final frozen-build contract; build/release work must replace/wire the stub
and the cleanup ledger tracks removing the temporary seam afterward. Missing external files still resolve
to compiled Default Dark rather than an unstyled window.

## Existing `/themes` files

- `Default Dark.srtheme` — canonical semantic mirror of compiled fallback.
- `dark.qss` — leave untouched until caller/reference audit proves whether it is obsolete. The `.srtheme` catalogue ignores `.qss` files.
- `Dark More Cohesive.srtheme` — removed legacy Theme Foundry source-scanner output.

## Current checkpoint state

- Themes sidebar surface exists with **Setting Themes** and intentionally-empty
  **Widget Themes**.
- Source/dev builds can discover file themes through the temporary explicit /
  build-stub / repository-local path seam before first Settings QWidget paint.
- Theme schema **v4** adds the remaining bucket open/closed palette and popup
  form-input palette.
- Sources uses the established circular Save RSS checkbox and central
  `StyledPopup` for duplicate, autocorrect and RSS-cache notices/questions.
- The no-sources close guard uses `StyledPopup`; the bespoke popup/shadow is
  gone. The legacy ResetDefaults toast API is retained but its visuals now use
  the popup semantic palette/shadow rather than another hardcoded skin.
- Settings More/Import menus use semantic `context.menu.*` roles.
- Styled combo/font-combo popup views bind to the live
  `COMBOBOX_POPUP_VIEW_STYLE` rather than freezing construction-time colours.
- Tooltips are consistent: both root and local tooltip QSS consume the same
  alpha-aware ThemeSpec roles and preserve the old global geometry.
- Bucket closed/open surfaces are ThemeSpec-owned while existing geometry,
  arrows and semantic bucket-shadow renderer stay unchanged.
- The Steam API-key input dialog keeps its form mechanics but uses the same
  popup container/input/button/shadow vocabulary as `StyledPopup`.
- The non-native wrapped Qt colour picker already consumes semantic
  `color_picker.*` roles and is now exercised by the full-role validation theme.
- The validation theme changes every semantic colour role, every shadow role
  and every gradient role so apparently-unaffected UI is meaningful evidence.

## Immediate remaining work

1. Windows eyes-on live-switch audit with schema-v4 Obnoxious: bucket closed/open,
   About `⋮`, Sources popups/Save RSS, combo dropdowns, tooltips, More/Import
   menus, Steam API-key form and colour picker.
2. Fix any remaining stubborn Settings chrome revealed by that full-role test;
   leave semantic status and user/widget-authored colours alone.
3. Rewrite Theme Foundry around the semantic schema-v4 `.srtheme` model.
4. Build/release work replaces the temporary theme-directory stub and retires
   the dev fallback as already recorded in `Future_Cleanup.md`.
5. Keep `dark.qss` until its remaining geometry/resource/base-selector ownership
   is deliberately retired or relocated; it is not selectable theme authority.
6. Remove the validation theme and this temporary plan after final validation.
