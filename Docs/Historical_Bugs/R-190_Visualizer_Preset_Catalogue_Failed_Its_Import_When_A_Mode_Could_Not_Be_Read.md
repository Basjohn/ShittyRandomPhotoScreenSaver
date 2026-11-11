# R-190 | The Visualizer preset catalogue failed its import when a mode's files could not be read for a moment, and stored presets were bare slot indices

**Status:** fixed 12 Nov 2026 (plan 1C.1). Two faults, both silent until the curated Spectrum presets were replaced
on 11 Nov.

## Symptom

Operator, 11 Nov evening, after installing a build with the new Spectrum presets: the first open of Spectrum
(Settings or its Studio) failed with an error that the Spectrum presets did not exist; a second attempt worked.

## Cause

1. **A failed import, retried by Python.** `core.settings.visualizer_presets` built every mode's catalogue once,
   at its first import. If no curated file of a mode could be read at that moment (each read failing with an
   `OSError`: a file held by the installer or a scanner right after an install, or being replaced), the build
   raised `RuntimeError: visualizer mode 'spectrum' has no authored presets`. Spectrum is the first registered
   mode, so any such failure named it (R-121 had already produced the same misleading message once). The raise
   failed the import itself; Python does not keep a failed import, so the next open imported again, found the
   files readable and worked. Reproduced by `tests/test_visualizer_preset_unreadable_folder.py`: on the pre-fix
   code the import fails with exactly that message. No log of the operator's frozen run exists (logging was
   off), so the exact moment cannot be shown; the mechanism and the message match.
2. **Bare slot indices.** A profile stored only `preset_<mode>`, a compact slot index. When the catalogue changed
   (11 Nov: slots 11-15 removed, then five more removed and Prism moved from slot 7 to 5), a stored index silently
   meant another preset, an index past the end fell back to Preset 1 without a word, and a stored Custom (the
   trailing index) became a curated preset whenever the catalogue grew. This had been true at every preset
   removal or addition since the compact catalogue (sparse authored numbering, Sept 2026).

A side trap found while fixing (1): the profile-lender bridge (`migrate_profile_lender_owned_settings`) consulted
the lender's catalogue while a curated file was being normalised; it stood aside only during the first import,
so a mode whose catalogue was empty could never be rebuilt (every file "failed" for want of its own catalogue).

## Fix and evidence

- The import never fails on an unreadable mode: the mode is read again on first use and no failure is cached; an
  unreadable file forces a re-read at the next open; a rebuild that finds nothing readable keeps the catalogue it
  has; the lender bridge stands aside during every catalogue build (`core/settings/visualizer_presets.py`,
  `core/settings/visualizer_settings_contract.py`).
- Stored presets carry the preset's identity and the catalogue's signature (`preset_references`), resolved by name
  after a catalogue change, repaired once at load, with a bridge for older profiles
  (`Docs/Architecture/Persisted_Input_Compatibility.md`, "Visualizer preset references"); the Settings mode page
  reloads presets that changed on disk since the process loaded them.
- Guard: `tests/test_visualizer_preset_compat.py` fails when a curated preset is removed, renamed or added without
  its line in `core/settings/visualizer_preset_compat.py`.
- Tests: `tests/test_visualizer_preset_unreadable_folder.py`, `tests/test_visualizer_preset_references.py`
  (every curated mode; the real Settings dialog and Studio on a profile copy), negative controls described in each.

## Lesson

A catalogue read once at import is a single point of failure that the import system silently retries; build it so
that a moment's unreadable file is a logged, retried condition, never a failed import. A stored choice that names a
position in authored content needs the content's identity beside it, or every authoring round re-points profiles.
