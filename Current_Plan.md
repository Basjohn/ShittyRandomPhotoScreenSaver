# Current Plan — Active Work

Last updated: 2026-09-10

Outside of Codex Work Began: `886e6fa419ff130ff2a9aedf5091ae6162d1e958`

The Qt Quick migration is closed and operator-accepted. This file contains **active work only**; completed Gmail lifecycle, widget resize/Edit lifetime, non-CUSTOM auto-shrink, Weather binding-loop validation, Visualizer replay-floor work, and other accepted closeout items are intentionally absent.

---

## 1. Voxel Sphere experimental acceptance pass

Execution authority: `Docs/Future_Work/Sphere_Visualizer_Decomposition.md`.

The face/bevel stability fix remains physically accepted. The 2026-09-10 hardware runs
after raw pre-AGC spectral onset, stable four-corner ingress, fragment interpolation and
energy-gated intake are the first passes the operator described as **reactive across the
board / alive** and then **a very good feeling place**. Protect that audio authority:
presentation work may not reduce onset frequency, packet strength, raw-pre-AGC freshness,
tracer travel or the accepted vocal-linked incoming bounce. The current narrow experiment
is detached-voxel travel semantics: real bounded cohorts for visibly slower intake plus an
optional reversed outtake/replacement presentation.

- [x] Preserve stable cube face identity/bevel UV selection from the **unrotated local
  face**. Broad light remains screen-X/Y anchored; no rotating normal regains face/UV
  authority.
- [x] Delete Sphere-local three-band `vocal_rise` / `bass_rise` fragmentation authority.
  Those support-shaped lanes re-armed continuously under real playback and are forbidden
  as generic packet sources.
- [x] Generic fragmentation now uses a Sphere-only **half-wave spectral-flux onset
  envelope over the existing temporally-unsmoothed pre-shape/pre-AGC analysis spectrum**,
  adaptive thresholding and local peak-picking. The tuple is copied lazily at the verified
  FFT commit boundary only while Sphere requests it; no second FFT/worker/timer/shared bus
  is added and accepted modes do not pay the tuple-allocation cost.
- [x] Typed vocal/kick/snare/onset events still outrank the generic spectral-onset path.
  Generic transient crest remains rotation/diagnostic evidence only and cannot detach
  cubes or spawn incoming particles.
- [x] Make one accepted fragment event visibly legible: packet release is shortened,
  admission remains sparse, and each event authors one strong region plus one weaker
  companion region rather than disappearing inside one octant. Accepted radial travel is
  not reduced.
- [x] Preserve the physically-good vocal-linked incoming bounce. Incoming remains
  independently typed/onset-owned. Distribution now uses four visible ingress quadrants:
  three remain near a ~46% deterministic admission floor while one dominant quadrant
  reaches ~70%; dominance walks on successive qualified events. This distribution layer
  does not replace fragmentation as the primary reactive reward.
- [x] Fix four-corner ingress population continuity. Stable voxel rank is now based only
  on voxel seed + visible quadrant; changing the dominant quadrant cannot re-hash the
  foundational ~46% population. Only the extra 24% fringe migrates, over a short ~110 ms
  crossfade, with a narrow per-voxel rank feather. This is a bug fix, not a user option.
- [x] Add canonical Sphere-only **Fragment Interpolation** option. Audio packet admission
  and target amplitude remain instantaneous; rendered section displacement follows that
  target through a ~30 ms critically-damped visual follower. No audio smoothing, frame
  blending, ghosting or motion blur is introduced. Default off globally; **Preset 6 on**.
- [x] Fix incoming admission so **playing state is never particle authority**. New incoming
  cohorts require a hysteretic live pre-AGC energy gate; true live silence cannot author a
  new cohort even if a stale/false typed event is present. Existing in-flight voxels are
  allowed to finish landing naturally. This gate is a bug fix and is always active.
- [x] Add optional Sphere-only **Intake Density** response. A qualified event snapshots the
  current live pre-AGC activity into a cohort density target; quiet active passages launch a
  smaller stable-ranked subset while strong passages approach the full 46/46/46/70
  four-corner population. Density is cohort-owned rather than continuously jittering with
  the energy lane. Default off globally; **Preset 6 on**.
- [x] Replace the old fake **Intake Velocity** scalar-decay presentation with a bounded
  four-slot Sphere-only **particle cohort** transport. Each qualified event captures stable
  voxel population, quadrant/lane, density, direction and a real normalized travel progress.
  New events do not globally reset in-flight cohorts; when all four slots are materially in
  flight the secondary reward coalesces rather than teleporting them. No timer/poller/worker/
  per-voxel Python objects.
