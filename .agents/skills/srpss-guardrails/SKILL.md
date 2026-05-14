---
name: srpss-guardrails
description: Use when editing or reviewing ShittyRandomPhotoScreenSaver/SRPSS code, especially architecture, settings, visualizers, Qt/PySide6 focus/effects, overlays, Gmail widget, rendering, startup, packaging, helper/secure-desktop behavior, regressions, or multi-file changes. Enforces SRPSS Spec.md, Index.md, and Docs/Guardrails.md contracts.
---

# SRPSS Guardrails Skill

You are working in the ShittyRandomPhotoScreenSaver (SRPSS) repository.

Use this skill to keep changes architecture-safe, regression-aware, and reviewable.

## Required document pass
Before editing substantial code, consult the relevant canonical docs:

1. `Spec.md` for architecture and behavior contracts.
2. `Index.md` for module ownership and file locations.
3. `Docs/Guardrails.md` for engineering rules and known anti-regression policies.
4. `Docs/Documentation_Maintenance.md` when shared work may require doc drift cleanup.
5. `Docs/Harness_Index.md` when diagnosis or validation may benefit from an existing harness/probe.
6. `Docs/Visualizer_Change_Checklist.md` for visualizer/settings changes.
7. `Docs/Historical_Bugs.md` when touching fragile or previously regressed areas.
8. `Current_Plan.md` only for active work context if relevant.

Do not treat stale memory as more authoritative than these repo docs.

## First response / planning behavior
For non-trivial work:

1. Inspect the relevant files first.
2. Identify the owning module/manager.
3. State the likely affected files.
4. Make a short implementation plan.
5. Then edit.

For tiny obvious edits, still inspect the target file before modifying it.

## Architecture ownership rules
Respect centralized ownership:

- Threading and async business work: `ThreadManager`.
- Qt object lifecycle: `ResourceManager`.
- Settings read/write/migration: `SettingsManager` and canonical defaults.
- Animations: `AnimationManager`.
- Worker process orchestration: `ProcessSupervisor`.

Never add shadow frameworks, duplicate managers, or parallel ownership paths.

## Settings rules
- Canonical defaults are single-source.
- New user-facing defaults must be added to the canonical defaults system, not hardcoded into UI/widget code.
- Section/root writes must invalidate descendant dotted-key cache entries.
- Reset/import preservation must use the shared preservation contract.
- Retired global preset schema keys stay retired.
- Preserve backwards compatibility unless a deliberate migration is requested.

## Visualizer rules
- Mode identity and labels come from `core/settings/visualizer_mode_registry.py`.
- Internal ids and key namespaces remain stable.
- Shared seams must remain neutral and explicit.
- Mode-owned behavior belongs to mode-owned code.
- Reindex logic normalizes index/filename numbering only; do not rewrite creative payload intent.
- `core/settings/models/_spotify_visualizer.py` is the grouped field-spec source of truth for visualizer settings ingestion/persistence. Update defaults/build specs/serializer specs together and preserve ordered grouped merges so `from_settings()`, `from_mapping()`, and `to_dict()` stay one contract.
- Do not reintroduce bespoke entry-point-specific field families or fallback paths once a visualizer settings group has been centralized.
- Visualizer setting changes require the visualizer change checklist sweep.

## Qt / UI / rendering rules
- Never recursively manipulate focus policies on large widget trees at runtime.
- If focus policy changes are needed, prefer construction-time setup.
- Never recreate or replace `QGraphicsEffect` while a `QVariantAnimation` is actively driving it unless the animation is safely reconnected to the new effect.
- When restoring focus/activation to a top-level window with separate top-level overlays, re-raise overlays after raising the main window.
- Do not remove custom styling, shadows, fades, or overlay effects to hide runtime issues.
- Fix startup, focus, visibility, and flicker bugs at the root cause.
- Respect staged startup contracts for dependent overlay widgets.
- Input routing is centralized; do not add widget-specific ad hoc global key/mouse handlers.

## Gmail widget rules
- Gmail is a normal feature and must not be hidden behind a dev gate or CLI flag.
- Gmail settings remain a flat dict under the current settings/defaults architecture unless the whole widget settings architecture is deliberately migrated.
- Gmail settings UI load/reset/import must block signals while populating controls.
- Gmail settings construction must not synchronously load backend/auth credential state.
- IMAP Save & Test must run off the UI thread and save credentials only after a successful test.
- Gmail visual settings must keep geometry and hit rects aligned.
- Gmail URL click routes must respect normal/SCR/secure-desktop vs MC-mode routing.
- Gmail must avoid idle churn: no per-tick network work, pixmap scaling, lazy pixmap conversion, over-painting, or unnecessary `update()` calls when data and animation state are unchanged.
- Gmail refresh/result/cache churn should defer around pending or active image transitions when possible.
- Gmail build/release work must verify image assets, notification sound assets, Qt multimedia dependencies, frozen build config, resource copy steps, and installer/package outputs.

## Regression prevention
- Verify new helper functions are wired into production call chains. Search for callers excluding tests.
- Do not declare a fix complete only because a helper looks correct.
- Preserve useful harnesses/probes that materially improve diagnosis quality.
- Do not treat tests alone as sufficient for visual/timing-sensitive bug closure.
- If a bug is visual, focus-related, timing-sensitive, multi-monitor, secure-desktop, or transition-related, explicitly state what still requires runtime validation.

## Editing discipline
- Prefer minimal, local patches.
- Do not rewrite unrelated systems.
- Do not change unrelated formatting.
- Do not rename files, ids, settings keys, CLI flags, or public labels unless asked.
- Do not delete compatibility aliases without explicit approval.
- Do not introduce broad abstractions for a one-off fix.
- Avoid “creative” schema repair. Repair should normalize structure without changing authored intent.

## Validation
After edits, run the narrowest useful checks available:

- `python -m py_compile <changed .py files>` for changed Python files.
- Targeted tests for changed contracts.
- Existing harnesses/probes when touching their guarded areas; prefer `Docs/Harness_Index.md` when it already documents the workflow.

If validation cannot be run, say exactly why.

## Final response contract
Final response must include:

1. Files changed.
2. What changed and why.
3. Checks run and their result.
4. Remaining risks, especially runtime/manual validation still needed.
5. Any behavior intentionally left unchanged.
