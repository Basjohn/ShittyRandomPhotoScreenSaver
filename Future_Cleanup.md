# Future Cleanup — Migration Deletion Ledger

Last updated: 2026-08-25

This file tracks caller-proven deletion/retirement work. It does not admit work ahead of
`Current_Plan.md`.

## Rule

Delete obsolete presentation with its replacement owner as soon as safe. Do not accumulate everything
until I.

```text
family replacement GREEN -> family pixel deletion
G replacement GREEN      -> old CUSTOM/edit pixel deletion
H cutover GREEN          -> old physical presenter/backend deletion
I                        -> residue only
```

Real product resilience is not migration debris.

## Unrelated focused-test debt

- `tests/test_logging_config.py::test_diagnostic_build_enables_every_family_beside_frozen_executable`
  fails on exact main because the diagnostic output set includes at least one `RotatingFileHandler`
  whose `maxBytes` is not the test's blanket 1 MiB expectation. The failure reproduces alone and is
  unrelated to F1 Clock ownership; determine whether the handler profile or the assertion is stale in
  a dedicated logging checkpoint.

## Phase-F family retirement

After each F1–F8 family is independently GREEN:

- prove old family pixel callers absent;
- delete old QWidget/QPainter family pixel presenter;
- delete/rehome presentation-only tests/helpers;
- retain presentation-neutral provider/model/business/settings code still used;
- retain a shared old helper only while another unported family genuinely requires it.

Git is historical pixel reference after deletion.


## Transition legacy — caller-proof early cleanup

All canonical transition implementations already exist in Quick.

Old transition-only presentation such as:

- `rendering/transition_factory.py` where it exists solely for old pixel construction;
- `transitions/gl_compositor_*_transition.py`;
- old compositor-transition presentation tests/helpers

may retire **before H** as soon as exact caller proof shows Quick no longer depends on them.

Preserve:

- canonical transition registry/settings;
- activation/admission;
- request/run lifecycle;
- authored math/shaders genuinely reused by Quick;
- deterministic recovery behavior.

If a final old transition seam is inseparable from the old physical `DisplayWidget` host, delete that
piece at H rather than creating compatibility architecture.

## Visualizer legacy — caller-proof early cleanup

Do not delete by path/name alone.

Preserve anything currently feeding the destination Quick visualizer, including:

- `VisualizerLogicalRuntime`;
- mode frame runtimes/authored algorithms;
- BeatEngine/source ownership;
- immutable render state;
- snapshot bridge/adapters;
- shaders/math reused by Quick.

Delete caller-proven compositor-only/old-pixel owners as soon as safe, including old overlay/card hosts
that no longer feed Quick.

Pieces inseparable from the physical old presenter may wait for H.

## Phase G

After Quick CUSTOM/input/edit presentation is GREEN:

- delete old QWidget edit/grid/pixel owners no longer called;
- preserve committed geometry/session semantics rehomed to Quick owners;
- preserve real non-pixel Settings controls where still current.

## Phase H — physical cutover + deletion

H removes the old physical presentation stack in the same audited cutover boundary:

- `DisplayWidget`;
- QRhiWidget / `GLCompositorWidget`;
- old compositor scheduling/presentation glue;
- software renderer/backend demotion fallback;
- `display.render_backend_mode` when it exists only for old fallback selection;
- obsolete `hw_accel`/fallback overlay policy;
- remaining physical-host transition/visualizer debris;
- obsolete presentation compatibility settings in the new Quick settings epoch.

No production switch back to the old presenter.

## Phase I — residual sweep

I should be small.

Remove only leftovers that could not safely leave with their owner:

- expired migration adapters;
- compatibility aliases;
- stale old-presenter utilities;
- obsolete tests/tools/comments;
- abandoned spike code.

Preserve product-neutral logic, real diagnostics and real resilience.

## Phase J

Archive/remove migration-only harnesses/planning material only after final validation evidence exists.

Historical evidence may remain under historical/evidence directories.
