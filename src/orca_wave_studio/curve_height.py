"""Peak-to-valley Z of deposited polylines per logical layer; no head model."""
import math
from .contracts import WaveError
from .regional_shell import RegionalShellSettings


def audit_curve_height(points,layers,limit):
    RegionalShellSettings(max_curve_height_mm=limit)
    if len(points)!=len(layers):raise WaveError('CURVE_HEIGHT: trajetória incompleta para conferir a altura.')
    bounds={}
    for point,layer in zip(points,layers):
        z=point[2]
        if not math.isfinite(z):raise WaveError('CURVE_HEIGHT: trajetória com altura inválida.')
        lo,hi=bounds.get(layer,(z,z));bounds[layer]=(min(lo,z),max(hi,z))
    layer,span=max(((k,hi-lo) for k,(lo,hi) in bounds.items()),key=lambda p:p[1],default=(None,0.))
    if limit is not None and span>limit+1e-7:
        raise WaveError('CURVE_HEIGHT: a camada '+str(layer)+' exige '+f'{span:.3f} mm, acima do limite de {limit:g} mm. '
                        'Ajuste a altura no passo 1 ou selecione outra região; o original foi preservado.')
    return {'limit_mm':limit,'maximum_deposited_layer_span_mm':span,'maximum_layer':layer,
            'logical_layers_checked':len(bounds),'scope':'all deposited polyline endpoints per logical layer',
            'head_clearance_verified':False}
