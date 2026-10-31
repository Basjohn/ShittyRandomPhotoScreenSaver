"""Bounded logical material paths for GPU procedural EB populations.

Lagrangian material knots retain history while stream material moves through an
inlet. The GPU samples these frozen paths; it never advances a solver.
"""
from __future__ import annotations
import math
import numpy as np
from core.constants.extruded_bubble_world import WORLD_CENTER, WORLD_HALF, WORLD_UNIT
from widgets.spotify_visualizer.extruded_bubble_drift import velocity

PATH_NODES = 128
CHAIN_PATHS = 240
CHAINS_PER_STEP = 12  # free chains per step of the Bead Chains Range (the renderer's _CHAINS_PER_STEP)
BEAD_CARRY = 5. / WORLD_UNIT
# A free chain enters and leaves the drawn population across a band of this many chains of fill (narrower only below
# two chains, so no fill still draws nothing), and the logical fill moves at most CHAIN_FADE_RATE chains a second: a
# chain takes at least CHAIN_FADE_BAND / CHAIN_FADE_RATE seconds to fade in or out, however the music moves the fill.
# With a one-chain band and the beat follower in the fill, a column at the fill's edge blinked off and on (2026-10-31).
CHAIN_FADE_BAND = 4.0
CHAIN_FADE_RATE = 4.0


def seeded_random(indices, salt):
    """The existing procedural 24-bit hash; stable CPU/GPU identities."""
    x = np.asarray(indices, dtype=np.uint32) * np.uint32(0x9e3779b9) ^ np.uint32((salt * 0x85ebca6b) & 0xffffffff)
    x ^= x >> 16; x *= np.uint32(0x7feb352d); x ^= x >> 15; x *= np.uint32(0x846ca68b); x ^= x >> 16
    return (x & 0xffffff).astype(np.float64) / 16777215.


def scene_entries(face_seed, uv, direction, weights):
    """Same physical inlet and exit lengths as sceneInlet in the procedural shader."""
    d = np.asarray(direction); half = np.asarray(WORLD_HALF); centre = np.asarray(WORLD_CENTER)
    choice = np.asarray(face_seed) * sum(weights)
    axis = np.where(choice < weights[0], 0, np.where(choice < weights[0]+weights[1],1,2))
    uv = np.asarray(uv)
    points = np.empty((len(axis),3))
    for k in range(3):
        mask = axis == k; other = [i for i in range(3) if i != k]
        points[mask,k] = centre[k] - np.sign(d[k]) * half[k]
        points[np.ix_(mask,other)] = centre[other] + (uv[mask]*2.-1.) * half[other]
    distances = np.full_like(points, 1e10)
    for k in range(3):
        if abs(d[k]) > 1e-6:
            distances[:,k] = (centre[k] + np.sign(d[k])*half[k] - points[:,k]) / d[k]
    return points, np.maximum(.001,np.min(distances,axis=1))


