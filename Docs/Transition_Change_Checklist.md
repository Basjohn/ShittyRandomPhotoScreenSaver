# Transition Change Checklist

Last updated: 2026-05-18

Use this checklist when adding, removing, or materially changing a GL transition.

## 1. Transition Runtime Module
- Add or update the transition module under `transitions/`.
- Keep behavior isolated to the transition implementation instead of smuggling transition-specific rules into shared compositor code unless the shared seam truly needs to expand.

## 2. Canonical Type / Persistence
- Update `core/settings/models/_enums.py::TransitionType`.
- Update `rendering/transition_registry.py` for canonical setting name, any legacy aliases, ordinary selector ordering, cycle/random participation, hardware-gating metadata, and startup warmup policy where applicable.
- Confirm any transition defaults or fallback values in `core/settings/default_settings.py` still point at a valid transition id/label.

## 3. Factory / Runtime Routing
- Register the runtime creator path in `rendering/transition_factory.py`.
- Ensure any direction handling, worker precompute metadata, or backend capability branching is wired in the same change.
- If the transition is shader-backed or compositor-warmed, confirm registry metadata also keeps `rendering/gl_compositor.py` and `rendering/gl_compositor_pkg/gl_lifecycle.py` aligned through the shared registry rather than new handwritten maps.

## 4. UI Surface
- Update per-transition specific controls in `ui/tabs/transitions_tab.py` only where the registry cannot already express the ordinary selector/load/save truth.
- Preserve user-facing labels unless there is an intentional rename with compatibility review.

## 5. Random Pool / Engine Selection
- If the transition participates in engine-driven random mode or C-key cycling, confirm the registry metadata allows `engine/screensaver_engine.py`, `engine/engine_handlers.py`, the context menu, and any factory-side random fallback to agree on availability.
- If it should be excluded from random mode or cycle mode, document why in the relevant runtime or audit note instead of relying on omission.

## 6. Tests
- Add or update targeted coverage for:
  - registry canonicalization/parity,
  - factory selection/instantiation,
  - random-pool eligibility when applicable,
  - startup warmup parity when shader-backed,
  - enum/label parity,
  - any transition-specific payload math or worker handoff that could silently drift.

## 7. Docs
- Refresh `Spec.md`, `Index.md`, and `Docs/TestSuite.md` when the transition changes live contracts or test inventory.
- Update `Current_Plan.md` only if the transition work remains actively unfinished after the change.

## 8. Closure Rule
- If the change is visually sensitive, tests are not enough by themselves. Keep runtime/manual validation in scope for final sign-off.
