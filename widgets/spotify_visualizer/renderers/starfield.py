"""Starfield mode uniform renderer."""
from __future__ import annotations


def get_uniform_names() -> list[str]:
    return [
        "u_star_density", "u_travel_speed", "u_star_reactivity",
        "u_travel_time",
        "u_nebula_tint1", "u_nebula_tint2", "u_nebula_cycle_speed",
        # Energy bands
        "u_overall_energy", "u_bass_energy", "u_mid_energy", "u_high_energy",
    ]


def upload_uniforms(gl, u: dict, s) -> bool:
    _set1f(gl, u, "u_star_density", s._star_density)
    _set1f(gl, u, "u_travel_speed", s._travel_speed)
    _set1f(gl, u, "u_star_reactivity", s._star_reactivity)
    _set1f(gl, u, "u_travel_time", s._starfield_travel_time)

    loc = u.get("u_nebula_tint1", -1)
    if loc >= 0:
        nt1 = s._nebula_tint1
        gl.glUniform3f(loc, float(nt1.redF()), float(nt1.greenF()), float(nt1.blueF()))
    loc = u.get("u_nebula_tint2", -1)
    if loc >= 0:
        nt2 = s._nebula_tint2
        gl.glUniform3f(loc, float(nt2.redF()), float(nt2.greenF()), float(nt2.blueF()))

    _set1f(gl, u, "u_nebula_cycle_speed", s._nebula_cycle_speed)

    # Energy bands
    eb = s._energy_bands
    _set1f(gl, u, "u_overall_energy", eb.overall)
    _set1f(gl, u, "u_bass_energy", eb.bass)
    _set1f(gl, u, "u_mid_energy", eb.mid)
    _set1f(gl, u, "u_high_energy", eb.high)

    return True


def _set1f(gl, u, name, val):
    loc = u.get(name, -1)
    if loc >= 0:
        gl.glUniform1f(loc, float(val))
