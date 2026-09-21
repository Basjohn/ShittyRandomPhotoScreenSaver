"""Quick Slide renderer with one seam-proof cardinal coverage partition."""

from __future__ import annotations

import math

from OpenGL import GL as gl

from rendering.quick.render.gl_resources import compile_program
from ..render_contract import (
    QUICK_TRANSITION_VERTEX_SOURCE,
    QuickTransitionRenderFrame,
)


_DIRECTION_VECTORS = {
    "left": (-1.0, 0.0),
    "right": (1.0, 0.0),
    "up": (0.0, -1.0),
    "down": (0.0, 1.0),
}
_MOTION_STYLE_CODES = {
    "Linear": 0,
    "Elastic": 1,
    "Wobble": 2,
    "Flex": 3,
    "Perspective Push": 4,
}


_SLIDE_FRAGMENT_SOURCE = """#version 410 core
in vec2 vUv;
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_progress;
uniform vec2 u_direction;
uniform int u_motionStyle;
uniform vec2 uItemSize;

float settledSegment(float q) {
    return q*q*q*(q*(6.0*q - 15.0) + 10.0);
}
float elasticArrival(float t) {
    // Position, velocity and acceleration agree at every join. The old late
    // spring branch jumped from speed 1 to 10 at .78, producing a sudden kick.
    if (t < 0.78) return 1.018 * settledSegment(t / 0.78);
    if (t < 0.90) return mix(1.018, 0.995, settledSegment((t - 0.78) / 0.12));
    return mix(0.995, 1.0, settledSegment((t - 0.90) / 0.10));
}

// Intersect the view ray for this output pixel with a shallow, tilted source
// card.  This is a projective image mapping, not an affine UV skew: a plane
// nearer the virtual camera expands and a plane farther away contracts.
vec3 rotateRodrigues(vec3 value, vec3 axis, float angle) {
    return value * cos(angle) + cross(axis, value) * sin(angle)
        + axis * dot(axis, value) * (1.0 - cos(angle));
}
vec2 perspectivePushUv(vec2 localUv, vec2 direction, float t) {
    float aspect = uItemSize.x / max(uItemSize.y, 1.0);
    vec2 screen = (localUv - 0.5) * vec2(2.0 * aspect, 2.0);
    vec3 rayOrigin = vec3(0.0, 0.0, 2.4);
    vec3 rayDirection = normalize(vec3(screen, -2.4));
    float envelope = sin(3.141592653589793 * t);
    envelope *= envelope;
    vec2 physicalDirection = normalize(vec2(direction.x * aspect, direction.y));
    vec3 cardCenter = vec3(-physicalDirection * (0.25 * envelope), -0.10 * envelope);
    vec3 axis = abs(direction.x) > 0.5
        ? vec3(0.0, 1.0, 0.0)
        : vec3(1.0, 0.0, 0.0);
    float tilt = 0.32 * envelope * (direction.x + direction.y);
    vec3 normal = rotateRodrigues(vec3(0.0, 0.0, 1.0), axis, tilt);
    float denom = dot(rayDirection, normal);
    float distance = dot(cardCenter - rayOrigin, normal) / denom;
    vec3 hit = rayOrigin + rayDirection * distance;
    vec3 tangent = abs(direction.x) > 0.5
        ? normalize(cross(axis, normal))
        : normalize(cross(normal, axis));
    vec3 relative = hit - cardCenter;
    vec2 card = abs(direction.x) > 0.5
        ? vec2(dot(relative, tangent), dot(relative, axis))
        : vec2(dot(relative, axis), dot(relative, tangent));
    return clamp(card * vec2(0.5 / aspect, 0.5) + 0.5, 0.0, 1.0);
}

void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    float t = clamp(u_progress, 0.0, 1.0);
    if (t <= 0.0) {
        FragColor = texture(uOldTex, uv);
        return;
    }
    if (t >= 1.0) {
        FragColor = texture(uNewTex, uv);
        return;
    }
    float travel = u_motionStyle == 1 ? elasticArrival(t) : t;
    float orthogonalAxis = abs(u_direction.x) > 0.5 ? uv.y : uv.x;
    if (u_motionStyle == 3) {
        float envelope = sin(3.141592653589793 * t);
        travel += 0.065 * envelope * envelope
            * sin(6.283185307179586 * orthogonalAxis);
    }

    // Both images use the same sample and exactly one owner. During Elastic's
    // arrival overshoot, its full destination surface clamps at the departing
    // edge so an opposite texture strip cannot wrap into view.
    vec2 shiftedUv = uv - u_direction * travel;
    vec2 localUv = travel > 1.0
        ? clamp(uv - u_direction * (travel - 1.0), 0.0, 1.0)
        : fract(shiftedUv);
    if (u_motionStyle == 2) {
        float envelope = sin(3.141592653589793 * t);
        float wobble = 0.012 * envelope * envelope * (
            sin(12.566370614359172 * orthogonalAxis)
            + 0.5 * sin(25.132741228718345 * orthogonalAxis)
        );
        if (abs(u_direction.x) > 0.5) {
            localUv.y = clamp(localUv.y + wobble, 0.0, 1.0);
        } else {
            localUv.x = clamp(localUv.x + wobble, 0.0, 1.0);
        }
    }
    float axis = abs(u_direction.x) > 0.5 ? uv.x : uv.y;
    float signedDirection = u_direction.x + u_direction.y;
    float destinationOwns = travel >= 1.0 ? 1.0 : (signedDirection < 0.0
        ? step(1.0 - travel, axis)
        : 1.0 - step(travel, axis));

    if (u_motionStyle == 4) {
        // The destination remains a full, moving underlay.  The partition
        // remains the sole coverage owner while the outgoing source uses its
        // true plane intersection above.
        localUv = travel > 1.0 ? clamp(shiftedUv, 0.0, 1.0) : fract(shiftedUv);
    }
    // Keep the established styles on their exact shared sample. Perspective
    // Push replaces only the outgoing card's image mapping.
    vec4 oldColor = texture(uOldTex, localUv);
    if (u_motionStyle == 4) {
        oldColor = texture(uOldTex, perspectivePushUv(localUv, u_direction, t));
    }
    vec4 newColor = texture(uNewTex, localUv);
    FragColor = mix(oldColor, newColor, destinationOwns);
}
"""


