"""GL object ledger: which OpenGL objects were created and not yet deleted (headless, deterministic).

While installed, the ledger wraps every ``OpenGL.GL`` create/delete pair the renderers use (they
call through the module object) and keeps the live names per kind: textures, buffers, vertex
arrays, framebuffers, renderbuffers, queries, programs, shaders and sync objects. It answers a
lifecycle question no timing can: after a renderer is released, did every object it created go
away? Counts do not depend on machine load, so a leak shows on any machine, on the first run.

    with GLObjectLedger() as ledger:
        ... create, render, release ...
    assert not ledger.live(), ledger.describe()
"""
from __future__ import annotations

from collections.abc import Iterable

# kind -> (creating functions, deleting functions)
_PAIRS = {
    "textures": (("glGenTextures", "glCreateTextures"), ("glDeleteTextures",)),
    "buffers": (("glGenBuffers", "glCreateBuffers"), ("glDeleteBuffers",)),
    "vertex_arrays": (("glGenVertexArrays", "glCreateVertexArrays"), ("glDeleteVertexArrays",)),
    "framebuffers": (("glGenFramebuffers", "glCreateFramebuffers"), ("glDeleteFramebuffers",)),
    "renderbuffers": (("glGenRenderbuffers", "glCreateRenderbuffers"), ("glDeleteRenderbuffers",)),
    "queries": (("glGenQueries", "glCreateQueries"), ("glDeleteQueries",)),
    "programs": (("glCreateProgram",), ("glDeleteProgram",)),
    "shaders": (("glCreateShader",), ("glDeleteShader",)),
    "syncs": (("glFenceSync",), ("glDeleteSync",)),
}


def _names(value) -> list:
    """Object names from a create's return value or a delete's argument (int, sequence, array)."""
    if value is None:
        return []
    if isinstance(value, (int,)) or not hasattr(value, "__iter__"):
        return [value]
    return [item for item in value]


def _key(name):
    try:
        return int(name)
    except (TypeError, ValueError):
        return name           # a sync handle: keep the object itself


class GLObjectLedger:
    """Live GL object names per kind while installed (``with`` block, current-context thread)."""

    def __init__(self, gl=None) -> None:
        if gl is None:
            from OpenGL import GL as gl
        self.gl = gl
        self._live: dict[str, set] = {kind: set() for kind in _PAIRS}
        self.created: dict[str, int] = {kind: 0 for kind in _PAIRS}
        self._saved: dict[str, object] = {}

    def __enter__(self) -> GLObjectLedger:
        for kind, (creators, deleters) in _PAIRS.items():
            for name in creators:
                self._wrap(name, kind, self._on_create)
            for name in deleters:
                self._wrap(name, kind, self._on_delete)
        return self

    def __exit__(self, *_exc) -> None:
        for name, original in self._saved.items():
            setattr(self.gl, name, original)
        self._saved.clear()

    def _wrap(self, name: str, kind: str, record) -> None:
        original = getattr(self.gl, name, None)
        if original is None or name in self._saved:
            return
        self._saved[name] = original

        def call(*args, **kwargs):
            result = original(*args, **kwargs)
            record(kind, name, args, result)
            return result

        setattr(self.gl, name, call)

    def _on_create(self, kind: str, _name: str, _args, result) -> None:
        for name in _names(result):
            self._live[kind].add(_key(name))
            self.created[kind] += 1

    def _on_delete(self, kind: str, _name: str, args, _result) -> None:
        if not args:
            return
        for name in _names(args[-1]):           # glDelete*(n, names) or glDelete*(names / name)
            self._live[kind].discard(_key(name))

    def live(self, kinds: Iterable[str] | None = None) -> dict[str, int]:
        """Kinds with objects still alive and how many."""
        chosen = _PAIRS if kinds is None else kinds
        return {kind: len(self._live[kind]) for kind in chosen if self._live[kind]}

    def describe(self) -> str:
        live = self.live()
        if not live:
            return "no GL objects alive"
        return "alive: " + ", ".join(f"{count} {kind}" for kind, count in sorted(live.items()))
