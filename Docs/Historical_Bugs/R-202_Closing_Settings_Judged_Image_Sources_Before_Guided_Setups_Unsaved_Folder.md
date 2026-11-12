# R-202 | Closing Settings judged the image sources before Guided Setup's unsaved folder was kept

**Status:** fixed 12 Nov 2026 (524015a4, found by the 1D.1 Guided Setup UX audit). Regression bar:
`tests/test_guided_setup_close_keeps_draft_sources.py`, which runs the real dialog through its own first-run entry
(`WA_DontShowOnScreen`). Both of its cases fail on the old dialog.

## Symptom

On a first run, a user added a folder in Guided Setup, then closed Settings without pressing Finish. Settings
showed the No Image Sources prompt over a wizard that held a folder. The Keep or Discard question about Guided
Setup's unsaved changes never came, so the folder could not be saved.

## Cause

Since df6cd487 (27 Sep 2026), Guided Setup edits a draft, and only Finish (or a confirmed Keep) writes it to the
store. `SettingsDialog.closeEvent` (`ui/settings_dialog.py`) ran its image-sources check first. That check reads
the saved store, where a source added in the wizard does not exist yet, and its prompt ended the close before the
wizard's unsaved-changes question was asked.

## Why it stayed hidden

It only happens on the path a first-time user takes: adding the first source in Guided Setup, then closing rather
than finishing. Every test either pressed Finish or started with a source already saved. Nothing was logged; the
prompt looked like the ordinary "you have no sources" warning.

## Fix

`closeEvent` resolves Guided Setup's unsaved changes first. If the user cancels, the close is refused. After Keep
or Discard, the image-sources check reads the store as it now stands.

## Lesson

When a page edits a draft, every check that reads the store at close has to run after the draft is resolved,
not before. Test the first-run path with the user's first source still in the draft.
