# Installer Reset Could Re-import Legacy QSettings — 2026-09-06

## Symptom

The installer `Revert Settings To Defaults` task deleted `settings_v2.json` but left the pre-JSON Qt `QSettings` registry tree. On first v5 launch, the SettingsManager sees no JSON store and can migrate that registry tree straight back into the new store.

## Fix

For 5.0.0, Standard and MC default the reset task ON and a selected reset deletes both the profile JSON snapshot and matching legacy registry tree. Diagnostic remains opt-in but its selected reset is complete too.

## Guard

`tests/test_installer_v5_reset_policy.py` pins both the 5.0.0-only default-on comment/policy and the JSON + registry deletion pair.
