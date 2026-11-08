"""App-owned store of linked OpenGL program binaries (``glGetProgramBinary``), keyed by source and driver.

Why: the driver's own shader cache is per executable path, and a onefile build extracts to a new folder per build, so
every new build linked every program cold; Neon Lake's basin is one ~6 s ``glLinkProgram`` on the render thread that
holds every display (R-180). This store lives in the per-user local data root (``<local>/SRPSS/gl_program_cache``), so
it survives builds, and it is shared by Standard and Media Center: the key carries everything that decides validity.

* **Key:** SHA-256 over this store's schema, the GL vendor, renderer and version strings, the driver's supported
  binary formats, and every stage's type and source. A shader edit or a driver update is a clean miss.
* **File:** a fixed header (magic, schema, binary format, payload length, the key, the payload's SHA-256) and the
  payload. Anything that does not check out (truncated, corrupted, another key) is a miss, never an error; the
  compile that follows replaces it.
* **Writes** are atomic (a per-writer temporary file, then ``os.replace``), so two processes or two render threads
  linking the same program never see a partial file. Any I/O failure only skips the store.
* **Bounded:** after a write, least-recently-used entries (a hit refreshes the file's time) are removed until the
  total is within ``MAX_CACHE_BYTES``; leftover temporary files older than ``STALE_TEMP_S`` go too.

This module does no GL: ``rendering.quick.render.gl_resources._link`` (the one link owner) queries the driver,
loads or saves, and counts hits and misses here. Nothing runs between links: no thread, timer or poll.
"""
from __future__ import annotations

import hashlib
import os
import struct
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

MAX_CACHE_BYTES = 64 * 1024 * 1024    # Neon Lake's basin is ~0.6 MB on an RTX 4090; every program the app has fits
STALE_TEMP_S = 3600.0
_SCHEMA = 1
_MAGIC = b"SRPSSGLB"
_HEADER = struct.Struct("<8sIIQ32s32s")   # magic, schema, binary format, payload length, key, payload SHA-256
_SUFFIX = ".bin"
_TEMP_SUFFIX = ".tmp"


@dataclass(frozen=True)
class DriverIdentity:
    """What makes a program binary valid: the driver's strings and the binary formats it accepts."""

    vendor: str
    renderer: str
    version: str
    formats: tuple[int, ...]


def program_key(stages: Iterable[tuple[int, str]], driver: DriverIdentity) -> str:
    """The cache key (hex SHA-256) of one program: (shader type, source) per stage, in link order, and the driver."""

    digest = hashlib.sha256()

    def field(value: bytes) -> None:
        digest.update(struct.pack("<Q", len(value)))
        digest.update(value)

    field(b"srpss-gl-program-binary/%d" % _SCHEMA)
    for text in (driver.vendor, driver.renderer, driver.version):
        field(text.encode("utf-8", errors="surrogatepass"))
    field(b",".join(b"%d" % value for value in driver.formats))
    for shader_type, source in stages:
        field(b"%d" % int(shader_type))
        field(source.encode("utf-8", errors="surrogatepass"))
    return digest.hexdigest()


class ProgramBinaryCache:
    """One directory of program binaries; ``root=None`` is a disabled store (nothing loaded or saved)."""

    def __init__(self, root: Optional[Path], *, max_bytes: int = MAX_CACHE_BYTES) -> None:
        self.root = Path(root) if root is not None else None
        self.max_bytes = int(max_bytes)
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        self.saved = 0

    @property
    def enabled(self) -> bool:
        return self.root is not None

    def _path(self, key: str) -> Path:
        assert self.root is not None
        return self.root / f"{key}{_SUFFIX}"

    def count(self, *, hit: bool) -> tuple[int, int]:
        """Count one link as a hit or a miss; returns (hits, misses)."""

        with self._lock:
            if hit:
                self.hits += 1
            else:
                self.misses += 1
            return self.hits, self.misses

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"hits": self.hits, "misses": self.misses, "saved": self.saved}

    def load(self, key: str) -> Optional[tuple[int, bytes]]:
        """The stored (binary format, payload) for *key*, or None when absent or not intact."""

        if self.root is None:
            return None
        path = self._path(key)
        try:
            with path.open("rb") as handle:
                header = handle.read(_HEADER.size)
                if len(header) != _HEADER.size:
                    return None
                magic, schema, binary_format, length, stored_key, payload_digest = _HEADER.unpack(header)
                if (magic != _MAGIC or schema != _SCHEMA or stored_key != bytes.fromhex(key)
                        or not 0 < length <= self.max_bytes):
                    return None
                payload = handle.read(length + 1)
        except (OSError, ValueError):
            return None
        if len(payload) != length or hashlib.sha256(payload).digest() != payload_digest:
            return None
        try:
            os.utime(path)   # least-recently-used order for pruning
        except OSError:
            pass
        return int(binary_format), payload

    def store(self, key: str, binary_format: int, payload: bytes) -> bool:
        """Write *payload* for *key* atomically, then prune to the size bound. False when nothing was stored."""

        if self.root is None or not payload or len(payload) > self.max_bytes:
            return False
        header = _HEADER.pack(_MAGIC, _SCHEMA, int(binary_format) & 0xFFFFFFFF, len(payload), bytes.fromhex(key),
                              hashlib.sha256(payload).digest())
        path = self._path(key)
        temporary = path.with_name(f"{key}.{os.getpid()}.{threading.get_ident()}{_TEMP_SUFFIX}")
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            with temporary.open("wb") as handle:
                handle.write(header)
                handle.write(payload)
            os.replace(temporary, path)
        except OSError:
            try:
                temporary.unlink()
            except OSError:
                pass
            return False
        with self._lock:
            self.saved += 1
        self.prune()
        return True

    def prune(self) -> None:
        """Remove least-recently-used entries until the store is within ``max_bytes``, and stale temporaries."""

        if self.root is None:
            return
        entries: list[tuple[float, str, int]] = []
        total = 0
        now = time.time()
        try:
            listing = list(os.scandir(self.root))
        except OSError:
            return
        for entry in listing:
            try:
                if not entry.is_file():
                    continue
                status = entry.stat()
            except OSError:
                continue
            if entry.name.endswith(_TEMP_SUFFIX):
                if now - status.st_mtime > STALE_TEMP_S:
                    _remove(entry.path)
                continue
            if entry.name.endswith(_SUFFIX):
                entries.append((status.st_mtime, entry.path, status.st_size))
                total += status.st_size
        if total <= self.max_bytes:
            return
        entries.sort()
        for _mtime, path, size in entries:
            if total <= self.max_bytes:
                break
            if _remove(path):
                total -= size


def _remove(path: str) -> bool:
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


_cache: Optional[ProgramBinaryCache] = None
_cache_lock = threading.Lock()


def default_cache_root() -> Optional[Path]:
    """``<per-user local data>/SRPSS/gl_program_cache``, outside any build's extraction folder; None without one."""

    from core.platform_paths import user_local_root

    local = user_local_root()
    return None if local is None else local / "SRPSS" / "gl_program_cache"


def program_binary_cache() -> ProgramBinaryCache:
    """The process's store, resolved once (render threads of every display share it)."""

    global _cache
    cache = _cache
    if cache is None:
        with _cache_lock:
            if _cache is None:
                _cache = ProgramBinaryCache(default_cache_root())
            cache = _cache
    return cache


__all__ = [
    "DriverIdentity",
    "MAX_CACHE_BYTES",
    "ProgramBinaryCache",
    "default_cache_root",
    "program_binary_cache",
    "program_key",
]
