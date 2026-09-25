"""One-shot Windows native memory map of a running process, and a diff of two maps.

Answers the first question of a private-commit investigation (R-97): *which kind of
memory is growing?* It is a VMMap-style classification taken from outside the
process. It only reads: no remote thread, no suspension, no injected code, and no
work at all inside the target, so it cannot change what it measures (R-84).

Each allocation (``VirtualQueryEx`` regions grouped by allocation base) is
classified as one of:

* ``image``            mapped executable image (named by module);
* ``mapped_file``      file-backed section view (named by file);
* ``shareable``        pagefile-backed section view (shared memory);
* ``heap``             an NT heap segment (owner heap identified);
* ``heap_large``       a heap block large enough to get its own ``VirtualAlloc``;
* ``segment_heap``     a segment-heap region;
* ``stack``            a thread stack (owner thread start module identified);
* ``teb_peb``          thread/process environment blocks;
* ``python_arena``     a 1 MiB read/write fully committed block (CPython obmalloc arena);
* ``private_other``    any other ``VirtualAlloc`` (drivers, OpenBLAS, allocators...).

Commit counts committed pages; ``resident_private`` counts private pages in the
working set (``QueryWorkingSet``). Commit that is not resident is either never
touched or trimmed; the split per category is what the investigation needs.

Typical use on the operator machine (the saver running normally)::

    python tools/win_memory_map.py capture --at 20 60 --out-dir logs/memory_map
    python tools/win_memory_map.py snapshot --pid 1234 --out a.json
    python tools/win_memory_map.py diff a.json b.json

``capture`` finds the SRPSS main process, waits until the given minutes after its
start, snapshots at each point and prints the diff of the first and last. Compare
snapshots at the same display count and after the same warm-up.
"""

from __future__ import annotations

import argparse
import bisect
import ctypes
import json
import os
import sys
import time
from collections import defaultdict
from ctypes import wintypes as wt
from pathlib import Path
from typing import Any, Iterable

PAGE = 4096
_USER_TOP = 0x7FFF_FFFF_0000

MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_FREE = 0x10000
MEM_PRIVATE = 0x20000
MEM_MAPPED = 0x40000
MEM_IMAGE = 0x1000000
PAGE_NOACCESS = 0x01
PAGE_READWRITE = 0x04
PAGE_GUARD = 0x100

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
THREAD_QUERY_INFORMATION = 0x0040
TH32CS_SNAPTHREAD = 0x00000004

_NT_HEAP_SIGNATURE = 0xFFEEFFEE
_SEGMENT_HEAP_SIGNATURE = 0xDDEEDDEE
_PYTHON_ARENA_SIZE = 1 << 20

# x64 layouts (PEB, TEB, _HEAP_SEGMENT, _HEAP_VIRTUAL_ALLOC_ENTRY).
_PEB_PROCESS_HEAP = 0x30
_PEB_NUMBER_OF_HEAPS = 0xE8
_PEB_PROCESS_HEAPS = 0xF0
_TEB_STACK_BASE = 0x08
_TEB_STACK_LIMIT = 0x10
_TEB_DEALLOCATION_STACK = 0x1478
_SEGMENT_SIGNATURE = 0x10
_SEGMENT_HEAP = 0x28
_VA_COMMIT_SIZE = 0x20
_VA_RESERVE_SIZE = 0x28


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_uint64),
        ("AllocationBase", ctypes.c_uint64),
        ("AllocationProtect", wt.DWORD),
        ("PartitionId", wt.WORD),
        ("RegionSize", ctypes.c_uint64),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
    ]


class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("ExitStatus", ctypes.c_long),
        ("PebBaseAddress", ctypes.c_uint64),
        ("AffinityMask", ctypes.c_uint64),
        ("BasePriority", ctypes.c_long),
        ("UniqueProcessId", ctypes.c_uint64),
        ("InheritedFromUniqueProcessId", ctypes.c_uint64),
    ]


