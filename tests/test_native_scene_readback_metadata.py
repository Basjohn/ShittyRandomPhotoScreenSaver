"""GPU-free falsifiers for the native readback metadata/capacity proof."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native/core/python"))
import scene_target_check as check


def readbacks(names, allocation, content):
    """Independent normalized-UV oracle; bytes carry no non-base pixel-validity claim."""
    import math

    entries = []
    for name in names:
        for level in range(max(allocation).bit_length()):
            size = tuple(max(1, dimension // (2 ** level)) for dimension in allocation)
            projected = tuple(min(size[axis], math.ceil(content[axis] * size[axis] / allocation[axis]))
                              for axis in range(2))
            entries.append(dict(name=name + (f"@{level}" if level else ""), level=level, size=size,
                                content=projected, format="rgba8", samples=1, data=bytes(size[0] * size[1] * 4)))
    return entries


@pytest.mark.parametrize("allocation,content", (((128, 64), (83, 47)), ((384, 320), (321, 257)),
                                               ((11, 7), (5, 3))))
def test_normalized_projection_includes_odd_actual_mip_extents(allocation, content):
    names = ("probe.colour",)
    entries = readbacks(names, allocation, content)
    result = check.readback_metadata_contract(entries, names, allocation, content)
    assert result["pass"]
    assert result["facts"]["expected_entries"] == len(entries)


@pytest.mark.parametrize("breakage", ("dropped", "duplicate", "base_content", "odd_policy", "shift_ceil",
                                    "shape", "level"))
def test_metadata_predicate_rejects_missing_wrong_or_malformed_entries(breakage):
    names, allocation, content = ("probe.colour",), (192, 128), (129, 73)
    entries = readbacks(names, allocation, content)
    if breakage == "dropped":
        entries.pop()
    elif breakage == "duplicate":
        entries.append(deepcopy(entries[-1]))
    elif breakage == "base_content":
        entries[1]["content"] = content
    elif breakage == "odd_policy":
        entries[1]["content"] = tuple(max(1, dimension >> 1) for dimension in content)
    elif breakage == "shift_ceil":
        # The clamped 1x1 level projects into the actual allocation, rather than ceil(content / 2**level).
        entry = entries[-1]
        entry["content"] = tuple(-(-dimension // (2 ** entry["level"])) for dimension in content)
    elif breakage == "shape":
        entries[1]["data"] = entries[1]["data"][:-1]
    else:
        entries[1]["level"] = 0
    assert not check.readback_metadata_contract(entries, names, allocation, content)["pass"]


def test_odd_allocation_normalized_projection_differs_from_shift_ceil():
    names, allocation, content = ("odd.colour",), (11, 7), (5, 3)
    entries = readbacks(names, allocation, content)
    assert check.readback_metadata_contract(entries, names, allocation, content)["pass"]
    entries[2]["content"] = (2, 1)  # ceil(5/4)=2; ceil(5*2/11)=1 is the actual normalized projection.
    assert not check.readback_metadata_contract(entries, names, allocation, content)["pass"]


def test_complete_readback_cannot_truncate_a_large_admitted_target_set():
    names = tuple(f"target{target}.attachment{attachment}" for target in range(4) for attachment in range(4))
    allocation = content = (1024, 1024)
    entries = readbacks(names, allocation, content)
    complete = check.readback_metadata_contract(entries, names, allocation, content)
    assert complete["pass"]
    assert len(entries) == len(names) * max(allocation).bit_length()
    assert not check.readback_metadata_contract(entries[:92], names, allocation, content)["pass"]


def test_metadata_program_uses_canonical_mipped_targets_and_references_every_target():
    from rendering.native.mode import program_json

    import json
    packs = {"readback_metadata": b"four outputs", "show_colour": b"sampler"}
    passes, targets = check._readback_metadata_program(packs, 4)
    declaration, supplied = program_json(passes, targets)
    program = json.loads(declaration)
    assert len(program["targets"]) == len(targets)
    assert all(target["mips"] and target["size"] == "surface" for target in program["targets"])
    assert all(len(target["colour"]) == 4 for target in program["targets"])
    written = {entry["target"] for entry in program["passes"] if "target" in entry}
    sampled = {sampler["texture"].split(".")[0] for entry in program["passes"]
               for sampler in entry.get("samplers", ())}
    assert written == sampled == {target.name for target in targets}
    assert supplied.count(packs["readback_metadata"]) == len(targets)


def test_metadata_round_runs_alone_before_any_native_launch():
    with pytest.raises(SystemExit, match="2"):
        check.main(["--rounds", "readback_metadata", "rest"])
