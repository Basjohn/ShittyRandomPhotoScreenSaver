# Media Key Debug Notes

Last updated: 2026-04-23

Operational notes for debugging media-key and runtime input routing behavior.

## 1. Scope
Use this guide when investigating:
- media key handling regressions,
- Ctrl/interaction-mode routing issues,
- differences between script, screensaver, and MC runtime behavior.

## 2. First Checks
- Confirm runtime variant (`main.py` vs `main_mc.py`).
- Confirm active input mode (`input.hard_exit`, Ctrl interaction state).
- Confirm focus/window-state assumptions before changing routing logic.

## 3. Logging and Repro
- Run with `--debug` and capture relevant logs.
- Use minimal reproducible sequences (key presses, mouse actions, focus transitions).
- Validate behavior in both normal and MC profiles when issue might be profile/runtime specific.

## 4. Architectural Boundaries
- Input handling is centralized in rendering/input and display native-event layers.
- Avoid per-widget global key-hook logic.
- Fix root routing paths instead of adding mode-specific exceptions where possible.

## 5. Regression Expectations
Any input/media-key fix should include:
- focused automated regression where feasible,
- runtime confirmation in affected launch modes,
- note in `Docs/Historical_Bugs.md` when the bug family has prior history.
