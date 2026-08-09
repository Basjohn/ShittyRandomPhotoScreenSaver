# U-06 — 2026-04-30 — Multi-Monitor MC Shadow Cache Corruption On Focus Loss (Unresolved)

## Classification

- [ ] COMPLETELY FUCKED
- [x] ACTIVE
- [ ] AWAITING VALIDATION
- [ ] SOLVED

- **Observed runtime symptom:** in MC mode, clicking into SRPSS on Display 1 and then clicking into anything on Display 0 frequently corrupts widget shadows/shadow caches until clicking back into SRPSS restores them through existing mitigations.
- **Current suspicion:** this is a visual Qt `QGraphicsEffect`/pixmap-cache corruption path triggered by multi-monitor focus/activation changes, not a property-level effect state change that Qt exposes cleanly. Normal logs cannot currently say "shadow corrupted" with certainty unless we add external visual or pixel-based observation.
- **Immediate correction made:** Gmail was missing from `rendering/widget_effects.py`'s peer-widget overlay-effect invalidation cadence. Add `gmail_widget` there so Gmail no longer sticks out when the existing mitigation fires.
- **Research/implementation guardrails:**
  - Do not regress the MC focus restore/key fix from U-05.
  - Do not apply broad focus-policy changes across widget trees; prior H1 work caused worse shadow corruption by destabilizing Qt focus routing.
  - Do not alter visual fidelity or global shadow styling as a first response.
  - Compare any proposed permanent fix against the Phase E effect-corruption history below and against R-18/flicker lessons before touching top-level window flags, focus routing, or graphics effects.
- **Next target:** inspect recent `/logs` around focus loss/cross-display click sequences and add low-noise diagnostics around effect invalidation reasons, screen index, focus owner, and widget effect participation. If the visual corruption remains non-detectable from Qt state, document that explicitly and prefer preventing the activation/cache trigger over pretending to detect it.

## Record Provenance

This standalone file preserves the complete former inline `U-06` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
