"""Retained framed waveform mode; consumes the sole logical owner's immutable geometry and scene."""
from __future__ import annotations
from core.waveform_ribbon_view import physical_view  # the camera owner; re-exported for its consumers
from widgets.spotify_visualizer.render_state import WaveformRibbonFrame
from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale
from rendering.quick.scene3d.frame import item_pixel_rect,orient_visualizer_scene_frame
from rendering.quick.scene3d.waveform import FLOOR_CHAIN_PROGRAMS, SCENE_SAMPLES, WaveformScene
from rendering.gl_programs.mip_chain import MIP_BOX_TEXTS
from rendering.quick.scene3d.resources import warm_programs
from rendering.quick.scene3d.target import scene_target_programs
from rendering.gl_programs.waveform_ribbon import FLOOR_VERTEX,FLOOR_FRAGMENT
from rendering.gl_programs.waveform_atmosphere import MEDIUM_INJECT_SOURCE,SKY_VERTEX,SKY_FRAGMENT
from rendering.gl_programs.ribbon import (RIBBON_VERTEX,RIBBON_BODY_FRAGMENT,RIBBON_LIGHT_FRAGMENT,
    RIBBON_SPARK_VERTEX,RIBBON_SPARK_FRAGMENT,RIBBON_STRAY_VERTEX,RIBBON_STRAY_FRAGMENT)


class QuickWaveformRibbonRenderer:
    mode_id='waveform_ribbon'

    def __init__(self):
        self._scene=WaveformScene()
        self._prepared_signature=None

    @property
    def has_resources(self):return self._scene.has_resources

    def prepare_step(self,frame):
        frame=orient_visualizer_scene_frame(frame)
        state=frame.snapshot.logical.mode_state
        if not isinstance(state,WaveformRibbonFrame):raise TypeError('Waveform renderer requires its own mode frame')
        scene=self._scene;recipe=state.scene
        scene.admit_preparation()
        if not scene.ribbons.prepare_programs(sparks=False,strays=recipe.strays is not None,continuation=True,strand_cohorts=True):
            return False
        if recipe.sparks is not None and not scene.bursts.prepare_step():return False
        programs=[(scene.resources,'floor',FLOOR_VERTEX,FLOOR_FRAGMENT)]
        programs.extend((scene.resources,key,MIP_BOX_TEXTS[fmt]) for fmt,key in FLOOR_CHAIN_PROGRAMS.items())
        if recipe.fog is not None:
            programs.extend(((scene.fog_resources,'fog medium',MEDIUM_INJECT_SOURCE),
                             (scene.fog_resources,'sky',SKY_VERTEX,SKY_FRAGMENT)))
        programs.extend((scene.resources,*entry) for entry in scene_target_programs(SCENE_SAMPLES,True,False,
            overlay=True,oit=True,hdr=True,rotation=frame.scene_output_rotation))
        if not warm_programs(programs):return False
        # The floor's, the sky's and the medium's pass block rings (N1.6), one allocation a step.
        if not scene.resources.pass_blocks.warm():return False
        if recipe.fog is not None and not scene.fog_resources.pass_blocks.warm():return False
        if recipe.fog is not None:
            if not scene.field.prepare_step():return False
            for volume in (scene.fog,scene.reflected_fog):
                if not volume.prepare_program():return False
        if recipe.floor.give>0. and not scene.floor_give.prepare_step():return False
        if not state.ready:return False
        signature=(*item_pixel_rect(frame)[2:],recipe.fog is not None,recipe.sparks is not None,
                   recipe.strays is not None,recipe.floor.give>0.)
        if signature!=self._prepared_signature:
            self._draw(frame,opacity=0.)
            self._prepared_signature=signature
            return False
        return True

    def _draw(self,frame,opacity):
        frame=orient_visualizer_scene_frame(frame)
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
            strand_payload=state.strands,strand_origin=state.strand_origin,pulse=state.pulse)

    def render(self,frame):
        opacity=frame.snapshot.presentation.content_fade
        if opacity>0.:self._draw(frame,opacity=opacity)

    def release_resources(self):
        self._scene.release();self._prepared_signature=None


def create_visualizer_renderer():return QuickWaveformRibbonRenderer()


#: The ribbons' history capacity the renderer draws with (``_draw``'s ``capacity``).
HISTORY_CAPACITY=256


def waveform_camera(state):
    """(view, projection, eye, lens) of a Waveform frame: its framed view's camera
    (``framed_view_camera.waveform_ribbon_camera``, the renderer's own ``physical_view``), or None before a card is
    drawn (no framed view)."""
    if not state.framed_view:return None
    from core.framed_view import FramedView
    from widgets.spotify_visualizer.framed_view_camera import waveform_ribbon_camera
    return waveform_ribbon_camera(state.parameters,FramedView(*state.framed_view),zoom=state.zoom)


