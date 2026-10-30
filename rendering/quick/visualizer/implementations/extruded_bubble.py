"""Extruded Bubble's Qt Quick renderer: an underwater scene of traced glass bubbles in its card.

The composition lab's proven passes (``tools/labs/extruded_bubble_lab.py``; ``Extruded_Bubble/Target.md`` section
10) on the shared Scene3D owners, with the lab's own programs (``extruded_bubble_program``) and the scene mapping
from Settings (``extruded_bubble_scene``). Each frame:

1. **Probe.** The water and light all round the eye into the shared ``SceneProbe`` (what every bubble's wall
   mirrors), with each bubble's glint as a bright proxy point so bubbles sparkle in one another.
2. **Shafts.** The volumetric light at half the card's resolution, then a separable blur (two owned R16F targets).
3. **Scene.** Through the card's ``SceneTarget`` (overlay, HDR with bloom, depth texture, background capture,
   order-independent transparency): the water and shafts, then the simulation's bubbles and fused clusters as traced
   shells over the captured background, then close-enough ordinary large shells through the shared ``DefocusLayer`` (no synthetic near cohort).

The simulation (``ExtrudedBubbleFrame``) owns all ordinary bubbles; none attach to the lens.
Bead chains, marine snow and fizz wakes are GPU-procedural (``BEAD_VERTEX``). Motion reads the logical
``travel``; wake emitters and their retirement lifetimes are tracked by stable identity in that same
simulation, frozen into the snapshot and uploaded separately from the compacted visible-shell buffer.
Instance data goes up in
fixed-capacity buffers (``glNamedBufferSubData``, a few KB a frame); uniforms are uploaded only when they change.
"""
from __future__ import annotations

import ctypes
import math
from functools import lru_cache

import numpy as np
from OpenGL import GL as gl

from rendering.gl_programs.extruded_bubble_program import (
    BACKDROP_FRAGMENT, BEAD_VERTEX, BLUR_FRAGMENT, BUBBLE_FRAGMENT, BUBBLE_VERTEX, CLUSTER_FRAGMENT, CLUSTER_VERTEX, FULL_VERTEX,
    NEAR_FRAGMENT, NEAR_CLUSTER_FRAGMENT, PARTICLE_FRAGMENT, PARTICLE_VERTEX, SHAFT_FRAGMENT, SPECK_VERTEX,
    TRAIL_FRAGMENT, TRAIL_SEGMENTS, TRAIL_VERTEX,
)
from core.constants.extruded_bubble_world import WAKE_STRIDE, SNOW_FULL
from rendering.gl_programs.extruded_bubble_scene import (
    CLUSTER_FLOATS, PROXY_FLOATS, SHELL_FLOATS, SURFACE_Y, bubble_instances, camera,
    SPECKS_FULL, cluster_instances, wake_instances, physical_camera, speck_amount,
    glint_proxies, light_on_screen, ray_motion, ray_strength, scene_knobs, screen_streak,
)
from core.settings.visualizer_paths import admit_path, world_point
from rendering.gl_programs.scene3d import scene3d_detail
from rendering.quick import gl_query
from rendering.quick.scene3d.defocus import DefocusLayer
from rendering.quick.scene3d.frame import item_pixel_rect
from rendering.quick.scene3d.probe import SceneProbe
from rendering.quick.scene3d.resources import MeshResources, warm_programs
from rendering.quick.scene3d.target import SceneTarget, scene_target_programs
from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame
from widgets.spotify_visualizer.extruded_bubble_simulation import MAX_BUBBLES, idle_activity as _idle_activity
from widgets.spotify_visualizer.extruded_bubble_material_paths import CHAINS_PER_STEP
from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale
from widgets.spotify_visualizer.extruded_bubble_geometry import WORLD_CENTER, WORLD_HALF, WORLD_UNIT, stream_basis
from widgets.spotify_visualizer.render_state import ExtrudedBubbleFrame

from ..implementation_values import parameter

_PROGRAMS = (
    ("backdrop", FULL_VERTEX, BACKDROP_FRAGMENT),
    ("shafts", FULL_VERTEX, SHAFT_FRAGMENT),
    ("blur", FULL_VERTEX, BLUR_FRAGMENT),
    ("shells", BUBBLE_VERTEX, BUBBLE_FRAGMENT),
    ("clusters", CLUSTER_VERTEX, CLUSTER_FRAGMENT),
    ("beads", BEAD_VERTEX, BUBBLE_FRAGMENT),
    ("near", BUBBLE_VERTEX, NEAR_FRAGMENT),
    ("near_clusters", CLUSTER_VERTEX, NEAR_CLUSTER_FRAGMENT),
    ("proxies", PARTICLE_VERTEX, PARTICLE_FRAGMENT),
    ("specks", SPECK_VERTEX, PARTICLE_FRAGMENT),
    ("trails", TRAIL_VERTEX, TRAIL_FRAGMENT),
)


@lru_cache(maxsize=2)
def projection_programs(projection_kind: str):
    """Bounded lazy specializations of the same traced-surface source.

    A dynamic projection branch changes GPU compiler arithmetic around very
    bright glass glints even when its value is Perspective. Constant folding
    preserves the accepted Perspective pixels and removes that per-ray branch.
    Cube/main mixed programs retain their ordinary uniform; only traced surface
    fragments specialize. Preparation and drawing use these exact cache keys.
    """
    if projection_kind not in ('Perspective', 'Orthographic'):
        raise ValueError(f'Unknown framed projection: {projection_kind!r}')
    rows=[]
    for key,vertex,fragment in _PROGRAMS:
        resource_key=key
        if key in ('shells','clusters','beads','near','near_clusters'):
            declaration='uniform float uOrthographic;'
            if fragment.count(declaration)!=1:
                raise ValueError(f'{key}: expected one framed projection declaration')
            value='1.0' if projection_kind=='Orthographic' else '0.0'
            fragment=fragment.replace(declaration,f'const float uOrthographic={value};')
            resource_key=f'{key}:{projection_kind}'
        rows.append((key,(resource_key,vertex,fragment)))
    return tuple(rows)
