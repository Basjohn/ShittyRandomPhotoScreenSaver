"""Exact binary codec for visualizer logical frames (native core P2, work order 2).

The engine worker encodes each ``VisualizerLogicalFrame`` into a frame-packet payload (``packet_abi``); the main
process decodes it back into the very same immutable frame: ``repr(decode(encode(frame))) == repr(frame)``, the
identity the production frame digests use (so -0.0 stays -0.0 and every float keeps all 64 bits).

The canonical frames are frozen dataclasses over a small, closed value domain (``render_state.freeze_render_value``):
None, bool, int, finite float, str, bytes, tuples, ``FrozenFields`` and the canonical frame dataclasses. One tagged
encoding covers it, so every mode shares one codec; a value outside the domain is refused, never guessed. Tuples of
floats (bars, waveforms, wake records) take a packed float64 fast path. Decoding builds dataclasses with
``object.__new__`` and sets their fields directly: the writer is our own engine, which built them through their
validating constructors, so the main thread does not validate them twice.

Layout: ``u16 CODEC_SCHEMA`` then one tagged value. Integers are little-endian; lengths are u32.
"""
from __future__ import annotations

import struct
from dataclasses import fields

CODEC_SCHEMA = 1

_NONE, _FALSE, _TRUE, _INT, _FLOAT, _STR, _BYTES, _TUPLE, _FIELDS, _DATACLASS, _FLOATS, _ARRAY, _PROXY = range(13)
_MAPPING_PROXY = type(__import__("types").MappingProxyType({}))

_RENDER_STATE = "widgets.spotify_visualizer.render_state"
#: Stable type ids (never renumber: append), as (module, class name).
_TYPES = tuple((_RENDER_STATE, name) for name in (
    "VisualizerLogicalFrame", "VisualizerCommonState", "VisualizerEnergyState", "VisualizerTransientState",
    "VisualizerProtectedEdge", "SpectrumFrame", "ExtrudedSpectrumFrame", "ShockwaveGridFrame", "SphereParticleCohort",
    "SphereFrame", "OscilloscopeFrame", "BubbleFrame", "DevCurveFrame", "ExtrudedBubbleFrame", "WaveformRibbonFrame",
)) + (
    ("core.ribbon_packet", "RibbonPacket"),                                  # Waveform Ribbon's packet
    ("widgets.spotify_visualizer.extruded_bubble_drift_log", "DriftFamily"),  # Extruded Bubble's drift geometry
) + tuple(("core.waveform_ribbon_scene", name) for name in (                # Waveform Ribbon's scene recipe
    "Recipe", "Environment", "Floor", "Flow", "Fog", "Shaping",
)) + (
    ("core.ribbon_style", "RibbonMaterial"), ("core.ribbon_style", "RibbonSparks"),
    # Waveform Ribbon's free strands (a style the shipped presets reach; found by the owner-on-the-worker identity
    # gate, work order 5 slice 5.2: a frame carrying it was refused at the worker's publish).
    ("core.ribbon_style", "RibbonStrays"),
)

_U16, _U32, _I64, _F64 = struct.Struct("<H"), struct.Struct("<I"), struct.Struct("<q"), struct.Struct("<d")
_I64_MIN, _I64_MAX = -(1 << 63), (1 << 63)-1


class FrameCodecError(ValueError):
    """A value outside the canonical frame domain, or a payload this build cannot read."""


_tables: tuple[dict, list, object] | None = None


def _types():
    global _tables
    if _tables is None:
        import importlib
        from widgets.spotify_visualizer import render_state
        classes = [getattr(importlib.import_module(module), name) for module, name in _TYPES]
        ids = {cls: index for index, cls in enumerate(classes)}
        layouts = [tuple(field.name for field in fields(cls)) for cls in classes]
        _tables = (ids, list(zip(classes, layouts)), render_state.FrozenFields)
    return _tables


def _is_array(value) -> bool:
    return type(value).__module__ == "numpy" and type(value).__name__ == "ndarray"


