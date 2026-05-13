# Transition Change Checklist

Last updated: 2026-05-13

Use this checklist when adding, removing, or materially changing a GL transition.

## 1. Transition Runtime Module
- Add or update the transition module under `transitions/`.
- Keep behavior isolated to the transition implementation instead of smuggling transition-specific rules into shared compositor code unless the shared seam truly needs to expand.

## 2. Canonical Type / Persistence
- Update `core/settings/models/_enums.py::TransitionType`.
- Confirm any transition defaults or fallback values in `core/settings/default_settings.py` still point at a valid transition id/label.

## 3. Factory Registration
- Register the transition in `rendering/transition_factory.py`.
- Ensure any direction handling, worker precompute metadata, or backend capability branching is wired in the same change.

## 4. UI Surface
- Update `ui/tabs/transitions_tab.py` labels, ordering, per-transition duration/direction handling, and random-pool membership behavior.
- Preserve user-facing labels unless there is an intentional rename with compatibility review.

## 5. Random Pool / Engine Selection
- If the transition participates in engine-driven random mode, confirm the runtime pool in `engine/screensaver_engine.py` can actually select it.
- If it should be excluded from random mode, document why in the relevant runtime or audit note instead of relying on omission.

## 6. Tests
- Add or update targeted coverage for:
  - factory selection/instantiation,
  - random-pool eligibility when applicable,
  - enum/label parity,
  - any transition-specific payload math or worker handoff that could silently drift.

## 7. Docs
- Refresh `Spec.md`, `Index.md`, and `Docs/TestSuite.md` when the transition changes live contracts or test inventory.
- Update `Current_Plan.md` only if the transition work remains actively unfinished after the change.

## 8. Closure Rule
- If the change is visually sensitive, tests are not enough by themselves. Keep runtime/manual validation in scope for final sign-off.
