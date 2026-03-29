# Visualizer Baseline Tuning Matrix

Use this with [Visualizer_Signal_Contract.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Signal_Contract.md) and [Visualizer_Reset_Matrix.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_Reset_Matrix.md).

This is the canonical cross-mode baseline sheet for:
- floor strategy
- AGC / normalization expectations
- transient role
- scheduler role
- likely failure modes

## 1. Cross-Mode Baseline

| Mode | Preferred block size baseline | Floor / normalization baseline | Primary continuous driver | Transient role | Scheduler role | Main failure mode to watch |
|------|-------------------------------|--------------------------------|---------------------------|----------------|----------------|----------------------------|
| `spectrum` | `256` or `128` when hardware tolerates it | dynamic floor on by default, anti-drift normalization must still allow real lane collapse | lane-routed bass / mid / treble under authored shape | kick lane express help, not whole-bar monolith boost | kick confirmation only | shape survives but all lanes move together over time |
| `bubble` | `256` | dynamic floor on, smooth stream envelope over raw volatility | mid / high sustained energy for stream speed, bass for pulse support | pulse accents and promotions | one-shot promotion assist | stream speed feels detached or too jerky relative to pulse |
| `blob` | `256` | manual floor and overlay-local smoothing must survive hitches | bass + overall for size/stage, mid/high for wobble | reinforce the same live bands, never replace them | kick -> stage/impact, snare -> wobble help | brief giant pulses, snap-back, or ghost/live mismatch |
| `sine_wave` | `256` | shared engine smoothing plus mode-local assist smoothing | continuous line energy and heartbeat floor | width/amplitude widening | beat-confirmed line assist | nothing-then-spike feel, or Osc fixes bleeding into Sine |
| `oscilloscope` | `256` | waveform freshness matters more than AGC feel | actual waveform samples plus support bands for glow | width/sensitivity assist | beat-confirmed line assist | stale/short waveform frames looking half-dead |

## 2. Tuning Guardrails

### 2.1 Continuous energy first

- Continuous energy should define where a mode lives most of the time.
- Transient bus should add speed/punch, not become the primary identity.
- Scheduler events should confirm hits and help weak onsets, not overpower calm passages.

### 2.2 Smoothing ownership

- Engine smoothing owns shared bar/waveform stability.
- Overlay/local smoothing owns mode-specific feel:
  - Blob event envelope and live-band filtering
  - Bubble stream envelope
  - Sine/Osc line assist smoothing
- If a bug only affects one mode, prefer fixing its local smoothing before touching shared engine policy.

### 2.3 Validation presets

- Spectrum:
  - use shaped presets where lane collapse is easy to see
- Bubble:
  - use a preset with obvious stream motion, not only pulse inflation
- Blob:
  - `Preset 1 (The Mighty Blob)` is the canonical validation preset
- Sine/Osc:
  - validate both mode switch behavior and steady-state feel, not just isolated beats

### 2.4 Preset-1 Synthetic Migration Guard

- The repo now carries a deterministic preset-1 baseline snapshot for all active modes:
  - data: [tests/data/visualizer_preset1_baselines.json](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\tests\data\visualizer_preset1_baselines.json)
  - generator: [tests/visualizer_preset1_baseline_utils.py](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\tests\visualizer_preset1_baseline_utils.py)
  - regression test: [tests/test_visualizer_preset1_baselines.py](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\tests\test_visualizer_preset1_baselines.py)
- Primary use:
  - record current curated preset-1 behavior before structural refactors such as `VIZ-AUD-015`
  - rerun after the refactor to confirm preset plumbing and per-mode reactions still match the recorded baseline within tolerance
- Governance rule:
  - if a curated preset 1 is intentionally reauthored, update the recorded baseline snapshot in the same change
  - do not "fix" a failing baseline test by loosening tolerances unless the generated metrics are genuinely too noisy to act as a migration fence
  - do not treat older `HEAD` preset JSON as more authoritative than the current curated file; authored preset content in the working tree is the source of truth

## 3. Retired Authored Keys

These keys are no longer canonical authored outputs:
- `energy_boost`
- `use_raw_energy`

Policy:
- curated repair, preset save/export, and the shipped preset tree must stay free of them
- current authored preset content in the repo is the source of truth, not any older compat-bearing snapshot
- if they still exist elsewhere in the runtime/settings schema, retire them deliberately there rather than preserving them as preset-authoring inputs

## 4. Governance

Whenever one of these changes:
- signal ownership
- reset ownership
- preset authored shape
- mode baseline defaults

update all of:
- [Index.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Index.md)
- [Spec.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Spec.md)
- [Current_Plan.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Current_Plan.md)
- [Docs/Historical_Bugs.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Historical_Bugs.md)
- [Docs/Visualizer_System_Audit/00_Audit_Index.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\Docs\Visualizer_System_Audit\00_Audit_Index.md)
