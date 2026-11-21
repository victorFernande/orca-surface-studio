"""Resolved machine/process/filament contract. No printer-brand defaults."""
from __future__ import annotations

from dataclasses import dataclass,asdict
import json
import math
import re

from .contracts import WaveError,fingerprint


def value(settings,key,default=None):
    raw=settings.get(key,default)
    if isinstance(raw,str):
        try:return json.loads(raw)
        except (ValueError,TypeError):return raw
    return raw


def number(settings,key,default=None,index=0):
    raw=value(settings,key,default)
    if isinstance(raw,(list,tuple)):raw=raw[min(index,len(raw)-1)] if raw else default
    elif isinstance(raw,str) and ',' in raw:
        # full_config_value serializes numeric vectors as "normal,silent";
        # exported 3MF settings use JSON arrays for the same resolved values.
        values=raw.split(',');raw=values[min(index,len(values)-1)].strip()
    try:result=float(raw)
    except (TypeError,ValueError):raise WaveError(f'PROFILE_MISSING: confira {key} no perfil selecionado.')
    if not math.isfinite(result) or result<=0:
        raise WaveError(f'PROFILE_INVALID: {key} precisa ser positivo e finito.')
    return result


@dataclass(frozen=True)
class PrinterProfile:
    name:str
    firmware:str
    nozzle_mm:float
    filament_mm:float
    layer_mm:float
    initial_layer_mm:float
    z_speed_mm_s:float
    z_acceleration_mm_s2:float
    max_volumetric_mm3_s:float|None
    height_mm:float
    bed:tuple
    revision:str

    @classmethod
    def from_settings(cls,settings):
        firmware=str(value(settings,'gcode_flavor','')).lower()
        if not firmware:
            raise WaveError('PROFILE_FIRMWARE: escolha um perfil com dialeto G-code definido.')
        if str(value(settings,'printer_kinematics','')).lower() in {'belt','belt_printer'} or value(settings,'belt_printer',False) in (True,1,'1'):
            raise WaveError('PROFILE_FRAME: o perfil de esteira precisa de transformação de eixos própria.')
        bed=value(settings,'printable_area',[])
        if isinstance(bed,str):bed=bed.split(',')
        points=[]
        for p in bed:
            if isinstance(p,str):p=re.split('[xX]',p)
            if len(p)!=2:raise WaveError('PROFILE_BED: contorno da mesa inválido.')
            points.append(tuple(float(v) for v in p))
        if len(points)<3 or not all(math.isfinite(v) for p in points for v in p):
            raise WaveError('PROFILE_BED: o perfil precisa informar o contorno da mesa.')
        flow=value(settings,'filament_max_volumetric_speed',None)
        if isinstance(flow,(list,tuple)):flow=flow[0] if flow else None
        flow=float(flow) if flow not in (None,'') else None
        if flow is not None and (not math.isfinite(flow) or flow<0):raise WaveError('PROFILE_FLOW: vazão inválida.')
        return cls(str(value(settings,'printer_settings_id','Impressora selecionada')),firmware,
                   number(settings,'nozzle_diameter'),number(settings,'filament_diameter'),
                   number(settings,'layer_height'),number(settings,'initial_layer_print_height'),
                   number(settings,'machine_max_speed_z'),number(settings,'machine_max_acceleration_z'),
                   flow or None,number(settings,'printable_height'),tuple(points),fingerprint(settings))

    def public_summary(self):
        return asdict(self)

    def contains(self,p,tolerance=.001):
        x,y,z=p
        if not all(math.isfinite(v) for v in p) or not -tolerance<=z<=self.height_mm+tolerance:return False
        inside=False
        for a,b in zip(self.bed,(*self.bed[1:],self.bed[0])):
            dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
            t=max(0.,min(1.,((x-a[0])*dx+(y-a[1])*dy)/den)) if den else 0.
            if math.hypot(x-a[0]-t*dx,y-a[1]-t*dy)<=tolerance:return True
            if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
        return inside
