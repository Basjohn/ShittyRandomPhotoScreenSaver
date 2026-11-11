"""External resource readings for the invisible live check (``tools/visualizer_live_check.py --resource-readings``).

Read from OUTSIDE the saver (the live check's parent process), so nothing here runs in the app or changes what it
measures: psutil per process, the process handle snapshot by object type
(``NtQueryInformationProcess(ProcessHandleInformation)``), the pagefile-backed section views in each process's address
space (``VirtualQueryEx``, the ``shareable`` category of ``tools/win_memory_map.py``) and the named section objects of
the session (``\\Sessions\\<n>\\BaseNamedObjects``, ``NtQueryDirectoryObject``). Native core P2 gate 4 (dormancy and
lifecycle): no process, mapping or handle growth over Settings round trips and mode switches, the engine worker
retired with its generation.

* **Light samples** (every parent tick, ~1 s): the saver's tree (each process's handles, threads, RSS and private
  bytes) and the named ``srpss_viz_`` mappings. They show the worker's lifetime: which PID exists when.
* **Readings** at each lifecycle edge the runner's drivers record (a reveal in ``settings_roundtrip.json``, a completed
  mode switch in ``mode_switch.json``), ``settle_s`` after it (a lifecycle spike is not a reading: the lifecycle settles
  first): the light sample plus each process's handles by object type and its section views.
* **Verdict** (``analyse_resource_readings``): per cycle, per metric, a least-squares slope per cycle and a growth
  flag. Growth is a monotonic rise beyond noise: the fitted rise over the run exceeds both the metric's floor and twice
  the spread of the first readings, AND the later half's median sits above the earlier half's. Process and mapping
  counts must be exactly flat. Over mode switches the memory metrics are judged per mode instead, from each mode's
  second visit on (``growth_by_mode``): a mode's first visit precedes the heavier modes' high-water.

Roles: the saver's own process is the tree's ``--runner`` process with no ``--runner`` child (a venv launcher is its
parent); every ``--multiprocessing-fork`` child is a worker, and its role comes from the supervisor's own log line
(``Started <role> worker (PID: n)``).
"""
from __future__ import annotations

import ctypes
import json
import re
import statistics
import sys
import time
from ctypes import wintypes as wt
from pathlib import Path

VIZ_MAPPING_PREFIX = "srpss_viz_"
DEFAULT_SETTLE_S = 5.0
USAGE_PAIRING_S = 5.0          # the app's own --usage sample paired with a reading lies within this
# Size of one engine-worker frame mapping's view: the ABI header plus three 1 MiB slots, rounded up to a page
# (``core/visualizer_engine/packet_abi.mapping_bytes``; a view's regions sum to its page-rounded size).
VIZ_VIEW_RESERVED = ((64 + 3 * (1 << 20)) + 0xFFF) & ~0xFFF

_STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
_STATUS_MORE_ENTRIES = 0x00000105
_STATUS_NO_MORE_ENTRIES = 0x8000001A
_PROCESS_QUERY_INFORMATION = 0x0400
_PROCESS_VM_READ = 0x0010
_PROCESS_HANDLE_INFORMATION = 51
_OBJECT_TYPES_INFORMATION = 3
_DIRECTORY_QUERY = 0x0001
_MEM_MAPPED = 0x40000


# -- native helpers (Windows only; imported lazily so the module still imports elsewhere) -----------------------------

class _UnicodeString(ctypes.Structure):
    _fields_ = [("Length", wt.USHORT), ("MaximumLength", wt.USHORT), ("Buffer", ctypes.c_void_p)]


class _ObjectAttributes(ctypes.Structure):
    _fields_ = [("Length", wt.ULONG), ("RootDirectory", wt.HANDLE), ("ObjectName", ctypes.POINTER(_UnicodeString)),
                ("Attributes", wt.ULONG), ("SecurityDescriptor", ctypes.c_void_p),
                ("SecurityQualityOfService", ctypes.c_void_p)]


