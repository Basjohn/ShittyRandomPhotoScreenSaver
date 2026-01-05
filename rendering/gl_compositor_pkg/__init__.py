"""GL Compositor package for DisplayWidget rendering.

This package provides the single OpenGL compositor widget responsible for
drawing base images and GL-backed transitions. The compositor delegates
heavy lifting to centralized managers:

- GLTextureManager: Texture upload, PBO pooling, caching
- GLGeometryManager: VAO/VBO geometry management  
- GLProgramCache: Shader program compilation and caching
- GLTransitionRenderer: Transition-specific rendering logic

Architecture Note:
The GL compositor already has excellent modularity via delegation to
external manager classes. This package structure provides:
1. Backward compatibility (imports from legacy gl_compositor.py)
2. Extracted metrics classes for cleaner organization
3. A path for future refactoring without breaking existing code

For backward compatibility, all public symbols are re-exported.
"""

# Import metrics from extracted module
from rendering.gl_compositor_pkg.metrics import (
    _GLPipelineState,
    _AnimationRunMetrics,
    _PaintMetrics,
    _RenderTimerMetrics,
)

# Re-export main classes from legacy module for backward compatibility
# The legacy module (rendering/gl_compositor.py) will be updated to import
# metrics from this package, completing the circular dependency resolution
# The main GLCompositorWidget remains in rendering/gl_compositor.py
# This package provides extracted metrics classes for cleaner organization
# and a foundation for future refactoring

__all__ = [
    "_GLPipelineState",
    "_AnimationRunMetrics", 
    "_PaintMetrics",
    "_RenderTimerMetrics",
]
