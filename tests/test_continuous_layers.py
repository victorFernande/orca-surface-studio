import math
import unittest

import numpy as np

from orca_wave_studio.continuous_layers import HeightField,SurfaceStage,LayerGridStage,ContinuousLayerWarp,_normal_certificate
from orca_wave_studio.regional_shell import RegionalShellSettings


def field():
    pts=[(x,y,10+.08*x+.002*x*x) for x in np.linspace(0,10,12) for y in (0.,10.)]
    return HeightField(pts,np.ones(len(pts)))


class ContinuousLayerTests(unittest.TestCase):
    def test_clipped_mesh_cannot_bypass_the_output_face_budget(self):
        from orca_wave_studio.bending import _refine
        from orca_wave_studio.contracts import WaveError
        points=[(0.,0.,0.),(1.,0.,0.),(0.,1.,0.),(0.,0.,1.)]
        faces=[(0,2,1),(0,1,3),(1,2,3),(2,0,3)]
        with self.assertRaisesRegex(WaveError,'BEND_COMPLEXITY'):
            _refine(list(points),faces,list(points),lambda tri:0.,.02,max_faces=3)

    def test_grid_reparametrization_preserves_order_base_top_and_chord_bound(self):
        stage=LayerGridStage([.5,6.48,12.36,19.56,48.,49.],[.5,6.5,12.4,19.6,48.,49.])
        for z in np.linspace(0,50,501):
            p=(3.,4.,float(z))
            self.assertLess(math.dist(stage.map_point(stage.flatten_point(p)),p),1e-10)
            self.assertGreater(stage.local_scale(*p),0)
        self.assertEqual(stage.map_point((3,4,.24)),(3,4,.24))
        self.assertEqual(stage.map_point((3,4,48.)),(3,4,48.))
        a=(1.,2.,5.);b=(5.,7.,20.);pa,pb=stage.map_point(a),stage.map_point(b)
        bound=stage.chord_error_bound(a,b,pa,pb)
        for t in np.linspace(0,1,501):
            p=tuple(x+t*(y-x) for x,y in zip(a,b));q=tuple(x+t*(y-x) for x,y in zip(pa,pb))
            self.assertLessEqual(math.dist(stage.map_point(p),q),bound+1e-10)

    def test_redundant_grid_knots_do_not_split_the_same_affine_interval(self):
        stage=LayerGridStage([0.,2.,3.,4.,6.],[0.,2.1,3.1,4.1,6.])
        self.assertEqual(stage.flat,(0.,2.,4.,6.))
        for z in np.linspace(2,4,101):self.assertAlmostEqual(stage.map_point((1,1,z))[2],z+.1,places=12)

    def test_reference_is_continuous_and_invertible_with_positive_spacing(self):
        s=SurfaceStage(field(),2.,18.)
        for x in np.linspace(-2,12,21):
            self.assertAlmostEqual(s.map_point((x,5,s.reference))[2],s.field.height(x,5),places=9)
            for z in np.linspace(0,20,41):
                p=(float(x),5.,float(z));self.assertLess(math.dist(s.map_point(s.flatten_point(p)),p),1e-9)
                j=s.local_scale(*p)
                self.assertGreaterEqual(j,s.jmin-1e-9);self.assertLessEqual(j,s.jmax+1e-9)
        for z in (s.anchor,s.cap):
            self.assertEqual(s.map_point((5,5,z)),(5,5,z))
        left=s.local_scale(5,5,s.reference-1e-7);right=s.local_scale(5,5,s.reference+1e-7)
        self.assertAlmostEqual(left,right,places=6)

    def test_short_extrusion_crossing_transition_has_no_vertical_tangent_jump(self):
        stage=SurfaceStage(field(),2.,18.)
        for level in (stage.anchor,stage.cap):
            self.assertAlmostEqual(stage.local_scale(11,4,level-1e-7),1.,places=6)
            self.assertAlmostEqual(stage.local_scale(11,4,level+1e-7),1.,places=6)
            a=(11.,4.,level-.01);b=(11.064,4.013,level+.015)
            bound=stage.chord_error_bound(a,b,stage.map_point(a),stage.map_point(b))
            self.assertLess(bound,.0001)

    def test_height_field_has_continuous_gradient_at_lateral_shoulders(self):
        h=field()
        for x in h.cuts(0):
            self.assertLess(math.dist(h.gradient(x-1e-7,5),h.gradient(x+1e-7,5)),1e-6)

    def test_short_chord_certificates_cover_lateral_and_vertical_joins(self):
        s=SurfaceStage(field(),2.,18.)
        for x in s.field.cuts(0):
            for z in (s.anchor,s.reference,s.cap):
                a=(x-.035,5.,z-.02);b=(x+.035,5.01,z+.02)
                pa=tuple(round(v,6) for v in s.map_point(a));pb=tuple(round(v,6) for v in s.map_point(b))
                bound=s.chord_error_bound(a,b,pa,pb)
                for t in np.linspace(0,1,101):
                    q=tuple(u+t*(v-u) for u,v in zip(a,b));line=tuple(u+t*(v-u) for u,v in zip(pa,pb))
                    self.assertLessEqual(math.dist(s.map_point(q),line),bound+1e-9)

    def test_local_jacobian_certificate_covers_the_entire_error_tube(self):
        s=SurfaceStage(field(),2.,18.);rng=np.random.default_rng(124)
        for _ in range(50):
            a=tuple(rng.uniform((-2,-2,0),(12,12,20)));b=tuple(rng.uniform((-2,-2,0),(12,12,20)))
            bound=s.vertical_lipschitz((a,b),.02)
            for t in np.linspace(0,1,31):
                p=tuple(x+t*(y-x) for x,y in zip(a,b))
                for dz in (-.02,0,.02):self.assertLessEqual(s.local_scale(p[0],p[1],p[2]+dz),bound+1e-8)
        self.assertEqual(s.vertical_lipschitz(((1,1,0),(2,2,1)),.02),1.)

    def test_bivariate_curvature_is_bounded_across_lateral_shoulders(self):
        points=[(x,y,10+.1*x+.04*y+.003*x*x+.002*x*y-.001*y*y)
                for x in np.linspace(0,10,9) for y in np.linspace(0,10,9)]
        h=HeightField(points,np.ones(len(points)),extension_mm=1.6);s=SurfaceStage(h,1.,20.)
        for tri in (((-.5,-.2,4.),(.7,-.1,8.),(.3,.5,12.)),
                    ((9.8,9.7,8.),(10.5,9.9,13.),(10.2,10.6,18.))):
            bound=s.mapped_triangle_error(tri);mapped=[s.map_point(p) for p in tri]
            for u in np.linspace(0,1,20):
                for v in np.linspace(0,1-u,20):
                    weights=(u,v,1-u-v)
                    p=tuple(sum(weights[i]*tri[i][k] for i in range(3)) for k in range(3))
                    q=tuple(sum(weights[i]*mapped[i][k] for i in range(3)) for k in range(3))
                    self.assertLessEqual(math.dist(s.map_point(p),q),bound+1e-8)
        a=(-.4,-.3,2.);b=(10.8,10.9,19.);pa,pb=s.map_point(a),s.map_point(b)
        bound=s.chord_error_bound(a,b,pa,pb)
        for t in np.linspace(0,1,501):
            p=tuple(x+t*(y-x) for x,y in zip(a,b));q=tuple(x+t*(y-x) for x,y in zip(pa,pb))
            self.assertLessEqual(math.dist(s.map_point(p),q),bound+1e-8)

    def test_chord_certificate_includes_clamps_and_all_vertical_branches(self):
        s=SurfaceStage(field(),2.,18.)
        for a,b in (((-2.,3.,1.),(12.,7.,19.)),((1.,1.,s.reference),(9.,9.,s.reference)),
                    ((5.,2.,5.),(11.,8.,15.))):
            pa,pb=s.map_point(a),s.map_point(b);bound=s.chord_error_bound(a,b,pa,pb)
            for t in np.linspace(0,1,201):
                p=tuple(x+t*(y-x) for x,y in zip(a,b));line=tuple(x+t*(y-x) for x,y in zip(pa,pb))
                self.assertLessEqual(math.dist(s.map_point(p),line),bound+1e-8)

    def test_triangle_certificate_covers_the_whole_face_not_only_vertices(self):
        s=SurfaceStage(field(),2.,18.)
        for tri in (((1.,1.,5.),(9.,1.,13.),(4.,9.,15.)),((1.,1.,9.),(9.,1.,12.),(4.,9.,11.))):
            bound=s.triangle_error(tri);flat=[s.flatten_point(p) for p in tri]
            for u in np.linspace(0,1,15):
                for v in np.linspace(0,1-u,15):
                    w=(u,v,1-u-v)
                    q=tuple(sum(w[i]*flat[i][k] for i in range(3)) for k in range(3))
                    original=tuple(sum(w[i]*tri[i][k] for i in range(3)) for k in range(3))
                    self.assertLessEqual(math.dist(s.map_point(q),original),bound+1e-8)

    def test_same_geometry_with_hole_uses_surface_coordinates_without_native_contouring(self):
        from test_bending import roof_with_hole,euler
        original=roof_with_hole();before=original.to_dict()
        warp=ContinuousLayerWarp(original,'1',RegionalShellSettings(retain_native_short_edges=True))
        self.assertEqual(before,original.to_dict())
        self.assertEqual(euler(warp.flattened_snapshot.objects[0]),euler(original.objects[0]))
        self.assertTrue(warp.summary['positive_jacobian'])
        self.assertTrue(all(r['core_in_one_native_band'] for r in warp.summary['reference_alignment']))
        self.assertLessEqual(warp.summary['mesh_normal_and_crease_error_budget_mm'],.02)
        for p in warp.original_world_vertices:
            self.assertLess(math.dist(warp.map_point(warp.flatten_point(p)),p),1e-8)
        self.assertEqual(warp.map_point((100,100,.2)),(100,100,.2))
        from orca_wave_studio.geometry import transform_point
        obj=warp.flattened_snapshot.objects[0];volume=obj['volumes'][0];instance=obj['instances_data'][0]
        for flat,reference in list(zip(volume['vertices'],warp.reference_world_vertices))[:warp.exact_vertex_count]:
            point=transform_point(flat,instance['matrix'],volume['matrix'])
            self.assertLess(math.dist(warp.map_point(point),reference),1e-8)

    def test_grid_cells_restore_complete_clipped_triangles_exactly(self):
        from orca_wave_studio.bending import _clip
        stage=LayerGridStage([0.,2.,4.,6.],[0.,2.1,3.9,6.])
        points=[(0.,0.,0.),(4.,0.,0.),(0.,4.,0.),(0.,0.,6.)]
        vertices=list(points);world=list(points);faces=[(0,2,1),(0,1,3),(1,2,3),(2,0,3)]
        for k,z in stage.clipping_planes():faces=_clip(vertices,faces,world,[0.,0.,1.,-z])
        flat=[stage.flatten_point(p) for p in world]
        for tri in faces:
            for weights in ((1/3,1/3,1/3),(.1,.2,.7),(.7,.2,.1)):
                p=tuple(sum(w*flat[i][k] for w,i in zip(weights,tri)) for k in range(3))
                q=tuple(sum(w*world[i][k] for w,i in zip(weights,tri)) for k in range(3))
                self.assertLess(math.dist(stage.map_point(p),q),1e-12)

    def test_composed_path_bound_and_material_jacobian(self):
        w=ContinuousLayerWarp.__new__(ContinuousLayerWarp)
        w.stages=[SurfaceStage(field(),1.,19.),SurfaceStage(field(),2.,18.)];w.anchor_z=1.
        a=(-1.,2.,.5);b=(11.,8.,19.5);pa,pb=w.map_point(a),w.map_point(b)
        bound=w.chord_error_bound(a,b,pa,pb)
        for t in np.linspace(0,1,301):
            p=tuple(x+t*(y-x) for x,y in zip(a,b));line=tuple(x+t*(y-x) for x,y in zip(pa,pb))
            self.assertLessEqual(math.dist(w.map_point(p),line),bound+1e-8)
        for z in np.linspace(3,17,21):
            p=(5.,5.,float(z));eps=1e-5
            numerical=(w.map_point((5,5,z+eps))[2]-w.map_point((5,5,z-eps))[2])/(2*eps)
            self.assertAlmostEqual(w.local_scale(*p),numerical,places=5)
            gx=(w.map_point((5+eps,5,z))[2]-w.map_point((5-eps,5,z))[2])/(2*eps)
            self.assertAlmostEqual(w.gradient(*p)[0],gx,places=5)
            self.assertGreater(w.volume_scale(*p,.12),0)
            self.assertGreater(w.normal_gap(*p,.12),0)

    def test_vertical_face_remains_the_same_plane_despite_reparametrization(self):
        s=SurfaceStage(field(),2.,18.)
        face=((0.,0.,4.),(0.,10.,4.),(0.,0.,16.))
        self.assertEqual(s.triangle_normal_error(face),0.)
        flat=[s.flatten_point(p) for p in face]
        for t in np.linspace(0,1,101):
            p=tuple(x+t*(y-x) for x,y in zip(flat[0],flat[2]))
            self.assertEqual(s.map_point(p)[0],0.)

    def test_active_first_layer_is_not_assumed_to_be_sv06_height(self):
        from test_bending import roof_with_hole
        warp=ContinuousLayerWarp(roof_with_hole(),'1',initial_layer_mm=1.2)
        for z in (.24,.8,1.2):
            self.assertEqual(warp.map_point((103.,105.,z)),(103.,105.,z))

    def test_batch_certificate_matches_scalar_across_branches_and_grid_knots(self):
        from orca_wave_studio.continuous_certificates import original_face_bounds
        stages=(SurfaceStage(field(),1.,19.),SurfaceStage(field(),2.,18.),
                LayerGridStage([.5,6.48,12.36,19.56,21.],[.5,6.5,12.4,19.6,21.]))
        rng=np.random.default_rng(932)
        flat=rng.uniform((-2.,-2.,0.),(12.,12.,22.),(200,3,3))
        original=rng.uniform((-2.,-2.,0.),(12.,12.,22.),(200,3,3))
        expected=[_normal_certificate(stages,list(t),list(r)) for t,r in zip(flat,original)]
        np.testing.assert_allclose(original_face_bounds(stages,flat,original),expected,rtol=1e-12,atol=2e-10)

    def test_composed_mesh_certificate_is_against_the_original_face(self):
        stages=(SurfaceStage(field(),1.,19.),SurfaceStage(field(),2.,18.))
        w=ContinuousLayerWarp.__new__(ContinuousLayerWarp);w.stages=stages
        flat=((1.,1.,.5),(9.,1.,14.),(4.,9.,19.5));original=[w.map_point(p) for p in flat]
        bound=_normal_certificate(stages,flat,original)
        n=np.cross(np.subtract(original[1],original[0]),np.subtract(original[2],original[0]));n/=np.linalg.norm(n)
        for u in np.linspace(0,1,25):
            for v in np.linspace(0,1-u,25):
                weights=(u,v,1-u-v)
                p=tuple(sum(weights[i]*flat[i][k] for i in range(3)) for k in range(3))
                distance=abs(float(np.dot(n,np.subtract(w.map_point(p),original[0]))))
                self.assertLessEqual(distance,bound+1e-8)