- [x] Fix the remaining **binary particle-velocity authority**. Shared typed transient
  strength is retained for event admission only because it legitimately clamps strong events
  to 1.0. Sphere now derives continuous cohort motion intensity from a positive live-pre-AGC
  loudness jump plus raw-spectrum flux-over-threshold. A clamped event with flat local audio
  therefore stays slow/modest, while a real kick/vocal/drum jump may reach full travel speed.
  Ordinary intake is intentionally gentler (~1.90 s -> ~0.84 s across the continuous range)
  than outtake (~1.45 s -> ~0.82 s). Velocity-off uses fixed ~1.42 s intake / ~1.12 s outtake.
- [x] Keep optional Sphere-only **Particle Velocity** presentation. It changes captured
  cohort travel duration/curve from Sphere-local acoustic contrast rather than shared clamped
  event strength or exponential decay of one global incoming scalar. Event admission is
  unchanged. Intake fade-in is also progress-continuous and gentler at low motion intensity;
  recoil may still exceed the authored launch radius, but that over-launch tail fades through
  a narrow radial field instead of presenting as a hard clip. Default off globally; Presets
  **5 and 6 on** for operator A/B.
- [x] Add optional Sphere-only **Particle Outtake**. Direction is captured per cohort at
  launch. Intake cohorts begin detached and return to their own canonical shell slots.
  Outtake cohorts instead move selected shell voxels outward and fade them while a canonical
  replacement fades in underneath; renderer uses one optional second instanced draw of the
  same static voxel buffer, not a new geometry owner. Default off globally/Presets 1-5;
  **Preset 6 on** for physical A/B testing.
- [x] Swelling now reads from the existing **unsmoothed live pre-AGC energy seam**, not
  the dynamically-normalized 0..1 control lane or support-shaped Bubble motion feed.
  Sphere maintains a very slow local floor/peak and
  maps four visibly separated stages to a larger bounded body-growth range (up to ~42%
  safety cap at extreme Size Response). This remains a slow envelope, never a beat pulse.
- [x] Light Tracer is no longer free-running. Every accepted spectral/typed event queues
  one bounded angular step; backlog is capped and the visible ribbon advances with an
  explicit bounded phase velocity instead of asymptotic easing. While travel remains, its
  brightness is held above a stable floor; only after it reaches the target may it fade.
  Faster passages queue more distance and therefore move it faster within the cap, while
  silence settles cleanly. Renderer ribbon geometry is nearly constant through drive fades
  with broader cross-handoff to suppress the stationary-block flicker.
- [x] Gloss/Specular remain light-directed per-face finish only; literal Fill/Edge RGBA,
  independent edge alpha, Toon, reactive-only Rainbow Ghosting, flat Drop Shadow and
  Settings-only Finish presets remain unchanged.
- [x] **Reactive Voxel / Preset 6** remains the primary operator-validation authority.
- [x] **Preset 5 is now the operator-supplied `Transparent React` A/B preset.** Preserve its
  authored literal fill `[4,7,8,100]`, edge `[233,248,255,255]`, Custom finish and other
  non-technical presentation values. It carries the current technical reactivity toggles but
  keeps Particle Outtake OFF so Preset 5/6 provide a quick intake/outtake comparison.
- [x] Isolation remains binding: no accepted visualizer renderer/runtime, transient bus,
  timer or polling owner changed. `beat_engine.py` exposes two read-only seams only:
  demand-published `get_pre_agc_analysis_spectrum()` and live-float
  `get_live_pre_agc_energy_bands()`. The spectrum copy is skipped entirely unless a
  consumer requests it.
- [x] Operator reports the energy-gated four-corner pass is now in a **very good feeling
  place**. Preserve the current fast musical reactivity/motion; do not retune onset,
  fragmentation, tracer travel, stable ingress identity or vocal bounce while calibrating
  intake presentation.
- [x] Modest intake calibration: require roughly **20% more acoustic evidence** before the
  recently-added intake layer reaches its strongest presentation. Gate open/close and typed
  force floor remain 0.090/0.042/0.030 and full density remains 1.50 while the four-corner
  minimum is unchanged. The superseded event-strength velocity gate is removed: it proved
  insufficiently granular once hardware showed the shared event lane reaching 1.0 for both
  modest and genuinely large attacks.
- [x] Focused Sphere/technical gate: **72 passed** with explicit raw-spectrum publication,
  live-pre-AGC swell, bounded tracer travel/settle, continuous acoustic-impact velocity,
  intake over-launch fade field, Preset-5 A/B authority, direction capture and outtake/
  replacement regressions.
