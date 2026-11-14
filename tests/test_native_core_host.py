"""N2.2's host interface and frame driver (native/core: host_adapter, frame_driver, probe_pass, conventions,
vulkan_context; rendering/native/hosts.py; native/core/python/host_check.py), the parts that need no built module:

- the core's shaders bake for every shipped target with the production conventions include spliced in, and the copy
  the core bakes is the production text;
- the build lists every C++ source, and no core source uses the STL's DLL-backed types (msvcp140, refused at load);
- the probe's analysis tells the decided conventions from a mirrored image, a wrong cull and a missing clip-NDC flip,
  and its facts checks hold for Vulkan, OpenGL and D3D's QRhi facts and refuse an uncorrected matrix;
- the Python face refuses what the module would refuse and decodes what it returns, on a stand-in module.
The built module's own runs are tests/test_native_core_module.py (skipped where no build is in the checkout).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "native" / "core"
SHADERS = CORE / "shaders"
sys.path.insert(0, str(CORE / "python"))

import probe_analysis as pa  # noqa: E402
import host_check  # noqa: E402

CORE_TARGETS = ("--glsl", "430", "--hlsl", "50", "--msl", "12")   # CMakeLists.txt's bake


def _composed(name: str, *, splice: bool = True) -> str:
    """cmake/compose_shader.cmake's splice, in Python."""
    text = (SHADERS / name).read_text(encoding="utf-8")
    if splice:
        text = text.replace("//@srpss_conventions", (SHADERS / "srpss_conventions.glsl").read_text(encoding="utf-8"))
    return text


def _shader_sources() -> list[str]:
    return sorted(p.name for p in SHADERS.iterdir() if p.suffix in (".vert", ".frag", ".comp"))


# ------------------------------------------------------------------------------------------------- shaders and build


def test_the_core_bakes_the_production_include():
    from rendering.gl_programs.conventions import SRPSS_CONVENTIONS_GLSL

    assert (SHADERS / "srpss_conventions.glsl").read_text(encoding="utf-8") == SRPSS_CONVENTIONS_GLSL


def test_every_core_shader_bakes_for_every_target_with_the_include(tmp_path):
    from tools.vulkan_shader_readiness import _qsb, compile_source

    qsb = _qsb()
    if not qsb.exists():
        pytest.skip("this PySide6 has no qsb")
    assert _shader_sources(), "the core has shaders"
    for name in _shader_sources():
        source = _composed(name)
        assert "//@" not in source, name
        assert compile_source(qsb, source, tmp_path / name, CORE_TARGETS) == (True, ""), name
    # Negative control: the probe's fragment stage without the splice does not bake (fragUv, ndcToUv undefined).
    unspliced = _composed("probe.frag", splice=False)
    assert compile_source(qsb, unspliced, tmp_path / "probe.frag", CORE_TARGETS)[0] is False


def test_the_build_splices_the_include_before_the_bake():
    cmake = (CORE / "CMakeLists.txt").read_text(encoding="utf-8")
    compose = cmake.find("cmake/compose_shader.cmake")
    bake = cmake.find('COMMAND "${CORE_QSB}"')
    assert 0 <= compose < bake, "the include is spliced before qsb runs"
    assert '"${_composed}"' in cmake[bake:bake + 200], "qsb bakes the composed text"
    script = (CORE / "cmake" / "compose_shader.cmake").read_text(encoding="utf-8")
    assert 'string(REPLACE "//@srpss_conventions" "${_conventions}"' in script


def listed_sources(cmake: str) -> set[str]:
    block = re.search(r"set\(_sources\n(.*?)\)", cmake, re.S)
    assert block, "CMakeLists.txt lists no _sources"
    return {item for item in block.group(1).split() if item.startswith("src/")}


def test_the_build_compiles_every_cpp_source():
    cmake = (CORE / "CMakeLists.txt").read_text(encoding="utf-8")
    on_disk = {f"src/{p.name}" for p in (CORE / "src").glob("*.cpp")}
    assert listed_sources(cmake) == on_disk
    # Negative control: the same reading with one source left out of the list.
    dropped = cmake.replace("    src/probe_pass.cpp\n", "", 1)
    assert dropped != cmake and listed_sources(dropped) != on_disk


