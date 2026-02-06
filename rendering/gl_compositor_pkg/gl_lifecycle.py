"""GL Compositor Lifecycle - Extracted from gl_compositor.py.

Contains GL initialization, pipeline setup, cleanup, and shader program creation.
All functions accept the compositor widget instance as the first parameter.
"""

from __future__ import annotations

import ctypes
import time
from typing import TYPE_CHECKING

try:
    from OpenGL import GL as gl  # type: ignore[import]
except ImportError:
    gl = None


from core.logging.logger import get_logger, is_perf_metrics_enabled
from rendering.gl_compositor_pkg.metrics import _GLPipelineState
from rendering.gl_state_manager import GLContextState
from rendering.gl_programs.program_cache import get_program_cache, GLProgramCache
from rendering.gl_programs.geometry_manager import GLGeometryManager
from rendering.gl_programs.texture_manager import GLTextureManager

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def handle_initializeGL(widget) -> None:  # type: ignore[override]
    """Initialize GL state for the compositor.

    Sets up logging and prepares the internal pipeline container. In this
    phase the shader program and fullscreen quad geometry are created when
    OpenGL is available, but all drawing still goes through QPainter until
    later phases explicitly enable the shader path.
    """
    # Transition to INITIALIZING state
    if not widget._gl_state.transition(GLContextState.INITIALIZING):
        logger.warning("[GL COMPOSITOR] Failed to transition to INITIALIZING state")
        return

    try:
        ctx = widget.context()
        if ctx is not None:
            fmt = ctx.format()
            logger.info(
                "[GL COMPOSITOR] Context initialized: version=%s.%s, swap=%s, interval=%s",
                fmt.majorVersion(),
                fmt.minorVersion(),
                fmt.swapBehavior(),
                fmt.swapInterval(),
            )

        # Log adapter information and detect obvious software GL drivers so
        # shader-backed paths can be disabled proactively. QPainter-based
        # compositor transitions remain available as the safe fallback.
        if gl is not None:
            try:
                vendor_bytes = gl.glGetString(gl.GL_VENDOR)
                renderer_bytes = gl.glGetString(gl.GL_RENDERER)
                version_bytes = gl.glGetString(gl.GL_VERSION)

                def _decode_gl_string(val: object) -> str:
                    if isinstance(val, (bytes, bytearray)):
                        try:
                            return val.decode("ascii", "ignore")
                        except Exception as e:
                            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
                            return ""
                    return str(val) if val is not None else ""

                vendor = _decode_gl_string(vendor_bytes)
                renderer = _decode_gl_string(renderer_bytes)
                version_str = _decode_gl_string(version_bytes)
                logger.info(
                    "[GL COMPOSITOR] OpenGL adapter: vendor=%s, renderer=%s, version=%s",
                    vendor or "?",
                    renderer or "?",
                    version_str or "?",
                )

                # Record GL info in centralized error handler for session-level tracking
                widget._error_handler.record_gl_info(vendor or "", renderer or "", version_str or "")
                
                # Check if error handler detected software GL and demoted capability
                if widget._error_handler.is_software_gl:
                    widget._gl_disabled_for_session = True
                    widget._use_shaders = False
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to query OpenGL adapter strings", exc_info=True)

        # Prepare an empty pipeline container tied to this context and, if
        # possible, compile the shared card-flip shader program and quad
        # geometry. The pipeline remains disabled for rendering until
        # BlockSpin and other transitions are explicitly ported.
        widget._gl_pipeline = _GLPipelineState()
        widget._use_shaders = False
        widget._gl_disabled_for_session = False
        init_gl_pipeline(widget, )
        
        # Transition to READY state on success
        if widget._gl_pipeline and widget._gl_pipeline.initialized:
            widget._gl_state.transition(GLContextState.READY)
        else:
            widget._gl_state.transition(GLContextState.ERROR, "Pipeline initialization failed")
    except Exception as e:
        # If initialization fails at this stage, we simply log and keep
        # using the existing QPainter-only path. Higher levels can decide
        # to disable GL transitions for the session based on this signal
        # in later phases when shader-backed effects are wired.
        logger.debug("[GL COMPOSITOR] initializeGL failed", exc_info=True)
        widget._gl_state.transition(GLContextState.ERROR, str(e))

