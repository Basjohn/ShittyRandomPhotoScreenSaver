"""Studio clip workers never outlive the Studio process (mode-neutral).

A Studio analyses recorded clips in a separate process (``waveform_recorded_inputs.ClipLoadJob``). That process must
end with the job that started it, however the job ends: a cancel, the Studio closing, the app quitting, or the app
itself crashing.

* **Windows (parent side).** Each worker runs in its own Job Object with ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE``
  (``WorkerTree``). The job handle lives only in the Studio process (never inherited), so the OS kills every process
  in the job when that handle closes: on completion, on the parent's exit and on a crash alike. ``terminate`` ends the
  whole tree at once. A tree, not one process: a virtual environment's ``python.exe`` is a launcher that starts the
  real interpreter *suspended* and resumes it after its own setup; killing only the launcher in that window (a cancel
  right after start) left that interpreter suspended forever, with no parent (the orphaned workers seen 5-6 Nov).
  Processes the worker already started before it joined the job are found once (a toolhelp snapshot) and joined too;
  everything it starts afterwards inherits the job.
* **Linux (child side).** The worker asks the kernel for ``SIGKILL`` when its parent dies (``die_with_parent``:
  ``prctl(PR_SET_PDEATHSIG)``) and exits at once if the parent is already gone. On Linux the venv interpreter is the
  worker itself (no launcher), so its parent is the Studio process. The death signal follows the parent *thread* that
  started it; ``QProcess`` starts workers from the GUI thread, which lives as long as the app.
* **Elsewhere** (macOS): both are inert; a cancel still kills the worker, a parent crash does not (documented limit).

Nothing here runs at rest: a tree is created when a worker starts and closed when it ends; no thread, timer or poll.
"""
from __future__ import annotations

import os
import sys

_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_PROCESS_SET_QUOTA = 0x0100
_PROCESS_TERMINATE = 0x0001
_TH32CS_SNAPPROCESS = 0x00000002
_INVALID_HANDLE = -1


def _kernel32():
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateJobObjectW.restype = wintypes.HANDLE
    k.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    k.SetInformationJobObject.restype = wintypes.BOOL
    k.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    k.OpenProcess.restype = wintypes.HANDLE
    k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k.AssignProcessToJobObject.restype = wintypes.BOOL
    k.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    k.TerminateJobObject.restype = wintypes.BOOL
    k.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    k.CloseHandle.restype = wintypes.BOOL
    k.CloseHandle.argtypes = (wintypes.HANDLE,)
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    return k


def _limit_information():
    import ctypes
    from ctypes import wintypes

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount", "ReadTransferCount",
            "WriteTransferCount", "OtherTransferCount")]

    class BasicLimit(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class ExtendedLimit(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BasicLimit), ("IoInfo", IoCounters),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    info = ExtendedLimit()
    info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    return info


def _descendants(kernel32, root: int) -> list[int]:
    """Every process below ``root`` right now (one toolhelp snapshot)."""
    import ctypes
    from ctypes import wintypes

    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", wintypes.WCHAR * 260)]

    first = kernel32.Process32FirstW
    first.restype, first.argtypes = wintypes.BOOL, (wintypes.HANDLE, ctypes.POINTER(Entry))
    following = kernel32.Process32NextW
    following.restype, following.argtypes = wintypes.BOOL, (wintypes.HANDLE, ctypes.POINTER(Entry))
    snapshot = kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == ctypes.c_void_p(_INVALID_HANDLE).value:
        return []
    children: dict[int, list[int]] = {}
    try:
        entry = Entry()
        entry.dwSize = ctypes.sizeof(Entry)
        ok = first(snapshot, ctypes.byref(entry))
        while ok:
            children.setdefault(int(entry.th32ParentProcessID), []).append(int(entry.th32ProcessID))
            ok = following(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    out, stack = [], list(children.get(root, ()))
    while stack:
        pid = stack.pop()
        if pid in out or pid == root:
            continue
        out.append(pid)
        stack.extend(children.get(pid, ()))
    return out


class WorkerTree:
    """One worker and everything it starts, bound to this process's lifetime (Windows; inert elsewhere)."""

    def __init__(self) -> None:
        self._job = None
        self._kernel32 = None

    @property
    def active(self) -> bool:
        return self._job is not None

    def adopt(self, pid: int) -> bool:
        """Put the started worker ``pid`` (and anything it already started) into a new kill-on-close job.
        Returns whether the tree is now bound (False off Windows or when the process is already gone)."""
        if sys.platform != "win32" or pid <= 0 or self._job is not None:
            return False
        import ctypes
        kernel32 = _kernel32()
        job = kernel32.CreateJobObjectW(None, None)            # no security attributes: never inherited
        if not job:
            raise OSError(ctypes.get_last_error(), "CreateJobObject failed")
        info = _limit_information()
        if not kernel32.SetInformationJobObject(job, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(info),
                                                ctypes.sizeof(info)):
            error = ctypes.get_last_error()
            kernel32.CloseHandle(job)
            raise OSError(error, "SetInformationJobObject failed")
        self._job, self._kernel32 = job, kernel32
        bound = self._assign(pid)
        for child in _descendants(kernel32, pid):            # started before the worker joined the job
            self._assign(child)
        return bound

    def _assign(self, pid: int) -> bool:
        kernel32 = self._kernel32
        handle = kernel32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, int(pid))
        if not handle:
            return False                                      # already gone
        try:
            return bool(kernel32.AssignProcessToJobObject(self._job, handle))
        finally:
            kernel32.CloseHandle(handle)

    def terminate(self) -> None:
        """End every process of the tree now (a cancel)."""
        if self._job is not None:
            self._kernel32.TerminateJobObject(self._job, 1)

    def close(self) -> None:
        """Release the tree: anything still in it is killed by the OS (kill on close)."""
        job, self._job = self._job, None
        if job is not None:
            self._kernel32.CloseHandle(job)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


_PR_SET_PDEATHSIG = 1


def die_with_parent() -> bool:
    """Worker side: on Linux, have the kernel kill this worker when its parent dies, and exit now if it already
    has. Returns whether the death signal is armed (False elsewhere: Windows binds from the parent side)."""
    if not sys.platform.startswith("linux"):
        return False
    import ctypes
    import signal
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(_PR_SET_PDEATHSIG, int(signal.SIGKILL), 0, 0, 0) != 0:
            return False
    except (OSError, AttributeError):
        return False
    if os.getppid() == 1:                                     # the parent died before the signal was armed
        os._exit(3)
    return True


__all__ = ["WorkerTree", "die_with_parent"]