# The STL types whose code lives in msvcp140.dll: the process's copy is shiboken6's older one, and
# rendering/native/runtime_check.py refuses a module that imports it. Qt's containers, locks and threads instead.
_STL_DLL = re.compile(r"\bstd::(mutex|recursive_mutex|lock_guard|unique_lock|scoped_lock|condition_variable|thread|"
                      r"function|vector|map|unordered_map|set|unordered_set|string|wstring|deque|list|atomic|"
                      r"shared_mutex|promise|future|ostringstream|stringstream)\b|#include\s*<(mutex|thread|functional|"
                      r"vector|map|unordered_map|set|string|deque|list|atomic|condition_variable|sstream|iostream)>")


def stl_dll_uses(text: str) -> list[str]:
    code = re.sub(r"//[^\n]*", "", text)
    return sorted({m.group(0) for m in _STL_DLL.finditer(code)})


def test_no_core_source_uses_the_stls_dll_backed_types():
    offenders = {p.name: stl_dll_uses(p.read_text(encoding="utf-8"))
                 for p in sorted((CORE / "src").glob("*")) if p.suffix in (".cpp", ".h")}
    assert {name: uses for name, uses in offenders.items() if uses} == {}
    # Negative control: the reading finds one in code, and not in a comment.
    assert stl_dll_uses("std::mutex m;\n") == ["std::mutex"]
    assert stl_dll_uses("// not std::function\n") == []


# `QList<T> name(qsizetype(n));` declares a function, not a sized container (build round 1 of N2.2 failed on five).
_VEXING_PARSE = re.compile(r"^\s*(?!return\b)[\w:<>,* ]+?\s+(\w+)\(\s*[\w:]+\(\s*\w+\s*\)\s*\)\s*;", re.M)


def vexing_parses(text: str) -> list[str]:
    return [m.group(0).strip() for m in _VEXING_PARSE.finditer(re.sub(r"//[^\n]*", "", text))]


def test_no_core_source_declares_a_function_where_it_meant_a_sized_object():
    found = {p.name: vexing_parses(p.read_text(encoding="utf-8"))
             for p in sorted((CORE / "src").glob("*")) if p.suffix in (".cpp", ".h")}
    assert {name: hits for name, hits in found.items() if hits} == {}
    # Negative control: round 1's declaration is found; a return statement and an explicit size are not.
    assert vexing_parses("    QList<VkLayerProperties> props(qsizetype(n));\n")
    assert vexing_parses("    return QStringLiteral(\"x\").arg(int(r));\n    props.resize(qsizetype(n));\n") == []


# ------------------------------------------------------------------------------------------------- the probe's analysis

W, H = 160, 90
FRONT = [0.0625 * W, 0.1 * H, 0.0625 * W, 0.45 * H, 0.375 * W, 0.1 * H]
BACK = [0.625 * W, 0.1 * H, 0.9375 * W, 0.1 * H, 0.625 * W, 0.45 * H]
CLIP_CORR = {   # QRhi::clipSpaceCorrMatrix() per backend (row-major here)
    "vulkan": [[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, 0.5, 0.5], [0, 0, 0, 1]],
    "opengl": np.eye(4).tolist(),
    "d3d": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0.5, 0.5], [0, 0, 0, 1]],
}
Y_UP = {"vulkan": (False, False), "opengl": (True, True), "d3d": (True, False)}   # (ndc, framebuffer)


def _column_major(m: np.ndarray) -> list[float]:
    return [float(v) for v in np.asarray(m, dtype=np.float64).T.ravel()]


def _ortho() -> np.ndarray:
    """QMatrix4x4::ortho(0, W, H, 0, -1, 1): item pixels (y down) to OpenGL clip space."""
    return np.array([[2 / W, 0, 0, -1], [0, -2 / H, 0, 1], [0, 0, -1, 0], [0, 0, 0, 1]], dtype=np.float64)


