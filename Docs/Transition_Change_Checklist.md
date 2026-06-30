# Transition Change Checklist

Last updated: 2026-06-30

Use this checklist when adding, removing, renaming, retuning, or materially changing a transition.

## 1. Registry And Identity
- Update `rendering/transition_registry.py` first for canonical id/name, legacy aliases, UI ordering, cycle/random participation, hardware gating, and startup warmup metadata.
- Update `core/settings/models/_enums.py::TransitionType` only when the persisted enum surface changes.
- Confirm defaults in `core/settings/default_settings.py` still reference valid registry ids.
- Preserve user-facing names unless the rename is intentional and compatibility-reviewed.

## 2. Runtime Routing
- Wire factory/runtime creation through `rendering/transition_factory.py`.
- Keep compositor-backed behavior aligned through `rendering/gl_compositor.py` and `rendering/gl_compositor_pkg/`.
- Shader-backed transitions must ensure first-use program/resource availability through the GL lifecycle helpers even when deferred warmup did not run.
- Keep shader-authoritative transitions shader-authoritative. Do not reintroduce CPU-side reveal simulation unless the compositor consumes it.

## 3. UI And Settings
- Update `ui/tabs/transitions_tab.py` only for controls or behavior the registry cannot express.
- Keep ordinary selector/load/save truth registry-driven.
- Ensure SST/import/default paths continue to canonicalize through the same transition id contract.

## 4. Random, Cycle, And Context Paths
- Confirm engine random selection, C-key cycling, context-menu routing, and factory fallback all agree with registry eligibility.
- If a transition is excluded from random/cycle pools, document the reason in the registry/audit context rather than relying on omission.

## 5. Performance And Warmup
- For GL transitions, verify warmup metadata, first-use ensure/bind behavior, and fallback logging.
- Fallbacks must be loud and route through the relevant logging family.
- Do not fix cadence, paint starvation, or startup stalls with repaint/update retry loops. Use `--perf` evidence and the transition perf parser where appropriate.

## 6. Tests
Add or update focused coverage for:
- registry canonicalization and legacy aliases,
- enum/default/label parity,
- factory instantiation and backend routing,
- random/cycle eligibility,
- startup warmup and first-use shader availability,
- transition-specific payload math or worker handoff,
- and any regression bar needed for the user-visible behavior.

## 7. Docs And Closure
- Refresh `Spec.md`, `Index.md`, and `Docs/TestSuite.md` when live contracts or test inventory change.
- Update `Current_Plan.md` only for remaining active work.
- Visual transition changes still need runtime/manual validation notes when tests cannot prove the visible behavior.
