"""C2 monotone phase field with derivative-control certificates."""
from __future__ import annotations
import math
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
        self._support_coordinates=tuple(np.r_[-np.inf,knots] for knots in self._support_knots)
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

    def prepare_points(self,points):
        self._prepared_points={};self._prepared_differentials={}
        keys=list(dict.fromkeys(tuple(map(float,p)) for p in points))
        if not keys or len(keys)>100000:return
        physical=self.map_points(np.asarray(keys))
        gx=self.evaluate(physical,(1,0,0));gy=self.evaluate(physical,(0,1,0));gz=1+self.evaluate(physical,(0,0,1))
        self._prepared_points={key:tuple(map(float,p)) for key,p in zip(keys,physical)}
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

    def _support_key(self,points):
        p=np.asarray(points);lo=p.min(axis=0);hi=p.max(axis=0)
        return tuple(int(i) for k,knots in enumerate(self._support_knots)
                     for i in np.searchsorted(knots,[lo[k],hi[k]],side='right'))

    def _support_points(self,key):
        return np.array([[self._support_coordinates[k][key[2*k+j]] for k in range(3)] for j in range(2)])

    def _hessian_for_cells(self,key):
        points=self._support_points(key)
        p=np.asarray(points);lo=p.min(axis=0);hi=p.max(axis=0);result={}
        # A degree-p basis i is nonzero only on [t_i,t_(i+p+1)].
        # Include the complete active support over the closed query box.
        for (i,j),values in self.hessian.items():
            selector=[]
            knots,degrees=self.hessian_domains[i,j]
            for k,(t,degree) in enumerate(zip(knots,degrees)):
                left=max(0,int(np.searchsorted(t,lo[k],side='right'))-degree-1)
                right=min(values.shape[k],int(np.searchsorted(t,hi[k],side='right')))
                selector.append(slice(left,right))
            region=values[tuple(selector)];result[i,j]=float(abs(region).max()) if region.size else 0.
        return tuple(result.items())

    def derivative_bounds(self,points):
        return self._derivative_query(self._support_key(points))

    def _derivative_for_cells(self,key):
        points=self._support_points(key)
        p=np.asarray(points);lo=p.min(axis=0);hi=p.max(axis=0);ranges=[]
        for values,(knots,degrees) in zip(self.first,self.first_domains):
            selector=[]
            for k,(t,degree) in enumerate(zip(knots,degrees)):
                left=max(0,int(np.searchsorted(t,lo[k],side='right'))-degree-1)
                right=min(values.shape[k],int(np.searchsorted(t,hi[k],side='right')))
                selector.append(slice(left,right))
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
