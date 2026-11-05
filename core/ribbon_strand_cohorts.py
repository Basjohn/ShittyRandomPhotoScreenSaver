"""Logical-clock strand admission held by root identity; rendering only evaluates age and the current sheet."""
from dataclasses import dataclass
import math
import numpy as np
from core.ribbon_geometry import MAX_PATH_SAMPLES
from core.ribbon_packet import KNOT_ROWS

COHORT_ROWS=4  # timing/admission, held geometry/light, held finish, EoL/fade/restore/activation
COHORT_BYTES=MAX_PATH_SAMPLES*COHORT_ROWS*16
ROOTS_PER_ACCENT=8
# A passing swell may lean an accent's few roots toward itself and lift their chance and glow a little.
# Restrained by design (operator: never hairy): no new admissions, no extra roots, life and fade untouched.
SWELL_LEAN=2.
SWELL_CHANCE=.5
SWELL_GLOW=.5


def remaining_strand(age,lifetime,fade,seed):
    """Fade amount within total lifetime; the shader dims tips earlier and recovers continuously on reactivation."""
    age=np.maximum(age,0.)
    span=np.maximum(np.minimum(fade,lifetime),1e-5)
    progress=np.clip((age-(lifetime-span))/span,0.,1.)
    expiry=1.-progress*progress*(3.-2.*progress)
    restoration=seed+(1.-seed)*(1.-np.exp(-age/np.maximum(.1,np.minimum(.4,lifetime*.1))))
    return np.minimum(expiry,restoration)


@dataclass(frozen=True)
class RibbonStrandControls:
    ranges: object


class RibbonStrandCohorts:
    def __init__(self, instances):
        self.records=np.zeros((instances,MAX_PATH_SAMPLES,COHORT_ROWS,4),np.float32)
        self.identities=np.full((instances,MAX_PATH_SAMPLES),np.iinfo(np.int64).min,np.int64)
        self.origin=0.
        self._visible_until=-math.inf
        self.payload=b''
        self._history=None
        self._accent_serial=0

    def update(self,snapshot,controls,hit,*,history,knot_hz,swell=None,gather=0.):
        now=snapshot.time
        changed_history=history is not self._history
        if hit<.08 and not changed_history:
            return self.payload if now<self._visible_until else b''
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
            self._accent_serial+=1
            drive=dict(snapshot.drives)['sparkle'];values=dict(snapshot.realized)
            def pair(key):
                low,high=controls.ranges[key]
                return float(low)+(float(high)-float(low))*drive
            admission=min(1.,values['sparkle'])*pair('strand_chance')*pair('strand_count')/8.
            x=knots[:,:,0,0]+packet.world_origin[0]+snapshot.head_x-snapshot.travel
            active=timing[:,:,0]>0.
            candidate=(np.abs(x)<=pair('strand_span')*.5)&(paths[:,2,3,None]>.02)
            age=now-(knots[:,:,1,0]+packet.coordinate_origin)
            candidate &= age+pair('strand_eol')<=(MAX_PATH_SAMPLES-1)/knot_hz
            if admission>0. and candidate.any():
                # A musical accent selects a few fixed-world roots; it must not renew every visible strand.
                roots=np.flatnonzero(candidate);count=min(len(roots),ROOTS_PER_ACCENT)
                phase=(self._accent_serial*.6180339887498949)%1.
                picks=(phase+np.arange(count)/count)%1.
                local=None
                if swell is not None and gather>0.:
                    local=np.clip(np.asarray(swell(x),np.float64),0.,1.)
                    if local.flat[roots].max()<=.02:local=None
                if local is None:
                    chosen=roots[(picks*len(roots)).astype(int)]
                else:
                    # Same evenly spaced picks through a swell-warped root density: the picks lean toward the
                    # swell (duplicates merge, so a lean can only lower the count, never raise it).
                    density=np.cumsum(1.+SWELL_LEAN*gather*local.flat[roots])
                    chosen=roots[np.minimum(np.searchsorted(density/density[-1],picks,side='right'),len(roots)-1)]
                selected=np.zeros_like(candidate);selected.flat[chosen]=True
                eligible=(~active)&selected
                origin=math.floor(now/16.)*16.
                shift=origin-self.origin
                timing[:,:,1:3]-=shift;self.records[:,:,3,3]-=shift;self.origin=origin
                # Living roots keep their admission/look. A repeat event adds a
                # temporary length/glow pulse instead of killing and respawning them.
                repeat=active&selected
                life=self.records[:,:,3]
                held=life[repeat]
                remaining=remaining_strand(now-self.origin-held[:,3],held[:,0],held[:,1],held[:,2])
                life[repeat]=np.column_stack((np.full(len(held),pair('strand_eol')),
                    np.full(len(held),pair('strand_eol')*pair('strand_fade')),remaining,np.full(len(held),now-self.origin)))
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
                life[eligible]=[pair('strand_eol'),pair('strand_eol')*pair('strand_fade'),1.,now-self.origin]
                if local is not None:
                    lift=gather*local[eligible]
                    timing[:,:,0][eligible]=np.minimum(1.,admission*(1.+SWELL_CHANCE*lift))
                    self.records[:,:,2,3][eligible]*=1.+SWELL_GLOW*lift
                changed=True
        if changed:
            self.payload=self.records.tobytes()
            active=timing[:,:,0]>0.
            life=self.records[:,:,3]
            self._visible_until=(self.origin+float(np.max((life[:,:,3]+life[:,:,0])[active]))
                                 if active.any() else -math.inf)
        return self.payload if now<self._visible_until else b''
