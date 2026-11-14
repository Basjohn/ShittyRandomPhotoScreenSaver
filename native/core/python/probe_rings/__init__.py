"""Probe Rings: the harness-only mode of N2.9's proof (Current_Plan.md item 8b; ``native/core/src/mode_content.h``).

A Visualizer mode drawn by the native core from data alone, as every new mode is built there: a Python simulation, a
schema, two fragment shaders and a spec. It is never registered (no ``MODE_CODES`` entry, no registry descriptor, no
Settings body, no preset): only ``native/core/python/generic_mode_check.py`` and its tests draw it.

- The simulation (:class:`RingsSimulation`): rings spawned on the level's upward crossings, growing with time and level,
  fading as they grow; one frame record per step.
- The schema (:data:`SCHEMA`): the record's fixed layout (``native_schema.NativeLayout``), its range rule on
  ``ring_count``. Its mode code (:data:`MODE_CODE`) lies outside the product's table, so nothing of it can reach a
  product stream.
- The shaders (``rings.frag``, ``glow.frag``): each pass declares ``ModeSettings`` (from :func:`resolve_settings`) and
  ``ModeFrame`` (members named as the record's fields); the rings pass blends ``alpha``, the glow pass ``add``.
- The spec (:data:`SPEC`): ordinary spec controls (``core.settings.visualizer_mode_settings``) with their defaults
  (:data:`DEFAULTS`), resolved to the shaders' settings by name (:data:`SETTING_UNIFORMS`).

Variants for the proof that a change needs no module build: :func:`shader_variant` (a shader change; with
``tint=True`` it adds a ModeSettings member), :data:`TINT_SPEC` and :data:`TINT_DEFAULTS` (the spec change that fills
it), and ``RingsSimulation(speed=...)`` (a simulation change).
"""
from __future__ import annotations

import colorsys
import math
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
MODE_ID = "probe_rings"
#: Outside ``packet_abi.MODE_CODES`` (append-only from 1; a test holds it out): never a product mode's code.
MODE_CODE = 254
VERSION = 1
MAX_RINGS = 8
#: The largest radius a ring reaches, in units of half the card's shorter side; it has faded out there.
MAX_RADIUS = 1.4
PASSES = (("rings", "rings.frag", "alpha"), ("glow", "glow.frag", "add"))


# ----------------------------------------------------------------------------------------------------- the schema

def _schema():
    from core.visualizer_engine.native_schema import NativeLayout, NativeSchema

    @dataclass(frozen=True, slots=True)
    class HarnessSchema(NativeSchema):
        """A ``NativeSchema`` whose mode code is its own, not ``MODE_CODES``' (the mode is never registered)."""

        code: int = 0

        @property
        def mode_code(self) -> int:
            return self.code

    entries = (("rings", "f64", MAX_RINGS), ("ring_alpha", "f64", MAX_RINGS), ("ring_count", "u32", 1),
               ("level", "f64", 1), ("time", "f64", 1), ("pulse_color", "f64x4", 1))
    layout = NativeLayout.build(entries)
    names = tuple(name for name, _kind, _count in entries)
    checks = (("ring_count", "at_most", MAX_RINGS),)
    holder: dict[str, Any] = {}

    def encode(values: Mapping[str, Any]) -> bytes:
        return layout.pack(holder["schema"].schema_id, values)

    def decode(payload: bytes) -> dict:
        from core.visualizer_engine.native_schema import PayloadRefused, validate_record_head

        schema = holder["schema"]
        validate_record_head(payload, schema)
        values = layout.unpack(payload)
        if values["ring_count"] > MAX_RINGS:
            raise PayloadRefused("record", f"ring_count is {values['ring_count']}, outside its rule")
        return {name: values[name] for name in names}

    schema = HarnessSchema(mode_id=MODE_ID, version=VERSION, layout=layout, encode=encode, decode=decode,
                           fields=names, checks=checks, code=MODE_CODE)
    holder["schema"] = schema
    return schema


SCHEMA = _schema()


# ------------------------------------------------------------------------------------------------- the simulation

def harness_level(t: float) -> float:
    """The scripted level: a kick of 1.5 per second with a softer off-beat (no audio in a harness)."""
    kick = max(0.0, math.sin(2.0 * math.pi * 1.5 * t)) ** 4
    off = 0.35 * max(0.0, math.sin(2.0 * math.pi * 3.0 * t + 1.0)) ** 6
    return min(1.0, kick + off)


class RingsSimulation:
    """Rings spawned when the level rises through ``spawn_level``, growing at ``speed`` (radius units a second, faster
    with the level) and fading as they grow; at most ``MAX_RINGS``, the oldest dropped first."""

    def __init__(self, *, speed: float = 0.35, spawn_level: float = 0.6) -> None:
        self.speed = float(speed)
        self.spawn_level = float(spawn_level)
        self.rings: list[float] = []
        self.time = 0.0
        self.level = 0.0

    def step(self, dt: float) -> dict:
        """Advance by ``dt`` seconds; the frame's record values."""
        self.time += float(dt)
        level = harness_level(self.time)
        if level >= self.spawn_level > self.level:
            self.rings.insert(0, 0.0)
        self.level = level
        grown = [r + self.speed * dt * (1.0 + level) for r in self.rings]
        self.rings = [r for r in grown if r < MAX_RADIUS][:MAX_RINGS]
        return self.values()

    def values(self) -> dict:
        count = len(self.rings)
        rings = self.rings + [0.0] * (MAX_RINGS - count)
        alpha = [max(0.0, 1.0 - r / MAX_RADIUS) if i < count else 0.0 for i, r in enumerate(rings)]
        r, g, b = colorsys.hsv_to_rgb((0.55 + 0.05 * self.time) % 1.0, 0.6, 1.0)
        return {"rings": tuple(rings), "ring_alpha": tuple(alpha), "ring_count": count, "level": self.level,
                "time": self.time, "pulse_color": (r, g, b, 1.0)}