class THREAD_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("ExitStatus", ctypes.c_long),
        ("TebBaseAddress", ctypes.c_uint64),
        ("UniqueProcess", ctypes.c_uint64),
        ("UniqueThread", ctypes.c_uint64),
        ("AffinityMask", ctypes.c_uint64),
        ("Priority", ctypes.c_long),
        ("BasePriority", ctypes.c_long),
    ]


class THREADENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ThreadID", wt.DWORD),
        ("th32OwnerProcessID", wt.DWORD),
        ("tpBasePri", ctypes.c_long),
        ("tpDeltaPri", ctypes.c_long),
        ("dwFlags", wt.DWORD),
    ]


class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", wt.DWORD),
        ("PageFaultCount", wt.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def _win32() -> tuple[Any, Any, Any]:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll")
    k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    k32.OpenProcess.restype = wt.HANDLE
    k32.OpenThread.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    k32.OpenThread.restype = wt.HANDLE
    k32.CloseHandle.argtypes = [wt.HANDLE]
    k32.VirtualQueryEx.argtypes = [
        wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t
    ]
    k32.VirtualQueryEx.restype = ctypes.c_size_t
    k32.ReadProcessMemory.argtypes = [
        wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)
    ]
    k32.ReadProcessMemory.restype = wt.BOOL
    k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
    k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
    k32.Thread32First.argtypes = [wt.HANDLE, ctypes.POINTER(THREADENTRY32)]
    k32.Thread32Next.argtypes = [wt.HANDLE, ctypes.POINTER(THREADENTRY32)]
    psapi.QueryWorkingSet.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD]
    psapi.QueryWorkingSet.restype = wt.BOOL
    psapi.GetMappedFileNameW.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.LPWSTR, wt.DWORD]
    psapi.GetMappedFileNameW.restype = wt.DWORD
    psapi.GetProcessMemoryInfo.argtypes = [
        wt.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX), wt.DWORD
    ]
    ntdll.NtQueryInformationProcess.argtypes = [
        wt.HANDLE, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p
    ]
    ntdll.NtQueryInformationProcess.restype = ctypes.c_long
    ntdll.NtQueryInformationThread.argtypes = [
        wt.HANDLE, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p
    ]
    ntdll.NtQueryInformationThread.restype = ctypes.c_long
    return k32, psapi, ntdll


class _Reader:
    def __init__(self, k32: Any, handle: int) -> None:
        self._k32 = k32
        self._handle = handle

    def read(self, address: int, size: int) -> bytes | None:
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t(0)
        if not self._k32.ReadProcessMemory(self._handle, ctypes.c_void_p(address), buf, size, ctypes.byref(got)):
            return None
        return buf.raw[: got.value] if got.value == size else None

    def u64(self, address: int) -> int | None:
        raw = self.read(address, 8)
        return int.from_bytes(raw, "little") if raw is not None else None

    def u32(self, address: int) -> int | None:
        raw = self.read(address, 4)
        return int.from_bytes(raw, "little") if raw is not None else None


def _regions(k32: Any, handle: int) -> list[dict[str, int]]:
    regions: list[dict[str, int]] = []
    mbi = MEMORY_BASIC_INFORMATION()
    address = 0
    while address < _USER_TOP:
        if not k32.VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        if mbi.State != MEM_FREE:
            regions.append(
                {
                    "base": int(mbi.BaseAddress),
                    "alloc_base": int(mbi.AllocationBase),
                    "alloc_protect": int(mbi.AllocationProtect),
                    "size": int(mbi.RegionSize),
                    "state": int(mbi.State),
                    "protect": int(mbi.Protect),
                    "type": int(mbi.Type),
                }
            )
        nxt = int(mbi.BaseAddress) + int(mbi.RegionSize)
        if nxt <= address:
            break
        address = nxt
    return regions


