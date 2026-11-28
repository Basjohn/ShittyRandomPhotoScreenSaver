"""Extruded Bubble's native program (Current_Plan.md N5.6, "Native record and route"): the Python renderer's frame
(``rendering/quick/visualizer/implementations/extruded_bubble.py``, ``QuickExtrudedBubbleRenderer.render``) as one
declared program of the generic mode, drawn from its packs (``extruded_bubble_shaders``, ``extruded_bubble_drift``).

In the renderer's order:

1. **Drift.** Each family's three entries (``extruded_bubble_drift``: the rebase's old steps, the main dispatch, the
   header mark) on the record's trigger ``drift_last_step``, into the one output the beads and specks read
   (``drift_out``, every family at its own offset). The renderer's warm-up pair check is a diagnostic with no drawn
   effect (it only logs whether the device keeps the pair arithmetic exact) and stays out of the product program.
2. **Probe.** Each cube face: the water and light (``probe_backdrop``), then the glints added (``proxies``, while the
   record has any), then the core's prefilter (``probe.py``'s cone chain). The cube has no depth: the Python face's
   depth test only orders the glints against the backdrop's far plane (NDC 0.9999), which the glints always pass.
3. **Shafts.** The half-resolution march into ``shafts_a``, the separable blur through ``shafts_b`` back into it.
4. **Scene.** The backdrop (emission added) and the specks (light added, while the record has any), the background
   capture, the transparent glass (shells, clusters, beads with snow and fizz, the wake trails) resolved onto the
   scene, the near layer's bubbles defocused onto it (while the record has a shell or a cluster), the emission's
   bloom and the overlay composite with the glow, tone mapped at the scene's exposure, in the content's orientation
   with OpenGL's rows (every pass draws the Python text's own clip space, as Waveform's).

Every count is the record's (a pass with no instances draws nothing, Python's ``if count:``); the explicit sizes
(the cube's face, the shafts' half resolution) are ``target_sizes``'.
"""
from __future__ import annotations

from typing import Any

#: The targets.
PROBE, SHAFTS_A, SHAFTS_B, SCENE, GLASS, NEAR = "probe", "shafts_a", "shafts_b", "scene", "glass", "near"
#: The storage the drift entries write and the draws read: its one output.
DRIFT_OUT = "drift_out"
#: The record's instance streams: (stream, its count field, its layout's attributes as (name, components)).
INSTANCE_STREAMS = {
    "shells": (("aSphere", 4), ("aExtra", 2), ("aOpacity", 1), ("aLensRadius", 1)),
    "clusters": (("aS0", 4), ("aS1", 4), ("aS2", 4), ("aInfo", 4), ("aAlphas", 3)),
    "proxies": (("aPoint", 4), ("aLook", 4)),
}
#: The record's storage streams (bound by block name).
STORAGE_STREAMS = ("wakes", "drift_steps")
#: Each drift family's geometry family id in the D3 key (``DriftRecordProjector``: ``FAMILIES``' order).
_CLOUD_GROUP = 256


def used_field(stream: str) -> str:
    """The record field holding a stream's used floats."""
    return f"{stream}_floats"


def _layout(stream: str):
    from rendering.native.mode import MeshAttribute, RecordLayout

    attributes, offset = [], 0
    for name, components in INSTANCE_STREAMS[stream]:
        attributes.append(MeshAttribute(name, components, offset))
        offset += 4 * components
    return RecordLayout(offset, tuple(attributes))


