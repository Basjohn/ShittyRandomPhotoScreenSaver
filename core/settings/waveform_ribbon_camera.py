"""Waveform's fixed floor and forward clipping contract for the shared framed camera.

The spec remains with the authored scene. Admission, flight and raster rendering
all consume this floor through its spec hook. Perspective retains positive clips;
Orthographic fits a raster slab around XY-visible world support without moving
the physical eye. The infinite ground has its own world-plane intersection.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
import itertools
import numpy as np
from core.settings.framed_camera import GroundedOrbitSpec

FLOOR_Y = 0.0
NEAR = 0.3
FAR = 200.0
YAW_SPAN = math.radians(35.)
# Low grounded eye with a physical near-level tilt endpoint; keep the floor in view.
# The closer radius also stays outside the maximum deformed sheet's transverse domain at either yaw limit.
GROUNDED_ORBIT = GroundedOrbitSpec(radius_range=(8.5,16.),eye_height=2.6,minimum_downward_pitch_degrees=.5)


def floor_height(x: float, z: float) -> float:
    return FLOOR_Y


def floor(values):
    """The fixed world floor, independent of viewport, camera and audio."""
    return floor_height


@dataclass(frozen=True, slots=True)
class RasterSupport:
    """World Y/Z support and image-plane padding, never a population or camera pose."""
    transverse: tuple = ((0.,8.5),(-6.5,6.5))
    padding_ndc: tuple = (0.,0.)


def scene_raster_support(packet,recipe,travel,*,now,viewport,burst_payload=None,burst_origin=0.,strand_payload=None):
    """Conservative current body/held-accent support for one immutable scene publication.

    Bodies use their analytic endpoint jets. Living spark records contribute their
    complete remaining world flight; held strand geometry survives later control
    changes. Only support changes--no birth, identity, geometry or phase is rewritten.
    """
    from core.ribbon_continuation import continuation_bounds
    low_high=continuation_bounds(packet,np.array((recipe.flow.head_x-travel,0.,0.)),recipe.material.cross_curve)
    low=np.array((low_high[0][0],low_high[1][0]));high=np.array((low_high[0][1],low_high[1][1]))
    pixel_radius=recipe.material.min_pixels*.5 if recipe.material.cross_curve==0. else 0.
    reach=0.
    if recipe.strays is not None:
        if strand_payload is None:
            reach=recipe.strays.reach;pixel_radius=max(pixel_radius,recipe.strays.width)
        elif strand_payload:
            records=np.frombuffer(strand_payload,np.float32).reshape(-1,3,4)
            held=records[records[:,0,0]>0.]
            if len(held):
                reach=float(held[:,1,1].max());pixel_radius=max(pixel_radius,float(held[:,1,2].max()))
    low[1]-=1.25*reach;high+=1.25*reach
    if recipe.sparks is not None:
        if burst_payload is None:
            # Explicit lab-only procedural sparks share the primitive's bounded analytic drift.
            sparks=recipe.sparks
            drift=1.25*sparks.drift*sparks.lifetime/(1.+.5*sparks.lifetime)
            low[1]-=drift;high+=drift;pixel_radius=max(pixel_radius,sparks.largest*.5)
        elif burst_payload:
            records=np.frombuffer(burst_payload,np.float32).reshape(-1,16)
            age=now-float(burst_origin)-records[:,3]
            live=records[(records[:,7]>0.)&(age>=0.)&(age<records[:,7])]
            if len(live):
                birth=live[:,1:3].astype(float)
                factor=live[:,7]/(1.+.5*live[:,7])
                end=birth+live[:,5:7]*factor[:,None]
                low=np.minimum(low,np.minimum(birth,end).min(axis=0))
                high=np.maximum(high,np.maximum(birth,end).max(axis=0))
                pixel_radius=max(pixel_radius,float((live[:,11]*(1.+4.*live[:,15])*.5).max()))
    low[0]=0.  # Every sheet/strand/spark uses its smooth or explicit ground collision.
    width,height=viewport
    if min(width,height)<=0:raise ValueError('Raster support needs a positive viewport')
    scale=min(1.,recipe.floor.resolution,recipe.floor.resolution_max_height/height)
    rw,rh=max(1,int(width*scale)),max(1,int(height*scale))
    padding=(2.*pixel_radius/min(width,rw),2.*pixel_radius/min(height,rh))
    return RasterSupport(((float(low[0]),float(high[0])),(float(low[1]),float(high[1]))),padding)


def orthographic_raster_projection(view,half_extent,support=None,*,guard=.4):
    """Fit only raster depth to XY-visible world support, preserving the true eye and projection XY.

    The same finite signed slab admits main and mirrored views. It is derived from
    world support, not a guessed negative near distance or moved reference eye.
    Camera-only queries use the authored body support; scene callers supply their
    immutable geometry/accent support through scene_raster_support.
    """
    from core.settings import framed_camera as fc
    from core.ribbon_continuation import frustum_axial_span
    support=RasterSupport() if support is None else support
    view=np.asarray(view,float)
    fit_extent=tuple(h*(1.+p) for h,p in zip(half_extent,support.padding_ndc))
    xy=np.asarray(fc.orthographic_matrix(fit_extent,0.,1.)).reshape(4,4,order='F')
    mirror=view.copy();mirror[:,1]*=-1.
    spans=[frustum_axial_span(xy@v,support.transverse,depth_clip=False) for v in (view,mirror)]
    axial=(min(s[0] for s in spans),max(s[1] for s in spans))
    points=np.array([(*point,1.) for point in itertools.product(axial,*support.transverse)])
    depths=np.concatenate((-(points@view.T)[:,2],-(points@mirror.T)[:,2]))
    margin=max(float(guard),float(np.max(np.abs(depths)))*np.finfo(np.float32).eps*32.)
    near,far=float(depths.min()-margin),float(depths.max()+margin)
    return np.asarray(fc.orthographic_matrix(half_extent,near,far)).reshape(4,4,order='F')
