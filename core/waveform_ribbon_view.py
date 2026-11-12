"""Waveform's physical camera view and the part of the scene axis it shows. Pure: no Qt/GL/clock.

The renderer draws with ``physical_view``; the logical capture sizes the travelling pulse from ``visible_span`` of that
very frustum (``core.waveform_ribbon_dynamics.VIEW_MARGIN``), built from the same numbers the renderer reads from the
card it draws (``card_span`` of the controller's ``framed_view``). The aperture is the CUSTOM edge-resize sensor scale
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


def visible_top(parameters:Mapping,aspect:float,aperture_scale:float=1.):
    """World y where the frustum's top plane crosses the vertical line through the camera pivot, zoom 1 (the card's
    top edge above the scene axis); None when that plane holds the line (a camera looking straight up or down)."""
    view,projection,_,_=physical_view(parameters,aspect,aperture_scale)
    mvp=projection@view
    plane=mvp[3]-mvp[1]          # clip y = w
    if abs(plane[1])<1e-12:
        return None
    x,_,z=SPEC.pivot
    return float(-(plane[0]*x+plane[2]*z+plane[3])/plane[1])


_SPAN_CACHE = [None, None]


def card_span(camera:Mapping, view):
    """``visible_span`` for the drawn card's framed ``view`` (``core.framed_view.FramedView``: the card's pixel aspect
    and its content aperture, ``framed_aperture_scale(..., content=True)``, exactly the numbers the renderer draws
    with, N0.4), followed by its ``visible_top`` when the camera has one. One cached solve per camera/view change;
    None for no view (no card drawn yet)."""
    if view is None:
        return None
    aspect, aperture = float(view[0]), float(view[1])
    key = (tuple(sorted((k, tuple(v) if isinstance(v, (list, tuple)) else v) for k, v in camera.items())),
           aspect, aperture)
    if _SPAN_CACHE[0] != key:
        top = visible_top(camera, aspect, aperture)
        _SPAN_CACHE[0], _SPAN_CACHE[1] = key, visible_span(camera, aspect, aperture)+(() if top is None else (top,))
    return _SPAN_CACHE[1]
