# ADR-0011 — Screen-ray selection and native regional wall contouring

Status: Implemented and native GUI Preview validated in 0.8.0; physical qualification pending.

The user chooses the walls to smooth by clicking the model. A simplified display
mesh cannot define manufacturing geometry. Store an orthographic camera ray,
radius and source revision; intersect the original transformed mesh in the build
worker. Reject misses, stale revisions, malformed rays and ambiguous instances.
Limit the first version to 24 spherical areas, radii 1–15 mm, one solid object
and one instance. A sphere includes wall thickness and can reach nearby walls;
the interface describes this. Source geometry is never replaced by the display.

Use closed native parameter-modifier meshes inside the private 3MF copy. The
normal part disables ZAA, selected modifiers enable it. Preserve the global
active profile and verify the native exported per-part configuration. Recompute
all paths and extrusion in Orca rather than splicing independent G-codes or
changing E according to 3D length alone. XYZ/E after native slicing stay intact;
the existing limiter only lowers feed. Region slicing can change path order and
internal paths; it does not promise byte-identical unselected planar G-code.

In the tested Orca source, `Layer::is_perimeter_compatible` omits ZAA fields.
Regions differing only in ZAA were merged into the first compatible region,
and the experiment returned zero contoured segments. Selected areas therefore
explicitly use 80% of the resolved outer/inner wall speeds. These are meaningful
local quality overrides, disclosed in the interface, and also keep those native
regions separate. Do not use an inactive setting as an undisclosed grouping hack.
Verify these overrides in the native exported package. Source inspection:
[Layer.cpp](https://github.com/OrcaSlicer/OrcaSlicer/blob/eef7710cb102fdb51a9bcdbd9efd61047f44774a/src/libslic3r/Layer.cpp).

Lower the perimeter-height minimization threshold from 35° to 1° so shallow
inclines receive the native bead-edge adjustment. This is not a maximum head
clearance angle. The CLI must pass this value explicitly; testing showed that
the project setting alone was replaced by 35°. The exact process declaration
changes with the command; user authorization remains host-owned.

Audit actual output, not just saved metadata: every selected area needs an
effect, and every adjusted extrusion endpoint must lie inside the chosen union
plus a bead-width margin. Reject native scope leakage or a selection with no
compatible contour. Maximum motion slope is reported separately; exceeding the
study limit sets an explicit physical gate, even when speed and body checks pass.

The Benchy test produced 1,143 nonplanar extrusion segments in two selected areas
and no out-of-scope adjusted endpoints under that check. However, its maximum
motion slope was approximately 63.08°. Nominal body clearance stayed positive,
but this does not qualify the nozzle or deposition through those transitions.
The candidate retains `print_allowed=false`. No native fork or print was made.

The authorized native GUI test selected bow/stern areas by click, generated the
result and verified identical generated/package/cache contents after restarts.
It produced 1,353 nonplanar extrusion segments, maximum motion slope 62.80°,
and no scope leakage under the bead-margin endpoint check. A native bridge
serialization issue reordered nested ray keys; comparison now canonicalizes
dictionary keys without reordering arrays or ignoring coordinate changes.
The headless UI regression explicitly reproduces that key reordering. The
final native Studio showed current paths, metrics, the Preview button and the
physical-gate warning. The nominal body bound was +1.24 mm; nozzle contact
and deposition remain unqualified. See the separate CLI/GUI evidence records.