- [ ] Operator physically A/B **Preset 5 Transparent React (Intake)** against **Preset 6
  Reactive Voxel (Outtake)**. Verify flat/low transients still author visible cohorts but move
  substantially more gently than obvious vocal/kick/drum peaks; intake fades in more gently,
  vocal recoil retains its full reactive push without hard clipping beyond launch radius,
  outtake remains pleasant, and fragmentation/tracer/audio authority is unchanged.


## 2. `dark.qss` retirement → ThemeSpec sole authority

Execution authority: `Docs/Settings_Dark_QSS_Retirement.md`.

Migrate the Settings dialog's remaining colour **and** structure authority out of
`themes/dark.qss` into `SettingsThemeSpec`, leaving ThemeSpec as the sole Settings GUI
style authority. Preserve the accepted dark-theme appearance and eliminate the
competing stylesheet authority completely.

- [ ] Inventory every remaining selector/property in `themes/dark.qss` against current
  `SettingsThemeSpec` ownership.
- [ ] Move required structural and colour semantics into the ThemeSpec-backed path
  without creating a second fallback authority.
- [ ] Delete `themes/dark.qss` once no runtime/build path requires it.
- [ ] Preserve dark-theme appearance with focused regression coverage and physical
  Settings GUI validation.
- [ ] Confirm widget themes/runtime theming remain unaffected by the Settings-only
  authority retirement.

---

## 3. Test / debris reconciliation

Owned in detail by `Docs/TestSuite.md` and `Future_Cleanup.md`.

- [ ] Delete the caller-dead `widgets/spotify_visualizer/renderers/` island and
  `rendering/image_processor.py` after splitting any mixed tests that still rely on
  them; then restore the two relaxed removal assertions in
  `test_defaults_schema_authority.py`.
- [ ] Run the broad `pytest tests/` inventory and reconcile remaining stale
  widget-glow / two-phase-retirement / defaults casualties against current owners.
- [ ] Reconcile nine Clock presentation tests whose shadow fixtures omit current
  required fields. Do **not** add production defaults merely to satisfy old fixtures.
- [ ] Reconcile 21 scene-controller cases whose fixtures omit the 11 current required
  style arguments.

---

## Standing guardrails

- **Visualizer fidelity / scaling (R-69, binding):** extreme CUSTOM geometry must
  never be solved by globally reducing head radius, authored reaction amplitude,
  motion, Ghost/history displacement, or by adding a second viewport/domain
  compensation that makes wide/tall modes less reactive. Bubble is the golden
  reference; tall-Spectrum response protection is equally binding.
- **Live CUSTOM ownership:** CUSTOM outer geometry is Python/session-owned; QML
  reports gesture intent only. One operation publishes one coherent
  rectangle/extent/scale. Visualizer sides = one-axis viewport extent; corners =
  independent X/Y extent; wheel = uniform whole-Visualizer scale. **Save is not a
  teardown boundary.**
- **CUSTOM is global layout mode:** the first widget entering CUSTOM disables authored
  stacking/adjacency globally, including number-key saved-layout load. Visualizer
  preset `Custom` is a separate concept.
- **Media ownership:** GSMTC/event ownership is primary; no fast Media polling or
  process-probe fallbacks. Visualizer consumes Media admission but never acquires a
  second Media owner.
- **Performance admission:** freshness/reactivity and latency-tail quality outrank
  prettier aggregate counters; no optimization may silently lower authored quality;
  prefer fewer/event-owned mechanisms over polling. See
  `Docs/Guardrails/Performance_Optimization_Contract.md`.
- **Defaults SSOT:** `core/settings/default_settings.py` is the sole authority;
  `.json`/`.sst` are derived and audit-gated. Never add a second default authority.
- **No fallback architecture:** failures should remain explicit and diagnosable; do
  not solve closeout work by adding silent fallback ownership, timers, or pollers.

## Authority order

```text
exact current source + current reconciled test tree
-> Current_Plan.md (this file: active work + order)
-> Spec.md
-> FWPlan.md (future / non-blocking implementation)
-> Future_Cleanup.md / Docs/TestSuite.md (cleanup + test truth)
-> Docs/Index.md + focused/decomposition docs
```

## Durable references

- `Docs/Index.md` — routing map to current owners.
- `Docs/TestSuite.md`
- `Future_Cleanup.md`
- `FWPlan.md`
- `Docs/Settings_Dark_QSS_Retirement.md`