def facts_for(backend: str, *, corrected: bool = True) -> dict:
    """The facts the module reports on a backend, from QRhi's numbers and the decided rules (F1 to F3)."""
    from rendering.gl_programs.conventions import front_face_clockwise

    ndc_up, fb_up = Y_UP[backend]
    correction = np.asarray(CLIP_CORR[backend], dtype=np.float64) @ np.diag([1, -1 if fb_up else 1, 1, 1])
    uploaded = (correction if corrected else np.eye(4)) @ _ortho()
    rule = "cw" if front_face_clockwise(_column_major(uploaded), ndc_y_up=ndc_up) else "ccw"
    return {"size": [W, H], "front_triangle": [FRONT[i:i + 2] for i in (0, 2, 4)],
            "back_triangle": [BACK[i:i + 2] for i in (0, 2, 4)], "front_colour": [0, 1, 1, 0],
            "back_colour": [1, 0, 0, 0], "is_y_up_in_ndc": ndc_up, "is_y_up_in_framebuffer": fb_up,
            "clip_space_corr": _column_major(CLIP_CORR[backend]), "target_correction": _column_major(correction),
            "gl_form": _column_major(_ortho()), "uploaded": _column_major(uploaded), "corrected": corrected,
            "double_correction_refused": True if corrected else None, "front_face": rule,
            "front_face_rule_on_uploaded": rule,
            "conventions_block": [0.0, 1.0 if (ndc_up and not fb_up) else 0.0, 0.0, 0.0]}


def _readback(facts: dict, image: np.ndarray) -> dict:
    return {"facts": facts, "rgba": np.ascontiguousarray(image, dtype=np.uint8).tobytes(), "width": W, "height": H}


@pytest.mark.parametrize("backend", sorted(Y_UP))
def test_the_decided_image_and_facts_pass_on_every_backend(backend):
    facts = facts_for(backend)
    result = pa.analyse(_readback(facts, pa.expected_image(facts)["image"]))
    assert result["pass"], {k: v for k, v in result["checks"].items() if not v}
    # The decision F3 restated: counter-clockwise on Vulkan and D3D, clockwise on the core's OpenGL.
    assert facts["front_face"] == ("cw" if backend == "opengl" else "ccw")


def test_a_mirrored_readback_fails():
    facts = facts_for("vulkan")
    image = pa.expected_image(facts)["image"][::-1]
    checks = pa.analyse(_readback(facts, image))["checks"]
    assert checks["background_frag_uv"] is False and checks["front_triangle_kept_where_authored"] is False


def test_the_wrong_triangle_culled_fails():
    facts = facts_for("opengl")
    exp = pa.expected_image(facts)
    image = exp["background"].copy()                   # the front triangle culled ...
    image[exp["back"]] = np.array([0, 255, 255, 0])    # ... and the back one drawn
    checks = pa.analyse(_readback(facts, image))["checks"]
    assert checks["front_triangle_kept_where_authored"] is False and checks["back_triangle_culled"] is False


def test_a_missing_clip_ndc_flip_fails_on_d3d():
    facts = facts_for("d3d")
    image = pa.expected_image(facts)["image"].copy()
    image[..., 3] = 255 - image[..., 3]                # ndcToUv's v mirrored: the block's y not read
    checks = pa.analyse(_readback(facts, image))["checks"]
    assert checks["ndc_to_uv_agrees_with_frag_uv"] is False and checks["background_frag_uv"] is True


def test_the_facts_checks_refuse_an_uncorrected_upload_and_a_wrong_block():
    facts = facts_for("vulkan", corrected=False)
    checks = pa.fact_checks(facts)
    assert checks["corrected_once"] is False and checks["uploaded_is_correction_times_gl_form"] is False
    block = dict(facts_for("d3d"), conventions_block=[0.0, 0.0, 0.0, 0.0])
    assert pa.fact_checks(block)["conventions_block_decided"] is False


def test_a_negative_control_must_fail_where_it_changes_the_rasterizers_input():
    good = facts_for("vulkan")
    image = pa.expected_image(good)["image"]
    # It changes the matrix and the image does not change: the control is broken (must fail).
    changed = facts_for("vulkan", corrected=False)
    assert pa.negative_verdict(good, _readback(changed, image))["ok"] is False
    # It changes the matrix and the image fails: as it must.
    assert pa.negative_verdict(good, _readback(changed, image[::-1]))["ok"] is True
    # It changes nothing the rasterizer gets (D3D's correction is depth only): vacuous, and it must pass.
    d3d = facts_for("d3d")
    vacuous = facts_for("d3d", corrected=False)
    d3d_image = pa.expected_image(d3d)["image"]
    verdict = pa.negative_verdict(d3d, _readback(vacuous, d3d_image))
    assert verdict["changes_anything"] is False and verdict["ok"] is True


