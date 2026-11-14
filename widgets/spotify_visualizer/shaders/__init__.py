"""Shader source loader for the 2D Visualizer modes' fragment shaders.

The Quick renderers draw them over the shared quad, declared with each shader's own pass block
(``rendering.quick.visualizer.render_contract.quick_visualizer_vertex_source``).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from core.logging.logger import get_logger
from core.settings.visualizer_mode_registry import is_mode_active

logger = get_logger(__name__)

_SHADER_DIR = Path(__file__).parent
_FRAGMENT_SHADER_CACHE: Dict[str, str] | None = None

# Registry of available fragment shader filenames keyed by vis_mode string.
_ALL_SHADER_FILES: Dict[str, str] = {
    "spectrum": "spectrum.frag",
    "oscilloscope": "oscilloscope.frag",
    "bubble": "bubble.frag",
    "devcurve": "devcurve.frag",
}
_SHADER_ALIASES: Dict[str, str] = {}


def _active_shader_files() -> Dict[str, str]:
    """Return only shader files for modes that are not behind a closed dev gate."""
    return {
        mode: filename
        for mode, filename in _ALL_SHADER_FILES.items()
        if is_mode_active(mode)
    }


#: The line a shader file writes where the conventions include goes (N1.4; ``rendering.gl_programs.conventions``). The
#: native core's bake splices the same text at the same line (``native/core/cmake/compose_shader.cmake``), so a file
#: both renderers draw is one source.
CONVENTIONS_MARKER = "//@srpss_conventions"


def _load_shader_source(path: Path, *, include_stack: tuple[Path, ...] = ()) -> str:
    """Load a shader and expand local ``#include`` directives and the conventions marker.

    The include expander stays deliberately local-only and rejects cycles. A line ``//@srpss_conventions`` becomes the
    conventions include's text (``SRPSS_CONVENTIONS_GLSL``; the file defines ``SRPSS_CONVENTIONS_FRAGMENT`` before it
    for ``fragPixel``), exactly as the native core's bake splices it.
    """
    resolved = path.resolve()
    if resolved in include_stack:
        chain = " -> ".join(item.name for item in (*include_stack, resolved))
        raise RuntimeError(f"Shader include cycle: {chain}")
    source = resolved.read_text(encoding="utf-8")
    expanded: list[str] = []
    for line in source.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == CONVENTIONS_MARKER:
            from rendering.gl_programs.conventions import SRPSS_CONVENTIONS_GLSL

            expanded.append(SRPSS_CONVENTIONS_GLSL)
            continue
        if not stripped.startswith("#include "):
            expanded.append(line)
            continue
        token = stripped[len("#include "):].strip()
        if len(token) < 3 or token[0] != '"' or token[-1] != '"':
            raise RuntimeError(f"Invalid shader include in {resolved.name}: {line.strip()}")
        include_name = token[1:-1]
        include_path = (resolved.parent / include_name).resolve()
        if include_path.parent != _SHADER_DIR.resolve():
            raise RuntimeError(f"Shader include escapes source directory: {include_name}")
        expanded.append(
            _load_shader_source(include_path, include_stack=(*include_stack, resolved))
        )
    return "".join(expanded)


def load_fragment_shader(vis_mode: str) -> str | None:
    """Load the fragment shader source for *vis_mode*.

    Returns ``None`` if the shader file does not exist or cannot be read,
    allowing the caller to skip compilation for that mode gracefully.
    """
    shader_key = _SHADER_ALIASES.get(vis_mode, vis_mode)
    cache = _FRAGMENT_SHADER_CACHE
    if cache is not None:
        cached = cache.get(shader_key)
        if cached is not None:
            return cached
        # Cache may have been warmed while a dev-gated mode was inactive.
        # Fall through to direct file load so explicit requests still work.

    filename = _ALL_SHADER_FILES.get(shader_key)
    if filename is None:
        logger.warning("[SHADER_LOADER] Unknown vis_mode: %s", vis_mode)
        return None

    path = _SHADER_DIR / filename
    if not path.is_file():
        logger.warning("[SHADER_LOADER] Shader file not found: %s", path)
        return None

    try:
        source = _load_shader_source(path)
        logger.debug("[SHADER_LOADER] Loaded %s (%d chars)", filename, len(source))
        return source
    except Exception:
        logger.exception("[SHADER_LOADER] Failed to read %s", path)
        return None


def preload_fragment_shaders(*, force: bool = False) -> Dict[str, str]:
    """Warm the shared fragment-shader source cache once per process."""

    global _FRAGMENT_SHADER_CACHE
    if _FRAGMENT_SHADER_CACHE is not None and not force:
        return dict(_FRAGMENT_SHADER_CACHE)

    result: Dict[str, str] = {}
    missing: list[str] = []
    active = _active_shader_files()
    for mode in active:
        src = load_fragment_shader(mode)
        if src is not None:
            result[mode] = src
        else:
            missing.append(mode)
    logger.info(
        "[SHADER_LOADER] Loaded %d/%d shaders: %s",
        len(result),
        len(active),
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
    _FRAGMENT_SHADER_CACHE = dict(result)
    return dict(_FRAGMENT_SHADER_CACHE)


def load_all_fragment_shaders() -> Dict[str, str]:
    """Load all available fragment shaders.

    Returns a dict mapping vis_mode → GLSL source for every shader that
    loaded successfully.  Modes whose files are missing or unreadable
    are silently skipped.
    """
    return preload_fragment_shaders()


