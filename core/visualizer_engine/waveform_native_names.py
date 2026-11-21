"""Waveform Ribbon's native member names (N5.4): the one rule naming each pass file's block member and the record or
settings field that fills it. The shader files (``rendering.gl_programs.waveform_shader_files``), the generated members
table and the native schema (``waveform_native_schema``) all read it; it imports nothing of theirs."""
from __future__ import annotations

import re

#: A pass whose members hold another pass's values names them as that pass does (one record field fills both): pass id
#: -> (the pass it shares, the members it keeps its own). The floor's reduced pre-pass draws the floor's members
#: (``waveform_plan.floor_prepass``) but its viewport and specular mode, the card's (the core's schema holds at most 256
#: fields).
SHARED_MEMBERS = {"floor_prepass": ("floor", frozenset({"uViewport", "uSpecMode"}))}


def member_name(pass_id: str, member: str) -> str:
    """A pass file's block member name, the record or settings field that fills it: ``<pass>_<member>`` in the core's
    field-name form, lower case words joined by ``_`` (``member_name("ribbon", "uMvp")`` -> ``ribbon_u_mvp``), or the
    shared pass's (``SHARED_MEMBERS``)."""
    shared = SHARED_MEMBERS.get(pass_id)
    if shared is not None and member not in shared[1]:
        pass_id = shared[0]
    return f"{pass_id}_{re.sub(r'(?<!^)(?=[A-Z])', '_', member).lower()}"


__all__ = ["SHARED_MEMBERS", "member_name"]
