"""Bounded event-owned ribbon sparks: birth records only, analytic flight on the shared scene clock."""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
from core.ribbon_packet import KNOT_ROWS

CAPACITY=2048
STRIDE=16
MIN_GAP=.16
MAX_BURST=36  # 8s / .16s * 36 < CAPACITY; active cohorts never need truncation


@dataclass(frozen=True)
class RibbonAccentControls:
    ranges: object


class RibbonBursts:
    def __init__(self):
        self.records=np.zeros((CAPACITY,STRIDE),np.float32)
        self.origin=0.
        self.last_birth=-math.inf
        self.serial=0
        self.payload=b''
        self.until=0.

    def visible_payload(self, now):
        return self.payload if now < self.until else b''

    def admit(self,snapshot,controls: RibbonAccentControls,strength):
        now=snapshot.time
        if strength<.08 or now-self.last_birth<MIN_GAP or not snapshot.ready:return False
        values=dict(snapshot.realized);drives=dict(snapshot.drives)
        def pair(key):
            low,high=controls.ranges[key]
            return float(low)+(float(high)-float(low))*drives['sparkle']
        count=math.ceil(pair('spark_count')*min(1.,strength)*min(1.,values['sparkle']))
        if not 0<=count<=MAX_BURST:raise ValueError('Ribbon burst count exceeds its fixed-capacity admission proof')
        if count==0:return False
        lifetime=pair('spark_lifetime')
        if not .2<=lifetime<=8.:raise ValueError('Ribbon burst lifetime exceeds the fixed-capacity admission proof')
        packet=snapshot.packet
        data=np.frombuffer(packet.payload,np.float32).reshape(packet.instances,-1,4)
        positions=[];widths=[];twists=[];colours=[]
        for path in data:
            if path[2,3]<=.02:continue
            n,start,capacity=int(path[0,0]),int(path[1,1]),int(path[1,2])
            knots=path[4:].reshape(-1,KNOT_ROWS,4)[(start+np.arange(n))%capacity]
            if n<4:continue
            # Midpoint of each valid swept B-spline interval, exactly the shader's positive basis weights.
            weights=np.array((1.,23.,23.,1.))/48.
            a,b,c,d=(knots[i:n-3+i] for i in range(4))
            live=(a[:,1,2]>.5)&(b[:,1,2]>.5)&(c[:,1,2]>.5)&(d[:,1,2]>.5)
            live&=(b[:,1,3]<.5)&(c[:,1,3]<.5)&(d[:,1,3]<.5)
            points=sum(weight*k[:,0,:3] for weight,k in zip(weights,(a,b,c,d)))+np.asarray(packet.world_origin)
            points[:,0]+=snapshot.head_x-snapshot.travel
            live&=np.abs(points[:,0])<8.  # authored world emitters, independent of the camera
            positions.append(points[live]);widths.append(sum(w*k[:,0,3] for w,k in zip(weights,(a,b,c,d)))[live])
            twists.append((sum(w*k[:,1,1] for w,k in zip(weights,(a,b,c,d)))+path[1,0])[live])
            tint=sum(w*k[:,4,:] for w,k in zip(weights,(a,b,c,d)))
            header=.5*(path[2,:3]+path[3,:3])
            colours.append((header[None,:]*(1.-tint[:,3,None])+tint[:,:3]*tint[:,3,None])[live])
        if not positions or not any(len(p) for p in positions):return False
        p=np.concatenate(positions);w=np.concatenate(widths);theta=np.concatenate(twists);colour=np.concatenate(colours)
        free=np.flatnonzero((self.records[:,7]<=0.)|(now-self.origin-self.records[:,3]>=self.records[:,7]))
        if len(free)<count:raise RuntimeError('Ribbon burst admission exceeded its proven capacity')
        new_origin=math.floor(now/16.)*16.
        self.records[:,3]-=new_origin-self.origin;self.origin=new_origin
        self.serial+=1
        rng=np.random.default_rng(self.serial)
        chosen=rng.integers(0,len(p),count);side=rng.choice((-1.,1.),count)
        birth=p[chosen].copy()
        birth[:,1]+=np.cos(theta[chosen])*w[chosen]*side
        birth[:,2]+=np.sin(theta[chosen])*w[chosen]*side
        # Same monotone floor-contact map as the ribbon surface, applied after its swept rim position.
        height=(birth[:,1]-.03)/.15
        birth[:,1]=.03+.15*np.logaddexp(0.,height)
        direction=rng.normal(size=(count,3));direction[:,1]+=pair('spark_rise')
        direction/=np.maximum(np.linalg.norm(direction,axis=1,keepdims=True),1e-6)
        out=self.records[free[:count]].copy()
        out[:,:3]=birth;out[:,3]=now-self.origin
        out[:,4:7]=direction*pair('spark_drift');out[:,7]=lifetime
        out[:,8:11]=colour[chosen];out[:,11]=pair('spark_size')*(.35+.65*rng.random(count))
        out[:,12]=pair('spark_light')*strength;out[:,13]=pair('spark_white')
        out[:,14]=rng.random(count);out[:,15]=1.
        self.records[free[:count]]=out
        self.payload=self.records.tobytes();self.last_birth=now;self.until=max(self.until,now+lifetime)
        return True
