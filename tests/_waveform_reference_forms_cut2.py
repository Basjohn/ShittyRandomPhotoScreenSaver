"""The straightforward forms of Waveform's logical-tick hot paths before the second tick cut (7 Nov 2026, main
cba6ee54): the snapshot as written (every packet-only term recomputed each tick, ``%`` for the HSV remainders, card
crest and HSV columns rebuilt each tick, the surge's windows from the packet headers), the spark emitter's cloth
evaluation (continuing an empty side) and the drive routing (each source clamped per target).

They are the oracle of ``tests/test_waveform_logical_tick_exactness.py``: each is patched over its production
counterpart and the published frames must stay byte-identical. Keep them as written (operation order included);
they are not production code and must never be imported by it.
"""
from __future__ import annotations

import colorsys
import math

import numpy as np

from core.ribbon_continuation import ANCHOR_INSET, anchored_values, anchors, continued_values
from core.ribbon_packet import KNOT_ROWS, RibbonPacket
from core.waveform_ribbon_authoring import RIBBON_CAPACITY, TARGETS
from core.waveform_ribbon_dynamics import (HIT_GLOW, HybridSnapshot, PACKET_FLOOR_HEIGHT, PULSE_GLOW, PULSE_GREY,
                                           PULSE_GRID, PULSE_SURGE, TOP_CLEARANCE, TROUGH_CLEARANCE, TROUGH_ROOM_MIN,
                                           unit)


def route(row, sources, *, passage=1.):
    return min(1., sum(gain * max(0., min(1., source)) ** power * (passage if index<3 else 1.)
                       for index,((gain, power), source) in enumerate(zip(row, sources))))


def cloth_values(knots, xs, phase=None):
    knots=np.asarray(knots,float);xs=np.asarray(xs,float)
    if phase is not None and len(knots)>=2*ANCHOR_INSET+2:
        tail,head=anchors(knots,phase)
        result=np.empty(xs.shape+(4,))
        inside=(xs>=tail)&(xs<=head)
        if inside.any():result[inside]=cloth_values(knots,xs[inside])
        for before,mask in ((True,xs<tail),(False,xs>head)):
            if mask.any():result[mask]=anchored_values(knots,xs[mask],phase,before)
        return result
    lo=np.clip(np.searchsorted(knots[:,0,0],xs,side='right')-1,0,len(knots)-2)
    controls=knots[np.clip(lo[:,None]+np.arange(-1,3),0,len(knots)-1)].copy()
    values=np.concatenate((controls[:,:,0,1:4],controls[:,:,1,1,None]),axis=2)
    first,last=lo==0,lo==len(knots)-2
    controls[first,0,0,:3]=2*controls[first,1,0,:3]-controls[first,2,0,:3]
    values[first,0,:2]=controls[first,0,0,1:3]
    controls[last,3,0,:3]=2*controls[last,2,0,:3]-controls[last,1,0,:3]
    values[last,3,:2]=controls[last,3,0,1:3]
    axial=controls[:,:,0,0]
    u=np.clip((xs-axial[:,1])/(axial[:,2]-axial[:,1]),0,1)
    def weights(u):
        return np.stack(((1-u)**3,3*u**3-6*u*u+4,-3*u**3+3*u*u+3*u+1,u**3),1)/6
    for _ in range(5):
        dw=np.stack((-3*(1-u)**2,9*u*u-12*u,-9*u*u+6*u+3,3*u*u),1)/6
        u=np.clip(u-((weights(u)*axial).sum(1)-xs)/(dw*axial).sum(1),0,1)
    result=(weights(u)[:,:,None]*values).sum(1)
    for before,mask in ((True,xs<knots[0,0,0]),(False,xs>knots[-1,0,0])):
        result[mask]=continued_values(knots,xs[mask],before)
    return result


