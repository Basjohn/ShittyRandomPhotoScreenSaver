"""Dependency-free shader-interface guard for Extruded Bubble.

The GL renderer's programs must also compile/link on the operator's OpenGL 4.6 context. This guard catches
vertex output assignments without a corresponding declaration before any Qt/OpenGL imports or visual capture.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
import unittest


_PROGRAM = Path(__file__).resolve().parents[1] / 'rendering/gl_programs/extruded_bubble_program.py'


def _literal_fragments(expression: ast.expr) -> str:
    """Extract a vertex shader's own GLSL literal text; linked GLSL helper imports aren't relevant to output declarations."""
    if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        return expression.value
    if isinstance(expression, ast.BinOp) and isinstance(expression.op, ast.Add):
        return _literal_fragments(expression.left) + _literal_fragments(expression.right)
    return ''


def _vertex_stages() -> dict[str, str]:
    source = ast.parse(_PROGRAM.read_text(encoding='utf-8'))
    named = {}
    for node in source.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('FULL_VERTEX', 'BUBBLE_VERTEX', 'CLUSTER_VERTEX',
                                                                  'PARTICLE_VERTEX'):
                    named[target.id] = _literal_fragments(node.value)
    return named


class ExtrudedBubbleShaderContractTests(unittest.TestCase):
    def test_each_vertex_varying_assignment_has_an_output_declaration(self):
        stages = _vertex_stages()
        self.assertEqual(set(stages), {'FULL_VERTEX', 'BUBBLE_VERTEX', 'CLUSTER_VERTEX', 'PARTICLE_VERTEX'})
        for stage, source in stages.items():
            writes = set(re.findall(r'\b(v[A-Z]\w*)\s*(?:\[[^]]+\])?\s*=(?!=)', source))
            declarations = set(re.findall(r'\b(?:flat\s+)?out\s+\w+\s+(v[A-Z]\w*)\b', source))
            self.assertFalse(writes - declarations, f'{stage}: undeclared vertex outputs {writes - declarations}')

    def test_bead_fade_output_is_not_written_by_cluster_or_particle_shaders(self):
        stages = _vertex_stages()
        self.assertIn('flat out float vOpacity;', stages['BUBBLE_VERTEX'])
        self.assertIn('vOpacity = aOpacity;', stages['BUBBLE_VERTEX'])
        self.assertNotIn('vOpacity', stages['CLUSTER_VERTEX'])
        self.assertNotIn('vOpacity', stages['PARTICLE_VERTEX'])


    def test_near_dof_is_selected_by_regular_bubbles_true_front_depth_not_an_identity_cohort(self):
        stages = _vertex_stages()
        vertex = stages['BUBBLE_VERTEX']
        self.assertIn('float frontDepth = depth - aSphere.w;', vertex)
        self.assertIn('aExtra.y < 0.5 && coc > 1.5', vertex)
        self.assertIn('sceneNearCircle(frontDepth, uFocus, uAperture, uNearCoc)', vertex)
        self.assertNotIn('aExtra.y > 2.5 ||', vertex)
        source = _PROGRAM.read_text(encoding='utf-8')
        self.assertIn('float frontDepth = -vSphere.z - vSphere.w;', source)
        self.assertIn('sceneDefocusWrite(', source)



if __name__ == '__main__':
    unittest.main()
