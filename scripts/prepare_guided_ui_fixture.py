"""Create reproducible offline UI fixtures; these are not printable results."""
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio.geometry import analyze_snapshot
from orca_wave_studio.model_preview import model_preview
from orca_wave_studio.roof_fixtures import roof_coupon
from orca_wave_studio.studio_ui import get_studio_html


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    snapshot,_=roof_coupon(25)
    objects=analyze_snapshot(snapshot)
    state={'status':'slicing_required','message':'Fixture isolada de interface.',
           'objects':objects,'revision':snapshot.revision,'native':True,'sequence':1,
           'bench_only':True,'component_test_only':True,'selected_object_ids':[str(objects[0]['id'])],
           'model_preview':model_preview(snapshot),'language':'pt',
           'printer_profile':{'name':'Perfil de teste local','nozzle_mm':.4,'layer_mm':.2,'firmware':'Marlin'}}
    for name,dock in [('model',False),('dock',True)]:
        (args.output/f'{name}.html').write_text(get_studio_html(state,dock=dock),encoding='utf-8')
    result={'sha256':'a'*64,'study_kind':'surface','workflow':'integrated',
            'component_test_only':True,'report':{'print_allowed':False,'physical_validation':False},
            'deformed_points':[[0,0,2],[1,0,2.1],[2,0,2.2]],'layer_ids':[0,0,0]}
    (args.output/'result.json').write_text(json.dumps(result),encoding='utf-8')
    print(args.output.resolve())


if __name__=='__main__':
    main()
