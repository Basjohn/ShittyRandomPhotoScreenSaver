"""Recorded native PCM through the production Waveform mode and retained GL host, without settings writes."""
from __future__ import annotations
import argparse
from bisect import bisect_left
from dataclasses import replace
import hashlib,json,math,subprocess,sys,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))


def dimensions(value):
    pair=tuple(int(part) for part in value.split('x'))
    if len(pair)!=2 or not all(1<=part<=8192 for part in pair):raise ValueError('Use positive WIDTHxHEIGHT up to 8192')
    return pair


def capture(args):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from PySide6.QtGui import QGuiApplication
    import numpy as np
    from PIL import Image,ImageDraw
    from OpenGL import GL as gl
    from OpenGL.raw.GL.VERSION.GL_3_3 import glGetQueryObjectui64v
    import ctypes
    from widgets.spotify_visualizer.feature_frame import load_jsonl,FeatureClip
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload
    from tools.visualizer_replay.pcm_reanalysis import reanalyzed_bubble_bands
    from tools.visualizer_replay.driver import replay_clip
    from tools.visualizer_replay.live_audio import recorded_pcm
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.labs.render_target import OffscreenRenderTarget
    from widgets.spotify_visualizer.presentation_geometry import resize_visualizer_presentation,framed_aperture_scale
    app=QGuiApplication.instance() or QGuiApplication([])
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    clip=load_jsonl(args.clip)
    origin=clip.frames[0].timestamp_us
    times=[(frame.timestamp_us-origin)/1e6 for frame in clip.frames]
    stop=args.start+args.duration
    if stop>times[-1]:raise ValueError('Requested recording window is incomplete')
    indices=sorted({bisect_left(times,args.start+i/args.fps) for i in range(math.ceil(args.duration*args.fps))})
    frames=clip.frames[:indices[-1]+1]
    activation=resolve_visualizer_activation_payload({'mode':'waveform_ribbon','preset_waveform_ribbon':args.preset-1},mode='waveform_ribbon')
    overrides=dict(item.split('=',1) for item in args.set)
    overrides={key:json.loads(value) for key,value in overrides.items()}
    settings={**activation.resolved_config,**overrides}
    print('Replaying production PCM',args.preset,args.start,stop,flush=True)
    with reanalyzed_bubble_bands():
        result=replay_clip(FeatureClip('waveform_capture',tuple(frames)),'waveform_ribbon',settings=settings,snapshots_at=indices)
    print('Logical replay ready',result['mode_metrics'],flush=True)
    views=[dimensions(value) for value in args.viewports.split(',')] if args.viewports else [dimensions(args.size)]
    if args.viewports and len(indices)>3:raise ValueError('Viewport audit captures at most three source instants')
    width,height=views[0]
    target=OffscreenRenderTarget(width,height);host=QuickVisualizerRenderHost()
    matrix=(2/width,0,0,0,0,-2/height,0,0,0,0,1,0,-1,1,0,1)
    records=[];contacts=[];encoder=None
    audio_alignment=None
    try:
        if args.ffmpeg:
            pcm,rate=recorded_pcm(args.clip)
            history=clip.frames[0].capture_history
            first=len(history.pcm_f32le)//4
            start=first+round(args.start*rate)
            audio=pcm[start:start+round(args.duration*rate)]
            if len(audio)!=round(args.duration*rate):raise ValueError('Native audio window is incomplete')
            with wave.open(str(output/'audio.wav'),'wb') as stream:
                stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(rate)
                stream.writeframes((np.clip(audio,-1.,1.)*32767).astype('<i2').tobytes())
            audio_alignment=dict(first_history_seconds=first/rate,audio_shift_seconds=0.,
                scope='first history removed to align source origin; original feature timestamp cadence retained')
            command=[str(args.ffmpeg.resolve()),'-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24',
                '-video_size',args.size,'-framerate',str(args.fps),'-i','pipe:0','-i',str(output/'audio.wav'),
                '-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-shortest',
                '-movflags','+faststart',str(output/'motion_with_audio.mp4')]
            encoder=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.PIPE,cwd=ROOT)
        for ordinal,index in enumerate(indices):
            for width,height in views:
                snapshot=result['snapshots'][index]
                if args.edge_viewport or args.viewports:
                    presentation=resize_visualizer_presentation(snapshot.presentation,display_size=(width,height),
                        outer_origin=(0.,0.),relative_scale=1.,viewport_extent=(width,height),committed_outer_size=(width,height))
                    snapshot=replace(snapshot,presentation=presentation)
                matrix=(2/width,0,0,0,0,-2/height,0,0,0,0,1,0,-1,1,0,1)
                with target.current():
                    target.resize(width,height);target.bind(clear=(0.,0.,0.,0.))
                    query=int(gl.glGenQueries(1)[0]);gl.glBeginQuery(gl.GL_TIME_ELAPSED,query)
                    host.render(snapshot=snapshot,viewport=(0,0,width,height),logical_size=(float(width),float(height)),matrix_values=matrix)
                    gl.glEndQuery(gl.GL_TIME_ELAPSED)
                    elapsed=ctypes.c_uint64();glGetQueryObjectui64v(query,gl.GL_QUERY_RESULT,ctypes.byref(elapsed));gl.glDeleteQueries(1,[query])
                    pixels=target.read_rgba()
                state=snapshot.logical.mode_state;scene=host._implementations['waveform_ribbon']._scene
                births=np.frombuffer(state.particles,np.float32).reshape(-1,16) if state.particles else np.empty((0,16))
                active=(births[:,7]>0)&(state.time-state.particle_origin-births[:,3]>=0)&(state.time-state.particle_origin-births[:,3]<births[:,7])
                living=births[active]
                strand_rows=np.frombuffer(state.strands,np.float32).reshape(-1,3,4)[:,0] if state.strands else np.empty((0,4))
                strand_age=state.time-state.strand_origin-strand_rows[:,1]
                live_roots=(strand_rows[:,0]>0)&(strand_age>=0)
                records.append(dict(source_time=times[index],gpu_ms=elapsed.value/1e6,ready=state.ready,size=(width,height),
                    packet_sha256=hashlib.sha256(state.packet.payload).hexdigest(),camera=dict(state.parameters),
                    viewport_extent=snapshot.presentation.viewport_extent,
                    aperture_scale=framed_aperture_scale(snapshot.presentation,content=True),reflection_size=scene.reflection.size,
                    specular_size=scene._specular_size if height>state.scene.floor.specular_max_height else None,rotation_angle=state.rotation_angle,rotation_speed=state.rotation_speed,
                    particle_serial=state.particle_serial,active_particles=len(living),
                    active_strand_root_cohorts=int(live_roots.sum()),strand_sha256=hashlib.sha256(state.strands).hexdigest(),
                    particle_x_span=(float(living[:,0].min()),float(living[:,0].max())) if len(living) else None,
                    particle_glow=(float(living[:,15].min()),float(living[:,15].max())) if len(living) else None,drives=dict(state.drives),realized=dict(state.realized)))
                image=Image.fromarray(pixels).convert('RGB')
                if ordinal in {0,len(indices)//4,len(indices)//2,3*len(indices)//4,len(indices)-1} or args.png_all:
                    suffix=f'_{width}x{height}' if args.viewports else ''
                    image.save(output/f'frame_{ordinal:04d}{suffix}.png')
                    thumb=image.copy();thumb.thumbnail((410,359));contacts.append((thumb,f'{width}x{height}'))
                if encoder is not None:encoder.stdin.write(np.asarray(image,np.uint8).tobytes())
        if encoder is not None:
            encoder.stdin.close();error=encoder.stderr.read();code=encoder.wait(timeout=60)
            if code:raise RuntimeError(error.decode('utf-8',errors='replace'))
        sheet=Image.new('RGB',(410*len(contacts),381),(12,12,18));draw=ImageDraw.Draw(sheet)
        for index,(image,label) in enumerate(contacts):
            sheet.paste(image,(410*index,22));draw.text((410*index+5,365),label,fill='white')
        draw.text((5,5),activation.preset_name,fill='white');sheet.save(output/'contact.png')
        paths=subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT,text=True).splitlines()
        paths+=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
        receipt=dict(recording=str(args.clip.resolve()),recording_sha256=hashlib.sha256(args.clip.read_bytes()).hexdigest(),
            source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            source_sha256={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in paths if (ROOT/path).is_file()},
            preset_path=activation.preset_path,settings=settings,frames=records,audio_alignment=audio_alignment,
            size=(width,height),fps=args.fps,scope='production logical/capture/renderer; offline native PCM reanalysis for body, passage and typed onsets; original cadence; not live/physical acceptance')
        receipt['artifacts_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
        (output/'capture.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
        print('Captured',len(records),'frames;',output,flush=True)
    finally:
        if encoder is not None and encoder.poll() is None:encoder.kill();encoder.wait(timeout=10)
        with target.current():host.release_resources()
        target.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clip',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--preset',type=int,choices=(1,2),default=1);parser.add_argument('--start',type=float,default=20.)
    parser.add_argument('--duration',type=float,default=4.);parser.add_argument('--fps',type=int,default=12)
    parser.add_argument('--size',default='820x718');parser.add_argument('--ffmpeg',type=Path)
    parser.add_argument('--edge-viewport',action='store_true',help='Use actual CUSTOM edge-resize world aperture at --size')
    parser.add_argument('--viewports',help='Same frozen source instants at WIDTHxHEIGHT,...; uses edge-resize presentation')
    parser.add_argument('--set',action='append',default=[]);parser.add_argument('--png-all',action='store_true')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not (math.isfinite(args.start) and args.start>=1. and math.isfinite(args.duration) and 0<args.duration<=30. and 1<=args.fps<=60):
        parser.error('Use start >=1, duration in (0,30] and fps in 1..60')
    try:
        sizes=[dimensions(value) for value in args.viewports.split(',')] if args.viewports else [dimensions(args.size)]
    except (ValueError,TypeError):parser.error('Sizes must be WIDTHxHEIGHT, positive and at most 8192')
    if args.ffmpeg and (args.viewports or any(part%2 for part in sizes[0])):
        parser.error('Video needs one even-width/even-height size')
    if args.worker:return capture(args)
    from tools.build_runner import BuildProcessOwner
    owner=BuildProcessOwner();process=owner.start([sys.executable,__file__,*sys.argv[1:],'--worker'],cwd=ROOT)
    try:
        try:code=process.wait(timeout=900)
        except subprocess.TimeoutExpired:owner.cancel();process.wait(timeout=10);raise
    finally:owner.retire(process);owner.shutdown()
    raise SystemExit(code)


if __name__=='__main__':main()
