"""ABI 43 (N5.2g with N4.g): field recipes (``native/core/src/field_recipe.h``), GPU-free.

- On the built module (``release/native_module``; compiled only on GitHub, so without it these skip and say so):
  ``field_recipe_check`` admits a recipe against its packs' reflection, and refuses each way a recipe can disagree with
  its pack (each refusal is the negative control of the admission it names); ``job_service_self_test``'s
  ``submit_field`` runs a field job through the product's ``JobService`` over the scripted backend: its outputs are
  published together under consecutive ids, each released by its own id, and dropped together when cancelled.
- Without the module: ``NativeMode.field`` and ``on_textures_ready`` hand the module what its functions parse.

The drawn proofs (the in-frame and job forms equal, the deadline's fallback, the outputs against Python's fields) run
on the hidden host once the module is built (``Current_Plan.md`` N5.2g).
"""
from __future__ import annotations

import os
import struct
from pathlib import Path

import pytest

from rendering.native import loader

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "release" / "native_module"
BUILT = os.name == "nt" and (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()
# A shipped compute pack with a sampler pair, a writeonly rgba16f image and one block (the motion blur's tile max,
# rendering/quick/scene3d/motion.py: uVelocity, uVelocityY, uTiles, MotionTileMax { int uTile; }).
TILE_MAX = ROOT / "rendering" / "quick" / "qml" / "shaders" / "transitions" / "scene3d_motion_tile_max.comp.qsb"

needs_module = pytest.mark.skipif(
    not BUILT or loader.EXPECTED_ABI < 43,
    reason=f"the native core is not built in this checkout: no release/native_module/{loader.MODULE_NAME}.pyd",
)


@pytest.fixture(scope="module")
def core():
    return loader.load(MODULE_DIR)


def _recipe(**changes) -> dict:
    recipe = {
        "input": "photo",
        "images": [{"name": "tiles", "format": "rgba16f", "size": [4, 4]}],
        "dispatches": [{"pack": 0, "block": 0, "groups": [1, 1, 1],
                        "bindings": {"uVelocity": "input", "uVelocityY": "input",
                                     "uTiles": {"image": "tiles", "access": "write"}}}],
        "outputs": [{"image": "tiles", "texture": "tiles_out"}],
    }
    recipe.update(changes)
    return recipe


def _block(size: int = 16) -> bytes:
    return struct.pack("<i", 8) + bytes(size - 4)


def _check(core, recipe: dict, blocks: list[bytes] | None = None) -> dict:
    return core.field_recipe_check(recipe, [TILE_MAX.read_bytes()], [_block()] if blocks is None else blocks)


# --------------------------------------------------------------------------------------------- on the built module


@needs_module
def test_a_recipe_bound_as_its_pack_declares_is_admitted_with_the_reflected_bindings(core):
    result = _check(core, _recipe())
    assert result["ok"], result
    dispatch = result["recipe"]["dispatches"][0]
    bound = {name: entry["binding"] for name, entry in dispatch["bindings"].items()}
    assert sorted(bound) == ["uTiles", "uVelocity", "uVelocityY"]
    assert len(set(bound.values())) == 3 and min(bound.values()) >= 0
    assert dispatch["block_binding"] >= 0 and 1 <= dispatch["block_size"] <= 16


def _bindings(**changes) -> dict:
    bindings = {"uVelocity": "input", "uVelocityY": "input", "uTiles": {"image": "tiles", "access": "write"}}
    bindings.update(changes)
    return {name: value for name, value in bindings.items() if value is not None}


@needs_module
@pytest.mark.parametrize("label, recipe, blocks, words", [
    ("image format", _recipe(images=[{"name": "tiles", "format": "rgba32f", "size": [4, 4]}]), None, "format"),
    ("writeonly image bound read", None, None, "qualifiers"),
    ("sampler unbound", None, None, "unbound"),
    ("binding the pack lacks", None, None, "unknown"),
    ("block too short", _recipe(), [_block(16)[:2]], "bytes"),
    ("block past its rounded size", _recipe(), [_block(16) + bytes(16)], "bytes"),
    ("no block for a pack that declares one", None, [], "unfilled"),
    ("sampler with no recipe input", _recipe(input=None), None, "input"),
    ("rgba8 output", _recipe(images=[{"name": "tiles", "format": "rgba8", "size": [4, 4]}]), None, "format"),
    ("output named as the input", _recipe(outputs=[{"image": "tiles", "texture": "photo"}]), None, "input"),
])
def test_every_disagreement_with_the_pack_is_refused_with_its_reason(core, label, recipe, blocks, words):
    if label == "writeonly image bound read":
        recipe = _recipe(dispatches=[{"pack": 0, "block": 0, "groups": [1, 1, 1],
                                      "bindings": _bindings(uTiles={"image": "tiles", "access": "read"})}])
    elif label == "sampler unbound":
        recipe = _recipe(dispatches=[{"pack": 0, "block": 0, "groups": [1, 1, 1],
                                      "bindings": _bindings(uVelocityY=None)}])
    elif label == "binding the pack lacks":
        recipe = _recipe(dispatches=[{"pack": 0, "block": 0, "groups": [1, 1, 1],
                                      "bindings": _bindings(uNothing="input")}])
    elif label == "no block for a pack that declares one":
        recipe = _recipe(dispatches=[{"pack": 0, "block": -1, "groups": [1, 1, 1], "bindings": _bindings()}])
    result = _check(core, recipe, blocks)
    assert not result["ok"], (label, result)
    assert words in result["error"], (label, result["error"])


def _jobs(core, steps: list[dict]) -> dict:
    result = core.job_service_self_test(steps)
    assert "error" not in result, result
    return result


@needs_module
def test_a_field_job_publishes_its_outputs_together_under_consecutive_ids(core):
    result = _jobs(core, [{"op": "submit_field", "name": "f", "outputs": 2},
                          {"op": "wait_idle"},
                          {"op": "release", "name": "f", "outputs": 1},
                          {"op": "wait_idle"},
                          {"op": "release", "name": "f"},
                          {"op": "wait_idle"}])
    published = result["steps"][1]["jobs"]["f"]
    assert published["state"] == "done", published
    first, second = published["field_outputs"]
    assert second == first + 1 and published["output"] == first
    assert result["steps"][1]["service"]["images"] == 2
    # Each output is released by its own id: one released leaves the other held (the control of the next step).
    assert result["steps"][3]["service"]["images"] == 1
    assert result["steps"][5]["service"]["images"] == 0


@needs_module
def test_a_field_job_needs_pixels_only_for_an_input(core):
    result = _jobs(core, [{"op": "submit_field", "name": "none", "outputs": 1},
                          {"op": "submit_field", "name": "with", "outputs": 1, "input": True},
                          {"op": "submit_field", "name": "without", "outputs": 1, "input": True, "pixels": False},
                          {"op": "wait_idle"}])
    jobs = result["steps"][-1]["jobs"]
    assert jobs["none"]["state"] == "done" and jobs["with"]["state"] == "done"
    assert jobs["without"]["state"] == "failed" and "pixels" in jobs["without"]["error"]


@needs_module
def test_a_field_job_cancelled_while_it_runs_drops_every_output(core):
    result = _jobs(core, [{"op": "hold"},
                          {"op": "submit_field", "name": "f", "outputs": 3},
                          {"op": "wait_entered", "count": 1},
                          {"op": "cancel", "name": "f"},
                          {"op": "go"},
                          {"op": "wait_idle"}])
    assert result["steps"][3]["result"] == "pending"
    last = result["steps"][-1]
    assert last["jobs"]["f"]["state"] == "cancelled"
    assert last["service"]["images"] == 0 and last["service"]["destroyed"] == 3


# --------------------------------------------------------------------------------------------- the Python face


class _Module:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def composite_mode_field(self, *args):
        self.calls.append(("field", args))

    def composite_mode_on_ready(self, *args):
        self.calls.append(("ready", args))


class _Composite:
    def _live(self) -> int:
        return 7


def test_native_mode_hands_the_field_and_the_ready_listener_to_the_module():
    from rendering.native.mode import NativeMode

    module = _Module()
    mode = NativeMode(module, _Composite())
    recipe = _recipe()
    mode.field(recipe, [b"pack"], [b"block"], pixels=b"\x00" * 16, size=(2, 2), deadline_ms=40)
    mode.field(recipe, [b"pack"], [b"block"])
    callback = lambda names: None  # noqa: E731
    mode.on_textures_ready(callback)
    mode.on_textures_ready(None)
    (kind, with_pixels), (_, without), ready, cleared = module.calls
    assert kind == "field"
    handle, recipe_json, packs, blocks, pixels, size, in_frame, deadline = with_pixels
    assert handle == 7 and packs == [b"pack"] and blocks == [b"block"]
    assert pixels == b"\x00" * 16 and size == (2, 2) and in_frame is False and deadline == 40
    import json

    assert json.loads(recipe_json) == recipe
    assert without[4] is None and without[5] == (0, 0) and without[7] == 0
    assert ready == ("ready", (7, callback)) and cleared == ("ready", (7, None))
