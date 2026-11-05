"""Retained framed waveform mode; consumes the sole logical owner's immutable geometry and scene."""
from __future__ import annotations
import numpy as np
from core.settings import framed_camera as fc
from core.settings.waveform_ribbon_camera import NEAR, FAR
from core.waveform_ribbon_scene import SPEC
from widgets.spotify_visualizer.render_state import WaveformRibbonFrame
from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale
from rendering.quick.scene3d.frame import item_pixel_rect
from rendering.quick.scene3d.waveform import WaveformScene
from rendering.quick.scene3d.resources import warm_programs
from rendering.quick.scene3d.target import scene_target_programs
from rendering.gl_programs.waveform_ribbon import FLOOR_VERTEX,FLOOR_FRAGMENT
from rendering.gl_programs.waveform_atmosphere import MEDIUM_GLSL,SKY_VERTEX,SKY_FRAGMENT
from rendering.gl_programs.fog_volume import fog_inject_source
from rendering.gl_programs.ribbon import (RIBBON_VERTEX,RIBBON_BODY_FRAGMENT,RIBBON_LIGHT_FRAGMENT,
    RIBBON_SPARK_VERTEX,RIBBON_SPARK_FRAGMENT,RIBBON_STRAY_VERTEX,RIBBON_STRAY_FRAGMENT)


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


class QuickWaveformRibbonRenderer:
    mode_id='waveform_ribbon'

    def __init__(self):
        self._scene=WaveformScene()
        self._prepared_signature=None

    @property
    def has_resources(self):return self._scene.has_resources

    def prepare_step(self,frame):
        state=frame.snapshot.logical.mode_state
        if not isinstance(state,WaveformRibbonFrame):raise TypeError('Waveform renderer requires its own mode frame')
        scene=self._scene;recipe=state.scene
        scene.admit_preparation()
        if not scene.ribbons.prepare_programs(sparks=False,strays=recipe.strays is not None,continuation=True,strand_cohorts=True):
            return False
        if recipe.sparks is not None and not scene.bursts.prepare_step():return False
        programs=[(scene.resources,'floor',FLOOR_VERTEX,FLOOR_FRAGMENT)]
        if recipe.fog is not None:
            programs.extend(((scene.fog_resources,'fog medium',fog_inject_source(MEDIUM_GLSL)),
                             (scene.fog_resources,'sky',SKY_VERTEX,SKY_FRAGMENT)))
        programs.extend((scene.resources,*entry) for entry in scene_target_programs(4,recipe.bloom>0.,False,
            overlay=True,oit=True,hdr=recipe.bloom>0.))
        if not warm_programs(programs):return False
        if recipe.fog is not None:
            if not scene.field.prepare_step():return False
            for volume in (scene.fog,scene.reflected_fog):
                if not volume.prepare_program():return False
        if not state.ready:return False
        signature=(*item_pixel_rect(frame)[2:],recipe.fog is not None,recipe.sparks is not None,
                   recipe.strays is not None,recipe.bloom>0.)
        if signature!=self._prepared_signature:
            self._draw(frame,opacity=0.)
            self._prepared_signature=signature
            return False
        return True

    def _draw(self,frame,opacity):
        state=frame.snapshot.logical.mode_state
        if not isinstance(state,WaveformRibbonFrame):raise TypeError('Waveform renderer requires its own mode frame')
        if not state.ready:return
        _x,_y,width,height=item_pixel_rect(frame)
        if min(width,height)<=0:return
        view,projection,eye,lens=physical_view(state.parameters,width/height,
            framed_aperture_scale(frame.snapshot.presentation,content=True),zoom=state.zoom)
        self._scene.render(state.packet,capacity=256,now=state.time,travel=state.travel,recipe=state.scene,
            size=(width,height),view=view,projection=projection,eye=eye,camera_lens=lens,card=frame,overlay=opacity,
            burst_payload=state.particles,burst_origin=state.particle_origin,react=state.passage,
            strand_payload=state.strands,strand_origin=state.strand_origin)

    def render(self,frame):
        opacity=frame.snapshot.presentation.content_fade
        if opacity>0.:self._draw(frame,opacity=opacity)

    def release_resources(self):
        self._scene.release();self._prepared_signature=None


def create_visualizer_renderer():return QuickWaveformRibbonRenderer()
