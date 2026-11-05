"""Compact feature clips: a recorded ``FeatureClip`` without the redundancy of its JSONL form.

A native recording (``feature_frame.load_jsonl``) stores, on every ~11 ms frame, the newest
1..4096 capture samples as float32 base64, so consecutive frames repeat almost all of the same
audio, plus every lane as decimal text. A compact clip stores:

* the de-duplicated mono capture stream once, quantised to int16 (``1/32768`` steps, an exact
  float32 value on decode), as an order-2 fixed-predictor residual split into byte planes;
* each frame's capture history as a slice of that stream (its serial, rate, length and end);
* every other lane the replay reads, as float64 (exact) rows, the analysis spectrum, and the
  sparse typed events / onsets / strings as JSON;

all in one xz stream behind a small readable header (name, provenance). Decoding rebuilds the
``FeatureFrame`` sequence the replay engine (``feature_replay.ReplayBeatEngine``) consumes:
every field equal to the source except the int16 PCM and ``waveform``. ``waveform`` is the
recorder's 64-point preview that replay reads only for frames *without* capture history (it
serves ``history[-256:]`` otherwise); a compact clip always carries history, so the preview is
rebuilt from the history tail.

Production owns the reader (the Visualizer Studios' clip workers load the shipped
``assets/production/studio_clips``); ``tools/build_studio_clips.py`` writes them.
"""
from __future__ import annotations

import json
import lzma
import struct
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from widgets.spotify_visualizer.feature_frame import (
    CAPTURE_HISTORY_MAX_SAMPLES, WAVEFORM_COUNT, BandEnergy, CaptureHistory, EnergyLanes, FeatureClip,
    FeatureFrame, RealScaleLanes, RecordedOnset, TransientEnergy, TypedEvent, load_jsonl,
)

SUFFIX = ".srclip"
MAGIC = b"SRPSSCLIP\x00"
FORMAT_VERSION = 1
PCM_SCALE = 32768.0
_LANES = ("continuous", "pre_agc", "bubble", "transient")
_BAND = ("bass", "mid", "high", "overall")
_ROW = 4 * len(_BAND) + 1 + 32 + 4 + 2           # lanes, onset strength, raw bars, live, musical level
_XZ_FILTERS = [{"id": lzma.FILTER_LZMA2, "preset": 9 | lzma.PRESET_EXTREME}]


def is_compact(path: str | Path) -> bool:
    return Path(path).suffix.lower() == SUFFIX


def load_feature_clip(path: str | Path, *, name: str | None = None) -> FeatureClip:
    """A recorded clip in either form: a compact ``.srclip`` or a native JSONL recording."""
    return load_compact(path, name=name) if is_compact(path) else load_jsonl(path, name=name)


def first_timestamp_us(path: str | Path) -> int:
    """The clip's first frame time (a compact clip's header, or a recording's first line), without loading it."""
    if is_compact(path):
        return int(read_header(path)["first_timestamp_us"])
    with open(path, encoding="utf-8") as stream:
        return int(json.loads(stream.readline())["timestamp_us"])


# ------------------------------------------------------------------------------------------ PCM
def quantise(samples: np.ndarray) -> np.ndarray:
    return np.clip(np.round(np.asarray(samples, dtype=np.float64) * PCM_SCALE), -32768, 32767).astype(np.int64)


def _encode_pcm(values: np.ndarray) -> bytes:
    residual = np.diff(np.diff(values, prepend=0), prepend=0)                 # order-2 fixed predictor
    zigzag = ((residual << 1) ^ (residual >> 63)).astype(np.uint32)
    return b"".join((zigzag >> shift & 0xFF).astype(np.uint8).tobytes() for shift in (0, 8, 16))


def _decode_pcm(blob: bytes, count: int) -> np.ndarray:
    planes = np.frombuffer(blob, dtype=np.uint8).reshape(3, count).astype(np.int64)
    zigzag = planes[0] | planes[1] << 8 | planes[2] << 16
    residual = (zigzag >> 1) ^ -(zigzag & 1)
    values = np.cumsum(np.cumsum(residual))
    return (values / PCM_SCALE).astype("<f4")