def _slide_motion_style(style: object) -> str:
    value = "Linear" if style is None else str(style).strip()
    if value not in _MOTION_STYLE_CODES:
        raise ValueError(f"unknown canonical Slide motion style: {style!r}")
    return value


def _slide_elastic_arrival(canonical_time: float) -> float:
    """Continuous travel and settlement with exact endpoints and C2 joins."""

    t = max(0.0, min(1.0, float(canonical_time)))
    if t == 0.0 or t == 1.0:
        return t
    if t < 0.78:
        start, end, q = 0.0, 1.018, t / 0.78
    elif t < 0.90:
        start, end, q = 1.018, 0.995, (t - 0.78) / 0.12
    else:
        start, end, q = 0.995, 1.0, (t - 0.90) / 0.10
    blend = q*q*q*(q*(6.0*q - 15.0) + 10.0)
    return start + (end - start) * blend


def _slide_direction_vector(direction: object) -> tuple[float, float]:
    """Resolve one of Slide's four product-supported cardinal directions."""

    value = "left" if direction is None else str(direction).strip().lower()
    vector = _DIRECTION_VECTORS.get(value)
    if vector is None:
        raise ValueError(f"unknown canonical Slide direction: {direction!r}")
    return vector


def _slide_perspective_card_uv(
    local_uv: tuple[float, float], direction: object, progress: float,
    logical_size: tuple[float, float],
) -> tuple[float, float]:
    """CPU reference for Perspective Push's aspect-correct ray/plane mapping."""

    x, y = (float(value) for value in local_uv)
    width, height = (float(value) for value in logical_size)
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0) or width <= 0.0 or height <= 0.0:
        raise ValueError("Perspective Push requires normalized UVs and positive size")
    dx, dy = _slide_direction_vector(direction)
    t = max(0.0, min(1.0, float(progress)))
    envelope = math.sin(math.pi * t) ** 2
    aspect = width / height
    ray_origin = (0.0, 0.0, 2.4)
    ray_direction = _normalize3(((x - 0.5) * 2.0 * aspect, (y - 0.5) * 2.0, -2.4))
    physical_direction = _normalize2((dx * aspect, dy))
    card_center = (-physical_direction[0] * 0.25 * envelope, -physical_direction[1] * 0.25 * envelope, -0.10 * envelope)
    axis = (0.0, 1.0, 0.0) if dx else (1.0, 0.0, 0.0)
    normal = _rodrigues((0.0, 0.0, 1.0), axis, 0.32 * envelope * (dx + dy))
    distance = _dot3(_subtract3(card_center, ray_origin), normal) / _dot3(ray_direction, normal)
    hit = _add3(ray_origin, _scale3(ray_direction, distance))
    tangent = _normalize3(_cross3(axis, normal) if dx else _cross3(normal, axis))
    relative = _subtract3(hit, card_center)
    card = (
        (_dot3(relative, tangent), _dot3(relative, axis))
        if dx else (_dot3(relative, axis), _dot3(relative, tangent))
    )
    return (
        max(0.0, min(1.0, card[0] * 0.5 / aspect + 0.5)),
        max(0.0, min(1.0, card[1] * 0.5 + 0.5)),
    )


