"""Conservative continuous head/prefix-material checks, independent of G-code.

All component envelopes are fixed-orientation AABBs relative to the nozzle TCP.
Slab intersection of the TCP segment with a Minkowski-expanded material AABB
checks every point of a motion. A hit is only a POTENTIAL_COLLISION: enclosing
boxes can overlap while the physical shapes remain disjoint. A disjoint result
is conditional on complete conservative inputs, never physical print approval.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict,dataclass
import math

from .contracts import WaveError,fingerprint


REQUIRED_COMPONENTS=frozenset({'nozzle','heater','sock','duct','fan','sensor'})
REAL_PROVENANCE=frozenset({'measured','manufacturer_cad'})


def _point(values):
    if (not isinstance(values,(tuple,list)) or len(values)!=3
            or not all(type(v) in (int,float) and math.isfinite(v) for v in values)):
        raise WaveError('HEAD_COORDINATE: use três coordenadas finitas em milímetros.')
    return tuple(float(v) for v in values)


@dataclass(frozen=True)
class AABB:
    minimum_mm: tuple[float,float,float]
    maximum_mm: tuple[float,float,float]

    def __post_init__(self):
        object.__setattr__(self,'minimum_mm',_point(self.minimum_mm))
        object.__setattr__(self,'maximum_mm',_point(self.maximum_mm))
        if any(lo>hi for lo,hi in zip(self.minimum_mm,self.maximum_mm)):
            raise WaveError('HEAD_AABB: limites mínimo/máximo invertidos.')


@dataclass(frozen=True)
class TCPRegistration:
    """Provenance of the TCP used to express every component's envelope."""
    source_frame: str
    tcp_in_source_frame_mm: tuple[float,float,float] | None
    method: str
    uncertainty_mm: float = 0.
    verified: bool = False

    def __post_init__(self):
        if self.tcp_in_source_frame_mm is not None:
            object.__setattr__(self,'tcp_in_source_frame_mm',_point(self.tcp_in_source_frame_mm))
        if (type(self.uncertainty_mm) not in (int,float)
                or not math.isfinite(self.uncertainty_mm) or self.uncertainty_mm<0):
            raise WaveError('HEAD_REGISTRATION: incerteza precisa ser finita e não negativa.')


@dataclass(frozen=True)
class HeadComponent:
    component_id: str
    kind: str
    bounds_relative_tcp_mm: AABB

    def __post_init__(self):
        if not self.component_id or not self.kind or not isinstance(self.bounds_relative_tcp_mm,AABB):
            raise WaveError('HEAD_COMPONENT: identificação, tipo e AABB relativos ao TCP são obrigatórios.')


@dataclass(frozen=True)
class HeadProfile:
    profile_id: str
    components: tuple[HeadComponent,...]
    tcp_registration: TCPRegistration | None = None
    units: str = 'mm'
    provenance: str = 'unmeasured'
    conservative_geometry_verified: bool = False

    def __post_init__(self):
        object.__setattr__(self,'components',tuple(self.components))
        if not all(isinstance(c,HeadComponent) for c in self.components):
            raise WaveError('HEAD_PROFILE: componente fora do contrato de envelope relativo ao TCP.')


@dataclass(frozen=True)
class TCPMotion:
    sequence: int
    start_mm: tuple[float,float,float]
    end_mm: tuple[float,float,float]
    kind: str = 'travel'
    motion_id: str = ''

    def __post_init__(self):
        if type(self.sequence) is not int or self.sequence<0:
            raise WaveError('HEAD_ORDER: sequência de movimento deve ser inteira e não negativa.')
        object.__setattr__(self,'start_mm',_point(self.start_mm))
        object.__setattr__(self,'end_mm',_point(self.end_mm))
        if self.kind not in {'travel','extrusion'}:
            raise WaveError('HEAD_MOTION: classifique o movimento como travel ou extrusion.')


@dataclass(frozen=True)
class MaterialDeposit:
    """A conservative material enclosure available AFTER ``sequence`` ends.

    A sequence of -1 denotes a pre-existing obstacle. Part, support, interface,
    skirt and any other supplied role are all checked, without role exclusions.
    Material created DURING the current extrusion is deliberately not claimed
    certified by these completed-deposit records.
    """
    sequence: int
    bounds_world_mm: AABB
    role: str = 'part'
    material_id: str = ''

    def __post_init__(self):
        if type(self.sequence) is not int or self.sequence<-1:
            raise WaveError('HEAD_ORDER: sequência de material deve ser inteira e pelo menos -1.')
        if not isinstance(self.bounds_world_mm,AABB) or not self.role:
            raise WaveError('HEAD_MATERIAL: envelope e função do material são obrigatórios.')


