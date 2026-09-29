"""Shared 3D scene GL helpers for Quick renderers.

Transitions use them today; a Visualizer mode may opt in (see
``Docs/Reference/Visualizer_Reference.md`` -> 3D scene foundation). The GLSL
library and its CPU mirrors live in ``rendering.gl_programs.scene3d``.

* ``frame`` -- the item-quad vertex source, the frame protocol and pixel rects (pure);
* ``resources`` -- context-local programs, meshes, image underlay, depth clear;
* ``target`` -- the multisampled ``SceneTarget`` for any pixel rect;
* ``post`` -- bloom on emitted light (``BloomChain``);
* ``motion`` -- motion blur along each surface's screen motion (``MotionBlur``);
* ``particles`` -- the shared additive particle pass and its tier budget;
* ``shadows`` -- the shared MIN-blended planar shadow pass;
* ``grid`` -- the bendable grid surface (drawn around an effect's displacement);
* ``uniforms`` -- per-frame uniform blocks;
* ``passes`` -- blend scopes.

Nothing here owns a clock, state or Settings; every GL handle belongs to the
consuming renderer and its legal render thread.
"""
