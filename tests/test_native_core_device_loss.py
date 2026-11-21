"""N3.6's device-loss rebuild (Current_Plan.md item 8b, "N3.6 Lifetime"; native/core/src/host_adapter.cpp,
vulkan_context.cpp; rendering/native/hosts.py; native/core/python/device_loss_check.py), the parts that need no built
module: the harness's judges against records with one fact changed, the order of the hidden host's lost path and the
window record's guards read from the source (each reading with its negative control in the test), and the Python face.
The built module's run is device_loss_check.py itself.
"""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "native" / "core"
sys.path.insert(0, str(CORE / "python"))

import device_loss_check as dlc  # noqa: E402

OLD, NEW = "1111", "2222"
TEARDOWN = ['job service stopped: {"thread_started": true}', "vkDeviceWaitIdle: VK_SUCCESS", "vkDestroyDevice",
            "resetDeviceFunctions"]


def _vulkan_swap():
    loss = {"reason": "forced", "qrhi_recreated": True, "invalidated_on_render_thread": True,
            "invalidated_on_gui_thread": False, "old_device": OLD, "new_device": NEW, "device_swapped": True,
            "qrhi_device_before": OLD, "qrhi_device": NEW, "rebuilt_on_new_device": True,
            "lost_device_teardown": list(TEARDOWN)}
    state = {"lost_device_alive": False, "vulkan_live_devices": 1, "device_alive": True, "device": {"vk_device": NEW}}
    return loss, state


def _vulkan_control():
    loss = {"reason": "forced", "qrhi_recreated": True, "invalidated_on_render_thread": True,
            "invalidated_on_gui_thread": False, "device_swapped": False, "qrhi_device_before": OLD,
            "qrhi_device": OLD, "rebuilt_on_new_device": False}
    state = {"lost_device_alive": False, "vulkan_live_devices": 1, "device_alive": True, "device": {"vk_device": OLD}}
    return loss, state


def _opengl():
    loss = {"reason": "forced", "qrhi_recreated": True, "invalidated_on_render_thread": True,
            "invalidated_on_gui_thread": False, "qrhi_device_before": "0", "qrhi_device": "0"}
    return loss, {"lost_device_alive": False, "device_alive": False}


CASES = {"vulkan_swap": (_vulkan_swap, True, True), "vulkan_control": (_vulkan_control, True, False),
         "opengl": (_opengl, False, True)}

