"""N2.3, the built packet reader (``native/core/src/packet_reader.h``) through rendering.native: the adversarial table with
each case's negative controls, the in-place writer's race, D1's own view and retire, D2's head read, one consumer and
the drop edge, and the bit-for-bit parity with the Python reference decoder on the shipped clip. These tests need the
compiled module, which only GitHub builds: where ``release/native_module/_srpss_native_core.pyd`` is not in this checkout
they skip and say so. GPU-free: no host, no window. The harness ``native/core/python/packet_reader_check.py`` runs the
same rounds and writes their evidence."""
from __future__ import annotations

import os
import sys
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path

import pytest

from rendering import native
from rendering.native import loader
from rendering.native import packet_reader as face
from tools import packet_reader_adversary as adversary

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "release" / "native_module"
BUILT = os.name == "nt" and (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()

pytestmark = pytest.mark.skipif(
    not BUILT,
    reason=f"the native core is not built in this checkout: no release/native_module/{loader.MODULE_NAME}.pyd (only "
           "GitHub builds it: tools/build_runner.py --mode github --run --select native_module, by the lead)",
)


@pytest.fixture(scope="module")
def core():
    return native.load(MODULE_DIR)


@pytest.fixture(scope="module")
def harness():
    sys.path.insert(0, str(ROOT / "native" / "core" / "python"))
    try:
        import packet_reader_check

        yield packet_reader_check
    finally:
        sys.path.remove(str(ROOT / "native" / "core" / "python"))
        sys.modules.pop("packet_reader_check", None)


def test_the_module_compiles_this_builds_frame_schemas(core):
    assert face.schema_table_differences(core.frame_schemas(), face.python_schema_table()) == []


def test_a_module_with_other_schemas_is_refused_before_any_reader_opens(core, monkeypatch):
    changed = face.python_schema_table()
    changed["schemas"][0]["fingerprint"] = "0" * 16
    monkeypatch.setattr(loader, "python_schema_table", lambda: changed)
    with pytest.raises(face.SchemaTableMismatch):
        core.packet_reader(f"srpss_viz_none_{os.getpid()}")
    assert core.packet_reader_live()["readers"] == 0


def test_the_reader_refuses_what_is_not_a_frame_mapping(core):
    with pytest.raises(ValueError, match="frame mapping's name"):
        core.packet_reader("not_ours")
    memory = SharedMemory(name=f"srpss_viz_blank_{os.getpid()}", create=True, size=4096)
    try:
        with pytest.raises(ValueError, match="not a visualizer frame mapping"):
            core.packet_reader(memory.name)
    finally:
        memory.close()
        memory.unlink()
    with pytest.raises(ValueError, match="unknown packet reader controls"):
        core.packet_reader("srpss_viz_x", controls=("not_a_control",))
    assert core.packet_reader_live() == {"readers": 0, "views": 0, "handles": 0}


def test_the_adversarial_table_holds_and_every_negative_control_fails_it(core):
    table = adversary.run_native_table(core)
    failures = {row["case"]: row["failures"] for row in table["cases"] if not row["held"]}
    assert not failures, failures
    unseen = {row["case"]: control for row in table["cases"] for control, seen in row["controls"].items()
              if not seen["failed"]}
    assert not unseen, unseen
    assert table["live_after"] == {"readers": 0, "views": 0, "handles": 0}


def test_the_in_place_writer_never_gets_a_mixed_record_past_the_seqlock(harness, core):
    result = harness.stress_round(core)
    assert result["seqlock"]["mixed"] == 0 and result["seqlock"]["torn_reads"] > 0, result["seqlock"]
    assert result["control_skip_seqlock"]["mixed"] > 0, result["control_skip_seqlock"]


def test_d1_the_readers_own_view_and_retire(harness, core):
    result = harness.d1_round(core)
    assert result["pass"], {name: ok for name, ok in result["checks"].items() if not ok}


def test_d2_the_head_read_one_consumer_and_the_drop_edge(harness, core):
    result = harness.d2_round(core)
    assert result["pass"], {name: ok for name, ok in result["checks"].items() if not ok}


@pytest.mark.qt
def test_the_reader_matches_the_reference_decoder_bit_for_bit_on_the_shipped_clip(harness, core, qt_app):
    frames = harness.spectrum_frames(1.5, "growing_pains")
    assert len(frames) > 30
    result = harness.parity(core, frames)
    assert result["pass"], {key: result[key] for key in ("accepted", "frames", "mismatches", "one_bit_control_seen")}