def init_gl_pipeline(widget) -> None:
    if widget._gl_disabled_for_session:
        return
    if gl is None:
        logger.info("[GL COMPOSITOR] PyOpenGL not available; disabling shader pipeline")
        widget._gl_disabled_for_session = True
        return
    if widget._gl_pipeline is None:
        widget._gl_pipeline = _GLPipelineState()
    if widget._gl_pipeline.initialized:
        return
    
    _pipeline_start = time.time()
    try:
        _shader_start = time.time()
        program = create_card_flip_program(widget, )
        widget._gl_pipeline.basic_program = program
        # Cache uniform locations for the shared card-flip program.
        widget._gl_pipeline.u_angle_loc = gl.glGetUniformLocation(program, "u_angle")
        widget._gl_pipeline.u_aspect_loc = gl.glGetUniformLocation(program, "u_aspect")
        widget._gl_pipeline.u_old_tex_loc = gl.glGetUniformLocation(program, "uOldTex")
        widget._gl_pipeline.u_new_tex_loc = gl.glGetUniformLocation(program, "uNewTex")
        widget._gl_pipeline.u_block_rect_loc = gl.glGetUniformLocation(program, "u_blockRect")
        widget._gl_pipeline.u_block_uv_rect_loc = gl.glGetUniformLocation(program, "u_blockUvRect")
        widget._gl_pipeline.u_spec_dir_loc = gl.glGetUniformLocation(program, "u_specDir")
        widget._gl_pipeline.u_axis_mode_loc = gl.glGetUniformLocation(program, "u_axisMode")

        # Compile all shader programs via centralized cache
        cache = get_program_cache()
        programs_to_compile = [
            (GLProgramCache.RAINDROPS, "raindrops_program", "raindrops_uniforms"),
            (GLProgramCache.WARP, "warp_program", "warp_uniforms"),
            (GLProgramCache.DIFFUSE, "diffuse_program", "diffuse_uniforms"),
            (GLProgramCache.BLOCK_FLIP, "blockflip_program", "blockflip_uniforms"),
            (GLProgramCache.PEEL, "peel_program", "peel_uniforms"),
            (GLProgramCache.CROSSFADE, "crossfade_program", "crossfade_uniforms"),
            (GLProgramCache.SLIDE, "slide_program", "slide_uniforms"),
            (GLProgramCache.WIPE, "wipe_program", "wipe_uniforms"),
            (GLProgramCache.BLINDS, "blinds_program", "blinds_uniforms"),
            (GLProgramCache.CRUMBLE, "crumble_program", "crumble_uniforms"),
            (GLProgramCache.PARTICLE, "particle_program", "particle_uniforms"),
        ]
        
        for program_name, program_attr, uniforms_attr in programs_to_compile:
            program_id = cache.get_program(program_name)
            if program_id is None:
                logger.debug("[GL SHADER] Failed to compile %s shader", program_name)
                widget._gl_disabled_for_session = True
                widget._use_shaders = False
                return
            setattr(widget._gl_pipeline, program_attr, program_id)
            setattr(widget._gl_pipeline, uniforms_attr, cache.get_uniforms(program_name))

        # NOTE: Shuffle and Claws shader initialization removed - these transitions are retired.

        # Initialize geometry - each compositor needs its own VAOs since
        # OpenGL VAOs are NOT shared between GL contexts (each display has its own context)
        if widget._geometry_manager is None:
            widget._geometry_manager = GLGeometryManager()
        if not widget._geometry_manager.initialize():
            logger.warning("[GL COMPOSITOR] Failed to initialize geometry manager")
            widget._gl_disabled_for_session = True
            widget._use_shaders = False
            return
        
        # Copy geometry IDs to pipeline state for backward compatibility
        widget._gl_pipeline.quad_vao = widget._geometry_manager.quad_vao
        widget._gl_pipeline.quad_vbo = widget._geometry_manager.quad_vbo
        widget._gl_pipeline.box_vao = widget._geometry_manager.box_vao
        widget._gl_pipeline.box_vbo = widget._geometry_manager.box_vbo
        widget._gl_pipeline.box_vertex_count = widget._geometry_manager.box_vertex_count
        
        # Initialize texture manager - each compositor needs its own textures since
        # OpenGL textures are NOT shared between GL contexts
        if widget._texture_manager is None:
            widget._texture_manager = GLTextureManager()

        widget._gl_pipeline.initialized = True
        _pipeline_elapsed = (time.time() - _pipeline_start) * 1000.0
        if _pipeline_elapsed > 50.0 and is_perf_metrics_enabled():
            logger.warning("[PERF] [GL COMPOSITOR] Shader pipeline init took %.2fms", _pipeline_elapsed)
        else:
            logger.info("[GL COMPOSITOR] Shader pipeline initialized (%.1fms)", _pipeline_elapsed)
    except Exception:
        logger.debug("[GL SHADER] Failed to initialize shader pipeline", exc_info=True)
        widget._gl_disabled_for_session = True
        widget._use_shaders = False

