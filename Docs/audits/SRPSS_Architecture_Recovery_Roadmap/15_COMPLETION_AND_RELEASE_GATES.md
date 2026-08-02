# 15 — Completion and Release Gates

## Architecture gate

- [ ] One explicit owner exists for every mutable subsystem.
- [ ] One compositor surface exists per display.
- [ ] Compositor does not own visualizer simulation, worker scheduling, or Settings lifecycle.
- [ ] Visualizer producer never waits for paint.
- [ ] Transition completion is local.
- [ ] No adaptive timer/presentation acknowledgement remains.
- [ ] No compatibility mega-layer remains.
- [ ] No silent fallback architecture remains.
- [ ] Generation count is minimal and tied to real lifetime boundaries.
- [ ] Architecture documents match code.

## Visualizer gate

- [ ] Deterministic replay passes every mode.
- [ ] Spectrum retains response and shape.
- [ ] Bubble retains elasticity and responsiveness.
- [ ] Manual review passes.
- [ ] Irregular paint cadence does not alter logical behavior.
- [ ] Background load does not materially change feel.
- [ ] Settings/Edit restart preserves correct mode state.

## Lifecycle gate

- [ ] 50 Settings cycles pass.
- [ ] 50 Edit cycles pass.
- [ ] 50 mixed cycles pass.
- [ ] No cross-thread GL error.
- [ ] No stale callback applies.
- [ ] No old-generation GL resource remains.
- [ ] Timers/workers return to expected counts.
- [ ] Resource plateau returns after recreation.

## Performance gate

- [ ] CPU materially lower than baseline and donor in comparable scenarios.
- [ ] No normal one-core saturation.
- [ ] General task submission rate materially reduced.
- [ ] No worker task per presentation frame.
- [ ] No per-frame INFO logging.
- [ ] p95/p99/max frame intervals meet targets.
- [ ] No repeated idle 100+ ms gaps.
- [ ] Average FPS is reported but not used alone.

## RAM/VRAM gate

- [ ] RAM reaches stable plateau.
- [ ] VRAM reaches stable plateau.
- [ ] Every major application-owned resource is byte-accounted.
- [ ] CPU caches are byte-bounded.
- [ ] GPU store is byte-bounded.
- [ ] Old image/transition resources release.
- [ ] No full-buffer hot-path hash remains by default.
- [ ] Lifecycle cycles do not accumulate memory.

## Product gate

- [ ] Overlay appears on correct displays.
- [ ] Cursor halo remains smooth.
- [ ] Image quality/crop/scaling is unchanged unless approved.
- [ ] Transition behavior remains correct.
- [ ] No supported mode is silently disabled.
- [ ] Background-load behavior is better than baseline.
- [ ] Resource usage is appropriate for a screensaver.

## Evidence gate

- [ ] All official benchmark artifacts stored.
- [ ] Environment manifests stored.
- [ ] Raw logs preserved.
- [ ] Parser version recorded.
- [ ] Phase reports complete.
- [ ] Decision records complete.
- [ ] Failed experiments retained or summarized honestly.
- [ ] Rollback commit identified.

## Release rule

A release candidate is rejected if any critical gate fails, even when average FPS or one resource metric improves.

Critical gates:

- visualizer fidelity;
- GL lifecycle safety;
- frame-time tails;
- bounded memory;
- correct multi-display behavior.

## Final comparison statement

The release report must explicitly compare the candidate against:

- `00edb57` for behavior, visualizer feel, and lifecycle;
- `7376bb9` for resource bounds and the known presentation/lifecycle regressions.

It must state remaining weaknesses. It must not claim success based on a single favorable number.
