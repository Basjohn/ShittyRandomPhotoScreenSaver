# R-05 — 2026-04-18 — Visualizer Preset Slot Label Mismatched Edit Target (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Observed failure pattern:**
  - preset slider labels could disagree with `Edit Preset` target file
  - `Save Preset As…` default path could drift back toward onefile extraction-like roots in some one-dir runtime shapes
- **Root causes:**
  - onefile extraction path detection was too strict (`part == "onefile"`), so prefixed extraction folder names could bypass shared ProgramData root enforcement
  - curated parser trusted embedded payload `name` too much, allowing stale authored metadata to mislabel slots despite filename slot correctness
  - `get_preset_file_path()` used `first-match` filename lookup while curated slot loading used `last-wins` index overwrite behavior; duplicate-slot files could therefore produce label/file divergence
  - snapshot override payload names could rename curated slot labels, even when `Edit Preset` still points to curated files
- **What fixed it:**
  - broadened onefile extraction detection to any segment starting with `onefile`
  - curated parsing now prefers filename-derived names and slot indices
  - file-open path resolution now follows the same parser/precedence as curated slot loading
  - snapshot overrides now replace settings only for existing curated slots and preserve curated labels
- **Why the final solution worked:**
  - all user-facing slot surfaces (label, slot assignment, edit file path) now use one consistent slot-resolution contract
  - root resolution no longer relies on a brittle exact folder-name check
- **Guardrails/tests added:**
  - onefile-prefixed runtime path resolves to shared ProgramData
  - curated filename-name precedence test
  - duplicate-slot file path precedence parity test
  - snapshot override cannot rename curated slot labels

## Record Provenance

This standalone file preserves the complete former inline `R-05` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
