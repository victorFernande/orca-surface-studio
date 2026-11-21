# ADR-0014 — Whole-object selection does not certify surface continuity

Status: Scope correction implemented in 0.10.1; complete stair removal remains unmet.

The guided UI hid the existing whole-object option. The previous native test
selected two radius-8 spheres, leaving the roof and other edges untreated.
Expose Choose on model / Whole object in step 2 and preserve the choice when
returning from advanced options. Keep the four-step workflow and invalidate
results whenever scope changes. Whole-object speeds follow the active profile;
the 80% modifier speed applies only to painted regions.

Explicitly enable native contouring at both object and normal-part levels in
the copied whole-object project, overriding local disabled settings only in
that copy. Verify those values after native slicing, including local minimum
Z and the disabled aggressive perimeter-height correction. Reject lost settings.

Count actual nominal-Z offsets separately from within-segment Z variation. A
horizontal path translated in Z is not proof of continuous surface following.
Never present either count as a percentage of smooth area. Keep continuity
certification and physical release false.

The native GUI test increased varying-Z extrusion segments from 166 to 2,260
and reduced maximum slope from 26.12 to 25.79 degrees. Whole-object fine layers
also include the roof. The original world mesh and native XYZ/E are preserved.
Nevertheless, the Preview still shows residual stairs. This is partial progress
on the user's request, not a complete surface-finishing solution.

The pinned ContourZ implementation only adjusts within a layer-height window,
returns points outside it to nominal Z, and suppresses upward perimeter offsets.
Eliminating that boundary requires a different layer/path planner with renewed
deposition and transition validation, rather than another reduction in layer
height or feed. The existing roof inverse-map backend rejects already contoured
G-code; its guard remains intact. No unvalidated composition or Orca fork was
introduced. See the native evidence in PECA_INTEIRA_V0101.md.
