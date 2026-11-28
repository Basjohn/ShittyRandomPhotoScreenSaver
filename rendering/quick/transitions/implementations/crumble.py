"""Lazy closed-solid Crumble renderer with static instanced debris."""

from __future__ import annotations
from rendering.gl_programs.crumble_program import (
    CRUMBLE_CHIP_VERTICES,
    CRUMBLE_FRAGMENT,
    CRUMBLE_GHOST_FRAGMENT,
    CRUMBLE_MOTION_FRAGMENT,
    CRUMBLE_MOTION_VERTEX,
    CRUMBLE_VERTEX,
    DEBRIS_FRAGMENT,
    DEBRIS_GHOST_FRAGMENT,
    DEBRIS_MOTION_FRAGMENT,
    DEBRIS_MOTION_VERTEX,
    DEBRIS_VERTEX,
)
from ..crumble_dynamics import MOTION_FRAMES
from rendering.gl_programs.scene3d import scene3d_request_samples, scene3d_shutter_progress, scene3d_trail_ghosts
from rendering.quick.scene3d.resources import UNDERLAY_PROGRAM, pack_floats
from ..native_scene import (TRAIL_EDGES_PASS, NativeScene, NativeSceneMesh, NativeScenePass, NativeScenePasses,
                            NativeSceneTexture, eased_show, ghost_values, item_quad_pass, native_clip_depth)
from ..run_geometry import (
    CRUMBLE_CHUNK_ATTRIBUTES,
    PREPARED_GEOMETRY,
    CrumbleGeometry,
    build_crumble_geometry,
    crumble_geometry_key,
    crumble_parameters,
)


# N5.2d: the native scene's passes (their texts the ones this renderer compiles, each vertex stage with its native clip
# depth); the chunks' and the chips' meshes by name. Chunks read the old picture and the motion table (nearest).
_CHUNK_INPUTS = tuple(zip(("aUv", "aCenter", "aZ", "aNormal", "aInset", "aFace", "aVariation", "aRadius", "aCrack",
                           "aRelease", "aAxis"), CRUMBLE_CHUNK_ATTRIBUTES))
_CHIP_INPUTS = (("aPosition", 3), ("aNormal", 3))
_CHIP_INSTANCE_INPUTS = (("aEdge", 2), ("aParent", 2), ("aMeta", 2), ("aRelease", 2))
_NATIVE_CHUNK_SAMPLERS = (("uOldTex", "old"), ("uMotion", "motion"))
_SCENE_PASSES = (
    item_quad_pass("underlay", UNDERLAY_PROGRAM[1], UNDERLAY_PROGRAM[2], (("uImage", "new"),)),
    NativeScenePass("chunks_ghost", native_clip_depth(CRUMBLE_MOTION_VERTEX), CRUMBLE_GHOST_FRAGMENT, mesh="chunks",
                    samplers=_NATIVE_CHUNK_SAMPLERS, target="ghosts"),
    NativeScenePass("debris_ghost", native_clip_depth(DEBRIS_MOTION_VERTEX), DEBRIS_GHOST_FRAGMENT, mesh="chips",
                    instances="mesh", target="ghosts"),
    TRAIL_EDGES_PASS,
    NativeScenePass("chunks", native_clip_depth(CRUMBLE_VERTEX), CRUMBLE_FRAGMENT, mesh="chunks",
                    samplers=_NATIVE_CHUNK_SAMPLERS, depth=True),
    NativeScenePass("chunks_motion", native_clip_depth(CRUMBLE_MOTION_VERTEX), CRUMBLE_MOTION_FRAGMENT, mesh="chunks",
                    samplers=_NATIVE_CHUNK_SAMPLERS, depth=True, moves=True),
    NativeScenePass("debris", native_clip_depth(DEBRIS_VERTEX), DEBRIS_FRAGMENT, mesh="chips", instances="mesh",
                    depth=True),
    NativeScenePass("debris_motion", native_clip_depth(DEBRIS_MOTION_VERTEX), DEBRIS_MOTION_FRAGMENT, mesh="chips",
                    instances="mesh", depth=True, moves=True),
)


def _scene_pass(name: str) -> NativeScenePass:
    return next(p for p in _SCENE_PASSES if p.name == name)


def _progress(sample) -> float:
    return max(0.0, min(1.0, float(sample.eased_progress)))


