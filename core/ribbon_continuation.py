"""Qt-free mirror of the swept cloth's C2 endpoint continuation and view-only culling."""
from __future__ import annotations
import numpy as np


def endpoint_jet(knots, before):
    """Centre y/z, width, twist and their first/second axial derivatives."""
    indices = (0, 0, 1, 2) if before else (-3, -2, -1, -1)
    controls = np.asarray(knots, float)[list(indices)].copy()
    values = np.column_stack((controls[:, 0, 1:4], controls[:, 1, 1]))
    if before:
        controls[0, 0, :3] = 2*controls[1, 0, :3]-controls[2, 0, :3]
        values[0, :2] = controls[0, 0, 1:3]
        weights, first, second = np.array((1,4,1,0))/6, np.array((-1,0,1,0))/2, np.array((1,-2,1,0))
        origin = controls[1, 0, 0]
    else:
        controls[3, 0, :3] = 2*controls[2, 0, :3]-controls[1, 0, :3]
        values[3, :2] = controls[3, 0, 1:3]
        weights, first, second = np.array((0,1,4,1))/6, np.array((0,-1,0,1))/2, np.array((0,1,-2,1))
        origin = controls[2, 0, 0]
    dx, ddx = first @ controls[:,0,0], second @ controls[:,0,0]
    du, ddu = first @ values, second @ values
    return origin, weights @ values, du/dx, (ddu*dx-du*ddx)/dx**3, abs(controls[2,0,0]-controls[1,0,0])


def continued_values(knots, xs, before):
    origin, value, first, second, reach = endpoint_jet(knots, before)
    delta = np.asarray(xs, float)-origin
    result = np.broadcast_to(value, delta.shape+(4,)).copy()
    result[...,:2] += np.sin(delta)[...,None]*first[:2]+(1-np.cos(delta))[...,None]*second[:2]
    g1, g2 = first[2:].copy()*(-1 if before else 1), second[2:].copy()
    g2[0] = g2[0]/value[2]-(g1[0]/value[2])**2
    g1[0] /= value[2]
    s = np.minimum(np.abs(delta)/reach,80.)
    correction = (s[...,None]*g1*reach+s[...,None]**2*(.5*g2*reach**2+g1*reach))*np.exp(-s)[...,None]
    result[...,2] *= np.exp(correction[...,0]); result[...,3] += correction[...,1]
    return result


# Anchored ends (5 Nov: seen from the framed camera's extreme turn, the far end of the history "staggers"). Continuing
# from the oldest/newest KNOT moved the whole continuation, and the last spline segments, at every knot admission (the
# endpoint jet jumps to the next knot). With an admission ``phase`` in [0, 1) the visible history instead ends at anchors
# ANCHOR_INSET knots inside each end that advance with the phase, so they are fixed in the scene and reach the next knot
# exactly when the ring admits/evicts: the anchors' segments never involve an admitted or evicted knot, and the jets
# are evaluated on the C2 spline itself, so the continuation is continuous in time. Beyond them the same C2 extension.
ANCHOR_INSET = 2


def anchors(knots, phase):
    """Tail and head anchor x of the visible history for admission ``phase`` (needs 2*ANCHOR_INSET+2 knots)."""
    x=np.asarray(knots,float)[:,0,0];phase=min(max(float(phase),0.),1.)
    i,j=ANCHOR_INSET,len(x)-1-ANCHOR_INSET
    return x[i]+phase*(x[i+1]-x[i]),x[j-1]+phase*(x[j]-x[j-1])


def _spline_jet(knots, xs):
    """Value, d/dx and d2/dx2 of the exact cloth fields at axial x (inside the history)."""
    knots=np.asarray(knots,float);xs=np.atleast_1d(np.asarray(xs,float))
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
    def weights(u):return np.stack(((1-u)**3,3*u**3-6*u*u+4,-3*u**3+3*u*u+3*u+1,u**3),1)/6
    def slope(u):return np.stack((-3*(1-u)**2,9*u*u-12*u,-9*u*u+6*u+3,3*u*u),1)/6
    def bend(u):return np.stack((6*(1-u),18*u-12,-18*u+6,6*u),1)/6
    for _ in range(5):
        u=np.clip(u-((weights(u)*axial).sum(1)-xs)/(slope(u)*axial).sum(1),0,1)
    w,dw,ddw=weights(u),slope(u),bend(u)
    dx,ddx=(dw*axial).sum(1),(ddw*axial).sum(1)
    du,ddu=(dw[:,:,None]*values).sum(1),(ddw[:,:,None]*values).sum(1)
    return (w[:,:,None]*values).sum(1),du/dx[:,None],(ddu*dx[:,None]-du*ddx[:,None])/dx[:,None]**3


def anchored_values(knots, xs, phase, before):
    """C2 continuation beyond the tail (``before``) or head anchor; the same form as ``continued_values``."""
    knots=np.asarray(knots,float);tail,head=anchors(knots,phase)
    origin=tail if before else head
    value,first,second=(v[0] for v in _spline_jet(knots,[origin]))
    i=ANCHOR_INSET if before else len(knots)-2-ANCHOR_INSET
    reach=abs(knots[i+1,0,0]-knots[i,0,0])
    delta=np.asarray(xs,float)-origin
    result=np.broadcast_to(value,delta.shape+(4,)).copy()
    result[...,:2]+=np.sin(delta)[...,None]*first[:2]+(1-np.cos(delta))[...,None]*second[:2]
    g1,g2=first[2:].copy()*(-1 if before else 1),second[2:].copy()
    g2[0]=g2[0]/value[2]-(g1[0]/value[2])**2
    g1[0]/=value[2]
    scaled=np.minimum(np.abs(delta)/reach,80.)
    correction=(scaled[...,None]*g1*reach+scaled[...,None]**2*(.5*g2*reach**2+g1*reach))*np.exp(-scaled)[...,None]
    result[...,2]*=np.exp(correction[...,0]);result[...,3]+=correction[...,1]
    return result


