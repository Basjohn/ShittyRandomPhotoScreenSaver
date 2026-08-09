# R-16 — 2026-04-18 — One-Dir Runtime Misdetected As Script + Curated Slot Drift (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Symptoms**
- Frozen Main build sometimes resolved visualizer preset save/edit defaults into extracted onefile paths.
- Preset slider labels could drift from the file opened by "Edit Preset" when curated JSON payloads carried mismatched `preset_index` values.

- **Root cause**
- `core/settings/visualizer_presets.py::_is_frozen_build()` used a narrower detection contract than `main.py`, so some one-dir runtimes were treated as script mode.
- Curated preset parsing trusted embedded `preset_index` before filename slot inference, so malformed payload indices could remap in-memory preset slots even when filenames were correct.

- **Fix**
- Unified frozen detection behavior with `main.py` semantics, including executable-name detection (`SRPSS*` / `.scr`) for runtimes where `sys.frozen` is absent.
- Added one-dir extraction-path guard: when bundled roots include a `onefile` segment, preset roots are treated as frozen-style and pinned to shared ProgramData roots.
- Hardened curated parsing to prefer filename-derived slot (`preset_N_*.json`) over payload index, while snapshot override parsing keeps payload-index behavior.
- Added regression tests for both detection paths and filename-slot precedence.

## Record Provenance

This standalone file preserves the complete former inline `R-16` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
