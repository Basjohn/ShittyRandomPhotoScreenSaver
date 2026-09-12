"""Focused, hardware-free System Stats S0 source contracts."""
from __future__ import annotations

from types import SimpleNamespace

from core.system_stats.source import (
    PersistentWindowsGpuAdapterSource,
    WholeSystemCpuRamSource,
    adapter_identity_from_instance,
)


class _Times(tuple):
    def __new__(cls, user: float, system: float, idle: float):
        value = super().__new__(cls, (user, system, idle))
        value.idle = idle
        return value


def test_cpu_ram_first_cpu_observation_is_warming_then_uses_own_delta():
    times = iter((_Times(10, 20, 70), _Times(13, 22, 75)))
    source = WholeSystemCpuRamSource(
        cpu_times=lambda: next(times),
        virtual_memory=lambda: SimpleNamespace(total=1000, used=400),
    )
    first = source.sample()
    second = source.sample()
    assert first.cpu_status == "warming"
    assert first.cpu_pct is None
    assert first.ram_status == "ok"
    assert (first.ram_used_bytes, first.ram_total_bytes) == (400, 1000)
    assert second.cpu_status == "ok"
    assert second.cpu_pct == 50.0


def test_cpu_source_rejects_reset_negative_and_zero_deltas():
    times = iter((_Times(10, 20, 70), _Times(9, 20, 71), _Times(9, 20, 71)))
    source = WholeSystemCpuRamSource(
        cpu_times=lambda: next(times),
        virtual_memory=lambda: SimpleNamespace(total=1, used=0),
    )
    assert source.sample().cpu_status == "warming"
    assert source.sample().cpu_status == "invalid_delta"
    assert source.sample().cpu_status == "invalid_delta"


def test_ram_source_rejects_invalid_snapshot():
    source = WholeSystemCpuRamSource(
        cpu_times=lambda: _Times(1, 1, 1),
        virtual_memory=lambda: SimpleNamespace(total=100, used=101),
    )
    sample = source.sample()
    assert sample.ram_status == "invalid"
    assert sample.ram_used_bytes is None


class _Pdh:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.closed: list[object] = []
        self.collected = 0
        self.query = object()
        self.engine_instances = (
            "luid_0x00000000_0x00000001_phys_0_eng_3D",
            "luid_0x00000000_0x00000001_phys_0_eng_copy",
            "luid_0x00000000_0x00000002_phys_0_eng_3D",
        )
        self.memory_instances = (
            "luid_0x00000000_0x00000001_phys_0",
            "luid_0x00000000_0x00000002_phys_0",
        )
        self.values = {
            ("GPU Engine", self.engine_instances[0], "Utilization Percentage"): 40.0,
            ("GPU Engine", self.engine_instances[1], "Utilization Percentage"): 60.0,
            ("GPU Engine", self.engine_instances[2], "Utilization Percentage"): 25.0,
            ("GPU Adapter Memory", self.memory_instances[0], "Dedicated Usage"): 400,
            ("GPU Adapter Memory", self.memory_instances[0], "Dedicated Limit"): 1000,
            ("GPU Adapter Memory", self.memory_instances[1], "Dedicated Usage"): 200,
            ("GPU Adapter Memory", self.memory_instances[1], "Dedicated Limit"): 500,
        }

    def is_available(self): return self.available
    def open_query(self): return self.query
    def close_query(self, query): self.closed.append(query)
    def enumerate_instances(self, object_name):
        return self.engine_instances if object_name == "GPU Engine" else self.memory_instances
    def add_counter(self, _query, object_name, instance, counter_name): return (object_name, instance, counter_name)
    def collect(self, _query): self.collected += 1
    def read_double(self, counter): return self.values[counter]
    def read_large(self, counter): return self.values[counter]


def test_pdh_source_groups_only_same_adapter_and_uses_max_engine_not_sum():
    pdh = _Pdh()
    source = PersistentWindowsGpuAdapterSource(pdh)
    assert source.sample().status == "warming"
    sample = source.sample()
    assert sample.status == "ok"
    assert [(row.adapter_identity, row.gpu_pct, row.vram_used_bytes, row.vram_total_bytes) for row in sample.adapters] == [
        ("luid_0x00000000_0x00000001", 60.0, 400, 1000),
        ("luid_0x00000000_0x00000002", 25.0, 200, 500),
    ]
    assert sample.engine_counter_count == 3
    assert sample.memory_counter_count == 4
    source.close()
    assert pdh.closed == [pdh.query]
    assert source.cardinality() == {"query_open": False, "engine_counters": 0, "memory_counters": 0, "adapter_identities": 0}


def test_pdh_source_is_explicitly_unsupported_without_backend():
    source = PersistentWindowsGpuAdapterSource(_Pdh(available=False))
    sample = source.sample()
    assert sample.status == "unsupported"
    assert sample.adapters == ()
    assert sample.query_open is False


def test_pdh_query_failure_is_terminal_not_recurring_rediscovery():
    class _BrokenPdh(_Pdh):
        def enumerate_instances(self, _object_name):
            raise RuntimeError("PDH unavailable")

    pdh = _BrokenPdh()
    source = PersistentWindowsGpuAdapterSource(pdh)
    assert source.sample().status == "query_error"
    assert source.sample().status == "query_error"
    assert pdh.closed == [pdh.query]


def test_adapter_identity_requires_luid_not_process_or_arbitrary_instance():
    assert adapter_identity_from_instance("pid_1234_luid_0x00000000_0x00000001_phys_0") == "luid_0x00000000_0x00000001"
    assert adapter_identity_from_instance("pid_1234_eng_3d") is None
