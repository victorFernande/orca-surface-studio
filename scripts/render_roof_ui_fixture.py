"""Render a local component-test state, not a native Orca or print result."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from orca_wave_studio.capture import atomic_write
from orca_wave_studio.geometry import analyze_snapshot
from orca_wave_studio.roof_fixtures import roof_coupon
from orca_wave_studio.roof_regions import roof_region_catalog
from orca_wave_studio.studio_ui import get_studio_html

snapshot,_=roof_coupon(25)
objects=analyze_snapshot(snapshot)
objects[0]['roof_regions']=roof_region_catalog(snapshot,'1')
state={'status':'slicing_required','message':'Fixture isolada de interface — sem conexão com impressora.',
    'objects':objects,'revision':snapshot.revision,'native':True,'sequence':1,'bench_only':True,
    'selected_object_ids':['1'],'component_test_only':True}
output=ROOT/'study/evidence/roof-study/ui/studio-regional.html'
atomic_write(output,get_studio_html(state).encode())
atomic_write(output.with_suffix('.json'),json.dumps(state,ensure_ascii=False,indent=2).encode())
print(output)
