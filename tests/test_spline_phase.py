import math
import json
import unittest
import numpy as np
from scipy.interpolate import NdBSpline
from scipy.optimize import brentq
from orca_wave_studio.spline_phase import SplinePhase
from orca_wave_studio.surface_coordinates import SurfaceCoordinates
from orca_wave_studio.continuous_layers import LayerGridStage
from orca_wave_studio.regional_shell import RegionalShellSettings
from orca_wave_studio.conformal import process_conformal_gcode
from orca_wave_studio.contracts import WaveError


class SplinePhaseTests(unittest.TestCase):
    def test_cached_bounds_are_identical_at_knots_and_outside_domain(self):
        f=self.field();rng=np.random.default_rng(218)
        def legacy(points,domains,arrays,hessian=False):
            lo=np.min(points,axis=0);hi=np.max(points,axis=0);out=[]
            for values,(knots,degrees) in zip(arrays,domains):
                slices=tuple(slice(max(0,int(np.searchsorted(t,lo[k],side='right'))-degree-1),
                                   min(values.shape[k],int(np.searchsorted(t,hi[k],side='right'))))
                             for k,(t,degree) in enumerate(zip(knots,degrees)))
                region=values[slices]
                if hessian:out.append(float(abs(region).max()) if region.size else 0.)
                else:out.append((min(0.,float(region.min())),max(0.,float(region.max()))) if region.size else (0.,0.))
            return out
        boxes=list(rng.uniform(-5,16,(250,2,3)))
        for axis,knots in enumerate(f._support_knots):
            for value in knots:
                for edge in (np.nextafter(value,-np.inf),value,np.nextafter(value,np.inf)):
                    points=np.array([[3.,4.,5.],[3.2,4.2,5.2]])
                    points[:,axis]=edge;boxes.append(points)
        for points in boxes:
            h=legacy(points,list(f.hessian_domains.values()),list(f.hessian.values()),True)
            self.assertEqual(f.hessian_bounds(points),dict(zip(f.hessian,h)))
            d=legacy(points,f.first_domains,f.first)
            expected=(1+d[2][0],1+d[2][1],tuple(max(abs(a),abs(b)) for a,b in d[:2]))
            self.assertEqual(f.derivative_bounds(points),expected)
            self.assertEqual(f.derivative_bounds(points),expected)
        bounds=f.hessian_bounds(boxes[0]);bounds.clear()
        self.assertTrue(f.hessian_bounds(boxes[0]),'callers must not mutate cached certificates')
        self.assertGreater(f._derivative_query.cache_info().hits,len(boxes))

    def field(self):
        axes=[np.arange(0.,11.),np.arange(0.,11.),np.arange(-2.5,11.)]
        x,y,z=np.meshgrid(*axes,indexing='ij');coeff=.025*np.sin(x*.4)*np.cos(y*.3)*(z-.5)*(9-z)/10
        for k in range(3):
            for where in (slice(0,3),slice(-3,None)):
                index=[slice(None)]*3;index[k]=where;coeff[tuple(index)]=0.
        coeff[:,:,axes[2]<=1.5]=0.
        return SplinePhase(axes,coeff)

    def test_design_matrix_and_derivative_controls_match_evaluation(self):
        f=self.field();points=np.random.default_rng(23).uniform([1,1,.2],[9,9,8],(300,3))
        matrix=NdBSpline.design_matrix(points,f.knots,3);matrix.resize((len(points),math.prod(f.shape)))
        np.testing.assert_allclose(matrix@f.coefficients.ravel(),f.evaluate(points),atol=1e-12)
        z=1+f.evaluate(points,(0,0,1))
        self.assertGreaterEqual(z.min(),f.cmin-1e-12);self.assertLessEqual(z.max(),f.cmax+1e-12)
        for i in range(3):
            for j in range(i,3):
                derivative=[0,0,0];derivative[i]+=1;derivative[j]+=1
                self.assertLessEqual(abs(f.evaluate(points,derivative)).max(),abs(f.hessian[i,j]).max()+1e-12)

    def test_inverse_base_and_complete_triangle_certificate(self):
        f=self.field();rng=np.random.default_rng(24)
        for p in rng.uniform([1,1,0],[9,9,8],(100,3)):
            self.assertLess(math.dist(f.map_point(f.flatten_point(p)),p),2e-9)
        self.assertEqual(f.map_point((4,4,.24)),(4,4,.24))
        tri=np.array([[2.,2.,1.],[8.,3.,7.],[5.,8.,6.]])
        flat=f.flatten_points(tri);bound=f.phase_triangle_error(tri)/f.cmin
        for u in np.linspace(0,1,20):
            for v in np.linspace(0,1-u,20):
                weights=np.array([u,v,1-u-v]);p=weights@tri;q=weights@flat
                self.assertLessEqual(math.dist(f.map_point(q),p),bound+1e-8)

    def test_complete_chord_certificate_crosses_knots_and_identity_boundary(self):
        f=self.field()
        for a,b in [((2.,2.,.24),(8.,8.,8.)),((1.,5.,3.),(9.,5.,3.)),((4.,2.,4.),(4.,8.,5.))]:
            p,q=f.map_point(a),f.map_point(b);bound=f.chord_error_bound(a,b,p,q)
            for t in np.linspace(0,1,501):
                source=np.array(a)+t*(np.array(b)-a);line=np.array(p)+t*(np.array(q)-p)
                self.assertLessEqual(math.dist(f.map_point(source),line),bound+1e-8)

    def test_local_derivative_bounds_cover_knots_and_zero_extension(self):
        f=self.field();rng=np.random.default_rng(35)
        for origin in [(1.,1.,.5),(3.,4.,4.5),(8.75,8.75,8.75),(-1.,5.,5.)]:
            lo=np.asarray(origin);hi=lo+np.array([.25,.5,.75])
            points=np.vstack((lo,hi,rng.uniform(lo,hi,(400,3))))
            minimum,maximum,xy=f.derivative_bounds((lo,hi))
            dz=1+f.evaluate(points,(0,0,1))
            self.assertGreaterEqual(dz.min(),minimum-1e-12)
            self.assertLessEqual(dz.max(),maximum+1e-12)
            h=f.hessian_bounds((lo,hi))
            for i in range(3):
                nu=[0,0,0];nu[i]=1
                if i<2:self.assertLessEqual(abs(f.evaluate(points,nu)).max(),xy[i]+1e-12)
                for j in range(i,3):
                    nu=[0,0,0];nu[i]+=1;nu[j]+=1
                    self.assertLessEqual(abs(f.evaluate(points,nu)).max(),h[i,j]+1e-12)

    def test_numerical_coordinates_and_short_edges_have_json_safe_report(self):
        warp=SurfaceCoordinates();warp.grid=self.field();warp.layer_grid=LayerGridStage([.5,9.],[.5,9.])
        warp.anchor_z=.5;warp.settings=RegionalShellSettings(retain_native_short_edges=True)
        point=warp.map_point(np.array([4.,4.,3.]))
        self.assertTrue(all(type(v) is float for v in point))
        lines=['G90','M83','G0 X4 Y4 Z0.24 F1200']
        for z in (.24,.44,3.,3.2):
            lines+=[';LAYER_CHANGE',f';Z:{z}',';HEIGHT:0.2','; printing object P id:0 copy 0',
                ';TYPE:Outer wall',';WIDTH:0.42',f'G0 X4 Y4 Z{z}','G1 X4.1 E0.01',
                '; stop printing object P id:0 copy 0']
        result=process_conformal_gcode(('\n'.join(lines)+'\n').encode(),warp,{0:'part'},'part')
        self.assertGreater(result.report['short_native_edges']['deposition'],0)
        json.dumps(result.report,allow_nan=False)
        warp.prepare_layer=None;warp.grid._prepared_points={};warp.grid._prepared_differentials={}
        control=process_conformal_gcode(('\n'.join(lines)+'\n').encode(),warp,{0:'part'},'part')
        self.assertEqual(result.gcode,control.gcode)

    def test_shifted_control_grid_cannot_claim_a_flat_base_above_its_support(self):
        axes=[np.arange(-4.,12.,2),np.arange(-4.,12.,2),np.arange(-3.75,12.,2)]
        coefficients=np.zeros(tuple(len(a) for a in axes));coefficients[3,3,4]=.1
        # The nonzero control's support starts at z=0.25. Checking only control
        # centers would wrongly allow the declaration anchor=0.5.
        with self.assertRaisesRegex(WaveError,'SPLINE_BASE'):
            SplinePhase(axes,coefficients,anchor=.5)

    def test_batch_inverse_matches_scalar_and_preserves_outside_base(self):
        f=self.field();points=np.random.default_rng(49).uniform([-2.,-2.,-.1],[12.,12.,12.],(500,3))
        points=np.vstack((points,[4.,4.,.24],[4.,4.,.5]))
        np.testing.assert_allclose(f.map_points(points),[f.map_point(p) for p in points],atol=2e-9,rtol=0.)

    def test_benchy_inverse_stall_converges_without_relaxing_residual(self):
        # Reduced vertical section of the native Benchy failure (logical layer
        # 76). Positive derivative bounds still allowed Newton to oscillate
        # inside its bracket for more than the previous 40-iteration limit.
        line=np.array([0.,0.,0.,0.,-.9197208832642783,2.9441539216509023,
            6.1514008214413485,4.4665241195462615,2.8781713271418154,
            1.9420191951239243,1.3548896629110891,.9751274502588885,
            .7249343990323606,.5562649194873959,.43707596689502864,
            .34564357681782426,.2684908489575099,.1983440327053416,
            .13140156553939292,.06559825184768547,0.,0.,0.])
        axes=[np.arange(13.),np.arange(13.),np.arange(-5.5,60.6,3.)]
        coefficients=np.zeros((13,13,len(line)));coefficients[3:-3,3:-3,:]=line
        f=SplinePhase(axes,coefficients);self.assertGreater(f.cmin,.45)
        points=np.array([[6.,6.,15.404204040573156+d] for d in (-.001,0.,.001)])
        unchanged=points.copy()
        expected=[brentq(lambda z:z+f.evaluate(np.array([[p[0],p[1],z]]))[0]-p[2],
                         *f.domain[2],xtol=1e-13) for p in points]
        for mapped in (f.map_points(points),np.array([f.map_point(p) for p in points])):
            np.testing.assert_array_equal(mapped[:,:2],points[:,:2])
            np.testing.assert_allclose(mapped[:,2],expected,atol=2e-9,rtol=0.)
            self.assertLess(abs(f.flatten_points(mapped)[:,2]-points[:,2]).max(),1e-9)
        f.prepare_points(points)
        np.testing.assert_allclose([f.map_point(p)[2] for p in points],expected,atol=2e-9,rtol=0.)
        np.testing.assert_array_equal(points,unchanged)


if __name__=='__main__':unittest.main()
