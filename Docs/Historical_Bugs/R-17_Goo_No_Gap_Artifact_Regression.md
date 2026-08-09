# R-17 — 2026-04-18 — Goo No-Gap/Artifact Regression Family (Resolved In Dev-Gated Path)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Symptoms**
- Goo rendered as disconnected edge blobs or rigid circles instead of coordinated center+border liquid.
- White highlight layer showed block/noise artifacts.
- Liquid could escape visual card limits or visually clip inconsistently.
- Center and inward border systems could visually merge, violating the explicit "never touch" rule.

- **Root cause**
- Single-field Goo architecture could not model border-vs-center pressure balancing or hard-gap behavior.
- Shader used hash/floor noise specular gating and lacked strict rounded-card clipping across all compositing passes.
- Runtime transport only carried one source field, so center/edge semantics were not representable.

- **Fix**
- Replaced single Goo field with a dual-field solver (`edge_liquid`, `core_liquid`) and per-tick gap invariant enforcement.
- Added pressure-coupled retreat/compression controls and mode-local settings (`goo_gap_min`, `goo_edge_pressure`, `goo_core_pressure`).
- Upgraded renderer/upload contract to dual vec4 arrays (`u_goo_edge_sources`, `u_goo_core_sources`) plus gap/boundary uniforms.
- Rewrote Goo shader compositing with strict rounded-card clipping, overlap barrier, vector contour stack, and smooth ribbon-style speculars (no block-noise path).
- Added regression coverage for solver invariants and Goo shader compile/contract checks.

- **Guardrail**
- Any future Goo change must preserve these invariants before runtime ask:
  - edge/core liquids never merge
  - no out-of-card pixels
  - no hash/floor specular artifact path

- **Follow-up regression noted 2026-04-18 (still open for visual sign-off)**
- **Observed pattern:** even after dual-field landing, runtime could still render disconnected "oval islands" and a hollow/weak center instead of pooled mock-like sheets.
- **Contributing causes:**
  - field influence had an effective hard radius cutoff, so neighboring sources did not fuse into fluid structures
  - center-void trim was too aggressive and suppressed core liquid visibility
  - evenly distributed core seeding reinforced ring/donut artifacts
- **Corrective direction now applied:**
  - switched Goo field influence to long-tail blending in shader so sources can merge naturally
  - reduced center-void trim to contour shaping (not center suppression)
  - randomized core angular homes and increased core depth/radius envelope to avoid stable ring lock
- **Loop-avoidance reminder:** if Goo resembles isolated circles, do not tune "hotness" first; inspect field kernel tail, threshold range, and center-void suppression as the first triage path.

## Record Provenance

This standalone file preserves the complete former inline `R-17` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
