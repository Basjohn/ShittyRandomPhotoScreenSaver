# R-58 — Move To Custom Copied Stale Backing Values Instead Of The Curated Runtime State

Date: 2026-08-08
Last updated: 2026-08-08
Status: Solved mechanically across every registered visualizer mode

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

Spectrum could run a curated preset correctly, but opening Settings and pressing
**Move To Custom** copied different technical values into Custom. The visible
Spectrum smoothing control initially behaved, yet later Settings recreation
could appear to restore the wrong response because the Custom fork started from
stale stored fields rather than the values the curated preset had supplied to
runtime.

The action itself is shared by all visualizer modes, so a Spectrum-only repair
would have left the same authority defect available to Oscilloscope, Sine Waves,
Bubble, and Spline Curve.

## Root Cause

Runtime resolves the selected curated preset as a replace-overlay before it
constructs the visualizer. Settings previously loaded the raw
`widgets.spotify_visualizer` mapping first. That mapping can retain old
mode-owned fields beneath a non-Custom preset index. The preset slider then did
exactly what it was designed to do: it switched to Custom and asked the parent
tab to snapshot the values currently held by the controls. The controls were
wrong because Settings and runtime had started from different authorities.

## Correction

`ui/tabs/widgets_tab_media.py::load_visualizer_settings()` now:

1. resolves the active mode and its selected preset index;
2. applies the same shared `apply_preset_to_config()` authority used by runtime;
3. loads every mode-specific UI section from that resolved mapping;
4. leaves the shared mode-neutral `VisualizerPresetSlider._move_to_custom()`
   behavior unchanged.

The correction therefore applies to all five registered modes. There is no
Spectrum-specific branch in the authority fix.

## Validation

- The shared authority correction landed in `94798add`; the explicit all-mode
  regression checkpoint is `1621e564`.
- Spectrum's exact stale technical-state case now survives Move To Custom,
  smoothing adjustment, save, Settings-tab destruction, and reconstruction.
- A parameterized runtime-shaped regression seeds stale backing values and a
  conflicting Custom cache for Spectrum, Oscilloscope, Sine Waves, Bubble, and
  Spline Curve. Every mode must display its explicit slot-0 curated technical
  values and copy those values into Custom.
- Bubble's mode-owned color fork remains covered separately.
- The `23:02–23:05` live run repeatedly recreated Custom Spectrum and preserved
  smoothing changes (`0.55`, `0.50`, `0.50`, then `0.60`). The logs do not emit
  the button click itself, so mechanical button-route coverage remains the exact
  proof of the action.

## Evidence

- `logs/evidence_chest/08_08_224a6817_main_mc_custom_settings_22_27/`
- `logs/evidence_chest/08_08_94798add_main_settings3_custom_spectrum_23_05/`
- `ui/tabs/widgets_tab_media.py`
- `ui/tabs/media/preset_slider.py`
- `tests/test_widgets_tab.py`

## Guardrail

When a stored preset index makes a curated preset authoritative, every editor,
preview, Custom fork, and runtime constructor must first resolve the same
curated replace-overlay. Never treat stale fields beneath a curated index as
the live state, and never fix this class of defect in only one mode when the
action is registry-shared.
