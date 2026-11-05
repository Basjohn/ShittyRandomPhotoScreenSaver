"""Bounded event-owned ribbon sparks: birth records only, analytic flight on the shared scene clock."""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
from core.ribbon_packet import KNOT_ROWS
from core.ribbon_continuation import cloth_values

CAPACITY=4096
STRIDE=16
MIN_GAP=.16
MAX_BURST=64  # 8s / .16s * 64 < CAPACITY; active cohorts never need truncation


@dataclass(frozen=True)
class RibbonAccentControls:
    ranges: object


class RibbonBursts:
    def __init__(self):
        self.records=np.zeros((CAPACITY,STRIDE),np.float32)
        self.origin=0.
        self.last_birth=-math.inf
        self.serial=0
        self.attempts=0
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
        admission=max(0.,min(1.,float(values['sparkle'])))
        if admission<=0.:return False
        # Stable low-discrepancy cohort admission: the Range controls how many
        # eligible accents spawn, while already-born count/light stay intact.
        threshold=(.25+self.attempts*.6180339887498949)%1.
        self.attempts+=1
        if threshold>=admission:return False
        # Contrast/support already decide whether an accent is admitted. Count
        # and light use their authored range once, not three attenuated copies
        # of that same source (which reduced ordinary bursts to one weak speck).
        count=math.ceil(pair('spark_count'))
        if not 0<=count<=MAX_BURST:raise ValueError('Ribbon burst count exceeds its fixed-capacity admission proof')
        if count==0:return False
        lifetime=pair('spark_lifetime')
        if not .2<=lifetime<=8.:raise ValueError('Ribbon burst lifetime exceeds the fixed-capacity admission proof')
        packet=snapshot.packet
        data=np.frombuffer(packet.payload,np.float32).reshape(packet.instances,-1,4)
        positions=[];widths=[];twists=[];colours=[];weights=[]
        # Fixed authored world emitters cover the body and its identical endpoint field.
        # Camera/viewport affect only drawing; they never select births or their identities.
        span=pair('spark_span')
        xs=np.linspace(-span*.5,span*.5,128)
        origin=np.asarray(packet.world_origin)+np.array((snapshot.head_x-snapshot.travel,0.,0.))
        local_x=xs-origin[0]
        for path in data:
            if path[2,3]<=.02:continue
            n,start,capacity=int(path[0,0]),int(path[1,1]),int(path[1,2])
            knots=path[4:].reshape(-1,KNOT_ROWS,4)[(start+np.arange(n))%capacity]
            if n<4:continue
            field=cloth_values(knots,local_x)
            positions.append(np.column_stack((xs,field[:,:2]+origin[1:])))
            widths.append(field[:,2]);twists.append(field[:,3]+path[1,0])
            tint=np.column_stack([np.interp(local_x,knots[:,0,0],knots[:,4,j]) for j in range(4)])
            header=.5*(path[2,:3]+path[3,:3])
            colours.append(header[None,:]*(1.-tint[:,3,None])+tint[:,:3]*tint[:,3,None])
            # Halos gather around this ribbon's own crests, while a fixed floor keeps every part of the visible
            # span eligible: births are never pinned to one spot, and a fading ribbon emits in proportion.
            height=field[:,0]
            crest=np.clip(1.4*(height-height.mean())/(height.std()+.05),-3.,3.)
            weights.append(float(path[2,3])*(.3+np.exp(crest)))
        if not positions or not any(len(p) for p in positions):return False
        p=np.concatenate(positions);w=np.concatenate(widths);theta=np.concatenate(twists);colour=np.concatenate(colours)
        weight=np.concatenate(weights);weight/=weight.sum()
        free=np.flatnonzero((self.records[:,7]<=0.)|(now-self.origin-self.records[:,3]>=self.records[:,7]))
        if len(free)<count:raise RuntimeError('Ribbon burst admission exceeded its proven capacity')
        new_origin=math.floor(now/16.)*16.
        self.records[:,3]-=new_origin-self.origin;self.origin=new_origin
        self.serial+=1
        rng=np.random.default_rng(self.serial)
        chosen=rng.choice(len(p),count,p=weight);side=rng.choice((-1.,1.),count)
        birth=p[chosen].copy()
        normal=np.column_stack((np.cos(theta[chosen]),np.sin(theta[chosen])))*side[:,None]
        birth[:,1:]+=normal*w[chosen,None]
        # Same monotone floor-contact map as the ribbon surface, applied after its swept rim position.
        height=(birth[:,1]-.03)/.15
        birth[:,1]=.03+.15*np.logaddexp(0.,height)
        # Leave the rim outward with an authored rise and a random spread; varied speeds fill a halo, not a shell.
        direction=.7*rng.normal(size=(count,3))
        direction[:,1:]+=normal;direction[:,1]+=pair('spark_rise')
        direction/=np.maximum(np.linalg.norm(direction,axis=1,keepdims=True),1e-6)
        speed=pair('spark_drift')*(.35+.65*rng.random(count))
        out=self.records[free[:count]].copy()
        out[:,:3]=birth;out[:,3]=now-self.origin
        out[:,4:7]=direction*speed[:,None];out[:,7]=lifetime*(.7+.3*rng.random(count))
        out[:,8:11]=colour[chosen];out[:,11]=pair('spark_size')*(.55+.45*rng.random(count))
        out[:,12]=pair('spark_light');out[:,13]=pair('spark_white')
        out[:,14]=rng.random(count);out[:,15]=pair('spark_glow')
        self.records[free[:count]]=out
        self.payload=self.records.tobytes();self.last_birth=now;self.until=max(self.until,now+lifetime)
        return True
