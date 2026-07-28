"""Centralized manager for GL geometry (VAO/VBO).

This module extracts geometry creation from gl_compositor.py into a dedicated
manager that handles quad and box mesh creation, binding, and cleanup.

Phase 2 of GLCompositor refactor - see audits/REFACTOR_GL_COMPOSITOR.md
"""

from __future__ import annotations

import ctypes
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from OpenGL import GL as gl
except ImportError:
    gl = None


class GLGeometryManager:
    """Manages VAO/VBO for quad and box meshes.
    
    Provides reusable geometry for all transitions:
    - Fullscreen quad for 2D transitions (crossfade, wipe, slide, etc.)
    - Box mesh for 3D transitions (block spin)
    
    Usage:
        manager = GLGeometryManager()
        if manager.initialize():
            manager.bind_quad()
            manager.draw_quad()
    """
    
    def __init__(self, owner: str = "GLGeometryManager", generation: object = None):
        self._owner = str(owner)
        self._generation = generation
        self._quad_vao: int = 0
        self._quad_vbo: int = 0
        self._box_vao: int = 0
        self._box_vbo: int = 0
        self._box_vertex_count: int = 0
        self._initialized: bool = False
        self._quad_vao_rid: Optional[str] = None
        self._quad_vbo_rid: Optional[str] = None
        self._box_vao_rid: Optional[str] = None
        self._box_vbo_rid: Optional[str] = None
    
    @property
    def quad_vao(self) -> int:
        """Get quad VAO ID."""
        return self._quad_vao
    
    @property
    def quad_vbo(self) -> int:
        """Get quad VBO ID."""
        return self._quad_vbo
    
    @property
    def box_vao(self) -> int:
        """Get box VAO ID."""
        return self._box_vao
    
    @property
    def box_vbo(self) -> int:
        """Get box VBO ID."""
        return self._box_vbo
    
    @property
    def box_vertex_count(self) -> int:
        """Get box vertex count."""
        return self._box_vertex_count
    
    def is_initialized(self) -> bool:
        """Check if geometry has been initialized."""
        return self._initialized
    
    def initialize(self) -> bool:
        """Initialize all geometry. Returns success.
        
        Must be called with a valid GL context.
        """
        if self._initialized:
            return True
        
        if gl is None:
            logger.warning("[GL GEOMETRY] PyOpenGL not available")
            return False
        
        try:
            if not self._create_quad_geometry():
                return False
            if not self._create_box_geometry():
                return False
            self._initialized = True
            logger.debug("[GL GEOMETRY] Geometry initialized")
            return True
        except Exception as e:
            logger.error("[GL GEOMETRY] Failed to initialize: %s", e)
            return False
    
    def _create_quad_geometry(self) -> bool:
        """Create fullscreen quad geometry."""
        if gl is None:
            return False
        
        try:
            # Fullscreen quad with interleaved position (x, y) and UV (u, v).
            vertices = [
                -1.0, -1.0, 0.0, 0.0,  # bottom-left
                 1.0, -1.0, 1.0, 0.0,  # bottom-right
                -1.0,  1.0, 0.0, 1.0,  # top-left
                 1.0,  1.0, 1.0, 1.0,  # top-right
            ]
            
            vertex_data = (ctypes.c_float * len(vertices))(*vertices)
            
            vao = gl.glGenVertexArrays(1)
            vbo = gl.glGenBuffers(1)
            self._quad_vao = int(vao)
            self._quad_vbo = int(vbo)
            
            gl.glBindVertexArray(self._quad_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._quad_vbo)
            gl.glBufferData(
                gl.GL_ARRAY_BUFFER,
                ctypes.sizeof(vertex_data),
                vertex_data,
                gl.GL_STATIC_DRAW,
            )
            
            stride = 4 * 4  # 4 floats per vertex (x, y, u, v)
            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))
            gl.glEnableVertexAttribArray(1)
            gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(8))
            
            gl.glBindVertexArray(0)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
            
            # Register GL handles with ResourceManager for VRAM leak prevention
            try:
                from core.resources.manager import ResourceManager
                rm = ResourceManager.get_or_create_app_shared()
                self._quad_vao_rid = rm.register_gl_vao(
                    self._quad_vao, description="GeometryManager quad VAO",
                    owner=self._owner, generation=self._generation,
                    dimensions=None, format="VERTEX_ARRAY", tracked_bytes=None,
                )
                self._quad_vbo_rid = rm.register_gl_vbo(
                    self._quad_vbo, description="GeometryManager quad VBO",
                    owner=self._owner, generation=self._generation,
                    dimensions=(4, 4), format="float32[x,y,u,v]",
                    tracked_bytes=ctypes.sizeof(vertex_data),
                )
            except Exception as e:
                logger.debug("[GL GEOMETRY] Failed to register quad handles: %s", e)
                self._quad_vao_rid = None
                self._quad_vbo_rid = None
            
            logger.debug("[GL GEOMETRY] Quad geometry created: VAO=%d, VBO=%d", self._quad_vao, self._quad_vbo)
            return True
        except Exception as e:
            logger.error("[GL GEOMETRY] Failed to create quad: %s", e)
            return False
    
    def _create_box_geometry(self) -> bool:
        """Create box mesh geometry for 3D transitions."""
        if gl is None:
            return False
        
        try:
            # Box mesh for 3D Block Spins: a thin rectangular prism with front,
            # back, and side faces. Each vertex stores position (x, y, z),
            # normal (nx, ny, nz) and UV (u, v).
            thickness = 0.05
            box_vertices = [
                # Front face (z = 0, normal +Z)
                -1.0, -1.0,  0.0,   0.0, 0.0, 1.0,   0.0, 0.0,
                 1.0, -1.0,  0.0,   0.0, 0.0, 1.0,   1.0, 0.0,
                 1.0,  1.0,  0.0,   0.0, 0.0, 1.0,   1.0, 1.0,

                -1.0, -1.0,  0.0,   0.0, 0.0, 1.0,   0.0, 0.0,
                 1.0,  1.0,  0.0,   0.0, 0.0, 1.0,   1.0, 1.0,
                -1.0,  1.0,  0.0,   0.0, 0.0, 1.0,   0.0, 1.0,

                # Back face (z = -thickness, normal -Z)
                -1.0, -1.0, -thickness,   0.0, 0.0, -1.0,   0.0, 0.0,
                 1.0, -1.0, -thickness,   0.0, 0.0, -1.0,   1.0, 0.0,
                 1.0,  1.0, -thickness,   0.0, 0.0, -1.0,   1.0, 1.0,

                -1.0, -1.0, -thickness,   0.0, 0.0, -1.0,   0.0, 0.0,
                 1.0,  1.0, -thickness,   0.0, 0.0, -1.0,   1.0, 1.0,
                -1.0,  1.0, -thickness,   0.0, 0.0, -1.0,   0.0, 1.0,

                # Left side (x = -1, normal -X)
                -1.0, -1.0,  0.0,       -1.0, 0.0, 0.0,   0.0, 0.0,
                -1.0, -1.0, -thickness, -1.0, 0.0, 0.0,   1.0, 0.0,
                -1.0,  1.0, -thickness, -1.0, 0.0, 0.0,   1.0, 1.0,

                -1.0, -1.0,  0.0,       -1.0, 0.0, 0.0,   0.0, 0.0,
                -1.0,  1.0, -thickness, -1.0, 0.0, 0.0,   1.0, 1.0,
                -1.0,  1.0,  0.0,       -1.0, 0.0, 0.0,   0.0, 1.0,

                # Right side (x = 1, normal +X)
                 1.0, -1.0,  0.0,        1.0, 0.0, 0.0,   1.0, 0.0,
                 1.0, -1.0, -thickness,  1.0, 0.0, 0.0,   0.0, 0.0,
                 1.0,  1.0, -thickness,  1.0, 0.0, 0.0,   0.0, 1.0,

                 1.0, -1.0,  0.0,        1.0, 0.0, 0.0,   1.0, 0.0,
                 1.0,  1.0, -thickness,  1.0, 0.0, 0.0,   0.0, 1.0,
                 1.0,  1.0,  0.0,        1.0, 0.0, 0.0,   1.0, 1.0,

                # Top face (y = 1, normal +Y)
                -1.0,  1.0,  0.0,       0.0, 1.0, 0.0,   0.0, 0.0,
                 1.0,  1.0,  0.0,       0.0, 1.0, 0.0,   1.0, 0.0,
                 1.0,  1.0, -thickness, 0.0, 1.0, 0.0,   1.0, 1.0,

                -1.0,  1.0,  0.0,       0.0, 1.0, 0.0,   0.0, 0.0,
                 1.0,  1.0, -thickness, 0.0, 1.0, 0.0,   1.0, 1.0,
                -1.0,  1.0, -thickness, 0.0, 1.0, 0.0,   0.0, 1.0,

                # Bottom face (y = -1, normal -Y)
                -1.0, -1.0,  0.0,       0.0, -1.0, 0.0,  0.0, 0.0,
                 1.0, -1.0,  0.0,       0.0, -1.0, 0.0,  1.0, 0.0,
                 1.0, -1.0, -thickness, 0.0, -1.0, 0.0,  1.0, 1.0,

                -1.0, -1.0,  0.0,       0.0, -1.0, 0.0,  0.0, 0.0,
                 1.0, -1.0, -thickness, 0.0, -1.0, 0.0,  1.0, 1.0,
                -1.0, -1.0, -thickness, 0.0, -1.0, 0.0,  0.0, 1.0,
            ]
            
            box_vertex_data = (ctypes.c_float * len(box_vertices))(*box_vertices)
            box_vao = gl.glGenVertexArrays(1)
            box_vbo = gl.glGenBuffers(1)
            self._box_vao = int(box_vao)
            self._box_vbo = int(box_vbo)
            self._box_vertex_count = len(box_vertices) // 8
            
            gl.glBindVertexArray(self._box_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._box_vbo)
            gl.glBufferData(
                gl.GL_ARRAY_BUFFER,
                ctypes.sizeof(box_vertex_data),
                box_vertex_data,
                gl.GL_STATIC_DRAW,
            )
            
            stride_box = 8 * 4  # 8 floats per vertex (x, y, z, nx, ny, nz, u, v)
            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride_box, ctypes.c_void_p(0))
            gl.glEnableVertexAttribArray(1)
            gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, stride_box, ctypes.c_void_p(12))
            gl.glEnableVertexAttribArray(2)
            gl.glVertexAttribPointer(2, 2, gl.GL_FLOAT, gl.GL_FALSE, stride_box, ctypes.c_void_p(24))
            
            gl.glBindVertexArray(0)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
            
            # Register GL handles with ResourceManager for VRAM leak prevention
            try:
                from core.resources.manager import ResourceManager
                rm = ResourceManager.get_or_create_app_shared()
                self._box_vao_rid = rm.register_gl_vao(
                    self._box_vao, description="GeometryManager box VAO",
                    owner=self._owner, generation=self._generation,
                    dimensions=None, format="VERTEX_ARRAY", tracked_bytes=None,
                )
                self._box_vbo_rid = rm.register_gl_vbo(
                    self._box_vbo, description="GeometryManager box VBO",
                    owner=self._owner, generation=self._generation,
                    dimensions=(self._box_vertex_count, 8),
                    format="float32[x,y,z,nx,ny,nz,u,v]",
                    tracked_bytes=ctypes.sizeof(box_vertex_data),
                )
            except Exception as e:
                logger.debug("[GL GEOMETRY] Failed to register box handles: %s", e)
                self._box_vao_rid = None
                self._box_vbo_rid = None
            
            logger.debug("[GL GEOMETRY] Box geometry created: VAO=%d, VBO=%d, vertices=%d",
                        self._box_vao, self._box_vbo, self._box_vertex_count)
            return True
        except Exception as e:
            logger.error("[GL GEOMETRY] Failed to create box: %s", e)
            return False
    
    def bind_quad(self) -> bool:
        """Bind quad VAO for fullscreen rendering."""
        if gl is None or not self._initialized:
            return False
        try:
            gl.glBindVertexArray(self._quad_vao)
            return True
        except Exception as e:
            logger.debug("[GL GEOMETRY] Exception suppressed: %s", e)
            return False
    
    def bind_box(self) -> bool:
        """Bind box VAO for 3D transitions."""
        if gl is None or not self._initialized:
            return False
        try:
            gl.glBindVertexArray(self._box_vao)
            return True
        except Exception as e:
            logger.debug("[GL GEOMETRY] Exception suppressed: %s", e)
            return False
    
    def draw_quad(self) -> None:
        """Draw fullscreen quad (4 vertices as triangle strip)."""
        if gl is None or not self._initialized:
            return
        try:
            gl.glBindVertexArray(self._quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            gl.glBindVertexArray(0)
        except Exception as e:
            logger.debug("[GL GEOMETRY] Exception suppressed: %s", e)
    
    def draw_box(self) -> None:
        """Draw box mesh (36 vertices as triangles)."""
        if gl is None or not self._initialized:
            return
        try:
            gl.glBindVertexArray(self._box_vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, self._box_vertex_count)
            gl.glBindVertexArray(0)
        except Exception as e:
            logger.debug("[GL GEOMETRY] Exception suppressed: %s", e)
    
    def unbind(self) -> None:
        """Unbind any bound VAO."""
        if gl is None:
            return
        try:
            gl.glBindVertexArray(0)
        except Exception as e:
            logger.debug("[GL GEOMETRY] Exception suppressed: %s", e)
    
    def has_live_resources(self) -> bool:
        """Return whether this manager still owns any VAO/VBO handle."""
        return any((self._quad_vao, self._quad_vbo, self._box_vao, self._box_vbo))

    def cleanup(self, *, strict: bool = False, gl_api=None) -> None:
        """Delete owned VAO/VBO handles, retaining every failed owner ID."""
        if gl_api is None:
            gl_api = gl
        if gl_api is None and self.has_live_resources():
            if strict:
                raise RuntimeError("Cannot delete live GL geometry: PyOpenGL is unavailable")
            return

        errors: list[str] = []
        resources = (
            ("_quad_vbo", "_quad_vbo_rid", "buffer"),
            ("_quad_vao", "_quad_vao_rid", "vertex_array"),
            ("_box_vbo", "_box_vbo_rid", "buffer"),
            ("_box_vao", "_box_vao_rid", "vertex_array"),
        )
        for handle_attr, rid_attr, kind in resources:
            handle = int(getattr(self, handle_attr, 0) or 0)
            if not handle:
                continue
            try:
                if kind == "buffer":
                    gl_api.glDeleteBuffers(1, [handle])
                else:
                    gl_api.glDeleteVertexArrays(1, [handle])
            except Exception as exc:
                errors.append(
                    f"{handle_attr}={handle}:{type(exc).__name__}:{exc}"
                )
                continue
            setattr(self, handle_attr, 0)
            self._release_resource_tracking(getattr(self, rid_attr, None))
            setattr(self, rid_attr, None)

        if errors:
            if strict:
                raise RuntimeError(
                    "GL geometry cleanup incomplete: " + " | ".join(errors)
                )
            return

        self._box_vertex_count = 0
        self._initialized = False
        logger.debug("[GL GEOMETRY] Geometry cleaned up")
    @staticmethod
    def _release_resource_tracking(resource_id: Optional[str]) -> None:
        if not resource_id:
            return
        try:
            from core.resources.manager import ResourceManager
            manager = ResourceManager.get_app_shared()
            if manager is not None:
                manager.release_tracking(resource_id)
        except Exception as e:
            logger.debug("[GL GEOMETRY] Failed to release resource tracking: %s", e)
