"""N2.3's proof (Current_Plan.md item 8b): the C++ packet reader (``native/core/src/packet_reader.h``) against the Python
reference reader, through ``rendering.native``. GPU-free: no host, no window, no graphics API.

Rounds:
  parity  the shipped Studio clip replayed through the production owner on Spectrum (as tools/native_schema_check.py),
          every logical frame published by the engine worker's native writer (PacketMailbox(role="writer",
          payload="native")) and read by the C++ reader: accepted, acknowledged at the accept edge, its record byte for
          byte the encoder's and the slot's, its fields (decoded by the C++ table) equal bit for bit to the reference
          decoder's (spectrum_native_schema.decode) and to the tagged codec's projection, its slot head equal to the
          Python reader's. Negative control: the comparison sees one flipped float bit.
  table   the adversarial table (tools/packet_reader_adversary.py: torn, stale, duplicate, refused at the head and in
          the record, oversize, another identity), each case again under each of its negative controls, which must
          fail it.
  stress  a writer process rewrites the latest slot in place while the reader reads: no mixed record is ever accepted
          and torn copies are counted. Negative control: skip_copy_reread (the begin re-read after the copy, alone)
          accepts mixed records. Then the same guard deterministically: a slot rewritten in place while the read is
          paused inside its copy (pause_in_copy) is torn; under skip_copy_reread it is accepted. (The head's own
          seqlock, skip_head_seqlock, is the table's control for the odd latest and the end behind.)
  d1      the reader's own view: the owner closes its mapping and the reader still reads the owner's last frame from
          its pinned view, while a new reader by that name is retired (the control: only the view keeps the section);
          retire stops every copy at once, even with a frame waiting (control: copy_while_retiring starts it), release
          unmaps, close leaves nothing alive; copies started equal finished.
  d2      the head read moves nothing (ten reads: nothing accepted, nothing acknowledged); one consumer: a protected
          edge reaches the core exactly once (control: a Python take, the forbidden second consumer, steals it); the
          drop edge: the dropped frame never comes back, a newer one does (control: head_resets_watermark resurrects it).
  reference (no module needed) the table and the stress on the Python reference reader and its naive control, and the
          clip's Python half (the native writer and reference decoder against the tagged codec).

Usage (repository venv, from the checkout holding the built module):
  python native/core/python/packet_reader_check.py --module-dir release/native_module
      [--rounds parity table stress d1 d2 reference] [--seconds 1.5] [--clip growing_pains] [--label n23_reader]
  python native/core/python/packet_reader_check.py --rounds reference      (no module)
Evidence: .artifacts/evidence/native_core/n2_3/<date>_<label>/summary.json. The last line is the verdict
("N23 VERDICT PASS" or "N23 VERDICT FAIL: ..."); the exit code is 0 for PASS, 1 for FAIL.
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import time
import traceback
from pathlib import Path

ROUNDS = ("parity", "table", "stress", "d1", "d2", "reference")
NATIVE_ROUNDS = ("parity", "table", "stress", "d1", "d2")
STRESS_READS = 200_000
#: The skip_copy_reread control (skip_seqlock until the split) reads until its first mixed record, at most this many reads (build round 1: 4 mixed records
#: in 200,000 reads, so a fixed count was a thin margin).
CONTROL_READ_CAP = 5_000_000


# ------------------------------------------------------------------------------------------------ the clip

def spectrum_frames(seconds: float, clip: str) -> list:
    """The logical frames the production owner hands its renderer while it replays ``clip`` on Spectrum."""
    from PySide6.QtWidgets import QApplication

    import tools.expanded_visualizer_evidence as evidence
    from widgets.spotify_visualizer.render_bridge import VisualizerSnapshotBridge

    QApplication.instance() or QApplication([])
    frames: list = []
    publish = VisualizerSnapshotBridge.publish

    def recording(self, snapshot):
        frames.append(snapshot.logical)
        return publish(self, snapshot)

    VisualizerSnapshotBridge.publish = recording
    try:
        evidence.owner_replay(evidence.shipped_clip(seconds, clip), "spectrum")
    finally:
        VisualizerSnapshotBridge.publish = publish
    return [frame for frame in frames if frame.mode_id == "spectrum"]


def _bits(value) -> object:
    """A float as its 64 bits (None stays None): equal bits, not equal values."""
    return None if value is None else struct.pack("<d", float(value))


def _tagged(frame):
    from core.visualizer_engine import frame_codec

    return frame_codec.decode(frame_codec.encode((1, 1, 0.0, frame)))[3]


def parity(core, frames: list) -> dict:
    from core.visualizer_engine import spectrum_native_schema as spectrum
    from core.visualizer_engine.packet_abi import FramePacketReader
    from core.visualizer_engine.packet_mailbox import PacketMailbox, publication_flags

    owner = PacketMailbox(role="reader", slot_bytes=64 * 1024, payload="native")     # creates the mapping, never takes
    writer = PacketMailbox(role="writer", attach=owner.mapping_name, payload="native")
    reader = core.packet_reader(owner.mapping_name)
    second = FramePacketReader(owner._memory.buf)                                     # an unchecked second view
    mismatches: list = []
    accepted = 0
    one_bit_seen = None
    try:
        for index, frame in enumerate(frames):
            writer.publish(frame, generation=frame.runtime_generation, activation_id=frame.activation_id)
            result = reader.read()
            native = reader.frame()
            packet = second.read_latest()
            problems = []
            if result != "accepted" or native is None or packet is None:
                problems.append(f"read {result}, python packet {packet is not None}")
            else:
                accepted += 1
                fields = dict(native.fields)
                if native.payload != packet.payload:
                    problems.append("the record differs from the slot's payload")
                if native.payload != spectrum.encode(frame):
                    problems.append("the record differs from the encoder's")
                if repr(fields) != repr(spectrum.decode(native.payload)):
                    problems.append("the fields differ from the reference decoder's")
                if repr(fields) != repr(spectrum.project(_tagged(frame))):
                    problems.append("the fields differ from the tagged codec's projection")
                head = native.head
                python_head = {
                    "sequence": packet.sequence, "payload_bytes": len(packet.payload),
                    "payload_schema": packet.payload_schema, "flags": packet.flags,
                    "protected_edge_mask": packet.protected_edge_mask,
                    "runtime_generation": packet.runtime_generation, "engine_generation": packet.engine_generation,
                    "activation_id": packet.activation_id, "mode_code": packet.mode_code,
                    "publish_ns": packet.publish_ns,
                }
                for key, expected in python_head.items():
                    if head[key] != expected:
                        problems.append(f"head {key}: {head[key]!r} != {expected!r}")
                for key, expected in (("logical_timestamp", packet.logical_timestamp),
                                      ("source_timestamp", packet.source_timestamp)):
                    if _bits(head[key]) != _bits(expected):
                        problems.append(f"head {key}: {head[key]!r} != {expected!r}")
                if head["flags"] != publication_flags(frame) or head["payload_schema"] != spectrum.SCHEMA_ID:
                    problems.append("the slot's flags or schema stamp")
                if writer._writer.consumed_sequence != native.sequence:
                    problems.append("not acknowledged at the accept edge")
                if one_bit_seen is None:
                    # Negative control: the comparison sees the lowest bit of one bar.
                    bars = list(fields["bars"])
                    bars[0] = struct.unpack("<d", struct.pack("<Q", struct.unpack("<Q", struct.pack(
                        "<d", bars[0]))[0] ^ 1))[0]
                    flipped = dict(fields, bars=tuple(bars))
                    one_bit_seen = repr(flipped) != repr(spectrum.decode(native.payload))
            if problems:
                mismatches.append({"frame": index, "problems": problems})
        state = reader.state()
    finally:
        second.release()
        reader.close()
        writer.close()
        owner.close()
    passed = bool(frames) and accepted == len(frames) and not mismatches and bool(one_bit_seen) \
        and state["refused"] == 0 and state["torn_reads"] == 0
    return {"pass": passed, "frames": len(frames), "accepted": accepted, "mismatches": mismatches[:20],
            "mismatch_count": len(mismatches), "one_bit_control_seen": one_bit_seen,
            "schema_id": hex(spectrum.SCHEMA_ID), "record_bytes": spectrum.LAYOUT.size,
            "fingerprint": spectrum.LAYOUT.fingerprint(), "reader_state": state}


def reference_clip_half(frames: list) -> dict:
    """The Python half the C++ reader is compared with: the native writer, the slot-head check and the reference
    decoder against the tagged codec, through a real native stream (tools/native_schema_check.py's comparison)."""
    from core.visualizer_engine import spectrum_native_schema as spectrum
    from core.visualizer_engine.packet_mailbox import PacketMailbox

    mailbox = PacketMailbox(slot_bytes=64 * 1024, payload="native")
    mismatches = []
    try:
        for index, frame in enumerate(frames):
            mailbox.publish(frame, generation=frame.runtime_generation, activation_id=frame.activation_id)
            taken = mailbox.take()
            if taken is None or repr(taken.state) != repr(spectrum.project(_tagged(frame))):
                mismatches.append(index)
        refused = mailbox.refused_payloads
    finally:
        mailbox.close()
    return {"pass": bool(frames) and not mismatches and not refused, "frames": len(frames),
            "mismatches": mismatches[:20], "refused": refused}


# ---------------------------------------------------------------------------------------- D1 and D2 rounds

def _mapping():
    from tools import packet_reader_adversary as adversary

    memory = adversary.create_mapping()
    return memory, adversary.Adversary(memory.name)


def _close_mapping(memory, adv) -> None:
    adv.close()
    memory.close()
    memory.unlink()


def d1_round(core) -> dict:
    from tools import packet_reader_adversary as adversary

    checks: dict[str, bool] = {}
    before = core.packet_reader_live()
    memory, adv = _mapping()
    name = memory.name
    reader = core.packet_reader(name)
    try:
        adv.publish(adversary.valid_record(1))
        checks["the first frame is accepted"] = reader.read() == "accepted"
        last = adv.publish(adversary.valid_record(2))
        _close_mapping(memory, adv)                      # the owner closes and unlinks; the reader keeps its own view
        late = core.packet_reader(name)
        late_state = late.state()
        checks["control: a new reader by the closed name is retired"] = (
            late_state["state"] == "retired" and bool(late_state["open_error"]) and late.read() == "retired"
            and late.head() is None)
        late.close()
        checks["the pinned view still reads the owner's last frame"] = (
            reader.read() == "accepted" and reader.frame().sequence == last
            and adversary.record_is_consistent(dict(reader.frame().fields)))
        head = reader.head()
        checks["the head read works on the pinned view"] = head is not None and head["sequence"] == last
        state = reader.state()
        checks["liveness: every copy started finished, the last accepted is the stream's"] = (
            state["copies_started"] == state["copies_finished"] == 2 and state["last_accepted_sequence"] == last)
        reader.retire()
        checks["retiring: no copy starts"] = (reader.read() == "retiring"
                                              and reader.state()["copies_started"] == state["copies_started"])
        reader.release()
        released = reader.state()
        checks["released: retired, unmapped, nothing retained"] = (
            released["state"] == "retired" and not released["mapped"] and reader.frame() is None
            and reader.read() == "retired" and reader.head() is None)
    finally:
        reader.close()
    # The same rule with a frame waiting (above, nothing new was published, so no copy could start anyway).
    checks["retiring with a frame waiting: no copy starts"] = _retiring_with_a_frame_waiting(core, controls=())
    checks["control: copy_while_retiring starts that copy"] = not _retiring_with_a_frame_waiting(
        core, controls=("copy_while_retiring",))
    after = core.packet_reader_live()
    checks["nothing left: readers, views and handles back to where they were"] = after == before
    return {"pass": all(checks.values()), "checks": checks, "live_before": before, "live_after": after}


def _retiring_with_a_frame_waiting(core, *, controls: tuple) -> bool:
    """A whole, admissible frame is waiting and the stream is retiring: the read returns retiring with no copy started,
    nothing retained and nothing acknowledged."""
    from tools import packet_reader_adversary as adversary

    memory, adv = _mapping()
    reader = core.packet_reader(memory.name, controls=controls)
    try:
        adv.publish(adversary.valid_record(1))
        reader.retire()
        result = reader.read()
        state = reader.state()
        held = (result == "retiring" and state["copies_started"] == 0 and reader.frame() is None
                and adv.consumed() == 0)
    finally:
        reader.close()
        _close_mapping(memory, adv)
    return held


def _edge_round(core, *, steal: bool) -> dict:
    """A protected edge published, then a frame without one: the core reads the second frame and must see the edge
    carried (the writer carries it until acknowledged), then not again. ``steal``: a Python take of that frame first
    (the forbidden second consumer)."""
    from core.visualizer_engine.packet_abi import FramePacketReader, FramePacketWriter
    from tools import packet_reader_adversary as adversary

    memory, adv = _mapping()
    reader = core.packet_reader(memory.name)
    writer = FramePacketWriter(adv.view)
    python = FramePacketReader(adv.view)
    edge = 0b100
    schema = adversary.spectrum_schema_id()
    identity = dict(runtime_generation=adversary.IDENTITY[0], engine_generation=adversary.IDENTITY[1],
                    activation_id=adversary.IDENTITY[2], mode_code=1)
    try:
        writer.publish(adversary.valid_record(1), payload_schema=schema, logical_timestamp=1.0,
                       protected_edges=edge, **identity)
        carried = writer.publish(adversary.valid_record(2), payload_schema=schema, logical_timestamp=2.0, **identity)
        python.has_unread()                                     # the owner's non-consuming checks
        reader.head()
        if steal:
            packet = python.read_latest()                       # PacketMailbox._consume's take and acknowledgement
            python.acknowledge(packet.sequence)
            writer.publish(adversary.valid_record(1), payload_schema=schema, logical_timestamp=3.0, **identity)
        first = reader.read()
        first_mask = reader.frame().head["protected_edge_mask"] if reader.frame() else None
        later = writer.publish(adversary.valid_record(2), payload_schema=schema, logical_timestamp=4.0, **identity)
        second = reader.read()
        second_mask = reader.frame().head["protected_edge_mask"]
        delivered = [mask for mask in (first_mask, second_mask) if mask and mask & edge]
        return {"first": first, "first_mask": first_mask, "second": second, "second_mask": second_mask,
                "carried_sequence": carried, "later_sequence": later, "delivered_times": len(delivered),
                "consumed_is_the_cores": adv.consumed() == reader.state()["acknowledged_sequence"]}
    finally:
        writer.release()
        python.release()
        reader.close()
        _close_mapping(memory, adv)


def d2_round(core) -> dict:
    from tools import packet_reader_adversary as adversary

    checks: dict[str, bool] = {}
    # The head read moves nothing.
    memory, adv = _mapping()
    reader = core.packet_reader(memory.name)
    try:
        sequence = adv.publish(adversary.valid_record(1), edges=0b10)
        heads = [reader.head() for _ in range(10)]
        state = reader.state()
        checks["ten head reads: the newest whole slot each time"] = all(h and h["sequence"] == sequence for h in heads)
        checks["ten head reads move nothing"] = (adv.consumed() == 0 and state["accepted_sequence"] == 0
                                                 and state["acknowledged"] == 0 and state["head_reads"] == 10
                                                 and state["copies_started"] == 0)
        checks["the read then takes the frame with its edge and acknowledges it"] = (
            reader.read() == "accepted" and reader.frame().head["protected_edge_mask"] == 0b10
            and adv.consumed() == sequence)
    finally:
        reader.close()
        _close_mapping(memory, adv)
    # One consumer: the edge reaches the core exactly once; a Python take steals it.
    held = _edge_round(core, steal=False)
    stolen = _edge_round(core, steal=True)
    checks["one consumer: the edge reaches the core exactly once"] = (
        held["delivered_times"] == 1 and held["first"] == held["second"] == "accepted" and held["consumed_is_the_cores"])
    checks["control: a Python take (a second consumer) steals the edge"] = stolen["delivered_times"] == 0
    # The drop edge.
    drop = _drop_round(core, controls=())
    resurrected = _drop_round(core, controls=("head_resets_watermark",))
    checks["drop: the dropped frame never comes back, a newer one does"] = drop["held"]
    checks["control: head_resets_watermark resurrects the dropped frame"] = not resurrected["held"]
    return {"pass": all(checks.values()), "checks": checks, "edge": held, "edge_stolen": stolen, "drop": drop,
            "drop_control": resurrected}


def _drop_round(core, *, controls: tuple) -> dict:
    from tools import packet_reader_adversary as adversary

    memory, adv = _mapping()
    reader = core.packet_reader(memory.name, controls=controls)
    try:
        dropped = adv.publish(adversary.valid_record(1))
        steps = {"accepted": reader.read(), "retained": reader.frame().sequence}
        reader.drop_retained_frame()
        steps["retained before the next read"] = reader.frame() is not None   # applied at the next frame edge
        steps["after the drop"] = reader.read()
        steps["retained after the drop"] = reader.frame()
        # The accepted watermark is the drop's (audit 14 Nov, low 2: the drop keeps none of its own).
        steps["watermark after the drop"] = reader.state()["accepted_sequence"]
        reader.head()                                                          # a head read and a late wake
        steps["late wake"] = reader.read()
        steps["retained after the late wake"] = None if reader.frame() is None else reader.frame().sequence
        newer = adv.publish(adversary.valid_record(2))
        steps["newer"] = reader.read()
        steps["retained newer"] = reader.frame().sequence
        state = reader.state()
    finally:
        reader.close()
        _close_mapping(memory, adv)
    held = (steps["accepted"] == "accepted" and steps["retained before the next read"]
            and steps["after the drop"] == "nothing" and steps["retained after the drop"] is None
            and steps["late wake"] == "nothing" and steps["retained after the late wake"] is None
            and steps["newer"] == "accepted" and steps["retained newer"] == newer
            and steps["watermark after the drop"] == dropped and state["drops_applied"] == 1)
    steps["retained after the drop"] = None if steps["retained after the drop"] is None else "a frame"
    return {"held": held, "steps": steps, "dropped": dropped}


# ------------------------------------------------------------------------------------------------ stress

def rewritten_during_copy(core, *, controls: tuple = ()) -> dict:
    """The re-read after the copy, isolated and deterministic: the reader pauses inside its payload copy (the
    pause_in_copy hook, on a second thread), the slot it copies is rewritten in place (its begin odd, another record),
    and the copy resumes. Held: torn, nothing retained, nothing acknowledged. Control (skip_copy_reread, the only guard
    that sees this write, since the head was whole when it was read): the rewritten record is accepted."""
    import threading

    from tools import packet_reader_adversary as adversary

    memory, adv = _mapping()
    reader = core.packet_reader(memory.name, controls=("pause_in_copy",) + tuple(controls))
    outcome: dict = {}
    try:
        first = adv.publish(adversary.valid_record(1))
        thread = threading.Thread(target=lambda: outcome.setdefault("read", reader.read()), name="copy-reread reader")
        thread.start()
        try:
            paused = reader.wait_paused(10000)
            if paused:
                adv.write_slot(adv.slot_of(first), sequence=first + 2, payload=adversary.valid_record(2),
                               begin=first + 1, end=first)
        finally:
            reader.resume()
            thread.join(30)
        frame = reader.frame()
        consumed = adv.consumed()
        torn = reader.state()["torn_reads"]
    finally:
        reader.close()
        _close_mapping(memory, adv)
    held = (paused and not thread.is_alive() and outcome.get("read") == "torn" and frame is None and consumed == 0
            and torn == 1)
    return {"held": held, "paused": paused, "read": outcome.get("read"), "retained": frame is not None,
            "consumed": consumed, "torn_reads": torn}


def stress_round(core) -> dict:
    from tools import packet_reader_adversary as adversary

    held = adversary.stress(lambda name: adversary.NativeReader(core, name), reads=STRESS_READS)
    control = adversary.stress(lambda name: adversary.NativeReader(core, name, controls=("skip_copy_reread",)),
                               reads=CONTROL_READ_CAP, stop_on_mixed=True)
    reread = rewritten_during_copy(core)
    reread_control = rewritten_during_copy(core, controls=("skip_copy_reread",))
    passed = (held["mixed"] == 0 and held["accepted"] > 0 and held["torn_reads"] > 0 and control["mixed"] > 0
              and reread["held"] and not reread_control["held"] and reread_control["read"] == "accepted")
    return {"pass": passed, "seqlock": held, "control_skip_copy_reread": control,
            "rewritten_during_copy": reread, "rewritten_during_copy_control": reread_control}


def reference_round(frames: list | None) -> dict:
    from tools import packet_reader_adversary as adversary

    table = adversary.run_reference_table()
    held = adversary.stress(lambda name: adversary.ReferenceReader(name), reads=STRESS_READS // 2)
    naive = adversary.stress(lambda name: adversary.ReferenceReader(name, naive=True), reads=STRESS_READS // 2)
    clip = reference_clip_half(frames) if frames is not None else None
    passed = (table["pass"] and held["mixed"] == 0 and held["torn_reads"] > 0 and naive["mixed"] > 0
              and (clip is None or clip["pass"]))
    return {"pass": passed, "table": table, "stress": held, "stress_naive_control": naive, "clip": clip}


# -------------------------------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--module-dir", default="release/native_module", help="the folder holding the built module")
    parser.add_argument("--repo", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--rounds", nargs="+", default=list(ROUNDS), choices=ROUNDS)
    parser.add_argument("--seconds", type=float, default=1.5, help="how much of the clip to replay")
    parser.add_argument("--clip", default="growing_pains", help="a shipped Studio clip's name")
    parser.add_argument("--label", default="n23_reader", help="the evidence folder's label")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.repo)
    if root not in sys.path:
        sys.path.insert(0, root)
    from tools import artifact_paths

    artifact_paths.repository_root(root)
    out = artifact_paths.evidence_dir("native_core", "n2_3", args.label)
    out.mkdir(parents=True, exist_ok=True)
    summary: dict = {"rounds": list(args.rounds), "module_dir": args.module_dir, "clip": args.clip,
                     "seconds": args.seconds, "results": {}}
    started = time.monotonic()
    core = None
    if set(args.rounds) & set(NATIVE_ROUNDS):
        from rendering import native

        module_dir = Path(args.module_dir)
        if not module_dir.is_absolute():
            module_dir = Path(root) / module_dir
        try:
            core = native.load(module_dir)
            summary["module"] = {"path": str(core.path), "abi": core.abi, "qt": core.qt_version}
        except native.NativeCoreUnavailable as exc:
            summary["module"] = {"error": exc.reason}
    frames = None
    if {"parity", "reference"} & set(args.rounds):
        frames = spectrum_frames(args.seconds, args.clip)
        summary["clip_frames"] = len(frames)
    from tools import packet_reader_adversary as adversary

    runners = {
        "parity": lambda: parity(core, frames),
        "table": lambda: adversary.run_native_table(core),
        "stress": lambda: stress_round(core),
        "d1": lambda: d1_round(core),
        "d2": lambda: d2_round(core),
        "reference": lambda: reference_round(frames),
    }
    for name in args.rounds:
        if name in NATIVE_ROUNDS and core is None:
            summary["results"][name] = {"pass": False, "error": f"no module: {summary['module'].get('error')}"}
            continue
        try:
            summary["results"][name] = runners[name]()
        except Exception:
            text = traceback.format_exc()
            summary["results"][name] = {"pass": False, "error": text.strip().splitlines()[-1], "traceback": text}
        (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    summary["seconds_total"] = round(time.monotonic() - started, 1)
    failed = [name for name, result in summary["results"].items() if not result.get("pass")]
    summary["verdict"] = "PASS" if not failed else f"FAIL: {', '.join(failed)}"
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    for name, result in summary["results"].items():
        print(f"{name}: {'PASS' if result.get('pass') else 'FAIL'}"
              + (f" ({result['error']})" if result.get("error") else ""))
    print(f"evidence: {out}")
    print(f"N23 VERDICT {summary['verdict']}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