class MaterialPaths:
    """Lagrangian material knots, with two boundary ghosts and no resampling diffusion.

    Knots move through progress with the stream and integrate physical drift at
    their own current positions. A bounded ring reindex preserves every retained
    knot; only fresh upstream material starts at zero. The renderer interpolates
    once between knots, including true inlet/outlet neighbours.
    """
    def __init__(self, nodes=PATH_NODES):
        if nodes < 5:
            raise ValueError('Material paths need interior knots and boundary ghosts')
        self.nodes = nodes
        self.progress = (np.arange(nodes)-1.)/(nodes-3.)
        self.displacement = None
        self.base = self.spans = self.travel = None
        self.shift = self.phase_offset = self._definition = None
        self._source = None  # the caller's (never mutated) definition array last seen, for an identity fast path

    def _resize(self, definition, spans, travel):
        """Keep the retained rows' state; a newly admitted row starts fresh, exactly as a new path would."""
        count, keep = len(definition), min(len(definition), len(self.displacement))
        displacement = np.zeros_like(definition); displacement[:keep] = self.displacement[:keep]
        shift = np.zeros(count); shift[:keep] = self.shift[:keep]
        phase_offset = np.zeros(count); phase_offset[:keep] = self.phase_offset[:keep]
        fresh = definition[keep:, :1] + (definition[keep:, -1:] - definition[keep:, :1]) * self.progress[None, :, None]
        self.displacement, self.shift, self.phase_offset = displacement, shift, phase_offset
        self.base = np.concatenate((self.base[:keep], fresh))
        self.spans = np.concatenate((self.spans[:keep], spans[keep:]))
        self.travel = np.concatenate((self.travel[:keep], travel[keep:]))
        self._definition = np.concatenate((self._definition[:keep], definition[keep:]))
        self._source = None

    def _sample(self, rows, coordinates, *, linear=True):
        at = (np.asarray(coordinates)-self.shift[:,None])*(self.nodes-3.)+1.
        at = np.clip(at,0.,self.nodes-1.)
        low=np.floor(at).astype(np.intp);high=np.minimum(low+1,self.nodes-1)
        path=np.arange(len(rows))[:,None];f=(at-low)[...,None]
        return rows[path,low]*(1.-f)+rows[path,high]*f

    def advance(self, base, spans, travel, speed, phases, dt, *, kind, phase, direction, across, depth_axis,
                origin, amount):
        definition=np.asarray(base);spans=np.asarray(spans);travel=np.asarray(travel)
        if definition.ndim!=3 or definition.shape[1:]!=(self.nodes,3):
            raise ValueError('Material paths require complete world-space inlet/exit rows')
        if self.displacement is None and (dt<=0 or amount==0.):
            return None
        count=len(definition)
        if self.displacement is None:
            self.displacement=np.zeros_like(definition)
            self.shift=np.zeros(count);self.phase_offset=np.zeros(count)
        else:
            if count!=len(self.displacement):
                self._resize(definition,spans,travel)
        if self._definition is not None and base is not self._source and not np.array_equal(definition,self._definition):
            # Preserve progress phase and world centreline at a path edit.
            # Static bead arc/scatter is still authored by the existing shader;
            # this does not claim to preserve that independently edited geometry.
            self.phase_offset = np.mod(self.phase_offset+self.travel/self.spans-self.travel/spans,1.)
            q=self.progress[None,:]+self.shift[:,None]
            new_base=definition[:,:1]+(definition[:,-1:]-definition[:,:1])*q[...,None]
            self.displacement += self.base-new_base
        rate=np.asarray(speed)/spans
        shifted=self.shift+rate*dt
        step=1./(self.nodes-3.)
        moved=np.floor(shifted/step+1e-10).astype(np.intp)
        self.shift=shifted-moved*step
        if np.any(moved):
            # Only the paths that advanced a knot shift their history; the others keep theirs as it is.
            rows=np.flatnonzero(moved)
            source=np.arange(self.nodes)[None,:]-moved[rows,None]
            shifted_rows=self.displacement[rows[:,None],np.maximum(source,0)]
            shifted_rows[source<0]=0.
            self.displacement[rows]=shifted_rows
        q=self.progress[None,:]+self.shift[:,None]
        node_base=definition[:,:1]+(definition[:,-1:]-definition[:,:1])*q[...,None]
        world=node_base+self.displacement
        field=velocity(kind,tuple(world[...,i] for i in range(3)),np.asarray(phases)[:,None],phase,
                       direction,across,depth_axis,origin,amount,ops=np)
        available=np.maximum(0.,np.minimum(dt,q/np.maximum(rate[:,None],1e-12)))
        for axis,component in enumerate(field):
            self.displacement[...,axis] += component*available
        self.displacement[q<=0.]=0.
        self.base,self.spans,self.travel=node_base,spans.copy(),travel.copy()
        if base is not self._source:
            # The caller's cached geometry is never mutated: the same object means the same definition.
            self._definition=definition.copy();self._source=base
        return self.displacement


def drawable_chains(bead_chains) -> int:
    """The most free chains the renderer can ever draw for this Bead Chains Range (its high end x chains per step at
    the full particle share); rows past it are never read, so the logical side need not solve them."""
    return min(CHAIN_PATHS, math.ceil(max(float(v) for v in bead_chains) * CHAINS_PER_STEP))


def chain_band(fill: float) -> float:
    """How many chains of fill the edge of the free-chain population fades across (the bead shader's band)."""
    return min(CHAIN_FADE_BAND, max(1.0, 2.0 * float(fill)))


def chain_opacity(fill: float, chain: int) -> float:
    """Free chain ``chain``'s population opacity at this fill; the opacities sum to the fill. Mirrors the shader."""
    return min(1.0, max(0.0, (float(fill) - (chain + 0.5)) / chain_band(fill) + 0.5))


def chain_draw_count(fill: float, bead_chains) -> int:
    """The chains whose population opacity can be above zero at this fill, within the rows the logical side solves."""
    fill = float(fill)
    if fill <= 0.0:
        return 0
    return max(0, min(drawable_chains(bead_chains), math.ceil(fill + 0.5 * chain_band(fill) - 0.5)))


def chain_geometry(controls, direction, across, depth_axis, face_weights, nodes=PATH_NODES, paths=CHAIN_PATHS):
    """The first ``paths`` stable chains: each row depends only on its own seeded identity."""
    from core.settings.visualizer_paths import world_point
    ids=np.arange(paths,dtype=np.uint32)
    source=np.asarray(world_point(controls.stream_path[:3],WORLD_HALF))
    end=np.asarray(world_point(controls.stream_path[3:],WORLD_HALF))
    if controls.emission_geometry=='SCENE':
        start,spans=scene_entries(seeded_random(ids,31),
            np.stack((seeded_random(ids,32),seeded_random(ids,33)),axis=-1),direction,face_weights)
    else:
        width=min(WORLD_HALF[0],WORLD_HALF[2])*.28*controls.particle_spread
        start=(source+np.asarray(across)[None,:]*(seeded_random(ids,1)*2.-1.)[:,None]*width
               +np.asarray(depth_axis)[None,:]*(seeded_random(ids,3)*2.-1.)[:,None]*width)
        spans=np.full(paths,np.linalg.norm(end-source))
    q=np.linspace(0.,1.,nodes)
    base=start[:,None,:]+np.asarray(direction)[None,None,:]*spans[:,None,None]*q[None,:,None]
    return base,spans,BEAD_CARRY*(.7+.6*seeded_random(ids,5)),6.2832*seeded_random(ids,6)