def buffer_bytes() -> dict[str, int]:
    """Each drift storage buffer's bytes at its family's canonical maximum (``frame_capacity``: the arena's own
    maxima, which no capacity passes), so no buffer is resized under a dispatch: every family's state and auxiliary
    rows (``DriftSolver._allocate``) and the output at its largest layout (``DriftSolver._relayout``)."""
    from core.constants.extruded_bubble_world import SNOW_FULL, SPECKS_FULL
    from widgets.spotify_visualizer.extruded_bubble_material_paths import CHAIN_PATHS, PATH_NODES

    capacity = {"chains": CHAIN_PATHS, "snow": SNOW_FULL, "specks": SPECKS_FULL}
    sizes = {"chains_state": 16 * CHAIN_PATHS * PATH_NODES, "chains_aux": 16 * CHAIN_PATHS}
    for family in ("snow", "specks"):
        sizes[f"{family}_state"] = sizes[f"{family}_aux"] = 16 * capacity[family]
    total = CHAIN_PATHS * PATH_NODES + SNOW_FULL + SPECKS_FULL
    sizes[DRIFT_OUT] = 16 * max(256, 1 << (total - 1).bit_length())
    for family in ("chains", "snow", "specks"):
        sizes[f"{family}_header"] = 32
    return sizes


def _drift_passes(pack) -> tuple[list, list]:
    """The drift entries and their buffers (``extruded_bubble_drift``)."""
    from rendering.native.mode import ComputeBinding, ComputePass, GeometryBuffer, StorageBuffer
    from widgets.spotify_visualizer.extruded_bubble_drift_log import FAMILIES

    sizes = buffer_bytes()
    buffers = [StorageBuffer(name, size) for name, size in sizes.items()]
    passes = []
    for family_id, family in enumerate(FAMILIES):
        buffers.append(GeometryBuffer(f"{family}_geometry", family_id, f"{family}_geometry_key"))
        chains = family == "chains"
        state, aux = ("Knots", "Paths") if chains else ("Motes", "Bases")
        groups = (f"{family}_groups", 1, 1)

        def entry(suffix, geometry, old_geometry):
            return ComputePass(
                f"drift_{family}{suffix}", pack(f"eb_drift_{family}{suffix}.comp"), groups=groups,
                trigger="drift_last_step",
                bindings=(ComputeBinding("DriftSteps", "drift_steps", "stream"),
                          ComputeBinding("Geometry", geometry),
                          ComputeBinding("OldGeometry", old_geometry),
                          ComputeBinding(state, f"{family}_state", access="read_write"),
                          ComputeBinding(aux, f"{family}_aux", access="read_write"),
                          ComputeBinding("Out", DRIFT_OUT, access="write"),
                          ComputeBinding("DriftHeader", f"{family}_header")))

        current, previous = f"{family}_geometry", f"{family}_geometry@previous"
        # The rebase's old steps run on the old rows (the previous key's); its OldGeometry is unread there
        # (``uRebase`` 0), bound to the current rows so the entry is held while either key is not resident.
        passes += [entry("_before", previous, current), entry("", current, previous),
                   ComputePass(f"drift_{family}_mark", pack(f"eb_drift_{family}_mark.comp"), groups=(1, 1, 1),
                               trigger="drift_last_step",
                               bindings=(ComputeBinding("DriftSteps", "drift_steps", "stream"),
                                         ComputeBinding("Geometry", current),
                                         ComputeBinding("DriftHeader", f"{family}_header", access="read_write")))]
    return passes, buffers


