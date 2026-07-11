from __future__ import annotations

from core.settings.visualizer_blob_contract import (
    BLOB_TYPE_SHAPED,
    normalize_blob_type,
)


def resolve_render_program_key(overlay, mode: str) -> str:
    """Resolve a stable mode id to its concrete GL renderer program."""
    if mode != "blob":
        return mode
    blob_type = normalize_blob_type(
        getattr(overlay, "_blob_type", None),
        legacy_shaper_enabled=getattr(overlay, "_blob_shaper_enabled", None),
    )
    return "blob_shaped" if blob_type == BLOB_TYPE_SHAPED else "blob_mighty"


def resolve_mode_program(overlay, gl, mode: str, logger):
    """Return the GL program for *mode*, lazily compiling it when needed."""

    program_key = resolve_render_program_key(overlay, mode)
    program = overlay._gl_programs.get(program_key)
    if program is not None:
        return program

    try:
        from widgets.spotify_visualizer.shaders import SHARED_VERTEX_SHADER, load_fragment_shader

        fs_source = load_fragment_shader(program_key)
        if fs_source:
            vs = gl.glCreateShader(gl.GL_VERTEX_SHADER)
            gl.glShaderSource(vs, SHARED_VERTEX_SHADER)
            gl.glCompileShader(vs)
            if gl.glGetShaderiv(vs, gl.GL_COMPILE_STATUS):
                overlay._compile_gl_mode_program(program_key, fs_source, vs, gl)
            gl.glDeleteShader(vs)
            program = overlay._gl_programs.get(program_key)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to lazily compile mode shader for %s", program_key, exc_info=True)

    if program is None:
        logger.warning(
            "[SPOTIFY_VIS] Mode '%s' shader unavailable; GL-only visualizer skipping frame",
            program_key,
        )
    return program


def dispatch_mode_uniforms(gl, mode: str, uniforms: dict, overlay) -> bool:
    """Upload mode-owned uniforms for *mode* via renderer-owned dispatch."""
    from widgets.spotify_visualizer.renderers import upload_mode_uniforms

    return upload_mode_uniforms(resolve_render_program_key(overlay, mode), gl, uniforms, overlay)
