# GL Handle Inventory (Phase 1 Audit)

_Generated: 2026-01-05_
_Purpose: Track all OpenGL resource allocations for ResourceManager integration_

## Summary

| Module | VAOs | VBOs | Programs | Shaders | Textures |
|--------|------|------|----------|---------|----------|
| `rendering/gl_programs/geometry_manager.py` | 2 | 2 | 0 | 0 | 0 |
| `rendering/gl_programs/base_program.py` | 0 | 0 | 1* | 2* | 0 |
| `rendering/gl_programs/texture_manager.py` | 0 | 0 | 0 | 0 | N |
| `rendering/gl_compositor.py` | 0 | 0 | 0 | 0 | 2 |
| `widgets/spotify_bars_gl_overlay.py` | 1 | 1 | 1 | 2 | 0 |

*Per program instance (multiple programs via program_cache.py)

## Detailed Inventory

### 1. `rendering/gl_programs/geometry_manager.py`

**Handles Created:**
- `_quad_vao` - Fullscreen quad VAO (line 114)
- `_quad_vbo` - Fullscreen quad VBO (line 115)
- `_box_vao` - Box geometry VAO (line 225)
- `_box_vbo` - Box geometry VBO (line 226)

**Current Cleanup:** ResourceManager-tracked cleanup

**Status:** ✅ Registered with ResourceManager (2026-01-05)

### 2. `rendering/gl_programs/base_program.py`

**Handles Created:**
- Program handle via `QOpenGLShaderProgram`
- Vertex shader (compiled and attached)
- Fragment shader (compiled and attached)

**Current Cleanup:** `QOpenGLShaderProgram` destructor

**Status:** ⚠️ Qt-managed but not tracked by ResourceManager

### 3. `rendering/gl_programs/texture_manager.py`

**Handles Created:**
- Dynamic texture handles via `glGenTextures` (line 138)
- PBO handles for async upload via `glGenBuffers` (line 338)

**Current Cleanup:** ResourceManager-tracked cleanup

**Status:** ✅ Registered with ResourceManager (2026-01-05)

### 4. `rendering/gl_compositor.py`

**Handles Created:**
- Delegates to `GLTextureManager` for all texture operations
- No direct GL handle creation

**Current Cleanup:** Via `GLTextureManager.cleanup()`

**Status:** ✅ Covered by GLTextureManager integration (2026-01-05)

### 5. `widgets/spotify_bars_gl_overlay.py`

**Handles Created:**
- `_gl_program` - Shader program (line 731)
- Vertex shader (line 732, deleted after link)
- Fragment shader (line 733, deleted after link)
- `_gl_vao` - Vertex array object (line 757)
- `_gl_vbo` - Vertex buffer object (line 758)

**Current Cleanup:** ResourceManager-tracked cleanup

**Status:** ✅ Registered with ResourceManager (2026-01-05)

## Risk Assessment

### High Risk (VRAM Leak Potential)
1. **Engine restart cycles** - If cleanup fails or is skipped, handles orphaned
2. **Context loss** - GL handles invalid but not cleared from Python objects
3. **Exception during init** - Partial handle creation without cleanup

### Medium Risk
1. **Shader compilation failure** - Shaders may leak if program creation fails
2. **Texture upload failure** - PBOs may leak on async upload errors

## Phase 2 Action Items

1. [ ] Add `register_gl_handle()` method to ResourceManager
2. [ ] Create cleanup handlers for each GL resource type
3. [ ] Wrap all `glGen*` calls with immediate registration
4. [ ] Add context validation before cleanup
5. [ ] Implement handle tracking statistics

## Phase 3 Action Items (Spotify Overlay)

1. [ ] Inject GLStateManager into SpotifyBarsGLOverlay
2. [ ] Replace `_gl_initialized` with state manager transitions
3. [ ] Register program, VAO, VBO with ResourceManager
4. [ ] Gate paintGL behind `is_gl_ready()`
