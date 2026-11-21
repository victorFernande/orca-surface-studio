# ADR-0013 — Native finishing bands and an enforced extrusion slope limit

Status: Implemented in 0.10.0; native GUI validation is recorded in the release report.

The 0.9.1 Benchy produced 63.36° extrusion segments. Source inspection found
that native ContourZ samples at 0.1 mm, applies a discontinuous eligibility
window and optionally lowers perimeter height by a normal-dependent half-width
term. Forcing the minimization angle to 1° activates that aggressive correction
almost everywhere. It is a deposition setting, not a head-clearance limit.
[Native implementation](https://github.com/OrcaSlicer/OrcaSlicer/blob/eef7710cb102fdb51a9bcdbd9efd61047f44774a/src/libslic3r/ContourZ.cpp).

Disable that optional perimeter lowering (angle 0), retain native raycast
contouring and let Orca slice finer height bands. Aim for one third of the
nominal height, bounded by the active nozzle/profile minimum and maximum;
round upward to 0.001 mm. A missing minimum falls back to 20% of the active
nozzle diameter. For the tested SV06 this resolves to 0.07 mm rather than
0.20 mm. Use the midpoint of that fine height as the local minimum Z value,
balancing native upward/downward adjustment. No brand-specific values or
custom XYZ/E rewriting are introduced.

The original world mesh is copied unchanged. Native layer_config_ranges refine
whole cross-sections in the selected height bands, with one nominal-layer
padding at either end. Fine layers therefore also affect unpainted walls at
those heights; Z contouring remains restricted to selected spheres. Preserve
the first layer, global machine/material/process values, start/end macros and
source project. The original project and nominal profile stay available.
The native model format is implemented in
[bbs_3mf.cpp](https://github.com/OrcaSlicer/OrcaSlicer/blob/eef7710cb102fdb51a9bcdbd9efd61047f44774a/src/libslic3r/Format/bbs_3mf.cpp).

Verify the ranges exported by Orca and actual nominal Z differences in the
emitted G-code. Feature HEIGHT metadata can describe bridge bead diameter;
it must not be mistaken for nominal layer spacing. Check the first layer and
all selected-object extrusion moves, including short native edges. If the
actual maximum slope exceeds the chosen limit, reject generation before writing
a final result or scheduling Preview. Slowing feed alone is not a slope fix.
The limit is an extrusion-motion constraint, not a claim about head collision.
Travel lifts are intentionally not treated as surface extrusion.

Native slicing owns extrusion, wall order, infill, bridges, retractions and
layer transitions. Post-processing still only limits feed and removes stale
statistics. The generated/package/cache hash checks remain. Geometry remains
an input invariant, while finer sampling and a lower measured slope are
output evidence, not a physical print certificate or a promise of zero stairs.

The existing four steps stay unchanged. The result summary discloses the
finishing height and collapsed details show the vertical sampling reduction.
This costs additional layers and print time. Existing physical gates remain;
no print is automatically started.