def cleanup_gl_pipeline(widget) -> None:
    if gl is None or widget._gl_pipeline is None:
        return

    try:
        is_valid = getattr(widget, "isValid", None)
        if callable(is_valid) and not is_valid():
            widget._reset_pipeline_state()
            return
    except Exception as e:
        logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)

    try:
        widget.makeCurrent()
    except Exception as e:
        logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
        widget._reset_pipeline_state()
        return

    try:
        # Clean up textures via texture manager
        try:
            if widget._texture_manager is not None:
                widget._texture_manager.cleanup()
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to cleanup texture manager", exc_info=True)

        # Delete shader programs
        program_attrs = [
            "basic_program", "raindrops_program", "warp_program", "diffuse_program",
            "blockflip_program", "peel_program", "crossfade_program", "slide_program",
            "wipe_program", "blinds_program", "crumble_program",
        ]
        try:
            for attr in program_attrs:
                prog_id = getattr(widget._gl_pipeline, attr, 0)
                if prog_id:
                    gl.glDeleteProgram(int(prog_id))
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to delete shader program", exc_info=True)

        # Delete geometry buffers
        try:
            for vbo_attr in ["quad_vbo", "box_vbo"]:
                vbo_id = getattr(widget._gl_pipeline, vbo_attr, 0)
                if vbo_id:
                    buf = (ctypes.c_uint * 1)(int(vbo_id))
                    gl.glDeleteBuffers(1, buf)
            for vao_attr in ["quad_vao", "box_vao"]:
                vao_id = getattr(widget._gl_pipeline, vao_attr, 0)
                if vao_id:
                    arr = (ctypes.c_uint * 1)(int(vao_id))
                    gl.glDeleteVertexArrays(1, arr)
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to delete geometry buffers", exc_info=True)

        widget._reset_pipeline_state()
    finally:
        try:
            widget.doneCurrent()
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)

