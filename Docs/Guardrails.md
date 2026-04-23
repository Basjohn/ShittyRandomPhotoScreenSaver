# SRPSS Guardrails

Last updated: 2026-04-23

Policy rules to keep architecture coherent and prevent repeat regressions.

## 1. Documentation Boundaries
- `Spec.md` for architecture contracts.
- `Index.md` for module ownership map.
- `Current_Plan.md` for active work only.
- `Docs/Historical_Bugs.md` for dated bug narratives.
- `Docs/Visualizer_Change_Checklist.md` for visualizer setting changes.

## 2. Centralized Ownership
- Threading through `ThreadManager`.
- Qt lifecycle through `ResourceManager`.
- Settings through `SettingsManager`.
- Animation through `AnimationManager`.

No shadow frameworks or parallel ownership paths.

## 3. Settings Safety
- Canonical defaults are single-source.
- Section/root writes must invalidate descendant cache entries.
- Reset/import preserve behavior uses one shared preservation contract.
- Retired global preset schema keys stay retired.

## 4. Visualizer Safety
- Mode identity and labels come from the mode registry.
- Internal ids remain stable even when user-facing labels change.
- Shared seams stay explicit and neutral.
- Reindex logic is index/filename normalization, not creative payload rewriting.

## 5. UI/UX Safety
- Do not remove custom styling to hide runtime issues.
- Fix startup/focus/visibility bugs at root cause.
- Respect staged startup contracts for dependent overlay widgets.

## 6. Testing and Validation
- Add automated regression coverage for changed contracts.
- Do not treat tests alone as sufficient for visual/timing-sensitive bug closure.
- Preserve useful harnesses/probes that materially improve diagnosis quality.
