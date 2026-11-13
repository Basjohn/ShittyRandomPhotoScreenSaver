"""The native core's harness rule for validation messages (the N0.6 rule, `QT_DEFECTS`; Current_Plan.md item 8b).

The module's messenger (``native/core/src/vulkan_context.cpp``) keeps every Vulkan validation error and warning with its
phase, thread and the caller's stack. A message is clean only when it is none of these; Qt 6.12.0's own recorded
defects are excused by their id, text and Qt caller, each only where the harness cannot avoid it
(``Docs/Future_Work/Native_Core_N06_N07_Qt_Facts.md`` section I has the record and the owners). Carried over from the
N0.6 harness (``native/spike_p1/python/run_n06.py``, evidence only, never imported here); the excuse for A goes when the
project takes the Qt patch release that fixes it (the plan's N0.6 box).

Also the environment rule: no variable that changes what Qt or the Vulkan loader does may be set, except
``VK_ADD_LAYER_PATH`` when the lead passes ``--layer-path`` (the validation layer is installed outside the registry).
"""
from __future__ import annotations

import os
from pathlib import Path

VALIDATION_LAYER = "VK_LAYER_KHRONOS_validation"
# The one variable a harness may set, for its own process and its children, when the lead passes --layer-path.
LAYER_PATH_VARIABLE = "VK_ADD_LAYER_PATH"
CONTAMINATING_PREFIXES = ("QT_VULKAN", "QT_VK_", "QSG_", "QT_QUICK_BACKEND", "QT_RHI", "VK_")
RECORDED_PREFIXES = CONTAMINATING_PREFIXES + ("QT_QPA", "QT_OPENGL", "QT_D3D", "QT_QUICK", "VULKAN_SDK")

QT_DEFECTS = {
    "A": "VUID-VkImageCreateInfo-initialLayout-12478: QVkTexture::create (qtbase v6.12.0, src/gui/rhi/qrhivulkan.cpp) "
         "creates every texture image with initialLayout PREINITIALIZED and tiling OPTIMAL; the 6.12 branch head has "
         "UNDEFINED. Every QRhi texture on Vulkan; excused everywhere.",
    "B": "SYNC-HAZARD-WRITE-AFTER-WRITE at vkCmdBeginRenderPass: QRhiVulkan::createOffscreenRenderPass gives a texture "
         "target without PreserveColorContents initialLayout UNDEFINED and no VK_SUBPASS_EXTERNAL dependency. Excused "
         "only in phases named 'discard'; every core target preserves (native/core/src/targets.h).",
    "C": "SYNC-HAZARD-READ-AFTER-WRITE at vkCmdBeginRenderPass (loadOp LOAD): QRhiVulkan's tracker transitions a colour "
         "target with dstAccessMask COLOR_ATTACHMENT_WRITE only. Never excused: the core primes its targets "
         "(native/core/src/targets.cpp primeForLoad).",
    "D": "SYNC-HAZARD-WRITE-AFTER-PRESENT / WRITE-AFTER-READ / UNASSIGNED-non-acquired-swapchain-image-used: Qt Quick's "
         "grabWindow on a Vulkan window. Excused only in phases named 'grab'; the core never grabs a window.",
}

# Frames of the layer, the loader and the messenger callback sit on top of the caller's stack in a message entry.
_NOT_CALLER = ("VkLayer_", "vulkan-1.dll")


def use_layer_path(path: Path | None, allowed: set[str]) -> None:
    """--layer-path: VK_ADD_LAYER_PATH for this process and its children, before anything loads the Vulkan loader."""
    if path is None:
        return
    os.environ[LAYER_PATH_VARIABLE] = str(path)
    allowed.add(LAYER_PATH_VARIABLE)


def environment_record(allowed: set[str] | frozenset[str] = frozenset()) -> dict:
    found = {k: v for k, v in sorted(os.environ.items()) if k.upper().startswith(RECORDED_PREFIXES)}
    contaminating = sorted(k for k in found if k.upper().startswith(CONTAMINATING_PREFIXES) and k.upper() not in allowed)
    return {"recorded": found, "contaminating_set": contaminating,
            "allowed_set_by_argument": sorted(k for k in found if k.upper() in allowed), "clean": not contaminating}