def segment_aabb_interval(start_mm,end_mm,box:AABB):
    """Analytic slab interval, rounded outwards to retain grazing contacts."""
    a,b=_point(start_mm),_point(end_mm)
    lo,hi=0.,1.
    for p,q,minimum,maximum in zip(a,b,box.minimum_mm,box.maximum_mm):
        delta=q-p
        if delta==0:
            if p<minimum or p>maximum:return None
            continue
        if not math.isfinite(delta):
            raise WaveError('HEAD_NUMERIC_RANGE: diferença de coordenadas fora da faixa numérica.')
        dlo,dhi=math.nextafter(delta,-math.inf),math.nextafter(delta,math.inf)
        if dlo<=0<=dhi:
            # An underflow-sized direction cannot safely narrow this slab.
            # Keeping the whole parameter interval is conservative.
            continue
        nlo,nhi=minimum-p,maximum-p
        if not math.isfinite(nlo) or not math.isfinite(nhi):
            raise WaveError('HEAD_NUMERIC_RANGE: limites relativos fora da faixa numérica.')
        nlo,nhi=math.nextafter(nlo,-math.inf),math.nextafter(nhi,math.inf)
        quotients=(nlo/dlo,nlo/dhi,nhi/dlo,nhi/dhi)
        enter=math.nextafter(min(quotients),-math.inf)
        leave=math.nextafter(max(quotients),math.inf)
        lo,hi=max(lo,enter),min(hi,leave)
        if lo>hi:return None
    return lo,hi


def _expanded_tcp_box(material,component,margin):
    m,c=material.bounds_world_mm,component.bounds_relative_tcp_mm
    def lower(a,b):
        return math.nextafter(math.nextafter(a-b,-math.inf)-margin,-math.inf)
    def upper(a,b):
        return math.nextafter(math.nextafter(a-b,math.inf)+margin,math.inf)
    return AABB(tuple(lower(a,b) for a,b in zip(m.minimum_mm,c.maximum_mm)),
                tuple(upper(a,b) for a,b in zip(m.maximum_mm,c.minimum_mm)))


def _profile_issues(profile):
    if profile is None:return ['MISSING_REAL_HEAD_PROFILE']
    issues=[]
    if not profile.profile_id:issues.append('MISSING_PROFILE_ID')
    if profile.units!='mm':issues.append('UNSUPPORTED_PROFILE_UNITS')
    if profile.provenance not in REAL_PROVENANCE:
        issues.append('SYNTHETIC_PROFILE' if profile.provenance=='synthetic_fixture' else 'UNVERIFIED_PROFILE_PROVENANCE')
    if profile.conservative_geometry_verified is not True:issues.append('UNVERIFIED_COMPONENT_ENCLOSURES')
    reg=profile.tcp_registration
    if not isinstance(reg,TCPRegistration) or reg.tcp_in_source_frame_mm is None:
        issues.append('MISSING_TCP_REGISTRATION')
    elif reg.verified is not True or not reg.source_frame or not reg.method:
        issues.append('UNVERIFIED_TCP_REGISTRATION')
    missing=REQUIRED_COMPONENTS-{c.kind for c in profile.components}
    if missing:issues.append('MISSING_REQUIRED_COMPONENTS:'+','.join(sorted(missing)))
    if len({c.component_id for c in profile.components})!=len(profile.components):
        issues.append('DUPLICATE_COMPONENT_ID')
    if any(any(lo==hi for lo,hi in zip(c.bounds_relative_tcp_mm.minimum_mm,c.bounds_relative_tcp_mm.maximum_mm))
           for c in profile.components):issues.append('DEGENERATE_COMPONENT_ENCLOSURE')
    return issues


