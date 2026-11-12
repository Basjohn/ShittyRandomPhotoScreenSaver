"""N1.7: no texture, render target or storage image in the renderer uses a format QRhi lacks (RG16F, RG32F,
R11G11B10F; ``QRhiTexture::Format`` in Qt 6.12 has none of them), except the targets D5.3's formats service takes
because widening them measurably costs (Docs/Future_Work/Native_Core_P3_Decisions.md, D5.3 and D5.6 row 13).

The scan reads every source file under ``rendering/`` (never a fixed module list), both the GL enums the Python
allocates with and the image formats GLSL declares, so a new two-channel float target fails here until it is widened
to RGBA16F/RGBA32F or the service list (decided in the plan, with its measurement) names it.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A format QRhi has no member for, as the GL enum or as a GLSL image layout qualifier.
_MISSING = re.compile(r"\bGL_(RG16F|RG32F|R11F_G11F_B10F)\b|layout\s*\([^)]*\b(rg16f|rg32f|r11f_g11f_b10f)\b")

# D5.3's formats service (N1.7, 12 Nov 2026): the scene target's multisampled velocity attachment stays RG16F
# (RGBA16F would add 127.5 MiB per 3840x2160 display at 4x and 255 MiB at 8x). (file, a text the line holds).
_FORMAT_SERVICE = (("rendering/quick/scene3d/target.py", '_allocate_attachment("velocity"'),)


def missing_format_lines(text: str) -> list[tuple[int, str]]:
    """(line number, line) of every use of a format QRhi lacks in ``text``."""
    return [(number, line.strip()) for number, line in enumerate(text.splitlines(), 1) if _MISSING.search(line)]


def _uses():
    for path in sorted((ROOT / "rendering").rglob("*")):
        if path.suffix not in (".py", ".glsl", ".frag", ".vert", ".comp"):
            continue
        relative = path.relative_to(ROOT).as_posix()
        for number, line in missing_format_lines(path.read_text(encoding="utf-8", errors="ignore")):
            yield relative, number, line


def test_no_renderer_texture_uses_a_format_qrhi_lacks_outside_the_formats_service():
    uses = list(_uses())
    unlisted = [use for use in uses if not any(use[0] == path and text in use[2] for path, text in _FORMAT_SERVICE)]
    assert not unlisted, f"formats QRhi lacks (widen to RGBA16F/RGBA32F, N1.7): {unlisted}"
    # Every service entry still names a real use (a stale entry would hide nothing and must go).
    for path, text in _FORMAT_SERVICE:
        assert any(use[0] == path and text in use[2] for use in uses), (path, text)


def test_the_scan_sees_each_missing_format_in_both_spellings():
    # The scan cannot pass vacuously: each format is found as a GL enum and as a GLSL image layout, and the widened
    # forms are not.
    for enum, glsl in (("GL_RG16F", "rg16f"), ("GL_RG32F", "rg32f"), ("GL_R11F_G11F_B10F", "r11f_g11f_b10f")):
        assert missing_format_lines(f"texture = allocate(gl.{enum}, width, height)")
        assert missing_format_lines(f"layout({glsl}, binding = 1) writeonly uniform image2D uOut;")
    assert not missing_format_lines("allocate(gl.GL_RGBA16F); allocate(gl.GL_RGBA32F); allocate(gl.GL_R16F)")
    assert not missing_format_lines("layout(rgba16f, binding = 1) writeonly uniform image2D uOut;\n"
                                    "layout(r16f, binding = 2) readonly uniform image2D uIn;")