def snapshot(self):
    if self._snapshot is not None:
        return self._snapshot
    if not self.ready:
        self._snapshot = HybridSnapshot(RibbonPacket(b'',0,0),0.,0.,0.,0.,0.,(),(),False)
        return self._snapshot
    raw = self.ring.packet()
    if raw is not self._base_packet:
        base=np.frombuffer(raw.payload,np.float32).reshape(RIBBON_CAPACITY,-1,4)
        # Fixed-x cloth has no transported-frame breaks. Check once per changed history packet (6 Hz),
        # before publication to the GPU reducer, rather than silently clearing a corridor across a gap.
        for path in base:
            count,start,capacity=int(path[0,0]),int(path[1,1]),int(path[1,2])
            knots=path[4:].reshape(-1,KNOT_ROWS,4)[(start+np.arange(count))%capacity]
            if count<4 or not (knots[:,1,2]>.5).all() or (knots[1:,1,3]>.5).any() or not (np.diff(knots[:,0,0])>0).all():
                raise ValueError('Waveform cloth history must be one valid monotone axial run')
        self._base_packet,self._base_array=raw,base
    data = self._base_array.copy()
    rows = data[:,4::KNOT_ROWS]
    # Cloth coordinate: fixed to the travelling history, so musical bends are sweeps carried by the ribbon
    # rather than a stationary lump field the cloth slides through.
    u = rows[:,:,0]+raw.world_origin[0]
    x = u+self.controls.scene.flow.head_x-self.travel
    owner = np.arange(RIBBON_CAPACITY)[:,None]
    # Keep elastic excursions legible above ordinary sustained input; the old unit tanh compressed hits twice.
    b,m,h = (3.*np.tanh(np.asarray(self.spring)/3.)).T[:,:,None]
    values = {key:self._value(key) for key in TARGETS}
    carrier = rows[:,:,1]+raw.world_origin[1]-2.
    # No time-varying axial scaling: horizontal motion is only the steady flow (DevCurve's rule). The former
    # elastic stretch scaled x about the centre on every kick and read as sideways bursts (operator, 5 Nov).
    # The axial roll turns the carrier (its helix and the bundle's separation) like a skewer. Height scales
    # both transverse carrier components, so a turn changes the visible phase, never the visible amplitude.
    separation = .65*(owner-1.)
    depth_wave = rows[:,:,2]+raw.world_origin[2]-separation
    # The travelling pulse swells the carrier's own crests and troughs where it is: always WITH the shape.
    # Appearance follows the authored-width band (legible, travelling); geometry follows the broad bounded
    # envelope so whole waves swell together and the curvature keeps its own sign (flow rule).
    swell = self.pulse_at(x)
    # Beyond the field the published edge value continues (a Whole Swell never ends at the grid edge).
    broad = np.interp(x,PULSE_GRID,self.geometric_gain(values['bend']))
    geometric = np.interp(x,PULSE_GRID,self._geom)
    gain = broad
    cy = carrier*values['height']*gain
    cz = depth_wave*values['height']*gain+separation*values['spread']
    cosine,sine = math.cos(self.angle),math.sin(self.angle)
    y,z = cosine*cy-sine*cz,sine*cy+cosine*cz
    # Depth sway acts in world space after the roll and travels with the cloth. The former standing bend
    # (a fixed spatial sine the ribbon slid through) is replaced by the travelling pulse above.
    z = z+.4*values['depth']*m*np.cos(.65*u+owner)
    idle=self.controls.idle_motion*(1.-self.passage)
    y+=idle*.08*np.sin(.45*self.time+.6*u+owner)
    z+=idle*.05*np.cos(.33*self.time+.4*u-owner)
    x,y,z = self._surge(data,x,y,z,PULSE_SURGE*values['bend'])
    rows[:,:,0] = x-raw.world_origin[0]-self.controls.scene.flow.head_x+self.travel
    # One common smooth bounding domain prevents floor-crossing/clamp kinks at extreme editor values. Peaks
    # are meant to rise high: the framing makes room for them, the body is never capped to fit a frame.
    rows[:,:,3] = 3.5*np.tanh(rows[:,:,3]*values['width']*(1.+.35*geometric)/3.5)
    rows[:,:,2] = 5.*np.tanh(z/5.)
    origin_twist = (data[:,1,0,None]+math.pi)%(2*math.pi)-math.pi
    twist = data[:,5::KNOT_ROWS,1]+origin_twist
    twist = twist*values['twist']+values['torsion']*(1.6*m*np.sin(.45*u+owner)+.12*h*np.sin(.7*u-owner))
    data[:,5::KNOT_ROWS,1] = twist+self.twist_phase+self.angle+idle*.18*np.sin(.28*self.time+.3*u+owner)
    data[:,1,0] = 0.
    # Admission phase of the history ring in [0, 1) (header extra.w): the renderer anchors the visible ends inside
    # the history and continues from there, so admitting/evicting a knot never steps the ends (core.ribbon_continuation).
    data[:,1,3] = unit((self.time-(self._next_knot-1./self.controls.scene.flow.knot_hz))*self.controls.scene.flow.knot_hz)
    # The floor is never hit and the shape never changes (operator, 5 Nov: "we collide with the floor a lot";
    # then: per-knot trough limits made boxy flat-bottomed troughs "instead of FLOWING"). When a ribbon's lower
    # edge (the cloth sweep's side is cos(twist)*Y + sin(twist)*Z, so the sheet hangs width*|cos(twist)| below its
    # centre) would come within TROUGH_CLEARANCE of the floor, the WHOLE ribbon rises (up to TROUGH_LIFT_MAX): an
    # offset is the only bound that preserves the shape exactly, so nothing is ever bent against its shape. The lift
    # eases through two stages on the logical clock (see _floor_room); a deeper trough than the cap may still graze.
    hang = np.abs(rows[:,:,3]*np.cos(data[:,5::KNOT_ROWS,1]))
    room = max(TROUGH_ROOM_MIN,PACKET_FLOOR_HEIGHT+values['lift']-TROUGH_CLEARANCE)
    soft_y = 5.*np.tanh(y/5.)
    # The card's top above the packet's rest line, scaled with Dynamic Zoom (the long lens is all but orthographic).
    headroom = None if self._view_top is None else \
        (self._view_top-PACKET_FLOOR_HEIGHT)*self.zoom-TOP_CLEARANCE-values['lift']
    rise = self._height_shift(y,hang,room,x,soft_y,headroom)
    rows[:,:,1] = soft_y+values['lift']+rise
    # Strong local musical regions change colour immediately, even before new head history enters view.
    # The crest mask is carried by immutable carrier geometry, so coloured regions travel with the waveform.
    # All cards at once as rows; each card's Python scalars become a column in exactly the dtype NumPy would
    # have cast them to against that operand (``column``), so the packet is byte-identical to a per-card loop.
    n = len(self.controls.cards)
    if n:
        cards = self.controls.cards
        def column(values,like):
            return np.asarray(values,dtype=np.result_type(like.dtype,np.float32))[:,None]
        locals_ = [max(self.power,*self.bands) if card['band']=='All' else
                   self.bands[('Bass','Mids','Highs').index(card['band'])] for card in cards]
        magnitude = np.abs(carrier[:n])
        crest = np.clip(magnitude/column([max(1.5*card['height'],1e-5) for card in cards],magnitude),0.,1.)
        # Existing visible rim slots respond immediately; this eased source creates no simulation in the draw.
        data[:n,6::KNOT_ROWS,3] = np.maximum(data[:n,6::KNOT_ROWS,3],
            values['sparkle']*max(self._hit,.4*self.bands[2])*crest)
        data[:n,7::KNOT_ROWS,3] *= (1.+HIT_GLOW*self._glow*(.25+.75*crest))*(1.+PULSE_GLOW*swell[:n])
        weight = .25+.75*crest
        power = column(locals_,weight)*weight
        threshold = self.controls.colour_threshold
        share = np.clip((power-threshold)/max(1e-5,1.-threshold),0.,1.)
        share = share*share*(3.-2.*share)*values['colour']
        tint = data[:n,8::KNOT_ROWS]
        swelling = np.clip(swell[:n],0.,1.)
        share = np.maximum(np.maximum(share,tint[:,:,3]),self.controls.pulse.colour*swelling)
        # The cards' quiet/peak HSV depends only on the cards: converted once per card set, not every tick.
        cached = getattr(self,'_card_hsv',None)
        if cached is None or cached[0] is not cards:
            hsv = []
            for card in cards:
                quiet = tuple((a+b)*.5 for a,b in zip(*card['quiet']))
                peak = tuple((a+b)*.5 for a,b in zip(*card['peak']))
                a,b = colorsys.rgb_to_hsv(*quiet),colorsys.rgb_to_hsv(*peak)
                hsv.append((a[0],(b[0]-a[0]+.5)%1.-.5,a[1],b[1]-a[1],a[2],b[2]-a[2]))
            self._card_hsv = cached = (cards,hsv)
        hsv = cached[1]
        hue_a,hue_d,sat_a,sat_d,val_a,val_d = (column(field,share) for field in zip(*hsv))
        hue = (hue_a+hue_d*share)%1.
        saturation = sat_a+sat_d*share
        value = val_a+val_d*share
        # The swell deepens colour where it is: saturation rises toward 1 (never toward white), hue and value
        # keep their own logic, and a neutral colour stays neutral rather than gaining an invented hue.
        vivid = self.controls.pulse.saturation*swelling*np.clip(saturation/PULSE_GREY,0.,1.)
        saturation = saturation+(1.-saturation)*vivid
        share = np.maximum(share,vivid)
        k = (np.array((5.,3.,1.))+hue[:,:,None]*6.)%6.
        tint[:,:,:3] = value[:,:,None]*(1.-saturation[:,:,None]*np.clip(np.minimum(k,4.-k),0.,1.))
        alpha = np.clip(share/.1,0.,1.)
        tint[:,:,3] = alpha*alpha*(3.-2.*alpha)
    self._fade_ribbons(data,rows)
    packet = RibbonPacket(data.tobytes(),raw.instances,raw.vertices,(raw.world_origin[0],2.,0.),raw.coordinate_origin)
    self._snapshot = HybridSnapshot(packet,self.time,self.travel,self.angle,self.angular_speed,self.twist_phase,
        tuple(self.drive.items()),tuple(values.items()),self.ready,passage=self.passage,
        head_x=self.controls.scene.flow.head_x,zoom=self.zoom,direction=self.direction,
        pulse=(self._level if self._rim_share==1. else self._level*self._rim_share).astype(np.float32).tobytes())
    return self._snapshot
