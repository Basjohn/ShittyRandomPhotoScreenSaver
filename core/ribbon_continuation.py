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


def cloth_values(knots, xs):
    """Invert the monotone axial B-spline; evaluate its exact transverse fields."""
    knots=np.asarray(knots,float);xs=np.asarray(xs,float)
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
        for before,knots in ((True,controls[:3]),(False,controls[3:])):
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