def _working_set(psapi: Any, handle: int) -> list[int]:
    """Return the resident page entries (address | flag bits)."""

    entries = 1 << 16
    while True:
        count = entries + 4096
        buf = (ctypes.c_uint64 * (count + 1))()
        if psapi.QueryWorkingSet(handle, buf, ctypes.sizeof(buf)):
            n = int(buf[0])
            return [int(buf[i + 1]) for i in range(min(n, count))]
        err = ctypes.get_last_error()
        if err != 24:  # ERROR_BAD_LENGTH: buffer too small, NumberOfEntries filled in.
            raise OSError(err, "QueryWorkingSet failed")
        entries = max(int(buf[0]), entries * 2)


def _mapped_name(psapi: Any, handle: int, address: int) -> str | None:
    buf = ctypes.create_unicode_buffer(1024)
    if psapi.GetMappedFileNameW(handle, ctypes.c_void_p(address), buf, 1024):
        return buf.value
    return None


def _threads(k32: Any, ntdll: Any, reader: _Reader, pid: int) -> list[dict[str, int]]:
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    if not snap or snap == wt.HANDLE(-1).value:
        return []
    tids: list[int] = []
    try:
        entry = THREADENTRY32()
        entry.dwSize = ctypes.sizeof(entry)
        ok = k32.Thread32First(snap, ctypes.byref(entry))
        while ok:
            if entry.th32OwnerProcessID == pid:
                tids.append(int(entry.th32ThreadID))
            ok = k32.Thread32Next(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    threads: list[dict[str, int]] = []
    for tid in tids:
        th = k32.OpenThread(THREAD_QUERY_INFORMATION, False, tid)
        if not th:
            continue
        try:
            tbi = THREAD_BASIC_INFORMATION()
            if ntdll.NtQueryInformationThread(th, 0, ctypes.byref(tbi), ctypes.sizeof(tbi), None) != 0:
                continue
            start = ctypes.c_uint64(0)
            ntdll.NtQueryInformationThread(th, 9, ctypes.byref(start), ctypes.sizeof(start), None)
            teb = int(tbi.TebBaseAddress)
            threads.append(
                {
                    "tid": tid,
                    "teb": teb,
                    "start": int(start.value),
                    "stack_base": reader.u64(teb + _TEB_STACK_BASE) or 0,
                    "stack_limit": reader.u64(teb + _TEB_STACK_LIMIT) or 0,
                    "deallocation_stack": reader.u64(teb + _TEB_DEALLOCATION_STACK) or 0,
                }
            )
        finally:
            k32.CloseHandle(th)
    return threads


def _heaps(ntdll: Any, reader: _Reader, handle: int) -> tuple[list[int], int]:
    pbi = PROCESS_BASIC_INFORMATION()
    if ntdll.NtQueryInformationProcess(handle, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), None) != 0:
        return [], 0
    peb = int(pbi.PebBaseAddress)
    default_heap = reader.u64(peb + _PEB_PROCESS_HEAP) or 0
    count = reader.u32(peb + _PEB_NUMBER_OF_HEAPS) or 0
    array = reader.u64(peb + _PEB_PROCESS_HEAPS) or 0
    heaps: list[int] = []
    raw = reader.read(array, 8 * count) if array and count else None
    if raw:
        heaps = [int.from_bytes(raw[i: i + 8], "little") for i in range(0, len(raw), 8)]
    return heaps, default_heap


