"""A process's unique set size on Windows without holding the Python GIL.

``--usage`` reports USS for every process of the app's tree on every sample. psutil's ``memory_full_info()`` gets it
by walking the target's whole working set (``QueryWorkingSet``, one entry per resident page) inside its C extension
with the GIL held: measured 11 Nov 2026, 4.4 ms for a 670 MB working set on an idle machine, during which a
pure-Python thread made no progress at all, and proportionally more for every further process and under load (the
engine worker added ~13 ms to each sample under a game-like load). The other per-process reads cost microseconds.

This reader asks the same question through ``ctypes.WinDLL`` (the GIL is released for the kernel's walk) into a
buffer it keeps, and counts the pages with numpy (released again for the array passes). Same definition as psutil's:
a page is unique unless it is shared **and** mapped by more than one process.

Diagnostic support only: imported by the usage sampler when ``--usage`` is active on Windows, never at rest.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

import numpy

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
ERROR_BAD_LENGTH = 24
# PSAPI_WORKING_SET_BLOCK (one little-endian ULONG_PTR per page): Protection:5, ShareCount:3, Shared:1, Node:3,
# VirtualPage:52. By an entry's low 16 bits: shared (bit 8) and mapped by more than one process (bits 5-7 above 1).
_LOW_WORDS = numpy.arange(1 << 16, dtype=numpy.uint32)
_SHARED_ELSEWHERE = ((_LOW_WORDS & 0x100) != 0) & (((_LOW_WORDS >> 5) & 0x7) > 1)
del _LOW_WORDS


class _SystemInfo(ctypes.Structure):
    _fields_ = [("wProcessorArchitecture", wintypes.WORD), ("wReserved", wintypes.WORD),
                ("dwPageSize", wintypes.DWORD), ("lpMinimumApplicationAddress", ctypes.c_void_p),
                ("lpMaximumApplicationAddress", ctypes.c_void_p), ("dwActiveProcessorMask", ctypes.c_size_t),
                ("dwNumberOfProcessors", wintypes.DWORD), ("dwProcessorType", wintypes.DWORD),
                ("dwAllocationGranularity", wintypes.DWORD), ("wProcessorLevel", wintypes.WORD),
                ("wProcessorRevision", wintypes.WORD)]


class WorkingSetReader:
    """``unique_set_size(pid)`` for the sampler's own thread (one reader, one caller: its buffer is reused).

    Each foreign call releases and retakes the GIL, and a retake behind a busy Python thread waits a switch interval
    (5 ms, or a 15.6 ms timer tick): three calls per process made a sample far longer than the walk itself. So the
    process handles are kept between samples (``retain`` closes those of processes that left the tree, ``close`` all
    of them) and a steady sample makes one foreign call per process.
    """

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("working-set queries are Windows-only")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.K32QueryWorkingSet.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        kernel32.K32QueryWorkingSet.restype = wintypes.BOOL
        kernel32.GetSystemInfo.argtypes = [ctypes.POINTER(_SystemInfo)]
        kernel32.GetSystemInfo.restype = None
        info = _SystemInfo()
        kernel32.GetSystemInfo(ctypes.byref(info))
        self._kernel32 = kernel32
        self._page_bytes = int(info.dwPageSize) or 4096
        self._buffer = numpy.zeros(1 + (1 << 16), dtype=numpy.uint64)     # the entry count, then one word per page
        self._handles: dict[int, int] = {}

    @property
    def open_handles(self) -> int:
        return len(self._handles)

    def _drop(self, pid: int) -> None:
        handle = self._handles.pop(pid, None)
        if handle:
            self._kernel32.CloseHandle(handle)

    def retain(self, pids) -> None:
        """Close the handles of every process not in ``pids`` (it left the sampled tree)."""
        keep = {int(pid) for pid in pids}
        for pid in [pid for pid in self._handles if pid not in keep]:
            self._drop(pid)

    def close(self) -> None:
        self.retain(())

    def unique_set_size(self, pid: int) -> int:
        """Bytes of ``pid``'s working set that no other process maps. Raises ``OSError`` when the process cannot
        be opened or queried (gone, or not ours to read); its handle is then dropped, so a later process that
        reuses the PID is opened afresh."""
        pid = int(pid)
        kernel32 = self._kernel32
        handle = self._handles.get(pid)
        if handle is None:
            handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            self._handles[pid] = handle
        try:
            for _attempt in range(4):
                buffer = self._buffer
                ok = kernel32.K32QueryWorkingSet(handle, buffer.ctypes.data, buffer.nbytes)
                error = 0 if ok else ctypes.get_last_error()
                entries = int(buffer[0])
                if ok:
                    break
                if error != ERROR_BAD_LENGTH:
                    raise ctypes.WinError(error)
                # Too small: the first word says how many entries there are now. Grow past it (the set changes
                # between calls) and keep the larger buffer for later samples.
                self._buffer = numpy.zeros(1 + entries + entries // 8 + 4096, dtype=numpy.uint64)
            else:
                raise OSError(f"the working set of pid {pid} outgrew its buffer four times")
        except OSError:
            self._drop(pid)
            raise
        if entries == 0:
            # An exited process whose handle is still held answers with an empty set: it is gone.
            self._drop(pid)
            raise ProcessLookupError(pid)
        # The flags are in each entry's low 16 bits: one table lookup and one count (two array passes, not six: each
        # pass over a large array is another release and retake of the GIL).
        low_words = buffer[1:1 + entries].view(numpy.uint16)[::4]
        return (entries - int(numpy.count_nonzero(_SHARED_ELSEWHERE[low_words]))) * self._page_bytes


__all__ = ["WorkingSetReader"]
