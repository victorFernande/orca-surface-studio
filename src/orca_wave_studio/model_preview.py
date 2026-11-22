"""Faithful display mesh, independent of processing and print geometry.

Large models use indexed float32 buffers rather than destructive clustering.
No source face is sampled, collapsed or truncated.
"""
from __future__ import annotations

import math
from array import array
import base64
import sys
from .contracts import fingerprint
from .geometry import transform_point


def _buffer(values, kind):
    data = array(kind, values)
    if data.itemsize != 4:
        raise RuntimeError('Display buffers require four-byte components')
    if sys.byteorder != 'little':
        data.byteswap()
    return base64.b64encode(data.tobytes()).decode('ascii')


def model_preview(snapshot):
    objects = []
    for obj in snapshot.objects:
        vertices, indices = [], []
        low, high = [math.inf] * 3, [-math.inf] * 3
        for instance in obj.get('instances_data', []):
            if not instance.get('printable', True):
                continue
            for volume in obj.get('volumes', []):
                if volume.get('kind') != 'part' or volume.get('negative'):
                    continue
                # Weld exact positions inside each volume, never between parts.
                welded, source_indices = {}, {}
                for face in volume['triangles']:
                    for source_index in face:
                        if source_index not in source_indices:
                            point = tuple(transform_point(volume['vertices'][source_index],
                                                          instance['matrix'], volume['matrix']))
                            if point not in welded:
                                welded[point] = len(vertices) // 3
                                vertices.extend(point)
                                for axis in range(3):
                                    low[axis] = min(low[axis], point[axis])
                                    high[axis] = max(high[axis], point[axis])
                            source_indices[source_index] = welded[point]
                        indices.append(source_indices[source_index])
        if not indices:
            continue
        count = len(indices) // 3
        item = {'id': str(obj['id']), 'name': obj['name'], 'bounds': [low, high],
                'display_only': True, 'source_triangles': count,
                'source_fidelity': 'original_faces', 'triangles': []}
        if count <= 4000:
            points = [vertices[i:i + 3] for i in range(0, len(vertices), 3)]
            item['triangles'] = [[points[index] for index in indices[i:i + 3]]
                                 for i in range(0, len(indices), 3)]
        else:
            item['mesh'] = {'encoding': 'indexed-f32-u32-le-v1',
                            'vertex_count': len(vertices) // 3, 'triangle_count': count,
                            'positions': _buffer(vertices, 'f'), 'indices': _buffer(indices, 'I')}
        objects.append(item)
    return {'id': fingerprint(objects), 'objects': objects, 'display_only': True,
            'source_fidelity': 'original_faces'}
