"""Windows process-tree snapshot helpers for low-impact diagnostic telemetry.

The legacy ``--usage`` heavy sample used psutil's Windows process/thread
enumeration path. Those calls are backed by a system-wide
``NtQuerySystemInformation`` snapshot that keeps the Python GIL held for the
whole call in the psutil extension. On busy systems that made a diagnostic
sample visible to SRPSS's pure-Python Visualizer cadence.

This module uses Toolhelp process snapshots through ``ctypes.WinDLL`` instead.
ctypes releases the GIL while native calls execute, and ``PROCESSENTRY32W``
already carries each process's thread count, so one snapshot supplies both the
recursive child topology and the thread-count aggregate.

It is diagnostic support only; importing it has no effect unless ``--usage`` is
active on Windows.
"""
from __future__ import annotations

import ctypes
import os
from collections import defaultdict
from ctypes import wintypes

TH32CS_SNAPPROCESS = 0x00000002
MAX_PATH = 260
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * MAX_PATH),
    ]


def _kernel32():
    if os.name != "nt":
        raise OSError("Toolhelp process snapshots are Windows-only")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


def snapshot_process_tree_threads(root_pid: int) -> dict[int, int]:
    """Return ``pid -> thread_count`` for ``root_pid`` and recursive children.

    The snapshot is point-in-time by design, matching the old psutil heavy
    refresh semantics. A process that exits while the caller subsequently
    reads its cheap per-process metrics is naturally ignored by that caller.
    """

    root_pid = int(root_pid)
    if root_pid <= 0:
        raise ValueError("root_pid must be positive")

    kernel32 = _kernel32()
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())

    by_parent: dict[int, list[tuple[int, int]]] = defaultdict(list)
    own_threads: dict[int, int] = {}
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())

        while ok:
            pid = int(entry.th32ProcessID)
            ppid = int(entry.th32ParentProcessID)
            threads = max(0, int(entry.cntThreads))
            own_threads[pid] = threads
            by_parent[ppid].append((pid, threads))
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)

    if root_pid not in own_threads:
        # A live caller should normally appear in its own process snapshot. A
        # missing root is safer treated as a failed diagnostic sample than as a
        # zero-thread tree that silently prunes every cached child.
        raise ProcessLookupError(root_pid)

    result: dict[int, int] = {root_pid: own_threads[root_pid]}
    pending = [root_pid]
    while pending:
        parent = pending.pop()
        for pid, threads in by_parent.get(parent, ()):
            if pid in result:
                continue
            result[pid] = threads
            pending.append(pid)
    return result


__all__ = ["snapshot_process_tree_threads"]