def record(values: Mapping[str, Any]) -> bytes:
    return SCHEMA.encode(values)


# ------------------------------------------------------------------------------------------------------- the spec

def _spec():
    from core.settings.visualizer_mode_settings import Bucket, Colour, ModeSettings, Slider

    look = Bucket("look", "Look")
    return ModeSettings(MODE_ID, (look,), (
        Colour(f"{MODE_ID}_color", "Ring Colour:", "Ring Colour", bucket="look"),
        Slider(f"{MODE_ID}_thickness", "Thickness:", 1.0, 12.0, bucket="look", decimals=1, suffix=" px"),
        Slider(f"{MODE_ID}_glow", "Glow:", 0.0, 1.0, bucket="look", percent=True),
    ))


def _tint_spec():
    from core.settings.visualizer_mode_settings import Colour, ModeSettings

    return ModeSettings(MODE_ID, SPEC.buckets, (*SPEC.entries,
                                                Colour(f"{MODE_ID}_tint", "Tint:", "Tint", bucket="look")))


SPEC = _spec()
DEFAULTS = {f"{MODE_ID}_color": [120, 220, 255, 255], f"{MODE_ID}_thickness": 3.0, f"{MODE_ID}_glow": 0.6}
#: The spec change of the proof: one control more (its shader member comes with ``shader_variant(tint=True)``).
TINT_SPEC = _tint_spec()
TINT_DEFAULTS = {**DEFAULTS, f"{MODE_ID}_tint": [0, 255, 0, 255]}
#: Spec key -> the ModeSettings member it fills.
SETTING_UNIFORMS = {f"{MODE_ID}_color": "u_ring_color", f"{MODE_ID}_thickness": "u_thickness_px",
                    f"{MODE_ID}_glow": "u_glow", f"{MODE_ID}_tint": "u_tint"}


def resolve_settings(stored: Mapping[str, Any], *, target_px: tuple[int, int], dpr: float, fade: float = 1.0,
                     spec=None, defaults: Mapping[str, Any] | None = None) -> dict:
    """Every ModeSettings member by name: each spec control's admitted value (colours 0-1, thickness in device
    pixels), and the card's (``u_target_px``, ``u_fade``)."""
    spec = SPEC if spec is None else spec
    defaults = DEFAULTS if defaults is None else defaults
    values: dict[str, Any] = {"u_target_px": [float(target_px[0]), float(target_px[1])], "u_fade": float(fade)}
    for control in spec.controls:
        admitted = control.admit(stored.get(control.key, defaults[control.key]), defaults[control.key])
        member = SETTING_UNIFORMS[control.key]
        if isinstance(admitted, list):
            values[member] = [channel / 255.0 for channel in admitted]
        elif control.key.endswith("_thickness"):
            values[member] = float(admitted) * float(dpr)
        else:
            values[member] = float(admitted)
    return values


# ---------------------------------------------------------------------------------------------------- the shaders

TINT_MEMBER = "    vec4 u_tint;         // the proof's spec change: a member the base spec does not fill\n"
TINT_LINE = "    rgb *= u_tint.rgb;\n"


def shader_text(filename: str) -> str:
    return (HERE / filename).read_text(encoding="utf-8")


def shader_variant(*, tint: bool = False, green: bool = False) -> str:
    """``rings.frag`` changed: ``tint`` adds the ModeSettings member ``u_tint`` (multiplied into the colour); ``green``
    draws the rings green (a change with no new member)."""
    text = shader_text("rings.frag")
    if tint:
        anchor = "    float u_fade;\n"
        assert text.count(anchor) == 1 and text.count("    //@colour\n") == 1
        text = text.replace(anchor, anchor + TINT_MEMBER).replace("    //@colour\n", TINT_LINE)
    if green:
        assert text.count("    //@colour\n") <= 1
        text = text.replace("    //@colour\n", "    rgb = vec3(0.0, 1.0, 0.0);\n")
    return text


def bake(text: str, name: str, folder: Path) -> bytes:
    """``text`` baked by ``tools/regen_qrc.py``'s own baker for every shipped target (the conventions spliced at its
    marker), in ``folder``: no module build."""
    from tools import regen_qrc

    source = Path(folder) / name
    source.write_text(text, encoding="utf-8")
    pack = source.with_name(name + ".qsb")
    regen_qrc._bake_quick_shader(regen_qrc.quick_shader_baker(sys.executable), source, pack,
                                 regen_qrc.quick_shader_targets(), subprocess.run)
    return pack.read_bytes()


def passes(folder: Path, *, rings_text: str | None = None, only: tuple[str, ...] | None = None):
    """The program's passes (``rendering.native.mode.ModePass``), baked into ``folder``; ``rings_text`` replaces
    ``rings.frag``; ``only`` keeps the named passes (the per-pass GPU time)."""
    from rendering.native.mode import ModePass

    built = []
    for name, filename, blend in PASSES:
        if only is not None and name not in only:
            continue
        text = rings_text if (name == "rings" and rings_text is not None) else shader_text(filename)
        built.append(ModePass(name, bake(text, filename, folder), blend))
    return tuple(built)


__all__ = ["DEFAULTS", "MAX_RADIUS", "MAX_RINGS", "MODE_CODE", "MODE_ID", "PASSES", "RingsSimulation", "SCHEMA",
           "SETTING_UNIFORMS", "SPEC", "TINT_DEFAULTS", "TINT_SPEC", "bake", "harness_level", "passes", "record",
           "resolve_settings", "shader_text", "shader_variant"]