# The probe's cube face size per 3D Detail tier (what bubbles mirror; smaller is softer and cheaper).
_PROBE_SIZE = {"High": 256, "Balanced": 256, "Performance": 128, "KAK": 64}
_BLOOM = 0.55
_NEAR_SPREAD = 22.0 * 1.6       # the widest circle the near layer spreads a giant over (pixels)
_SHELL_CAPACITY = MAX_BUBBLES
_CLUSTER_CAPACITY = MAX_BUBBLES // 2
_UNIT_SHAFTS, _UNIT_BACKGROUND, _UNIT_PROBE = 4, 5, 6
# Procedural small bubbles: chains per step of the Bead Chains range, beads a chain, and marine snow motes (both
# scaled by the tier's particle share). Beads climb by the stream's travel only, with integrated energy response.
_CHAINS_PER_STEP, _BEADS_PER_CHAIN, _SNOW = CHAINS_PER_STEP, 160, SNOW_FULL
_FIZZ_PER_BUBBLE, _WAKE_BINDING = 64, 7         # wake motes behind stable logical emitters; separate SSBO binding
_BEAD_CLIMB, _SNOW_CARRY, _SPECK_CARRY = 5.0 / WORLD_UNIT, 8.0 / WORLD_UNIT, 0.30  # specks inherit 30% of integrated stream velocity


def _near_spread(height: int) -> float:
    """Resolution-scaled lens budget; camera gestures do not reallocate its read level."""
    return _NEAR_SPREAD * height / 941.0


def chain_drive(state) -> float:
    """Where the Bead Chains Range sits: how loud the passage is, swung a little by the beat-level follower."""
    return min(1.0, float(getattr(state, "passage", 0.0)) * (0.8 + 0.4 * float(state.level)))


def _procedural_fill(parameters, level: float, emission: float) -> tuple[float, float, float]:
    """Continuous (chains, snow, fizz per owner), each authored Range resolved once.

    Level is the simulation's normalized band-driven follower, not the engine's
    passage-presence scalar. Particles-resolved emission must not remap Bead Chains.
    """
    share = scene3d_detail(parameter(parameters, "scene3d_detail")).particles
    low, high = (float(v) for v in parameter(parameters, "extruded_bubble_bead_chains"))
    chains = max(0.0, (low + (high - low) * max(0.0, min(1.0, float(level)))) * _CHAINS_PER_STEP * share)
    amount = max(0.0, min(1.0, float(emission))) * share
    return chains, _SNOW * amount, _FIZZ_PER_BUBBLE * amount


def _scene_samples(parameters) -> int:
    """The card's multisampling: the tier's overlay samples (one sample when it has none)."""
    return max(1, scene3d_detail(parameter(parameters, "scene3d_detail")).overlay_samples)


