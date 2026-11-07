# R-174 | Save Preset As wrote Bubble's values over Neon Lake's Preset 1

**Status:** fixed 7 Nov 2026 (`core/settings/visualizer_preset_file.py`, `ui/tabs/media/preset_slider.py`).
Regression tests with negative controls are in `tests/test_visualizer_preset_cross_mode_write.py`. The lead restored
the lost file from git.

## Symptom

At 21:45:04 on 6 Nov, during the operator's source run,
`presets/visualizer_modes/shockwave_grid/preset_1_synthwave.json` (Neon Lake Preset 1) was rewritten as a Bubble
preset:

- `"mode": "bubble"`, `"visualizer_preset_mode": "bubble"`, the name "Preset 1 (Synthwave)", `preset_index` 0;
- a snapshot of 78 Bubble keys;
- about 13,000 lines of Neon Lake content lost.

No Bubble file changed, and no log line named the write. The bad file is kept at
`.artifacts/evidence/settings/preset_cross_mode_write/20261106_preset_write/preset_1_synthwave.bubble_content_written_2145.json`.

## Evidence

- **Settings was open from 21:44:34 to 21:45:11.** At 21:44:41 the log has
  `[VIS_PRESETS_SAVE] Before/After filtering for bubble: 78 keys`. That line comes from
  `build_visualizer_preset_payload("bubble")`, which builds the payload before the file dialog opens. The write came
  23 s later, with nothing logged, and then `saved mode=bubble preset=8`.
- **The written file matches one writer exactly.** It has the key order of `build_visualizer_preset_payload`, plus a
  `description` of "Saved from current Settings state.". That is the `setdefault` in
  `VisualizerPresetSlider._save_custom_preset_as`, the preset row's **Save Preset As…** on Custom.
- **The name and slot came from the chosen filename.** "Preset 1 (Synthwave)" and slot 0 are what
  `_apply_filename_metadata` derives from `preset_1_synthwave.json`.
- **So the target came from the file dialog's answer.** The values came from Bubble, the active mode. The log cannot
  show whether the dialog was navigated to Neon Lake's folder or opened there.

## Cause

`_save_custom_preset_as` wrote wherever the file dialog answered, with `json.dump` straight to the path:

- no check that the path is in the mode's own preset folder;
- no check that a file already there belongs to the same mode;
- no log line.

The dialog's start folder is the mode's own folder, but nothing kept the save there. A Bubble Save As could therefore
replace any other mode's curated file, and the overwrite confirmation Windows shows does not say which mode a file
belongs to.

The patch path (`save_changes_to_preset`, behind Save To <Preset> and the Studio's Overwrite) reads its target from
the mode's own slot, but it did not verify the file's mode either.

## Fix

Every preset-file write now goes through the owner, `core/settings/visualizer_preset_file.py`:

- `check_preset_write_target(mode, path, payload)` fails closed, raising `PresetModeMismatch` with an error log, when
  any of these holds:
  - the payload names another mode;
  - the path is outside `get_visualizer_presets_dir(mode)`;
  - the file already at the path is another mode's preset.
- `write_new_preset_file` (Save Preset As) and `save_changes_to_preset` (the patch) both run that check. Each logs one
  info line, `[VIS_PRESETS] wrote preset file mode=... index=... path=...`.
- Save Preset As shows "Not Saved", naming the mode's folder, and writes nothing.

## Installed builds

Installed builds were exposed the same way. There the curated tree is ProgramData's shared preset tree, with the
same per-mode folders, and the same unbounded dialog started there. The check resolves against the active root
(`get_visualizer_presets_dir`), so it covers source and installed runs alike.

Loose-JSON import already places each file in the folder of the mode its payload names. A whole-tree import or replace
copies the tree as it is, and is not checked file by file.

## Proof

`tests/test_visualizer_preset_cross_mode_write.py` writes only to a tmp copy of the real curated tree:

- **The operator's path:** the real preset row's Save Preset As on Bubble's Custom, with the dialog answering Neon
  Lake's Preset 1, leaves the file byte-identical and shows an error. On the old code that test fails: the file is
  overwritten.
- **The owner's checks:** a Bubble payload over Neon Lake's file is refused, and so is a mislabelled payload. A new
  file in another mode's folder is refused, and so is a patch of a slot whose file holds another mode's preset.
- **Negative controls:** Save As into Bubble's own folder still saves, and a write into the mode's own folder is
  written and logged once.

## Lesson

A writer of mode-owned files must take its target and its values from one mode and check both against the file
system before writing. A file dialog answer is user input, not a target the code owns. A file write that changes
authored content must never go unlogged.
