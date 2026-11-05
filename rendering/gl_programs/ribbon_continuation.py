"""C2 continuation of a monotone cloth's exact endpoint jets; no camera inputs.

Included after the caller's Knot/paths declarations. The history stays finite;
the same swept surface has an analytic definition at every axial coordinate.

Anchored ends (mirror: ``core.ribbon_continuation.anchors``): a path's header ``extra.w`` carries the ring's admission
phase in [0, 1). The visible history ends ANCHOR_INSET knots inside each end, at anchors that advance with that phase
(fixed in the scene, reaching the next knot exactly when the ring admits/evicts), and the continuation starts from the
C2 spline's own jet there. Continuing from the end KNOT jumped at every admission (the tail "staggered" in depth).
"""
CONTINUATION_GLSL = """
Knot continuationControl(int owner,int i) {
    int count=int(paths[owner].meta.x),cap=int(paths[owner].extra.z),start=int(paths[owner].extra.y);
    return paths[owner].knots[(start+clamp(i,0,count-1))%cap];
}
// Components: transverse centre y/z, half width, axial twist.
vec4 continuationValues(Knot k) { return vec4(k.p.yz,k.p.w,k.q.y); }
vec4 continuationWeights(float u) {
    float u2=u*u,u3=u2*u,v=1.0-u;
    return vec4(v*v*v,3.0*u3-6.0*u2+4.0,-3.0*u3+3.0*u2+3.0*u+1.0,u3)/6.0;
}
vec4 clothField(int owner,float x) {
    int last=int(paths[owner].meta.x)-1,lo=0,hi=last;
    while(hi-lo>1) { int mid=(lo+hi)/2;if(continuationControl(owner,mid).p.x<=x)lo=mid;else hi=mid; }
    Knot a=continuationControl(owner,lo-1),b=continuationControl(owner,lo),
         c=continuationControl(owner,hi),d=continuationControl(owner,hi+1);
    vec4 av=continuationValues(a),bv=continuationValues(b),cv=continuationValues(c),dv=continuationValues(d);
    if(lo==0) { a.p.xyz=2.0*b.p.xyz-c.p.xyz;av.xy=a.p.yz; }
    if(hi==last) { d.p.xyz=2.0*c.p.xyz-b.p.xyz;dv.xy=d.p.yz; }
    vec4 xs=vec4(a.p.x,b.p.x,c.p.x,d.p.x);
    float u=clamp((x-b.p.x)/(c.p.x-b.p.x),0.0,1.0);
    for(int i=0;i<5;i++) {
        vec4 w=continuationWeights(u);
        vec4 dw=vec4(-3.0*(1.0-u)*(1.0-u),9.0*u*u-12.0*u,-9.0*u*u+6.0*u+3.0,3.0*u*u)/6.0;
        u=clamp(u-(dot(w,xs)-x)/max(dot(dw,xs),1e-8),0.0,1.0);
    }
    vec4 w=continuationWeights(u);
    return av*w.x+bv*w.y+cv*w.z+dv*w.w;
}
const int ANCHOR_INSET=2;
bool continuationAnchored(int owner) { return int(paths[owner].meta.x)>=2*ANCHOR_INSET+2; }
// The anchor segment's first chronological knot: its controls never include an admitted or evicted knot.
int continuationAnchorKnot(int owner,bool before) {
    return before?ANCHOR_INSET:int(paths[owner].meta.x)-2-ANCHOR_INSET;
}
float continuationAnchor(int owner,bool before) {
    int last=int(paths[owner].meta.x)-1;
    if(!continuationAnchored(owner)) return continuationControl(owner,before?0:last).p.x;
    int i=continuationAnchorKnot(owner,before);
    return mix(continuationControl(owner,i).p.x,continuationControl(owner,i+1).p.x,clamp(paths[owner].extra.w,0.0,1.0));
}
// Exact cloth value and its first/second axial derivatives at x (same spline and guards as clothField).
void clothJet(int owner,float x,out vec4 value,out vec4 first,out vec4 second) {
    int last=int(paths[owner].meta.x)-1,lo=0,hi=last;
    while(hi-lo>1) { int mid=(lo+hi)/2;if(continuationControl(owner,mid).p.x<=x)lo=mid;else hi=mid; }
    Knot a=continuationControl(owner,lo-1),b=continuationControl(owner,lo),
         c=continuationControl(owner,hi),d=continuationControl(owner,hi+1);
    vec4 av=continuationValues(a),bv=continuationValues(b),cv=continuationValues(c),dv=continuationValues(d);
    if(lo==0) { a.p.xyz=2.0*b.p.xyz-c.p.xyz;av.xy=a.p.yz; }
    if(hi==last) { d.p.xyz=2.0*c.p.xyz-b.p.xyz;dv.xy=d.p.yz; }
    vec4 xs=vec4(a.p.x,b.p.x,c.p.x,d.p.x);
    float u=clamp((x-b.p.x)/(c.p.x-b.p.x),0.0,1.0);
    for(int i=0;i<5;i++) {
        vec4 w=continuationWeights(u);
        vec4 dw=vec4(-3.0*(1.0-u)*(1.0-u),9.0*u*u-12.0*u,-9.0*u*u+6.0*u+3.0,3.0*u*u)/6.0;
        u=clamp(u-(dot(w,xs)-x)/max(dot(dw,xs),1e-8),0.0,1.0);
    }
    vec4 w=continuationWeights(u);
    vec4 dw=vec4(-3.0*(1.0-u)*(1.0-u),9.0*u*u-12.0*u,-9.0*u*u+6.0*u+3.0,3.0*u*u)/6.0;
    vec4 ddw=vec4(6.0*(1.0-u),18.0*u-12.0,-18.0*u+6.0,6.0*u)/6.0;
    float dx=dot(dw,xs),ddx=dot(ddw,xs);
    vec4 du=av*dw.x+bv*dw.y+cv*dw.z+dv*dw.w,ddu=av*ddw.x+bv*ddw.y+cv*ddw.z+dv*ddw.w;
    value=av*w.x+bv*w.y+cv*w.z+dv*w.w;
    first=du/dx;second=(ddu*dx-du*ddx)/(dx*dx*dx);
}
vec4 continuationField(int owner,float x) {
    int last=int(paths[owner].meta.x)-1;
    if(continuationAnchored(owner)) {
        float tail=continuationAnchor(owner,true),head=continuationAnchor(owner,false);
        bool before=x<=0.5*(tail+head);
        float origin=before?tail:head,delta=x-origin,sign_=before?-1.0:1.0;
        vec4 f,first,second;
        clothJet(owner,origin,f,first,second);
        int i=continuationAnchorKnot(owner,before);
        float reach=max(abs(continuationControl(owner,i+1).p.x-continuationControl(owner,i).p.x),1e-5);
        vec4 result=f;
        result.xy+=first.xy*sin(delta)+second.xy*(1.0-cos(delta));
        float s=abs(delta),scaled=min(s/reach,80.0),decay=exp(-scaled);
        vec2 g1=first.zw*sign_,g2=second.zw;
        g2.x=g2.x/f.z-pow(g1.x/f.z,2.0);g1.x/=f.z;
        vec2 correction=(g1*reach*scaled+(0.5*g2*reach*reach+g1*reach)*scaled*scaled)*decay;
        result.z=f.z*exp(correction.x);result.w=f.w+correction.y;
        return result;
    }
    bool before=x<=0.5*(continuationControl(owner,0).p.x+continuationControl(owner,last).p.x);
    Knot b=continuationControl(owner,before?0:last-1),c=continuationControl(owner,before?1:last);
    Knot a=continuationControl(owner,before?0:last-2),d=continuationControl(owner,before?2:last);
    vec4 av=continuationValues(a),bv=continuationValues(b),cv=continuationValues(c),dv=continuationValues(d);
    // Geometric guard positions extrapolate; scalar width/twist guards repeat, exactly as station().
    if(before) { a.p.xyz=2.0*b.p.xyz-c.p.xyz;av.xy=a.p.yz; }
    else { d.p.xyz=2.0*c.p.xyz-b.p.xyz;dv.xy=d.p.yz; }
    vec4 f=before?(av+4.0*bv+cv)/6.0:(bv+4.0*cv+dv)/6.0;
    vec4 du=before?(cv-av)*0.5:(dv-bv)*0.5;
    vec4 ddu=before?av-2.0*bv+cv:bv-2.0*cv+dv;
    float dx=before?(c.p.x-a.p.x)*0.5:(d.p.x-b.p.x)*0.5;
    float ddx=before?a.p.x-2.0*b.p.x+c.p.x:b.p.x-2.0*c.p.x+d.p.x;
    vec4 first=du/dx,second=(ddu*dx-du*ddx)/(dx*dx*dx);
    float origin=before?b.p.x:c.p.x,delta=x-origin,sign_=before?-1.0:1.0;
    // Fixed world-unit frequency; phase is inherited from the actual endpoint jets, never from the view.
    float frequency=1.0;
    vec4 result=f;
    result.xy+=first.xy*sin(frequency*delta)/frequency+second.xy*(1.0-cos(frequency*delta))/(frequency*frequency);
    // Positive widths: continue log(width). Twist and width settle smoothly over one control spacing.
    float reach=max(abs(c.p.x-b.p.x),1e-5),s=abs(delta),scaled=min(s/reach,80.0),decay=exp(-scaled);
    vec2 g1=first.zw*sign_,g2=second.zw;
    g2.x=g2.x/f.z-pow(g1.x/f.z,2.0);g1.x/=f.z;
    vec2 correction=(g1*reach*scaled+(0.5*g2*reach*reach+g1*reach)*scaled*scaled)*decay;
    result.z=f.z*exp(correction.x);result.w=f.w+correction.y;
    return result;
}
"""
