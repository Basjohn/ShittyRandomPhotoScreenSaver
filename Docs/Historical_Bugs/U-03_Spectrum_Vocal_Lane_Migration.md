# U-03 — 2026-04-08 / 2026-04-25 — Non-Mirrored Spectrum Vocal Lane Still Missing After Claimed Landing (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Resolution date:** 2026-04-25
- **Root cause:** the original migration only promoted one exact stock old linear layout. If a user's old `Bass / Low / Mid / Hi-Mid / Treble` family had been nudged even slightly, it bypassed migration and kept surfacing the stale labels. A stale runtime/widget default also still carried the old linear label family.
- **Fix applied:** migration now promotes legacy-shaped five-lane linear layouts lacking `Vocal` even when the user previously moved the boundaries, preserving those user positions while renaming the old `Low`/`Mid` family into `Low-Mid`/`Vocal`. Widget/model defaults were also updated so fresh/runtime paths stop reintroducing the stale labels.
- **Validation status:** user-confirmed resolved in editor UI and runtime.

## Record Provenance

This standalone file preserves the complete former inline `U-03` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
