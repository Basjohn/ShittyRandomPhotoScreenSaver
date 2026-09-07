# Visualizer replay — reactivity minimum bar (recreate for this environment)

Live checklist. Delete items as they land; this is not a changelog. Owner-linked
from `Current_Plan.md`.

## What this is (and, emphatically, what it is not)

The Qt Quick migration deleted the replay harness (`tests/test_visualizer_replay.py`)
but left its assets: **67 goldens** under `tests/goldens/visualizer_replay/v1/`
(13 synthetic fixtures × modes), each carrying **32 quantitative reactivity
metrics** (`attack_slope_per_s`, `bar_flux`, `bar_peak`, `beat_count`,
`bubble_radius_excursion`, `bubble_particle_peak`, …), replay `frames`, a digest,
a presentation trace, and a hash-verified `manifest.json`. The goldens are
currently inert — nothing runs them.

This task recreates a harness **for the current headless environment**
(`QT_QPA_PLATFORM=offscreen`) that replays the fixtures through the *current*
logical tick + overlay path and enforces those metrics as a **reactivity minimum
bar**.

It is explicitly a floor, not a ceiling:

- **Current reactivity should pass it.** Per operator physical experience the
  live visualizer reactivity is good; the thresholds are set *below* current
  measured reactivity so today's build passes with margin.
- **It must never destroy or constrain what we have now.** It only ever helps:
  it catches a genuine reactivity *regression* or recovers us from a mistake. It
  is not an exact-pixel/byte golden and must not fail on legitimate tuning (e.g.
  the DevCurve travel change) that stays above the floor.
- **No runtime coupling.** The harness asserts in tests only; it never gates or
  alters runtime behaviour, and adds no timer/poller to production.

## Why metric floors, not exact goldens

The captured goldens predate recent intentional changes (e.g. DevCurve travel now
driven by de-kicked transients), so their exact `frames`/`digest` will not
reproduce and *should not* be expected to. Exact-match goldens would fail on every
legitimate tuning and pressure us to re-bless drift — the opposite of a minimum
bar. The durable contract is the **quantitative metrics as per-fixture/per-mode
minimums** (with a few upper bounds where "should be quiet" is the point, e.g.
silence). The frames/digests may be refreshed as a reference measurement, but the
*assertions* are thresholds derived from a current, healthy run.

## What the deleted harness did (recover the useful behaviour)

From its former test ids: replay all supported modes through the **actual tick and
overlay path**; golden drift detection; metrics are **quantitative and sane**; the
presentation schedule **does not change the logical series** (stalls don't alter
logical output); a reviewable PNG/HTML artifact writer; a bootstrap that requires
acknowledgement and refuses to overwrite; and **fixture hash-tamper rejection**
(fixtures are immutable, integrity-checked via `manifest.json`).

Keep the integrity properties (immutable hash-verified fixtures, headless, no Qt
window) and the "presentation schedule never changes the logical series" invariant.
Replace exact golden-drift with metric-floor assertions.

## Plan

- [ ] **Rebuild the replay driver** (`tests/test_visualizer_replay.py` or a small
  `tests/visualizer_replay/` package) that, per fixture, feeds the synthetic audio
  features through the current logical tick + overlay path for each mode, headless
  (`QT_QPA_PLATFORM=offscreen`), producing the same 32-metric block the goldens
  use. Verify fixture integrity against `manifest.json` first (reject tamper).
- [ ] **Take a current healthy reference run** and record the measured metrics.
  This is the calibration pass — operator confirms reactivity is good, so these
  numbers define "healthy". Refresh the goldens' metric block from this run if
  desired; keep the fixtures themselves immutable.
- [ ] **Derive minimum-bar thresholds** below the healthy measurements (with
  margin) per fixture/mode. Examples of the *shape* (tune to real numbers):
  - beats_* → `bar_flux ≥ floor`, `beat_count ≥ n`, an attack is present;
  - isolated_impulse / sudden_volume_step → `attack_slope_per_s ≥ floor`;
  - silence → motion metrics ≈ 0 (**upper** bound — the one "must stay quiet");
  - sustained_bass / sustained_treble → energy lands in the correct lane;
  - broadband_noise → broad, non-degenerate response;
  - bubble mode → `bubble_radius_excursion` / `bubble_particle_peak` ≥ floor;
  - DevCurve → travel responds to sustained transient activity but is bounded
    (consistent with the ±10% cruise contract and no per-kick jerk).
- [ ] **Assert floors, not equality.** A mode/fixture passes when it meets its
  minimums; it fails only when reactivity drops below the floor (a regression).
- [ ] **Preserve the logical-vs-presentation invariant**: replaying with injected
  stalls must not change the logical metric series.
- [ ] **Keep the artifact writer optional/diagnostic** (reviewable PNG/HTML) —
  never a required gate, and off by default so CI stays fast/headless.
- [ ] **Negative control**: a deliberately broken reactivity (e.g. zero a lane,
  freeze travel) must fail the matching floor — proving the bar actually bites.

## Acceptance

- Current build passes every floor with margin (matches operator physical
  experience that reactivity is healthy now).
- A synthetic reactivity regression fails the specific floor it violates.
- No exact-pixel/byte requirement; legitimate tuning above the floor never fails.
- Headless, deterministic, no production runtime coupling, no added timers/pollers.
