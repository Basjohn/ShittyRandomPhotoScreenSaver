"""N3.6's release-timing box (Current_Plan.md item 8b, "N3.6 Lifetime"; research N3 section 12): retirement calls
deleteLater at once (``native/core/src/rhi_owned.h``), QRhi::finish() only at an edge no frame follows and never inside a
frame (``frame_driver.cpp``), raw Vulkan objects to the device's deferred queue (``vulkan_context.cpp``,
``gpu_timer.cpp``). The parts that need no built module: the sources read for each rule (each reading with its negative
control in the test), the harness's judge against readings with one fact changed, and the Python face. The built
module's run is ``native/core/python/device_loss_check.py --rounds release``.
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

#: A QRhiResource held by a plain unique_ptr (deleted at once, inside a frame too): QRhi itself is no resource.
_PLAIN_RESOURCE = re.compile(r"std::unique_ptr<(QRhi[A-Z]\w*)>")


def _code(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", re.sub(r"//[^\n]*", "", text), flags=re.S)


def plain_resources(text: str) -> list[str]:
    return _PLAIN_RESOURCE.findall(_code(text))


def owner_problems(owned: str) -> list[str]:
    """``RhiOwned`` (checkpoint audit 11 L1: a class that counts its wrappers per QRhi) retires through one ``retire()``
    that calls ``deleteLater`` and never ``delete``, from its destructor, its move assignment, its nullptr assignment and
    its ``reset``; ``release()`` hands the resource over uncounted and never retires it."""
    code = _code(owned)
    problems = []
    retire = _body(code, "void retire() noexcept")
    if "resource->deleteLater();" not in retire or "rhiOwnedRetired(" not in retire:
        problems.append("retire() does not deleteLater and uncount")
    if re.search(r"\bdelete\s+\w", code):
        problems.append("a plain delete")
    for signature in ("~RhiOwned()", "RhiOwned &operator=(RhiOwned &&other) noexcept",
                      "RhiOwned &operator=(std::nullptr_t) noexcept", "void reset(Resource *resource = nullptr)"):
        if "retire();" not in _body(code, signature):
            problems.append(f"{signature} does not retire")
    release = _body(code, "Resource *release() noexcept")
    if "retire();" in release or "deleteLater" in release:
        problems.append("release() retires what it hands over")
    return problems


def test_every_qrhi_resource_of_the_core_is_retired_by_delete_later():
    found = {path.name: plain_resources(path.read_text(encoding="utf-8"))
             for path in sorted((CORE / "src").glob("*.cpp")) + sorted((CORE / "src").glob("*.h"))}
    assert not {name: hits for name, hits in found.items() if hits}, found
    owned = (CORE / "src" / "rhi_owned.h").read_text(encoding="utf-8")
    assert owner_problems(owned) == []
    # Negative controls: a plain owner is caught; QRhi itself (no resource) is not; a retire that deletes, and a
    # destructor that forgets its resource, are caught.
    assert plain_resources("std::unique_ptr<QRhiBuffer> m_arena;") == ["QRhiBuffer"]
    assert plain_resources("std::unique_ptr<QRhi> m_rhi;") == []
    deletes = owned.replace("resource->deleteLater();", "delete resource;", 1)
    assert deletes != owned and owner_problems(deletes)
    leaks = owned.replace("~RhiOwned() { retire(); }", "~RhiOwned() {}", 1)
    assert leaks != owned and owner_problems(leaks)


def _body(source: str, signature: str) -> str:
    start = source.index(signature)
    open_brace = source.index("{", start)
    depth = 0
    for index in range(open_brace, len(source)):
        depth += {"{": 1, "}": -1}.get(source[index], 0)
        if depth == 0:
            return source[open_brace:index + 1]
    raise ValueError(f"{signature} has no closing brace")


def finish_problems(body: str) -> list[str]:
    """The invalidation's finish: outside any frame and never on a lost device, after the core's own release."""
    guard = re.search(r"if \(rhi && !rhi->isRecordingFrame\(\) && !rhi->isDeviceLost\(\)\) \{(.*?)\}", body, re.S)
    if guard is None or "rhi->finish();" not in guard.group(1):
        return ["no guarded finish"]
    if body.count("->finish()") != 1:
        return ["a finish outside the guard"]
    if body.find("releaseOutsideFrame(") > body.find("rhi->finish();"):
        return ["the finish before the core's release"]
    return []


def test_a_finish_only_where_no_frame_follows_and_never_inside_one():
    source = (CORE / "src" / "frame_driver.cpp").read_text(encoding="utf-8")
    body = _body(source, "void FrameDriver::onSceneGraphInvalidated()")
    assert finish_problems(body) == []
    unguarded = body.replace("!rhi->isRecordingFrame() && ", "", 1)
    assert unguarded != body and finish_problems(unguarded)
    # The frame edge itself (inside the frame) never finishes, and never waits for a queue.
    edge = _body(source, "void FrameDriver::onBeforeRendering()")
    assert "finish()" not in edge and "WaitIdle" not in edge


def timer_release_problems(timer: str, driver: str) -> list[str]:
    problems = []
    body = _body(timer, "void GpuTimer::release(QRhi *rhi, bool outsideFrame, qint64 windowEdge)")
    inside = re.search(r"else if \(!outsideFrame && .*?\) \{(.*?)\n                \}", body, re.S)
    if inside is None:
        return ["no in-frame branch"]
    branch = inside.group(1)
    wait, defer = branch.find("vkQueueWaitIdle"), branch.find("deferRawVulkanDestroy(")
    if defer < 0 or not re.search(r"if \(windowEdge >= 0\) \{", branch) or (wait >= 0 and wait < defer):
        problems.append("the in-frame release waits instead of deferring")
    if re.search(r"m_timer->release\(rhi, (?:false|outsideFrame)\)", driver):
        problems.append("a frame driver release without the window's edge")
    return problems


def test_the_timers_pool_goes_to_the_deferred_queue_inside_a_frame():
    timer = (CORE / "src" / "gpu_timer.cpp").read_text(encoding="utf-8")
    driver = (CORE / "src" / "frame_driver.cpp").read_text(encoding="utf-8")
    assert timer_release_problems(timer, driver) == []
    # Negative controls: the ABI 29 wait, and a release call that drops the edge.
    waits = timer.replace("deferRawVulkanDestroy(object, windowEdge);", "m_vk->df->vkQueueWaitIdle(m_vk->queue);", 1)
    assert waits != timer and timer_release_problems(waits, driver)
    edgeless = driver.replace("m_timer->release(rhi, false, windowEdge());", "m_timer->release(rhi, false);", 1)
    assert edgeless != driver and timer_release_problems(timer, edgeless)


def test_a_device_destroys_its_deferred_objects_once_idle_and_before_it_goes():
    source = (CORE / "src" / "vulkan_context.cpp").read_text(encoding="utf-8")
    body = _body(source, "QStringList VulkanDevice::destroy()")
    idle, release, gone = (body.find("waitIdle(device)"), body.find("releaseAllRawVulkan(m_device)"),
                           body.find("destroyDevice(device, nullptr)"))
    assert 0 <= idle < release < gone
    edge = _body(source, "int releaseRawVulkan(quint64 device, qint64 edge, int framesInFlight)")
    assert "edge >= entry.retiredAtEdge + qint64(framesInFlight)" in edge


def _release_steps():
    return {
        "detached": {"released": True, "release_reason": "detached: released at the frame edge",
                     "gpu_timer_last": {"release_waits": 0, "deferred_releases": 1}},
        "deferred": {"raw_vulkan_deferred": 1, "raw_vulkan_released_at_edges": 0, "raw_vulkan_released_at_idle": 0,
                     "pending": 1},
        "edges": {"raw_vulkan_deferred": 0, "raw_vulkan_released_at_edges": 1, "raw_vulkan_released_at_idle": 0,
                  "pending": 0, "driver_raw_vulkan_released": 1},
        "closed": {"raw_vulkan_deferred": 0, "raw_vulkan_released_at_edges": 0, "raw_vulkan_released_at_idle": 1,
                   "pending": 0},
        "invalidated": {"no_frame_finishes": 1},
    }


RELEASE_CONTROLS = [
    ("detached", "gpu_timer_last", {"release_waits": 1, "deferred_releases": 0}, "no_wait_inside_the_frame"),
    ("detached", "release_reason", "detached", "released_inside_the_next_frame"),   # released outside a frame
    ("deferred", "pending", 0, "pool_deferred_not_destroyed"),                       # destroyed at once
    ("edges", "pending", 1, "pool_destroyed_at_a_later_edge"),                       # never drained
    ("edges", "raw_vulkan_released_at_edges", 0, "pool_destroyed_at_a_later_edge"),
    ("closed", "raw_vulkan_released_at_idle", 0, "pool_left_goes_at_the_close"),     # leaked past the device
    ("invalidated", "no_frame_finishes", 0, "finish_where_no_frame_follows"),
]


@pytest.mark.parametrize("vulkan", [True, False])
def test_the_release_round_passes_and_each_changed_reading_fails_its_check(vulkan):
    steps = _release_steps()
    checks = dlc.judge_release(steps, vulkan=vulkan)
    assert checks and all(checks.values()), checks
    for step, key, value, check in RELEASE_CONTROLS:
        if check not in checks:
            continue
        bad = copy.deepcopy(steps)
        bad[step][key] = value
        assert dlc.judge_release(bad, vulkan=vulkan)[check] is False, (step, key, check)


def test_only_vulkans_release_is_judged_for_a_wait_inside_the_frame():
    """Checkpoint audit 11 L4: OpenGL never waits for a queue, so its release_waits is a fact, never a check."""
    steps = _release_steps()
    assert "no_wait_inside_the_frame" in dlc.judge_release(steps, vulkan=True)
    assert "no_wait_inside_the_frame" not in dlc.judge_release(steps, vulkan=False)


def test_the_face_passes_the_in_frame_detach_and_the_raw_counts():
    from rendering.native import loader

    calls: list = []
    record = lambda name, result=None: lambda *args: (calls.append((name, args)), result)[1]  # noqa: E731
    module = SimpleNamespace(host_attach=record("host_attach", 4), host_detach=record("host_detach"),
                             raw_vulkan_counts=record("raw_vulkan_counts", '{"raw_vulkan_pending": 0}'))
    core = loader.NativeCore(module, {"abi": loader.EXPECTED_ABI})
    host = core.hidden_host(8, 8)
    host.detach()
    host.detach(at_frame_edge=True)
    assert calls[-2:] == [("host_detach", (4,)), ("host_detach", (4, True))]
    assert core.raw_vulkan_counts() == {"raw_vulkan_pending": 0}
    text = (CORE / "src" / "module.cpp").read_text(encoding="utf-8")
    assert '{ "raw_vulkan_counts", raw_vulkan_counts, ' in text