def create_card_flip_program(widget) -> int:
    """Compile and link the basic textured card-flip shader program."""

    if gl is None:
        raise RuntimeError("OpenGL context not available for shader program")

    # 3D card-flip program: the vertex shader treats the image pair as a
    # thin 3D slab (box) in world space. Geometry is provided by the
    # dedicated box mesh VBO/VAO created in _init_gl_pipeline.
    vs_source = """#version 410 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec2 aUv;

out vec2 vUv;
out vec3 vNormal;
out vec3 vViewDir;
out float vEdgeX;
flat out int vFaceKind;  // 1=front, 2=back, 3=side

uniform float u_angle;
uniform float u_aspect;
uniform vec4 u_blockRect;   // xy = clip min, zw = clip max
uniform vec4 u_blockUvRect; // xy = uv min,  zw = uv max
uniform float u_specDir;    // -1 or +1, matches fragment shader
uniform int u_axisMode;

void main() {
// Preserve the local X coordinate as a thickness parameter for side
// faces while remapping UVs into the per-tile rectangle.
float edgeCoord = aUv.x;
vEdgeX = edgeCoord;

// Remap local UVs into the per-tile UV rectangle so that a grid of slabs
// each samples its own portion of the image pair.
vUv = mix(u_blockUvRect.xy, u_blockUvRect.zw, aUv);

// Classify faces in object space so texture mapping is stable regardless
// of the current rotation.
int face = 0;
if (abs(aNormal.z) > 0.5) {
    face = (aNormal.z > 0.0) ? 1 : 2;
} else {
    face = 3;
}
vFaceKind = face;

float ca = cos(u_angle);
float sa = sin(u_angle);

// Pure spin around Y; no X tilt so the top face does not open up.
mat3 rotY = mat3(
    ca,  0.0, sa,
    0.0, 1.0, 0.0,
   -sa,  0.0, ca
);

mat3 rotX = mat3(
    1.0, 0.0, 0.0,
    0.0,  ca, -sa,
    0.0,  sa,  ca
);

// Diagonal rotation: rotate around the axis (1,1,0) or (1,-1,0) normalised.
// Rodrigues formula: R(v,a) = v*cos(a) + (k x v)*sin(a) + k*(k.v)*(1-cos(a))
float inv_sqrt2 = 0.70710678;

vec3 pos;
vec3 normal;
if (u_axisMode == 1) {
    pos = rotX * aPos;
    normal = normalize(rotX * aNormal);
} else if (u_axisMode == 2) {
    // Diagonal TL->BR: axis = normalize(1, -1, 0)
    vec3 k = vec3(inv_sqrt2, -inv_sqrt2, 0.0);
    float kDotP = dot(k, aPos);
    vec3 kCrossP = cross(k, aPos);
    pos = aPos * ca + kCrossP * sa + k * kDotP * (1.0 - ca);
    float kDotN = dot(k, aNormal);
    vec3 kCrossN = cross(k, aNormal);
    normal = normalize(aNormal * ca + kCrossN * sa + k * kDotN * (1.0 - ca));
} else if (u_axisMode == 3) {
    // Diagonal TR->BL: axis = normalize(1, 1, 0)
    vec3 k = vec3(inv_sqrt2, inv_sqrt2, 0.0);
    float kDotP = dot(k, aPos);
    vec3 kCrossP = cross(k, aPos);
    pos = aPos * ca + kCrossP * sa + k * kDotP * (1.0 - ca);
    float kDotN = dot(k, aNormal);
    vec3 kCrossN = cross(k, aNormal);
    normal = normalize(aNormal * ca + kCrossN * sa + k * kDotN * (1.0 - ca));
} else {
    pos = rotY * aPos;
    normal = normalize(rotY * aNormal);
}

// Orthographic-style projection: treat the rotated slab as sitting in
// clip space so that when it faces the camera it fills the viewport
// similarly to the old 2D card, without extreme perspective stretching.
vNormal = normal;
vViewDir = vec3(0.0, 0.0, 1.0);

// Use -pos.z so the face nearest the camera always wins the depth test:
// at angle 0 the front (old image) is in front, at angle pi the back
// (new image) is in front. This avoids sudden flips when the CPU swaps
// the base pixmap at transition start/end.
float z_clip = -pos.z * 0.5;  // small but non-zero depth for proper occlusion

// Map the rotated slab into the caller-supplied block rect in clip space.
// When rendering a single full-frame slab the rect covers the entire
// viewport (-1..1 in both axes); in grid mode each tile uses a smaller
// rect.
float nx = pos.x * 0.5 + 0.5;
float ny = pos.y * 0.5 + 0.5;
float x_clip = mix(u_blockRect.x, u_blockRect.z, nx);
float y_clip = mix(u_blockRect.y, u_blockRect.w, ny);

// Add axis mode uniform for BlockSpin
// uniform int u_axisMode;  // 0 = Y, 1 = X
gl_Position = vec4(x_clip, y_clip, z_clip, 1.0);
}
"""

    fs_source = """#version 410 core
in vec2 vUv;
in vec3 vNormal;
in vec3 vViewDir;
in float vEdgeX;
flat in int vFaceKind;  // 1=front, 2=back, 3=side
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_angle;
uniform float u_aspect;
uniform float u_specDir;  // -1 or +1, controls highlight travel direction
uniform int u_axisMode;   // 0 = Y-axis, 1 = X-axis, 2 = diag TL-BR, 3 = diag TR-BL

void main() {
// Qt images are stored top-to-bottom, whereas OpenGL's texture
// coordinates assume (0,0) at the bottom-left. Flip the V coordinate so
// the sampled image appears upright.
vec2 uv_front = vec2(vUv.x, 1.0 - vUv.y);

// For horizontal (Y-axis) spins we mirror the back face horizontally so
// that when the card flips left/right the new image appears with the
// same orientation as a plain 2D draw. For vertical (X-axis) spins the
// geometric rotation inverts the slab in Y, so we sample with the raw
// UVs to keep the new image upright.
vec2 uv_back;
if (u_axisMode == 0) {
    uv_back = vec2(1.0 - vUv.x, 1.0 - vUv.y);  // horizontal spin
} else if (u_axisMode == 1) {
    uv_back = vec2(vUv.x, vUv.y);              // vertical spin
} else {
    // Diagonal spins: mirror both axes like horizontal
    uv_back = vec2(1.0 - vUv.x, 1.0 - vUv.y);
}

vec3 n = normalize(vNormal);
vec3 viewDir = normalize(vViewDir);
vec3 lightDir = normalize(vec3(-0.15, 0.35, 0.9));

// Normalised spin progress 0..1 from angle 0..pi and an edge-biased
// highlight envelope so specular accents are strongest near the start
// and end of the spin (slab faces most flush) and softest around the
// midpoint. A complementary mid-spin phase is used for the white rim
// outline so it appears when the slab is most edge-on. Use the absolute
// angle so LEFT/RIGHT and UP/DOWN directions share the same envelope.
float t = clamp(abs(u_angle) / 3.14159265, 0.0, 1.0);
float edgeFactor = abs(t - 0.5) * 2.0;  // 0 at mid-spin, 1 at edges
float highlightPhase = edgeFactor * edgeFactor;
float midPhase = (1.0 - edgeFactor);
midPhase = midPhase * midPhase;

vec3 color;

if (vFaceKind == 3) {
    // Side faces: darker glass core with a moving specular band across
    // the slab thickness, plus a very thin white outline along the rim
    // when the slab is most edge-on.
    vec3 base = vec3(0.0);
    vec3 halfVec = normalize(lightDir + viewDir);
    float ndh = max(dot(n, halfVec), 0.0);

    // Side faces use the original local X coordinate in [0,1] to
    // represent slab thickness from one edge to the other, independent
    // of any grid tiling. Move the highlight band centre from one edge
    // to the opposite edge over the spin, clamped far enough inside the
    // edges so the thicker band never leaves the face.
    float edgeT = (u_specDir < 0.0) ? (1.0 - t) : t;
    float bandHalfWidth = 0.09;  // thicker band for a more readable sheen
    float bandCenter = mix(bandHalfWidth, 1.0 - bandHalfWidth, edgeT);
    float d = abs(vEdgeX - bandCenter);
    float bandMask = 1.0 - smoothstep(bandHalfWidth, bandHalfWidth * 1.6, d);

    // Stronger, brighter specular so the edge sheen is clearly visible
    // and approaches white at its apex without blowing out the face.
    float spec = pow(ndh, 6.0) * bandMask * highlightPhase;
    float edgeSpec = clamp(4.0 * spec, 0.0, 1.0);
    color = mix(base, vec3(1.0), edgeSpec);

    // Thin white outline hugging the side-face rim. This uses both the
    // preserved local thickness coordinate (vEdgeX) and the tile UV's
    // vertical coordinate so the border tracks the outer rectangle of
    // the slab. It is only active around mid-spin so it never appears
    // on the very first/last frames.
    float xEdge = min(vEdgeX, 1.0 - vEdgeX);
    float yEdge = min(vUv.y, 1.0 - vUv.y);
    float edgeDist = min(xEdge, yEdge);
    float outlineMask = 1.0 - smoothstep(0.02, 0.08, edgeDist);
    float outlinePhase = outlineMask * midPhase;
    if (outlinePhase > 0.0) {
        float outlineStrength = clamp(1.2 * outlinePhase, 0.0, 1.0);
        color = mix(color, vec3(1.0), outlineStrength);
    }
} else {
    // Front/back faces: map old/new images directly to their respective
    // geometry so the card ends exactly on the new image without
    // mirroring or late flips.
    if (vFaceKind == 1) {
        color = texture(uOldTex, uv_front).rgb;
    } else {
        color = texture(uNewTex, uv_back).rgb;
    }

    // Subtle vertical rim highlight near the long edges so the slab
    // reads as a solid object while keeping the face image essentially
    // unshaded. Gate this with the same highlightPhase so we do not get
    // bright rims on the very first/last frames.
    float xN = vUv.x * 2.0 - 1.0;
    float rim = 0.0;
    if (rim > 0.0 && highlightPhase > 0.0) {
        vec3 halfVec = normalize(lightDir + viewDir);
        float ndh = max(dot(n, halfVec), 0.0);
        float spec = pow(ndh, 18.0) * highlightPhase;
        vec3 rimColor = color + vec3(spec * 0.45);  // dimmer, reduces bleed
        color = mix(color, rimColor, rim);
    }
}

FragColor = vec4(color, 1.0);
}
"""

    vert = widget._compile_shader(vs_source, gl.GL_VERTEX_SHADER)
    try:
        frag = widget._compile_shader(fs_source, gl.GL_FRAGMENT_SHADER)
    except Exception as e:
        logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
        gl.glDeleteShader(vert)
        raise

    try:
        program = gl.glCreateProgram()
        gl.glAttachShader(program, vert)
        gl.glAttachShader(program, frag)
        gl.glLinkProgram(program)
        status = gl.glGetProgramiv(program, gl.GL_LINK_STATUS)
        if status != gl.GL_TRUE:
            log = gl.glGetProgramInfoLog(program)
            logger.debug("[GL SHADER] Failed to link card-flip program: %r", log)
            gl.glDeleteProgram(program)
            raise RuntimeError(f"Failed to link card-flip program: {log!r}")
    finally:
        gl.glDeleteShader(vert)
        gl.glDeleteShader(frag)

    return int(program)

# NOTE: _create_peel_program() has been moved to rendering/gl_programs/peel_program.py
# The PeelProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_wipe_program() has been moved to rendering/gl_programs/wipe_program.py
# The WipeProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_diffuse_program() has been moved to rendering/gl_programs/diffuse_program.py
# The DiffuseProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_blockflip_program() has been moved to rendering/gl_programs/blockflip_program.py
# The BlockFlipProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_blinds_program() has been moved to rendering/gl_programs/blinds_program.py
# The BlindsProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_crossfade_program() has been moved to rendering/gl_programs/crossfade_program.py
# The CrossfadeProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_slide_program() has been moved to rendering/gl_programs/slide_program.py
# The SlideProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_shuffle_program() REMOVED - Shuffle transition was retired (dead code)

# NOTE: _create_warp_program() has been moved to rendering/gl_programs/warp_program.py
# The WarpProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_raindrops_program() has been moved to rendering/gl_programs/raindrops_program.py
# The RaindropsProgram helper is now responsible for shader compilation and rendering.

# NOTE: _create_claws_program() REMOVED - Claws/Shooting Stars transition was retired (dead code)

