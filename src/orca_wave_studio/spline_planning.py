"""Propose one smooth phase field for all detected surface references.

This optimizer is a proposal, not a print qualification. The paired slicing
copy, actual emitted bead heights and actual motion slopes have independent
guards in the native-slicing workflow.
"""
from __future__ import annotations

from dataclasses import replace
import math
import time
from pathlib import Path
import json
import hashlib

import numpy as np
from scipy import sparse
from scipy.interpolate import NdBSpline
import osqp

from .contracts import WaveError
from .phase_planning import _references,assess_phase_field
from .printer_profile import number
from .spline_phase import SplinePhase
from .spline_layers import SplineLayerWarp
from .material_sampling import material_samples


def phase_cache_key(mesh,profile,minimum,maximum,slope,step_mm=.4,max_curve_height_mm=None):
    """Identity of geometry and geometric constraints; never a print receipt."""
    hasher=hashlib.sha256()
    points=np.asarray([p for face in mesh.faces for p in face.points],dtype='<f8')
    hasher.update(points.tobytes())
    hasher.update(json.dumps({'kernel':'cubic_spline_phase_v1','planner_revision':5,
        'layer':profile.layer_mm,'initial':profile.initial_layer_mm,
        'minimum':minimum,'maximum':maximum,'slope':slope,'reference_extension':4*step_mm,
        'max_curve_height_mm':max_curve_height_mm},sort_keys=True).encode())
    return hasher.hexdigest()


def _csc32(matrix):
    matrix=sparse.csc_matrix(matrix)
    matrix.indices=matrix.indices.astype(np.int32)
    matrix.indptr=matrix.indptr.astype(np.int32)
    return matrix


def _design(points,knots,degrees,columns):
    matrix=NdBSpline.design_matrix(points,tuple(knots),degrees,extrapolate=False)
    # SciPy may omit trailing all-zero coefficient columns.
    matrix.resize((len(points),columns))
    return matrix


