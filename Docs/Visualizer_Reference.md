# Visualizer Reference

Last updated: 2026-04-23

Architecture and contract reference for the visualizer subsystem.

## 1. Mode Registry Contract
Source of truth: `core/settings/visualizer_mode_registry.py`.

| Internal ID | User Label | Status |
|---|---|---|
| `spectrum` | Spectrum | active |
| `oscilloscope` | Oscilloscope | active |
| `sine_wave` | Sine Waves | active |
| `bubble` | Bubble | active |
| `blob` | Blob | dev-gated (`-devblob`) |
| `devcurve` | Spline Curve | active |

`--devcurve` remains a compatibility no-op alias.

## 2. Runtime Pipeline
- audio capture and analysis,
- mode-aware runtime shaping,
- settings/model apply,
- overlay state transport,
- renderer/shader uniform upload.

## 3. Shared Settings Contracts
- mapping normalization: `visualizer_settings_snapshot.py`
- technical normalization / legacy migration contract: `visualizer_settings_contract.py`
- preset-index fallback: `visualizer_preset_indices.py`

Technical persistence rule:
- runtime and canonical saved settings use per-mode technical keys only;
- curated/custom presets may vary technical payload inside a mode;
- shared/global technical keys are accepted only as legacy migration inputs and must not survive normalized payloads.

## 4. Preset Contracts
- authored source: `presets/visualizer_modes/`.
- curated load/apply logic: `core/settings/visualizer_presets.py`.
- repair/audit/reindex: `tools/visualizer_preset_repair.py`.

Reindex contract:
- update filename slot numbering,
- update `preset_index`,
- preserve friendly names and non-index payload content.

## 5. Startup and Visibility Contracts
- Startup timing policy is centralized.
- Secondary-stage visualizer-dependent widgets must wait for valid anchor visibility/geometry.
- Avoid pre-position reveal artifacts.

## 6. Diagnostics
- Use `SRPSS_VIZ_DIAGNOSTICS=1` or `--viz-diagnostics`.
- For transport bugs, verify:
  - model normalization,
  - config-applier kwargs,
  - overlay `set_state` storage,
  - renderer uniform upload.

## 7. Regression Hotspots
- settings serialization omissions,
- runtime bridge key omissions,
- overlay parameter accepted-but-not-stored cases,
- schema drift between defaults, presets, and repair tooling.