def _run_geometry(run, logical_size: tuple[float, float]) -> CrumbleGeometry:
    """The run's prepared geometry (COMPUTE's, ``prepare_run_geometry``; built here when it has not prepared it)."""
    key = crumble_geometry_key(run.request.parameter_dict(), logical_size[0] / logical_size[1])
    return PREPARED_GEOMETRY.get_or_build(key, build_crumble_geometry)


class QuickCrumbleRenderer(NativeScenePasses):
    transition_id = "crumble"
    scene_pixels = True                  # N5.2d: its motion reads the item's device pixels (uViewport)

    # ------------------------------------------------------------------------------- N5.2d: the scene, one owner

    @classmethod
    def native_scene_passes(cls) -> tuple[NativeScenePass, ...]:
        return _SCENE_PASSES

    def native_scene(self, run, logical_size: tuple[float, float]) -> NativeScene:
        parameters = run.request.parameter_dict()
        debris = crumble_parameters(parameters)[6]
        geometry = _run_geometry(run, logical_size)
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        samples = scene3d_request_samples(parameters) or (1 if motion or trails else 0)
        chips = debris > 0.0 and bool(geometry.debris)
        names = ["underlay"]
        if trails:                       # _draw_scene: the ghosts (MAX into their buffer) and their edges first
            names += ["chunks_ghost"] + (["debris_ghost"] if chips else []) + [TRAIL_EDGES_PASS.name]
        names += ["chunks_motion" if motion else "chunks"]
        if chips:
            names += ["debris_motion" if motion else "debris"]
        meshes = [NativeSceneMesh("chunks", bytes(geometry.chunks), _CHUNK_INPUTS)]
        if chips:
            meshes.append(NativeSceneMesh("chips", pack_floats(CRUMBLE_CHIP_VERTICES), _CHIP_INPUTS,
                                          bytes(geometry.debris), _CHIP_INSTANCE_INPUTS))
        table = NativeSceneTexture("motion", bytes(geometry.motion), (MOTION_FRAMES, geometry.chunk_count))
        return NativeScene(tuple(map(_scene_pass, names)), tuple(meshes), samples, False, motion=motion,
                           trails=trails, textures=(table,))

    def scene_show(self, run, sample) -> int:
        return eased_show(_progress(sample))

    def scene_values(self, run, sample, logical_size: tuple[float, float],
                     pixels: tuple[int, int] | None = None) -> dict[str, object]:
        """The chunks' and chips' values for the frame (``render``'s, one owner): their time, and with motion blur
        their time one shutter ago; with trails each ghost's time and fade (``<member>@<pass>_<k>``)."""
        parameters = run.request.parameter_dict()
        seed, _pieces, _complexity, _weight, depth, thickness, debris = crumble_parameters(parameters)
        progress = _progress(sample)
        motion = bool(parameters.get("motion_blur", False))
        trails = bool(parameters.get("motion_trails", False))
        values: dict[str, object] = {"uProgress": progress, "uDepth": depth, "uThickness": thickness, "uSeed": seed,
                                     "uMotionFrames": float(MOTION_FRAMES)}
        if debris > 0.0:
            values["uDebris"] = debris
        if motion or trails:
            width, height = pixels if pixels is not None else logical_size
            values["uViewport"] = (float(width), float(height))
        chips = ("debris",) if debris > 0.0 else ()
        if motion:
            values["uProgressBefore"] = max(progress - scene3d_shutter_progress(run.request.duration_ms), 0.0)
            for name in ("chunks", *chips):         # the shared motion blocks' ghost member, read by no stage here
                values[f"uGhostFade@{name}_motion"] = 0.0
        if trails:
            ghosts = scene3d_trail_ghosts(progress, run.request.duration_ms)
            for name in (f"{piece}_ghost" for piece in ("chunks", *chips)):
                values.update(ghost_values(name, ghosts, "uProgress", lambda time: {"uProgress": time}, progress))
        return values

    # The old picture bind_frame binds (unit 0; the motion table is bound on unit 1 here); every other value is in
    # the programs' pass blocks.
    _CHUNK_SAMPLERS = ("uOldTex",)


def create_transition_renderer() -> QuickCrumbleRenderer:
    return QuickCrumbleRenderer()