# ----------------------------------------------------------------------------------- encode
def _history_stream(frames: Iterable[FeatureFrame]):
    """The de-duplicated capture stream and each frame's (start, end) slice of it."""
    chunks: list[np.ndarray] = []
    total = 0
    slices: list[tuple[int, int]] = []
    previous: np.ndarray | None = None
    previous_end = 0
    for frame in frames:
        history = frame.capture_history
        if history is None:
            raise ValueError("compact clips need native capture history on every frame")
        pcm = np.frombuffer(history.pcm_f32le, dtype="<f4")
        overlap = 0
        if previous is not None:
            # The longest suffix of the previous history that starts this one (capture appends samples).
            for shift in np.flatnonzero(previous == pcm[0]):
                tail = previous[shift:]
                if len(tail) <= len(pcm) and np.array_equal(tail, pcm[:len(tail)]):
                    overlap = len(tail)
                    break
            if overlap == 0 and previous_end:
                raise ValueError("capture histories do not overlap; this recording cannot be compacted")
        start = previous_end - overlap
        fresh = pcm[overlap:]
        if len(fresh):
            chunks.append(fresh)
            total += len(fresh)
        previous_end = total
        slices.append((start, total))
        previous = pcm
    return (np.concatenate(chunks) if chunks else np.zeros(0, "<f4")), slices


def _row(frame: FeatureFrame) -> list[float]:
    lanes = frame.energy
    row = [float(getattr(getattr(lanes, lane), band)) for lane in _LANES for band in _BAND]
    row.append(float(lanes.transient.onset_strength))
    row += [float(v) for v in frame.raw_bars]
    row += [float(v) for v in frame.real.live] + [float(v) for v in frame.real.musical_level]
    return row


def encode(frames: Iterable[FeatureFrame], *, name: str, provenance: Mapping[str, Any] | None = None) -> bytes:
    frames = tuple(frames)
    if not frames:
        raise ValueError("a clip needs at least one frame")
    if any(frame.real is None for frame in frames):
        raise ValueError("compact clips need schema 2 (real-scale) frames")
    stream, slices = _history_stream(frames)
    values = quantise(stream)
    rows = np.asarray([_row(frame) for frame in frames], dtype="<f8")
    spectra = [tuple(float(v) for v in frame.real.analysis_spectrum) for frame in frames]
    integers = np.asarray([(frame.timestamp_us, frame.capture_history.capture_serial,
                            frame.capture_history.sample_rate, start, end,
                            int(frame.playing) | int(frame.visible) << 1 | int(frame.energy.transient.onset_detected) << 2,
                            len(spectrum))
                           for frame, (start, end), spectrum in zip(frames, slices, spectra)], dtype="<i8")
    sparse = {}
    for index, frame in enumerate(frames):
        entry = {}
        if frame.mode != frames[0].mode:
            entry["mode"] = frame.mode
        if frame.control_event != "none":
            entry["control_event"] = frame.control_event
        if frame.energy.transient.onset_type:
            entry["onset_type"] = frame.energy.transient.onset_type
        if frame.real.events:
            entry["events"] = [[e.kind, e.strength] for e in frame.real.events]
        if frame.real.onsets:
            entry["onsets"] = [[o.kind, o.strength, o.magnitude, o.loudness, o.presence] for o in frame.real.onsets]
        if entry:
            sparse[str(index)] = entry
    spectrum_blob = np.asarray([v for spectrum in spectra for v in spectrum], dtype="<f8").tobytes()
    pcm_blob = _encode_pcm(values)
    sections = {"integers": integers.tobytes(), "rows": rows.tobytes(), "spectra": spectrum_blob,
                "pcm": pcm_blob, "sparse": json.dumps(sparse, separators=(",", ":")).encode("utf-8")}
    layout = [[key, len(blob)] for key, blob in sections.items()]
    body = lzma.compress(b"".join(sections.values()), format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64,
                         filters=_XZ_FILTERS)
    header = {"format": FORMAT_VERSION, "name": name, "frames": len(frames), "samples": int(len(values)),
              "mode": frames[0].mode, "first_timestamp_us": frames[0].timestamp_us,
              "last_timestamp_us": frames[-1].timestamp_us, "layout": layout,
              "clipped_samples": int(np.count_nonzero(np.abs(np.asarray(stream, np.float64)) * PCM_SCALE > 32767)),
              "provenance": dict(provenance or {})}
    head = json.dumps(header, indent=1, sort_keys=True).encode("utf-8")
    return MAGIC + struct.pack("<I", len(head)) + head + body


def write_compact(path: str | Path, frames: Iterable[FeatureFrame], *, name: str,
                  provenance: Mapping[str, Any] | None = None) -> bytes:
    data = encode(frames, name=name, provenance=provenance)
    Path(path).write_bytes(data)
    return data