def _group_allocations(regions: list[dict[str, int]]) -> list[dict[str, Any]]:
    allocations: dict[int, dict[str, Any]] = {}
    for region in regions:
        key = region["alloc_base"]
        alloc = allocations.get(key)
        if alloc is None:
            alloc = {
                "base": key,
                "type": region["type"],
                "alloc_protect": region["alloc_protect"],
                "reserved": 0,
                "commit": 0,
                # A heap's large blocks begin after a randomized reserved prefix,
                # so the block header sits on the first committed page, not the base.
                "first_commit": None,
                "rw_commit": 0,
                "regions": [],
            }
            allocations[key] = alloc
        alloc["reserved"] += region["size"]
        if region["state"] == MEM_COMMIT:
            alloc["commit"] += region["size"]
            if region["protect"] & PAGE_READWRITE:
                alloc["rw_commit"] += region["size"]
            if alloc["first_commit"] is None and not (region["protect"] & (PAGE_GUARD | PAGE_NOACCESS)):
                alloc["first_commit"] = region["base"]
        alloc["regions"].append((region["base"], region["size"], region["state"], region["protect"]))
    return sorted(allocations.values(), key=lambda a: a["base"])


def _attach_residency(allocations: list[dict[str, Any]], ws_entries: Iterable[int]) -> None:
    bases = [a["base"] for a in allocations]
    for alloc in allocations:
        alloc["resident_private"] = 0
        alloc["resident_shared"] = 0
    for entry in ws_entries:
        page = entry & ~0xFFF
        index = bisect.bisect_right(bases, page) - 1
        if index < 0:
            continue
        alloc = allocations[index]
        if page >= alloc["base"] + alloc["reserved"]:
            continue
        if (entry >> 8) & 1:
            alloc["resident_shared"] += PAGE
        else:
            alloc["resident_private"] += PAGE


def _module_index(allocations: list[dict[str, Any]]) -> tuple[list[int], list[dict[str, Any]]]:
    images = [a for a in allocations if a["type"] == MEM_IMAGE]
    return [a["base"] for a in images], images


def _module_for(address: int, bases: list[int], images: list[dict[str, Any]]) -> str:
    index = bisect.bisect_right(bases, address) - 1
    if index >= 0 and address < images[index]["base"] + images[index]["reserved"]:
        return str(images[index].get("detail") or "?")
    return "?"


