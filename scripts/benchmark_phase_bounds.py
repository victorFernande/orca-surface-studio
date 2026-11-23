"""Compare exact certificate queries on a saved mesh; never slices or prints.

The baseline is Python source from a local Git commit in this repository.
Only the certificate-query stage is timed, not the complete plugin workflow.
"""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio.spline_phase import SplinePhase
from orca_wave_studio.geometry import transform_point


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('snapshot',type=Path);p.add_argument('phase_cache',type=Path)
    p.add_argument('output',type=Path);p.add_argument('--baseline-ref',default='032c8e8')
    p.add_argument('--faces',type=int,default=12000);p.add_argument('--repeats',type=int,default=3)
    args=p.parse_args()
    if args.faces<1 or args.repeats<1:p.error('Use positive counts.')
    source=subprocess.check_output(['git','show',f'{args.baseline_ref}:src/orca_wave_studio/spline_phase.py'],cwd=ROOT)
    namespace={'__name__':'orca_wave_studio._benchmark_baseline','__package__':'orca_wave_studio'}
    exec(compile(source,'<local Git baseline>','exec'),namespace)
    saved=json.loads(args.snapshot.read_text(encoding='utf-8'))
    obj=saved['objects'][0];vol=obj['volumes'][0];instance=obj['instances_data'][0]
    vertices=np.asarray([transform_point(v,instance['matrix'],vol['matrix']) for v in vol['vertices']])
    triangles=np.asarray(vol['triangles']);indices=np.linspace(0,len(triangles)-1,min(args.faces,len(triangles)),dtype=int)
    faces=vertices[triangles[indices]]
    # Include nearby subdivision queries as encountered during mesh refinement.
    mids=(faces[:,0]+faces[:,1])/2
    queries=np.concatenate((faces,np.stack((faces[:,0],mids,faces[:,2]),axis=1)))
    with np.load(args.phase_cache,allow_pickle=False) as cache:
        axes=tuple(cache[k].copy() for k in ('x','y','z'));coeff=cache['coefficients'].copy()
    def run(cls):
        times=[];reference=None;stats=None
        for _ in range(args.repeats):
            field=cls(axes,coeff);start=time.perf_counter()
            values=[(field.hessian_bounds(q),field.derivative_bounds(q)) for q in queries]
            times.append(time.perf_counter()-start)
            if reference is not None:assert values==reference
            reference=values
            if hasattr(field,'_hessian_query'):
                stats={key:getattr(field,key).cache_info()._asdict() for key in ('_hessian_query','_derivative_query')}
        return times,reference,stats
    before,expected,_=run(namespace['SplinePhase']);after,actual,stats=run(SplinePhase)
    assert actual==expected,'Certificate changed; reject the optimization.'
    report={'scope':'exact local coefficient-bound queries only; not end-to-end slicing',
            'baseline_ref':args.baseline_ref,'source_sha256':hashlib.sha256(args.snapshot.read_bytes()).hexdigest(),
            'source_faces':len(triangles),'query_boxes':len(queries),'repeats':args.repeats,
            'baseline_seconds':before,'optimized_seconds':after,
            'baseline_median_seconds':statistics.median(before),'optimized_median_seconds':statistics.median(after),
            'speedup':statistics.median(before)/statistics.median(after),'identical_certificates':True,
            'cache':stats,'printer_contacted':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
