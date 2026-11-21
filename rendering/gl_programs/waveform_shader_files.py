"""Waveform Ribbon's shader files, one text for both renderers (Current_Plan.md N5.4; Native_Port_Playbook.md checklist
16: the Python renderer draws these texts, the native core draws the same files).

Why it exists: the Python renderer composes its programs from Python texts (``rendering.gl_programs.ribbon``,
``waveform_ribbon``, ``waveform_atmosphere``, ``ribbon_bursts``, ``fog_volume``, ``waveform_floor_give``), converted
portable (N1.6: one std140 pass block a program); the native core loads ``.qsb`` packs baked from the shader folder
(``widgets/spotify_visualizer/shaders``, ``tools/regen_qrc.py --shaders``). Each program's converted text is written
there as a body (``waveform_*.glsl``, its version line left to the wrapper) and a test holds every file equal to its
text (``tests/test_waveform_shader_files.py``), so the two renderers draw one source.

The wrappers: the core fills a block member by its name, from one source for every pass that declares it
(``native/core/src/mode_content.cpp``), while Waveform draws one program with other values in another pass: the
mirrored camera's (the planar reflection's passes and the mirrored fog volume) and the floor's reduced pre-pass. A
variant is a wrapper file (``#version``, ``#define`` renames of those members, ``#include`` of the body): the
arithmetic is the body's, only the members' names differ, so each pass's values reach its own members. The Python
renderer packs by its layout's offsets, which the renames leave as they are. The varying members were measured on the
Python renderer's packs of every curated preset (N5.4 port record).

``waveform_shader_files()`` gives every file's name and text; ``tools/waveform_shader_files.py`` writes them.
"""
from __future__ import annotations

_VERSION = "#version 460 core\n"

#: The members whose values differ between the camera's passes and the mirrored camera's (the planar reflection's
#: draws, its sky and its fog volume), renamed in a mirror variant.
MIRROR_MEMBERS = ("uMvp", "uEye", "uViewZ", "uViewport", "uFogView", "uFogRange", "uFogInvView", "uSkyReflection")
#: The floor's reduced pre-pass (``WaveformScene._floor``: the reflection term alone into its own target): its mode
#: and its target's size.
PREPASS_MEMBERS = ("uSpecMode", "uViewport")


def mirror_name(member: str) -> str:
    """A member's name in the mirror variants (``uMvp`` -> ``uMirrorMvp``)."""
    return "uMirror" + member[1:]


def prepass_name(member: str) -> str:
    """A member's name in the floor's pre-pass variant (``uSpecMode`` -> ``uPrepassSpecMode``)."""
    return "uPrepass" + member[1:]


VARIANTS = {
    "": {},
    "_mirror": {member: mirror_name(member) for member in MIRROR_MEMBERS},
    "_prepass": {member: prepass_name(member) for member in PREPASS_MEMBERS},
}


def _bodies() -> dict[str, str]:
    """Body name -> the converted text the Python renderer compiles (its version line first)."""
    from rendering.gl_programs import ribbon, ribbon_bursts, waveform_atmosphere, waveform_floor_give, waveform_ribbon
    from rendering.gl_programs.fog_volume import FOG_INTEGRATE_COMPUTE

    return {
        "waveform_ribbon_vertex": ribbon.RIBBON_CONTINUOUS_VERTEX,
        "waveform_ribbon_body": ribbon.RIBBON_BODY_FRAGMENT,
        "waveform_ribbon_light": ribbon.RIBBON_LIGHT_FRAGMENT,
        "waveform_strays_vertex": ribbon.RIBBON_COHORT_STRAY_VERTEX,
        "waveform_strays_fragment": ribbon.RIBBON_COHORT_STRAY_FRAGMENT,
        "waveform_bursts_vertex": ribbon_bursts.VERTEX,
        "waveform_bursts_fragment": ribbon_bursts.FRAGMENT,
        "waveform_floor_vertex": waveform_ribbon.FLOOR_VERTEX,
        "waveform_floor_fragment": waveform_ribbon.FLOOR_FRAGMENT,
        "waveform_sky_vertex": waveform_atmosphere.SKY_VERTEX,
        "waveform_sky_fragment": waveform_atmosphere.SKY_FRAGMENT,
        "waveform_field": waveform_atmosphere.FIELD_COMPUTE,
        "waveform_medium": waveform_atmosphere.MEDIUM_INJECT_SOURCE,
        "waveform_fog_integrate": FOG_INTEGRATE_COMPUTE,
        "waveform_give_section": waveform_floor_give.FLOOR_GIVE_SECTION_COMPUTE,
        "waveform_give_blur": waveform_floor_give.FLOOR_GIVE_BLUR_COMPUTE,
    }


