from __future__ import annotations


def resolve_mode_program(overlay, gl, mode: str, logger):
    """Return the GL program for *mode*, lazily compiling it when needed."""

    program = overlay._gl_programs.get(mode)
    if program is not None:
        return program

    try:
        from widgets.spotify_visualizer.shaders import SHARED_VERTEX_SHADER, load_fragment_shader

        fs_source = load_fragment_shader(mode)
        if fs_source:
            vs = gl.glCreateShader(gl.GL_VERTEX_SHADER)
            gl.glShaderSource(vs, SHARED_VERTEX_SHADER)
            gl.glCompileShader(vs)
            if gl.glGetShaderiv(vs, gl.GL_COMPILE_STATUS):
                overlay._compile_gl_mode_program(mode, fs_source, vs, gl)
            gl.glDeleteShader(vs)
            program = overlay._gl_programs.get(mode)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to lazily compile mode shader for %s", mode, exc_info=True)

    if program is None:
        logger.warning(
            "[SPOTIFY_VIS] Mode '%s' shader unavailable; GL-only visualizer skipping frame",
            mode,
        )
    return program


def dispatch_mode_uniforms(gl, mode: str, uniforms: dict, overlay) -> bool:
    """Upload mode-owned uniforms for *mode* via renderer-owned dispatch."""
    from widgets.spotify_visualizer.renderers import upload_mode_uniforms

    return upload_mode_uniforms(mode, gl, uniforms, overlay)
