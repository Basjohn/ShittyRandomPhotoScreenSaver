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
- Source/dev builds discover file themes through the temporary explicit /
  build-stub / repository-local path seam before first Settings QWidget paint.
- Theme schema **v4** owns the current semantic Settings visual vocabulary.
- Full-role Obnoxious Windows testing has exercised bucket states, tooltips,
  popup/dialog language, combo popup views, menus, About controls and the
  custom non-native Qt colour picker.
- The picker wrapper now explicitly fills its owned content frame from
  `color_picker.window`; QColorDialog's actual colour wells/sliders/preview
  remain Qt-owned and truthful to the selected colour.
- The frameless picker wrapper permits transparent outer corners so the
  existing rounded title/content frames can define the visible shell.
- Themes navigation now uses a dedicated `_ThemePillButton` whose own
  `sizeHint()` / `minimumSizeHint()` reserve the full rendered label plus
  generous padding. FlowLayout therefore receives the correct width directly.

## Immediate remaining work

1. One final Windows eyes-on check that picker OK/Cancel casts now clear the
   actual QDialogButtonBox clip boundary; close-X alignment is already green.
2. Rewrite Theme Foundry around semantic schema-v4 `.srtheme` files.
3. Build/release work replaces the temporary theme-directory stub and retires
   the dev fallback as recorded in `Future_Cleanup.md`.
4. Keep `dark.qss` until remaining geometry/resource/base-selector ownership is
   deliberately retired or relocated; it is not selectable theme authority.
5. Remove the validation theme and this temporary plan after final validation.