#: Each pass file: (wrapper file, body, variant). The ribbon's body and both extensions are one draw (its vertex stage
#: decodes the part), so the ribbon needs no per-part variant.
PASS_FILES = (
    ("waveform_ribbon.vert", "waveform_ribbon_vertex", ""),
    ("waveform_ribbon_mirror.vert", "waveform_ribbon_vertex", "_mirror"),
    ("waveform_ribbon_body.frag", "waveform_ribbon_body", ""),
    ("waveform_ribbon_light.frag", "waveform_ribbon_light", ""),
    ("waveform_ribbon_light_mirror.frag", "waveform_ribbon_light", "_mirror"),
    ("waveform_strays.vert", "waveform_strays_vertex", ""),
    ("waveform_strays_mirror.vert", "waveform_strays_vertex", "_mirror"),
    ("waveform_strays.frag", "waveform_strays_fragment", ""),
    ("waveform_strays_mirror.frag", "waveform_strays_fragment", "_mirror"),
    ("waveform_bursts.vert", "waveform_bursts_vertex", ""),
    ("waveform_bursts_mirror.vert", "waveform_bursts_vertex", "_mirror"),
    ("waveform_bursts.frag", "waveform_bursts_fragment", ""),
    ("waveform_bursts_mirror.frag", "waveform_bursts_fragment", "_mirror"),
    ("waveform_floor.vert", "waveform_floor_vertex", ""),
    ("waveform_floor_prepass.vert", "waveform_floor_vertex", "_prepass"),
    ("waveform_floor.frag", "waveform_floor_fragment", ""),
    ("waveform_floor_prepass.frag", "waveform_floor_fragment", "_prepass"),
    ("waveform_sky.vert", "waveform_sky_vertex", ""),
    ("waveform_sky_mirror.vert", "waveform_sky_vertex", "_mirror"),
    ("waveform_sky.frag", "waveform_sky_fragment", ""),
    ("waveform_sky_mirror.frag", "waveform_sky_fragment", "_mirror"),
    ("waveform_field.comp", "waveform_field", ""),
    ("waveform_medium.comp", "waveform_medium", ""),
    ("waveform_medium_mirror.comp", "waveform_medium", "_mirror"),
    ("waveform_fog_integrate.comp", "waveform_fog_integrate", ""),
    ("waveform_fog_integrate_mirror.comp", "waveform_fog_integrate", "_mirror"),
    ("waveform_give_section.comp", "waveform_give_section", ""),
    ("waveform_give_blur.comp", "waveform_give_blur", ""),
)


def body_text(text: str) -> str:
    """A converted text as its body file holds it: without its version line (the wrapper's first line)."""
    if not text.startswith(_VERSION):
        raise ValueError("a Waveform program's text starts with its version line")
    return text[len(_VERSION):]


def wrapper_text(body: str, variant: str) -> str:
    """A pass file: the version line, the variant's renames and the body's include."""
    renames = VARIANTS[variant]
    lines = [_VERSION.rstrip("\n"),
             f"// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): {body}"
             + (f", the {variant[1:]} variant (its members renamed, the arithmetic the body's)" if renames else "")]
    lines += [f"#define {old} {new}" for old, new in renames.items()]
    lines.append(f'#include "{body}.glsl"')
    return "\n".join(lines) + "\n"


def waveform_shader_files() -> dict[str, str]:
    """Every Waveform shader file's name and text: the bodies (``.glsl``) and the pass files."""
    files = {f"{name}.glsl": body_text(text) for name, text in _bodies().items()}
    files.update({name: wrapper_text(body, variant) for name, body, variant in PASS_FILES})
    return files


__all__ = ["MIRROR_MEMBERS", "PASS_FILES", "PREPASS_MEMBERS", "VARIANTS", "body_text", "mirror_name", "prepass_name",
           "waveform_shader_files", "wrapper_text"]