def snapshot(pid: int) -> dict[str, Any]:
    if sys.platform != "win32":
        raise SystemExit("win_memory_map reads Windows process memory; run it on Windows")
    k32, psapi, ntdll = _win32()
    handle = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        raise OSError(ctypes.get_last_error(), f"OpenProcess({pid}) failed")
    try:
        reader = _Reader(k32, handle)
        started = time.perf_counter()
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        regions = _regions(k32, handle)
        ws = _working_set(psapi, handle)
        threads = _threads(k32, ntdll, reader, pid)
        heap_list, default_heap = _heaps(ntdll, reader, handle)
        allocations = _group_allocations(regions)
        _attach_residency(allocations, ws)

        for alloc in allocations:
            if alloc["type"] in (MEM_IMAGE, MEM_MAPPED):
                name = _mapped_name(psapi, handle, alloc["base"])
                alloc["detail"] = os.path.basename(name) if name else None
                if alloc["type"] == MEM_IMAGE:
                    alloc["category"] = "image"
                else:
                    alloc["category"] = "mapped_file" if name else "shareable"
        module_bases, images = _module_index(allocations)

        heap_ids = {base: index for index, base in enumerate(heap_list)}
        heap_names = {
            base: ("heap%d%s" % (index, "(default)" if base == default_heap else ""))
            for index, base in enumerate(heap_list)
        }
        by_base = {a["base"]: a for a in allocations}
        heap_first_region = {
            base: (base, base + by_base[base]["reserved"]) for base in heap_list if base in by_base
        }

        stack_owner: dict[int, dict[str, int]] = {}
        teb_pages: set[int] = set()
        for thread in threads:
            if thread["deallocation_stack"]:
                stack_owner[thread["deallocation_stack"]] = thread
            teb_pages.add(thread["teb"] & ~0xFFFF)

        def heap_of_list_node(node: int) -> int | None:
            for base, (lo, hi) in heap_first_region.items():
                if lo <= node < hi:
                    return base
            return None

        chain_cache: dict[int, int | None] = {}

        def owner_of_va_block(start: int) -> int | None:
            seen: list[int] = []
            node = start
            owner: int | None = None
            for _ in range(8192):
                if node in chain_cache:
                    owner = chain_cache[node]
                    break
                heap = heap_of_list_node(node)
                if heap is not None:
                    owner = heap
                    break
                seen.append(node)
                nxt = reader.u64(node)
                if not nxt or nxt == start:
                    break
                node = nxt
            for visited in seen:
                chain_cache[visited] = owner
            return owner

        for alloc in allocations:
            if alloc["type"] != MEM_PRIVATE:
                continue
            base = alloc["base"]
            if base in stack_owner:
                thread = stack_owner[base]
                alloc["category"] = "stack"
                alloc["detail"] = _module_for(thread["start"], module_bases, images)
                continue
            if any(base <= teb < base + alloc["reserved"] for teb in teb_pages) and alloc["reserved"] <= 0x10000:
                alloc["category"] = "teb_peb"
                alloc["detail"] = None
                continue
            first_commit = alloc["first_commit"]
            header = reader.read(first_commit, 0x40) if first_commit is not None else None
            if header is not None:
                at_base = first_commit == base
                signature = int.from_bytes(header[_SEGMENT_SIGNATURE: _SEGMENT_SIGNATURE + 4], "little")
                if at_base and signature == _NT_HEAP_SIGNATURE:
                    owner = int.from_bytes(header[_SEGMENT_HEAP: _SEGMENT_HEAP + 8], "little")
                    alloc["category"] = "heap"
                    alloc["detail"] = heap_names.get(owner, "heap@%x" % owner)
                    continue
                if at_base and (signature == _SEGMENT_HEAP_SIGNATURE or base in heap_ids):
                    alloc["category"] = "segment_heap" if signature == _SEGMENT_HEAP_SIGNATURE else "heap"
                    alloc["detail"] = heap_names.get(base)
                    continue
                commit_size = int.from_bytes(header[_VA_COMMIT_SIZE: _VA_COMMIT_SIZE + 8], "little")
                reserve_size = int.from_bytes(header[_VA_RESERVE_SIZE: _VA_RESERVE_SIZE + 8], "little")
                flink = int.from_bytes(header[0:8], "little")
                if reserve_size == alloc["reserved"] and 0 < commit_size <= reserve_size and 0 < flink < _USER_TOP:
                    owner = owner_of_va_block(first_commit)
                    if owner is not None:
                        alloc["category"] = "heap_large"
                        alloc["detail"] = heap_names.get(owner, "heap@%x" % owner)
                        continue
            if (
                alloc["reserved"] == _PYTHON_ARENA_SIZE
                and alloc["commit"] == _PYTHON_ARENA_SIZE
                and alloc["rw_commit"] == _PYTHON_ARENA_SIZE
            ):
                alloc["category"] = "python_arena"
                alloc["detail"] = None
                continue
            alloc["category"] = "private_other"
            alloc["detail"] = None

        thread_rows = [
            {
                "tid": t["tid"],
                "start_module": _module_for(t["start"], module_bases, images),
                "stack_reserved": (t["stack_base"] - t["deallocation_stack"]) if t["deallocation_stack"] else 0,
            }
            for t in threads
        ]
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return {
            "pid": pid,
            "taken_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "taken_epoch": time.time(),
            "elapsed_ms": round(elapsed_ms, 1),
            "counters": {
                "private_usage": int(counters.PrivateUsage),
                "working_set": int(counters.WorkingSetSize),
                "pagefile_usage": int(counters.PagefileUsage),
                "page_faults": int(counters.PageFaultCount),
            },
            "heaps": [
                {"name": heap_names[b], "base": b, "default": b == default_heap} for b in heap_list
            ],
            "threads": thread_rows,
            "allocations": [
                {
                    "base": a["base"],
                    "category": a.get("category", "unknown"),
                    "detail": a.get("detail"),
                    "alloc_protect": a["alloc_protect"],
                    "reserved": a["reserved"],
                    "commit": a["commit"],
                    "resident_private": a["resident_private"],
                    "resident_shared": a["resident_shared"],
                }
                for a in allocations
            ],
        }
    finally:
        k32.CloseHandle(handle)