def program(variant: tuple) -> dict:
    """The program for ``variant`` (``variant_of``: the scene's samples)."""
    from rendering.gl_programs.extruded_bubble_program import TRAIL_SEGMENTS
    from rendering.native.extruded_bubble_shaders import pack
    from rendering.native.mode import (
        BlendState, BloomStep, CapturePass, CompositeStep, DefocusStep, ModePass, ModeStream, ModeTarget,
        PassGeometry, PassOutput, PassSampler, PrefilterStep, TargetAttachment, TransparencyResolve,
        TransparencyTarget,
    )

    (samples,) = variant

    def qsb(name):
        return pack(name)

    light = BlendState(("add", "one", "one"), ("add", "zero", "one"))      # rgb ONE, ONE; alpha ZERO, ONE
    maximum = BlendState(("max", "one", "one"), ("max", "one", "one"))
    # Replace declared as an enabled blend (ONE, ZERO): on OpenGL an attachment with blending off beside a blended one
    # drew blended with the funcs the previous pipeline left (the light blend's alpha ZERO, ONE), so the backdrop's
    # alpha stayed the cleared 0 and the scene composed as glass over nothing (28 Nov, R-256).
    replace = BlendState(("add", "one", "zero"), ("add", "one", "zero"))
    linear = dict(filter="linear", wrap="clamp")
    background = PassSampler("uBackground", f"{SCENE}.capture_colour", **linear)
    probe = PassSampler("uProbe", f"{PROBE}.colour", "linear", "clamp", "linear")

    def full(program_key):
        return PassGeometry(qsb(f"eb_{program_key}.vert"), vertices=3)

    def quads(program_key, **counts):
        return PassGeometry(qsb(f"eb_{program_key}.vert"), topology="triangle_strip", vertices=4, **counts)

    passes, buffers = _drift_passes(qsb)
    for face in range(6):
        passes += [ModePass(f"probe_backdrop_f{face}", qsb("eb_probe_backdrop.frag"), "replace", target=PROBE,
                            face=face, geometry=full("probe_backdrop")),
                   ModePass(f"proxies_f{face}", qsb("eb_proxies.frag"), light, target=PROBE, face=face,
                            geometry=quads("proxies", instance_from="proxies"))]
    passes.append(PrefilterStep("probe_prefilter", PROBE))
    passes += [ModePass("shafts", qsb("eb_shafts.frag"), "replace", target=SHAFTS_A, geometry=full("shafts")),
               ModePass("blur_x", qsb("eb_blur.frag"), "replace", target=SHAFTS_B, geometry=full("blur"),
                        samplers=(PassSampler("uSource", f"{SHAFTS_A}.colour", **linear),)),
               ModePass("blur_y", qsb("eb_blur.frag"), "replace", target=SHAFTS_A, geometry=full("blur"),
                        samplers=(PassSampler("uSource", f"{SHAFTS_B}.colour", **linear),))]
    # The scene: colour replaced and emission added (``SceneTarget.emission_writes``); the scope leaves the depth test
    # off, so neither the backdrop nor the specks write depth.
    passes += [ModePass("backdrop", qsb("eb_backdrop.frag"), "replace", target=SCENE,
                        outputs=(PassOutput(True, replace), PassOutput(True, "additive")), geometry=full("backdrop"),
                        samplers=(PassSampler("uShafts", f"{SHAFTS_A}.colour", **linear),)),
               ModePass("specks", qsb("eb_specks.frag"), light, target=SCENE,
                        outputs=(PassOutput(True, light), PassOutput(True, "additive")),
                        geometry=PassGeometry(qsb("eb_specks.vert"), topology="triangle_strip", vertices=4,
                                              instances="speck_count",
                                              storage=(("EbMaterialDrift", DRIFT_OUT),))),
               CapturePass("background", SCENE)]
    glass = (PassOutput(True), PassOutput(True), PassOutput(True, "additive"))

    def transparent(name, geometry, samplers):
        return ModePass(name, qsb(f"eb_{name}.frag"), "additive", target=GLASS, outputs=glass, depth_test="less",
                        samplers=samplers, geometry=geometry, sorted_pack=qsb(f"eb_{name}_sorted.frag"))

    passes += [transparent("shells", quads("shells", instance_from="shells"), (background, probe)),
               transparent("clusters", quads("clusters", instance_from="clusters"), (background, probe)),
               transparent("beads", PassGeometry(qsb("eb_beads.vert"), topology="triangle_strip", vertices=4,
                                                 instances="bead_instances",
                                                 storage=(("EbMaterialDrift", DRIFT_OUT), ("EbWakes", "wakes"))),
                           (background, probe)),
               transparent("trails", PassGeometry(qsb("eb_trails.vert"), topology="triangle_strip",
                                                  vertices=2 * (TRAIL_SEGMENTS + 1), instances="trail_instances",
                                                  storage=(("EbWakes", "wakes"),)), (background,)),
               TransparencyResolve("glass_resolve", GLASS)]
    near = (PassOutput(True, "premultiplied"), PassOutput(True, maximum))
    passes += [ModePass("near", qsb("eb_near.frag"), "premultiplied", target=NEAR, outputs=near,
                        samplers=(background, probe), geometry=quads("near", instance_from="shells")),
               ModePass("near_clusters", qsb("eb_near_clusters.frag"), "premultiplied", target=NEAR, outputs=near,
                        samplers=(background, probe), geometry=quads("near_clusters", instance_from="clusters")),
               DefocusStep("near_defocus", NEAR, SCENE, when="near_layer"),
               BloomStep("scene_bloom", f"{SCENE}.emission"),
               CompositeStep("scene_show", "overlay_glow", f"{SCENE}.colour", "scene_bloom.glow",
                             scene_frame="oriented", scene_rows="up")]
    one = (1, 1)
    targets = [
        ModeTarget(PROBE, (TargetAttachment("colour", "rgba16f", clear=(0.0, 0.0, 0.0, 1.0)),), size=one,
                   allocation="exact", cube=True),
        ModeTarget(SHAFTS_A, (TargetAttachment("colour", "r16f"),), size=one, allocation="exact"),
        ModeTarget(SHAFTS_B, (TargetAttachment("colour", "r16f"),), size=one, allocation="exact"),
        ModeTarget(SCENE, (TargetAttachment("colour", "rgba16f"), TargetAttachment("emission", "rgba16f")),
                   depth=True, samples=int(samples)),
        TransparencyTarget(GLASS, SCENE, borrow=("emission",)),
        ModeTarget(NEAR, (TargetAttachment("colour", "rgba16f"), TargetAttachment("circle", "rgba16f")), mips=True),
    ]
    streams = [ModeStream(name, name, "instance", _layout(name), used=used_field(name)) for name in INSTANCE_STREAMS]
    streams += [ModeStream("wakes", "wakes", "storage", used=used_field("wakes")),
                # The drift window (``pack_drift_stream``), the record's ``drift_stream`` field.
                ModeStream("drift_steps", "drift_stream", "storage", used="drift_stream_used")]
    # The window's first serial travels for the route's own checks (``DriftRecordProjector``); no pass reads it.
    return {"passes": passes, "targets": targets, "streams": streams, "buffers": buffers,
            "unread": ["drift_first_step"]}


