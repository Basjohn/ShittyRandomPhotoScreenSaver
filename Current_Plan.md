# Current Plan — Active Work

Last updated: 2026-09-10

Outside of Codex Work Began: `886e6fa419ff130ff2a9aedf5091ae6162d1e958`

The Qt Quick migration is closed and operator-accepted. This file contains **active work only**; completed Gmail lifecycle, widget resize/Edit lifetime, non-CUSTOM auto-shrink, Weather binding-loop validation, Visualizer replay-floor work, and other accepted closeout items are intentionally absent.

---

## 1. Voxel Sphere experimental acceptance pass

Execution authority: `Docs/Future_Work/Sphere_Visualizer_Decomposition.md`.

The face/bevel stability fix remains physically accepted. The 2026-09-10 hardware run
after raw pre-AGC spectral onset + four-corner ingress is the first pass the operator
described as **reactive across the board / alive**. Protect that audio authority: this
continuity pass may not reduce onset frequency, packet strength, raw-pre-AGC freshness or
the accepted vocal-linked incoming bounce. The current problem is perceptual jerk from
hard geometry/population state changes, not insufficient musical detection.

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
- [x] **Reactive Voxel / Preset 6** remains the operator-validation authority.
- [x] Isolation remains binding: no accepted visualizer renderer/runtime, transient bus,
  timer or polling owner changed. `beat_engine.py` exposes two read-only seams only:
  demand-published `get_pre_agc_analysis_spectrum()` and live-float
  `get_live_pre_agc_energy_bands()`. The spectrum copy is skipped entirely unless a
  consumer requests it.
- [x] Focused Sphere/technical gate: **62 passed** with explicit raw-spectrum publication,
  live-pre-AGC swell and bounded tracer travel/settle regressions.
- [ ] Operator physically validate Preset 6 with **Fragment Interpolation on**: preserve
  the newly accepted fast musical reactivity while reducing whole-image jerk; dominant
  ingress should migrate without global population swaps, fragment geometry should begin
  on the event frame but travel continuously, and the vocal bounce must remain intact.


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