def _normalize2(value: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(*value)
    return (value[0] / length, value[1] / length)


def _normalize3(value: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(_dot3(value, value))
    return tuple(component / length for component in value)  # type: ignore[return-value]


def _dot3(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _cross3(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:
    return (left[1] * right[2] - left[2] * right[1], left[2] * right[0] - left[0] * right[2], left[0] * right[1] - left[1] * right[0])


def _subtract3(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(a - b for a, b in zip(left, right))  # type: ignore[return-value]


def _add3(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(a + b for a, b in zip(left, right))  # type: ignore[return-value]


def _scale3(value: tuple[float, float, float], scale: float) -> tuple[float, float, float]:
    return tuple(component * scale for component in value)  # type: ignore[return-value]


def _rodrigues(value: tuple[float, float, float], axis: tuple[float, float, float], angle: float) -> tuple[float, float, float]:
    cosine, sine = math.cos(angle), math.sin(angle)
    crossed, dot = _cross3(axis, value), _dot3(axis, value)
    return tuple(value[index] * cosine + crossed[index] * sine + axis[index] * dot * (1.0 - cosine) for index in range(3))  # type: ignore[return-value]


def _slide_partition_sample(
    direction: object,
    progress: float,
    coordinate: tuple[float, float],
    motion_style: object = "Linear",
) -> tuple[str, tuple[float, float]]:
    """Return the sole image owner and shared local UV for one output point."""

    x, y = (float(value) for value in coordinate)
    if not 0.0 <= x < 1.0 or not 0.0 <= y < 1.0:
        raise ValueError("Slide coverage coordinates must be normalized pixel centres")
    dx, dy = _slide_direction_vector(direction)
    style = _slide_motion_style(motion_style)
    t = max(0.0, min(1.0, float(progress)))
    if t == 0.0:
        return "source", (x, y)
    if t == 1.0:
        return "destination", (x, y)
    if style == "Elastic":
        amount = _slide_elastic_arrival(t)
    elif style == "Flex":
        perpendicular = y if dx else x
        amount = t + 0.065 * math.sin(math.pi * t)**2 * math.sin(2.0 * math.pi * perpendicular)
    else:
        amount = t
    axis = x if dx else y
    signed_direction = dx + dy
    if amount >= 1.0:
        destination_owns = True
    elif signed_direction < 0.0:
        destination_owns = axis >= 1.0 - amount
    else:
        destination_owns = axis < amount
    shifted_uv = (x - dx * amount, y - dy * amount)
    if amount > 1.0:
        arrived_uv = (x - dx * (amount - 1.0), y - dy * (amount - 1.0))
        local_uv = tuple(max(0.0, min(1.0, value)) for value in arrived_uv)
    else:
        local_uv = tuple(value % 1.0 for value in shifted_uv)
    if style == "Wobble":
        perpendicular = y if dx else x
        wobble = 0.012 * math.sin(math.pi * t)**2 * (
            math.sin(4.0 * math.pi * perpendicular)
            + 0.5 * math.sin(8.0 * math.pi * perpendicular)
        )
        if dx:
            local_uv = (local_uv[0], max(0.0, min(1.0, local_uv[1] + wobble)))
        else:
            local_uv = (max(0.0, min(1.0, local_uv[0] + wobble)), local_uv[1])
    return ("destination" if destination_owns else "source"), local_uv


class QuickSlideRenderer:
    transition_id = "slide"

    def __init__(self) -> None:
        self._program = 0
        self._uniforms: dict[str, int] = {}

    @property
    def has_resources(self) -> bool:
        return bool(self._program)

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        if not self._program:
            self._initialize()
        uniforms = self._uniforms
        progress = float(frame.sample.eased_progress)
        direction = _slide_direction_vector(frame.run.request.direction)
        motion_style = _slide_motion_style(
            frame.run.request.parameter_dict()["motion_style"]
        )

        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"],
            1,
            gl.GL_FALSE,
            frame.matrix_values,
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform1f(uniforms["u_progress"], progress)
        gl.glUniform2f(uniforms["u_direction"], *direction)
        gl.glUniform1i(uniforms["u_motionStyle"], _MOTION_STYLE_CODES[motion_style])
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.source_texture_id)
        gl.glUniform1i(uniforms["uOldTex"], 0)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.destination_texture_id)
        gl.glUniform1i(uniforms["uNewTex"], 1)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        if not self._program:
            return
        gl.glDeleteProgram(self._program)
        self._program = 0
        self._uniforms.clear()

    def _initialize(self) -> None:
        program = compile_program(
            QUICK_TRANSITION_VERTEX_SOURCE,
            _SLIDE_FRAGMENT_SOURCE,
            label="Quick Slide",
        )
        self._program = program
        try:
            uniform_names = (
                "uMatrix",
                "uItemSize",
                "u_progress",
                "u_direction",
                "u_motionStyle",
                "uOldTex",
                "uNewTex",
            )
            uniforms = {
                name: int(gl.glGetUniformLocation(program, name))
                for name in uniform_names
            }
            required = (
                "uMatrix",
                "uItemSize",
                "u_progress",
                "u_direction",
                "u_motionStyle",
                "uOldTex",
                "uNewTex",
            )
            missing = [name for name in required if uniforms[name] < 0]
            if missing:
                raise RuntimeError(
                    "Quick Slide uniforms are incomplete: " + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_transition_renderer() -> QuickSlideRenderer:
    return QuickSlideRenderer()
