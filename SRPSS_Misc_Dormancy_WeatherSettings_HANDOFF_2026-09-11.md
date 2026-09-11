# SRPSS Misc Handoff — Visualizer Dormancy + Weather Settings — 2026-09-11

## Authority

This slice continues from `GODZIP_FirstRun_OnboardingResume_UserDefaults_2026-09-11.zip`. The operator's latest canonical defaults remain authoritative; generated JSON/SST defaults are derived only.

## Visualizer dormancy schema

Per-mode Visualizer dormancy now uses `widgets.spotify_visualizer.mode_activation`, an explicit stable-id -> boolean map matching the shape used by Transition activation. The old persisted `enabled_modes` list is not accepted by ordinary runtime/model/UI readers. `enabled_modes` remains only as a derived in-memory tuple/property where a consumer naturally needs the enabled-id view.

Existing profiles require one temporary forward reader because the retired list was the immediately preceding persisted schema. SettingsManager runs that migration before current defaults are merged, preserving the user's prior dormancy choices, writes `mode_activation`, removes `enabled_modes` immediately, and logs a warning when the old value was actually relied on. `Current_Plan.md` marks this compatibility seam as migration debris to remove after profile-migration tests/physical validation prove it safe.

Canonical defaults preserve the operator's current all-six-admitted intent: Spectrum, Oscilloscope, Sine Wave, Bubble, Dev Curve and Sphere are true. No other user-authored defaults were retuned.

## Weather runtime SETTINGS shortcut

The missing-location Weather QML already emitted the semantic target `weather_location`; the retained Weather presenter already had a callback slot, but `WeatherFamilyAdapter` never injected one. The fix wires that existing semantic action into a weak generation-scoped DisplayManager callback, emits a dedicated `settings_target_requested(str)` signal, and passes the target through the existing queued Settings admission/runtime-destruction barrier.

`SettingsDialog` resolves the semantic target in `ui/settings_launch_targets.py`, constructs Widgets with initial view state `{subtab_id: weather}`, suppresses persisted tab/view restoration for that targeted launch, and focuses the existing `weather_location` control after the lazy page exists. Generic S/context-menu Settings behavior is unchanged. No target-specific timer, direct Weather -> dialog construction, alternate Settings lifecycle, poller or thread was added.

## Validation

- `tests/test_visualizer_mode_activation_schema_current.py`: current-schema + temporary migration contract.
- `tests/test_weather_settings_target_contract.py`: semantic Weather target/lifecycle/navigation contract.
- Direct Qt-free execution of those two modules: 8/8 assertions PASS.
- Full selective GODZIP test payload (`pytest -q tests`): 18/18 PASS.
- Whole-tree Python syntax compilation: GREEN.
- Persisted-key sweep: the literal `enabled_modes` remains only in the one migration seam and its focused test; current defaults/model/UI/runtime do not serialize or read it as product state.
- `tools/regenerate_defaults_artifacts.py --check`: GREEN after regeneration.
- `tools/check_defaults_authority.py`: PASS.
- Physical Windows/PySide gates remain: Visualizer per-mode toggle/restart persistence; old-profile migration warning/removal; Weather no-location SETTINGS click lands on Widgets -> Weather -> Location and runtime restarts cleanly after Settings closes.
