"""Native height bands and an output gate, without rewriting deposition XYZ/E."""
from __future__ import annotations

import math
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .contracts import WaveError
from .engine_parser import read
from .geometry import transform_point
from .printer_profile import number


def finishing_plan(settings, obj, areas):
    """Refine layer sampling in selected height bands, respecting nozzle limits."""
    nominal=number(settings,'layer_height');initial=number(settings,'initial_layer_print_height')
    nozzle=number(settings,'nozzle_diameter')
    minimum=number(settings,'min_layer_height',nozzle*.2)
    maximum=number(settings,'max_layer_height',nozzle*.75)
    if minimum>maximum or nominal<minimum-1e-6 or nominal>maximum+1e-6:
        raise WaveError('FINISH_PROFILE: confira as alturas mínima, nominal e máxima no perfil selecionado.')
    # Aim at three times the source vertical resolution, never below the
    # machine/nozzle profile minimum. Quantize upward, not below that limit.
    fine=min(nominal,math.ceil(max(minimum,nominal/3)*1000-1e-8)/1000)
    inst=next(i for i in obj['instances_data'] if i.get('printable',True))
    zs=[transform_point(p,inst['matrix'],v['matrix'])[2] for v in obj['volumes'] for p in v['vertices']]
    bottom,top=min(zs),max(zs);height=top-bottom
    if height<=initial+fine:
        raise WaveError('FINISH_HEIGHT: a peça precisa de altura acima da primeira camada para estudar o acabamento.')
    bands=[]
    for area in areas or [{'center':[0,0,(top+bottom)/2],'radius_mm':height}]:
        center=area['center'][2]-bottom;radius=area['radius_mm']
        # Keep one conventional layer of padding around the selected envelope;
        # the native height interpolation then settles before contouring starts.
        lo=max(initial,math.floor((center-radius)/nominal)*nominal-nominal)
        hi=min(height,math.ceil((center+radius)/nominal)*nominal+nominal)
        if hi>lo:bands.append([round(lo,6),round(hi,6)])
    merged=[]
    for lo,hi in sorted(bands):
        if merged and lo<=merged[-1][1]+1e-6:merged[-1][1]=max(merged[-1][1],hi)
        else:merged.append([lo,hi])
    if not merged:raise WaveError('FINISH_BAND: as áreas não alcançam uma faixa imprimível da peça.')
    return {'nominal_layer_mm':nominal,'finishing_layer_mm':fine,
            'profile_minimum_layer_mm':minimum,'profile_maximum_layer_mm':maximum,
            'minimum_z_mm':fine/2,'first_layer_mm':initial,
            'ranges':[{'min_z':lo,'max_z':hi,'layer_height':fine} for lo,hi in merged],
            'sampling_reduction_percent':100*(1-fine/nominal),
            'mesh_vertices_moved':0,'xyz_e_rewritten':False,
            'scope':('whole cross-sections in selected height bands; Z contouring only in selected areas'
                     if areas else 'whole object above the preserved first layer; all eligible surfaces')}


def verify_finishing_ranges(package, plan):
    with ZipFile(package) as archive:
        try:root=ET.fromstring(archive.read('Metadata/layer_config_ranges.xml'))
        except KeyError:raise WaveError('FINISH_NATIVE: o Orca não preservou as faixas de acabamento.')
    objects=root.findall('object')
    if len(objects)!=1 or objects[0].get('id')!='1':
        raise WaveError('FINISH_NATIVE: identificação das faixas de acabamento alterada.')
    actual=[]
    for band in objects[0].findall('range'):
        options={e.get('opt_key'):e.text for e in band.findall('option')}
        actual.append({'min_z':float(band.get('min_z')),'max_z':float(band.get('max_z')),
                       'layer_height':float(options.get('layer_height','nan'))})
    if len(actual)!=len(plan['ranges']) or any(
            not math.isclose(a[k],b[k],abs_tol=1e-6) for a,b in zip(actual,plan['ranges']) for k in b):
        raise WaveError('FINISH_NATIVE: o fatiador alterou as faixas ou a altura de acabamento.')
    return {'matched':True,'ranges':actual}


def audit_finishing(data, mapping, plan, slope_limit):
    """Check real emitted extrusion, including short edges and both wall sides."""
    parsed=read(data,set(),mapping,profile_macros=True,require_planar=False)
    maximum=0.;worst=None;fine_segments=0;first=0;feature_heights=[];nominal={}
    for move in parsed.moves.values():
        if move.deposits and move.obj in mapping.values() and move.z is not None:
            if move.layer in nominal and abs(nominal[move.layer]-move.z)>2e-5:
                raise WaveError('FINISH_LAYERS: a camada lógica tem alturas nominais incompatíveis.')
            nominal[move.layer]=move.z
    ordered=sorted(nominal)
    steps={layer:nominal[layer]-nominal[previous] for previous,layer in zip(ordered,ordered[1:])}
    minimum=plan.get('profile_minimum_layer_mm',plan['finishing_layer_mm'])
    maximum_layer=plan.get('profile_maximum_layer_mm',plan['first_layer_mm'])
    if any(not minimum-2e-5<=h<=maximum_layer+2e-5 for h in steps.values()):
        raise WaveError('FINISH_LAYERS: o espaçamento entre camadas saiu dos limites do perfil.')
    for move in parsed.moves.values():
        if not move.deposits or move.obj not in mapping.values():continue
        if move.layer==0:
            first+=1
            if max(abs(p[2]-plan['first_layer_mm']) for p in (move.start,move.end))>2e-5:
                raise WaveError('FINISH_FIRST_LAYER: o contorno alterou a primeira camada; o resultado foi recusado.')
        if move.h is not None:
            feature_heights.append(move.h)
        if move.layer in steps and abs(steps[move.layer]-plan['finishing_layer_mm'])<=2e-5:fine_segments+=1
        angle=math.degrees(math.atan2(abs(move.end[2]-move.start[2]),math.dist(move.start[:2],move.end[:2])))
        if angle>maximum:maximum=angle;worst=move.i+1
    if not fine_segments or not first:
        raise WaveError('FINISH_NATIVE: a trajetória não confirmou o acabamento e a primeira camada esperados.')
    if maximum>slope_limit+1e-7:
        raise WaveError(f'FINISH_SLOPE: o Orca ainda gerou uma transição de {maximum:.1f}°, acima de {slope_limit:g}°. '
                        'O resultado foi recusado para preservar a peça; escolha uma região menor.')
    return {'maximum_motion_slope_deg':maximum,'limit_deg':slope_limit,'within_study_limit':True,
            'worst_line':worst,'finishing_deposition_segments':fine_segments,
            'first_layer_preserved':True,'minimum_layer_step_mm':min(steps.values()),
            'maximum_layer_step_mm':max(steps.values()),
            'maximum_feature_height_mm':max(feature_heights,default=0.),'physical_qualification':False}
