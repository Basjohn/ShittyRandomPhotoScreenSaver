# Documentation Maintenance

Last updated: 2026-05-22

Use this as the lightweight drift-check routine for SRPSS's canonical docs.

## Purpose
- Keep `Spec.md`, `Index.md`, `Current_Plan.md`, and long-lived reference docs aligned with the codebase.
- Prevent active plans from turning into changelogs.
- Catch stale file references, ownership claims, and “recently shipped” text that belongs in history instead.

## When To Run This
- After any shared architecture change.
- After widget-family work that affects more than one module or document.
- After promoting an experiment/flagged path into the canonical runtime contract.
- Before closing a large task that changed both code and docs.

## Drift Check

### 1. Confirm the document roles still hold
- `Spec.md` should state architecture and behavior contracts only.
- `Index.md` should map live modules/files and their ownership.
- `Current_Plan.md` should contain active work only.
- `Docs/Historical_Bugs.md` should capture dated regressions, failed attempts, and final fixes.

### 2. Verify file references against the repo
- Confirm referenced files actually exist.
- Remove or update stale references instead of letting them linger as “known broken” links.
- Prefer `rg` over memory or assumptions when checking whether a module, helper, or tool still exists.

Suggested commands:
```powershell
rg -n "Gmail_Widget_Plan\.md|Documentation_Maintenance|Harness_Index" Docs Current_Plan.md Index.md Spec.md AGENTS.md
rg --files Docs tools core widgets ui rendering
```

### 3. Verify ownership claims against code
- For each changed shared area, confirm the named owner/module still matches implementation.
- Check especially:
  - manager ownership in `Spec.md`
  - module descriptions in `Index.md`
  - active-task claims in `Current_Plan.md`

Suggested commands:
```powershell
rg -n "resolve_visualizer_activation_payload|_get_mode_technical_config|GMAIL_SIGNAL_BLOCK_ATTRS|widgets\.shadows\.enabled" core widgets ui rendering
rg -n "ThreadManager|ResourceManager|SettingsManager|AnimationManager|ProcessSupervisor" core Spec.md Index.md
rg -n "_spotify_visualizer|from_settings|from_mapping|to_dict|Visualizer settings model" core Spec.md Index.md Docs/Guardrails.md Docs/Visualizer_Change_Checklist.md
```

Notes:
- `GMAIL_SIGNAL_BLOCK_ATTRS` now belongs to `rendering/widget_descriptors.py` and is re-used by `ui/tabs/widgets_tab_gmail.py`; drift checks should verify that shared ownership instead of assuming the Gmail tab module is still the canonical source.

### 4. Remove completed work from the active plan
- If a task is implemented and its remaining work is only historical context, move that truth into `Spec.md`, `Index.md`, or `Docs/Historical_Bugs.md`.
- Keep only real unfinished decisions, follow-up work, or watchlist items in `Current_Plan.md`.

### 5. Update historical records only when there is a real regression story
- Add to `Docs/Historical_Bugs.md` when a task produced a bug family, failed fix path, or anti-regression lesson.
- Do not paste feature-complete summaries into history unless there was an actual bug or regression worth preserving.

### 6. Keep new docs discoverable
- If you add a long-lived reference doc, add it to `Index.md`.
- If it changes validation or recurring workflows, consider whether `Docs/TestSuite.md` should point to it.

## Good Outcomes
- Canonical docs point at real files.
- Shared contracts are described once, in the right place.
- Finished work disappears from `Current_Plan.md`.
- Historical notes stay useful instead of becoming a second plan.
