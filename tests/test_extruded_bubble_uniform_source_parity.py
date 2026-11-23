"""Unaccepted EB integration regression: exact shaft vec4 crash, shared physical path.

Qt-free: python tests/test_extruded_bubble_uniform_source_parity.py
The test is *not* native Windows GL 4.6 or visual acceptance.
"""
from __future__ import annotations

import ast
from pathlib import Path
import struct
import unittest

from rendering.gl_programs.extruded_bubble_program import FULLSCREEN_BLOCK
from rendering.gl_programs.scene3d import _STD140

ROOT = Path(__file__).resolve().parents[1]
RENDER = ROOT / 'rendering/quick/visualizer/implementations/extruded_bubble.py'
SHADER = ROOT / 'rendering/gl_programs/extruded_bubble_program.py'


def _uploader():
    # Compile the actual _Uniforms class without importing the Qt/PyOpenGL render
    # host, whose runtime import prerequisites are unavailable in this harness.
    tree = ast.parse(RENDER.read_text(encoding='utf-8'))
    declarations = [n for n in tree.body if getattr(n, "name", None) in {"_Uniforms", "_members"}]
    namespace = {'_UNSET': object(), '_STD140': _STD140, 'struct': struct}
    exec(compile(ast.fix_missing_locations(ast.Module(body=declarations, type_ignores=[])), str(RENDER), 'exec'), namespace)
    uploader = namespace['_Uniforms']()
    uploader.register(9, FULLSCREEN_BLOCK, bytes(FULLSCREEN_BLOCK.size))
    return uploader


class EBSourceAndUploadTests(unittest.TestCase):
    def test_exact_four_component_ray_block_uniform_never_crashes(self):
        uploader = _uploader()
        exact = (-10.840106010437012, 1.3623005151748657,
                 -17.55120849609375, 0.052287131547927856)
        offset = next(offset for (name, _), offset in zip(FULLSCREEN_BLOCK.fields, FULLSCREEN_BLOCK.offsets)
                      if name == 'uBlock0')
        uploader.set(9, {'uBlock0': exact})
        original = uploader.packed(9)
        self.assertEqual(struct.unpack_from('<4f', original, offset), exact)
        uploader.set(9, {'uBlock0': exact})
        self.assertEqual(uploader.packed(9), original)
        uploader.set(9, {'uBlock0': (1., 2., 3., 4.)})
        self.assertEqual(struct.unpack_from('<4f', uploader.packed(9), offset), (1., 2., 3., 4.))

    def test_failed_upload_never_poison_uniform_cache(self):
        uploader = _uploader()
        for _ in range(2):
            with self.assertRaises(struct.error):
                uploader.set(9, {'uBlock1': (1., 2., 3., 4., 5.)})
            self.assertNotIn((9, 'uBlock1'), uploader._values)

    def test_all_free_populations_have_authored_source_and_exit(self):
        glsl = SHADER.read_text(encoding='utf-8')
        render = RENDER.read_text(encoding='utf-8')
        self.assertIn('uniform vec3 uStreamSource;', glsl)
        self.assertIn('uniform vec3 uStreamEnd;', glsl)
        self.assertTrue('pathEnabled ? mix(uStreamSource, uStreamEnd, progress)' in glsl,
                        'BEAM chains must retain their authored path inside the SCENE/BEAM choice')
        self.assertTrue('sceneEntry.xyz + along * s' in glsl,
                        'SCENE chains must retain their physical upstream-face path')
        self.assertIn('p = mix(uStreamSource, uStreamEnd, progress)', glsl)
        self.assertIn('1.0 - smoothstep(0.84, 1.0, progress)', glsl)
        self.assertIn('1.0 - smoothstep(0.82, 1.0, progress)', glsl)
        self.assertIn('"uStreamSource": stream_source, "uStreamEnd": stream_end', render)
        self.assertIn('"uSpeckSource": stream_source, "uSpeckEnd": stream_end', render)
        self.assertIn('vec3 centre = vec3(ebWake[owner * WAKE_STRIDE]', glsl,
                      'attached fizz must retain parent source and retirement owner')
        self.assertNotIn('speck_path = admit_path', render, 'shared stream paths should have one admitted owner')


if __name__ == '__main__':
    unittest.main()