def test_the_qt_alone_hidden_control_reports_whether_its_cycle_rendered():
    """``hidden_qt_alone_every_cycle_ok`` can fail (audit 13 Nov, low 2: the cycle returned True whatever happened)."""
    rendered = {"initialized": True, "texture_created": True, "target_created": True,
                "target_size": list(host_check.HOST_SIZE), "frames": host_check.QT_ALONE_FRAMES}
    assert host_check.qt_alone_cycle_ok(rendered) is True
    for broken in ({"initialized": False}, {"texture_created": False}, {"target_created": False},
                   {"target_size": [0, 0]}, {"frames": host_check.QT_ALONE_FRAMES - 1}, {"frames": 0}):
        assert host_check.qt_alone_cycle_ok(dict(rendered, **broken)) is False, broken
    assert host_check.qt_alone_cycle_ok({}) is False
    # The cycle (GPU, run by the lead's host_check) answers with that verdict, never a constant.
    import ast
    import inspect

    cycle = ast.parse(inspect.getsource(host_check._cycle_hidden_qt_alone).lstrip())
    returns = [node.value for node in ast.walk(cycle) if isinstance(node, ast.Return) and node.value is not None]
    assert [ast.unparse(value) for value in returns if not isinstance(value, ast.Name)] == [
        "qt_alone_cycle_ok(steps)"], [ast.unparse(value) for value in returns]


@pytest.mark.parametrize("backend", sorted(Y_UP))
def test_every_backend_has_a_front_face_control_that_bites(backend):
    """The fixed front face opposite to the backend's rule changes the rasterizer's input, so it must fail there:
    fixed-ccw on OpenGL, fixed-cw on Vulkan, D3D11 and D3D12 (audit 13 Nov, 2: D3D had none)."""
    facts = facts_for(backend)
    expected = pa.expected_image(facts)["image"]
    opposite = "ccw" if facts["front_face"] == "cw" else "cw"
    names = [name for name, config in host_check.NEGATIVES.items() if config == {"front_face": opposite}]
    assert names and set(names) <= set(host_check.FRONT_FACE_CONTROLS)
    flipped = dict(facts, front_face=opposite)
    # The control's run culls the authored front triangle: its image is not the decided one.
    culled = pa.negative_verdict(facts, _readback(flipped, expected[:, ::-1]))
    assert culled["changes_anything"] and culled["image_failed"] and culled["ok"]
    negatives = {name: culled for name in names}
    same = [name for name in host_check.FRONT_FACE_CONTROLS if name not in names]
    negatives.update({name: pa.negative_verdict(facts, _readback(dict(facts), expected)) for name in same})
    assert host_check.front_face_rule_has_a_biting_control(negatives)
    # Negative control: the controls before the fix (fixed-ccw only) bite nowhere the rule is counter-clockwise.
    before = {name: verdict for name, verdict in negatives.items() if name != "front_face_fixed_cw"}
    assert host_check.front_face_rule_has_a_biting_control(before) is (backend == "opengl")


# ------------------------------------------------------------------------------------------------- the Python face


def _stand_in(calls: list):
    def record(name, result=None):
        return lambda *args: (calls.append((name, args)), result)[1]

    return SimpleNamespace(
        host_attach=record("host_attach", 7), host_probe=record("host_probe"),
        host_probe_readback=record("host_probe_readback"), host_reattach=record("host_reattach"),
        host_detach=record("host_detach"), host_state=record("host_state", json.dumps({"attached": True})),
        host_close=record("host_close", json.dumps({"steps": ["x"]})), host_frames=record("host_frames"),
        host_set_content=record("host_set_content"),
        host_probe_result=record("host_probe_result", {"facts": json.dumps({"size": [2, 1]}), "rgba": b"\0" * 8,
                                                       "width": 2, "height": 1, "frame": 3}))


