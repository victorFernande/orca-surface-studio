"""Rigid placement of the study copy and unqualified per-printer head maps."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
from .capture import atomic_write
from .contracts import WaveError,fingerprint
from .geometry import transform_point


def rotate_study_copy(snapshot,object_id,degrees,profile):
    if type(degrees) not in (int,float) or not math.isfinite(degrees) or not -360<=degrees<=360:
        raise WaveError('PLACEMENT_ANGLE: use um ângulo entre -360 e 360 graus.')
    selected=next((o for o in snapshot.objects if str(o['id'])==str(object_id)),None)
    if selected is None:raise WaveError('PLACEMENT_OBJECT: selecione um modelo.')
    points=[transform_point(p,i['matrix'],v['matrix']) for i in selected['instances_data'] if i.get('printable',True)
            for v in selected['volumes'] for p in v['vertices']]
    if not points:raise WaveError('PLACEMENT_OBJECT: modelo sem geometria imprimível.')
    pivot=[(min(p[k] for p in points)+max(p[k] for p in points))/2 for k in (0,1)]
    angle=math.radians(degrees);c,s=math.cos(angle),math.sin(angle)
    c=round(c) if abs(c-round(c))<1e-14 else c;s=round(s) if abs(s-round(s))<1e-14 else s
    transform=[[c,-s,0.,pivot[0]*(1-c)+s*pivot[1]],
               [s,c,0.,pivot[1]*(1-c)-s*pivot[0]],[0.,0.,1.,0.],[0.,0.,0.,1.]]
    rotated=copy.deepcopy(snapshot)
    target=next(o for o in rotated.objects if str(o['id'])==str(object_id))
    for instance in target['instances_data']:
        if not instance.get('printable',True):continue
        old=instance['matrix']
        instance['matrix']=[[sum(transform[i][k]*old[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
    for instance in target['instances_data']:
        if instance.get('printable',True):
            for volume in target['volumes']:
                if any(not profile.contains(transform_point(p,instance['matrix'],volume['matrix'])) for p in volume['vertices']):
                    raise WaveError('PLACEMENT_BED: a peça girada sai da mesa; reposicione no Prepare do Orca.')
    return rotated,{'rotation_z_deg':float(degrees),'pivot_xy_mm':pivot,'scale_changed':False,
        'source_project_modified':False,'physical_validation':False,'print_allowed':False}


class HeadMapStore:
    """A user sketch is never a calibrated collision or printing certificate."""
    def __init__(self,storage):self.folder=Path(storage)/'head-maps'
    @staticmethod
    def identity(profile):
        if (not isinstance(profile,dict) or not isinstance(profile.get('name'),str) or not profile['name']
                or type(profile.get('nozzle_mm')) not in (int,float)
                or not math.isfinite(profile['nozzle_mm']) or profile['nozzle_mm']<=0):
            raise WaveError('HEAD_MAP_PROFILE: escolha o perfil da impressora no Orca.')
        return {'printer_name':profile['name'],'nozzle_mm':profile['nozzle_mm']}
    def load(self,profile):
        identity=self.identity(profile);key=fingerprint(identity);path=self.folder/(key+'.json')
        try:
            data=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data,dict) or data.get('identity')!=identity:raise ValueError('profile mismatch')
            components=self.validate(data['components'])
        except (OSError,ValueError,KeyError,TypeError):components=[]
        return {'profile_key':key,'identity':identity,'components':components,
            'frame':'printer XY relative to nozzle tip; +Y toward bed rear',
            'registration_verified':False,'complete_head_verified':False,'print_allowed':False}
    @staticmethod
    def validate(components):
        if not isinstance(components,list) or len(components)>12:raise WaveError('HEAD_MAP: use até 12 partes do cabeçote.')
        result=[]
        for part in components:
            if not isinstance(part,dict):raise WaveError('HEAD_MAP: parte inválida.')
            name=part.get('name');values=[part.get(k) for k in ('x_min','x_max','y_min','y_max','clearance_z')]
            if not isinstance(name,str) or not 1<=len(name.strip())<=60 or any(ord(c)<32 for c in name):
                raise WaveError('HEAD_MAP: informe o nome da parte.')
            if any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>300 for v in values):
                raise WaveError('HEAD_MAP: informe medidas finitas em milímetros.')
            a,b,c,d,z=values
            if a>=b or c>=d or z<=0:raise WaveError('HEAD_MAP: confira os limites e a altura acima da ponta do bico.')
            result.append({'name':name.strip(),**dict(zip(('x_min','x_max','y_min','y_max','clearance_z'),values))})
        return result
    def save(self,profile,key,components):
        current=self.load(profile)
        if key!=current['profile_key']:raise WaveError('HEAD_MAP_STALE: a impressora mudou; recarregue o mapa.')
        current['components']=self.validate(components)
        self.folder.mkdir(parents=True,exist_ok=True)
        atomic_write(self.folder/(key+'.json'),json.dumps(current,ensure_ascii=False,indent=2).encode())
        return current
