# AAMP2026 Phase 3 Detailed Plan – GL Compositor & Transition Reliability (Live Checklist)

Status: Planning-only (no code). Spec.md remains current-state. Main audit references this doc for detail.

## 0) Preconditions / Policy Anchors
- [ ] Phase 1/2 plans finalized; supervisor and shared-memory schemas agreed.
- [ ] Lock-free/atomic + ThreadManager enforced; no raw Qt timers.
- [ ] Fallback groups A→B→C and `[PERF] [GL COMPOSITOR]` tagging baseline confirmed.

## 1) Scope & Goals
- [ ] Unify GL state management (GLStateManager) across compositor + overlays.
- [ ] Ensure transition factory parity and reliable watchdog/fallback behavior.
- [ ] Align Spotify overlays with state machine and dt_max guardrails.

## 2) GLStateManager Rollout
- [ ] Apply to `widgets/spotify_bars_gl_overlay.py`, GL warmup paths, legacy overlays; enforce READY→ERROR→DESTROYING transitions.
- [ ] Refactor all GL programs to query GLStateManager before issuing calls; add state validation helpers.
- [ ] Gate paintGL on readiness; prevent early execution; integrate `_first_frame_drawn` pattern.
- [ ] Implement centralized GL error handling hook (state manager emits, compositor responds).
- [ ] Ensure state transitions log structured events (screen, overlay, generation, error_code); synthetic visualizer test rerun before/after overlay refactors.

## 3) Transition Controller Alignment
- [ ] `rendering/transition_controller.py` uses TransitionStateManager for CPU + GL.
- [ ] Enforce `snap_to_new=True` on all cleanup paths; no residual blending.
- [ ] Parity across transition types (Crossfade/Slide/Wipe/Diffuse/BlockFlip/Blinds/Peel, etc.).
- [ ] Integrate GLStateManager readiness checks per transition renderer (CPU + GL parity).

## 4) Transition Architecture Unification (carried over from 2025 audit)
- [ ] Document all transition types (CPU + GL) and current duplication.
- [ ] Design unified `BaseTransition` interface + lifecycle (configure → warmup → present → cleanup).
- [ ] Define CPU/GL renderer abstraction + transition registry/factory (existing code audited before extending).
- [ ] Migrate Crossfade, Slide, Wipe, Diffuse, BlockFlip, Blinds, Peel to the new architecture; remove duplicate implementations.
- [ ] Ensure watchdog + telemetry integration per transition after migration.

## 5) Watchdog & Telemetry
- [ ] Standardize watchdog start/stop hooks per transition/overlay/compositor.
- [ ] `[PERF] [GL COMPOSITOR]` logs include queue latency vs render time once workers feed textures.
- [ ] Integrate supervisor health info if worker-fed textures stall.

## 6) Failure Paths & Demotion
- [ ] Tests for shader compile failure, lost context, swap-chain issues; verify Group demotion A→B→C.
- [ ] Ensure final frame correctness (snap to target image) after demotion.
- [ ] Log demotion with capability level (FULL_SHADERS → COMPOSITOR_ONLY → SOFTWARE_ONLY).

## 7) Visual Regression / Snapshot Testing
- [ ] Capture snapshot comparisons for each transition type; confirm final frame matches target image.
- [ ] Include GL + software paths; multi-monitor where applicable.

## 8) Supervisor Integration (Texture Feeds)
- [ ] When worker-fed textures arrive, ensure compositor handles missing/late frames without blocking.
- [ ] Backpressure rules honored; last-good frame reuse documented.

## 9) Testing Strategy (Design)
- [ ] Extend `tests/test_gl_state_manager.py` for overlays; add demotion/failure cases.
- [ ] Add `tests/test_transition_factory.py` / `tests/test_transition_registry.py` for base transition framework.
- [ ] Watchdog tests: stalled render triggers expected telemetry and cleanup.
- [ ] Visual regression harness invocation and expected baselines documented.
- [ ] Ensure `test_gl_state_manager.py` + new transition tests include GLStateManager readiness assertions.

## 10) Documentation & Backups Plan
- [ ] Keep audit Phase 3 checklist in sync with this doc.
- [ ] Spec.md stays current-state (no planning).
- [ ] Index.md: add/adjust entries for GL state manager + overlays when implemented.
- [ ] `/bak`: snapshots pre/post for GL compositor/overlay modules touched.

## 11) Exit Criteria (Planning Only)
- [ ] All checkboxes resolved with concrete decisions documented.
- [ ] Main audit updated with any deltas; no code written.
