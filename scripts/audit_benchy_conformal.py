"""Read-only proof of roof extrusion, protected regions and Preview payload."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio.contracts import digest
from orca_wave_studio.engine_parser import read
from orca_wave_studio.package import extract_plate_gcode


def audit(folder):
    report=json.loads((folder/'conformal-report.json').read_text(encoding='utf-8'))
    source=(folder/'native-flat/plate_1.gcode').read_bytes()
    final=(folder/'benchy-conformal.gcode').read_bytes()
    package=folder/'benchy-conformal.gcode.3mf'
    anchor=report['warp']['anchor_z_mm'];top=report['warp']['zmax_mm']
    values=[]
    for content in (source,final):
        parsed=read(content,set(),{0:'1'})
        body_e=upper_e=0.;upper_nonplanar=roof_nonplanar=roof_top=0
        layers={}
        for m in parsed.moves.values():
            if not m.deposits:continue
            if m.z<=anchor:body_e+=m.de
            if m.z>top:
                upper_e+=m.de
                upper_nonplanar+=abs(m.end[2]-m.z)>2e-6 or abs(m.start[2]-m.z)>2e-6
            if anchor<m.z<=top and abs(m.end[2]-m.start[2])>2e-6:
                roof_nonplanar+=1
                if m.role=='top surface':
                    roof_top+=1
                    row=layers.setdefault(str(m.layer),{'logical_z_mm':m.z,'up':0,'down':0,
                        'z_min_mm':min(m.start[2],m.end[2]),'z_max_mm':max(m.start[2],m.end[2])})
                    row['up' if m.end[2]>m.start[2] else 'down']+=1
                    row['z_min_mm']=min(row['z_min_mm'],m.start[2],m.end[2])
                    row['z_max_mm']=max(row['z_max_mm'],m.start[2],m.end[2])
        values.append({'body_extrusion_mm':body_e,'upper_detail_extrusion_mm':upper_e,
            'upper_detail_displaced_moves':upper_nonplanar,'roof_nonplanar_extrusions':roof_nonplanar,
            'roof_top_surface_nonplanar_extrusions':roof_top,'roof_top_surface_layers':layers})
    before,after=values
    assert before['roof_nonplanar_extrusions']==0
    assert after['roof_top_surface_nonplanar_extrusions']>0
    assert any(row['up'] and row['down'] for row in after['roof_top_surface_layers'].values())
    assert after['upper_detail_displaced_moves']==0
    assert abs(after['body_extrusion_mm']-before['body_extrusion_mm'])<1e-4
    assert abs(after['upper_detail_extrusion_mm']-before['upper_detail_extrusion_mm'])<1e-4
    assert digest(final)==digest(extract_plate_gcode(package,0))==report['processed_sha256']
    assert report['max_geometric_error_mm']<=.02
    assert report['min_subdivided_segment_mm']>=.15-2e-6
    assert not report['print_allowed']
    result={'status':'PASS_FILE_AUDIT_PENDING_NATIVE_GUI','source':before,'processed':after,
        'gcode_and_package_sha256':digest(final),'native_preview_validated':False,
        'physical_validation':False,'print_allowed':False,
        'native_short_edge_proposal':report['native_short_edge_proposal'],
        'changed_inherited_short_edges':report['inherited_mapped_short_deposition_segments'],
        'changed_inherited_short_min_mm':report['inherited_mapped_short_deposition_min_mm'],
        'min_recreated_deposition_segment_mm':report['min_subdivided_segment_mm'],
        'max_chord_error_mm':report['max_geometric_error_mm']}
    (folder/'file-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    audit(ROOT/'study/evidence/benchy-roof/conformal-v041')
