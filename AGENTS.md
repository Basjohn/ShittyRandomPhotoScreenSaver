# AGENTS.md — SRPSS Codex Instructions

## Project identity
This repository is ShittyRandomPhotoScreenSaver (SRPSS): a Python/PySide6/Qt6 multi-monitor screensaver/media-center project with OpenGL rendering, configurable overlay widgets, visualizers, settings persistence, and Windows packaging.

## Canonical docs to consult
Before substantial edits, read these files as needed:

- `Spec.md` — canonical architecture and behavior contracts.
- `Index.md` — current module ownership map and file locations.
- `Docs/Guardrails.md` — engineering safety rules and anti-regression policy.
- `Docs/Documentation_Maintenance.md` — lightweight drift-check routine for keeping canonical docs aligned.
- `Docs/Harness_Index.md` — compact reference for recurring investigation harnesses and smoke commands.
- `Current_Plan.md` — active work only, if present and relevant.
- `Docs/Visualizer_Change_Checklist.md` — required sweep for visualizer setting changes.
- `Docs/Historical_Bugs.md` — dated bug narratives and root-cause record when touching fragile areas.

If a task touches architecture, settings, visualizers, Qt focus/effects, Gmail widget behavior, rendering, startup/focus, packaging, or helper/secure-desktop behavior, use the `srpss-guardrails` skill explicitly.

## Working style
- Inspect relevant files before editing.
- Prefer small, surgical patches over broad rewrites.
- Do not rename public/internal ids, setting keys, or file contracts unless the task explicitly requires migration.
- Do not invent parallel frameworks, duplicate managers, or shadow ownership paths.
- Do not hide runtime issues by removing styling, animations, shadows, overlays, or settings UI unless explicitly asked.
- Do not leave dead helper functions unwired; verify new helpers have production callers.
- Preserve backwards compatibility for settings, presets, runtime flags, and user-facing behavior unless explicitly asked otherwise.
- Treat visual/timing-sensitive bugs as requiring runtime reasoning; tests alone are not proof of closure.

## Central ownership contracts
- Threading and async business work go through `ThreadManager`.
- Qt object lifecycle goes through `ResourceManager`.
- Settings read/write/migration goes through `SettingsManager` and canonical defaults.
- Animations route through `AnimationManager`.
- Cross-module publish/subscribe events go through `EventSystem`.
- Worker process orchestration goes through `ProcessSupervisor`.

## Settings safety
- Canonical defaults must remain single-source.
- Section/root writes must invalidate descendant dotted-key cache entries.
- Reset/import preservation must use the shared preservation contract in `core/settings/defaults.py`.
- Retired global preset schema keys stay retired.
- Do not add hardcoded widget defaults when canonical defaults are available.

## Visualizer safety
- Mode identity and labels come from `core/settings/visualizer_mode_registry.py`.
- Internal ids remain stable even when user-facing labels change.
- Shared seams must stay neutral and explicit.
- Mode-owned behavior belongs to mode-owned code.
- Reindex logic is index/filename normalization, not creative payload rewriting.

## Qt/UI/rendering safety
- Do not recursively manipulate focus policies on large widget trees at runtime.
- Do not recreate or replace a `QGraphicsEffect` while an active animation is driving it unless the animation is safely reconnected.
- When restoring focus/activation to a top-level window with separate top-level overlays, re-raise overlays after raising the main window.
- Respect staged startup contracts for dependent overlay widgets.
- Input routing is centralized; do not add widget-specific ad hoc global key/mouse handlers.

## Gmail/widget safety
- Gmail is a normal feature, not a dev-gated feature.
- Gmail settings remain a flat dict under the existing settings/defaults architecture unless the whole widget settings architecture is deliberately migrated.
- Gmail UI construction/load must avoid synchronous backend/auth work and avoid settings flicker hazards.
- IMAP Save & Test must not block the settings UI.
- Gmail must avoid per-tick network work, pixmap scaling, lazy conversions, over-painting, and unnecessary updates when data/animation state are unchanged.
- Gmail refresh/result/cache churn must defer around pending or active image transitions when possible.

## Validation expectations
After modifying Python files, run at least syntax/import-safe checks on changed files when possible, e.g. `python -m py_compile <changed files>`.

When relevant, also run or update targeted tests/harnesses. Prefer targeted validation over broad slow commands unless the task asks for full validation.

When a recurring diagnostic or smoke command already exists, prefer the documented tool flow in `Docs/Harness_Index.md` over inventing a fresh ad hoc workflow.

Final response must include:
- Files changed.
- What changed and why.
- Commands/checks run.
- Remaining risks or validation still needing real runtime/manual testing.

## Git safety
- Before risky edits, inspect `git status --short`.
- Do not run destructive commands such as `git reset --hard`, `git clean`, broad `git restore`, or force operations unless explicitly requested.
- For file-specific recovery, target only the named file/path.
- Do not overwrite uncommitted user work.