class _ShaftTargets:
    """Two half-resolution single-channel targets the shafts march into and blur between."""

    def __init__(self, label: str) -> None:
        self.label = label
        self.size = (0, 0)
        self.textures: list[int] = []
        self.framebuffers: list[int] = []

    @property
    def has_resources(self) -> bool:
        return bool(self.textures or self.framebuffers)

    def warm(self, width: int, height: int) -> bool:
        size = (max(1, int(width) // 2), max(1, int(height) // 2))
        if size == self.size and self.textures:
            return True
        self.release()
        name = (ctypes.c_uint * 1)()
        for _ in range(2):
            gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
            texture = int(name[0])
            self.textures.append(texture)
            gl.glTextureStorage2D(texture, 1, gl.GL_R16F, *size)
            for key in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
                gl.glTextureParameteri(texture, key, gl.GL_LINEAR)
            for key in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
                gl.glTextureParameteri(texture, key, gl.GL_CLAMP_TO_EDGE)
            gl.glCreateFramebuffers(1, name)
            self.framebuffers.append(int(name[0]))
            gl.glNamedFramebufferTexture(self.framebuffers[-1], gl.GL_COLOR_ATTACHMENT0, texture, 0)
            if not texture or not self.framebuffers[-1]:
                raise RuntimeError(f"{self.label}: shaft target allocation failed")
        self.size = size
        return False

    def release(self) -> None:
        if self.framebuffers:
            gl.glDeleteFramebuffers(len(self.framebuffers), self.framebuffers)
        if self.textures:
            gl.glDeleteTextures(len(self.textures), self.textures)
        self.textures, self.framebuffers, self.size = [], [], (0, 0)


class _Instances:
    """One fixed-capacity instance buffer and its vertex array (attributes of ``sizes`` floats, divisor 1); a
    buffer read only as storage gives its row's ``floats`` instead."""

    def __init__(self, capacity: int, sizes: tuple[int, ...], floats: int | None = None) -> None:
        self.capacity, self.sizes = capacity, sizes
        self.stride = 4 * (sum(sizes) if floats is None else floats)
        self.vao = self.buffer = 0
        self.count = 0

    def allocate(self) -> None:
        name = (ctypes.c_uint * 1)()
        gl.glCreateBuffers(1, name)
        self.buffer = int(name[0])
        gl.glNamedBufferStorage(self.buffer, self.capacity * self.stride, None, gl.GL_DYNAMIC_STORAGE_BIT)
        gl.glCreateVertexArrays(1, name)
        self.vao = int(name[0])
        if not (self.buffer and self.vao):
            raise RuntimeError("Extruded Bubble instance allocation failed")
        gl.glVertexArrayVertexBuffer(self.vao, 0, self.buffer, 0, self.stride)
        gl.glVertexArrayBindingDivisor(self.vao, 0, 1)
        offset = 0
        for location, size in enumerate(self.sizes):
            gl.glEnableVertexArrayAttrib(self.vao, location)
            gl.glVertexArrayAttribFormat(self.vao, location, size, gl.GL_FLOAT, gl.GL_FALSE, offset)
            gl.glVertexArrayAttribBinding(self.vao, location, 0)
            offset += 4 * size

    def upload(self, rows: np.ndarray) -> int:
        rows = np.ascontiguousarray(rows[:self.capacity], dtype=np.float32)
        self.count = len(rows)
        if self.count:
            gl.glNamedBufferSubData(self.buffer, 0, rows.nbytes, rows)
        return self.count

    def release(self) -> None:
        if self.vao:
            gl.glDeleteVertexArrays(1, [self.vao])
        if self.buffer:
            gl.glDeleteBuffers(1, [self.buffer])
        self.vao = self.buffer = self.count = 0


class _Uniforms:
    """Uniform uploads by name for linked programs, each sent only when its value changed (``glProgramUniform*``:
    no program bind). Values: int/bool, float, 2/3/4-float tuples, 9 (mat3) or 16 (mat4) floats, column-major."""

    def __init__(self) -> None:
        self._locations: dict[tuple[int, str], int] = {}
        self._values: dict[tuple[int, str], object] = {}

    def set(self, program: int, values: dict[str, object]) -> None:
        for name, value in values.items():
            key = (program, name)
            if self._values.get(key, _UNSET) == value:
                continue
            location = self._locations.get(key)
            if location is None:
                location = self._locations[key] = int(gl.glGetUniformLocation(program, name))
            if location < 0:
                self._values[key] = value
                continue                      # not read by this program (the driver dropped it)
            if isinstance(value, (bool, int)):
                gl.glProgramUniform1i(program, location, int(value))
            elif isinstance(value, float):
                gl.glProgramUniform1f(program, location, value)
            elif len(value) == 2:
                gl.glProgramUniform2f(program, location, *value)
            elif len(value) == 3:
                gl.glProgramUniform3f(program, location, *value)
            elif len(value) == 4:
                gl.glProgramUniform4f(program, location, *value)
            elif len(value) == 9:
                gl.glProgramUniformMatrix3fv(program, location, 1, gl.GL_FALSE, value)
            elif len(value) == 16:
                gl.glProgramUniformMatrix4fv(program, location, 1, gl.GL_FALSE, value)
            else:
                raise ValueError(f"uniform {name}: unsupported value {value!r}")
            self._values[key] = value  # Cache only values actually accepted by the uploader.

    def clear(self) -> None:
        self._locations.clear()
        self._values.clear()


_UNSET = object()


def _floats(values) -> tuple[float, ...]:
    return tuple(float(v) for v in values)


def _common(knobs, *, view_to_world, tan, time, surface_travel, rays, streak, eye=(0.0, 0.0, 0.0)) -> dict[str, object]:
    """What every scene program reads (``COMMON``), as the lab sets it from a scene's knobs."""
    exposure = float(knobs["exposure"])
    values = {
        "uViewToWorld": _floats(view_to_world), "uEye": _floats(eye), "uTan": _floats(tan), "uTime": float(time),
        "uSurfaceTravel": float(surface_travel),
        "uSun": _floats(knobs["sun"]), "uSunBelow": _floats(knobs["sun_below"]),
        "uLightSource": _floats(knobs["light_source"]), "uLightEnd": _floats(knobs["light_end"]),
        "uWisps": 0.0, "uVeils": float(knobs.get("veils", 0.0)),
        "uSurfaceY": float(knobs.get("surface", SURFACE_Y)), "uShaftY": float(knobs.get("shaft_y", SURFACE_Y)),
        "uLightStrength": float(knobs["light_strength"]),
        "uPositionalLight": 1.0 if knobs["mode"] == "deep" else 0.0,
        "uGlow": float(knobs.get("glow", 1.0)), "uRays": float(rays) * float(knobs["light_strength"]),
        "uMist": float(knobs.get("mist", 0.0)),
        "uSurfaceGain": float(knobs.get("surface_gain", 1.0)), "uSurfaceSky": float(knobs.get("surface_sky", 1.0)),
        "uDust": float(knobs.get("dust", 0.0)), "uFloor": (float(knobs.get("floor", 0.0)), float(WORLD_CENTER[1] - WORLD_HALF[1] - 4.0)), "uShaftWhite": float(knobs.get("shaft_white", 0.35)), "uRayFocus": float(knobs.get("ray_focus", 0.0)), "uRayCut": float(knobs.get("ray_cut", 0.25)),
        "uShaftScale": float(knobs.get("shaft_scale", 1.0)), "uShaftSoft": float(knobs.get("shaft_soft", 0.0)),
        "uSurfaceShaft": float(knobs["surface_shaft"]),
        "uShaftFan": float(knobs.get("shaft_fan",0.0)), "uFanRays": float(knobs["fan_rays"]),
        "uFanMix": (float(knobs["fan_contrast"]),float(knobs["fan_march"])),
        "uLightingScene": float(knobs["lighting_scene"]), "uBeamWidth": float(knobs["beam_width"]),
        "uWorldCenter": WORLD_CENTER, "uWorldHalf": WORLD_HALF,
        "uFanReach": float(knobs.get("fan_reach", 0.6)),
        "uSpecks": 0.0, "uLightPower": float(knobs.get("light_power", 0.0)),
        "uGlintPower": float(knobs.get("glint_power", 0.0)), "uProbeFill": float(knobs.get("probe_fill", 0.0)),
        "uGlintSharp": float(knobs.get("glint_sharp", 6000.0)), "uProbeMode": 0.0, "uStreak": _floats(streak),
        "uSparkle": float(knobs.get("sparkle", 0.0)), "uLightColour": _floats(knobs["light"]),
        "uFilm": float(knobs.get("film", 0.0)), "uFilmRange": _floats(knobs.get("film_range", (250.0, 600.0))),
        "uCrisp": float(knobs.get("crisp", 0.0)), "uAbsorb": _floats(knobs["absorb"]),
    }
    for name, key in (("uDeep", "deep"), ("uWater", "water"), ("uSkyTint", "sky"), ("uShaftColour", "shaft")):
        values[name] = tuple(float(v) * exposure for v in knobs[key])
    return values


def _glass(knobs, near: bool) -> dict[str, object]:
    """The traced glass's own knobs (shells, clusters; the near layer's lens and reflection differ)."""
    return {
        "uEta": 1.33, "uBehind": 8.0, "uShell": float(knobs.get("shell", 0.1)),
        "uLens": float(knobs.get("lens", 0.85)),
        "uIors": _floats(knobs.get("iors", (1.33, 1.5, 1.0))), "uRough": float(knobs.get("rough", 0.0)),
        "uShellMin": 0.0, "uDiag": 0, "uLightDir": _floats(knobs["spec_dir"]),
        "uSpecColour": _floats(knobs["specular_light"]), "uSpecThrough": 0.4, "uSpecShape": (0.05, 0.25, 0.012),
        "uInnerBlur": float(knobs.get("inner_blur", 0.25)),
        "uReflect": float(knobs.get("face_reflect", 1.0)),
        "uSpeckGlow": 0.6 * float(knobs["light_strength"]), "uFrameShare": 1.0,
        "uNearCoc": 22.0, "uNearGain": 1.0,
        "uFocus": float(knobs.get("focus", 4.2)), "uAperture": float(knobs.get("aperture", 3.0)),
        "uNearLayer": 1.0 if near else 0.0,
        "uBackground": _UNIT_BACKGROUND, "uProbe": _UNIT_PROBE,
    }


class QuickExtrudedBubbleRenderer:
    mode_id = "extruded_bubble"

    def __init__(self) -> None:
        self._resources = MeshResources("Extruded Bubble")
        self._target = SceneTarget("Extruded Bubble")
        self._near = DefocusLayer("Extruded Bubble near layer")
        self._shafts = _ShaftTargets("Extruded Bubble shafts")
        self._probe: SceneProbe | None = None
        self._shells = _Instances(_SHELL_CAPACITY, (4, 2, 1, 1))
        self._wakes = _Instances(MAX_BUBBLES * 2, (), floats=WAKE_STRIDE)   # read as storage (EbWakes)
        self._drift = _Instances(0, (), floats=4)
        self._clusters = _Instances(_CLUSTER_CAPACITY, (4, 4, 4, 4, 3))
        self._proxies = _Instances(_SHELL_CAPACITY, (4, 4))
        self._empty_vao = 0                       # the procedural layers read no attributes
        self._uniforms = _Uniforms()
        self._knobs_for: object = None
        self._knobs: dict[str, object] = {}

    @property
    def has_resources(self) -> bool:
        return (self._resources.has_resources or self._target.has_resources or self._near.has_resources()
                or self._shafts.has_resources or bool(self._shells.vao) or bool(self._wakes.vao) or bool(self._drift.vao) or bool(self._empty_vao)
                or self._probe is not None)

    def _probe_for(self, parameters) -> SceneProbe:
        size = _PROBE_SIZE[scene3d_detail(parameter(parameters, "scene3d_detail")).name]
        if self._probe is not None and self._probe.size != size:
            self._probe.release()
            self._probe = None
        if self._probe is None:
            self._probe = SceneProbe("Extruded Bubble probe", size)
        return self._probe

    def _programs(self, samples: int, projection_kind: str = 'Perspective'):
        r = self._resources
        return [*((r, *program) for _key,program in projection_programs(projection_kind)),
                *((r, *program) for program in scene_target_programs(samples, True, False, overlay=True,
                                                                       background=True, oit=True, hdr=True))]

    def prepare_step(self, frame: QuickVisualizerRenderFrame) -> bool:
        """One unit of what a first visible frame would otherwise compile or allocate (a program, the instance
        buffers, the shaft targets, the probe, the near layer, the scene target), on a hidden reveal frame; True
        once nothing is left."""
        parameters = frame.snapshot.logical.mode_state.parameters
        samples = _scene_samples(parameters)
        if not warm_programs(self._programs(samples, str(parameter(parameters, "extruded_bubble_camera_projection")))):
            return False
        if not self._shells.vao:
            self._allocate_instances()
            return False
        width, height = item_pixel_rect(frame)[2:]
        state=frame.snapshot.logical.mode_state
        material_bytes=len(state.drift_paths)+len(state.snow_drift_offsets)+len(state.speck_drift_offsets)
        if material_bytes and self._warm_material_buffer(material_bytes):
            return False
        if not self._shafts.warm(width, height):
            return False
        if not self._probe_for(parameters).warm():
            return False
        if not self._near.warm(width, height,
                               _near_spread(height / framed_aperture_scale(frame.snapshot.presentation))):
            return False
        return self._target.warm((width, height), samples, overlay=True, bloom=True, depth_texture=True,
                                 background=True, oit=True, hdr=True)

    def render(self, frame: QuickVisualizerRenderFrame) -> None:
        state = frame.snapshot.logical.mode_state
        if not isinstance(state, ExtrudedBubbleFrame):
            raise TypeError("Extruded Bubble renderer received another mode frame")
        presentation = frame.snapshot.presentation
        if presentation.content_fade <= 0.0:
            return
        if frame.content_rotation_quarters:
            raise ValueError("Extruded Bubble does not offer content rotation")
        x, y, width, height = item_pixel_rect(frame)
        if width <= 0 or height <= 0:
            return
        optical_height = height / framed_aperture_scale(presentation)
        parameters = state.parameters
        if parameters != self._knobs_for:
            self._knobs, self._knobs_for = scene_knobs(parameters), parameters
        knobs = self._knobs
        samples = _scene_samples(parameters)
        r = self._resources
        projection_kind = str(parameter(parameters, "extruded_bubble_camera_projection"))
        programs = {key: r.program(*program) for key,program in projection_programs(projection_kind)}
        if not self._shells.vao:
            self._allocate_instances()
        self._shafts.warm(width, height)
        probe = self._probe_for(parameters)

        pose = (float(parameter(parameters, "extruded_bubble_turn")), float(parameter(parameters, "extruded_bubble_tilt")))
        scale = float(parameter(parameters, "extruded_bubble_scene_scale"))
        fov_y = float(parameter(parameters, "extruded_bubble_camera_fov"))
        orthographic = 1.0 if projection_kind == "Orthographic" else 0.0
        # Orbit = Alt+left drag; Scene Pan = physical lateral/up translation;
        # Scene Scale = physical dolly. None of these change the centred lens.
        view_to_world, world_to_view, eye, tan, projection = physical_camera(
            *pose, width / height, scale,
            pan_x=float(parameter(parameters, "extruded_bubble_scene_pan_x")),
            pan_y=float(parameter(parameters, "extruded_bubble_scene_pan_y")),
            position_offset=tuple(parameter(parameters, "extruded_bubble_camera_position")),
            fov_y_degrees=fov_y, surface_bound=knobs["mode"] == "surface",
            aperture_scale=framed_aperture_scale(presentation), projection_kind=projection_kind)
        if knobs["mode"] == "deep":
            to_emitter = tuple(float(p) - float(e) for p, e in zip(knobs["light_source"], eye))
            distance = math.sqrt(sum(v*v for v in to_emitter))
            if distance > 1e-6:
                knobs = {**knobs, "sun_below": tuple(v/distance for v in to_emitter)}
        shift = (0.0, 0.0)
        pixel = 2.0 * tan[1] / height
        # A single physical population; close bubbles enter the existing defocus pass by real camera depth.
        shells = bubble_instances(state.bubbles)
        shell_count = self._shells.upload(shells)
        wake_count = self._wakes.upload(wake_instances(state.wakes))
        material_payload=b''.join((state.drift_paths,state.snow_drift_offsets,state.speck_drift_offsets))
        if material_payload:
            self._warm_material_buffer(len(material_payload))
            self._drift.upload(np.frombuffer(material_payload,dtype=np.float32).reshape(-1,4))
        drift_uniforms={'uChainDriftEnabled':int(bool(state.drift_paths)),
            'uSnowDriftOffset':len(state.drift_paths)//16+1 if state.snow_drift_offsets else 0,
            'uSpeckDriftOffset':(len(state.drift_paths)+len(state.snow_drift_offsets))//16+1 if state.speck_drift_offsets else 0}
        self._uniforms.set(programs['beads'],drift_uniforms)
        self._uniforms.set(programs['specks'],drift_uniforms)
        cluster_count = self._clusters.upload(cluster_instances(state.bubbles, state.clusters))
        proxy_count = self._proxies.upload(glint_proxies(shells, knobs["sun_below"],
                                                         float(knobs["proxy_power"]),
                                                         light_source=(knobs["light_source"] if knobs["mode"] == "deep"
                                                                       else None)))
        # The rays read the simulation's ray driver and shimmer, never the raw level (it holds at 1 when loud).
        flicker, reach = ray_motion(parameters, state.rays, state.sustain)
        common = _common({**knobs, "fan_reach": float(knobs.get("fan_reach", 0.6)) * reach}, view_to_world=view_to_world, eye=eye,
                         tan=tan, time=state.motion_phase, surface_travel=state.motion_phase,
                         rays=ray_strength(parameters, state.rays),
                         streak=screen_streak(state.stream))
        common["uOrthographic"] = orthographic
        dust_across, _depth = stream_basis(_floats(state.stream))
        common.update({"uDustAlong": _floats(state.stream), "uDustAcross": dust_across,
                       "uDustBands": (float(knobs["band_freq"]), float(WORLD_UNIT), float(knobs["band_gather"]))})
        for key in programs:
            if key != "blur":
                self._uniforms.set(programs[key], common)
        # Bounded screen-space optical proxy: four dominant physical shells, not
        # a per-particle shadow pass. Never allocate any extra scene target.
        leaders = sorted((tuple(float(v) for v in row[:4]) for row in shells if row[3] > 0.0),
                         key=lambda b: -b[3])[:4]
        leaders += [(0.0, 0.0, 0.0, 0.0)] * (4 - len(leaders))
        ray_uniforms = {"uLensShift": shift, "uFlicker": flicker,
                        "uShimmer": float(state.shimmer),
                        "uRaySource": _floats(knobs["ray_source"]),
                        "uRayEnd": _floats(knobs["ray_end"]),
                        "uLightFaces": _floats(knobs["scene_light"]["faces"]),
                        "uLightTravel": _floats(knobs["scene_light"]["travel"]),
                        "uLightAxis": _floats(knobs["scene_light"]["axis"]),
                        "uLightReach": _floats(knobs["scene_light"]["reach"]),
                        "uParticleAtten": max(0.0, min(0.08, 0.08 * float(state.emission)))}
        for i, bubble in enumerate(leaders):
            ray_uniforms[f"uBlock{i}"] = bubble
        self._uniforms.set(programs["shafts"], ray_uniforms)
        sun_screen = light_on_screen(knobs["sun_below"], world_to_view, projection, (width, height))
        view = {"uWorldToView": _floats(world_to_view), "uEye": _floats(eye), "uProjection": _floats(projection), "uPixel": pixel,
                "uPixelSize": pixel, "uFrameSize": (float(width), float(height)), "uSunScreen": sun_screen,
                "uProbeLevels": float(probe.levels), "uLensShift": shift}
        for key, near in (("shells", False), ("clusters", False), ("near", True), ("near_clusters", True), ("beads", False)):
            self._uniforms.set(programs[key], {**view, **_glass(knobs, near),
                                             "uNearCoc": 22.0 * optical_height / 941.0,
                                             "uNearMax": _near_spread(optical_height)})
        self._uniforms.set(programs["trails"], {**view, "uFocus": float(knobs.get("focus", 4.2)),
                                                "uAperture": float(knobs.get("aperture", 3.0)),
                                                "uNearCoc": 22.0 * optical_height / 941.0, "uNearMax": _near_spread(optical_height)})
        chain_fill, snow_fill, fizz_fill = _procedural_fill(parameters, chain_drive(state), state.emission)
        idle_activity = _idle_activity(state.level)
        beads, snow = math.ceil(chain_fill) * _BEADS_PER_CHAIN, math.ceil(snow_fill)
        if state.snow_drift_offsets and len(state.snow_drift_offsets)<snow*16:
            raise ValueError('Logical marine-snow drift does not cover the rendered population')
        trail_fizz = (_FIZZ_PER_BUBBLE * scene3d_detail(parameter(parameters, "scene3d_detail")).particles
                      * float(parameter(parameters, "extruded_bubble_wake_trails")))
        fizz_per = math.ceil(max(fizz_fill, trail_fizz))
        stream = _floats(state.stream)
        across, depth_axis = stream_basis(stream)
        stream_path = admit_path(parameter(parameters, "extruded_bubble_stream_direction"), [0., 0.], "stream")
        stream_source = _floats(world_point(stream_path[:3]))
        stream_end = _floats(world_point(stream_path[3:]))
        scene_emission = 1 if parameter(parameters, "extruded_bubble_emission_geometry") == "SCENE" else 0
        from widgets.spotify_visualizer.extruded_bubble_geometry import scene_source_face_weights
        scene_faces = _floats(scene_source_face_weights(stream_path[:3], stream))
        self._uniforms.set(programs["beads"], {
            "uWorldCenter": WORLD_CENTER, "uWorldHalf": WORLD_HALF,
            "uStreamAcross": across, "uStreamDepth": depth_axis,
            "uStreamWorld": stream, "uStreamSource": stream_source, "uStreamEnd": stream_end,
            "uParticleSpread": float(parameter(parameters, "extruded_bubble_particle_spread")),
            "uSceneEmission": scene_emission, "uSceneFaces": scene_faces,
            "uBeadsPerChain": _BEADS_PER_CHAIN,
            "uBeadCount": beads, "uBeadSize": float(parameter(parameters, "extruded_bubble_bead_size"))
            * (0.9 + 0.2 * max(0.0, min(1.0, float(state.level)))),
            "uBeadScatter": float(parameter(parameters, "extruded_bubble_bead_scatter")),
            "uChainFill": chain_fill, "uChainActivity": float(state.chain_activity),
            "uSnowFill": snow_fill, "uFizzFill": fizz_fill, "uTrailFizz": trail_fizz,
            "uBeadTravel": _BEAD_CLIMB * float(state.travel),
            "uSnowDrift": _SNOW_CARRY * float(state.travel), "uSnowCount": snow, "uFizzPer": fizz_per,
            "uWakeCount": wake_count})
        fizz = wake_count * fizz_per
        trails = float(parameter(parameters, "extruded_bubble_wake_trails"))
        # One wake path for the veils and the fizz that streams inside them (0 Wake Trails: fizz as before).
        wake_path = {"uTrails": trails,
                     "uTrailTime": float(state.motion_phase)}
        for key in ("trails", "beads"):
            self._uniforms.set(programs[key], wake_path)
        self._uniforms.set(programs["blur"], {"uSource": 0})
        share, brightness = speck_amount(state.emission)
        # Optional glow lift never adds another source follower: the same musical
        # rays/flash state already advances once on the simulation clock.
        glow_react = max(0.0, min(1.0, float(parameter(parameters, "extruded_bubble_particle_glow_reactivity"))))
        glow_multiplier = 1.0 + glow_react * (0.50 * float(state.rays) + 0.20 * float(state.flash))
        specks = round(SPECKS_FULL * share * scene3d_detail(parameter(parameters, "scene3d_detail")).particles)
        if state.speck_drift_offsets and len(state.speck_drift_offsets)<specks*16:
            raise ValueError('Logical particulate drift does not cover the rendered population')
        self._uniforms.set(programs["specks"], {
            "uWorldToView": _floats(world_to_view), "uRowMajor": 0, "uProjection": _floats(projection), "uPixel": pixel,
            "uSpecks": brightness, "uSpeckBloom": float(knobs["speck_bloom"]) * glow_multiplier,
            "uParticleLighting": 1.0,
            "uParticleActivity": idle_activity, "uParticleRadiusShare": 0.25 + 0.75 * idle_activity,
            "uSpeckWarm": _floats(knobs["speck_warm"]),
            "uStreamWorld": stream,
            "uStreamAcross": across,
            "uWorldCenter": WORLD_CENTER, "uWorldHalf": WORLD_HALF, "uWorldUnit": WORLD_UNIT,
            "uSpeckTravel": _SPECK_CARRY * float(state.travel),
            "uParticleSpread": float(parameter(parameters, "extruded_bubble_particle_spread")),
            "uSceneEmission": scene_emission, "uSceneFaces": scene_faces,
            "uSpeckSource": stream_source, "uSpeckEnd": stream_end,
            "uWarmShare": float(knobs["warm_share"]),
            "uClouds": (float(knobs["cloud_contrast"]), float(knobs["cloud_floor"]), float(knobs["cloud_glow"])),
            "uBandFreq": float(knobs["band_freq"]), "uBandGather": float(knobs["band_gather"]),
            "uSpeckSize": float(knobs["speck_size"])})
        self._uniforms.set(programs["proxies"], {"uSpecks": 1.0, "uSpeckBloom": 0.0, "uParticleActivity": 1.0,
                                                 "uParticleLighting": 0.0,
                                                 "uParticleRadiusShare": 1.0,
                                                 "uSpeckWarm": _floats(knobs["light"]), "uRowMajor": 1,
                                                 "uPixel": 2.0 / probe.size})

        gl.glDisable(gl.GL_BLEND)
        gl.glDisable(gl.GL_DEPTH_TEST)
        self._capture_probe(probe, programs, proxy_count, frame.quad_vao)
        self._draw_shafts(programs, frame.quad_vao)

        with self._target.scope(frame, samples, r, overlay=presentation.content_fade, bloom=_BLOOM,
                                depth_texture=True, oit=True, hdr=1.0):
            scene_viewport = (frame.viewport[0] - x, frame.viewport[1] - y, frame.viewport[2], frame.viewport[3])
            allocation = self._target.allocation
            self._uniforms.set(programs["backdrop"], {"uProbeMode": 0.0, "uViewToWorld": _floats(view_to_world),
                                                      "uTan": _floats(tan), "uShafts": _UNIT_SHAFTS, "uLensShift": shift,
                                                      "uFrameSize": (float(width), float(height)),
                                                      "uOrthographic": orthographic})
            target_size = (float(allocation[0]), float(allocation[1]))
            for key in ("shells", "clusters", "near", "near_clusters", "beads"):
                self._uniforms.set(programs[key], {"uTargetSize": target_size})
            # The card's camera covers the item's pixels (the target's origin), not the window's viewport.
            gl.glViewport(0, 0, width, height)
            with self._target.emission_writes():
                gl.glBindTextureUnit(_UNIT_SHAFTS, self._shafts.textures[0])
                gl.glUseProgram(programs["backdrop"])
                gl.glBindVertexArray(frame.quad_vao)
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
                if specks:
                    # Light only: added over the water, never hiding it, and writing no depth.
                    gl.glEnablei(gl.GL_BLEND, 0)
                    gl.glBlendEquationSeparatei(0, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
                    gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE)
                    gl.glDepthMask(gl.GL_FALSE)
                    gl.glUseProgram(programs["specks"])
                    gl.glBindVertexArray(self._empty_vao)
                    self._draw_material_instances(specks,bool(material_payload))
                    gl.glDepthMask(gl.GL_TRUE)
                    gl.glDisablei(gl.GL_BLEND, 0)
                background, _depth = self._target.background(frame, r)
                gl.glBindTextureUnit(_UNIT_BACKGROUND, background)
                gl.glBindTextureUnit(_UNIT_PROBE, probe.texture)
                with self._target.transparent_writes(frame, r):
                    if shell_count:
                        gl.glUseProgram(programs["shells"])
                        gl.glBindVertexArray(self._shells.vao)
                        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, shell_count)
                    if cluster_count:
                        gl.glUseProgram(programs["clusters"])
                        gl.glBindVertexArray(self._clusters.vao)
                        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, cluster_count)
                    if beads + snow + fizz:
                        # Wakes read stable emitters (including retiring tombstones), never reused shell slots.
                        prior = gl_query.get_indexed_int(gl.GL_SHADER_STORAGE_BUFFER_BINDING, _WAKE_BINDING)
                        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, _WAKE_BINDING, self._wakes.buffer)
                        gl.glUseProgram(programs["beads"])
                        gl.glBindVertexArray(self._empty_vao)
                        self._draw_material_instances(beads+snow+fizz,bool(material_payload))
                        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, _WAKE_BINDING, prior)
                    if trails > 0.0 and wake_count:
                        # Wake trails: one sheet per stable emitter, read from the same records as the fizz.
                        prior = gl_query.get_indexed_int(gl.GL_SHADER_STORAGE_BUFFER_BINDING, _WAKE_BINDING)
                        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, _WAKE_BINDING, self._wakes.buffer)
                        self._uniforms.set(programs["trails"], {"uTargetSize": target_size})
                        gl.glUseProgram(programs["trails"])
                        gl.glBindVertexArray(self._empty_vao)
                        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 2 * (TRAIL_SEGMENTS + 1), wake_count)
                        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, _WAKE_BINDING, prior)
            # Only ordinary large bubbles whose front surface actually reaches the focus region enter this layer.
            # BUBBLE_VERTEX makes the same depth decision in both passes so a bubble is never drawn twice.
            # Procedural beads/snow/fizz never write this layer. Keep its warmed
            # resources, but an absent ordinary population has no optics to composite.
            if shell_count or cluster_count:
                self._near.begin(width, height)
                gl.glViewport(0, 0, width, height)
                gl.glUseProgram(programs["near"])
                gl.glBindVertexArray(self._shells.vao)
                gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, shell_count)
                if cluster_count:
                    gl.glUseProgram(programs["near_clusters"])
                    gl.glBindVertexArray(self._clusters.vao)
                    gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, cluster_count)
                self._near.end()
                self._near.composite(_near_spread(optical_height))
            for unit in (_UNIT_SHAFTS, _UNIT_BACKGROUND, _UNIT_PROBE):
                gl.glBindTextureUnit(unit, 0)
            gl.glViewport(*scene_viewport)

    def _warm_material_buffer(self,size):
        rows=size//16
        if self._drift.buffer and self._drift.capacity>=rows:
            return False
        self._drift.release()
        self._drift.capacity=max(256,1<<(max(rows,1)-1).bit_length())
        self._drift.allocate()
        return True

    def _draw_material_instances(self,count,enabled):
        if not enabled:
            gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP,0,4,count)
            return
        previous=gl_query.get_indexed_int(gl.GL_SHADER_STORAGE_BUFFER_BINDING,6)
        start=gl_query.get_indexed_int64(gl.GL_SHADER_STORAGE_BUFFER_START,6)
        size=gl_query.get_indexed_int64(gl.GL_SHADER_STORAGE_BUFFER_SIZE,6)
        generic=gl_query.get_int(gl.GL_SHADER_STORAGE_BUFFER_BINDING)
        try:
            gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,6,self._drift.buffer)
            gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP,0,4,count)
        finally:
            if previous and size:
                gl.glBindBufferRange(gl.GL_SHADER_STORAGE_BUFFER,6,previous,start,size)
            else:
                gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,6,previous)
            gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,generic)

    def _allocate_instances(self) -> None:
        for instances in (self._shells, self._wakes, self._clusters, self._proxies):
            instances.allocate()
        name = (ctypes.c_uint * 1)()
        gl.glCreateVertexArrays(1, name)
        self._empty_vao = int(name[0])

    def _capture_probe(self, probe: SceneProbe, programs, proxy_count: int, quad_vao: int) -> None:
        """The water and light all round the eye, each bubble's glint added as a bright point."""
        backdrop, proxies = programs["backdrop"], programs["proxies"]

        def draw(face, world_to_face, projection):
            self._uniforms.set(backdrop, {"uViewToWorld": _floats(world_to_face), "uTan": (1.0, 1.0), "uLensShift": (0.0, 0.0),
                                          "uProbeMode": 1.0, "uOrthographic": 0.0,
                                          "uFrameSize": (float(probe.size), float(probe.size))})
            gl.glDisable(gl.GL_BLEND)
            gl.glUseProgram(backdrop)
            gl.glBindVertexArray(quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            if not proxy_count:
                return
            self._uniforms.set(proxies, {"uWorldToView": _floats(world_to_face), "uProjection": _floats(projection),
                                        "uOrthographic": 0.0})
            gl.glEnablei(gl.GL_BLEND, 0)
            gl.glBlendEquationSeparatei(0, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
            gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE)
            gl.glDepthMask(gl.GL_FALSE)
            gl.glUseProgram(proxies)
            gl.glBindVertexArray(self._proxies.vao)
            gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, proxy_count)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glDisablei(gl.GL_BLEND, 0)

        probe.capture(draw)

    def _draw_shafts(self, programs, quad_vao: int) -> None:
        """The volumetric light at half resolution, then a separable blur back into the first target."""
        prior_framebuffer = int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING))
        prior_viewport = [int(v) for v in gl.glGetIntegerv(gl.GL_VIEWPORT)]
        textures, framebuffers = self._shafts.textures, self._shafts.framebuffers
        try:
            gl.glViewport(0, 0, *self._shafts.size)
            gl.glBindVertexArray(quad_vao)
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, framebuffers[0])
            gl.glUseProgram(programs["shafts"])
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            gl.glUseProgram(programs["blur"])
            for source, target, step in ((textures[0], framebuffers[1], (1.0, 0.0)),
                                         (textures[1], framebuffers[0], (0.0, 1.0))):
                gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, target)
                gl.glBindTextureUnit(0, source)
                self._uniforms.set(programs["blur"], {"uStep": step})
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            gl.glBindTextureUnit(0, 0)
        finally:
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, prior_framebuffer)
            gl.glViewport(*prior_viewport)

    def _release_empty_vao(self) -> None:
        if self._empty_vao:
            gl.glDeleteVertexArrays(1, [self._empty_vao])
        self._empty_vao = 0

    def release_resources(self) -> None:
        errors: list[str] = []
        releases = [self._target.release, self._near.release, self._shafts.release, self._resources.release_resources,
                    self._shells.release, self._wakes.release, self._drift.release, self._clusters.release, self._proxies.release, self._release_empty_vao]
        if self._probe is not None:
            releases.append(self._probe.release)
        for release in releases:
            try:
                release()
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError("Quick Extruded Bubble cleanup incomplete: " + " | ".join(errors))
        self._probe = None
        self._uniforms.clear()
        self._knobs_for, self._knobs = None, {}


def create_visualizer_renderer() -> QuickExtrudedBubbleRenderer:
    return QuickExtrudedBubbleRenderer()


__all__ = ["QuickExtrudedBubbleRenderer", "create_visualizer_renderer"]
