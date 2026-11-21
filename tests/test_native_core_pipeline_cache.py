"""N3.6's pipeline cache box: the core's own file for the job thread's QRhi (``native/core/src/pipeline_cache.h``,
``job_service.cpp``'s ``RhiUploadBackend``; Current_Plan.md item 8b, "N3.6 Lifetime").

- On the built module (``release/native_module``; skipped without it, and saying so): ``pipeline_cache_self_test``
  runs the module's own format, file and writers in a temporary directory: the file it writes is accepted and read back
  equal, each refusal differs from the accepted file in its one fact (the controls), and two writer threads replacing
  the file while it is read never give a torn read.
- Without the module: the job QRhi's load and save read from the source in their decided places (each reading with its
  negative control in the test), and the Python face.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from rendering.native import loader

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "native" / "core"
MODULE_DIR = ROOT / "release" / "native_module"
BUILT = os.name == "nt" and (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()

needs_module = pytest.mark.skipif(
    not BUILT,
    reason=f"the native core is not built in this checkout: no release/native_module/{loader.MODULE_NAME}.pyd",
)

#: The refusals the self-test makes, each named by the one fact its file or device differs in.
REFUSALS = ("driver_version", "vendor", "device", "cache_uuid", "backend", "abi", "short", "size", "checksum", "magic",
            "format", "sections")


@needs_module
def test_the_core_file_round_trips_refuses_every_mismatch_and_is_never_torn(tmp_path):
    core = loader.load(MODULE_DIR)
    if core.abi < 30:
        pytest.skip(f"the built module is ABI {core.abi}, before N3.6's pipeline cache")
    result = core.pipeline_cache_self_test(tmp_path)
    assert result["accepted"] and result["two_sections_accepted"]
    assert result["refusals"] == {name: name for name in REFUSALS}
    assert all(count == 0 for count in result["refusals_left_sections"].values())   # a refusal hands nothing over
    assert result["absent"]["result"] == "absent"
    assert result["save_committed"] and result["loaded"]["result"] == "accepted" and result["round_trip_equal"]
    assert result["other_device"]["result"] == "rejected: device" and result["other_device_sections"] == 0
    c = result["concurrency"]
    assert c["torn"] == 0, c["torn_results"]
    assert c["reads"] >= 200 and c["read_a"] + c["read_b"] > 0
    assert c["writer_a_saved"] > 0 and c["writer_b_saved"] > 0
    assert c["final_is_one_writers"] and c["files_left"] == ["srpss_core_vulkan"]   # no temporary file left


# ------------------------------------------------------------------------------------------- the source's places


def _body(source: str, signature: str) -> str:
    start = source.index(signature)
    open_brace = source.index("{", start)
    depth = 0
    for index in range(open_brace, len(source)):
        depth += {"{": 1, "}": -1}.get(source[index], 0)
        if depth == 0:
            return source[open_brace:index + 1]
    raise ValueError(f"{signature} has no closing brace")


def job_qrhi_cache_problems(source: str) -> list[str]:
    """The job QRhi keeps its cache's data (the flag), loads the core's file right after its creation and before any
    pipeline, and saves it in its orderly teardown before the QRhi goes, never after a device loss."""
    problems = []
    set_up = _body(source, "bool setUp(QString *error) override")
    tear_down = _body(source, "void tearDown() override")
    if "QRhi::EnablePipelineCacheDataSave" not in set_up:
        problems.append("the job QRhi keeps no pipeline cache data")
    create, load = set_up.find("QRhi::create("), set_up.find("setPipelineCacheData(")
    if load < 0 or load < create:
        problems.append("the file is not loaded into the job QRhi after its creation")
    lost, data, reset = (tear_down.find("deviceLost()"), tear_down.find("pipelineCacheData()"),
                         tear_down.find("m_rhi.reset();"))
    if data < 0 or reset < 0 or data > reset:
        problems.append("the job QRhi's data is not saved before it goes")
    if lost < 0 or lost > data:
        problems.append("a lost device's cache would be saved")
    if "savePipelineCache(" not in tear_down:
        problems.append("the teardown writes no file")
    return problems


def test_the_job_qrhi_loads_at_creation_and_saves_at_its_orderly_teardown():
    source = (CORE / "src" / "job_service.cpp").read_text(encoding="utf-8")
    assert job_qrhi_cache_problems(source) == []
    # Negative controls: the save after the QRhi went, and no loss guard.
    tear_down = _body(source, "void tearDown() override")
    late = tear_down.replace("m_rhi.reset(); // QRhiVulkan::destroy", "// moved", 1).replace(
        "QJsonObject cache;\n        if (m_rhi) {", "QJsonObject cache;\n        m_rhi.reset();\n        if (m_rhi) {", 1)
    assert late != tear_down and job_qrhi_cache_problems(source.replace(tear_down, late))
    unguarded = tear_down.replace("if (deviceLost())", "if (false)", 1)
    assert unguarded != tear_down and job_qrhi_cache_problems(source.replace(tear_down, unguarded))


def test_the_file_sits_beside_qt_quicks_own():
    source = (CORE / "src" / "pipeline_cache.cpp").read_text(encoding="utf-8")
    body = _body(source, "QString pipelineCacheDirectory()")
    assert "QStandardPaths::CacheLocation" in body and re.search(
        r'QStringLiteral\("qtpipelinecache-"\) \+ QSysInfo::buildAbi\(\)', body)
    assert 'QStringLiteral("srpss_core_") + backend' in source
    assert "QSaveFile file(path);" in _body(source, "bool savePipelineCache(")


def test_the_job_harness_reads_the_load_and_the_save_from_the_stop_record():
    import sys

    sys.path.insert(0, str(CORE / "python"))
    import job_service_check as jsc

    stop = {"thread_started": True, "pipeline_cache_load": {"result": "absent"},
            "pipeline_cache_save": {"save": "nothing to save: the job QRhi built no pipeline"}}
    close = {"device_teardown": ["job service stopped: " + json.dumps(stop), "vkDeviceWaitIdle: VK_SUCCESS"]}
    records = jsc.pipeline_cache_records(close)
    assert records == [stop] and jsc.pipeline_cache_by_rule(records)
    written = dict(stop, pipeline_cache_save={"saved_bytes": 1234.0})
    assert jsc.pipeline_cache_by_rule([written])
    # Negative controls: no load, no save, a failed save, two services.
    for bad in ({k: v for k, v in stop.items() if k != "pipeline_cache_load"},
                {k: v for k, v in stop.items() if k != "pipeline_cache_save"},
                dict(stop, pipeline_cache_save={"save_failed": "denied"})):
        assert not jsc.pipeline_cache_by_rule([bad]), bad
    assert not jsc.pipeline_cache_by_rule([stop, stop]) and not jsc.pipeline_cache_by_rule([])


def test_the_face_passes_the_directory_and_the_self_test_through():
    calls: list = []
    record = lambda name, result: lambda *args: (calls.append((name, args)), result)[1]  # noqa: E731
    module = SimpleNamespace(pipeline_cache_self_test=record("pipeline_cache_self_test", '{"accepted": true}'),
                             pipeline_cache_directory=record("pipeline_cache_directory", "D:/cache"))
    core = loader.NativeCore(module, {"abi": loader.EXPECTED_ABI})
    assert core.pipeline_cache_self_test(Path("D:/t")) == {"accepted": True}
    assert core.pipeline_cache_directory() == "D:/cache" and core.pipeline_cache_directory("") == "D:/cache"
    assert calls == [("pipeline_cache_self_test", (str(Path("D:/t")),)), ("pipeline_cache_directory", ()),
                     ("pipeline_cache_directory", ("",))]
    text = (CORE / "src" / "module.cpp").read_text(encoding="utf-8")
    for name in ("pipeline_cache_self_test", "pipeline_cache_directory"):
        assert f'{{ "{name}", {name}, ' in text, name