class _DirectoryEntry(ctypes.Structure):
    _fields_ = [("Name", _UnicodeString), ("TypeName", _UnicodeString)]


def _status(value: int) -> int:
    return value & 0xFFFFFFFF


class NativeReader:
    """The handle-type table, per-process handle snapshots, section views and the session's named objects."""

    def __init__(self) -> None:
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.ntdll = ctypes.WinDLL("ntdll")
        self.k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        self.k32.OpenProcess.restype = wt.HANDLE
        self.k32.CloseHandle.argtypes = [wt.HANDLE]
        self.ntdll.NtQueryInformationProcess.argtypes = [wt.HANDLE, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong,
                                                         ctypes.POINTER(ctypes.c_ulong)]
        self.ntdll.NtQueryInformationProcess.restype = ctypes.c_long
        self.ntdll.NtQueryObject.argtypes = [wt.HANDLE, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong,
                                             ctypes.POINTER(ctypes.c_ulong)]
        self.ntdll.NtQueryObject.restype = ctypes.c_long
        self.ntdll.NtOpenDirectoryObject.argtypes = [ctypes.POINTER(wt.HANDLE), wt.DWORD,
                                                     ctypes.POINTER(_ObjectAttributes)]
        self.ntdll.NtOpenDirectoryObject.restype = ctypes.c_long
        self.ntdll.NtQueryDirectoryObject.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG, wt.BOOLEAN, wt.BOOLEAN,
                                                      ctypes.POINTER(wt.ULONG), ctypes.POINTER(wt.ULONG)]
        self.ntdll.NtQueryDirectoryObject.restype = ctypes.c_long
        self.type_names = self._object_type_names()

    # The object type table (index -> name), checked against a section this process creates.
    def _object_type_names(self) -> dict[int, str]:
        size = 1 << 16
        while True:
            buffer = ctypes.create_string_buffer(size)
            needed = ctypes.c_ulong(0)
            status = _status(self.ntdll.NtQueryObject(None, _OBJECT_TYPES_INFORMATION, buffer, size,
                                                      ctypes.byref(needed)))
            if status == _STATUS_INFO_LENGTH_MISMATCH:
                size = max(size * 2, needed.value + 4096)
                continue
            if status != 0:
                return {}
            break
        raw = buffer.raw
        count = int.from_bytes(raw[0:4], "little")
        names: dict[int, str] = {}
        offset = 8
        base = ctypes.addressof(buffer)
        for _ in range(count):
            length = int.from_bytes(raw[offset:offset + 2], "little")
            maximum = int.from_bytes(raw[offset + 2:offset + 4], "little")
            pointer = int.from_bytes(raw[offset + 8:offset + 16], "little")
            index = raw[offset + 0x5A]
            name = ""
            if pointer and base <= pointer < base + size:
                start = pointer - base
                name = raw[start:start + length].decode("utf-16-le", errors="replace")
            names[int(index)] = name
            offset = (offset + 0x68 + maximum + 7) & ~7
        # Verify the layout: a section this process creates must be typed "Section".
        section = self.k32.CreateFileMappingW(wt.HANDLE(-1), None, 0x04, 0, 4096, None)
        try:
            own = self.handle_entries(self.k32.GetCurrentProcess())
            index = next((type_index for handle, type_index in own if handle == int(section or 0)), None)
        finally:
            if section:
                self.k32.CloseHandle(section)
        if index is None or names.get(index) != "Section":
            return {}
        return names

    def handle_entries(self, process_handle) -> list[tuple[int, int]]:
        """(handle value, object type index) of every handle in the process (ProcessHandleInformation)."""
        size = 1 << 16
        while True:
            buffer = ctypes.create_string_buffer(size)
            needed = ctypes.c_ulong(0)
            status = _status(self.ntdll.NtQueryInformationProcess(process_handle, _PROCESS_HANDLE_INFORMATION, buffer,
                                                                  size, ctypes.byref(needed)))
            if status == _STATUS_INFO_LENGTH_MISMATCH:
                size = max(size * 2, needed.value + 4096)
                continue
            if status != 0:
                raise OSError(f"NtQueryInformationProcess(ProcessHandleInformation) failed: {status:#x}")
            break
        raw = buffer.raw
        count = int.from_bytes(raw[0:8], "little")
        entries = []
        for i in range(count):
            at = 16 + 40 * i
            entries.append((int.from_bytes(raw[at:at + 8], "little"), int.from_bytes(raw[at + 28:at + 32], "little")))
        return entries

    def _open(self, pid: int, access: int):
        handle = self.k32.OpenProcess(access, False, int(pid))
        if not handle:
            raise OSError(ctypes.get_last_error(), f"OpenProcess({pid}) failed")
        return handle

    def handle_types(self, pid: int) -> dict[str, int]:
        handle = self._open(pid, _PROCESS_QUERY_INFORMATION)
        try:
            entries = self.handle_entries(handle)
        finally:
            self.k32.CloseHandle(handle)
        counts: dict[str, int] = {}
        for _value, type_index in entries:
            name = self.type_names.get(type_index) or f"type_{type_index}"
            counts[name] = counts.get(name, 0) + 1
        return dict(sorted(counts.items()))

    def section_views(self, pid: int) -> dict:
        """Pagefile-backed section views (shared memory) mapped in the process, and how many are frame-mapping sized."""
        from tools import win_memory_map

        k32, psapi, _ntdll = win_memory_map._win32()
        handle = k32.OpenProcess(_PROCESS_QUERY_INFORMATION | _PROCESS_VM_READ, False, int(pid))
        if not handle:
            raise OSError(ctypes.get_last_error(), f"OpenProcess({pid}) failed")
        try:
            views: dict[int, int] = {}
            for region in win_memory_map._regions(k32, handle):
                if region["type"] == _MEM_MAPPED:
                    views[region["alloc_base"]] = views.get(region["alloc_base"], 0) + region["size"]
            shareable = {base: size for base, size in views.items()
                         if win_memory_map._mapped_name(psapi, handle, base) is None}
        finally:
            k32.CloseHandle(handle)
        return {"shareable_views": len(shareable), "shareable_mb": round(sum(shareable.values()) / 2**20, 2),
                "viz_sized_views": sum(1 for size in shareable.values() if size == VIZ_VIEW_RESERVED)}

    def named_objects(self, prefix: str = "srpss") -> list[tuple[str, str]]:
        """(name, type) of every object in this session's BaseNamedObjects whose name starts with ``prefix``."""
        session = wt.DWORD(0)
        self.k32.ProcessIdToSessionId(self.k32.GetCurrentProcessId(), ctypes.byref(session))
        path = f"\\Sessions\\{session.value}\\BaseNamedObjects" if session.value else "\\BaseNamedObjects"
        text = ctypes.create_unicode_buffer(path)
        name = _UnicodeString(len(path) * 2, len(path) * 2 + 2, ctypes.cast(text, ctypes.c_void_p))
        attributes = _ObjectAttributes(ctypes.sizeof(_ObjectAttributes), None, ctypes.pointer(name), 0x40, None, None)
        directory = wt.HANDLE()
        status = _status(self.ntdll.NtOpenDirectoryObject(ctypes.byref(directory), _DIRECTORY_QUERY,
                                                          ctypes.byref(attributes)))
        if status != 0:
            raise OSError(f"NtOpenDirectoryObject({path}) failed: {status:#x}")
        found: list[tuple[str, str]] = []
        try:
            context, restart = wt.ULONG(0), True
            size = 1 << 16
            buffer = ctypes.create_string_buffer(size)
            entry_size = ctypes.sizeof(_DirectoryEntry)
            while True:
                returned = wt.ULONG(0)
                status = _status(self.ntdll.NtQueryDirectoryObject(directory, buffer, size, False, restart,
                                                                   ctypes.byref(context), ctypes.byref(returned)))
                restart = False
                if status == _STATUS_NO_MORE_ENTRIES:
                    break
                if status not in (0, _STATUS_MORE_ENTRIES):
                    raise OSError(f"NtQueryDirectoryObject failed: {status:#x}")
                base = ctypes.addressof(buffer)
                for i in range(size // entry_size):
                    entry = _DirectoryEntry.from_address(base + i * entry_size)
                    if not entry.Name.Buffer:
                        break
                    object_name = ctypes.wstring_at(entry.Name.Buffer, entry.Name.Length // 2)
                    if object_name.startswith(prefix):
                        found.append((object_name, ctypes.wstring_at(entry.TypeName.Buffer,
                                                                      entry.TypeName.Length // 2)))
                if status == 0:
                    break
        finally:
            self.k32.CloseHandle(directory)
        return sorted(found)


# -- the sampler (parent side) --------------------------------------------------------------------------------------

def _tree(root_pid: int) -> list:
    import psutil

    try:
        root = psutil.Process(root_pid)
        return [root, *root.children(recursive=True)]
    except psutil.Error:
        return []


def _process_row(process) -> dict | None:
    import psutil

    try:
        with process.oneshot():
            memory = process.memory_info()
            cmd = process.cmdline()
            return {"pid": process.pid, "ppid": process.ppid(), "created": process.create_time(),
                    "handles": process.num_handles(), "threads": process.num_threads(),
                    "rss_mb": round(memory.rss / 2**20, 1),
                    "private_mb": round(getattr(memory, "private", 0) / 2**20, 1),
                    "runner": "--runner" in cmd, "worker": "--multiprocessing-fork" in cmd}
    except psutil.Error:
        return None


def classify_tree(rows: list[dict]) -> list[dict]:
    """Mark the saver's own process (``main``): the ``--runner`` process with no ``--runner`` child."""
    runners = {row["pid"] for row in rows if row["runner"]}
    parents_of_runners = {row["ppid"] for row in rows if row["runner"]}
    for row in rows:
        row["main"] = row["pid"] in runners and row["pid"] not in parents_of_runners
    return rows


class TreeResourceSampler:
    """Parent side: light samples every tick, full readings ``settle_s`` after each lifecycle edge."""

    def __init__(self, root_pid: int, out: Path, *, settle_s: float = DEFAULT_SETTLE_S, native=None) -> None:
        self.root_pid = int(root_pid)
        self.out = Path(out)
        self.settle_s = float(settle_s)
        self.readings: list[dict] = []
        self._seen_edges: set[tuple] = set()
        self._due: list[tuple[float, dict]] = []
        self._native = native
        self._native_error: str | None = None
        self._samples = (self.out / "resource_samples.jsonl").open("a", encoding="utf-8")

    def native(self):
        if self._native is None and self._native_error is None:
            try:
                self._native = NativeReader()
            except Exception as exc:  # observation only
                self._native_error = repr(exc)
        return self._native

    def light(self) -> dict:
        rows = classify_tree([row for row in map(_process_row, _tree(self.root_pid)) if row is not None])
        sample = {"wall": time.time(), "processes": rows}
        native = self.native()
        if native is not None:
            try:
                sample["viz_mappings"] = [name for name, kind in native.named_objects(VIZ_MAPPING_PREFIX)
                                          if kind == "Section"]
            except OSError as exc:
                sample["viz_mappings_error"] = str(exc)
        return sample

    def full(self, edge: dict) -> dict:
        reading = self.light()
        reading["edge"] = edge
        native = self.native()
        reading["native_error"] = self._native_error
        if native is not None:
            try:
                reading["srpss_named_objects"] = native.named_objects("srpss")
            except OSError as exc:
                reading["srpss_named_objects_error"] = str(exc)
            for row in reading["processes"]:
                if not (row["main"] or row["worker"]):
                    continue
                try:
                    row["handle_types"] = native.handle_types(row["pid"])
                    row.update(native.section_views(row["pid"]))
                except OSError as exc:
                    row["native_error"] = str(exc)
        return reading

    def poll(self, edges: list[dict]) -> None:
        """One parent tick: a light sample, and every reading now due (``edges``: the runner's recorded edges)."""
        now = time.time()
        self._samples.write(json.dumps(self.light()) + "\n")
        self._samples.flush()
        for edge in edges:
            key = (edge.get("kind"), edge.get("index"), edge.get("wall"))
            if key in self._seen_edges or edge.get("wall") is None:
                continue
            self._seen_edges.add(key)
            self._due.append((float(edge["wall"]) + self.settle_s, edge))
        ready = [item for item in self._due if item[0] <= now]
        self._due = [item for item in self._due if item[0] > now]
        for due_at, edge in sorted(ready, key=lambda item: item[0]):
            reading = self.full(edge)
            reading["late_s"] = round(reading["wall"] - due_at, 2)
            self.readings.append(reading)
            self._flush()

    def _flush(self) -> None:
        (self.out / "resource_readings.json").write_text(
            json.dumps({"settle_s": self.settle_s, "readings": self.readings}, indent=1), encoding="utf-8")

    def close(self) -> None:
        self._samples.close()
        self._flush()


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None          # absent, or being rewritten by the runner: the next tick reads it


def recorded_edges(out: Path) -> list[dict]:
    """The lifecycle edges the runner's drivers recorded so far: Settings reveals and completed mode switches."""
    edges: list[dict] = []
    state = _read_json(Path(out) / "settings_roundtrip.json")
    if state:
        reveals = [event for event in state.get("events", []) if event.get("event") == "reveal"]
        for ordinal, event in enumerate(reveals):
            edges.append({"kind": "settings_reveal", "index": ordinal, "wall": event.get("wall"),
                          "generation": event.get("generation")})
    state = _read_json(Path(out) / "mode_switch.json")
    if state:
        for event in state.get("events", []):
            if event.get("event") == "reveal":
                edges.append({"kind": "startup_reveal", "index": 0, "wall": event.get("wall"),
                              "generation": event.get("generation")})
        for record in state.get("switches", []):
            if record.get("completed"):
                edges.append({"kind": "mode_switch", "index": int(record["index"]) + 1,
                              "wall": record.get("completed_wall"), "mode": record.get("completed_mode")})
    return edges


# -- analysis -------------------------------------------------------------------------------------------------------

def worker_roles(log_dir: Path) -> dict[int, str]:
    """PID -> role from the supervisor's own start lines in every main-log part."""
    roles: dict[int, str] = {}
    for path in sorted(Path(log_dir).glob("screensaver.log*")):
        for match in re.finditer(r"Started (\w+) worker \(PID: (\d+)\)",
                                 path.read_text(encoding="utf-8", errors="replace")):
            roles[int(match.group(2))] = match.group(1)
    return roles


_USAGE_FIELDS = ("processes", "children", "threads_app", "handles_app", "handles_main", "rss_main_mb",
                 "private_main_mb", "visualizer_worker_pid", "visualizer_worker_rss_mb", "visualizer_worker_threads",
                 "shm_segments_live")


def usage_rows(usage_log: Path) -> list[dict]:
    """The app's own ``--usage`` samples (wall time to the second, as the logger stamps them)."""
    import datetime as dt

    rows = []
    if not Path(usage_log).exists():
        return rows
    for line in Path(usage_log).read_text(encoding="utf-8", errors="replace").splitlines():
        if "[USAGE] sample" not in line:
            continue
        stamp = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", line)
        row = {"wall": dt.datetime.strptime(stamp.group(1), "%Y-%m-%d %H:%M:%S").timestamp() if stamp else None}
        for field in _USAGE_FIELDS:
            match = re.search(rf"\b{field}=(\S+)", line)
            if match:
                value = match.group(1)
                try:
                    row[field] = float(value) if "." in value else int(value)
                except ValueError:
                    row[field] = value
        rows.append(row)
    return rows


def _fit_slope(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean_x, mean_y = (n - 1) / 2.0, statistics.fmean(values)
    numerator = sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values))
    denominator = sum((i - mean_x) ** 2 for i in range(n))
    return numerator / denominator


#: A metric's floor: a fitted rise over the whole run below it is never growth (counts are exact: any rise counts).
FLOORS = {"processes": 0.5, "workers": 0.5, "viz_mappings": 0.5, "viz_views_main": 0.5, "viz_views_worker": 0.5,
          "handles_main": 10.0, "handles_worker": 10.0, "handles_tree": 10.0, "threads_main": 2.0,
          "threads_worker": 2.0, "rss_main_mb": 5.0, "private_main_mb": 5.0, "rss_worker_mb": 5.0,
          "private_worker_mb": 5.0, "sections_main": 0.5, "sections_worker": 0.5, "files_main": 4.0,
          "events_main": 4.0, "semaphores_main": 2.0}
EXACT = ("processes", "workers", "engine_workers", "viz_mappings", "viz_views_main", "viz_views_worker")


def growth(values: list[float], floor: float) -> dict:
    """Slope per cycle and whether the series grows: a monotonic rise beyond noise (module docstring)."""
    values = [float(v) for v in values if v is not None]
    if len(values) < 4:
        return {"n": len(values), "slope": None, "growth": None}
    slope = _fit_slope(values)
    rise = slope * (len(values) - 1)
    head = values[:5]
    noise = max(head) - min(head)
    half = len(values) // 2
    later_higher = statistics.median(values[half:]) > statistics.median(values[:half])
    grows = rise > max(floor, 2.0 * noise) and later_higher
    steps = [b - a for a, b in zip(values, values[1:])]
    return {"n": len(values), "first": values[0], "last": values[-1], "min": min(values), "max": max(values),
            "slope": round(slope, 3), "fitted_rise": round(rise, 2), "head_spread": round(noise, 2),
            "rises": sum(1 for s in steps if s > 0), "falls": sum(1 for s in steps if s < 0), "growth": grows}


#: Memory metrics whose reading depends on the mode drawn: over mode switches each mode is judged against its own
#: earlier visits, never as one series across modes.
MODE_DEPENDENT = ("rss_main_mb", "private_main_mb", "rss_worker_mb", "private_worker_mb")


def growth_by_mode(cycles: list[dict], metric: str, floor: float) -> dict | None:
    """One memory metric over mode-switch readings, each mode against its own earlier visits.

    A lap of switches visits modes of very different size, and the first visit of a mode comes before the heavier
    modes have set the process's high-water (the GPU driver keeps what they committed, largely not resident: measured
    11 Nov 2026, +100 to +190 MB of private bytes from a mode's first visit to its second on both process paths, then
    flat). So the step from the first visit to the second is reported and never judged; growth is a rise from the
    second visit on: the median later step above the floor with most later steps rising. With no later visit of any
    mode there is nothing to judge (``growth`` None). None when the readings hold no repeated mode at all.
    """
    visits: dict[str, list[float]] = {}
    for row in cycles:
        if row.get("kind") == "mode_switch" and row.get("mode") and row.get(metric) is not None:
            visits.setdefault(str(row["mode"]), []).append(float(row[metric]))
    if not visits or max(len(values) for values in visits.values()) < 2:
        return None
    first = [values[1] - values[0] for values in visits.values() if len(values) >= 2]
    later = [b - a for values in visits.values() for a, b in zip(values[1:], values[2:])]
    grows = None
    if later:
        grows = bool(statistics.median(later) > floor and sum(1 for step in later if step > 0) > len(later) / 2)
    return {"modes": len(visits), "visits": max(len(values) for values in visits.values()),
            "first_step_median": round(statistics.median(first), 2), "first_step_max": round(max(first), 2),
            "later_steps": len(later), "later_step_median": round(statistics.median(later), 2) if later else None,
            "later_step_max": round(max(later), 2) if later else None, "growth": grows}


def reading_row(reading: dict, roles: dict[int, str]) -> dict:
    """One reading as the per-cycle table's row (the main process, the engine worker, the tree)."""
    processes = reading["processes"]
    main = next((row for row in processes if row.get("main")), None)
    # The supervisor's workers (named by its own log); any other spawn child is another owner's (the FEEDS parser's
    # lazy process pool comes and goes with its refreshes) and is reported, never judged.
    workers = [row for row in processes if row.get("worker") and row["pid"] in roles]
    others = [row for row in processes if row.get("worker") and row["pid"] not in roles]
    engine = [row for row in workers if roles.get(row["pid"]) == "visualizer"]
    worker = engine[0] if len(engine) == 1 else None
    edge = reading.get("edge", {})
    row = {"kind": edge.get("kind"), "index": edge.get("index"), "mode": edge.get("mode"),
           "generation": edge.get("generation"), "wall": round(reading["wall"], 1), "late_s": reading.get("late_s"),
           "processes": (1 if main else 0) + len(workers),
           "workers": len(workers), "engine_workers": len(engine),
           "engine_worker_pid": worker["pid"] if worker else None,
           "worker_pids": sorted(p["pid"] for p in workers), "other_child_pids": sorted(p["pid"] for p in others),
           "viz_mappings": len(reading.get("viz_mappings", [])) if "viz_mappings" in reading else None,
           "handles_tree": sum(p["handles"] for p in [*([main] if main else []), *workers])}
    for prefix, process in (("main", main), ("worker", worker)):
        if process is None:
            continue
        row[f"handles_{prefix}"] = process["handles"]
        row[f"threads_{prefix}"] = process["threads"]
        row[f"rss_{prefix}_mb"] = process["rss_mb"]
        row[f"private_{prefix}_mb"] = process["private_mb"]
        types = process.get("handle_types") or {}
        if types:
            row[f"sections_{prefix}"] = types.get("Section", 0)
            row[f"files_{prefix}"] = types.get("File", 0)
            row[f"events_{prefix}"] = types.get("Event", 0)
            row[f"semaphores_{prefix}"] = types.get("Semaphore", 0)
            row[f"threads_objects_{prefix}"] = types.get("Thread", 0)
        if "viz_sized_views" in process:
            row[f"viz_views_{prefix}"] = process["viz_sized_views"]
            row[f"shareable_views_{prefix}"] = process["shareable_views"]
    return row


def analyse_resource_readings(out: Path, *, kinds: tuple[str, ...]) -> dict:
    """The per-cycle table and each metric's growth verdict over the readings of ``kinds`` (startup excluded)."""
    out = Path(out)
    state = _read_json(out / "resource_readings.json") or {"readings": []}
    roles = worker_roles(out / "logs")
    rows = [reading_row(reading, roles) for reading in state["readings"]]
    usage = usage_rows(out / "logs" / "screensaver_usage.log")
    for row in rows:
        # The app's own sample nearest the reading (it samples every 15 s): within USAGE_PAIRING_S, else none (a
        # sample further away may sit inside the next lifecycle edge).
        near = [u for u in usage if u["wall"] is not None and abs(u["wall"] - row["wall"]) <= USAGE_PAIRING_S]
        row["usage"] = min(near, key=lambda u: abs(u["wall"] - row["wall"])) if near else None
    cycles = [row for row in rows if row["kind"] in kinds and not (row["kind"] == "settings_reveal"
                                                                   and row["index"] == 0)]
    metrics = sorted({key for row in cycles for key, value in row.items()
                      if isinstance(value, (int, float)) and not isinstance(value, bool)
                      and key not in ("index", "wall", "late_s", "generation", "engine_worker_pid")})
    verdicts = {metric: growth([row.get(metric) for row in cycles], FLOORS.get(metric, 0.0)) for metric in metrics}
    for metric in MODE_DEPENDENT:
        by_mode = growth_by_mode(cycles, metric, FLOORS.get(metric, 0.0)) if metric in verdicts else None
        if by_mode is not None:
            # The series across modes is kept for the table; the verdict is the per-mode one.
            verdicts[metric] = {**verdicts[metric], "series_growth": verdicts[metric].get("growth"),
                                "by_mode": by_mode, "growth": by_mode["growth"]}
    exact_changes = {metric: sorted({row.get(metric) for row in cycles} - {None})
                     for metric in EXACT if metric in metrics}
    grown = sorted(metric for metric, verdict in verdicts.items() if verdict.get("growth"))
    not_flat = sorted(metric for metric, values in exact_changes.items() if len(values) > 1)
    worker_pids = [row["engine_worker_pid"] for row in cycles]
    return {"roles": {str(pid): role for pid, role in sorted(roles.items())}, "rows": rows,
            "cycles": len(cycles), "metrics": verdicts, "exact_values": exact_changes,
            "growth": grown, "exact_not_flat": not_flat,
            "distinct_engine_worker_pids": len({pid for pid in worker_pids if pid is not None}),
            "readings_without_one_engine_worker": sum(1 for row in cycles if row["engine_workers"] != 1)}


TABLE_COLUMNS = (("index", "#"), ("mode", "mode"), ("processes", "proc"), ("engine_worker_pid", "worker"),
                 ("viz_mappings", "maps"), ("viz_views_main", "vmain"), ("viz_views_worker", "vwork"),
                 ("handles_main", "h_main"), ("handles_worker", "h_work"), ("sections_main", "sec_m"),
                 ("files_main", "file_m"), ("threads_main", "t_main"), ("threads_worker", "t_work"),
                 ("rss_main_mb", "rss_m"), ("private_main_mb", "priv_m"), ("rss_worker_mb", "rss_w"),
                 ("private_worker_mb", "priv_w"))


def print_resource_table(summary: dict) -> None:
    print("resource readings (" + ", ".join(label for _, label in TABLE_COLUMNS) + ")")
    for row in summary["rows"]:
        cells = []
        for key, _label in TABLE_COLUMNS:
            value = row.get(key)
            cells.append("-" if value is None else (f"{value:g}" if isinstance(value, float) else str(value)))
        print(f"  {row['kind']:16s} " + " ".join(f"{cell:>8s}" for cell in cells))
    for metric, verdict in summary["metrics"].items():
        by_mode = verdict.get("by_mode")
        if by_mode is not None:
            judged = ("not judged (no mode was visited three times)" if by_mode["growth"] is None
                      else "GROWTH" if by_mode["growth"] else "flat")
            print(f"  {metric:22s} by mode, {by_mode['visits']} visits: first step median "
                  f"{by_mode['first_step_median']:>8} (reported, never judged); later steps "
                  f"{by_mode['later_steps']} median {by_mode['later_step_median']} max {by_mode['later_step_max']} "
                  f"{judged}")
        elif verdict.get("slope") is not None:
            print(f"  {metric:22s} slope/cycle {verdict['slope']:>9} rise {verdict['fitted_rise']:>8} "
                  f"head spread {verdict['head_spread']:>7} {'GROWTH' if verdict['growth'] else 'flat'}")
    print(f"resource verdict: {summary['cycles']} cycles, growth {summary['growth'] or 'none'}, "
          f"exact counts not flat {summary['exact_not_flat'] or 'none'}, "
          f"distinct engine worker PIDs {summary['distinct_engine_worker_pids']}, "
          f"readings without exactly one engine worker {summary['readings_without_one_engine_worker']}")


if __name__ == "__main__" and sys.platform == "win32":    # a manual check: the current session's srpss objects
    reader = NativeReader()
    print(len(reader.type_names), "object types;", reader.named_objects("srpss"))
