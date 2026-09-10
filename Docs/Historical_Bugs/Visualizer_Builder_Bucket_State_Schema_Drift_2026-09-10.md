# Visualizer Builder Bucket-State Schema Drift — 2026-09-10

## Failure

Sphere's Settings builder was reorganized from the old `surface` / `motion` bucket names into `appearance`, `particle_flow`, `reaction`, `rotation` and `effects`, but `ui.visualizer_bucket_states` in the canonical defaults was not updated. The persisted bucket-state getter is intentionally fail-fast, so selecting Voxel Sphere raised `KeyError: 'sphere:appearance'` during lazy body construction.

## Root cause

The UI builder and the canonical UI-state schema changed in separate edits, and the existing tests did not prove that every `build_collapsible_bucket(mode_key, bucket_key)` call has a corresponding canonical `ui.visualizer_bucket_states` entry.

## Binding contract

Visualizer bucket names are persisted schema. Renaming/adding/removing a bucket requires updating `core/settings/default_settings.py` and regenerating all derived defaults artifacts in the same slice. Do not hide missing schema with a runtime `.get(..., False)` fallback; missing canonical registration should remain an explicit failure.

A Qt-free regression test now parses every visualizer mode builder and checks all persisted bucket keys against canonical UI defaults, so this contract remains testable even when PySide6 is unavailable.