def classify_group(g: dict) -> str | None:
    """Which recorded Qt 6.12.0 defect a message group is, by its id, text and Qt caller; None when it is none."""
    gid, msg, callers = g.get("id") or "", g.get("message") or "", g.get("caller_modules") or []
    qt_call = "Qt6Gui.dll" in callers[:2]
    if gid == "VUID-VkImageCreateInfo-initialLayout-12478" and callers[:1] == ["Qt6Gui.dll"]:
        return "A"
    if (gid == "SYNC-HAZARD-WRITE-AFTER-WRITE" and qt_call and "vkCmdBeginRenderPass" in msg
            and "oldLayout VK_IMAGE_LAYOUT_UNDEFINED" in msg and "attachment storeOp" in msg):
        return "B"
    if (gid == "SYNC-HAZARD-READ-AFTER-WRITE" and qt_call and "VK_ATTACHMENT_LOAD_OP_LOAD" in msg
            and "layout transition initiated by vkCmdPipelineBarrier" in msg):
        return "C"
    if (gid in ("SYNC-HAZARD-WRITE-AFTER-PRESENT", "SYNC-HAZARD-WRITE-AFTER-READ",
                "UNASSIGNED-non-acquired-swapchain-image-used") and qt_call and "Qt6Quick.dll" in callers[:3]):
        return "D"
    return None


def _excused(g: dict) -> bool:
    phase = g.get("phase") or ""
    return (g.get("qt_defect") == "A" or (g.get("qt_defect") == "B" and "discard" in phase)
            or (g.get("qt_defect") == "D" and "grab" in phase))


def message_groups(messages: dict) -> list[dict]:
    """Errors and warnings grouped by (id, phase, source, severity) with the caller chain below the layer and the
    loader."""
    groups: dict = {}
    for e in messages.get("entries", []):
        if e.get("qt_known_false_positive"):
            continue  # counted apart by the module (Qt's own debug filter hides the same two)
        stack = e.get("stack", [])
        last_layer = max((i for i, f in enumerate(stack) if f.startswith(_NOT_CALLER)), default=-1)
        chain: list = []
        for frame in stack[last_layer + 1:]:
            module = frame.split("+0x")[0]
            if not chain or chain[-1] != module:
                chain.append(module)
        # Severity is part of the key: a loader error must never ride in a loader warning's group.
        key = (e.get("id"), e.get("phase"), e.get("source"), e.get("severity"))
        g = groups.setdefault(key, {"id": e.get("id"), "phase": e.get("phase"), "source": e.get("source"),
                                    "severity": e.get("severity"), "count": 0, "threads": [], "caller_modules": chain,
                                    "caller_frames": stack[last_layer + 1:last_layer + 13],
                                    "objects": e.get("objects", []), "message": e.get("message", "")[:1500]})
        g["count"] += int(e.get("count", 1))   # the module keeps one entry per repeat, with its count
        if e.get("thread") not in g["threads"]:
            g["threads"].append(e.get("thread"))
    for g in groups.values():
        g["qt_defect"] = classify_group(g)
    return sorted(groups.values(), key=lambda g: (g["phase"] or "", g["id"] or ""))


def validation_warnings(messages: dict) -> int:
    """Warnings that are validation findings (the loader's own general messages are not)."""
    loader = sum(int(e.get("count", 1)) for e in messages.get("entries", []) if e.get("severity") == "warning"
                 and e.get("id") == "Loader Message")
    return messages.get("warnings", 0) - loader


def validation_summary(messages: dict) -> dict:
    """Errors and warnings split into the recorded Qt defects excused where they are and the rest, which must be none;
    errors beyond the module's entry cap count as unexplained."""
    groups = message_groups(messages)
    recorded: dict = {}
    unexplained_errors = unexplained_warnings = 0
    for g in groups:
        if g.get("id") == "Loader Message" and g.get("severity") != "error":
            continue  # the loader's general warnings are not validation findings; a loader error is counted
        g["excused"] = _excused(g)
        if g["excused"]:
            recorded[g["qt_defect"]] = recorded.get(g["qt_defect"], 0) + g["count"]
        elif g.get("severity") == "error":
            unexplained_errors += g["count"]
        else:
            unexplained_warnings += g["count"]
    in_entries = sum(g["count"] for g in groups if g.get("severity") == "error")
    unexplained_errors += max(0, messages.get("errors", 0) - in_entries)
    # Distinct messages beyond the module's entry cap were never seen: never clean.
    unexplained_warnings += int(messages.get("entries_dropped", 0))
    return {"errors_total": messages.get("errors", 0), "warnings_total": validation_warnings(messages),
            "recorded_qt_defects_excused": recorded, "unexplained_errors": unexplained_errors,
            "unexplained_warnings": unexplained_warnings,
            "clean": unexplained_errors == 0 and unexplained_warnings == 0, "groups": groups}
