"""Audio-synchronized full-reactivity lab comparison using existing recorded PCM and DSP replay."""
from __future__ import annotations

import argparse
from dataclasses import asdict,replace
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import wave
from time import perf_counter_ns

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

import numpy as np
from PIL import Image,ImageDraw
from tools.labs.waveform_ribbon_reactivity import CANDIDATES,HeadHistory,PRE_ROLL,clamp
from tools.labs.waveform_ribbon_recorded_input import RecordedRibbonInput
from tools import artifact_paths  # noqa: E402
from tools import evidence_media  # noqa: E402

FPS=24
SIZE=(410,359)
NATIVE=(820,718)
CHECKPOINTS=(.5,2.,3.5,5.5,8.5)


def review_exports(output,ffmpeg):
    """Small individual motion previews and a native synchronized sheet; MP4 retains the common audible source."""
    for slot,key in enumerate(CANDIDATES):
        x,y=(slot%2)*410,(slot//2)*381
        result=subprocess.run([str(ffmpeg.resolve()),'-hide_banner','-loglevel','error','-i',str(output/'comparison_with_audio.mp4'),
                               '-vf',f'crop=410:381:{x}:{y},fps=15','-an','-loop','0','-q:v','72',
                               str(output/key/'motion.webp')],cwd=ROOT,capture_output=True,timeout=60)
        if result.returncode:
            raise RuntimeError(result.stderr.decode('utf-8',errors='replace'))
    sheet=Image.new('RGB',(820*4,718*5+24),(12,12,18))
    draw=ImageDraw.Draw(sheet)
    for column,key in enumerate(CANDIDATES):
        draw.text((column*820+8,6),f'{key} | same music at .5, 2, 3.5, 5.5, 8.5 seconds',fill='white')
        for row,t in enumerate(CHECKPOINTS):
            with Image.open(output/key/f'full_{t:05.2f}.png') as image:
                sheet.paste(image,(column*820,24+row*718))
    sheet.save(output/'synchronized_native_sheet.png')


def appearance_recipe(base,values):
    """Pure projection of logical envelopes into existing material/colour/particle controls; no integration."""
    bass,mids,highs,level,hit=(values[key] for key in ('bass','mids','highs','loudness','hit'))
    drive=clamp(.7*level**2+.3*hit)
    material=replace(base.material,glint_density=1.4+4*highs,glint_chance=clamp(.01+.30*highs+.25*hit),
                     glint_light=2.+3*highs+3*hit,strand_light=base.material.strand_light*(.8+.4*level+.35*hit),
                     fill_light=base.material.fill_light*(.8+.4*level+.35*hit),glow=.7+.4*hit,hot=.08*hit)
    sparks=replace(base.sparks,light=18.*clamp(.7*highs+hit),smallest=1.2,largest=3.+3*hit,
                   drift=.5+1.2*bass,lifetime=2.5,white=.12)
    return replace(base,material=material,sparks=sparks,
                   grade_share=(.1,0.),bloom=.08+.08*drive)


def capture(args):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from tools.labs import waveform_ribbon_lab as module
    from tools.visualizer_replay.live_audio import recorded_pcm
    output=args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    print('Preparing canonical PCM/feature replay',args.recording,flush=True)
    source=RecordedRibbonInput(args.recording,start=args.start)
    (output/'input.json').write_text(json.dumps(source.metadata,indent=2)+'\n',encoding='utf-8')
    print('Replayed input percentiles',source.metadata['p10_p50_p90'],flush=True)
    pcm,rate=recorded_pcm(args.recording)
    sample_start=round((args.start+source.metadata['first_history_seconds'])*rate)
    audio=pcm[sample_start:sample_start+round(args.seconds*rate)]
    if len(audio)!=round(args.seconds*rate):
        raise ValueError('Recorded audio window is incomplete')
    with wave.open(str(output/'audio.wav'),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(rate)
        stream.writeframes((np.clip(audio,-1.,1.)*32767).astype('<i2').tobytes())
    base=replace(module.RECIPES['complete'],ribbon_colours=module.ALTERNATE.ribbon_colours)
    # This explicit musical fixture admits only the fixed mock pose/native aspect. It does not pretend to prove
    # the broader navigation profile. In the fixed sweep plane, side and bow have zero world-x component.
    view,projection,_=module.camera(module.POSES['mock'],NATIVE[0]/NATIVE[1])
    edge=abs(1./projection[0,0])
    spacing=base.flow.speed/base.flow.knot_hz
    head=math.ceil((edge+2*spacing+.05)/spacing)*spacing
    base=replace(base,flow=replace(base.flow,head_x=head,fade_in=.1,fade_out=.5))
    manifest=dict(scope='recorded full-reactivity comparison; fixed mock pose only; production navigation unadmitted',
                  recording=source.metadata,seconds=args.seconds,fps=FPS,viewport=SIZE,native_viewport=NATIVE,
                  flow=asdict(base.flow),visible_right_edge=edge,hidden_end_margin=head-edge,
                  base_recipe=asdict(base),native_checkpoints=CHECKPOINTS,
                  nominal_centre_transport_seconds=head/base.flow.speed,
                  audio_shift_seconds=0.,audio_first_history_alignment_seconds=source.metadata['first_history_seconds'],
                  audio_reconstructed_duration_seconds=len(pcm)/rate,
                  feature_duration_seconds=source.metadata['duration'],
                  source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  source_sha256={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in (Path(__file__),Path(module.__file__),ROOT/'tools/labs/waveform_ribbon_reactivity.py',
                                              ROOT/'tools/labs/waveform_ribbon_recorded_input.py')},
                  candidates={})
    proof=HeadHistory('A',base,input_source=source,accents=True,body_envelope=True)
    proof.advance(PRE_ROLL)
    original=proof.ring.packet().payload
    proof_lab=module.Lab(replace(base,sparks=None,strays=None,bloom=.12),NATIVE)
    proof_info={}
    try:
        for label,level in (('low',0.),('high',1.)):
            snapshot=proof.snapshot(body_level=level)
            Image.fromarray(proof_lab.render_history(snapshot,PRE_ROLL)).save(output/f'body_range_{label}.png')
            flat=proof_lab.render_history(snapshot,PRE_ROLL,flat=True)
            Image.fromarray(flat).save(output/f'body_range_{label}_geometry.png')
            rgb=flat[:,:,:3].astype(int)
            visible=(rgb[:,:,0]>120)&(rgb[:,:,2]>120)&(rgb[:,:,1]<60)
            yy,xx=np.where(visible)
            proof_info[label]=dict(pixels=int(visible.sum()),height=int(yy.max()-yy.min()+1),width=int(xx.max()-xx.min()+1))
    finally:
        proof_lab.close()
    assert proof.ring.packet().payload==original,'Body projection mutated musical history'
    if proof_info['high']['height']<1.5*proof_info['low']['height'] or proof_info['high']['pixels']<1.5*proof_info['low']['pixels']:
        raise AssertionError(f'Authored low/high body forms are not visibly distinct: {proof_info}')
    (output/'body_range_proof.json').write_text(json.dumps(proof_info,indent=2)+'\n',encoding='utf-8')
    print('Same-time visible body range',proof_info,flush=True)
    if args.proof_only:return
    models={key:HeadHistory(key,base,input_source=source,accents=True,trace=True,body_envelope=True) for key in CANDIDATES}
    labs={}
    encoder=None
    native=None
    diagnostics={key:[] for key in CANDIDATES}
    projection_ns={key:[] for key in CANDIDATES}
    try:
        for key in CANDIDATES:
            labs[key]=module.Lab(base,SIZE)
        native=module.Lab(base,NATIVE)
        command=[str(args.ffmpeg.resolve()),'-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24',
                 '-video_size','820x762','-framerate',str(FPS),'-i','pipe:0','-i',str(output/'audio.wav'),
                 '-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',
                 '-shortest','-movflags','+faststart',str(output/'comparison_with_audio.mp4')]
        with (output/'encoder.log').open('wb') as log:
            encoder=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log,cwd=ROOT)
            try:
                for index in range(round(args.seconds*FPS)):
                    t=index/FPS;now=PRE_ROLL+t
                    grid=Image.new('RGB',(820,762),(12,12,18))
                    for slot,key in enumerate(CANDIDATES):
                        model=models[key];model.advance(now)
                        current=appearance_recipe(base,model.appearance)
                        labs[key].recipe=current
                        started=perf_counter_ns();snapshot=model.snapshot();projection_ns[key].append(perf_counter_ns()-started)
                        image=Image.fromarray(labs[key].render_history(snapshot,now)).convert('RGB')
                        x,y=(slot%2)*410,(slot//2)*381
                        grid.paste(image,(x,y+22))
                        draw=ImageDraw.Draw(grid)
                        title={'A':'flow / rolling twist','B':'traveling packets','C':'elastic torsion','D':'macro / PCM detail'}[key]
                        draw.text((x+5,y+4),f'{key} {title} | {args.start+t:.1f}s',fill='white')
                        for band,color in (('bass','#ff598e'),('mids','#63c9ff'),('highs','#db9cff')):
                            k=('bass','mids','highs').index(band)
                            left=x+220+k*60
                            draw.rectangle((left,y+7,left+round(model.appearance[band]*50),y+13),fill=color)
                        if index in {0,FPS,2*FPS,4*FPS,6*FPS,8*FPS,10*FPS,15*FPS,round(args.seconds*FPS)-1,
                                     *(round(t*FPS) for t in CHECKPOINTS)}:
                            destination=output/key;destination.mkdir(exist_ok=True)
                            native.recipe=current
                            Image.fromarray(native.render_history(snapshot,now)).save(destination/f'full_{t:05.2f}.png')
                            actual=native.render_history(snapshot,now,flat=True)
                            control=HeadHistory(key,base,fixture='idle',body_envelope=True);control.advance(now)
                            idle=native.render_history(control.snapshot(),now,flat=True)
                            def mask(p):
                                rgb=p[:,:,:3].astype(int)
                                return (rgb[:,:,0]>120)&(rgb[:,:,2]>120)&(rgb[:,:,1]<60)
                            changed=int(np.count_nonzero(mask(actual)^mask(idle)))
                            diagnostics[key].append(dict(time=t,body_difference_pixels=changed,
                                                         body_level=model.body_level,
                                                         appearance=model.appearance.copy()))
                            Image.fromarray(actual).save(destination/f'body_{t:05.2f}.png')
                    encoder.stdin.write(np.asarray(grid,np.uint8).tobytes())
                    if index%(FPS*2)==0:
                        print('Recorded four-way',round(t,2),'/',args.seconds,flush=True)
                encoder.stdin.close()
                if encoder.wait(timeout=60)!=0:
                    raise RuntimeError('Video encoder failed; inspect encoder.log')
            finally:
                if encoder.poll() is None:
                    encoder.kill();encoder.wait(timeout=10)
        for key,model in models.items():
            manifest['candidates'][key]=dict(events=model.event_log,head_trace=model.trace,body_checks=diagnostics[key],
                 cpu_snapshot_ms=dict(median=float(np.median(projection_ns[key])/1e6),
                                      p90=float(np.percentile(projection_ns[key],90)/1e6),
                                      scope='lab CPU snapshot projection only, not whole frame or production cost'))
            if max(row['body_difference_pixels'] for row in diagnostics[key])<200:
                raise AssertionError(f'{key} has no meaningful recorded-body realization')
    finally:
        if native is not None:native.close()
        for lab in labs.values():lab.close()
    review_exports(output,args.ffmpeg)
    manifest['artifacts_sha256']={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in output.rglob('*') if p.is_file() and p.name!='receipt.json'}
    (output/'receipt.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Recorded audio bake-off:',output,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recording',type=Path,required=True)
    parser.add_argument('--start',type=float,default=20.)
    parser.add_argument('--seconds',type=float,default=20.)
    parser.add_argument('--output',type=artifact_paths.evidence_arg,default=artifact_paths.default_evidence('visualizers/waveform_ribbon','music_bakeoff'))
    parser.add_argument('--ffmpeg',type=Path,required=True)
    parser.add_argument('--proof-only',action='store_true')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if not (math.isfinite(args.start) and args.start>=0 and math.isfinite(args.seconds) and 9<=args.seconds<=60):
        parser.error('Use a finite non-negative start and 9..60 seconds for the synchronized checkpoint package')
    if args.worker:return capture(args)
    work=evidence_media.redirect_output(args,'output','waveform_ribbon_music_bakeoff')
    from tools.build_runner import BuildProcessOwner
    owner=BuildProcessOwner()
    process=owner.start([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],'--output',str(work),'--worker'],cwd=ROOT)
    try:
        try:result=process.wait(timeout=900)
        except subprocess.TimeoutExpired:
            owner.cancel();process.wait(timeout=10);raise
    finally:
        owner.retire(process);owner.shutdown()
    raise SystemExit(evidence_media.finish(result))


if __name__=='__main__':main()