def encode(frame) -> bytes:
    ids, layouts, frozen_fields = _types()
    out = bytearray(_U16.pack(CODEC_SCHEMA))
    append = out.extend

    def put(value) -> None:
        kind = type(value)
        if value is None:
            out.append(_NONE)
        elif kind is bool:
            out.append(_TRUE if value else _FALSE)
        elif kind is int:
            if not _I64_MIN <= value <= _I64_MAX:
                raise FrameCodecError(f"integer out of 64-bit range: {value}")
            out.append(_INT)
            append(_I64.pack(value))
        elif kind is float:
            out.append(_FLOAT)
            append(_F64.pack(value))
        elif kind is str:
            data = value.encode("utf-8")
            out.append(_STR)
            append(_U32.pack(len(data)))
            append(data)
        elif kind is bytes:
            out.append(_BYTES)
            append(_U32.pack(len(value)))
            append(value)
        elif kind is tuple:
            if value and all(type(item) is float for item in value):
                out.append(_FLOATS)
                append(_U32.pack(len(value)))
                append(struct.pack(f"<{len(value)}d", *value))
            else:
                out.append(_TUPLE)
                append(_U32.pack(len(value)))
                for item in value:
                    put(item)
        elif kind is frozen_fields:
            out.append(_FIELDS)
            append(_U32.pack(len(value.entries)))
            for name, item in value.entries:
                put(name)
                put(item)
        elif kind in ids:
            type_id = ids[kind]
            out.append(_DATACLASS)
            append(_U16.pack(type_id))
            for name in layouts[type_id][1]:
                put(getattr(value, name))
        elif kind is _MAPPING_PROXY:    # read-only maps inside Waveform's recipe (key order kept)
            out.append(_PROXY)
            append(_U32.pack(len(value)))
            for key, item in value.items():
                put(key)
                put(item)
        elif _is_array(value):          # Extruded Bubble's CPU-reference geometry (never mutated)
            dtype = value.dtype.str.encode("ascii")
            data = value.tobytes(order="C")
            out.append(_ARRAY)
            append(_U16.pack(len(dtype)))
            append(dtype)
            append(_U16.pack(value.ndim))
            for size in value.shape:
                append(_I64.pack(size))
            append(_U32.pack(len(data)))
            append(data)
        else:
            raise FrameCodecError(f"not a canonical frame value: {kind.__name__}")

    put(frame)
    return bytes(out)


def decode(payload: bytes):
    _ids, layouts, frozen_fields = _types()
    view = memoryview(payload)
    if len(view) < 2 or _U16.unpack_from(view, 0)[0] != CODEC_SCHEMA:
        raise FrameCodecError("frame payload of another codec schema")
    position = 2
    new, set_field = object.__new__, object.__setattr__

    def take():
        nonlocal position
        tag = view[position]
        position += 1
        if tag == _NONE:
            return None
        if tag == _FALSE:
            return False
        if tag == _TRUE:
            return True
        if tag == _INT:
            value = _I64.unpack_from(view, position)[0]
            position += 8
            return value
        if tag == _FLOAT:
            value = _F64.unpack_from(view, position)[0]
            position += 8
            return value
        if tag in (_STR, _BYTES):
            size = _U32.unpack_from(view, position)[0]
            data = bytes(view[position+4:position+4+size])
            position += 4+size
            return data.decode("utf-8") if tag == _STR else data
        if tag == _FLOATS:
            count = _U32.unpack_from(view, position)[0]
            values = struct.unpack_from(f"<{count}d", view, position+4)
            position += 4+8*count
            return values
        if tag == _TUPLE:
            count = _U32.unpack_from(view, position)[0]
            position += 4
            return tuple(take() for _ in range(count))
        if tag == _FIELDS:
            count = _U32.unpack_from(view, position)[0]
            position += 4
            entries = tuple((take(), take()) for _ in range(count))
            return frozen_fields._from_frozen_entries(entries)
        if tag == _DATACLASS:
            type_id = _U16.unpack_from(view, position)[0]
            position += 2
            if type_id >= len(layouts):
                raise FrameCodecError(f"unknown frame type id {type_id}")
            cls, names = layouts[type_id]
            instance = new(cls)
            for name in names:
                set_field(instance, name, take())
            return instance
        if tag == _PROXY:
            count = _U32.unpack_from(view, position)[0]
            position += 4
            items = {}
            for _ in range(count):
                key = take()
                items[key] = take()
            return _MAPPING_PROXY(items)
        if tag == _ARRAY:
            import numpy as np
            length = _U16.unpack_from(view, position)[0]
            dtype = bytes(view[position+2:position+2+length]).decode("ascii")
            position += 2+length
            ndim = _U16.unpack_from(view, position)[0]
            shape = tuple(_I64.unpack_from(view, position+2+8*axis)[0] for axis in range(ndim))
            position += 2+8*ndim
            size = _U32.unpack_from(view, position)[0]
            array = np.frombuffer(bytes(view[position+4:position+4+size]), dtype=np.dtype(dtype)).reshape(shape)
            position += 4+size
            return array             # read-only, as the frame's own (never mutated)
        raise FrameCodecError(f"unknown tag {tag}")

    frame = take()
    if position != len(view):
        raise FrameCodecError("trailing bytes after the frame")
    return frame
