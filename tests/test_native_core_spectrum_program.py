"""N2.5 round 4's proof of the standing port rule on the built module: a Settings-only uniform added to Spectrum's
shader reaches the native item with no module rebuild.

A copy of ``spectrum.frag`` gains a member ``u_test_tint`` (a value that would come from Settings), is baked by
``tools/regen_qrc.py``'s own baker, and is handed to the module at run time: the core packs the new value at the
member's reflected offset (GPU-free, ``spectrum_block``). Negative control: the module's compiled-in copy, the old path,
cannot see the member and refuses the name. The drawn proof (the copy drawing the value) is spectrum_check's
``program`` round. Every reflected member of the product pack is filled by the settings or the core's frame members.
"""
from __future__ import annotations

import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from rendering.native import loader

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "release" / "native_module"
BUILT = os.name == "nt" and (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()

pytestmark = pytest.mark.skipif(
    not BUILT,
    reason=f"the native core is not built in this checkout: no release/native_module/{loader.MODULE_NAME}.pyd",
)

#: The member a Settings-only change adds, and the line that reads it (so a drawn frame shows it).
TEST_MEMBER = "    float u_test_tint;             // N2.5 round 4's proof: a Settings-only uniform\n"
TEST_READ = "    if (u_test_tint > 0.5) { fragColor = vec4(1.0, 0.0, 1.0, 1.0); return; }\n"


def tinted_pack(folder: Path) -> bytes:
    """``spectrum.frag`` with ``u_test_tint`` added, baked by regen_qrc's baker (no module build)."""
    from tools import regen_qrc

    source = regen_qrc.mode_shader_dir() / "spectrum.frag"
    text = source.read_text(encoding="utf-8")
    anchor = "    vec2 u_target_px;"
    assert text.count(anchor) == 1 and text.count("void main() {") == 1
    text = text.replace(anchor, TEST_MEMBER + anchor).replace("void main() {", "void main() {\n" + TEST_READ)
    copy = Path(folder) / "spectrum.frag"
    copy.write_text(text, encoding="utf-8")
    pack = Path(folder) / "spectrum.frag.qsb"
    regen_qrc._bake_quick_shader(regen_qrc.quick_shader_baker(sys.executable), copy, pack,
                                 regen_qrc.quick_shader_targets(), subprocess.run)
    return pack.read_bytes()


def _frame():
    """One real frame's record, card and settings (the Python renderer's own settings arithmetic)."""
    from core.visualizer_engine import spectrum_native_schema
    from rendering.native.composite import composite_geometry
    from rendering.native.spectrum import spectrum_presentation
    from rendering.quick.visualizer.implementations.spectrum import spectrum_settings_values
    from tests.test_native_program_values import _snapshot

    snapshot = _snapshot()
    presentation = snapshot.presentation
    card = spectrum_presentation(presentation, composite_geometry(presentation), window_size=(1920.0, 1080.0),
                                 window_pixels=(1920, 1080))
    settings = spectrum_settings_values(
        snapshot.logical, presentation, item_size=card["item_size"], oriented_size=card["oriented_size"],
        content_rotation_quarters=card["quarters"], content_rect=card["content_rect"],
        item_from_window=card["item_from_window"], window_from_target=card["window_from_target"],
        target_px=card["target_size"])
    return spectrum_native_schema.encode(snapshot.logical), card, settings


@pytest.fixture(scope="module")
def core():
    from rendering import native

    return native.load(MODULE_DIR)


@pytest.mark.qt
def test_a_settings_only_uniform_reaches_the_native_block_with_no_rebuild(core, tmp_path, qt_app):
    pack = tinted_pack(tmp_path)
    record, card, settings = _frame()
    layout = core.spectrum_block_layout(pack)
    member = next(row for row in layout["members"] if row[0] == "u_test_tint")
    offset = member[2]
    block, facts = core.spectrum_block(record, card, pack, dict(settings, u_test_tint=0.75))
    assert block is not None, facts
    assert struct.unpack_from("<f", block, offset)[0] == 0.75
    assert facts["unfilled"] == [] and not facts["compiled_in"]
    # The product pack itself: every member filled by the settings or the core's frame members.
    from rendering.native.program_values import mode_fragment_pack

    product_pack = mode_fragment_pack("spectrum")
    product = core.spectrum_block_layout(product_pack)
    block, facts = core.spectrum_block(record, card, product_pack, settings)
    assert block is not None and facts["unfilled"] == [], facts
    assert set(product["frame_members"]).isdisjoint(settings)
    # Negative control: the compiled-in copy (the old path) has no such member and refuses the name.
    with pytest.raises(ValueError, match="u_test_tint"):
        core.spectrum_block(record, card, None, dict(settings, u_test_tint=0.75))


@pytest.mark.qt
def test_an_unknown_name_or_a_frame_member_is_refused(core, qt_app):
    from rendering.native.program_values import mode_fragment_pack

    record, card, settings = _frame()
    pack = mode_fragment_pack("spectrum")
    with pytest.raises(ValueError, match="u_no_such_member"):
        core.spectrum_block(record, card, pack, dict(settings, u_no_such_member=1.0))
    with pytest.raises(ValueError, match="u_bars"):
        core.spectrum_block(record, card, pack, dict(settings, u_bars=[0.5]))
    # An unfilled member is reported (the harness's error): a setting left out.
    partial = {name: value for name, value in settings.items() if name != "u_fill_color"}
    _block, facts = core.spectrum_block(record, card, pack, partial)
    assert facts["unfilled"] == ["u_fill_color"]
