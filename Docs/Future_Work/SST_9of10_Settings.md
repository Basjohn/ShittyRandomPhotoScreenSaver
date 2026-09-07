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
- [x] Review the 59 changed default values; classify intended vs regression
  (audit 2026-09-07). Breakdown:
  - ~45 `ui.*_bucket_states` / `*_tech_states` True->False: collapse-on-fresh-install.
    Cosmetic, intended-by-design.
  - `spotify_visualizer.mode` devcurve->bubble: intended (devcurve is a dev mode).
  - **Behavioural — operator DECIDED 2026-09-07:**
    - `widgets.*.monitor` ALL/2 -> '1': KEEP migrated '1' (safe on any install).
    - `accessibility.dimming` -> RESTORED ON @ opacity 15 (commit; parity restored).
    - `accessibility.pixel_shift.enabled` False: KEEP migrated OFF.
- [x] **Missing-preset fallback: operator chose HONOR CANONICAL** (2026-09-07).
  Pre-migration returned 0 (first slot) for every mode; the migration honors the
  shipped canonical `preset_<mode>` (sine_wave 4, others 0), clamped to curated
  range. Kept the resolver; updated the 5 plumbing tests to the canonical
  contract. `test_visualizer_settings_plumbing.py` fully green (91 passed).

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
Triage done (2026-09-07). The "347" is inflated by cross-test Qt contamination in
the big -k batch + display-gated noise; isolated settings clusters:
plumbing 25, presets 13, settings_manager 9, transient 6, gmail 6 (~59 real).
Root breakdown (from settings_plumbing sample):
- **Test-mock staleness (majority):** local `_Tab`/`_DummyTab`/`Host` mocks lack the
  migration's strict API -- `_config_bool`/`_default_int` now require a `default`
  arg; new `_default_str`/`_widget_default`/`_default_bool`. Production is the new
  strict owner; UPDATE the mocks. Mechanical, no design input, restores the safety
  net. (~40+ of the 59.)
- **Migration-internal test inconsistencies (need operator intent):** e.g.
  `resolve_audio_block_size("bubble") == 512` while canonical `bubble_audio_block_size`
  is (and always was) 128; sine_wave preset/fallback index `== 0` vs canonical 4.
  These are CHECKPOINT7 WIP where the test and the canonical disagree -- fixing the
  wrong side changes real audio/preset behavior. **Blocked on operator decision.**
- Prior wind-down: lane-energy 0.0, ordinary_widget_host shiboken6 source-scan +
  two-phase retirement.

Confirmed NOT regressions vs pre-migration: canonical default *values* for
block_size/preset are unchanged; `resolve_audio_block_size` is byte-identical to
the pre tree.

### Cluster status (2026-09-07)
- [x] `test_visualizer_settings_plumbing.py` — GREEN (91). Mock staleness ->
  CanonicalWidgetDefaultsStub; retired `*_growth` dropped; canonical preset
  fallback; block_size literal 512->128.
- [x] `test_visualizer_presets.py` — GREEN (58). Fail-loud curated/override
  contract; `_seed_curated_slots` helper; sphere release artifact regenerated.
- [ ] `test_settings_manager.py` (~9), `test_transient_preset_preservation.py`
  (~6), `test_gmail_settings_roundtrip.py` (~6) — pending triage.

### Production bugs found & fixed during reconciliation
- preset-repair `_normalize_spectrum_linear_notches` missing canonical_default
  (both tool callers) — would crash preset repair on any spectrum payload.
- `technical_controls` transient-mix default_key doubled the two-token
  `sine_wave_` prefix (`sine_wave_wave_transient_width_mix`) -> fail-loud KeyError
  crashing the sine_wave Settings body.

## Phase 4 — 9/10 architecture upgrades (no parity/feature loss)
- [ ] Kill the literal-vs-derived dual representation: schema GENERATES the
  canonical set (retire the parity test; one artifact, drift impossible).
- [ ] Explicit `required` vs `derivable-from-reference` tags on keys (sphere-class
  derivations are declared, not implicit).
- [ ] One-time large-migration reset gated on a settings_v2 schema-version stamp
  (fires once, never re-wipes).
