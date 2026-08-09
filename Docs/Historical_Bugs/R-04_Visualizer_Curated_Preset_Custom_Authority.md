# R-04 — 2026-04-18 — Visualizer Curated Preset Selection Reused Custom Runtime Values (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final resolved state:** selecting a curated visualizer preset now deterministically applies curated values, and selecting Custom applies custom values only.
- **Observed failure pattern:**
  - curated preset selection sometimes behaved like a hybrid of curated + prior custom/live runtime values
  - one problematic example was Bubble preset changes where `manual_floor`/`audio_block_size` continued reflecting stale custom values, degrading reactivity and making presets look "wrong"
- **Root cause:**
  - `SpotifyVisualizerSettings.from_mapping()` applied `apply_preset_to_config(...)` and then re-applied a broad runtime override set through `_restore_explicit_visualizer_runtime_overrides(...)`
  - this post-overlay restore step could stomp curated payload values with stale source mapping values
  - additionally, `apply_preset_to_config(...)` preserved mode technical keys not present in curated payloads, allowing more hidden carry-over
- **What finally worked:**
  - removed the post-overlay runtime override restore pass from model hydration
  - tightened curated apply semantics to clear all mode-specific keys not present in the curated payload before applying curated settings
  - kept Custom slot semantics unchanged (`Custom` remains pass-through for user-authored state)
- **Why the final solution worked:**
  - it enforces one authoritative source per selection path:
    - curated index -> curated payload
    - custom index -> custom payload
  - there is no longer a second merge phase that can re-introduce stale state after curated application
- **Regression guards added:**
  - curated apply clears mode keys absent from curated payload
  - curated `from_mapping` values win over saved custom/runtime values
  - custom `from_mapping` preserves custom values
- **Takeaways:**
  - do not add post-overlay re-merge phases in visualizer preset hydration
  - if curated presets are selected, partial technical carry-over from prior custom state is a correctness bug, not a convenience feature

## Record Provenance

This standalone file preserves the complete former inline `R-04` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
