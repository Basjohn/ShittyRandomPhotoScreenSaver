"""Small, hardware-neutral sources for the System Stats S0 admission probe.

The diagnostic ``--usage`` collector is intentionally not imported here: its
process accounting is neither cheap enough nor semantically valid for a
whole-system card.  These sources make one whole-system CPU/RAM observation
and, when Windows exposes suitable PDH counters, retain one adapter-scoped
query rather than rediscovering PID/process counters on every sample.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Protocol

import psutil


@dataclass(frozen=True)
class CpuRamSample:
    """One immutable whole-system CPU/RAM observation."""

    cpu_status: str
    cpu_pct: float | None
    ram_status: str
    ram_used_bytes: int | None
    ram_total_bytes: int | None


class WholeSystemCpuRamSource:
    """Use OS-wide cumulative CPU time and one memory-status snapshot.

    The source owns its baseline instead of using ``psutil.cpu_percent``'s
    module-global baseline.  That makes the first value honestly warming and
    avoids coupling the later product to diagnostics or another caller.
    """

    def __init__(
        self,
        *,
        cpu_times: Callable[[], Any] = psutil.cpu_times,
        virtual_memory: Callable[[], Any] = psutil.virtual_memory,
    ) -> None:
        self._cpu_times = cpu_times
        self._virtual_memory = virtual_memory
        self._previous_total: float | None = None
        self._previous_idle: float | None = None

    @staticmethod
    def _totals(times: Any) -> tuple[float, float] | None:
        try:
            values = tuple(float(value) for value in times)
            idle = float(getattr(times, "idle"))
        except (TypeError, ValueError, AttributeError):
            return None
        total = sum(values)
        if total < 0.0 or idle < 0.0 or idle > total:
            return None
        return total, idle

    def _read_cpu(self) -> tuple[str, float | None]:
        totals = self._totals(self._cpu_times())
        if totals is None:
            return "unavailable", None
        total, idle = totals
        previous_total = self._previous_total
        previous_idle = self._previous_idle
        self._previous_total = total
        self._previous_idle = idle
        if previous_total is None or previous_idle is None:
            return "warming", None
        delta_total = total - previous_total
        delta_idle = idle - previous_idle
        if delta_total <= 0.0 or delta_idle < 0.0 or delta_idle > delta_total:
            return "invalid_delta", None
        busy_pct = 100.0 * (delta_total - delta_idle) / delta_total
        if busy_pct < 0.0 or busy_pct > 100.0:
            return "invalid_delta", None
        return "ok", busy_pct

    def _read_ram(self) -> tuple[str, int | None, int | None]:
        try:
            memory = self._virtual_memory()
            total = int(getattr(memory, "total"))
            used = int(getattr(memory, "used"))
        except (TypeError, ValueError, AttributeError):
            return "unavailable", None, None
        if total <= 0 or used < 0 or used > total:
            return "invalid", None, None
        return "ok", used, total

    def sample(self) -> CpuRamSample:
        """Read CPU and RAM once; CPU needs one prior observation."""

        cpu_status, cpu_pct = self._read_cpu()
        ram_status, ram_used, ram_total = self._read_ram()
        return CpuRamSample(cpu_status, cpu_pct, ram_status, ram_used, ram_total)


class PdhAdapter(Protocol):
    """Minimal PDH seam, intentionally injectable for hardware-free tests."""

    def is_available(self) -> bool: ...
    def open_query(self) -> Any: ...
    def close_query(self, query: Any) -> None: ...
    def enumerate_instances(self, object_name: str) -> tuple[str, ...]: ...
    def add_counter(
        self, query: Any, object_name: str, instance: str, counter_name: str
    ) -> Any: ...
    def collect(self, query: Any) -> None: ...
    def read_double(self, counter: Any) -> float: ...
    def read_large(self, counter: Any) -> int: ...


class Win32PdhAdapter:
    """Thin lazy wrapper around pywin32 PDH; no import means unsupported."""

    def __init__(self) -> None:
        try:
            import win32pdh

            self._pdh: Any | None = win32pdh
        except (ImportError, OSError):
            self._pdh = None

    def is_available(self) -> bool:
        return self._pdh is not None

    def open_query(self) -> Any:
        return self._pdh.OpenQuery()

    def close_query(self, query: Any) -> None:
        self._pdh.CloseQuery(query)

    def enumerate_instances(self, object_name: str) -> tuple[str, ...]:
        _counters, instances = self._pdh.EnumObjectItems(
            None, None, object_name, self._pdh.PERF_DETAIL_WIZARD
        )
        return tuple(dict.fromkeys(str(instance) for instance in instances))

    def add_counter(
        self, query: Any, object_name: str, instance: str, counter_name: str
    ) -> Any:
        path = self._pdh.MakeCounterPath(
            (None, object_name, instance, None, -1, counter_name)
        )
        return self._pdh.AddCounter(query, path)

    def collect(self, query: Any) -> None:
        self._pdh.CollectQueryData(query)

    def read_double(self, counter: Any) -> float:
        _kind, value = self._pdh.GetFormattedCounterValue(
            counter, self._pdh.PDH_FMT_DOUBLE
        )
        return float(value)

    def read_large(self, counter: Any) -> int:
        _kind, value = self._pdh.GetFormattedCounterValue(
            counter, self._pdh.PDH_FMT_LARGE
        )
        return int(value)


_LUID_PATTERN = re.compile(r"(luid_0x[0-9a-f]+_0x[0-9a-f]+)", re.IGNORECASE)


def adapter_identity_from_instance(instance: str) -> str | None:
    """Return the PDH LUID identity shared by engine and memory instances."""

    match = _LUID_PATTERN.search(str(instance))
    return match.group(1).lower() if match is not None else None


@dataclass(frozen=True)
class AdapterGpuSample:
    """One adapter value; ``gpu_pct`` is max engine, never an engine sum."""

    adapter_identity: str
    gpu_pct: float | None
    vram_used_bytes: int | None
    vram_total_bytes: int | None


@dataclass(frozen=True)
class GpuVramSample:
    status: str
    adapters: tuple[AdapterGpuSample, ...]
    query_open: bool
    engine_counter_count: int
    memory_counter_count: int


class PersistentWindowsGpuAdapterSource:
    """Persistent PDH adapter candidate for S0, not a process-GPU collector."""

    _ENGINE_OBJECT = "GPU Engine"
    _MEMORY_OBJECT = "GPU Adapter Memory"
    _ENGINE_COUNTER = "Utilization Percentage"
    _DEDICATED_USAGE = "Dedicated Usage"
    _DEDICATED_LIMIT = "Dedicated Limit"

    def __init__(
        self,
        adapter: PdhAdapter | None = None,
        *,
        identity_from_instance: Callable[
            [str], str | None
        ] = adapter_identity_from_instance,
    ) -> None:
        self._adapter: PdhAdapter = adapter or Win32PdhAdapter()
        self._identity_from_instance = identity_from_instance
        self._query: Any | None = None
        self._engine_counters: dict[str, list[Any]] = {}
        self._usage_counters: dict[str, Any] = {}
        self._limit_counters: dict[str, Any] = {}
        self._warmed = False
        # A failed discovery/query is terminal for this source lifetime.  S0
        # must expose that failure, not rediscover counters every pulse and turn
        # an unavailable optional metric into recurring work.
        self._terminal_status: str | None = None

    def cardinality(self) -> dict[str, int | bool]:
        return {
            "query_open": self._query is not None,
            "engine_counters": sum(
                len(values) for values in self._engine_counters.values()
            ),
            "memory_counters": len(self._usage_counters) + len(self._limit_counters),
            "adapter_identities": len(
                set(self._engine_counters).union(
                    self._usage_counters, self._limit_counters
                )
            ),
        }

    def _snapshot(
        self, status: str, adapters: tuple[AdapterGpuSample, ...] = ()
    ) -> GpuVramSample:
        counts = self.cardinality()
        return GpuVramSample(
            status=status,
            adapters=adapters,
            query_open=bool(counts["query_open"]),
            engine_counter_count=int(counts["engine_counters"]),
            memory_counter_count=int(counts["memory_counters"]),
        )

    def _open(self) -> str:
        if not self._adapter.is_available():
            self._terminal_status = "unsupported"
            return "unsupported"
        query: Any | None = None
        try:
            query = self._adapter.open_query()
            engine_instances = self._adapter.enumerate_instances(self._ENGINE_OBJECT)
            memory_instances = self._adapter.enumerate_instances(self._MEMORY_OBJECT)
            for instance in engine_instances:
                identity = self._identity_from_instance(instance)
                if identity is not None:
                    self._engine_counters.setdefault(identity, []).append(
                        self._adapter.add_counter(
                            query, self._ENGINE_OBJECT, instance, self._ENGINE_COUNTER
                        )
                    )
            for instance in memory_instances:
                identity = self._identity_from_instance(instance)
                if identity is None:
                    continue
                self._usage_counters[identity] = self._adapter.add_counter(
                    query, self._MEMORY_OBJECT, instance, self._DEDICATED_USAGE
                )
                self._limit_counters[identity] = self._adapter.add_counter(
                    query, self._MEMORY_OBJECT, instance, self._DEDICATED_LIMIT
                )
            if not self._engine_counters and not self._usage_counters:
                self._adapter.close_query(query)
                self._terminal_status = "no_adapter_counters"
                return "no_adapter_counters"
            self._query = query
            self._adapter.collect(query)
            self._warmed = True
            return "warming"
        except Exception:
            if query is not None and self._query is None:
                try:
                    self._adapter.close_query(query)
                except Exception:
                    pass
            self.close()
            self._terminal_status = "query_error"
            return "query_error"

    def sample(self) -> GpuVramSample:
        """Collect retained counters; discovery happens only on first use."""

        if self._query is None:
            if self._terminal_status is not None:
                return self._snapshot(self._terminal_status)
            return self._snapshot(self._open())
        try:
            self._adapter.collect(self._query)
            identities = sorted(
                set(self._engine_counters).union(
                    self._usage_counters, self._limit_counters
                )
            )
            adapters: list[AdapterGpuSample] = []
            for identity in identities:
                engine_values = [
                    self._adapter.read_double(counter)
                    for counter in self._engine_counters.get(identity, ())
                ]
                valid_engines = [
                    value for value in engine_values if 0.0 <= value <= 100.0
                ]
                used = (
                    self._adapter.read_large(self._usage_counters[identity])
                    if identity in self._usage_counters
                    else None
                )
                total = (
                    self._adapter.read_large(self._limit_counters[identity])
                    if identity in self._limit_counters
                    else None
                )
                if used is not None and (
                    used < 0 or total is None or total <= 0 or used > total
                ):
                    used, total = None, None
                adapters.append(
                    AdapterGpuSample(
                        adapter_identity=identity,
                        gpu_pct=max(valid_engines) if valid_engines else None,
                        vram_used_bytes=used,
                        vram_total_bytes=total,
                    )
                )
            return self._snapshot("ok", tuple(adapters))
        except Exception:
            self.close()
            self._terminal_status = "query_error"
            return self._snapshot("query_error")

    def close(self) -> None:
        query, self._query = self._query, None
        self._engine_counters.clear()
        self._usage_counters.clear()
        self._limit_counters.clear()
        self._warmed = False
        if query is not None:
            try:
                self._adapter.close_query(query)
            except Exception:
                pass
