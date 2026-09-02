# R-77 — Post-Phase-I QWidget/runtime residue required coordinated retirement

Date: 2026-09-02  
Status: **Implemented in coordinated cleanup / awaiting destination + physical validation**

## Operator evidence that changed the diagnosis

A first cleanup attempt classified 25 QWidget-era/compositor helper files as independently removable and supplied a quarantine script before their replacement caller rewrites were installed. Running that script against the R-76 tree broke application startup immediately.

That failure is binding evidence: **file-level deadness cannot be inferred from destination architecture alone**. R-76 still had compatibility imports/call chains through old logical/presenter seams even though retained Qt Quick already owned the actual pixels.

Examples in the pre-cleanup tree included:

- `tick_pipeline.py` importing `mode_transition` and `spectrum_presentation_smoothing`;
- logical publication dynamically importing `legacy_render_snapshot_adapter`;
- `logical_tick_state.py` importing old mode-transition helpers;
- `mode_transition.py` chaining into `thread_affinity`, `presentation_fade`, `spectrum_presentation_smoothing` and `widgets.shadow_utils`.

Deleting those files **before** rewriting the callers was therefore guaranteed to fail.

## Correct diagnosis

The residue was architectural compatibility debt, not a set of independently caller-dead files. Current Quick owners had replaced the old presentation responsibilities, but some current logical/configuration paths still flowed through modules whose names/contents mixed retired QWidget presentation with surviving neutral semantics.

The valid cleanup unit is therefore the **entire import/ownership transaction**:

```text
trace startup + production imports
-> identify surviving neutral semantics
-> rehome/rename those semantics into current logical/source owners
-> rewrite every production caller
-> prove startup/import closure
-> only then quarantine/remove the obsolete modules
```

## Coordinated repair

The superseding cleanup does the caller rewrites and removals in the same checkpoint:

- strips the retired GUI presentation half from `tick_pipeline.py`; logical publication remains;
- renames/re-homes the current immutable frame-capture seam to `logical_frame_capture.py` / `capture_visualizer_logical_frame`;
- removes retired presenter fade/transition/overlay/card helpers only after their current callers are gone;
- removes old compositor manager/cache/profiler files while retaining transition shader modules still used by retained Quick;
- changes `SpotifyVisualizerAudioWorker`'s parent contract from misleading `QWidget` typing to `QObject`;
- makes Settings-only QtWidgets references in neutral descriptor code type-only/lazy;
- removes dead QWidget-specific GL-format/config-applier surfaces only with caller proof.

`QApplication` app-loop ownership, Settings GUI QWidget code, and QtGui image resources such as QImage/QPixmap are explicitly not classified as QWidget presentation residue.

## Deployment / stale-tree rule

A replacement ZIP cannot delete files that already exist in an extracted local tree. The checkpoint therefore includes a temporary GUI quarantine utility that can move the exact audited obsolete paths to `./deletelater/<original path>` **after the replacement caller code is installed**, and can Undo/Restore them without overwrite.

Never run a deletion/quarantine manifest from a newer cleanup against an older caller graph. The cleanup utility is a deployment aid, not evidence that the files are safe to remove independently.

## Regression contract

- production screensaver runtime outside Settings/tools must not import `QWidget` or `QOpenGLWidget` presentation owners;
- no production import/dynamic-import string may reference the retired 25-module set;
- `tick_pipeline.py` must remain logical-only and must not regain `push_gpu_frame` / `present_tick` / QWidget geometry ownership;
- current immutable capture uses `logical_frame_capture.py`;
- retained Quick transition shader modules remain available;
- startup/import closure is mandatory validation for any future retirement pass.

Source-only cleanup gate: `tests/test_post_phase_i_qwidget_runtime_cleanup.py`.
Full destination/runtime validation remains required before `[x]`.