def waveform_pass_values(state,size,*,camera=None,values=None):
    """Every pass's block members (unprefixed, by pass id: ``waveform_shader_files.PASS_FILES``) of a Waveform logical
    frame drawn at ``size`` (the card's device pixels), the very values the Python scene draws with (N5.4: its plan's
    owners, ``rendering.quick.scene3d.waveform_plan``), and the draws' counts: ``(passes, counts)``. ``camera``: the
    frame's (``waveform_camera``'s when None); ``values``: a ``RibbonValues`` to keep its per-packet caches across
    frames. Only the stages the recipe draws are present: the yielding floor, the fog (field, media, volumes, skies),
    the strays, the event sparks and the floor's pre-pass."""
    import numpy as np
    from core.ribbon_style import RibbonSparks
    from core.waveform_ribbon_scene import FLOOR_CONTACT
    from rendering.gl_programs.mist import FOG_OFF
    from rendering.quick.scene3d.floor_give import floor_give_values
    from rendering.quick.scene3d.fog_volume import fog_volume_values
    from rendering.quick.scene3d.pulse_rim import pulse_rim_values
    from rendering.quick.scene3d.ribbon import RibbonValues, STRAY_SEGMENTS, _sweep_axis
    from rendering.quick.scene3d.ribbon_bursts import burst_values
    from rendering.quick.scene3d.waveform import colour_grade
    from rendering.quick.scene3d.waveform_field import field_values
    from rendering.quick.scene3d.waveform_plan import (field_receiver_values, floor_prepass, floor_prepass_size,
                                                       floor_values, fog_focus, fog_grid, frame_geometry,
                                                       history_mist, history_mvp, medium_values, reflection_size,
                                                       sky_values)
    if camera is None:camera=waveform_camera(state)
    if camera is None:raise ValueError('a Waveform frame without a framed view has no camera')
    view,projection,eye,lens=camera
    values=values if values is not None else RibbonValues()
    recipe,packet,now=state.scene,state.packet,state.time
    size=(int(size[0]),int(size[1]))
    fog=recipe.fog
    fogged,giving=fog is not None,recipe.floor.give>0.
    rim=recipe.pulse_rim>0. and bool(state.pulse)
    grade=colour_grade(recipe,state.passage)
    side=-1. if recipe.flow.direction<0. else 1.
    passes,counts={},{}
    give=None
    if giving:
        passes['give_section'],passes['give_blur'],give=floor_give_values(
            packet,translation=(recipe.flow.head_x-state.travel,0.,0.),floor=recipe.floor,contact=FLOOR_CONTACT,
            camber=recipe.material.cross_curve,side=side)
        counts['give_samples']=int(recipe.floor.give_span[2])
    frame=frame_geometry(packet,capacity=HISTORY_CAPACITY,now=now,travel=state.travel,recipe=recipe,size=size,
                         view=view,projection=projection,grade=grade,
                         pulse_rim=pulse_rim_values(recipe.pulse_rim) if rim else None,floor_give=give)
    mirrored_size=reflection_size(size,recipe.floor)
    receivers={'':dict(FOG_OFF),'_mirror':dict(FOG_OFF)}
    if fogged:
        passes['field']=field_values(packet,translation=frame.scroll[:3,3],span=fog.field_span,grade=grade,side=side)
        counts['field_samples']=int(fog.field_span[2])
        medium=medium_values(recipe,now=now,origin=frame.continuation_origin,count=frame.continuation_count,
                             mirror=frame.mirror,grade=grade)
        for name,camera_view,cell,slices in (('',view,fog.cell,fog.slices),
                                             ('_mirror',frame.mirrored,fog.reflection_cell,fog.reflection_slices)):
            grid=fog_grid(size,cell,slices)
            dispatch,receivers[name]=fog_volume_values(view=camera_view,lens=lens,depth_range=fog.depth_range,
                                                       grid=grid,focus_depth=fog_focus(camera_view))
            passes['medium'+name]={**medium,**dispatch}
            passes['integrate'+name]=dict(dispatch)
            passes['sky'+name]=sky_values(receivers[name],backdrop=recipe.environment.backdrop,
                                          reflection=bool(name))
            counts['fog_grid'+name]=grid
    draws={'':{**frame.draw,'mist':history_mist({**frame.draw['mist'],**receivers['']},frame.mirror)},
           '_mirror':{**frame.draw,'mist':history_mist({**frame.draw['mist'],**receivers['_mirror']},frame.mirror),
                      'view':tuple(frame.reflected_view.flatten(order='F')),'viewport':mirrored_size}}
    for name,mvp in (('',frame.ribbon_mvp),('_mirror',frame.reflected_mvp)):
        draw=draws[name]
        found=values.ribbon(packet,mvp,shading='light',**draw)
        if found is not None:
            passes['ribbon'+name],counts['ribbon_vertices']=found
        if recipe.strays is not None:
            stray=values.sparks(packet,mvp,RibbonSparks(),now,draw['mist'],draw['mist_frame'],draw['grade'],
                                recipe.material,_sweep_axis(draw['sweep_axis']),draw['floor'],recipe.strays,
                                state.strands,state.strand_origin,draw['continuation'],draw['floor_give'],
                                draw['viewport'])
            if stray is not None:
                passes['strays'+name]=stray[0]
                counts['strays_vertices']=stray[2]*recipe.strays.per_knot*STRAY_SEGMENTS*6
        if recipe.sparks is not None and state.particles:
            matrix=(np.asarray(frame.mvp,float).reshape(4,4,order='F') if not name
                    else projection@frame.mirrored)
            passes['bursts'+name]=burst_values(mvp=tuple(history_mvp(matrix,frame.mirror).flatten(order='F')),
                                               now=now-state.particle_origin,viewport=draw['viewport'],
                                               mist=draw['mist'],grade=draw['grade'])
    counts['ribbon_instances']=packet.instances
    passes['floor']=floor_values(recipe,mvp=frame.mvp,eye=eye,view=view,size=size,lit=fogged,give_span=give,
                                 field=field_receiver_values(recipe,origin=frame.continuation_origin,
                                                             count=frame.continuation_count,mirror=frame.mirror,
                                                             grade=grade) if fogged else None,
                                 fog_uniforms=receivers[''] if fogged else None)
    prepass=floor_prepass_size(size,recipe.floor)
    if prepass is not None:
        passes['floor_prepass']=floor_prepass(passes['floor'],prepass)
    counts['reflection_size']=mirrored_size
    counts['prepass_size']=prepass
    return passes,counts
