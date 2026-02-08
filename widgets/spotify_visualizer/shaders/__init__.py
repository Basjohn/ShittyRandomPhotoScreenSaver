"""Shader source loader for Spotify visualizer GL overlay.

All fragment shaders share a common fullscreen-quad vertex shader.
Each visualizer type has its own fragment shader file loaded at
``initializeGL()`` time so that no runtime recompilation is needed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from core.logging.logger import get_logger

logger = get_logger(__name__)

_SHADER_DIR = Path(__file__).parent

# Shared vertex shader for all visualizer types (fullscreen quad)
SHARED_VERTEX_SHADER: str = """#version 330 core
layout(location = 0) in vec2 a_pos;
out vec2 v_uv;
void main() {
    v_uv = a_pos * 0.5 + 0.5;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

# Registry of available fragment shader filenames keyed by vis_mode string.
_SHADER_FILES: Dict[str, str] = {
    "spectrum": "spectrum.frag",
    "oscilloscope": "oscilloscope.frag",
    "starfield": "starfield.frag",
    "blob": "blob.frag",
    "helix": "helix.frag",
}


def load_fragment_shader(vis_mode: str) -> str | None:
    """Load the fragment shader source for *vis_mode*.

    Returns ``None`` if the shader file does not exist or cannot be read,
    allowing the caller to skip compilation for that mode gracefully.
    """
    filename = _SHADER_FILES.get(vis_mode)
    if filename is None:
        logger.warning("[SHADER_LOADER] Unknown vis_mode: %s", vis_mode)
        return None

    path = _SHADER_DIR / filename
    if not path.is_file():
        logger.warning("[SHADER_LOADER] Shader file not found: %s", path)
        return None

    try:
        source = path.read_text(encoding="utf-8")
        logger.debug("[SHADER_LOADER] Loaded %s (%d chars)", filename, len(source))
        return source
    except Exception:
        logger.exception("[SHADER_LOADER] Failed to read %s", path)
        return None


def load_all_fragment_shaders() -> Dict[str, str]:
    """Load all available fragment shaders.

    Returns a dict mapping vis_mode → GLSL source for every shader that
    loaded successfully.  Modes whose files are missing or unreadable
    are silently skipped.
    """
    result: Dict[str, str] = {}
    missing: list[str] = []
    for mode in _SHADER_FILES:
        src = load_fragment_shader(mode)
        if src is not None:
            result[mode] = src
        else:
            missing.append(mode)
    logger.info(
        "[SHADER_LOADER] Loaded %d/%d shaders: %s",
        len(result),
        len(_SHADER_FILES),
        ", ".join(sorted(result.keys())),
    )
    if missing:
        logger.error(
            "[SHADER_LOADER] Missing shaders: %s",
            ", ".join(sorted(missing)),
        )
        raise RuntimeError(
            "Visualizer shaders missing: " + ", ".join(sorted(missing))
        )
    return result