def _solve(axes,regions,physical,profile,minimum,maximum,slope,anchor,
           *,progress,cancelled,previous=None,time_limit=100.,max_curve_height_mm=None):
    shape=tuple(len(a) for a in axes);n=math.prod(shape)
    limited=max_curve_height_mm is not None;variables=n+len(regions)+int(limited)
    step=float(axes[0][1]-axes[0][0]);ids=np.arange(n).reshape(shape)
    knots=tuple(a[0]+(np.arange(len(a)+4)-2)*step for a in axes)
    differences=[]
    for k in range(3):
        left=[slice(None)]*3;right=left.copy();left[k]=slice(None,-1);right[k]=slice(1,None)
        a=ids[tuple(left)].ravel();b=ids[tuple(right)].ravel();count=len(a);r=np.arange(count)
        differences.append(sparse.coo_matrix((np.r_[-np.ones(count)/step,np.ones(count)/step],
            (np.r_[r,r],np.r_[a,b])),shape=(count,variables)).tocsc())
    constraints=[];lower=[];upper=[]
    if limited:
        # The extra variable is the lower bound of a shared coefficient range.
        # A nonnegative partition-of-unity B-spline stays inside that range.
        # For a fixed flattened Z, physical Z = flattened Z - displacement:
        # its peak-to-valley curve height is bounded by the same range.
        rows=np.arange(n)
        constraints.append(sparse.coo_matrix((np.r_[np.ones(n),-np.ones(n)],
            (np.r_[rows,rows],np.r_[rows,np.full(n,variables-1)])),shape=(n,variables)).tocsc())
        lower.append(np.zeros(n));upper.append(np.full(n,max_curve_height_mm-1e-4))
        constraints.append(sparse.coo_matrix(([1.],([0],[variables-1])),shape=(1,variables)).tocsc())
        lower.append(np.array([-max_curve_height_mm+1e-4]));upper.append(np.array([0.]))
    # Wide coefficient bounds preserve a positive global Jacobian. Local
    # material and motion constraints are refined below and checked after slice.
    positive=max(.2,profile.layer_mm/maximum*.56)
    peak=max(1.05,min(3.,profile.layer_mm/minimum*.875))
    xy=max(.5,1.56*math.tan(math.radians(slope)))
    for k,matrix in enumerate(differences):
        constraints.append(matrix)
        lower.append(np.full(matrix.shape[0],positive-1 if k==2 else -xy))
        upper.append(np.full(matrix.shape[0],peak-1 if k==2 else xy))
    fixed=np.zeros(shape,dtype=bool)
    for k in range(3):
        for where in (slice(0,3),slice(-3,None)):
            index=[slice(None)]*3;index[k]=where;fixed[tuple(index)]=True
    fixed[:,:,axes[2]<=anchor+step+1e-8]=True
    boundary=np.flatnonzero(fixed.ravel())
    constraints.append(sparse.coo_matrix((np.ones(len(boundary)),
        (np.arange(len(boundary)),boundary)),shape=(len(boundary),variables)).tocsc())
    lower.append(np.zeros(len(boundary)));upper.append(np.zeros(len(boundary)))
    for i,region in enumerate(regions):
        points=region['fitted'];basis=_design(points,knots,3,n)
        constant=sparse.coo_matrix((-np.ones(len(points)),
            (np.arange(len(points)),np.full(len(points),i))),shape=(len(points),variables-n))
        constraints.append(sparse.hstack((basis,constant),format='csc'))
        lower.append(-points[:,2]-.025);upper.append(-points[:,2]+.025)
    critical_count=0;initial=None
    if previous is not None:
        gradient=np.stack([previous.evaluate(physical,tuple(int(j==k) for j in range(3)))
                           for k in range(3)],axis=-1);gradient[:,2]+=1
        # Keep room for source-copy interpolation and emitted chords.
        trigger=max(0.,slope-2.);safe=max(0.,slope-.5)
        low_z=max(.95,min(1.,profile.layer_mm/(maximum*.84)))
        bad=(gradient[:,2]<low_z+.01)|(gradient[:,2]>2.)|(np.hypot(gradient[:,0],gradient[:,1])/gradient[:,2]>math.tan(math.radians(trigger)))
        points=physical[bad];g=gradient[bad]
        if len(points):
            _,chosen=np.unique(np.floor(points/.4),axis=0,return_index=True)
            points=points[chosen];g=g[chosen];critical_count=len(points)
            jacobian=[]
            for k in range(3):
                derivative_knots=list(knots);derivative_knots[k]=derivative_knots[k][1:-1]
                degrees=[3]*3;degrees[k]=2
                basis=_design(points,derivative_knots,tuple(degrees),differences[k].shape[0])
                jacobian.append(basis@differences[k])
            constraints.append(jacobian[2]);lower.append(np.full(len(points),low_z-1));upper.append(np.full(len(points),1.))
            norm=np.hypot(g[:,0],g[:,1]);nx=np.divide(g[:,0],norm,out=np.zeros_like(norm),where=norm>1e-10)
            ny=np.divide(g[:,1],norm,out=np.zeros_like(norm),where=norm>1e-10)
            tangent=math.tan(math.radians(safe))
            constraints.append(sparse.diags(nx)@jacobian[0]+sparse.diags(ny)@jacobian[1]-tangent*jacobian[2])
            lower.append(np.full(len(points),-np.inf));upper.append(np.full(len(points),tangent))
        initial=np.r_[previous.coefficients.ravel(),[previous.flatten_points(r['fitted'])[:,2].mean() for r in regions],
                      [float(previous.coefficients.min())] if limited else []]
    matrix=_csc32(sparse.vstack(constraints,format='csc'))
    baseline=np.r_[np.zeros(n),[sum(r['original_z_range'])/2 for r in regions],[0.] if limited else []]
    objective=sparse.diags(np.r_[np.full(n,.05),np.full(len(regions),.1),[.0001] if limited else []],format='csc')
    for difference in differences:objective+=10*difference.T@difference
    solver=osqp.OSQP();solver.setup(P=_csc32(sparse.triu(objective,format='csc')),q=-objective@baseline,
        A=matrix,l=np.concatenate(lower),u=np.concatenate(upper),verbose=False,
        eps_abs=1e-5,eps_rel=1e-7,max_iter=300,time_limit=3.,rho=1.,adaptive_rho=True,
        adaptive_rho_interval=100,adaptive_rho_tolerance=2.,polishing=False)
    if initial is not None:solver.warm_start(x=initial)
    started=time.monotonic();result=None
    while time.monotonic()-started<time_limit:
        if cancelled():raise WaveError('Geração cancelada.')
        result=solver.solve(raise_error=False)
        elapsed=time.monotonic()-started
        progress(f'Distribuindo as camadas e suavizando transições: {elapsed:.0f} s…')
        if result.info.status in ('solved','primal infeasible','dual infeasible'):break
    if result is None or result.x is None or not np.isfinite(result.x).all() or np.max(abs(result.x))>1000:
        if max_curve_height_mm is not None:
            raise WaveError('CURVE_HEIGHT: não foi possível conciliar o limite da curva com as superfícies e transições. '
                            'Ajuste a altura no passo 1 ou escolha outra região; o original foi preservado.')
        raise WaveError('SPLINE_PLAN: não foi possível propor camadas contínuas para esta peça.')
    coefficients=result.x[:n].reshape(shape).copy();coefficients[fixed]=0.
    field=SplinePhase(axes,coefficients,anchor)
    curve_height_certificate(field,max_curve_height_mm)
    return field,{'optimizer_status':result.info.status,'optimizer_primal_residual':float(result.info.prim_res),
        'critical_source_points':critical_count,'independent_emitted_checks_required':True,
        'physical_validation':False,'print_allowed':False}


