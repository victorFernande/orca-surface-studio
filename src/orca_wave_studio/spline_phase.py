"""C2 monotone phase field with derivative-control certificates."""
from __future__ import annotations
import math
from bisect import bisect_right
from functools import lru_cache
import numpy as np
from scipy.interpolate import NdBSpline,BSpline
from .contracts import WaveError

_INVERSE_TOLERANCE=1e-9
_INVERSE_NEWTON_STEPS=8


class SplinePhase:
    def __init__(self,axes,displacement,anchor=.5):
        self.axes=tuple(np.asarray(a,dtype=float) for a in axes)
        self.coefficients=np.asarray(displacement,dtype=float)
        self.shape=tuple(len(a) for a in self.axes);self.anchor=float(anchor)
        if self.coefficients.shape!=self.shape or not np.isfinite(self.coefficients).all():raise WaveError('SPLINE_GRID: coeficientes inválidos.')
        self.steps=tuple(float(a[1]-a[0]) for a in self.axes)
        if any(len(a)<7 or h<=0 or np.max(abs(np.diff(a)-h))>1e-8 for a,h in zip(self.axes,self.steps)):
            raise WaveError('SPLINE_GRID: use eixos uniformes com margem cúbica.')
        self.knots=tuple(a[0]+(np.arange(len(a)+4)-2)*h for a,h in zip(self.axes,self.steps))
        self.domain=tuple((float(t[3]),float(t[-4])) for t in self.knots)
        # Three zero control rows give a C2 zero extension at the base domain.
        for k in range(3):
            for start in (slice(0,3),slice(-3,None)):
                selector=[slice(None)]*3;selector[k]=start
                if np.max(abs(self.coefficients[tuple(selector)]))>1e-9:raise WaveError('SPLINE_BOUNDARY: falta a margem de deslocamento zero.')
        active_below_anchor=self.knots[2][:self.shape[2]]<anchor-1e-9
        if np.max(abs(self.coefficients[:,:,active_below_anchor]),initial=0.)>1e-9:
            raise WaveError('SPLINE_BASE: a primeira camada não ficaria plana.')
        self.spline=NdBSpline(self.knots,self.coefficients,3,extrapolate=False)
        certificate_knots=list(self.knots);certificate_coeff=self.coefficients.copy()
        for _ in range(2):
            for k in range(3):
                spline=BSpline(certificate_knots[k],np.moveaxis(certificate_coeff,k,0),3,extrapolate=False)
                knots=spline.t;interior=np.unique(knots[(knots>=knots[3])&(knots<=knots[-4])])
                for value in (interior[:-1]+interior[1:])/2:spline=spline.insert_knot(float(value))
                certificate_knots[k]=spline.t;certificate_coeff=np.moveaxis(spline.c,0,k)
        def derivative(nu):
            values=certificate_coeff;knots=list(certificate_knots);degrees=[3,3,3]
            for k,count in enumerate(nu):
                for _ in range(count):
                    degree=degrees[k];t=knots[k];n=values.shape[k]
                    factor=degree/(t[degree+1:degree+n]-t[1:n])
                    shape=[1]*3;shape[k]=len(factor)
                    values=np.diff(values,axis=k)*factor.reshape(shape);knots[k]=t[1:-1];degrees[k]-=1
            return values,knots,degrees
        self.first=[];self.first_domains=[]
        for k in range(3):
            nu=[0,0,0];nu[k]=1
            values,knots,degrees=derivative(nu);self.first.append(values);self.first_domains.append((knots,degrees))
        self.hessian={}
        self.hessian_domains={}
        for i in range(3):
            for j in range(i,3):
                nu=[0,0,0];nu[i]+=1;nu[j]+=1
                values,knots,degrees=derivative(nu);self.hessian[i,j]=values;self.hessian_domains[i,j]=(knots,degrees)
        self.cmin=1+float(self.first[2].min());self.cmax=1+float(self.first[2].max())
        self.gmax=tuple(float(abs(a).max()) for a in self.first[:2])
        self.global_hessian={key:float(abs(values).max()) for key,values in self.hessian.items()}
        if self.cmin<=0:raise WaveError('SPLINE_FOLD: os controles não preservam a ordem vertical.')
        # Newton can oscillate while technically staying inside the bracket.
        # Keep its fast initial steps, then guarantee bracket contraction by
        # bisection. The certified derivative upper bound translates bracket
        # width into the original phase residual; no tolerance is relaxed.
        residual_bound=(self.domain[2][1]-self.domain[2][0])*self.cmax
        self._inverse_iterations=_INVERSE_NEWTON_STEPS+math.ceil(math.log2(
            max(1.,residual_bound/_INVERSE_TOLERANCE)))+2
        self.bounds={'minimum_phase_z_derivative':self.cmin,'maximum_phase_z_derivative':self.cmax,
            'maximum_phase_xy_derivative':self.gmax,'maximum_slope':math.hypot(*self.gmax)/self.cmin,
            'certificate':'nonnegative B-spline derivative basis and complete coefficient differences'}
        # Bounds depend on the active knot supports, not the exact coordinates
        # inside a support cell. Use searchsorted's exact closed-box convention;
        # no rounding, looser tolerance or sampled certificate is introduced.
        domains=[*self.first_domains,*self.hessian_domains.values()]
        self._support_knots=tuple(np.unique(np.concatenate([knots[k] for knots,_ in domains])) for k in range(3))
        self._support_lists=tuple(knots.tolist() for knots in self._support_knots)
        self._support_coordinates=tuple(np.r_[-np.inf,knots] for knots in self._support_knots)
        self._first_tables=self._bounds_tables(self.first_domains,self.first)
        self._hessian_tables=self._bounds_tables(list(self.hessian_domains.values()),list(self.hessian.values()))
        self._hessian_query=lru_cache(maxsize=32768)(self._hessian_for_cells)
        self._derivative_query=lru_cache(maxsize=32768)(self._derivative_for_cells)
        self._map=lru_cache(maxsize=120000)(self._map_point)
        self._differential=lru_cache(maxsize=120000)(self._at_differential)
        self._prepared_points={};self._prepared_differentials={}

    def evaluate(self,points,nu=None):
        points=np.asarray(points,dtype=float);inside=np.ones(points.shape[:-1],dtype=bool)
        for k,(lo,hi) in enumerate(self.domain):inside &= (points[...,k]>=lo)&(points[...,k]<=hi)
        output=np.zeros(points.shape[:-1]);output[inside]=self.spline(points[inside],nu=nu)
        return output

    def flatten_points(self,points):
        p=np.asarray(points,dtype=float);q=p.copy();q[...,2]+=self.evaluate(p);return q
    def flatten_point(self,p):return tuple(map(float,self.flatten_points(np.asarray([p]))[0]))
    def map_point(self,p):
        key=tuple(map(float,p));prepared=self._prepared_points.get(key)
        return prepared if prepared is not None else self._map(key)

    def prepare_points(self,points,*,differentials=True):
        self._prepared_points={};self._prepared_differentials={}
        keys=list(dict.fromkeys(tuple(map(float,p)) for p in points))
        if not keys or len(keys)>100000:return
        physical=self.map_points(np.asarray(keys))
        self._prepared_points={key:tuple(map(float,p)) for key,p in zip(keys,physical)}
        if not differentials:return
        gx=self.evaluate(physical,(1,0,0));gy=self.evaluate(physical,(0,1,0));gz=1+self.evaluate(physical,(0,0,1))
        self._prepared_differentials={key:(float(1/c),(float(-a/c),float(-b/c)))
            for key,a,b,c in zip(keys,gx,gy,gz)}

    def map_points(self,points):
        """Vectorized safeguarded inverse with the same scalar tolerance."""
        source=np.asarray(points,dtype=float);result=source.copy()
        eligible=(source[:,2]>self.anchor)
        for k,(low,high) in enumerate(self.domain):
            eligible &= (source[:,k]>low)&(source[:,k]<high)
        indices=np.flatnonzero(eligible)
        if not len(indices):return result
        p=source[indices].copy();target=p[:,2].copy()
        lo=np.full(len(p),self.domain[2][0]);hi=np.full(len(p),self.domain[2][1])
        active=np.ones(len(p),dtype=bool)
        for iteration in range(self._inverse_iterations):
            chosen=np.flatnonzero(active)
            if not len(chosen):break
            q=p[chosen];error=q[:,2]+self.evaluate(q)-target[chosen]
            converged=abs(error)<_INVERSE_TOLERANCE;active[chosen[converged]]=False
            chosen=chosen[~converged];error=error[~converged]
            if not len(chosen):continue
            q=p[chosen];lo[chosen]=np.where(error<0,q[:,2],lo[chosen]);hi[chosen]=np.where(error>0,q[:,2],hi[chosen])
            if iteration>=_INVERSE_NEWTON_STEPS:
                p[chosen,2]=(lo[chosen]+hi[chosen])/2
                continue
            derivative=1+self.evaluate(q,(0,0,1));trial=q[:,2]-error/derivative
            p[chosen,2]=np.where((trial>lo[chosen])&(trial<hi[chosen]),trial,(lo[chosen]+hi[chosen])/2)
        if active.any():raise WaveError('SPLINE_INVERSE: a inversão em lote não atingiu a tolerância.')
        result[indices]=p;return result

    def _map_point(self,p):
        x,y,s=p
        if s<=self.anchor or any(q<lo or q>hi for q,(lo,hi) in zip((x,y),self.domain[:2])):return p
        lo,hi=self.domain[2]
        if s<=lo or s>=hi:return p
        z=min(hi,max(lo,s))
        for iteration in range(self._inverse_iterations):
            q=np.array([[x,y,z]]);error=z+float(self.evaluate(q)[0])-s
            if abs(error)<_INVERSE_TOLERANCE:return x,y,z
            if error<0:lo=z
            else:hi=z
            if iteration>=_INVERSE_NEWTON_STEPS:
                z=(lo+hi)/2
                continue
            j=1+float(self.evaluate(q,(0,0,1))[0]);trial=z-error/j
            z=trial if lo<trial<hi else (lo+hi)/2
        raise WaveError('SPLINE_INVERSE: a inversão não atingiu a tolerância.')

    def _at_differential(self,p):
        physical=self.map_point(p);q=np.array([physical])
        gx=float(self.evaluate(q,(1,0,0))[0]);gy=float(self.evaluate(q,(0,1,0))[0]);gz=1+float(self.evaluate(q,(0,0,1))[0])
        return 1/gz,(-gx/gz,-gy/gz)
    def _get_differential(self,p):
        key=tuple(map(float,p));prepared=self._prepared_differentials.get(key)
        return prepared if prepared is not None else self._differential(key)
    def local_scale(self,x,y,s):return self._get_differential((x,y,s))[0]
    def gradient(self,x,y,s):return self._get_differential((x,y,s))[1]
    def volume_scale(self,x,y,s,h):return (self.map_point((x,y,s))[2]-self.map_point((x,y,s-h))[2])/h
    def normal_gap(self,x,y,s,h):return h*self.volume_scale(x,y,s,h)/math.hypot(1,*self.gradient(x,y,s))
    def surface_heights(self,x,y):return None

    def hessian_bounds(self,points):
        return dict(self._hessian_query(self._support_key(points)))

    def _support_keys_many(self,points):
        p=np.asarray(points,dtype=float)
        lo=p.min(axis=1);hi=p.max(axis=1)
        keys=np.empty((len(p),6),dtype=np.int64)
        for k,knots in enumerate(self._support_knots):
            keys[:,2*k]=np.searchsorted(knots,lo[:,k],side='right')
            keys[:,2*k+1]=np.searchsorted(knots,hi[:,k],side='right')
        return keys

    def hessian_bounds_many(self,points):
        """The same closed support boxes as scalar queries, grouped without rounding."""
        keys=self._support_keys_many(points)
        if not len(keys):return {key:np.empty(0) for key in self.hessian}
        unique,inverse=np.unique(keys,axis=0,return_inverse=True)
        values=self._control_bounds_many(unique,list(self.hessian.values()),self._hessian_tables,absolute=True)[:,:,1]
        return {key:values[inverse,i] for i,key in enumerate(self.hessian)}

    def derivative_bounds_many(self,points):
        keys=self._support_keys_many(points)
        if not len(keys):return np.empty(0),np.empty(0),np.empty((0,2))
        unique,inverse=np.unique(keys,axis=0,return_inverse=True)
        values=self._control_bounds_many(unique,self.first,self._first_tables,absolute=False)[inverse]
        return 1+values[:,2,0],1+values[:,2,1],np.maximum(abs(values[:,:2,0]),abs(values[:,:2,1]))

    def _bounds_tables(self,domains,arrays):
        result=[]
        for (knots,degrees),array in zip(domains,arrays):
            left=[];right=[]
            for k,(t,degree) in enumerate(zip(knots,degrees)):
                indices=np.searchsorted(t,self._support_coordinates[k],side='right')
                left.append(np.maximum(0,indices-degree-1));right.append(np.minimum(array.shape[k],indices))
            result.append((left,right))
        return result

    def _control_bounds_many(self,keys,arrays,tables,*,absolute):
        """Reduce exact coefficient slices in bounded batches, never sampled bounds."""
        result=np.zeros((len(keys),len(arrays),2))
        for j,(array,(left_table,right_table)) in enumerate(zip(arrays,tables)):
            left=np.stack([left_table[k][keys[:,2*k]] for k in range(3)],axis=1)
            right=np.stack([right_table[k][keys[:,2*k+1]] for k in range(3)],axis=1)
            widths=right-left;shapes,groups=np.unique(widths,axis=0,return_inverse=True)
            for group,shape in enumerate(shapes):
                if np.any(shape<=0):continue
                ids=np.flatnonzero(groups==group);size=int(np.prod(shape))
                if size>4096:
                    for index in ids:
                        region=array[tuple(slice(a,b) for a,b in zip(left[index],right[index]))]
                        result[index,j,1]=float(abs(region).max()) if absolute else max(0.,float(region.max()))
                        if not absolute:result[index,j,0]=min(0.,float(region.min()))
                    continue
                offsets=np.indices(tuple(shape)).reshape(3,-1)
                chunk=max(1,262144//size)
                for start in range(0,len(ids),chunk):
                    batch=ids[start:start+chunk];origin=left[batch]
                    block=array[origin[:,0,None]+offsets[0],origin[:,1,None]+offsets[1],origin[:,2,None]+offsets[2]]
                    result[batch,j,1]=abs(block).max(axis=1) if absolute else np.maximum(0.,block.max(axis=1))
                    if not absolute:result[batch,j,0]=np.minimum(0.,block.min(axis=1))
        return result

    def inverse_phase_errors(self,points,errors):
        p=np.asarray(points,dtype=float);errors=np.asarray(errors,dtype=float)
        if not len(p):return np.empty(0)
        lo=p.min(axis=1);hi=p.max(axis=1)
        lo[:,2]-=errors/self.cmin;hi[:,2]+=errors/self.cmin
        minimum,_,_=self.derivative_bounds_many(np.stack((lo,hi),axis=1))
        return errors/minimum

    def phase_triangle_errors(self,points):
        p=np.asarray(points,dtype=float);result=np.zeros(len(p))
        if not len(p):return result
        active=p[:,:,2].max(axis=1)>self.anchor
        q=p[active]
        if not len(q):return result
        h=self.hessian_bounds_many(q);d=np.roll(q,-1,axis=1)-q
        curve=sum(h[i,j][:,None]*abs(d[:,:,i]*d[:,:,j])*(1 if i==j else 2) for i,j in h)
        result[active]=curve.max(axis=1)/6+1e-9
        return result

    def phase_edge_errors(self,points):
        p=np.asarray(points,dtype=float);result=np.zeros(len(p))
        if not len(p):return result
        active=p[:,:,2].max(axis=1)>self.anchor;q=p[active]
        if not len(q):return result
        h=self.hessian_bounds_many(q);d=q[:,1]-q[:,0]
        result[active]=sum(h[i,j]*abs(d[:,i]*d[:,j])*(1 if i==j else 2) for i,j in h)/8+1e-9
        return result

    def chord_curvature_bounds_many(self,a,b,pa,pb):
        """Complete implicit-chord curvature; verified endpoint errors are separate."""
        a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
        pa=np.asarray(pa,dtype=float);pb=np.asarray(pb,dtype=float)
        result=np.full(len(a),1e-9)
        active=np.maximum(pa[:,2],pb[:,2])>self.anchor
        if not active.any():return result
        d=b[active]-a[active];p=pa[active];q=pb[active]
        speed=(abs(d[:,2])+(self.gmax[0]*abs(d[:,0])+self.gmax[1]*abs(d[:,1])))/self.cmin
        lo=np.minimum(p,q);hi=np.maximum(p,q);lo[:,2]-=speed/2;hi[:,2]+=speed/2
        minimum,_,gradient=self.derivative_bounds_many(np.stack((lo,hi),axis=1))
        speed=(abs(d[:,2])+(gradient[:,0]*abs(d[:,0])+gradient[:,1]*abs(d[:,1])))/minimum
        lo=np.minimum(p,q);hi=np.maximum(p,q);lo[:,2]-=speed/2;hi[:,2]+=speed/2
        h=self.hessian_bounds_many(np.stack((lo,hi),axis=1));direction=np.column_stack((d[:,:2],speed))
        result[active]=sum(h[i,j]*abs(direction[:,i]*direction[:,j])*(1 if i==j else 2) for i,j in h)/(8*minimum)+1e-8
        return result

    def _support_key(self,points):
        if len(points)==2:
            a,b=points
            return tuple(index for k,knots in enumerate(self._support_lists)
                         for index in (bisect_right(knots,min(a[k],b[k])),bisect_right(knots,max(a[k],b[k]))))
        p=np.asarray(points);lo=p.min(axis=0);hi=p.max(axis=0)
        return tuple(int(i) for k,knots in enumerate(self._support_knots)
                     for i in np.searchsorted(knots,[lo[k],hi[k]],side='right'))

    def _support_points(self,key):
        return np.array([[self._support_coordinates[k][key[2*k+j]] for k in range(3)] for j in range(2)])

    def _hessian_for_cells(self,key):
        result={}
        # A degree-p basis i is nonzero only on [t_i,t_(i+p+1)].
        # Include the complete active support over the closed query box.
        for ((i,j),values),(left,right) in zip(self.hessian.items(),self._hessian_tables):
            selector=[slice(left[k][key[2*k]],right[k][key[2*k+1]]) for k in range(3)]
            region=values[tuple(selector)];result[i,j]=float(abs(region).max()) if region.size else 0.
        return tuple(result.items())

    def derivative_bounds(self,points):
        return self._derivative_query(self._support_key(points))

    def _derivative_for_cells(self,key):
        ranges=[]
        for values,(left,right) in zip(self.first,self._first_tables):
            selector=[slice(left[k][key[2*k]],right[k][key[2*k+1]]) for k in range(3)]
            region=values[tuple(selector)]
            ranges.append((min(0.,float(region.min())),max(0.,float(region.max()))) if region.size else (0.,0.))
        return 1+ranges[2][0],1+ranges[2][1],tuple(max(abs(a),abs(b)) for a,b in ranges[:2])

    def inverse_phase_error(self,points,error):
        p=np.asarray(points);lo=p.min(axis=0);hi=p.max(axis=0)
        lo[2]-=error/self.cmin;hi[2]+=error/self.cmin
        minimum,_,_=self.derivative_bounds((lo,hi));return error/minimum

    @staticmethod
    def quadratic(bounds,d):
        return sum(bounds[i,j]*abs(d[i]*d[j])*(1 if i==j else 2) for i,j in bounds)

    def phase_triangle_error(self,points):
        points=np.asarray(points)
        if points[:,2].max()<=self.anchor:return 0.
        h=self.hessian_bounds(points)
        return max(self.quadratic(h,b-a) for a,b in zip(points,np.roll(points,-1,axis=0)))/6+1e-9

    def phase_edge_error(self,a,b):
        if max(a[2],b[2])<=self.anchor:return 0.
        return self.quadratic(self.hessian_bounds((a,b)),np.asarray(b)-a)/8+1e-9

    def chord_error_bound(self,a,b,pa,pb):
        a=np.asarray(a);b=np.asarray(b);d=b-a
        endpoint=max(math.dist(self.map_point(a),pa),math.dist(self.map_point(b),pb))
        if max(pa[2],pb[2])<=self.anchor:return endpoint+1e-9
        speed=(abs(d[2])+sum(g*abs(v) for g,v in zip(self.gmax,d[:2])))/self.cmin
        lo=np.minimum(pa,pb).copy();hi=np.maximum(pa,pb).copy();lo[2]-=speed/2;hi[2]+=speed/2
        minimum,_,gradient=self.derivative_bounds((lo,hi))
        speed=(abs(d[2])+sum(g*abs(v) for g,v in zip(gradient,d[:2])))/minimum
        lo=np.minimum(pa,pb).copy();hi=np.maximum(pa,pb).copy();lo[2]-=speed/2;hi[2]+=speed/2
        bounds=self.hessian_bounds((lo,hi));direction=(d[0],d[1],speed)
        return float(self.quadratic(bounds,direction)/(8*minimum)+endpoint+1e-8)