# ----------------------------------------------------------------------------------- decode
def _split(data: bytes) -> tuple[dict, bytes]:
    if not data.startswith(MAGIC):
        raise ValueError("not a compact SRPSS clip")
    (length,) = struct.unpack_from("<I", data, len(MAGIC))
    start = len(MAGIC) + 4
    header = json.loads(data[start:start + length].decode("utf-8"))
    if header.get("format") != FORMAT_VERSION:
        raise ValueError(f"unsupported compact clip format: {header.get('format')}")
    return header, data[start + length:]


def read_header(path: str | Path) -> dict:
    """The readable header (name, frame count, timestamps, provenance) without decoding the body."""
    with open(path, "rb") as stream:
        head = stream.read(len(MAGIC) + 4)
        if not head.startswith(MAGIC):
            raise ValueError("not a compact SRPSS clip")
        (length,) = struct.unpack_from("<I", head, len(MAGIC))
        header = json.loads(stream.read(length).decode("utf-8"))
    if header.get("format") != FORMAT_VERSION:
        raise ValueError(f"unsupported compact clip format: {header.get('format')}")
    return header


def _preview(history: np.ndarray) -> tuple[float, ...]:
    """The 64-point preview replay reads only without history: the newest samples, resampled."""
    tail = history[-256:].astype(np.float64)
    positions = np.linspace(0.0, len(tail) - 1, WAVEFORM_COUNT)
    return tuple(float(v) for v in np.clip(np.interp(positions, np.arange(len(tail)), tail), -1.0, 1.0))


def decode(data: bytes, *, name: str | None = None) -> FeatureClip:
    header, body = _split(data)
    payload = lzma.decompress(body, format=lzma.FORMAT_XZ)
    sections, offset = {}, 0
    for key, size in header["layout"]:
        sections[key] = payload[offset:offset + size]
        offset += size
    count = int(header["frames"])
    integers = np.frombuffer(sections["integers"], dtype="<i8").reshape(count, 7)
    rows = np.frombuffer(sections["rows"], dtype="<f8").reshape(count, _ROW)
    spectra = np.frombuffer(sections["spectra"], dtype="<f8")
    stream = _decode_pcm(sections["pcm"], int(header["samples"]))
    sparse = json.loads(sections["sparse"].decode("utf-8"))
    frames = []
    spectrum_at = 0
    for index in range(count):
        timestamp, serial, rate, start, end, flags, spectrum_count = (int(v) for v in integers[index])
        row = rows[index].tolist()
        extra = sparse.get(str(index), {})
        bands = [BandEnergy(*row[k * 4:k * 4 + 4]) for k in range(3)]
        detected = bool(flags & 4)
        transient = TransientEnergy(*row[12:16], onset_detected=detected,
                                    onset_type=extra.get("onset_type", ""), onset_strength=row[16])
        history = stream[start:end]
        if not 0 < len(history) <= CAPTURE_HISTORY_MAX_SAMPLES:
            raise ValueError(f"frame {index}: capture history slice out of range")
        spectrum = tuple(spectra[spectrum_at:spectrum_at + spectrum_count].tolist())
        spectrum_at += spectrum_count
        real = RealScaleLanes(live=tuple(row[49:53]), musical_level=tuple(row[53:55]), analysis_spectrum=spectrum,
                              events=tuple(TypedEvent(kind, strength) for kind, strength in extra.get("events", ())),
                              onsets=tuple(RecordedOnset(*onset) for onset in extra.get("onsets", ())))
        frames.append(FeatureFrame(
            timestamp_us=timestamp,
            energy=EnergyLanes(continuous=bands[0], pre_agc=bands[1], bubble=bands[2], transient=transient),
            raw_bars=tuple(row[17:49]), waveform=_preview(history), playing=bool(flags & 1),
            visible=bool(flags & 2), mode=extra.get("mode", header["mode"]),
            control_event=extra.get("control_event", "none"), schema_version=2, real=real,
            capture_history=CaptureHistory(history.tobytes(), capture_serial=serial, sample_rate=rate)))
    return FeatureClip(name=name or header["name"], frames=tuple(frames))


def load_compact(path: str | Path, *, name: str | None = None) -> FeatureClip:
    return decode(Path(path).read_bytes(), name=name)


__all__ = [
    "FORMAT_VERSION", "SUFFIX", "decode", "encode", "first_timestamp_us", "is_compact", "load_compact",
    "load_feature_clip",
    "quantise", "read_header", "write_compact",
]
