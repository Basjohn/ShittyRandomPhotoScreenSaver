# A-05 — 2026-03-22 — Blob Ghost/Pulse Investigation (Resolved Subsystems Archived)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- Blob spent a long period oscillating between several failure classes:
  - ghost shape mismatch
  - ghost flicker
  - live core briefly hitting the "correct" shape and then snapping back
  - settings that appeared to do nothing, especially when trying to disable kick assist or cap reactive lift
- The user repeatedly reported that Blob could look musically expressive for a moment and then throw jarring oversized pulses unrelated to the actual track.

**Failed / retired approaches**
1. *Delayed-history / state-blend ghost replay:* created obvious "second blob" behavior and visible flicker.
2. *Ghost-only peak time / stage snapshotting:* preserved the wrong motion model and still produced wrong-shape behavior.
3. *Trying to solve the remaining pulse problem as ghost math:* misleading. Once parity returned, the real issue was in the live-core reaction path.

**Root causes that were actually fixed**
- **Divergent live vs ghost source paths:** Blob ghost memory and live uniforms were not always starting from the same processed support signal. That made the ghost look like a different interpretation of the audio.
- **Wrong event-energy ownership:** discrete kick/snare help could leak back into the same `bass/overall` channels driving whole-body scale, creating giant pulses instead of smooth staged growth.
- **Zero-valued controls silently ignored:** parts of Blob’s live-band path still used `... or default` reads, so valid `0` values for settings like `blob_kick_lane_gain`, `blob_pulse_cap`, and transient mixes were replaced by defaults. This made "off" or "minimum" settings feel fake.

**Final working state / guardrails**
- Ghost and live Blob now share the same processed live-band source before ghost hold/decay, restoring silhouette parity.
- Scheduler help is now intentionally asymmetric:
  - continuous `bass/overall` remain the main whole-body support
  - kick assist primarily feeds staged growth inputs
  - snare assist primarily feeds live `mid/high` wobble/stretch behavior
- `blob_pulse_cap` and `blob_pulse_release_ms` were added so reactive lift can be capped and released more gracefully without slowing attack.
- `blob_kick_lane_gain` now genuinely applies to Blob as a real user control; `0%` disables scheduler kick assist for Blob while leaving continuous support and snare-driven deformation available.
- Most importantly: Blob control reads in the live-band path must preserve valid zeroes. Do not reintroduce `... or default` when reading zero-allowed Blob controls.

**Regression coverage & validation**
- `tests/test_ghost_isolation.py` now guards Blob scheduler boost routing, kick-lane disable behavior, and the retired ghost-path contracts.
- `tests/test_visualizer_reactivity_quality.py` covers bounded Blob boost behavior on calm passages.
- User later confirmed that ghost/main-blob shape parity became correct again after this work, even though some preset/live-feel tuning remained an artistic validation task.

**Takeaways**
- Blob problems that "look like ghosting" may actually be live-core ownership bugs.
- Do not spend discrete scheduler events in the same channels that drive whole-body scalar pulse unless that is an intentional design choice.
- When a slider supports `0`, never read it through truthy fallback logic.
- Record retired experimental branches explicitly; otherwise Blob work tends to bounce back to the same two failed ideas.

## Record Provenance

This standalone file preserves the complete former inline `A-05` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