def _mb(value: float) -> str:
    return "%+9.1f" % (value / 1048576.0)


def _mbu(value: float) -> str:
    return "%9.1f" % (value / 1048576.0)


def _size_bucket(size: int) -> str:
    if size >= 64 << 20:
        return ">=64M"
    if size % (1 << 20) == 0:
        return "%dM" % (size >> 20)
    if size % 1024 == 0:
        return "%dK" % (size >> 10)
    return str(size)


def summarize(snap: dict[str, Any]) -> str:
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for a in snap["allocations"]:
        row = totals[a["category"]]
        row[0] += 1
        row[1] += a["commit"]
        row[2] += a["resident_private"]
        row[3] += a["reserved"]
    counters = snap["counters"]
    private_commit = sum(a["commit"] for a in snap["allocations"] if a["category"] not in ("image", "mapped_file", "shareable"))
    lines = [
        "pid=%d taken=%s elapsed_ms=%s private_usage_mb=%s private_alloc_commit_mb=%s working_set_mb=%s threads=%d heaps=%d"
        % (
            snap["pid"], snap["taken_at"], snap["elapsed_ms"], _mbu(counters["private_usage"]).strip(),
            _mbu(private_commit).strip(), _mbu(counters["working_set"]).strip(), len(snap["threads"]), len(snap["heaps"]),
        ),
        "%-16s %6s %10s %10s %10s" % ("category", "count", "commit_mb", "resid_mb", "reserve_mb"),
    ]
    for name, row in sorted(totals.items(), key=lambda kv: -kv[1][1]):
        lines.append("%-16s %6d %s %s %s" % (name, row[0], _mbu(row[1]), _mbu(row[2]), _mbu(row[3])))
    return "\n".join(lines)


def _group_key(a: dict[str, Any]) -> tuple[str, str, str]:
    size = a["reserved"]
    if a["category"] == "heap_large":
        # Large heap blocks start after a randomized reserved prefix, so exact
        # sizes scatter; group them by power-of-two range instead.
        low = 1 << max(0, size.bit_length() - 1)
        return (a["category"], str(a.get("detail") or ""), "%s-%s" % (_size_bucket(low), _size_bucket(low * 2)))
    return (a["category"], str(a.get("detail") or ""), _size_bucket(size))


