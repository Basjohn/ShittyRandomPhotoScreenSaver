# SRPSS First-Run Source Onboarding Resume Handoff — 2026-09-11

## Authority

This slice continues from `GODZIP_DefaultsMerge_UserPreserved_2026-09-11.zip` and preserves the operator's latest canonical defaults supplied afterward. `core/settings/default_settings.py` remains the sole Normal-profile defaults authority; the JSON snapshot and both SST files are regenerated derivatives.

## What changed

- Normal RUN startup with no configured folders/RSS feeds still opens the existing source warning and Settings onboarding flow.
- Closing Settings after adding a source now resumes the original RUN startup in the same process instead of returning through `run_config()` and exiting.
- CONFIG-only invocations (`/c`, `/c:...`, `-c`, `-s`, `--s`) remain Settings-only and exit when Settings closes.
- `QApplication.quitOnLastWindowClosed` is temporarily disabled only during interrupted-RUN onboarding so closing the sole Settings window cannot queue application termination before runtime windows are created; the prior policy is restored afterward.
- Startup-dependent Interaction Mode is resolved after onboarding so values changed during the onboarding Settings session are honored by the resumed RUN.
- No first-run flag, timer, poller, alternate settings owner, or special persisted lifecycle state was added. Launch intent remains the authority.

## Defaults preserved

The operator's latest `core/settings/default_settings.py` is preserved exactly as supplied before derivative regeneration. Notable intentional changes relative to the preceding GODZIP include:

- Transition activation defaults: Block Puzzle Flip OFF, Crossfade OFF, Diffuse OFF.
- Visualizer `mode_activation.sphere = true` (the later dormancy-schema migration preserves this intent while retiring persisted `enabled_modes`).
- Sphere defaults enabled for overflow, depth shading, incoming fade, fragment interpolation, particle-density response, transient velocity, and light tracer.

The MC profile override remains unchanged, including `display.show_on_monitors = [2]`.

## Validation

- `tools/check_defaults_authority.py`: PASS.
- `tools/regenerate_defaults_artifacts.py --check`: GREEN for JSON snapshot + Normal SST + MC SST.
- `tests/test_startup_source_onboarding_resume.py`: 4/4 direct Qt-free assertions PASS.
- Physical Windows/PySide launch behavior remains NEEDS RUN VALIDATION: normal RUN with zero sources -> add source -> close Settings -> saver continues; `/c` and `--s` -> close Settings -> process exits without starting runtime.

## Packaging guardrail

Continue the selective GODZIP policy: production files follow the superseding manifested tree, but only new tests and edited/new docs/images are carried. Do not reintroduce unchanged historical tests/docs/images merely to make the archive exhaustive.
