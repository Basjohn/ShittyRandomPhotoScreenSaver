"""ABI 41 (N5.2f with N4.c), GPU-free on the core's sources: QRhi's DrawIndirect / DrawIndirectMulti answers reach the
device facts, the indirect admission and the draw-parameters forms through one helper, and the harness control that
hides them is wired end to end. Each check has a planted-defect control that must fail it."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "native" / "core" / "src"


def _source(name: str) -> str:
    return (CORE / name).read_text(encoding="utf-8")


def _function(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin:text.index(end, begin)]


def facts_report_the_answers(compute_cpp: str) -> bool:
    facts = _function(compute_cpp, "QJsonObject computeDeviceFacts(", "\n}\n")
    return ('QStringLiteral("draw_indirect"), drawIndirectAvailable(rhi)' in facts
            and 'QStringLiteral("draw_indirect_multi"), drawIndirectMultiAvailable(rhi)' in facts)


def one_answer_everywhere(mesh_cpp: str, mode_cpp: str) -> bool:
    """The helpers read the control; the admission and the draw-parameters forms read the helpers, never QRhi alone."""
    available = _function(mesh_cpp, "bool drawIndirectAvailable(", "\n}\n")
    multi = _function(mesh_cpp, "bool drawIndirectMultiAvailable(", "\n}\n")
    parameters = _function(mesh_cpp, "bool drawParametersAvailable(", "\n}\n")
    limits = _function(mode_cpp, "D15 point 3's and 6's device limits", "ABI 33 (N5.4): a linear sampler")
    admission = _function(limits, "if (!pass.indirect.isEmpty() &&", "return false;")
    return ("!hideDrawIndirect()" in available and "QRhi::DrawIndirect)" in available
            and "drawIndirectAvailable(rhi)" in multi and "QRhi::DrawIndirectMulti" in multi
            and "drawIndirectMultiAvailable(rhi)" in parameters and "QRhi::DrawIndirect)" not in parameters
            and "drawIndirectAvailable(rhi)" in admission and "isFeatureSupported" not in admission)


def control_is_wired(module_cpp: str, mesh_cpp: str) -> bool:
    control = _function(module_cpp, "PyObject *mesh_buffer_control(", "\n}\n")
    keys = control[:control.index("for (auto it")]
    return ('QStringLiteral("hide_draw_indirect")' in keys
            and 'srpss_core::setHideDrawIndirect(o.value(QStringLiteral("hide_draw_indirect")).toBool())' in control
            and "g_hideDrawIndirect.storeRelaxed(hide ? 1 : 0)" in mesh_cpp
            and "g_hideDrawIndirect.loadRelaxed() != 0" in mesh_cpp)


def test_the_device_facts_report_draw_indirect_and_multi():
    assert facts_report_the_answers(_source("compute_passes.cpp"))
    # Control: the facts read straight from QRhi (blind to the harness control) are caught.
    assert not facts_report_the_answers(_source("compute_passes.cpp").replace(
        "drawIndirectAvailable(rhi));", "rhi->isFeatureSupported(QRhi::DrawIndirect));"))


def test_admission_facts_and_draw_parameters_take_one_answer():
    assert one_answer_everywhere(_source("mesh_buffers.cpp"), _source("mode_content.cpp"))
    # Control: the admission reading QRhi directly (the hide control would no longer refuse it) is caught.
    assert not one_answer_everywhere(_source("mesh_buffers.cpp"), _source("mode_content.cpp").replace(
        "!drawIndirectAvailable(rhi)", "!rhi->isFeatureSupported(QRhi::DrawIndirect)"))
    # Control: the helper ignoring the control is caught.
    assert not one_answer_everywhere(_source("mesh_buffers.cpp").replace(
        "rhi && !hideDrawIndirect() &&", "rhi &&"), _source("mode_content.cpp"))


def test_the_hide_draw_indirect_control_is_wired():
    assert control_is_wired(_source("module.cpp"), _source("mesh_buffers.cpp"))
    # Control: the key accepted but never applied is caught.
    assert not control_is_wired(_source("module.cpp").replace(
        "srpss_core::setHideDrawIndirect(", "(void)("), _source("mesh_buffers.cpp"))


def test_the_abi_is_41_or_later_on_both_sides():
    from rendering.native import loader

    abi = _source("abi.h")
    defined = int(re.search(r"#define SRPSS_NATIVE_CORE_ABI (\d+)", abi).group(1))
    assert defined >= 41 and loader.EXPECTED_ABI == defined
    assert "// 41 (N5.2f with N4.c):" in abi
