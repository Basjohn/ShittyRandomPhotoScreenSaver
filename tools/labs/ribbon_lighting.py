"""Lab optical reduction of admitted ribbon history, not a runtime per-frame producer.

One soft source per absolute two-second history bin and uninterrupted strip. Area/emission-weighted moments of
control segments approximate low-frequency light from the sheet. They are deliberately not a second spline,
surface-clearance oracle or simulation. Source radius includes the segment extent and sheet width. Moving the
camera never changes these lights; moving the actual packet does. Over-capacity fails instead of dropping light.
"""
import numpy as np

from core.ribbon_packet import KNOT_ROWS
from rendering.gl_programs.lighting import MAX_SOFT_LIGHTS


def ribbon_lights(packet, translation, age_fade, *, bin_seconds=2.):
    """Return contiguous float32 centre/radius² and RGB arrays for the lab's shared-lattice ring packet."""
    if not np.isfinite(bin_seconds) or bin_seconds <= 0:
        raise ValueError('Light bin duration must be finite and positive')
    now, fade_in, lifetime, fade_out = age_fade
    positions, fluxes = [], []
    origin = np.asarray(packet.world_origin, float)+np.asarray(translation, float)
    if not packet.instances:
        return np.empty((0,4),np.float32), np.empty((0,3),np.float32)
    rows = np.frombuffer(packet.payload,np.float32).reshape(packet.instances,-1,4)
    for path in rows:
        count, start, capacity = int(path[0,0]), int(path[1,1]), int(path[1,2])
        knots = path[4:].reshape(-1,KNOT_ROWS,4)[(start+np.arange(count))%capacity].astype(float)
        left, right = knots[:-1], knots[1:]
        valid = (left[:,1,2]>.5)&(right[:,1,2]>.5)&(right[:,1,3]<.5)
        coordinate = .5*(left[:,1,0]+right[:,1,0])+packet.coordinate_origin
        age = now-coordinate
        def smooth(x):
            x=np.clip(x,0.,1.)
            return x*x*(3.-2.*x)
        fade = (smooth(age/fade_in) if fade_in>0 else np.ones_like(age))
        fade *= (smooth((lifetime-age)/fade_out) if fade_out>0 else 1.)
        width = .5*(left[:,0,3]+right[:,0,3])
        emission = .5*(left[:,3,3]+right[:,3,3])
        length = np.linalg.norm(right[:,0,:3]-left[:,0,:3],axis=1)
        weight = length*2.*width*emission*fade
        centre = .5*(left[:,0,:3]+right[:,0,:3])
        # Stable bins do not slide through the entire population when the history ring evicts one knot.
        bins = np.floor(coordinate/bin_seconds).astype(np.int64)
        runs = np.cumsum(~valid)
        keys = np.stack((runs,bins),axis=1)
        for key in np.unique(keys[valid],axis=0):
            select=valid&np.all(keys==key,axis=1)
            w=weight[select]
            total=w.sum()
            if total<=0:
                continue
            c=np.sum(centre[select]*w[:,None],axis=0)/total
            variance=np.sum(w*(np.sum((centre[select]-c)**2,axis=1)+width[select]**2/3.+length[select]**2/12.))/total
            positions.append((*tuple(c+origin),max(variance,.01)))
            fluxes.append(.5*(path[2,:3]+path[3,:3])*total)
    if len(positions)>MAX_SOFT_LIGHTS:
        raise ValueError(f'Ribbon illumination exceeds {MAX_SOFT_LIGHTS} soft sources')
    return np.asarray(positions,np.float32).reshape(-1,4),np.asarray(fluxes,np.float32).reshape(-1,3)
