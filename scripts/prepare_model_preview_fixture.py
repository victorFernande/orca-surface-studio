"""Prepare a local, offline single-mesh 3MF visual regression fixture."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--source-tree', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    sys.path.insert(0, str(args.source_tree / 'scripts'))
    from run_benchy_probe import read_reference
    from orca_wave_studio import __version__
    from orca_wave_studio.geometry import analyze_snapshot
    from orca_wave_studio.model_preview import model_preview
    from orca_wave_studio.studio_ui import get_studio_html

    snapshot = read_reference(args.model)
    before = time.perf_counter()
    preview = model_preview(snapshot)
    elapsed = time.perf_counter() - before
    objects = analyze_snapshot(snapshot)
    state = {'status': 'slicing_required', 'message': 'Teste local da visualização.',
             'objects': objects, 'revision': snapshot.revision, 'native': True,
             'sequence': 1, 'bench_only': True, 'component_test_only': True,
             'selected_object_ids': [str(objects[0]['id'])], 'model_preview': preview,
             'printer_profile': {'name': 'Fixture local', 'nozzle_mm': .4, 'layer_height': .2}}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'model.html').write_text(get_studio_html(state), encoding='utf8')
    metrics = {'version': __version__, 'source_sha256': hashlib.sha256(args.model.read_bytes()).hexdigest(),
               'source_triangles': sum(o['source_triangles'] for o in preview['objects']),
               'display_triangles': sum(o.get('mesh', {}).get('triangle_count', len(o['triangles']))
                                        for o in preview['objects']),
               'preview_seconds': elapsed, 'payload_bytes': len(json.dumps(preview).encode('utf8')),
               'native_orca_controlled': False, 'printer_contacted': False}
    (args.output / 'metrics.json').write_text(json.dumps(metrics, indent=2) + '\n', encoding='utf8')
    print(json.dumps(metrics))


if __name__ == '__main__':
    main()