def diff(a: dict[str, Any], b: dict[str, Any], *, top: int = 30) -> str:
    lines = ["A: " + a["taken_at"] + "  B: " + b["taken_at"] + "  pid %d -> %d" % (a["pid"], b["pid"])]
    ca, cb = a["counters"], b["counters"]
    minutes = (b.get("taken_epoch", 0.0) - a.get("taken_epoch", 0.0)) / 60.0
    lines.append(
        "private_usage %s MB (%s MB/h over %.1f min)   working_set %s MB   threads %d -> %d"
        % (
            _mb(cb["private_usage"] - ca["private_usage"]).strip(),
            ("%+.1f" % ((cb["private_usage"] - ca["private_usage"]) / 1048576.0 * 60.0 / minutes)) if minutes >= 1.0 else "n/a",
            minutes,
            _mb(cb["working_set"] - ca["working_set"]).strip(),
            len(a["threads"]), len(b["threads"]),
        )
    )
    cats: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    for side, snap in ((0, a), (1, b)):
        for alloc in snap["allocations"]:
            row = cats[alloc["category"]]
            row[side] += 1
            row[2 + side] += alloc["commit"]
            row[4 + side] += alloc["resident_private"]
    lines.append("")
    lines.append("%-16s %9s %10s %10s %10s %10s" % ("category", "count", "commit_A", "d_commit", "resid_A", "d_resid"))
    for name, row in sorted(cats.items(), key=lambda kv: -abs(kv[1][3] - kv[1][2])):
        lines.append(
            "%-16s %4d->%-4d %s %s %s %s"
            % (name, row[0], row[1], _mbu(row[2]), _mb(row[3] - row[2]), _mbu(row[4]), _mb(row[5] - row[4]))
        )

    a_by = {x["base"]: x for x in a["allocations"]}
    b_by = {x["base"]: x for x in b["allocations"]}
    groups: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0])
    for base, alloc in b_by.items():
        old = a_by.get(base)
        if old is not None and (old["category"], old["reserved"]) == (alloc["category"], alloc["reserved"]):
            if old["commit"] != alloc["commit"] or old["resident_private"] != alloc["resident_private"]:
                g = groups[_group_key(alloc)]
                g[2] += 1
                g[3] += alloc["commit"] - old["commit"]
                g[4] += alloc["resident_private"] - old["resident_private"]
            continue
        g = groups[_group_key(alloc)]
        g[0] += 1
        g[3] += alloc["commit"]
        g[4] += alloc["resident_private"]
        if old is not None:
            og = groups[_group_key(old)]
            og[1] += 1
            og[3] -= old["commit"]
            og[4] -= old["resident_private"]
    for base, old in a_by.items():
        if base not in b_by:
            g = groups[_group_key(old)]
            g[1] += 1
            g[3] -= old["commit"]
            g[4] -= old["resident_private"]
    lines.append("")
    lines.append("largest changes by (category, owner, allocation size): new / freed / grown allocations")
    lines.append("%-14s %-28s %-8s %5s %5s %5s %10s %10s" % ("category", "owner", "size", "new", "freed", "grown", "d_commit", "d_resid"))
    ranked = sorted(groups.items(), key=lambda kv: -abs(kv[1][3]))
    for (cat, owner, size), g in ranked[:top]:
        if not g[3] and not g[4]:
            continue
        lines.append(
            "%-14s %-28s %-8s %5d %5d %5d %s %s"
            % (cat, owner[:28], size, g[0], g[1], g[2], _mb(g[3]), _mb(g[4]))
        )

    starts_a: dict[str, int] = defaultdict(int)
    starts_b: dict[str, int] = defaultdict(int)
    for t in a["threads"]:
        starts_a[t["start_module"]] += 1
    for t in b["threads"]:
        starts_b[t["start_module"]] += 1
    changed = {m for m in set(starts_a) | set(starts_b) if starts_a[m] != starts_b[m]}
    if changed:
        lines.append("")
        lines.append("threads by start module (A -> B): " + ", ".join(
            "%s %d->%d" % (m, starts_a[m], starts_b[m]) for m in sorted(changed)
        ))
    return "\n".join(lines)


def _find_srpss_pid(*, wait: bool = False) -> int:
    while True:
        try:
            return _find_srpss_pid_once()
        except SystemExit:
            if not wait:
                raise
        time.sleep(5.0)


def _find_srpss_pid_once() -> int:
    import psutil

    candidates = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        cmd = " ".join(proc.info.get("cmdline") or []).lower()
        name = (proc.info.get("name") or "").lower()
        if "multiprocessing" in cmd or "--multiprocessing-fork" in cmd:
            continue
        if name.startswith("srpss") or "main.py" in cmd or "main_mc.py" in cmd or "main_diagnostic.py" in cmd:
            if "win_memory_map" in cmd:
                continue
            candidates.append(proc)
    if not candidates:
        raise SystemExit("no running SRPSS main process found; pass --pid")
    candidates.sort(key=lambda p: p.info["create_time"])
    return int(candidates[-1].info["pid"])