def cloud_geometry(controls, direction, across, depth_axis, face_weights, family, count):
    """Stable seeded bases of actual GPU motes, cached until authored geometry changes."""
    from core.settings.visualizer_paths import world_point
    ids=np.arange(count,dtype=np.uint32)
    salts=(13,14,15,34) if family=='snow' else (1,3,5,23)
    seed=np.stack([seeded_random(ids,salt) for salt in salts[:3]],axis=-1)
    source=np.asarray(world_point(controls.stream_path[:3],WORLD_HALF))
    end=np.asarray(world_point(controls.stream_path[3:],WORLD_HALF))
    if controls.emission_geometry=='SCENE':
        start,spans=scene_entries(seeded_random(ids,salts[3]),seed[:,(0,2)],direction,face_weights)
    else:
        if family=='specks':
            transverse=np.cross(direction,(0.,1.,0.) if abs(direction[1])<.9 else (0.,0.,1.))
            transverse/=np.linalg.norm(transverse);deep=np.cross(direction,transverse);width=.52
        else:
            transverse,deep=np.asarray(across),np.asarray(depth_axis);width=.46
        width*=min(WORLD_HALF[0],WORLD_HALF[2])*controls.particle_spread
        start=source+transverse[None,:]*(seed[:,0]*2.-1.)[:,None]*width+deep[None,:]*(seed[:,2]*2.-1.)[:,None]*width
        spans=np.full(count,np.linalg.norm(end-source))
    return start,spans,seed[:,1],8./WORLD_UNIT if family=='snow' else .30,6.2832*seeded_random(ids,6)


class ProceduralOffsets:
    """Batched physical drift for stable GPU mote IDs, with no per-mote Python objects.

    The shader's existing analytic stream bases remain authoritative. Only extra
    displacement/phase crosses the snapshot. Reset at actual inlet recycling is
    explicitly invisible for one logical sample, never a visible offset reset.
    """
    def __init__(self):
        self.displacement=np.zeros((0,3))
        self.phase_offset=np.zeros(0)
        self.previous_base=np.zeros((0,3))
        self.geometry_key=None
        self.spans=np.zeros(0);self.carry=0.;self.travel=0.
        self._geometry=self._progress=None  # last call's geometry object and progress, reused when unchanged

    def advance(self, geometry, key, travel, speed, dt, *, kind, phase, direction, across, depth_axis, origin, amount):
        start,spans,seed,carry,phases=geometry
        count=len(seed);old_count=len(self.displacement);overlap=min(count,old_count)
        if count!=old_count:
            offsets=np.zeros((count,3));offsets[:overlap]=self.displacement[:overlap]
            phase_offsets=np.zeros(count);phase_offsets[:overlap]=self.phase_offset[:overlap]
            self.displacement,self.phase_offset=offsets,phase_offsets
        if self.geometry_key is not None and key!=self.geometry_key:
            self.phase_offset[:overlap]=np.mod(self.phase_offset[:overlap]
                +self.travel*self.carry/self.spans[:overlap]-self.travel*carry/spans[:overlap],1.)
            previous_q=np.mod(seed[:overlap]+self.travel*carry/spans[:overlap]+self.phase_offset[:overlap],1.)
            new_previous_base=start[:overlap]+np.asarray(direction)[None,:]*(previous_q*spans[:overlap])[:,None]
            self.displacement[:overlap]+=self.previous_base[:overlap]-new_previous_base
        if geometry is self._geometry and key==self.geometry_key and count==old_count:
            previous_q=self._progress   # the same expression over the same arrays as last call's progress
        else:
            previous_q=np.mod(seed+self.travel*carry/spans+self.phase_offset,1.)
        progress=np.mod(seed+travel*carry/spans+self.phase_offset,1.)
        recycled=(progress<previous_q-1e-10)|((travel-self.travel)*carry/spans>=1.) if old_count else np.zeros(count,dtype=bool)
        self.displacement[recycled]=0.
        base=start+np.asarray(direction)[None,:]*(progress*spans)[:,None]
        world=base+self.displacement
        field=velocity(kind,tuple(world.T),phases,phase,direction,across,depth_axis,origin,amount,ops=np)
        available=np.where(recycled,np.minimum(dt,progress*spans/max(speed*carry,1e-12)),dt)
        for axis,component in enumerate(field):
            self.displacement[:,axis]+=component*available
        packed=np.empty((count,4),dtype=np.float32);packed[:,:3]=self.displacement
        # Publish resolved progress too: the renderer must not independently
        # round a lifetime wrap from a large travel/span quotient.
        packed[:,3]=progress-recycled.astype(float)
        self.previous_base=base;self.spans=spans;self.carry=carry;self.travel=travel;self.geometry_key=key
        self._geometry,self._progress=geometry,progress
        return packed