def test_the_python_face_passes_through_and_refuses_what_the_module_would():
    from rendering import native
    from rendering.native import loader

    calls: list = []
    core = loader.NativeCore(_stand_in(calls), {"abi": loader.EXPECTED_ABI})
    host = core.hidden_host(64, 32)
    assert isinstance(host, native.HiddenHost) and calls[-1] == ("host_attach", ("hidden", 0, 64, 32, True))
    host.set_probe(correction="none")
    assert calls[-1] == ("host_probe", (7, json.dumps({"correction": "none"})))
    with pytest.raises(ValueError, match="unknown probe option"):
        host.set_probe(colour="red")
    result = host.probe_result()
    assert result is not None and (result.width, result.height, result.frame) == (2, 1, 3)
    assert result.facts == {"size": [2, 1]}
    assert host.close() == {"steps": ["x"]} and host.close() == {"steps": ["x"]}
    assert [c for c in calls if c[0] == "host_close"] == [("host_close", (7,))]   # closed once
    with pytest.raises(RuntimeError, match="closed"):
        host.frames(1)
    with pytest.raises(ValueError, match="hidden host owns its window"):
        core.attach_host(object(), kind="hidden")
    with pytest.raises(TypeError, match="QQuickWindow"):
        core.attach_host(object())


# ------------------------------------------------------------------------------------------------- the harness verdict


def test_the_harness_fails_a_vulkan_run_without_the_layer_when_validation_is_required():
    record = {"rounds": ["hidden"], "hidden": {"pass": True, "checks": {"x": True}}, "live_hosts_at_end": 0,
              "module_loaded": True, "instance_created": True,
              "validation": {"layer_loaded": False}, "instance_teardown": {"ok": True}}
    assert host_check.api_verdict("vulkan", record, require_validation=True)[0] is False
    assert host_check.api_verdict("vulkan", record, require_validation=False)[0] is True
    clean = dict(record, validation={"layer_loaded": True, "clean": True})
    assert host_check.api_verdict("vulkan", clean, require_validation=True)[0] is True
    dirty = dict(record, validation={"layer_loaded": True, "clean": False, "unexplained_errors": 1})
    assert host_check.api_verdict("vulkan", dirty, require_validation=True)[0] is False
    left_open = dict(clean, live_hosts_at_end=1)
    assert host_check.api_verdict("vulkan", left_open, require_validation=True)[0] is False


def test_the_lifecycle_judges_the_core_against_qt_alone_on_the_same_api():
    def series(handles, users, trough, span):
        return {"handle_slope_per_cycle": handles, "user_object_slope_per_cycle": users,
                "private_trough_growth_mib": trough, "private_range_mib": span}

    # Round 2 (13 Nov), OpenGL: Qt's threaded render control keeps 2 handles and 1 USER object per cycle; ours the same.
    opengl_control = series(2.0, 1.0, 1.0, 8.0)
    assert all(v for k, v in host_check._against(series(2.0, 1.0, 0.5, 9.0), opengl_control).items()
               if k != "private_tolerance_mib")
    # Vulkan: the driver's 32/64 MiB blocks move private bytes by ~92 MiB in Qt alone; a 48 MiB trough step is noise.
    vulkan_control = series(3.0, 0.0, -20.0, 92.0)
    assert host_check._against(series(3.0, 0.0, 48.5, 180.0), vulkan_control)["private_bytes"] is True
    # Negative controls: a handle, a USER object or a trough growth beyond Qt alone's is ours and fails.
    assert host_check._against(series(3.0, 0.0, 0.0, 9.0), opengl_control)["handles"] is False
    assert host_check._against(series(2.0, 2.0, 0.0, 9.0), opengl_control)["user_objects"] is False
    assert host_check._against(series(3.0, 0.0, 150.0, 200.0), vulkan_control)["private_bytes"] is False
    quiet = series(0.0, 0.0, 0.0, 1.3)                                     # D3D11's Qt alone: 1.3 MiB of noise
    assert host_check._against(series(0.0, 0.0, 17.0, 20.0), quiet)["private_bytes"] is False   # the 16 MiB floor


def test_a_module_that_never_loaded_reports_that_alone():
    # Build round 1 (12 Nov): the module was not built, and the verdict also blamed validation and the teardown.
    unloaded = {"api": "vulkan", "rounds": ["hidden", "window"], "module_loaded": False, "instance_created": False,
                "error": "the module did not load: the native core is not built"}
    ok, reasons = host_check.api_verdict("vulkan", unloaded, require_validation=True)
    assert ok is False and reasons == ["vulkan: the module did not load: the native core is not built"]
    # A child that left no record at all says so, and nothing else.
    crashed = {"api": "opengl", "rounds": ["hidden"], "error": "the child process ended without a record (3)"}
    assert host_check.api_verdict("opengl", crashed, require_validation=True)[1] == [
        "opengl: the child process ended without a record (3)"]
    # A Vulkan instance that was not created: that reason alone, no validation or teardown verdict.
    no_instance = dict(unloaded, module_loaded=True, error="the Vulkan instance failed: vkCreateInstance: -9")
    assert host_check.api_verdict("vulkan", no_instance, require_validation=True)[1] == [
        "vulkan: the Vulkan instance failed: vkCreateInstance: -9"]


