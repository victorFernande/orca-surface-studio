"""Compose a monotone spatial phase field and its Z-only native layer grid."""
from __future__ import annotations
import math
import numpy as np


class SurfaceCoordinates:
    def prepare_short_edges(self,moves,pitch):
        """Only inverse endpoints are needed by the short-edge preflight.

        Do not repeat full bead and subdivided-chord preparation in this pass.
        Every retained short chord still receives its complete certificate.
        """
        self._prepared_chords={};self._prepared_cells={}
        self._prepared_chord_context=(self.grid,self.layer_grid)
        points=[self.layer_grid.map_point(p) for m in moves
                if m.deposits and None not in m.start+m.end
                and math.dist(m.start[:2],m.end[:2])<self.settings.min_segment_mm
                for p in (m.start,m.end)]
        self.grid.prepare_points(points,differentials=False)

    def _planar_chord_bound(self,a,b):
        f=self.grid;bounds=getattr(f,'global_hessian',None)
        if bounds is None or a[2]!=b[2]:return math.inf
        dx=b[0]-a[0];dy=b[1]-a[1]
        speed=(f.gmax[0]*abs(dx)+f.gmax[1]*abs(dy))/f.cmin
        return f.quadratic(bounds,(dx,dy,speed))/(8*f.cmin)+2e-8+2e-9/f.cmin

    def can_skip_short_edge_join(self,a,b,minimum,tolerance,retain):
        """Prove a move needs no short-edge joining before solving its endpoints.

        XY is invariant. For a planar native edge, global complete C2 controls
        enclose its implicit physical chord. The final path/bead audit still
        processes the move; this avoids redundant inverse queries in preflight.
        """
        if math.dist(a[:2],b[:2])>=minimum-2e-6:return True
        return retain and math.dist(a,b)<minimum and self._planar_chord_bound(a,b)<=tolerance

    def normal_gaps(self,points,pitches):
        """Batch the same finite-height model used by normal_gap."""
        p=np.asarray(points,dtype=float).copy();bottom=p.copy();bottom[:,2]-=np.asarray(pitches)
        for a in (p,bottom):
            z=a[:,2].copy();grid=self.layer_grid
            a[:,2]=np.where((z<=grid.flat[0])|(z>=grid.flat[-1]),z,np.interp(z,grid.flat,grid.physical))
        top=self.grid.map_points(p);low=self.grid.map_points(bottom)
        dz=1+self.grid.evaluate(top,(0,0,1))
        gx=self.grid.evaluate(top,(1,0,0))/dz;gy=self.grid.evaluate(top,(0,1,0))/dz
        return (top[:,2]-low[:,2])/np.sqrt(1+gx*gx+gy*gy)

    def prepare_layer(self,moves,pitch):
        """Batch numerical queries; missed adaptive queries use scalar fallback."""
        self._prepared_chords={};self._prepared_cells={};self._prepared_chord_context=(self.grid,self.layer_grid)
        if not hasattr(self.grid,'prepare_points'):return
        valid=[m for m in moves if None not in m.start+m.end and m.start!=m.end]
        if not valid:return
        endpoints=[self.layer_grid.map_point(p) for m in valid for p in (m.start,m.end)]
        physical=self.grid.map_points(np.asarray(endpoints));queries=[];chords=[]
        step=self.settings.step_mm
        def lerp(a,b,t):return tuple(x+(y-x)*t for x,y in zip(a,b))
        for index,m in enumerate(valid):
            count=max(1,math.ceil(max(math.dist(m.start,m.end),math.dist(*physical[2*index:2*index+2]))/step-1e-8))
            if count>10000:return
            knots=[lerp(m.start,m.end,j/count) for j in range(count+1)]
            for left,right in zip(knots,knots[1:]):
                if left[2]==right[2]:chords.append((left,right))
                # Both forms occur in the unchanged path/finite-bead code.
                # At floating-point ties they can be distinct exact keys.
                for point in (left,lerp(left,right,.5),tuple((a+b)/2 for a,b in zip(left,right)),right):
                    queries.append(self.layer_grid.map_point(point))
                    if m.deposits:queries.append(self.layer_grid.map_point((point[0],point[1],point[2]-pitch)))
            if len(queries)>200000:return
        self.grid.prepare_points(queries)
        batch=getattr(self.grid,'chord_curvature_bounds_many',None)
        if chords and callable(batch):
            a=np.asarray([self.layer_grid.map_point(left) for left,_ in chords])
            b=np.asarray([self.layer_grid.map_point(right) for _,right in chords])
            pa=np.asarray([self.grid.map_point(p) for p in a]);pb=np.asarray([self.grid.map_point(p) for p in b])
            errors=batch(a,b,pa,pb)
            self._prepared_chords={key:(tuple(p),tuple(q),float(error)) for key,p,q,error in zip(chords,pa,pb,errors)}

    def map_point(self,p):return self.grid.map_point(self.layer_grid.map_point(p))
    def flatten_point(self,p):return self.layer_grid.flatten_point(self.grid.flatten_point(p))
    def local_scale(self,x,y,s):
        p=self.layer_grid.map_point((x,y,s))
        return self.grid.local_scale(*p)*self.layer_grid.local_scale(x,y,s)
    def gradient(self,x,y,s):return self.grid.gradient(*self.layer_grid.map_point((x,y,s)))
    def volume_scale(self,x,y,s,h):return (self.map_point((x,y,s))[2]-self.map_point((x,y,s-h))[2])/h
    def gap_and_scale(self,x,y,s,h):
        key=(x,y,s,h);cache=getattr(self,'_prepared_cells',None)
        context=getattr(self,'_prepared_cell_context',None)
        if cache is None or context is None or context[0] is not self.grid or context[1] is not self.layer_grid:
            self._prepared_cells=cache={};self._prepared_cell_context=(self.grid,self.layer_grid)
        value=cache.get(key)
        if value is None:
            scale=self.volume_scale(x,y,s,h)
            value=(h*scale/math.hypot(1,*self.gradient(x,y,s)),scale)
            # Layer preparation clears this cache. Bound standalone queries too.
            if len(cache)>=100000:cache.clear()
            cache[key]=value
        return value
    def normal_gap(self,x,y,s,h):return self.gap_and_scale(x,y,s,h)[0]
    def surface_heights(self,x,y):return None

    def chord_error_bound(self,a,b,pa,pb):
        context=getattr(self,'_prepared_chord_context',None)
        if context and context[0] is self.grid and context[1] is self.layer_grid:
            prepared=self._prepared_chords.get((tuple(a),tuple(b)))
            if prepared is not None:
                p,q,error=prepared
                return error+max(math.dist(p,pa),math.dist(q,pb))+1e-8
        # A planar slice maps to a constant phase Z. Global derivative controls
        # can prove its full physical chord without searching local supports.
        # Include actual endpoint mismatch (including emitted XYZ rounding).
        # If this conservative bound is too large, keep the exact local path.
        fast=self._planar_chord_bound(a,b)
        tolerance=getattr(getattr(self,'settings',None),'tolerance_mm',0.)
        if fast<=tolerance:
            fast+=max(math.dist(self.map_point(a),pa),math.dist(self.map_point(b),pb))
            if fast<=tolerance:return fast
        if a[2]==b[2]:
            p=self.map_point(a);q=self.map_point(b)
            return float(self.grid.chord_error_bound(self.layer_grid.map_point(a),self.layer_grid.map_point(b),p,q)
                         +max(math.dist(p,pa),math.dist(q,pb))+1e-8)
        a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float);delta=b-a
        cuts=[0.,1.]
        if delta[2]:cuts.extend((z-a[2])/delta[2] for z in self.layer_grid.flat if 0<(z-a[2])/delta[2]<1)
        cuts=sorted(set(cuts));bound=0.
        for left,right in zip(cuts,cuts[1:]):
            u=a if left==0 else a+left*delta
            v=b if right==1 else a+right*delta
            p=self.map_point(u);q=self.map_point(v)
            error=self.grid.chord_error_bound(self.layer_grid.map_point(u),self.layer_grid.map_point(v),p,q)
            endpoint=max(math.dist(p,np.asarray(pa)+left*(np.asarray(pb)-pa)),
                         math.dist(q,np.asarray(pa)+right*(np.asarray(pb)-pa)))
            bound=max(bound,error+endpoint)
        return float(bound+1e-8)
