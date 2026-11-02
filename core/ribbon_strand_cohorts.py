"""Logical-clock strand admission held by root identity; rendering only evaluates age and the current sheet."""
from dataclasses import dataclass
import math
import numpy as np
from core.ribbon_geometry import MAX_PATH_SAMPLES
from core.ribbon_packet import KNOT_ROWS

COHORT_ROWS=3  # timing/admission, held geometry/light, held finish
COHORT_BYTES=MAX_PATH_SAMPLES*COHORT_ROWS*16


@dataclass(frozen=True)
class RibbonStrandControls:
    ranges: object


class RibbonStrandCohorts:
    def __init__(self, instances):
        self.records=np.zeros((instances,MAX_PATH_SAMPLES,COHORT_ROWS,4),np.float32)
        self.identities=np.full((instances,MAX_PATH_SAMPLES),np.iinfo(np.int64).min,np.int64)
        self.origin=0.
        self._has_live=False
        self.payload=b''
        self._history=None

    def update(self,snapshot,controls,hit,*,history,knot_hz):
        now=snapshot.time
        changed_history=history is not self._history
        if hit<.08 and not changed_history:
            return self.payload if self._has_live else b''
        self._history=history
        packet=snapshot.packet
        paths=np.frombuffer(packet.payload,np.float32).reshape(packet.instances,-1,4)
        knots=paths[:,4:].reshape(packet.instances,MAX_PATH_SAMPLES,KNOT_ROWS,4)
        identities=np.rint((knots[:,:,1,0].astype(float)+packet.coordinate_origin)*knot_hz).astype(np.int64)
        timing=self.records[:,:,0]
        replaced=identities!=self.identities
        changed=bool((timing[:,:,0][replaced]>0.).any())
        self.records[replaced]=0.
        self.identities[:]=identities
        if hit>=.08:
            drive=dict(snapshot.drives)['sparkle'];values=dict(snapshot.realized)
            def pair(key):
                low,high=controls.ranges[key]
                return float(low)+(float(high)-float(low))*drive
            admission=min(1.,values['sparkle'])*pair('strand_chance')*pair('strand_count')/8.
            x=knots[:,:,0,0]+packet.world_origin[0]+snapshot.head_x-snapshot.travel
            active=timing[:,:,0]>0.
            candidate=(np.abs(x)<=pair('strand_span')*.5)&(paths[:,2,3,None]>.02)
            eligible=(~active)&candidate
            if admission>0. and candidate.any():
                origin=math.floor(now/16.)*16.
                timing[:,:,1:3]-=origin-self.origin;self.origin=origin
                # Living roots keep their admission/look. A repeat event adds a
                # temporary length/glow pulse instead of killing and respawning them.
                repeat=active&candidate
                elapsed=np.maximum(now-self.origin-timing[:,:,2][repeat],0.)
                previous=np.clip((timing[:,:,3][repeat]+(1.-timing[:,:,3][repeat])*1.3
                    *(1.-np.exp(-elapsed/.025)))*np.exp(-elapsed/.35),0.,1.)
                timing[:,:,2][repeat]=now-self.origin
                timing[:,:,3][repeat]=previous
                timing[:,:,0][eligible]=admission
                timing[:,:,1][eligible]=now-self.origin
                timing[:,:,2][eligible]=now-self.origin-100.
                timing[:,:,3][eligible]=0.
                self.records[:,:,1][eligible]=[pair(key) for key in ('strand_length','strand_reach','strand_width','strand_light')]
                self.records[:,:,2][eligible]=[pair(key) for key in ('strand_beads','strand_peel','strand_halo','strand_glow')]
                changed=True
        if changed:
            self.payload=self.records.tobytes()
            self._has_live=bool((timing[:,:,0]>0.).any())
        return self.payload if self._has_live else b''
