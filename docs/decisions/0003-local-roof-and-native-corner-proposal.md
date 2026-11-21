# ADR-0003 — Local roofs below taller details

Status: Implemented; user accepted the native-short-edge exception for the
digital Preview test on 2026-11-20. Physical printing remains blocked.

## Context

The installed global cap uses maximum model height minus 1.2 mm. On Benchy,
this selects the chimney and misses the requested curved roof. The original
3MF also contains zero-area facets and exact duplicate coordinates. The
native sliced roof contains small corner edges that cannot all meet the
planned 0.15 mm minimum under a 0.02 mm chord error certificate.

## Decision

Normalize a private copy without moving vertices or filling finite-area holes.
Split collinear T junctions and retain strict closed-manifold validation.
Choose the highest substantial connected curved upward region below taller
details; preserve the existing global-cap pilot otherwise. Refine conformingly
on the original surface. Fix shared boundaries, cavity ceilings and projected
taller details, keep a planar collar, then recompute geodesic distance from
that whole collar before applying a smooth lift. Keep all math bound to the
source revision and include geometry/normalization/refinement in the report.

Use the native preview profile with narrow solid infill kept rectilinear;
preserve the backup profile and disable physical transport. Travel is not
subject to the deposition minimum and may use finer steps to meet the same
chord tolerance. Short deposition chains can be joined only when every native
edge/corner is certified and each edge's material contribution is retained.

Keep strict minimum enforcement as the product default. Provide an explicit
comparison flag and an unchecked native UI option to retain original short edges with original XY,
mapped Z and integrated cell-volume extrusion. Do not subdivide these short
edges. Refuse if the chord certificate fails. Record their changed count and
minimum separately from newly subdivided deposition. This exception requires
the user's acceptance; this was explicitly given for the Preview experiment.

## Evidence and limits

The strict Benchy experiment rejects at line 114878. The explicit proposal
generates 1,567 nonplanar top-surface extrusion moves and changes 57 inherited
short corners. The minimum recreated segment is 0.155944 mm and maximum
certified error is 0.0198794 mm. The chimney's deposition Z and total extrusion
remain unchanged. G-code and packaged payload have identical SHA-256.
See TESTE_BENCHY.md and its file-audit.json for reproduction and exact values.

With renewed mouse/keyboard consent, the package opened in native Preview.
On native layer 201, nominal 40.2 mm, positive-E top-surface moves showed the
nozzle marker descending 39.623 to 39.607 mm and rising to 39.610 mm. Generated,
packaged and native-cache payload hashes match. No Print action was used.

Version 0.4.1 is installed on disk with activation state preserved. The open
Orca instance still runs 0.4.0; the new native preparation/capture/generation
button flow remains pending a restart and explicit validation. Unit tests
and isolated WebView component checks do not replace that experiment.
Physical clearance, actual deposition and arbitrary-model compatibility
remain unvalidated.
