# GL State Management Refactoring Guide (2026 High-Safety Edition)

_Role_: Supplemental deep-dive for **Phase 3 – GL Compositor & Transition Reliability** from `audits/ARCHITECTURE_AND_MULTIPROCESSING_PLAN_2026.md`.

> [!CAUTION]
> **VRAM LEAK GUARDRAIL**: All OpenGL resources (Programs, VAOs, VBOs, Textures, Shaders) MUST be registered with `ResourceManager` immediately upon generation. Failure to register GL handles leads to orphaned VRAM contexts during engine restarts.

---

## 1. Purpose & Policy
- **Consistency**: Unified `GLStateManager` lifecycle across Compositor, Visualizers, and Overlays.
- **Safety**: Mandatory `ResourceManager` tracking for all native GL handles.
- **Reliability**: Session-wide demotion (Group A→B→C) triggered by any internal GL failure.
- **Performance**: Zero GL calls issued unless `GLStateManager.is_ready()` is True.

---

## 2. Granular 12-Phase Execution Plan

### Phase 1: Native Handle Audit & Inventory
- [ ] List all `glGen*`, `glCreate*`, and `QOpenGLShaderProgram` calls across the codebase.
- [ ] Identify handlers currently relying on manual `delete*` in `__del__` (dangerous) or `cleanup()` (unreliable).
- [ ] **Target**: `rendering/gl_compositor.py`, `widgets/spotify_bars_gl_overlay.py`, `transitions/`.

### Phase 2: ResourceManager GL Cleanup Hooks
- [ ] Implement standardized cleanup wrappers in `core/resources/manager.py` or as helpers (e.g., `gl_delete_program`, `gl_delete_buffers`).
- [ ] Ensure cleanup handlers correctly bind the active GL context before issuing `glDelete*`.
- [ ] Verify `ResourceManager` can handle weakrefs to GL-wrapping objects.

### Phase 3: Spotify Visualizer Overlay Hardening
- [ ] Inject `GLStateManager` into `SpotifyBarsGLOverlay`.
- [ ] Replace `_gl_initialized` flag with `GLStateManager.transition(READY)`.
- [ ] **ResourceManager Registration**: Register the program, VAO, and VBO handles with custom cleanup handlers.
- [ ] Gate `paintGL` and `resizeGL` behind `self.is_gl_ready()`.

### Phase 4: Transition Controller Integration
- [ ] Update `rendering/transition_controller.py` to use `TransitionStateManager` natively.
- [ ] Enforce `snap_to_new=True` on all GL transition cleanup paths.
- [ ] Ensure transition renderers query their internal `GLStateManager` before setiap draw call.

### Phase 5: GLErrorHandler Capability Demotion
- [ ] Subscribe `GLErrorHandler` to all `GLStateManager` ERROR/CONTEXT_LOST callbacks.
- [ ] Implement "Session Poisoning": choice of A→B→C demotion must be global (if the visualizer fails, the compositor demotes to software to prevent driver instability).

### Phase 6: GL Warmup Protection
- [ ] Refactor GL "warmup" paths to use the state manager.
- [ ] Ensure `INITIALIZING` state covers the entire duration of shader compilation and buffer prep.
- [ ] Prevent `paintGL` from firing until the first frame is actually ready.

### Phase 7: Supervisor & Worker Texture Handover (Phase 2 Alignment)
- [ ] Ensure `GLStateManager` is aware of "Frame Stalls" when worker-fed textures are late.
- [ ] Implement `READY_STALLED` sub-state or watchdog flag for telemetry.

### Phase 8: Watchdog & Telemetry Wiring
- [ ] Wire `[PERF] [GL COMPOSITOR]` to capture `GLStateManager.get_transition_history()` on dt_max spikes.
- [ ] Log VRAM usage estimates if driver extensions allow (NV_dedicated_video_memory, etc.).

### Phase 9: Failure Injection Testing
- [ ] Create tests that simulate shader compile failure, context loss during render, and invalid cleanup order.
- [ ] Assert that `ResourceManager` correctly purges all handles without a crash.

### Phase 10: Performance Baseline (VRAM Focus)
- [ ] Measure VRAM delta after 100 engine restarts.
- [ ] Confirm VRAM usage remains `< 1GB` (per Roadmap goal) for typical operations.

### Phase 11: Success Verification & Parity
- [ ] Confirm zero stray `_gl_initialized` booleans in the codebase.
- [ ] Verify 100% of GL handles are accounted for in `ResourceManager.get_stats()`.

### Phase 12: Documentation & Guardrail Lock
- [ ] Update `Spec.md` and `Index.md` with final refactored modules.
- [ ] Cross-link all results into `audits/ARCHITECTURE_AND_MULTIPROCESSING_PLAN_2026.md`.

---

## 3. Implementation Patterns (Standardized)

### Safely Creating GL Resources
```python
def setup_gl(self):
    from OpenGL import GL as gl
    self.state_manager.transition(GLContextState.INITIALIZING)
    
    try:
        # Create handle
        vbo = gl.glGenBuffers(1)
        # IMMEDIATELY register for cleanup
        self.resource_manager.register(
            vbo, 
            resource_type="gl_buffer",
            cleanup_handler=lambda h: gl.glDeleteBuffers(1, [h])
        )
        self.vbo = vbo
        
        self.state_manager.transition(GLContextState.READY)
    except Exception as e:
        self.state_manager.transition(GLContextState.ERROR, str(e))
```

### Safely Rendering
```python
def paintGL(self):
    if not self.state_manager.is_ready():
        return
        
    with GLStateGuard(self.state_manager, "render_bars") as guard:
        if guard.is_valid:
            # GL calls here
            pass
```

---

## 4. Success Criteria
1. **Zero Raw Flags**: No `_gl_initialized` or `_gl_disabled` outside of the state manager.
2. **Handle Parity**: `VRAM Total Cleared == VRAM Total Allocated` across engine lifecycle.
3. **Global Demotion**: Any GL component failure triggers session-wide A→B→C fallback.
4. **Telemetry**: `screensaver_perf.log` includes GL state history on every watchdog trigger.
