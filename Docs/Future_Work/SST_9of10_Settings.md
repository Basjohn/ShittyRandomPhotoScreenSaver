# SST 9/10 Settings — live checklist (Strategy B)

Goal: a 9/10 single-authority, fail-loud SST settings system that behaves as well
as the pre-migration build, with none of the migration rot. Chosen over revert (C)
because the harness proved the defaults migration is fundamentally sound.

Oracle: `deleteme/PreSettings` (known-good pre-settings-migration tree, ~2026-09-05).
Audit: `python tools/settings_migration_audit.py` (0 blocking gaps as of 2026-09-07).

## Phase 0 — Baseline (DONE)
- [x] Build pre-migration-oracle harness (`tools/settings_migration_audit.py`).
- [x] Confirm defaults migration sound: 0 dropped-needed defaults, 0 unresolved
  runtime-resolvable keys. The 370 "dropped" were runtime/session state correctly
  purged (367) + retired-by-design (_growth, dead glow/line keys).

## Phase 1 — Lock the defaults gate (9/10 completeness proof)
- [ ] Permanent regression test wrapping the harness's resolve-gap check (no
  reference tree needed): descriptors + per-mode×key + literal call-sites must all
  resolve to a canonical default or be derivable-by-design. This is the proof that
  makes fail-loud safe.
- [ ] Review the 59 changed default values; classify intended vs regression.
  Known-intended: UI bucket-states True->False (collapsed), spotify_visualizer.mode
  devcurve->bubble. **Flag for operator:** `widgets.*.monitor` normalized ALL/2 -> 1
  (fresh-install default now single-monitor) — confirm intended.

## Phase 2 — Behavioral runtime regressions (post-migration, operator-felt)
Not defaults problems; code regressions from the migration's broad rewrite.
- [x] **Visualizer never receives audio** — FIXED (c9b25510). Real root: playback
  IS detected at runtime (`VIS_PLAYBACK_EDGE playing=True`), but the migration left
  7 more `_COMPUTE_SNAPSHOT_ATTRS` unseeded in `audio_worker.__init__`
  (`_bar_gate_prev1/2/output`, `_last_raw_bass/mid/treble`, `_prev_raw_bass`), so
  `make_compute_snapshot` raised every frame -> `engine=0/0` -> the tick fell back to
  synthetic idle energy. Seeded all snapshot attrs; regression test added
  (test_visualizer_compute_lanes). **Operator: confirm reactivity with Spotify
  playing.**
- [ ] Cursor halo "doesn't work": teardown state shows `halo_enabled: True,
  halo_shape: 'cursor_light', native_cursor_visible: False, motion_visible: True`
  in a healthy generation (off only while the context menu is open, which is
  expected). No static fault visible -> needs an operator run to confirm whether
  it renders; then diff cursor/halo path vs pre tree if still broken.
- [ ] Context-menu / transition "brief stall": observed as `Tick dt spike_ms=224/73/46`
  first-frame/transition-start spikes (known GIL-held-C-call hitch class). Needs a
  pre-vs-now `--perf` comparison to confirm it's a migration regression vs
  pre-existing warmup.
- [ ] (operator: "cannot list everything") — remaining runtime behaviors: capture
  a fresh `main_mc.py --debug --perf --viz --usage --life --cache --set` run and
  triage sidecars.

## Phase 3 — Stale test reconciliation
- [ ] Triage the ~347 focused settings/visualizer/widget failures: separate
  contract-staleness (update to current owners) from real regressions (fix at the
  owning boundary). Prior wind-down items: lane-energy 0.0, ordinary_widget_host
  shiboken6 source-scan + two-phase retirement, `_pre_agc` families.

## Phase 4 — 9/10 architecture upgrades (no parity/feature loss)
- [ ] Kill the literal-vs-derived dual representation: schema GENERATES the
  canonical set (retire the parity test; one artifact, drift impossible).
- [ ] Explicit `required` vs `derivable-from-reference` tags on keys (sphere-class
  derivations are declared, not implicit).
- [ ] One-time large-migration reset gated on a settings_v2 schema-version stamp
  (fires once, never re-wipes).
