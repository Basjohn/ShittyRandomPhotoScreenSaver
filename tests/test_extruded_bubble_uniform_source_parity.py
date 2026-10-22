"""Unaccepted EB integration regression: exact shaft vec4 crash, shared physical path.

Qt-free: python tests/test_extruded_bubble_uniform_source_parity.py
The test is *not* native Windows GL 4.6 or visual acceptance.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RENDER = ROOT / 'rendering/quick/visualizer/implementations/extruded_bubble.py'
SHADER = ROOT / 'rendering/gl_programs/extruded_bubble_program.py'


def _uploader():
    # Compile the actual _Uniforms class without importing the Qt/PyOpenGL render
    # host, whose runtime import prerequisites are unavailable in this harness.
    tree = ast.parse(RENDER.read_text(encoding='utf-8'))
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == '_Uniforms')

    class FakeGL:
        def __init__(self):
            self.calls = []
        def glGetUniformLocation(self, program, name):
            self.calls.append(('location', program, name))
            return 4
        def glProgramUniform4f(self, program, location, *values):
            self.calls.append(('vec4', program, location, *values))
        def glProgramUniform3f(self, program, location, *values):
            self.calls.append(('vec3', program, location, *values))
        def glProgramUniform1f(self, program, location, value):
            self.calls.append(('float', program, location, value))

    gl = FakeGL()
    namespace = {'gl': gl, '_UNSET': object()}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[klass], type_ignores=[])), str(RENDER), 'exec'), namespace)
    return namespace['_Uniforms'](), gl


class EBSourceAndUploadTests(unittest.TestCase):
    def test_exact_four_component_ray_block_uniform_never_crashes(self):
        uploader, gl = _uploader()
        exact = (-10.840106010437012, 1.3623005151748657,
                 -17.55120849609375, 0.052287131547927856)
        uploader.set(9, {'uBlock0': exact})
        self.assertIn(('vec4', 9, 4, *exact), gl.calls)
        original_count = len(gl.calls)
        uploader.set(9, {'uBlock0': exact})
        self.assertEqual(len(gl.calls), original_count, 'unchanged uniform should not be reuploaded')
        uploader.set(9, {'uBlock0': (1., 2., 3., 4.)})
        self.assertIn(('vec4', 9, 4, 1., 2., 3., 4.), gl.calls)

    def test_failed_upload_never_poison_uniform_cache(self):
        uploader, _ = _uploader()
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, 'unsupported value'):
                uploader.set(7, {'uBlock1': (1., 2., 3., 4., 5.)})
            self.assertNotIn((7, 'uBlock1'), uploader._values)

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
        self.assertIn('vec3 centre = vec3(ebWake[owner * 8]', glsl,
                      'attached fizz must retain parent source and retirement owner')
        self.assertNotIn('speck_path = admit_path', render, 'shared stream paths should have one admitted owner')


if __name__ == '__main__':
    unittest.main()
