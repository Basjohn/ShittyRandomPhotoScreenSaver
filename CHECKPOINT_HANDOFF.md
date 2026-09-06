# CHECKPOINT18 HANDOFF — 5.0.0 Installer Migration Reset Safety

Authority is the superseding CHECKPOINT18 GODZIP built on CHECKPOINT17 at source HEAD `db5785ce3143c0d9658bc6fb95436a13f761ce03` with a dirty assistant worktree.

## Installer migration-reset correction

The old installer task deleted only `settings_v2.json`. That was not a true first-v5 reset: when the JSON store was absent, `SettingsManager` could detect the old Qt `QSettings` registry profile and migrate it straight back into the new JSON store.

For **5.0.0 only**:

- Standard `resetsettings` defaults checked.
- MC `resetsettings` defaults checked.
- Inline ISS comments explicitly say to reconsider/remove the default-on policy after the 5.0.0 migration release.
- Standard reset deletes `%APPDATA%/SRPSS/settings_v2.json` plus `HKCU\\Software\\ShittyRandomPhotoScreenSaver\\Screensaver`.
- MC reset deletes `%APPDATA%/SRPSS_MC/settings_v2.json` plus `HKCU\\Software\\ShittyRandomPhotoScreenSaver\\Screensaver_MC`.
- Diagnostic remains unchecked by default because it deliberately consumes the ordinary profile; if explicitly selected, its reset clears both ordinary JSON and legacy QSettings too.

Caches, credentials, themes, curated presets and other state are not deleted by this task.

## Settings-error behavior

- Malformed JSON or a non-mapping snapshot is a load failure and regenerates canonical defaults.
- Valid old settings are intentionally migrated, missing canonical leaves filled, known aliases/schema normalized, capability dependencies repaired and bounded validation applied.
- A syntactically valid historical semantic value outside known migration/repair rules can survive. The 5.0.0 default-checked reset is the clean mass-migration baseline, not permission to weaken validation.

## Tests / docs

- New `tests/test_installer_v5_reset_policy.py` pins default-on Standard/MC, opt-in Diagnostic and complete JSON + legacy-registry deletion.
- `Docs/Defaults_Guide.md` and `Docs/TestSuite.md` updated.
- Historical record: `Docs/Historical_Bugs/Installer_Reset_Reimported_Legacy_QSettings_2026-09-06.md`.

Verification before packaging: focused defaults + installer gate **32/32**, defaults authority audit clean, deterministic defaults snapshot exact, first-party Python compile **435/435**.

## Architectural note for next layout work

Weather and the Steam card families still carry migration-era per-value CUSTOM size payload routes. Reddit/Media/Gmail use the newer single whole-retained-presentation scale. Achievement Pulse partially adopted that shared transform while retaining the Steam payload route; Abandonment Issues still owns a local authored-canvas scale; Weather owns a local intrinsic-fit scale plus font/icon payload scaling. This is accepted parity behavior, not a fundamental visual requirement. Normalize these seams before making non-CUSTOM stacker auto-shrink a universal feature.
