# R-33 — 2026-07-10 — Defaults SST Regeneration Reached Installed Profiles And Canonicalized Machine Layout Slots (Resolved In Code)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Observed failure pattern:** Foundry Save and Regenerate could make existing installation JSON appear invalid/reset, turning a small default tweak into a disruptive profile recovery. The canonical Normal literal also contained saved layout-slot display identities and geometry from one machine.
- **Root cause:** `regenerate_sst_defaults.py` relied on a throwaway QSettings organization, but JSON storage paths are application/profile-owned and ignore that organization. Because no `storage_base_dir` was supplied, `reset_to_defaults()` and `save()` targeted installed `Screensaver` / `Screensaver_MC` JSON. Separately, Foundry import did not exclude profile-local CUSTOM/layout-slot payloads, allowing active machine geometry into defaults.
- **Final fix:** Foundry imports exclude CUSTOM geometry and layout slots, canonical slots start empty, and text settings describe finite values or accepted free-text domains. Default SST generation no longer constructs `SettingsManager` at all: both artifacts derive directly from the profile-aware sanitized builder, validate exact canonical parity and private-field absence, carry deterministic generated metadata instead of `migrated_at` / `last_migration_completed`, and replace their targets atomically only after validation.
- **Bars:** `tests/test_regenerate_sst_defaults.py` proves unchanged repeat runs are byte-identical, Normal/MC snapshots equal their selected canonical profile, the actual MC leaf delta equals the Foundry-owned override mapping, Weather coordinates and credential fields are absent, a settings-manager constructor cannot be reached, and an installation JSON sentinel remains unchanged. `tests/test_settings_profile_separation.py`, `tests/test_default_settings_editor.py`, defaults parity, SettingsManager import/export, Steam credential, and visualizer SST round-trip suites protect the surrounding runtime paths.
- **Security/privacy note:** regenerated canonical JSON/SST files contain no saved display identities/layout slots, operational migration state, or credential fields. The Foundry changes source defaults and checked-in derived artifacts only; generated SST work has no code path to installed settings JSON.

## Record Provenance

This standalone file preserves the complete former inline `R-33` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
