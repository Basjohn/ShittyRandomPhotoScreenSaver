"""Centralized cache for GL shader programs.

This module replaces the scattered module-level globals in gl_compositor.py
with a proper cache class that manages lazy loading, compilation tracking,
and cleanup of all shader programs.

Phase 1 of GLCompositor refactor - see audits/REFACTOR_GL_COMPOSITOR.md
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from rendering.gl_programs.base_program import BaseGLProgram

logger = logging.getLogger(__name__)


class GLProgramCache:
    """Manages compiled shader programs with lazy initialization.
    
    Centralizes all shader compilation, caching, and cleanup.
    Handles compilation errors with fallback notification.
    
    Usage:
        cache = GLProgramCache()
        program = cache.get_program("crossfade")
        if program:
            uniforms = cache.get_uniforms("crossfade")
            # render with program and uniforms
    """
    
    # Program name constants
    CROSSFADE = "crossfade"
    SLIDE = "slide"
    WIPE = "wipe"
    BLOCK_FLIP = "blockflip"
    BLINDS = "blinds"
    DIFFUSE = "diffuse"
    PEEL = "peel"
    WARP = "warp"
    RAINDROPS = "raindrops"
    CRUMBLE = "crumble"
    
    def __init__(self):
        # Program instances (BaseGLProgram subclasses)
        self._program_instances: Dict[str, "BaseGLProgram"] = {}
        # Compiled GL program IDs
        self._programs: Dict[str, int] = {}
        # Cached uniform locations per program
        self._uniforms: Dict[str, Dict[str, int]] = {}
        # Track which programs have been initialized
        self._initialized: Set[str] = set()
        # Track which programs failed to compile
        self._failed: Set[str] = set()
    
    def get_program_instance(self, name: str) -> Optional["BaseGLProgram"]:
        """Get the program helper instance (lazy-loaded).
        
        Returns the BaseGLProgram subclass instance, not the compiled GL program.
        """
        if name in self._program_instances:
            return self._program_instances[name]
        
        instance = self._load_program_instance(name)
        if instance:
            self._program_instances[name] = instance
        return instance
    
    def _load_program_instance(self, name: str) -> Optional["BaseGLProgram"]:
        """Lazy-load a program instance by name."""
        try:
            if name == self.CROSSFADE:
                from rendering.gl_programs.crossfade_program import crossfade_program
                return crossfade_program
            elif name == self.SLIDE:
                from rendering.gl_programs.slide_program import slide_program
                return slide_program
            elif name == self.WIPE:
                from rendering.gl_programs.wipe_program import wipe_program
                return wipe_program
            elif name == self.BLOCK_FLIP:
                from rendering.gl_programs.blockflip_program import blockflip_program
                return blockflip_program
            elif name == self.BLINDS:
                from rendering.gl_programs.blinds_program import blinds_program
                return blinds_program
            elif name == self.DIFFUSE:
                from rendering.gl_programs.diffuse_program import diffuse_program
                return diffuse_program
            elif name == self.PEEL:
                from rendering.gl_programs.peel_program import peel_program
                return peel_program
            elif name == self.WARP:
                from rendering.gl_programs.warp_program import warp_program
                return warp_program
            elif name == self.RAINDROPS:
                from rendering.gl_programs.raindrops_program import raindrops_program
                return raindrops_program
            elif name == self.CRUMBLE:
                from rendering.gl_programs.crumble_program import crumble_program
                return crumble_program
            else:
                logger.warning("[GL CACHE] Unknown program name: %s", name)
                return None
        except ImportError as e:
            logger.warning("[GL CACHE] Failed to import %s program: %s", name, e)
            return None
    
    def get_program(self, name: str) -> Optional[int]:
        """Get compiled program by name, compile if needed.
        
        Returns the GL program ID, or None if compilation failed.
        Must be called with a valid GL context.
        """
        if name in self._failed:
            return None
        
        if name in self._programs:
            return self._programs[name]
        
        # Need to compile
        instance = self.get_program_instance(name)
        if instance is None:
            self._failed.add(name)
            return None
        
        try:
            program_id = instance.create_program()
            self._programs[name] = program_id
            self._initialized.add(name)
            
            # Cache uniforms
            uniforms = instance.cache_uniforms(program_id)
            self._uniforms[name] = uniforms
            
            logger.info("[GL CACHE] Compiled %s program: %d", name, program_id)
            return program_id
        except Exception as e:
            logger.error("[GL CACHE] Failed to compile %s: %s", name, e)
            self._failed.add(name)
            return None
    
    def get_uniforms(self, name: str) -> Dict[str, int]:
        """Get cached uniform locations for a program.
        
        Returns empty dict if program not compiled or failed.
        """
        return self._uniforms.get(name, {})
    
    def is_available(self, name: str) -> bool:
        """Check if program is available (compiled or can be compiled)."""
        if name in self._failed:
            return False
        if name in self._programs:
            return True
        # Check if we can load the instance
        return self.get_program_instance(name) is not None
    
    def is_compiled(self, name: str) -> bool:
        """Check if program has been compiled."""
        return name in self._programs
    
    def precompile_all(self) -> Dict[str, bool]:
        """Precompile all programs. Returns success status per program.
        
        Must be called with a valid GL context.
        """
        all_names = [
            self.CROSSFADE, self.SLIDE, self.WIPE, self.BLOCK_FLIP,
            self.BLINDS, self.DIFFUSE, self.PEEL, self.WARP,
            self.RAINDROPS, self.CRUMBLE,
        ]
        results = {}
        for name in all_names:
            program = self.get_program(name)
            results[name] = program is not None
        return results
    
    def cleanup(self) -> None:
        """Delete all programs and clear caches.
        
        Must be called with a valid GL context.
        """
        try:
            from OpenGL import GL as gl
        except ImportError:
            gl = None
        
        if gl is not None:
            for name, program_id in self._programs.items():
                try:
                    gl.glDeleteProgram(program_id)
                    logger.debug("[GL CACHE] Deleted program %s: %d", name, program_id)
                except Exception as e:
                    logger.debug("[GL CACHE] Failed to delete %s: %s", name, e)
        
        self._programs.clear()
        self._uniforms.clear()
        self._initialized.clear()
        self._failed.clear()
        self._program_instances.clear()
        logger.debug("[GL CACHE] All programs cleaned up")
    
    def get_failed_programs(self) -> Set[str]:
        """Get set of programs that failed to compile."""
        return self._failed.copy()
    
    def get_compiled_programs(self) -> Set[str]:
        """Get set of successfully compiled programs."""
        return self._initialized.copy()


# Module-level singleton instance for backward compatibility
_program_cache: Optional[GLProgramCache] = None


def get_program_cache() -> GLProgramCache:
    """Get the global program cache singleton."""
    global _program_cache
    if _program_cache is None:
        _program_cache = GLProgramCache()
    return _program_cache


def cleanup_program_cache() -> None:
    """Clean up the global program cache."""
    global _program_cache
    if _program_cache is not None:
        _program_cache.cleanup()
        _program_cache = None