#: One fact changed per control, and the check that must fail for it.
CONTROLS = {
    "vulkan_swap": [
        ("loss", "qrhi_device", OLD, "qrhi_rebuilt_on_new_device"),        # Qt re-adopted the lost device
        ("loss", "rebuilt_on_new_device", False, "qrhi_rebuilt_on_new_device"),
        ("loss", "new_device", OLD, "device_swapped"),
        ("loss", "device_swapped", False, "device_swapped"),
        ("loss", "invalidated_on_render_thread", False, "invalidated_on_render_thread"),
        ("loss", "invalidated_on_gui_thread", True, "invalidated_on_render_thread"),
        ("loss", "lost_device_teardown", TEARDOWN[:2], "lost_device_destroyed"),
        ("loss", "reason", "lost", "forced"),
        ("loss", "error", "no new device", "qrhi_recreated"),
        ("loss", "qrhi_device_before", NEW, "qrhi_before_on_old_device"),
        ("state", "vulkan_live_devices", 2, "one_device_live"),             # the lost device leaked
        ("state", "lost_device_alive", True, "no_lost_device_left"),
        ("state", "device", {"vk_device": OLD}, "host_reports_new_device"),
    ],
    "vulkan_control": [
        ("loss", "qrhi_device", NEW, "qrhi_rebuilt_on_same_device"),
        ("loss", "device_swapped", True, "device_kept"),
        ("loss", "lost_device_teardown", TEARDOWN, "device_kept"),
        ("state", "vulkan_live_devices", 0, "one_device_live"),
    ],
    "opengl": [
        ("loss", "device_swapped", True, "no_device_of_ours"),
        ("state", "device_alive", True, "no_device_of_ours"),
        ("loss", "qrhi_recreated", False, "qrhi_recreated"),
    ],
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_a_rebuilt_loss_passes_and_each_changed_fact_fails_its_check(case):
    make, vulkan, swap = CASES[case]
    loss, state = make()
    checks = dlc.judge_loss(loss, state, vulkan=vulkan, swap=swap)
    assert checks and all(checks.values()), checks
    for where, key, value, check in CONTROLS[case]:
        bad_loss, bad_state = copy.deepcopy(loss), copy.deepcopy(state)
        (bad_loss if where == "loss" else bad_state)[key] = value
        bad = dlc.judge_loss(bad_loss, bad_state, vulkan=vulkan, swap=swap)
        assert bad[check] is False, (where, key, value, check)


def test_the_resend_must_go_through_the_rebuilt_devices_one_job_service():
    good = {"services": [{"label": f"device {NEW}", "published": 2.0, "backend": {"uploads": 2.0}}]}
    assert dlc.resent_through_jobs(good, NEW, 2)
    assert not dlc.resent_through_jobs(good, OLD, 2)                              # the old device's service
    assert not dlc.resent_through_jobs(good, NEW, 3)                              # an image not uploaded
    two = {"services": good["services"] + [{"label": f"device {OLD}", "published": 0.0, "backend": {}}]}
    assert not dlc.resent_through_jobs(two, NEW, 2)                               # the lost device's left running
    assert not dlc.resent_through_jobs({"services": []}, NEW, 2)
    assert not dlc.resent_through_jobs(good, None, 2)


def test_a_lost_devices_teardown_stops_its_job_service_before_the_device():
    assert dlc.teardown_ok(TEARDOWN) and dlc.teardown_ok(TEARDOWN[1:])
    assert not dlc.teardown_ok(TEARDOWN[1:] + TEARDOWN[:1])        # the job service stopped after the device went
    assert not dlc.teardown_ok(TEARDOWN[:-1])
    assert not dlc.teardown_ok([TEARDOWN[0], "vkDestroyDevice", "resetDeviceFunctions"])
    assert not dlc.teardown_ok([])


def mix_owners(spec) -> set[str]:
    """The owners the M3 program crosses a loss with (checkpoint audit 11 M3), read from its declaration."""
    from rendering.native.mode import BloomStep, CompositeStep, ComputePass, ModePass

    found = set()
    if spec.images or spec.buffers:
        if any(isinstance(p, ComputePass) for p in spec.passes):
            found.add("storage_and_compute")
    if any(getattr(t, "depth", False) for t in spec.targets):
        found.add("scene_target_with_depth")
    if spec.meshes and any(isinstance(p, ModePass) and p.geometry is not None and p.geometry.mesh for p in spec.passes):
        found.add("mesh")
    if any(isinstance(p, BloomStep) for p in spec.passes):
        found.add("bloom")
    if any(isinstance(p, CompositeStep) for p in spec.passes):
        found.add("composite")
    return found


MIX_OWNERS = {"storage_and_compute", "scene_target_with_depth", "mesh", "bloom", "composite"}


def test_the_m3_program_holds_every_owner_the_crossfade_round_never_crossed_a_loss_with():
    from dataclasses import replace

    from rendering.native.mode import BloomStep

    packs = {name: b"pack" for name in ("field.comp", "sample.frag", "box.vert", "box.frag")}
    spec = dlc.mix_spec(packs, "vulkan")
    assert mix_owners(spec) == MIX_OWNERS
    assert set(dlc.SCENES) == {"program", "spectrum", "background"}
    # Negative controls: the program without its bloom step, and without its mesh.
    no_bloom = replace(spec, passes=tuple(p for p in spec.passes if not isinstance(p, BloomStep)))
    assert mix_owners(no_bloom) == MIX_OWNERS - {"bloom"}
    assert mix_owners(replace(spec, meshes=())) == MIX_OWNERS - {"mesh"}


# ------------------------------------------------------------------------------------------- the source's order


def _body(source: str, signature: str) -> str:
    start = source.index(signature)
    open_brace = source.index("{", start)
    depth = 0
    for index in range(open_brace, len(source)):
        depth += {"{": 1, "}": -1}.get(source[index], 0)
        if depth == 0:
            return source[open_brace:index + 1]
    raise ValueError(f"{signature} has no closing brace")


#: The hidden host's lost path, in Qt's threaded loop's order: Qt Quick's target and scene graph go while the old QRhi
#: lives (the invalidation's slot gives the new device), then Qt's QRhi, then the lost device, then Qt's QRhi again.
RECOVER_ORDER = ("target.reset();", "control->invalidate();", "resetRhi(", "lostDevice->destroy()",
                 "control->initialize()", "createColorTarget(")


def recover_order_problems(body: str) -> list[str]:
    positions = [body.find(step) for step in RECOVER_ORDER]
    missing = [step for step, at in zip(RECOVER_ORDER, positions) if at < 0]
    if missing:
        return [f"missing {', '.join(missing)}"]
    return [f"{a} after {b}" for (a, pa), (b, pb) in zip(zip(RECOVER_ORDER, positions),
                                                         zip(RECOVER_ORDER[1:], positions[1:])) if pa > pb]


def test_the_hidden_hosts_lost_path_destroys_the_device_only_after_qts_qrhi_on_it():
    source = (CORE / "src" / "host_adapter.cpp").read_text(encoding="utf-8")
    body = _body(source, "bool recover(const QString &reason, QString *error)")
    assert recover_order_problems(body) == []
    # Negative control: the lost device destroyed while Qt's QRhi still runs on it.
    early = body.replace("control->invalidate();", "lostDevice->destroy(); control->invalidate();", 1)
    early = early.replace("if (lostDevice) {\n            loss.insert(QStringLiteral(\"lost_device_teardown\"), "
                          "stringsJson(lostDevice->destroy()));", "if (lostDevice) {", 1)
    assert early != body and recover_order_problems(early)


def window_slot_problems(source: str) -> list[str]:
    """The window record's slots: the replacement only for a QRhi that reports its device lost, direct (the render
    thread, before Qt's next QRhi), and the lost device destroyed at the next initialisation, never in the invalidation."""
    problems = []
    invalidated = re.search(r"connect\(window, &QQuickWindow::sceneGraphInvalidated, window, \[weak, window\]\(\) \{"
                            r"(.*?)\}, Qt::DirectConnection\);", source, re.S)
    initialized = re.search(r"connect\(window, &QQuickWindow::sceneGraphInitialized, window, \[weak, window\]\(\) \{"
                            r"(.*?)\}, Qt::DirectConnection\);", source, re.S)
    if not invalidated or not initialized:
        return ["the window record's direct slots are missing"]
    if not re.search(r"if \(!r \|\| !rhi \|\| !rhi->isDeviceLost\(\)\)\s*return;", invalidated.group(1)):
        problems.append("an ordinary invalidation would replace the device")
    if "replaceDevice(" not in invalidated.group(1):
        problems.append("the invalidation gives no new device")
    if "->destroy()" in invalidated.group(1):
        problems.append("the invalidation destroys a device under Qt's live QRhi")
    if "lostDevice->destroy()" not in initialized.group(1):
        problems.append("the lost device is never destroyed")
    return problems


def test_the_window_record_replaces_only_a_lost_device_and_destroys_it_after_qts_rebuild():
    source = (CORE / "src" / "host_adapter.cpp").read_text(encoding="utf-8")
    assert window_slot_problems(source) == []
    unguarded = source.replace("if (!r || !rhi || !rhi->isDeviceLost())", "if (!r || !rhi)", 1)
    assert unguarded != source and window_slot_problems(unguarded)
    early = source.replace("            QMutexLocker lock(&r->mutex);\n            if (rhi->backend() == QRhi::Vulkan",
                           "            QMutexLocker lock(&r->mutex);\n            r->device->destroy();\n"
                           "            if (rhi->backend() == QRhi::Vulkan", 1)
    assert early != source and window_slot_problems(early)


# ------------------------------------------------------------------------------------------------- the Python face


def test_the_face_sends_the_forced_loss_to_the_module():
    from rendering.native import loader

    calls: list = []
    record = lambda name, result=None: lambda *args: (calls.append((name, args)), result)[1]  # noqa: E731
    module = SimpleNamespace(host_attach=record("host_attach", 5),
                             host_force_device_lost=record("host_force_device_lost"))
    host = loader.NativeCore(module, {"abi": loader.EXPECTED_ABI}).hidden_host(16, 16)
    host.force_device_loss()
    host.force_device_loss(swap_device=False)
    assert calls[-2:] == [("host_force_device_lost", (5, True)), ("host_force_device_lost", (5, False))]
    # Negative control: a module without the entry (an ABI 29 build) cannot take the call.
    old = loader.NativeCore(SimpleNamespace(host_attach=record("host_attach", 6)),
                            {"abi": loader.EXPECTED_ABI}).hidden_host(16, 16)
    with pytest.raises(AttributeError):
        old.force_device_loss()
    text = (CORE / "src" / "module.cpp").read_text(encoding="utf-8")
    assert '{ "host_force_device_lost", host_force_device_lost, ' in text
