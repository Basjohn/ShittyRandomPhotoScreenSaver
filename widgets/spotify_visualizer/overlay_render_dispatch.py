from __future__ import annotations

def resolve_render_program_key(overlay, mode: str) -> str:
    """Resolve a stable mode id to its concrete GL renderer program."""
    return mode


def resolve_mode_program(overlay, gl, mode: str, logger):
    """Return the GL program for *mode*, lazily compiling it when needed."""

    program_key = resolve_render_program_key(overlay, mode)
    program = overlay._gl_programs.get(program_key)
    if program is not None:
        return program

    surface_kind = str(
        getattr(getattr(overlay, "_surface_host", None), "render_surface_kind", "")
        or ""
    ).strip().lower()
    if surface_kind == "compositor":
        warned = getattr(overlay, "_unavailable_program_warnings", None)
        if not isinstance(warned, set):
            warned = set()
            overlay._unavailable_program_warnings = warned
        if program_key not in warned:
            warned.add(program_key)
            logger.warning(
                "[SPOTIFY_VIS][COMPOSITOR] Mode '%s' was unavailable after hidden "
                "prewarm; refusing visible-path shader compilation",
                program_key,
            )
        return None

    try:
        from widgets.spotify_visualizer.shaders import SHARED_VERTEX_SHADER, load_fragment_shader

        fs_source = load_fragment_shader(program_key)
        if fs_source:
            vs = 0
            try:
                vs = int(gl.glCreateShader(gl.GL_VERTEX_SHADER))
                gl.glShaderSource(vs, SHARED_VERTEX_SHADER)
                gl.glCompileShader(vs)
                if gl.glGetShaderiv(vs, gl.GL_COMPILE_STATUS):
                    overlay._compile_gl_mode_program(program_key, fs_source, vs, gl)
            finally:
                if vs:
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
