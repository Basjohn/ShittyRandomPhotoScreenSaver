# Test Suite Guide

Last updated: 2026-04-23

Testing strategy, execution guidance, and minimum quality bar.

## 1. Testing Philosophy
- Keep fast deterministic unit coverage for core logic.
- Add integration/regression coverage for lifecycle and cross-module behavior.
- Treat visual/timing-sensitive bugs as requiring runtime validation in addition to tests.

## 2. How to Run
- Full suite:
```powershell
pytest tests -q
```
- Collect only:
```powershell
pytest --collect-only tests -q
```
- Targeted file/class:
```powershell
pytest tests/test_settings_manager.py -q
pytest tests/test_visualizer_presets.py::TestVisualizerPresetRepair -q
```

## 3. High-Value Regression Areas
- Settings manager cache invalidation and section-write behavior.
- Visualizer mode/preset contracts and schema normalization.
- Overlay/widget lifecycle and startup staging behavior.
- Rendering/compositor fallback and transition lifecycle.
- Input routing and runtime interaction-mode behavior.

## 4. Visualizer Test Expectations
When changing visualizer settings/contracts, include tests for:
- model serialization round-trip,
- normalization contracts,
- runtime bridge kwargs transport,
- preset repair/reindex behavior,
- mode-prefix compatibility for future/unknown-style payload prefixes.

## 5. Test Hygiene
- Keep tests isolated and deterministic.
- Clean up Qt objects/timers in teardown paths.
- Prefer focused assertions over broad brittle snapshots.
- Avoid locking tests to artistic preset content unless explicitly intentional.

## 6. Runtime Validation Rule
For bugs with user-visible rendering/startup/focus behavior:
- tests are required,
- but final sign-off requires runtime observation (manual or harness-backed evidence).
