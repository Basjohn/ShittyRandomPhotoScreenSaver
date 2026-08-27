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

This layer intentionally does **not** guess a frozen executable path. Settings accepts an explicit `themes_directory` from startup/build authority, and resolves the persisted theme before Settings widgets are constructed. Build/Codex/Claude work can choose the correct packaged-directory policy beside the build scripts. Do not add `cwd()`, hard-coded Program Files paths, `_MEIPASS` guesses or source-tree assumptions to semantic theme modules.

## Existing `/themes` files

- `Default Dark.srtheme` — canonical semantic mirror of compiled fallback.
- `dark.qss` — leave untouched until caller/reference audit proves whether it is obsolete. The `.srtheme` catalogue ignores `.qss` files.
- `Dark More Cohesive.srtheme` — removed legacy Theme Foundry source-scanner output.

## Current checkpoint state

- Themes sidebar surface exists with two pills: **Setting Themes** and
  **Widget Themes**.
- Setting Themes is the landing page; Widget Themes is intentionally empty.
- Both theme pills now have authored minimum width and the catalogue list text
  is enlarged for readability without overriding semantic list colours.
- The previously deferred live rendered-style consumers in `widgets_tab.py`
  and `widgets_tab_steam.py` are migrated.
- Whole-UI frozen rendered-style scan now leaves only
  `ui/tabs/presets_tab.py`, disconnected legacy debris already logged for
  deletion. It is not a live migration target.

## Current palette-audit state

- `.srtheme` schema is now **v3** because newly centralized Settings chrome
  roles are required members of a complete theme.
- Sources ratio/RSS/action chrome, Transitions pills/actions, Widgets
  pills/actions, General cache/shadow-direction controls and Spectrum/DevCurve
  selector pills now consume live semantic roles rather than local colour
  literals.
- Status colours and user/widget-authored colours deliberately remain outside
  Settings ThemeSpec; semantic product data is not Settings skin.
- `Theme Plumbing Test - Obnoxious.srtheme` is a deliberately fluorescent
  validation theme for eyes-on live switching. It is test data, not a proposed
  product theme.

## Immediate remaining work

1. Wire packaged themes directory from real startup/build authority so file
   themes are resolved before first Settings widget construction.
2. Perform Windows eyes-on live switching between Default Dark and the
   obnoxious test theme, especially forged corners/acrylic/nav/shadows.
3. Finish the smaller remaining literal Settings-chrome audit (not semantic
   status/user-content colours), including special popup/Steam surfaces where
   appropriate.
4. Rewrite Theme Foundry to edit/save semantic schema-v3 `.srtheme` files.
5. Remove the test theme and this temporary plan after validation/durable docs.