def cloth_values(knots, xs, phase=None):
    """Invert the monotone axial B-spline; evaluate its exact transverse fields. With an admission ``phase`` (the
    packet header's extra.w) the history is drawn between its anchors and continued beyond them (see ``anchors``)."""
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
        cube=u**3   # u**3 once (it was evaluated three times; the same values)
        return np.stack(((1-u)**3,3*cube-6*u*u+4,-3*cube+3*u*u+3*u+1,cube),1)/6
    for _ in range(5):
        dw=np.stack((-3*(1-u)**2,9*u*u-12*u,-9*u*u+6*u+3,3*u*u),1)/6
        u=np.clip(u-((weights(u)*axial).sum(1)-xs)/(dw*axial).sum(1),0,1)
    result=(weights(u)[:,:,None]*values).sum(1)
    for before,mask in ((True,xs<knots[0,0,0]),(False,xs>knots[-1,0,0])):
        # Only a side with points beyond the history is continued (an empty side used to evaluate the whole
        # endpoint jet for nothing: always so inside the anchors, the anchored call's common case).
        if mask.any():result[mask]=continued_values(knots,xs[mask],before)
    return result


def continuation_bounds(packet, translation, camber):
    """Conservative current-cloth and C2-extension bounds, independent of a mode's amplitude policy.

    Interior cubic controls form a convex hull. Reduce their current published extrema; a hardcoded old
    amplitude domain cannot admit larger rolled crests. Endpoint jets bound the unbounded continuation.
    """
    rows = np.frombuffer(packet.payload, np.float32).reshape(packet.instances,-1,4)
    origin = np.asarray(packet.world_origin)+translation
    low, high = np.array((0.,0.)), np.array((0.,0.))
    for path in rows:
        count,start,capacity = int(path[0,0]),int(path[1,1]),int(path[1,2])
        if count<3 or min(path[2,3],path[3,3])<=0.0:continue
        history=path[4:].reshape(-1,5,4)[(start+np.arange(count))%capacity]
        radius=float(history[:,0,3].max())*np.sqrt(1.+camber*camber)
        centre=history[:,0,1:3]+origin[1:]
        low=np.minimum(low,centre.min(axis=0)-radius);high=np.maximum(high,centre.max(axis=0)+radius)
        indices=(start+np.array((0,1,2,count-3,count-2,count-1)))%capacity
        controls=path[4:].reshape(-1,5,4)[indices]
        anchored=count>=2*ANCHOR_INSET+2
        for before,knots in ((True,controls[:3]),(False,controls[3:])):
            if anchored:
                # The continuation starts at the anchors (see ``anchors``); bound their jets instead.
                v,d,dd=(value[0] for value in _spline_jet(history,[anchors(history,path[1,3])[0 if before else 1]]))
                i=ANCHOR_INSET if before else count-2-ANCHOR_INSET
                reach=abs(float(history[i+1,0,0]-history[i,0,0]))
            else:
                _,v,d,dd,reach=endpoint_jet(knots,before)
            # s*exp(-s/L)<=L/e; s²*exp(-s/L)<=4L²/e².
            g1=d[2]/v[2];g2=dd[2]/v[2]-g1*g1
            log_bound=abs(g1)*reach/np.e+abs(.5*g2+(-1 if before else 1)*g1/reach)*4*reach**2/np.e**2
            radius=v[2]*np.exp(log_bound)*np.sqrt(1+camber**2)
            centre=v[:2]+dd[:2]+origin[1:]
            amplitude=np.hypot(d[:2],dd[:2])
            low=np.minimum(low,centre-amplitude-radius);high=np.maximum(high,centre+amplitude+radius)
    # The 1-Lipschitz soft floor map never raises a point by more than .5 here.
    return (0.,float(high[0]+.5)),(float(low[1]),float(high[1]))


def frustum_axial_span(mvp, transverse):
    """Conservative x interval of a clipped view intersecting a fixed y/z slab.

    Only culling/tessellation depends on the view. Surface values never do.
    Each frustum half-space is bounded over the slab's four corners; this can
    overdraw, but cannot clip an admitted surface or miss an end-on view.
    """
    matrix=np.asarray(mvp,float).reshape(4,4)
    corners=np.array([(y,z,1.) for y in transverse[0] for z in transverse[1]])
    low,high=-np.inf,np.inf
    for axis in range(3):
        for sign in (-1,1):
            plane=matrix[3]+sign*matrix[axis]
            if abs(plane[0])<1e-12:continue
            limits=-(corners@plane[1:])/plane[0]
            if plane[0]>0:low=max(low,float(limits.min()))
            else:high=min(high,float(limits.max()))
    if not np.isfinite((low,high)).all():raise ValueError('Continuation needs a bounded physical frustum')
    return (low,high) if low<=high else (0.,0.)