def check_head_clearance(motions,material,profile:HeadProfile|None=None,*,
                         motions_complete=False,material_prefix_complete=False,
                         clearance_mm=0.,max_pair_checks=1_000_000,max_collision_records=100):
    """Audit completed material against the entire trajectory, including travel.

    ``sequence`` refers to the same ordered motion timeline in both inputs.
    Complete coverage must be declared explicitly by their producer. A synthetic
    profile can exercise the geometry algorithm but always returns global UNKNOWN.
    There is NO deliberate-nozzle-contact exclusion. Extrusion's developing bead
    contact remains UNCERTIFIED, even if completed prefix boxes are disjoint.
    """
    if (type(clearance_mm) not in (int,float) or not math.isfinite(clearance_mm) or clearance_mm<0
            or type(max_pair_checks) is not int or max_pair_checks<1
            or type(max_collision_records) is not int or max_collision_records<1):
        raise WaveError('HEAD_LIMITS: margem e limites de trabalho inválidos.')
    moves=tuple(motions);deposits=tuple(material)
    if not all(isinstance(m,TCPMotion) for m in moves) or not all(isinstance(d,MaterialDeposit) for d in deposits):
        raise WaveError('HEAD_INPUT: movimentos/material fora do contrato de auditoria.')
    if profile is not None and not isinstance(profile,HeadProfile):
        raise WaveError('HEAD_PROFILE: perfil fora do contrato.')
    reasons=_profile_issues(profile)
    coverage=[]
    if any(code.startswith(('MISSING_REQUIRED_COMPONENTS','DEGENERATE_COMPONENT_ENCLOSURE',
                            'UNVERIFIED_COMPONENT_ENCLOSURES')) for code in reasons):
        coverage.append('COMPONENT_GEOMETRY_COVERAGE_UNCONFIRMED')
    if motions_complete is not True:coverage.append('MOTION_COVERAGE_UNCONFIRMED')
    if material_prefix_complete is not True:coverage.append('MATERIAL_PREFIX_COVERAGE_UNCONFIRMED')
    if not moves:coverage.append('NO_MOTIONS_TO_AUDIT')
    sequences=[m.sequence for m in moves]
    if sequences!=sorted(set(sequences)):coverage.append('NONMONOTONIC_MOTION_TIMELINE')
    if any(math.dist(a.end_mm,b.start_mm)>1e-6 for a,b in zip(moves,moves[1:])):
        coverage.append('INCOMPLETE_MOTION_CHAIN')
    result={'status':'UNKNOWN','geometry_status':'UNKNOWN','reason_codes':[],
        'algorithm':'continuous TCP segment / Minkowski-expanded prefix-material AABB / exact slab interval',
        'profile_id':profile.profile_id if profile else None,
        'profile_sha256':fingerprint(asdict(profile)) if profile else None,
        'profile_provenance':profile.provenance if profile else None,
        'required_components':sorted(REQUIRED_COMPONENTS),
        'component_frame':'relative to TCP, fixed orientation','units':'mm',
        'motion_count':len(moves),'material_count':len(deposits),
        'material_roles':dict(Counter(d.role for d in deposits)),
        'checked_prefix_pairs':0,'potential_collision_count':0,'collisions':[],
        'collision_records_truncated':False,'coverage_complete':False,
        'current_deposition_contact_status':'UNCERTIFIED' if any(m.kind=='extrusion' for m in moves) else 'NOT_APPLICABLE',
        'clearance_margin_mm':float(clearance_mm),'registration_uncertainty_mm':None,
        'conservative_box_hits_are_exact_shape_collisions':False,
        'physical_validation':False,'print_allowed':False}
    # Unknown registration/units cannot be used as a geometric coordinate frame.
    unusable={'UNSUPPORTED_PROFILE_UNITS','MISSING_TCP_REGISTRATION','UNVERIFIED_TCP_REGISTRATION','DUPLICATE_COMPONENT_ID'}
    if profile is None or unusable.intersection(reasons) or 'NONMONOTONIC_MOTION_TIMELINE' in coverage:
        result['reason_codes']=reasons+coverage
        return result
    reg=profile.tcp_registration
    result['registration_uncertainty_mm']=reg.uncertainty_mm
    margin=clearance_mm+reg.uncertainty_mm
    ordered=sorted(deposits,key=lambda d:d.sequence)
    prefix=[];cursor=0;exhausted=False
    for move in moves:
        while cursor<len(ordered) and ordered[cursor].sequence<move.sequence:
            prefix.append(ordered[cursor]);cursor+=1
        for component in profile.components:
            for deposit in prefix:
                if result['checked_prefix_pairs']>=max_pair_checks:
                    exhausted=True;break
                result['checked_prefix_pairs']+=1
                interval=segment_aabb_interval(move.start_mm,move.end_mm,_expanded_tcp_box(deposit,component,margin))
                if interval is None:continue
                result['potential_collision_count']+=1
                if len(result['collisions'])<max_collision_records:
                    result['collisions'].append({
                        'motion_id':move.motion_id or str(move.sequence),'motion_sequence':move.sequence,
                        'motion_kind':move.kind,'component_id':component.component_id,'component_kind':component.kind,
                        'material_id':deposit.material_id or str(deposit.sequence),
                        'material_sequence':deposit.sequence,'material_role':deposit.role,
                        'tcp_segment_parameter_interval':list(interval),
                        'status':'POTENTIAL_COLLISION','nozzle_contact_ignored':False})
            if exhausted:break
        if exhausted:break
    if exhausted:coverage.append('RESOURCE_BUDGET_EXHAUSTED')
    if result['current_deposition_contact_status']=='UNCERTIFIED':
        coverage.append('CURRENT_DEPOSITION_NOZZLE_CONTACT_UNCERTIFIED')
    result['coverage_complete']=not coverage
    result['collision_records_truncated']=result['potential_collision_count']>len(result['collisions'])
    if result['potential_collision_count']:
        result['geometry_status']='POTENTIAL_COLLISION'
    elif coverage:result['geometry_status']='UNCERTIFIED'
    else:result['geometry_status']='PASS_DIGITAL'
    result['reason_codes']=reasons+coverage
    result['status']='UNKNOWN' if reasons else result['geometry_status']
    return result