def _open_counters(pid: int) -> tuple[Any, Any, int]:
    k32, psapi, _ntdll = _win32()
    handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        raise OSError(ctypes.get_last_error(), f"OpenProcess({pid}) failed")
    return k32, psapi, handle


def _read_counters(psapi: Any, handle: int) -> tuple[int, int] | None:
    counters = PROCESS_MEMORY_COUNTERS_EX()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        return None
    return int(counters.PrivateUsage), int(counters.WorkingSetSize)


def _write(path: Path, snap: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p_snap = sub.add_parser("snapshot", help="one snapshot of a process")
    p_snap.add_argument("--pid", type=int, default=None, help="default: the running SRPSS main process")
    p_snap.add_argument("--out", type=Path, default=None)
    p_diff = sub.add_parser("diff", help="compare two snapshots")
    p_diff.add_argument("a", type=Path)
    p_diff.add_argument("b", type=Path)
    p_diff.add_argument("--top", type=int, default=30)
    p_cap = sub.add_parser("capture", help="snapshot at minutes after process start, then diff first and last")
    p_cap.add_argument("--pid", type=int, default=None)
    p_cap.add_argument("--wait", action="store_true", help="wait for the SRPSS main process to start")
    p_cap.add_argument("--at", type=float, nargs="+", required=True, help="minutes after the process started")
    p_cap.add_argument("--out-dir", type=Path, default=Path("logs") / "memory_map")
    p_cap.add_argument(
        "--trace", type=float, default=0.0,
        help="also record private commit and working set every N seconds (read from outside) to a CSV",
    )
    args = parser.parse_args(argv)

    if args.command == "diff":
        a = json.loads(args.a.read_text(encoding="utf-8"))
        b = json.loads(args.b.read_text(encoding="utf-8"))
        print(diff(a, b, top=args.top))
        return 0
    pid = args.pid or _find_srpss_pid(wait=bool(getattr(args, "wait", False)))
    if args.command == "snapshot":
        snap = snapshot(pid)
        if args.out is not None:
            _write(args.out, snap)
        print(summarize(snap))
        return 0
    import psutil

    created = psutil.Process(pid).create_time()
    taken: list[Path] = []
    trace_file = None
    trace_handle = None
    if args.trace > 0:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        trace_file = (args.out_dir / ("memtrace_%d.csv" % pid)).open("a", encoding="utf-8")
        trace_file.write("epoch,minutes,private_mb,working_set_mb\n")
        trace_k32, trace_psapi, trace_handle = _open_counters(pid)
    for minute in sorted(args.at):
        target = created + minute * 60.0
        if target > time.time():
            print("pid=%d waiting %.0f s for the %.0f-minute snapshot" % (pid, target - time.time(), minute), flush=True)
        while time.time() < target:
            if trace_file is not None:
                values = _read_counters(trace_psapi, trace_handle)
                if values is None:
                    break
                now = time.time()
                trace_file.write(
                    "%.3f,%.3f,%.2f,%.2f\n"
                    % (now, (now - created) / 60.0, values[0] / 1048576.0, values[1] / 1048576.0)
                )
                trace_file.flush()
                time.sleep(max(0.0, min(args.trace, target - time.time())))
            else:
                time.sleep(max(0.0, target - time.time()))
        if not psutil.pid_exists(pid):
            print("pid=%d exited" % pid)
            break
        snap = snapshot(pid)
        path = args.out_dir / ("memmap_%d_%05.1fmin.json" % (pid, minute))
        _write(path, snap)
        taken.append(path)
        print(summarize(snap), flush=True)
    if trace_file is not None:
        trace_file.close()
        trace_k32.CloseHandle(trace_handle)
    if len(taken) >= 2:
        a = json.loads(taken[0].read_text(encoding="utf-8"))
        b = json.loads(taken[-1].read_text(encoding="utf-8"))
        print()
        print(diff(a, b))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