def variant_of(snapshot: Any) -> tuple:
    """The program variant of the drawn snapshot: its scene's samples (the tier's, ``_scene_samples``)."""
    from rendering.quick.visualizer.implementations.extruded_bubble import _scene_samples

    return (int(_scene_samples(snapshot.logical.mode_state.parameters)),)


def target_sizes(snapshot: Any, settings: dict | None = None) -> dict:
    """The explicit sizes: the cube's face (the tier's ``_PROBE_SIZE``) and the shafts' half resolution of the card's
    oriented content (``_ShaftTargets.warm``)."""
    from rendering.gl_programs.scene3d import scene3d_detail
    from rendering.native.extruded_bubble_values import card_geometry
    from rendering.quick.visualizer.implementation_values import parameter
    from rendering.quick.visualizer.implementations.extruded_bubble import _PROBE_SIZE

    side = int(_PROBE_SIZE[scene3d_detail(parameter(snapshot.logical.mode_state.parameters,
                                                    "scene3d_detail")).name])
    shafts = card_geometry(snapshot.presentation)["shafts"]
    return {PROBE: (side, side), SHAFTS_A: shafts, SHAFTS_B: shafts}


__all__ = ["DRIFT_OUT", "INSTANCE_STREAMS", "STORAGE_STREAMS", "buffer_bytes", "program", "target_sizes",
           "used_field", "variant_of"]