def test_the_validation_rule_excuses_only_qts_recorded_defects():
    import vk_validation as validation

    def entry(eid, caller, count=1, message=""):
        return {"phase": "hidden", "source": "our_instance", "severity": "error", "id": eid, "message": message,
                "count": count, "stack": ["VkLayer_khronos_validation.dll+0x10", f"{caller}+0x20"]}

    excused = {"errors": 5, "entries": [entry("VUID-VkImageCreateInfo-initialLayout-12478", "Qt6Gui.dll", 5)]}
    assert validation.validation_summary(excused)["clean"] is True
    # The same id from our own module, or a hazard C (never excused), is not clean; repeats are counted.
    ours = {"errors": 2, "entries": [entry("VUID-VkImageCreateInfo-initialLayout-12478", "_srpss_native_core.pyd", 2)]}
    assert validation.validation_summary(ours)["unexplained_errors"] == 2
    hazard = {"errors": 1, "entries": [entry("SYNC-HAZARD-READ-AFTER-WRITE", "Qt6Gui.dll", 1,
                                             "VK_ATTACHMENT_LOAD_OP_LOAD layout transition initiated by "
                                             "vkCmdPipelineBarrier")]}
    assert validation.validation_summary(hazard)["clean"] is False
    dropped = {"errors": 0, "entries": [], "entries_dropped": 1}
    assert validation.validation_summary(dropped)["clean"] is False


def test_the_n06_spike_reads_the_cores_validation_rule(monkeypatch):
    """One source for the ``QT_DEFECTS`` rule: the spike's ``run_n06.py`` reads the core's ``vk_validation`` at each
    call, so the edit that drops A's excuse at the next Qt patch drops it in both (its copy had to be edited twice)."""
    import vk_validation as validation

    spike = str(ROOT / "native" / "spike_p1" / "python")
    if spike not in sys.path:
        sys.path.append(spike)
    import run_n06

    def summary_of_a(module) -> dict:
        entry = {"phase": "hidden", "source": "our_instance", "severity": "error", "count": 3, "message": "",
                 "id": "VUID-VkImageCreateInfo-initialLayout-12478",
                 "stack": ["VkLayer_khronos_validation.dll+0x10", "Qt6Gui.dll+0x20"]}
        return module.validation_summary({"errors": 1, "entries": [entry]})

    assert run_n06.QT_DEFECTS is validation.QT_DEFECTS
    assert summary_of_a(run_n06)["clean"] is True and summary_of_a(validation)["clean"] is True
    # The upgrade's one edit: A is no longer excused. Both harnesses now count it.
    real = validation.excused
    monkeypatch.setattr(validation, "excused", lambda g: g.get("qt_defect") != "A" and real(g))
    assert summary_of_a(validation)["clean"] is False
    assert summary_of_a(run_n06)["clean"] is False


def test_the_loaders_warnings_are_skipped_and_its_errors_counted():
    """Audit 13 Nov, low 1: a "Loader Message" group was skipped at any severity, so a loader error was never
    unexplained. Its warnings stay out (not validation findings); its errors count, even beside a warning."""
    import vk_validation as validation

    def loader(severity, count=1):
        return {"phase": "hidden", "source": "our_instance", "severity": severity, "id": "Loader Message",
                "message": "loader", "count": count, "stack": ["vulkan-1.dll+0x10"]}

    warnings_only = {"errors": 0, "warnings": 3, "entries": [loader("warning", 3)]}
    summary = validation.validation_summary(warnings_only)
    assert summary["clean"] is True and summary["warnings_total"] == 0
    an_error = {"errors": 2, "warnings": 0, "entries": [loader("error", 2)]}
    assert validation.validation_summary(an_error)["unexplained_errors"] == 2
    # A warning first must not carry the error's group (and its count) out with it.
    both = {"errors": 1, "warnings": 1, "entries": [loader("warning"), loader("error")]}
    summary = validation.validation_summary(both)
    assert summary["unexplained_errors"] == 1 and summary["unexplained_warnings"] == 0 and summary["clean"] is False
