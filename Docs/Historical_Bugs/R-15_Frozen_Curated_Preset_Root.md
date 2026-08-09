# R-15 — 2026-04-18 — Frozen Curated Presets Silently Fell Back to Onefile Tree (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Symptoms**
- Normal/frozen runtime could load curated visualizer presets from onefile extraction paths under `%LOCALAPPDATA%` instead of shared curated content.
- MC path behavior could appear correct while SCR path drifted to older bundled payloads, causing cross-build preset mismatch on the same machine.

- **Root cause**
- `core/settings/visualizer_presets.py::_presets_root()` allowed frozen-mode fallback to `_bundled_presets_root()` when shared-root bootstrap failed.
- Bootstrap failures were debug-logged and then masked by that fallback, so runtime stayed functional but silently selected the wrong preset source.

- **Fix**
- Frozen-mode root resolution is now strict-canonical:
  - always resolve to `%ProgramData%\SRPSS\presets\visualizer_modes`
  - attempt bootstrap from bundled shipped tree only as a copy source
  - never return bundled/onefile paths as active curated root
  - never return bundled/onefile paths as active curated root
- Added regression tests to lock this behavior, including bootstrap-failure and missing-bundled scenarios.

- **Why this worked**
- It removed ambiguous runtime source selection entirely: frozen curated reads now have one authoritative root regardless of bootstrap outcome.
- This aligns SCR and MC with the same machine-wide curated preset contract.

## Record Provenance

This standalone file preserves the complete former inline `R-15` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
