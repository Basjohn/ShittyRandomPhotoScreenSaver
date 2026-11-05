"""Waveform Ribbon tail stagger: per-tick motion of the published cloth (and its C2 continuation) at FIXED scene x.

Seen from the framed camera's extreme turn, the far ends of the history are in view. This probe evaluates the
Qt-free mirror of the shader's cloth (``core.ribbon_continuation.cloth_values``: exact B-spline inside the history,
endpoint continuation beyond it) at fixed scene positions every logical tick and reports the temporal second
difference (per tick^2) of the centre height/depth in three regions: the interior of the view, the history's tail
end (oldest knots) and the continuation beyond it. A tail that steps at every knot admission shows spikes there at
the knot cadence that the interior does not have. No renderer, no Qt.
"""
from __future__ import annotations
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))


def scene_field(snapshot,xs,ribbon=0,legacy=False):
    """Centre (y, z), half width and twist of one ribbon at scene x positions (history axis)."""
    import numpy as np
    from core.ribbon_packet import KNOT_ROWS
    from core.ribbon_continuation import cloth_values
    packet=snapshot.packet
    path=np.frombuffer(packet.payload,np.float32).reshape(packet.instances,-1,4)[ribbon]
    count,start,capacity=int(path[0,0]),int(path[1,1]),int(path[1,2])
    knots=path[4:].reshape(-1,KNOT_ROWS,4)[(start+np.arange(count))%capacity].astype(float)
    shift=packet.world_origin[0]+snapshot.head_x-snapshot.travel
    values=cloth_values(knots,np.asarray(xs,float)-shift,phase=None if legacy else float(path[1,3]))
    return values,float(knots[0,0,0]+shift),float(knots[-1,0,0]+shift)


def measure(model,seconds=12.,dt=1/90,xs=None,bands=(.5,.4,.3),legacy=False):
    """``legacy`` evaluates the former end-knot continuation (negative control)."""
    import numpy as np
    xs=np.arange(-90.,31.,1.) if xs is None else np.asarray(xs,float)
    rows=[];tails=[];heads=[]
    for _ in range(round(seconds/dt)):
        snapshot=model.advance(dt,bands=bands,intensity=.6,presence=1.)
        values,tail,head=scene_field(snapshot,xs,legacy=legacy)
        rows.append(values[:,:2]);tails.append(tail);heads.append(head)
    Y=np.asarray(rows);tails=np.asarray(tails)
    jerk=np.abs(Y[2:]-2*Y[1:-1]+Y[:-2]).max(axis=2)  # (ticks-2, xs)
    tail=tails[1:-1,None]
    # Interior: well inside both ends of the history (the head end has the same admission step as the tail).
    interior=(xs[None,:]>tail+10.)&(xs[None,:]<np.asarray(heads)[1:-1,None]-10.)
    near=(np.abs(xs[None,:]-tail)<=3.)
    beyond=(xs[None,:]<tail-3.)&(xs[None,:]>=tail-40.)
    return dict(interior=float(jerk[interior].max()),tail=float(jerk[near].max()) if near.any() else 0.,
                continuation=float(jerk[beyond].max()) if beyond.any() else 0.,
                tail_x=(float(tails.min()),float(tails.max())))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--presets',default='1,2,3,4,5,6,7')
    parser.add_argument('--legacy',action='store_true',help='measure the former end-knot continuation (negative control)')
    args=parser.parse_args()
    from core.waveform_ribbon_dynamics import WaveformDynamics
    from tools.visualizer_replay.waveform_ribbon_breathing_probe import preset_controls
    for index in (int(p) for p in args.presets.split(',')):
        model=WaveformDynamics(preset_controls(index-1))
        while not model.ready:model.advance(1/90,bands=(0.,0.,0.),intensity=0.,presence=0.)
        result=measure(model,legacy=args.legacy)
        print(f"preset {index}{' (end-knot continuation)' if args.legacy else ''}: max second difference per tick^2  interior {result['interior']:.5f}  tail end "
              f"{result['tail']:.5f}  continuation {result['continuation']:.5f}  tail x {result['tail_x'][0]:.1f}..{result['tail_x'][1]:.1f}",flush=True)


if __name__=='__main__':main()
