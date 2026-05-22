# Visualizer Reference

Last updated: 2026-05-22

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
- settings/model normalization and resolved activation payload selection,
- widget/runtime config application,
- audio capture and analysis,
- mode-aware runtime shaping,
- overlay state transport,
- renderer/shader uniform upload,
- outer card geometry resolution.

Key ownership split:
- `widgets/spotify_visualizer_widget.py` owns coordinator/lifecycle behavior.
- `widgets/spotify_visualizer/card_geometry.py` owns outer-card size/placement policy.
- `widgets/spotify_bars_gl_overlay.py` and the extracted overlay helpers own GL transport/render-state application.
- `WidgetManager` owns committed CUSTOM geometry reapply.

## 3. Shared Settings Contracts
- mapping normalization: `visualizer_settings_snapshot.py`
- technical normalization / legacy migration contract: `visualizer_settings_contract.py`
- preset-index fallback: `visualizer_preset_indices.py`

Technical persistence rule:
- runtime and canonical saved settings use per-mode technical keys only;
- curated/custom presets may vary technical payload inside a mode;
- shared/global technical keys are accepted only as legacy migration inputs and must not survive normalized payloads.

Routing rule:
- Outside `Custom`, visualizer routing is exact `Follow Media` parity.
- In `Custom`, the visualizer owns its own numbered-display `position` / `monitor`.
- `Custom + ALL` is not a valid steady-state routing outcome and must not be treated as a normal persisted result.

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
- In `Custom`, visualizer visibility still follows Media even when display ownership is independent.
- Committed CUSTOM geometry must reapply through shared runtime seams, not through widget-local ad hoc resize overrides.

## 6. CUSTOM Geometry Contract
- The visualizer participates in the same global CUSTOM edit session as the other supported widget families.
- The edit shell uses the composited card-plus-overlay view rather than only the bare QWidget shell or the whole display.
- Saved CUSTOM payload stores adaptive width/height scale intent rather than freezing one captured card size forever.
- Runtime CUSTOM sizing should stay single-authority: live mode/preset card metrics come from the visualizer geometry policy, while committed CUSTOM placement/scale comes from the shared runtime reapply path.

## 7. Diagnostics
- Use `SRPSS_VIZ_DIAGNOSTICS=1` or `--viz-diagnostics`.
- For transport bugs, verify:
  - model normalization,
  - config-applier kwargs,
  - overlay `set_state` storage,
  - renderer uniform upload.
- For CUSTOM-routing bugs, verify:
  - effective position/monitor routing resolution,
  - visualizer create-time media-anchor resolution across displays,
  - committed custom-layout payload,
  - final runtime geometry authority.

## 8. Regression Hotspots
- settings serialization omissions,
- runtime bridge key omissions,
- overlay parameter accepted-but-not-stored cases,
- schema drift between defaults, presets, and repair tooling,
- split-authority geometry bugs between widget-local preferred sizing and manager-owned CUSTOM geometry,
- create-time cross-display anchor resolution when visualizer and Media are on different displays.
