"""Waveform's physical camera view and the part of the scene axis it shows. Pure: no Qt/GL/clock.

The renderer draws with ``physical_view``; the logical capture sizes the travelling pulse from ``visible_span`` of that
very frustum (``core.waveform_ribbon_dynamics.VIEW_MARGIN``). The aperture is the CUSTOM edge-resize sensor scale
(``presentation_geometry.framed_aperture_scale``): a larger card reveals more world, so a 1282x1005 card shows about
x in [-16, 16] where the canonical 420x280 card shows about [-5, 5].
"""
from __future__ import annotations
from collections.abc import Mapping
import numpy as np
from core.settings import framed_camera as fc
from core.settings.waveform_ribbon_camera import NEAR, FAR
from core.waveform_ribbon_scene import SPEC


def physical_view(parameters,aspect,aperture_scale=1.,*,zoom=1.):
    """``zoom`` scales the visible extent (Dynamic Zoom); the physical eye, pose and world never move.

    Perspective is the only projection (Orthographic retired 5 Nov 2026); ``lens`` is the tangent pair."""
    fov=float(parameters['waveform_ribbon_camera_fov'])
    axes,eye,_=fc.resolve_camera_frame(SPEC,parameters)
    right,up,back=(np.asarray(axes[i:i+3]) for i in (0,3,6))
    view=np.identity(4);view[0,:3],view[1,:3],view[2,:3]=right,up,back
    view[:3,3]=-view[:3,:3]@np.asarray(eye)
    tangents=fc.viewport_tangents(fov,aspect,aperture_scale,SPEC.fov_range)
    lens=(tangents[0]*zoom,tangents[1]*zoom);projection=fc.perspective_matrix(lens,NEAR,FAR)
    return view,np.asarray(projection).reshape(4,4,order='F'),np.asarray(eye),lens


def visible_span(parameters:Mapping,aspect:float,aperture_scale:float=1.):
    """(low, high) world x of the scene axis (the rest line through the camera pivot) inside the frustum, zoom 1."""
    from core.ribbon_continuation import frustum_axial_span
    view,projection,_,_=physical_view(parameters,aspect,aperture_scale)
    y,z=SPEC.pivot[1],SPEC.pivot[2]
    low,high=frustum_axial_span(projection@view,((y,y),(z,z)))
    if not high>low:
        raise ValueError('Waveform camera sees no part of the scene axis')
    return float(low),float(high)


_SPAN_CACHE = [None, None]


def card_span(camera:Mapping, extent, baseline_height:float):
    """``visible_span`` for a card of world ``extent`` (width, height): aspect from the extent and the edge-resize
    aperture extent height / ``baseline_height`` (the canonical card's; ``framed_aperture_scale`` without the shell
    inset, within a few percent of the renderer's). One cached solve per camera/extent change; None for no extent."""
    if extent is None:
        return None
    width, height = float(extent[0]), float(extent[1])
    if not (width > 0. and height > 0.):
        return None
    key = (tuple(sorted((k, tuple(v) if isinstance(v, (list, tuple)) else v) for k, v in camera.items())),
           width, height, float(baseline_height))
    if _SPAN_CACHE[0] != key:
        _SPAN_CACHE[0], _SPAN_CACHE[1] = key, visible_span(camera, width/height, height/float(baseline_height))
    return _SPAN_CACHE[1]
