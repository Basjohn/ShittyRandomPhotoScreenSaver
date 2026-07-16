"""Centralized cache for GL shader programs.

This module replaces the scattered module-level globals in gl_compositor.py
with a proper cache class that manages lazy loading, compilation tracking,
and cleanup of all shader programs.

IMPORTANT: OpenGL program IDs are scoped to a GL context share group. Numeric
IDs can be reused by unrelated programs after context recreation, so cache
identity is the verified share group rather than the numeric handle alone.

Phase 1 of GLCompositor refactor - see audits/REFACTOR_GL_COMPOSITOR.md
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Hashable, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from rendering.gl_programs.base_program import BaseGLProgram

logger = logging.getLogger(__name__)


@dataclass
class _ProgramBucket:
    """Programs and uniforms owned by one verified OpenGL share group."""

    programs: Dict[str, int] = field(default_factory=dict)
    uniforms: Dict[str, Dict[str, int]] = field(default_factory=dict)
    initialized: Set[str] = field(default_factory=set)
    failed: Set[str] = field(default_factory=set)


def _load_gl():
    from OpenGL import GL as gl  # type: ignore

    return gl


def _qt_cpp_pointer(obj: object) -> int:
    try:
        import shiboken6

        pointer = shiboken6.getCppPointer(obj)
        if pointer:
            return int(pointer[0])
    except Exception:
        pass
    return id(obj)


def _qt_object_is_valid(obj: object | None) -> bool:
    if obj is None:
        return False
    try:
        import shiboken6

        return bool(shiboken6.isValid(obj))
    except Exception:
        return True


def _current_share_group_identity() -> tuple[Hashable, object | None]:
    """Return a stable key and wrapper for the current GL share group."""

    try:
        from PySide6.QtGui import QOpenGLContext

        context = QOpenGLContext.currentContext()
        if context is None:
            return ("no_context", 0), None
        share_group = context.shareGroup()
        if share_group is not None:
            return ("share_group", _qt_cpp_pointer(share_group)), share_group
        return ("context", _qt_cpp_pointer(context)), context
    except Exception:
        return ("no_context", 0), None


class GLProgramCache:
    """Manages compiled shader programs with lazy initialization.
    
    Compiled handles and uniforms are bucketed by the current verified OpenGL
    share group. Compositor pipelines hold non-owning bindings.
    
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
    WARP = "warp"
    RAINDROPS = "raindrops"
    CRUMBLE = "crumble"
    PARTICLE = "particle"
    BURN = "burn"
    
    def __init__(self):
        # Program instances (BaseGLProgram subclasses)
        self._program_instances: Dict[str, "BaseGLProgram"] = {}
        self._buckets: Dict[Hashable, _ProgramBucket] = {}
        self._group_wrappers: Dict[Hashable, object] = {}

    def _get_bucket(self, *, create: bool = True) -> tuple[Hashable, Optional[_ProgramBucket]]:
        key, wrapper = _current_share_group_identity()
        existing_wrapper = self._group_wrappers.get(key)
        if existing_wrapper is not None and not _qt_object_is_valid(existing_wrapper):
            # A C++ pointer can eventually be reused after its old share group
            # dies. Never let that resurrect the old numeric program IDs.
            self._buckets.pop(key, None)
            self._group_wrappers.pop(key, None)
            existing_wrapper = None

        if wrapper is not None and existing_wrapper is None:
            self._group_wrappers[key] = wrapper

        bucket = self._buckets.get(key)
        if bucket is None and create:
            bucket = _ProgramBucket()
            self._buckets[key] = bucket
        return key, bucket

    @staticmethod
    def _program_is_valid(gl, program_id: int) -> bool:
        try:
            if not gl.glIsProgram(int(program_id)):
                return False
            link_status = gl.glGetProgramiv(int(program_id), gl.GL_LINK_STATUS)
            return bool(link_status)
        except Exception:
            return False
    
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
            elif name == self.WARP:
                from rendering.gl_programs.warp_program import warp_program
                return warp_program
            elif name == self.RAINDROPS:
                from rendering.gl_programs.raindrops_program import raindrops_program
                return raindrops_program
            elif name == self.CRUMBLE:
                from rendering.gl_programs.crumble_program import crumble_program
                return crumble_program
            elif name == self.PARTICLE:
                from rendering.gl_programs.particle_program import particle_program
                return particle_program
            elif name == self.BURN:
                from rendering.gl_programs.burn_program import burn_program
                return burn_program
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
        _, bucket = self._get_bucket()
        if bucket is None:
            return None

        if name in bucket.failed:
            return None

        if name in bucket.programs:
            program_id = bucket.programs.get(name)
            if program_id is None:
                return None

            try:
                gl = _load_gl()
                if self._program_is_valid(gl, int(program_id)):
                    return int(program_id)
            except Exception:
                logger.debug("[GL CACHE] Failed to validate cached %s program", name, exc_info=True)

            bucket.programs.pop(name, None)
            bucket.uniforms.pop(name, None)
            bucket.initialized.discard(name)

        # Need to compile
        instance = self.get_program_instance(name)
        if instance is None:
            bucket.failed.add(name)
            return None
        
        try:
            program_id = instance.create_program()
            bucket.programs[name] = program_id
            bucket.initialized.add(name)
            
            # Cache uniforms
            uniforms = instance.cache_uniforms(program_id)
            bucket.uniforms[name] = uniforms
            
            logger.info("[GL CACHE] Compiled %s program: %d", name, program_id)
            return program_id
        except Exception as e:
            logger.error("[GL CACHE] Failed to compile %s: %s", name, e)
            bucket.failed.add(name)
            return None
    
    def get_uniforms(self, name: str) -> Dict[str, int]:
        """Get cached uniform locations for a program.
        
        Returns empty dict if program not compiled or failed.
        """
        _, bucket = self._get_bucket(create=False)
        if bucket is None:
            return {}
        return bucket.uniforms.get(name, {})
    
    def is_available(self, name: str) -> bool:
        """Check if program is available (compiled or can be compiled)."""
        _, bucket = self._get_bucket()
        if bucket is None:
            return False
        if name in bucket.failed:
            return False
        if name in bucket.programs:
            return True
        # Check if we can load the instance
        return self.get_program_instance(name) is not None
    
    def is_compiled(self, name: str) -> bool:
        """Check if program has been compiled."""
        _, bucket = self._get_bucket(create=False)
        return bool(bucket is not None and name in bucket.programs)
    
    def precompile_all(self) -> Dict[str, bool]:
        """Precompile all programs. Returns success status per program.
        
        Must be called with a valid GL context.
        """
        all_names = [
            self.CROSSFADE, self.SLIDE, self.WIPE, self.BLOCK_FLIP,
            self.BLINDS, self.DIFFUSE, self.WARP,
            self.RAINDROPS, self.CRUMBLE, self.PARTICLE, self.BURN,
        ]
        results = {}
        for name in all_names:
            program = self.get_program(name)
            results[name] = program is not None
        return results
    
    def invalidate_program(self, name: str) -> None:
        """Forget one current-share-group binding without deleting its handle."""

        _, bucket = self._get_bucket(create=False)
        if bucket is None:
            return
        bucket.programs.pop(name, None)
        bucket.uniforms.pop(name, None)
        bucket.initialized.discard(name)
        bucket.failed.discard(name)

    def cleanup_current_group(self) -> int:
        """Delete programs for the current share group exactly once."""

        key, bucket = self._get_bucket(create=False)
        if bucket is None:
            return 0

        try:
            gl = _load_gl()
        except Exception:
            gl = None

        deleted = 0
        if gl is not None:
            for name, program_id in list(bucket.programs.items()):
                try:
                    if self._program_is_valid(gl, int(program_id)):
                        gl.glDeleteProgram(int(program_id))
                        deleted += 1
                    logger.debug("[GL CACHE] Deleted program %s: %d", name, program_id)
                except Exception as e:
                    logger.debug("[GL CACHE] Failed to delete %s: %s", name, e)

        self._buckets.pop(key, None)
        self._group_wrappers.pop(key, None)
        return deleted

    def cleanup(self) -> None:
        """Delete the current share group's programs and abandon dead groups."""

        self.cleanup_current_group()
        if self._buckets:
            logger.debug(
                "[GL CACHE] Abandoning %d non-current/dead share-group bucket(s)",
                len(self._buckets),
            )
        self._buckets.clear()
        self._group_wrappers.clear()
        self._program_instances.clear()
        logger.debug("[GL CACHE] All programs cleaned up")
    
    def get_failed_programs(self) -> Set[str]:
        """Get set of programs that failed to compile."""
        _, bucket = self._get_bucket(create=False)
        return bucket.failed.copy() if bucket is not None else set()
    
    def get_compiled_programs(self) -> Set[str]:
        """Get set of successfully compiled programs."""
        _, bucket = self._get_bucket(create=False)
        return bucket.initialized.copy() if bucket is not None else set()


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
