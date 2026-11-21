"""Separate support field for the restricted single flat-ceiling roof coupon.

Native support layers stay attached to their fixed base. Their uniform ceiling
maps to the target underside minus a vertical gap, independently of the model
field. This remains a deposition estimate and never grants physical approval.
"""
import copy
import math

from .contracts import WaveError
from .engine_parser import read


def with_paired_support_gap(warp, source, mapping, object_id, *, vertical_gap_mm):
    """Return an independent roof-field copy with a separate support mapping.

    ``source`` is the labelled native planar slice of the restricted coupon's
    single flat ceiling. ``vertical_gap_mm`` is the gap to the ideal underside,
    not an assertion about the final bead surface or normal clearance. Existing
    model coordinates and the input field are preserved. Ownership ambiguity,
    duplicate application and nonpositive column Jacobians raise ``WaveError``.
    """
    if (type(vertical_gap_mm) not in (float, int) or not math.isfinite(vertical_gap_mm)
            or not .1 <= vertical_gap_mm <= 1.):
        raise WaveError('SUPPORT_GAP: use a finite vertical gap between 0.1 and 1 mm.')
    if getattr(warp, 'summary', {}).get('surface_scope') != 'complete_rectangular_paired_shell':
        raise WaveError('SUPPORT_SCOPE: only the paired rectangular coupon is supported.')
    if getattr(warp, 'object_id', None) != object_id:
        raise WaveError('SUPPORT_OBJECT: the roof field belongs to another object.')
    if hasattr(warp, 'support_warp'):
        raise WaveError('SUPPORT_DUPLICATE: an independent support field is already attached.')
    parsed = read(source, set(), mapping)
    supports = [m for m in parsed.moves.values() if m.deposits and 'support' in m.role]
    if not supports or any(m.obj != object_id for m in supports):
        raise WaveError('SUPPORT_OWNER: every support trace must belong to the selected object.')
    if any(None in m.start + m.end or abs(m.start[2]-m.end[2]) > 2e-5 for m in supports):
        raise WaveError('SUPPORT_SOURCE: support traces must be planar and fully positioned.')
    ceiling = max(m.end[2] for m in supports)
    if not warp.anchor_z < ceiling < warp.flat_bottom_z:
        raise WaveError('SUPPORT_CEILING: the support ceiling must lie between anchor and roof.')
    child = copy.copy(warp)
    child.bottom_plane = (*warp.bottom_plane[:2], warp.bottom_plane[2] - vertical_gap_mm)
    child.top_plane = (*warp.top_plane[:2], warp.top_plane[2] - vertical_gap_mm)
    child.flat_bottom_z = ceiling
    child.flat_top_z = ceiling + warp.thickness_mm
    child.shell_scale = 1.
    if any(child._field(x, y) <= child.anchor_z for x in child.bounds_xy[0] for y in child.bounds_xy[1]):
        raise WaveError('SUPPORT_JACOBIAN: requested gap reaches the fixed support base.')
    result = copy.copy(warp)
    result.summary = copy.deepcopy(warp.summary)
    result.support_warp = child
    result.summary['independent_support_field'] = {
        'native_support_ceiling_z_mm': ceiling, 'target_vertical_gap_mm': float(vertical_gap_mm),
        'fixed_base_z_mm': warp.anchor_z, 'base_and_model_preserved': True,
        'source_support_deposition_moves': len(supports), 'print_allowed': False,
        'scope': 'single selected rectangular paired shell; not arbitrary supports or models'}
    return result
