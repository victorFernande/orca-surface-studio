"""Compose a monotone spatial phase field and its Z-only native layer grid."""
from __future__ import annotations
import math
import numpy as np


class SurfaceCoordinates:
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
        if not hasattr(self.grid,'prepare_points'):return
        valid=[m for m in moves if m.deposits and None not in m.start+m.end and m.start!=m.end]
        if not valid:return
        endpoints=[self.layer_grid.map_point(p) for m in valid for p in (m.start,m.end)]
        physical=self.grid.map_points(np.asarray(endpoints));queries=[]
        step=self.settings.step_mm
        def lerp(a,b,t):return tuple(x+(y-x)*t for x,y in zip(a,b))
        for index,m in enumerate(valid):
            count=max(1,math.ceil(max(math.dist(m.start,m.end),math.dist(*physical[2*index:2*index+2]))/step-1e-8))
            if count>10000:return
            knots=[lerp(m.start,m.end,j/count) for j in range(count+1)]
            for left,right in zip(knots,knots[1:]):
                for point in (left,lerp(left,right,.5),right):
                    queries.extend((self.layer_grid.map_point(point),
                                    self.layer_grid.map_point((point[0],point[1],point[2]-pitch))))
            if len(queries)>200000:return
        self.grid.prepare_points(queries)

    def map_point(self,p):return self.grid.map_point(self.layer_grid.map_point(p))
    def flatten_point(self,p):return self.layer_grid.flatten_point(self.grid.flatten_point(p))
    def local_scale(self,x,y,s):
        p=self.layer_grid.map_point((x,y,s))
        return self.grid.local_scale(*p)*self.layer_grid.local_scale(x,y,s)
    def gradient(self,x,y,s):return self.grid.gradient(*self.layer_grid.map_point((x,y,s)))
    def volume_scale(self,x,y,s,h):return (self.map_point((x,y,s))[2]-self.map_point((x,y,s-h))[2])/h
    def normal_gap(self,x,y,s,h):return h*self.volume_scale(x,y,s,h)/math.hypot(1,*self.gradient(x,y,s))
    def surface_heights(self,x,y):return None

    def chord_error_bound(self,a,b,pa,pb):
        a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float);delta=b-a
        cuts=[0.,1.]
        if delta[2]:cuts.extend((z-a[2])/delta[2] for z in self.layer_grid.flat if 0<(z-a[2])/delta[2]<1)
        cuts=sorted(set(cuts));bound=0.
        for left,right in zip(cuts,cuts[1:]):
            u=a+left*delta;v=a+right*delta;p=self.map_point(u);q=self.map_point(v)
            error=self.grid.chord_error_bound(self.layer_grid.map_point(u),self.layer_grid.map_point(v),p,q)
            endpoint=max(math.dist(p,np.asarray(pa)+left*(np.asarray(pb)-pa)),
                         math.dist(q,np.asarray(pa)+right*(np.asarray(pb)-pa)))
            bound=max(bound,error+endpoint)
        return float(bound+1e-8)