def curve_height_certificate(field,limit):
    """Complete coefficient hull, including the zero extension; not head clearance."""
    lo=float(field.coefficients.min(initial=0.));hi=float(field.coefficients.max(initial=0.))
    bound=hi-lo
    if limit is not None and bound>limit+1e-7:
        raise WaveError('CURVE_HEIGHT: as superfícies não couberam no limite da curva. '
                        'Aumente o limite em mm ou escolha outra região; o original foi preservado.')
    return {'limit_mm':limit,'certified_peak_to_valley_upper_bound_mm':bound,
            'scope':'one constant surface-coordinate layer; full B-spline coefficient hull',
            'head_clearance_verified':False}


def prepare_spline_warp(snapshot,object_id,settings,profile,resolved,*,progress=lambda message:None,cancelled=lambda:False,cache_folder=None):
    if cancelled():raise WaveError('Geração cancelada.')
    progress('Reconhecendo o interior das superfícies e suas bordas…')
    mesh,regions=_references(snapshot,object_id,settings.max_slope_deg,4*settings.step_mm,cancelled=cancelled)
    if settings.max_curve_height_mm is not None and any(
            float(np.ptp(r['fitted'][:,2]))>settings.max_curve_height_mm+.05 for r in regions):
        raise WaveError('CURVE_HEIGHT: a superfície selecionada exige uma curva maior que o limite em mm. '
                        'Aumente o limite ou escolha outra região; o original foi preservado.')
    step=3.;anchor=max(.5,2*profile.initial_layer_mm)
    axes=[np.arange(math.floor((mesh.bounds[0][k]-6-2*step)/step)*step,
        math.ceil((mesh.bounds[1][k]+6+2*step)/step)*step+step/2,step) for k in (0,1)]
    axes.append(anchor+np.arange(-2,math.ceil((mesh.bounds[1][2]+10-anchor)/step)+1)*step)
    if math.prod(len(a) for a in axes)>24000 or len(regions)>12:
        raise WaveError('SPLINE_COMPLEXITY: reduza a peça para este estudo de camadas contínuas.')
    minimum=number(resolved,'min_layer_height',profile.nozzle_mm*.2)
    maximum=number(resolved,'max_layer_height',profile.nozzle_mm*.75)
    if not 0<minimum<=profile.layer_mm<=maximum:
        raise WaveError('SPLINE_PROFILE: confira a altura e os limites de camada do perfil.')
    progress('Conferindo também o material dentro do sólido e junto à base…')
    physical=material_samples(mesh,cancelled=cancelled)
    key=phase_cache_key(mesh,profile,minimum,maximum,settings.max_slope_deg,settings.step_mm,settings.max_curve_height_mm)
    path=Path(cache_folder)/(key+'.npz') if cache_folder is not None else None
    field=None;passes=[];cache_hit=False
    if path is not None and path.is_file():
        try:
            with np.load(path,allow_pickle=False) as cached:
                if str(cached['geometry_key'].item())!=key:raise ValueError('cache identity')
                field=SplinePhase([cached[k] for k in ('x','y','z')],cached['coefficients'],anchor)
                curve_height_certificate(field,settings.max_curve_height_mm)
                if assess_phase_field(field,regions,profile,minimum,maximum,'cached proposal',anchor,
                        field.domain[2][1],require_global_profile_bounds=False) is None:
                    raise ValueError('reference alignment')
                cache_hit=True
                progress('Reutilizando o cálculo da peça e conferindo novamente formato e espaçamento…')
        except (OSError,ValueError,KeyError,WaveError):field=None
    if field is None:
        for _ in range(2):
            field,audit=_solve(axes,regions,physical,profile,minimum,maximum,settings.max_slope_deg,anchor,
                progress=progress,cancelled=cancelled,previous=field)
            # Most default-height jobs already fit. Preserve the fast sparse
            # proposal and add the coupled range constraints only when needed.
            if (settings.max_curve_height_mm is not None and
                    curve_height_certificate(field,None)['certified_peak_to_valley_upper_bound_mm']>settings.max_curve_height_mm):
                progress('Ajustando o movimento ao limite de altura da curva…')
                field,audit=_solve(axes,regions,physical,profile,minimum,maximum,settings.max_slope_deg,anchor,
                    progress=progress,cancelled=cancelled,previous=field,max_curve_height_mm=settings.max_curve_height_mm)
            passes.append(audit)
    status='cached proposal; independent checks required' if cache_hit else audit['optimizer_status']
    candidate=assess_phase_field(field,regions,profile,minimum,maximum,status,
        anchor,field.domain[2][1],require_global_profile_bounds=False)
    if candidate is None:
        raise WaveError('SPLINE_ALIGNMENT: as superfícies ainda não cabem em camadas contínuas; o original foi preservado.')
    if path is not None and not cache_hit:
        from .capture import atomic_write
        import io
        payload=io.BytesIO()
        np.savez_compressed(payload,geometry_key=key,coefficients=field.coefficients,
                           **dict(zip(('x','y','z'),field.axes)))
        path.parent.mkdir(parents=True,exist_ok=True)
        atomic_write(path,payload.getvalue())
    _,regrid,reference_audit=candidate
    settings=replace(settings,nominal_layer_height_mm=reference_audit['pitch'])
    warp=SplineLayerWarp(snapshot,object_id,field,regrid,settings,reference_audit=reference_audit,
        progress=progress,cancelled=cancelled)
    warp._spacing_regions=regions
    warp.summary['planning_passes']=passes
    warp.summary['curve_height']=curve_height_certificate(field,settings.max_curve_height_mm)
    warp.summary['phase_cache']={'key':key,'proposal_reused':cache_hit,'qualification_reused':False}
    warp.summary['profile_height_bounds_pass']=False
    warp.summary['profile_height_validation']='required on actual finite bead contributions after native slice'
    return warp
