"""Bounded display mesh, independent of the processing/print geometry."""
from __future__ import annotations

import math
from .contracts import fingerprint
from .geometry import transform_point


def model_preview(snapshot, max_triangles=4000):
    objects=[]
    for obj in snapshot.objects:
        triangles=[];low=[math.inf]*3;high=[-math.inf]*3
        instances=[i for i in obj.get('instances_data',[]) if i.get('printable',True)]
        total=sum(len(v.get('triangles',[])) for v in obj.get('volumes',[]))*len(instances)
        source_faces=[]
        for instance in instances:
            for vol in obj.get('volumes',[]):
                if vol.get('kind')!='part' or vol.get('negative'):continue
                points=[transform_point(p,instance['matrix'],vol['matrix']) for p in vol['vertices']]
                for p in points:
                    for k in range(3):low[k]=min(low[k],p[k]);high[k]=max(high[k],p[k])
                for tri in vol['triangles']:
                    source_faces.append(tuple(points[i] for i in tri))
        if source_faces:
            # Cluster only the display mesh. Sampling independent source facets
            # would make a dense STL appear full of holes in the viewport.
            cell=max(max(high[k]-low[k] for k in range(3))/100,1e-5)
            triangles=source_faces
            for attempt in range(12):
                buckets={};sums={};mapped=[]
                for tri in source_faces:
                    keys=[]
                    for p in tri:
                        key=tuple(math.floor((p[k]-low[k])/cell) for k in range(3));keys.append(key)
                        if key not in sums:sums[key]=[0.,0.,0.,0]
                        row=sums[key]
                        for k in range(3):row[k]+=p[k]
                        row[3]+=1
                    if len(set(keys))==3:buckets.setdefault(tuple(sorted(keys)),keys)
                if len(buckets)<=max_triangles or attempt==11:
                    triangles=[[[round(sums[key][k]/sums[key][3],5) for k in range(3)] for key in keys]
                               for keys in list(buckets.values())[:max_triangles]]
                    break
                cell*=1.35
        if triangles:
            objects.append({'id':str(obj['id']),'name':obj['name'],'triangles':triangles,
                            'bounds':[low,high],'display_only':True,'source_triangles':total})
    return {'id':fingerprint(objects),'objects':objects,'display_only':True}
