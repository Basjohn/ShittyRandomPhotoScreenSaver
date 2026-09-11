# SRPSS Foundry Suite Dark Glass / Chrome Polish Handoff — 2026-09-11

## Authority / merge safety

- The working authority for this slice is the already-applied GODZIP Foundry Dark Glass modernization on top of repo HEAD `95df65f279075645744f6fe8036aa4d6cdedc9c5` (`main`).
- The pre-edit `Current_Plan.md` base was byte/Git-blob identical to the repo copy (`81396b2777b576c8293421ba70d887dd99294158`) before the completed Foundry line was appended.
- `Docs/TestSuite.md` is restored exactly to current repo test truth (`63d7765f61a67cca1d38bc4ce1d24600005d5064`). Tool modernization is intentionally not added to the product test inventory.
- `tools/godzip_themes/` remains a frozen tool-owned theme snapshot and is normally unselected by CREATE GOD ZIP workflow defaults. This follow-up does not recopy the unchanged 56-theme payload.

## GODZIP Foundry polish

- Replaced the native title bar with frameless Settings-style custom chrome while preserving system move, minimize, maximize/restore and close behavior.
- Increased header breathing room so title/subtitle/status chips do not clip the custom chrome.
- Normal navigation tabs now use rounded ThemeSpec-backed borders.
- `CMD` is no longer part of the ordinary left tab run. Its page remains in the stack but its normal tab is hidden; a dedicated rounded navigation button lives in the tab widget's far-right corner and selects the CMD page.
- Existing compact Apply dashboard, background task lane, nonmodal always-on-top result/confirm windows and tool-local theme selection remain intact.

## Shared Qt Foundry chrome

New `tools/foundry_chrome.py` owns shared standalone-Foundry appearance behavior for Qt tools:

- frameless window flags and translucent host;
- Settings-style draggable title bar with cog/minimize/maximize/close;
- tool-local appearance chooser;
- Default Dark Glass fallback and tool-specific persisted theme ids;
- Windows Glass/Acrylic backdrop application.

The shared chrome consumes the frozen `tools/godzip_themes/` catalogue through `godzip_foundry_theme.py`; it does not read/write the product Settings theme selection and does not consume `dark.qss`.

## Defaults Foundry

`tools/default_settings_editor.py` now uses the shared frameless Dark Glass shell and live tool-local appearance chooser. The defaults authority/edit/import/regeneration behavior is unchanged. Its UI appearance no longer loads the product Settings theme as state.

## Theme Foundry

`tools/theme_foundry.py` now uses the same frameless shell and tool-local appearance chooser. The theme used to skin Theme Foundry itself is independent from the `.srtheme` draft being authored; choosing a tool appearance cannot mutate the theme under edit.

## Build Foundry

`tools/build_runner.py` deliberately remains stdlib/Tkinter bootstrap-safe. It must still launch before the project Qt environment exists.

- It reads the same frozen `.srtheme` snapshot directly with stdlib JSON and projects the semantic colours into its existing custom Tk chrome.
- A settings cog exposes the same tool theme catalogue.
- Appearance changes are persisted and applied by a clean **Apply & Restart** rather than attempting to repaint a large active Tk tree during a build.
- No PySide6 dependency was introduced into Build Foundry.

## Test / debris policy

The user explicitly does not want dedicated product-regression tests for standalone tool cosmetics. The previous temporary `tests/test_godzip_foundry_modern_ui_contract.py` is therefore retired as GODZIP debris. No replacement tool test is added and `Docs/TestSuite.md` remains the repo-current product test guide.

## Validation completed

- Changed/new Python tool files compile successfully.
- Whole-tree Python AST parse: 499 source files clean.
- Frozen tool themes: 56/56 parse as `srpss.settings-theme`, schema v6.
- Build Foundry bootstrap smoke (`--smoke-test --mode venv`) completes successfully and discovers seven jobs; environment-specific external-tool warnings on Linux are expected.
- Build Foundry still imports Tkinter and does not import PySide6.
- Static UI wiring confirms GODZIP frameless chrome, rounded tabs and right-corner CMD navigation; Defaults/Theme use shared Foundry chrome and tool-local appearance selection.
- Cache/bytecode debris removed before packaging.

Physical Windows review is useful for final aesthetics (window drag/maximize, native backdrop, clipping and Tk theme projection), but there is no new product-runtime acceptance gate from this tool-only slice.
