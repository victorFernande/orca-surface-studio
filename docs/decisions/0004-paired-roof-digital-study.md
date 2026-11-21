# ADR-0004 — Paired roof skins and separate approval gates

Status: Implemented for the digital study; full Benchy and physical printing
remain unapproved. Supersedes ADR-0003 as the default **Superfície curva**
preparation in the Studio UI. The old top-only engine remains an explicit
compatibility backend, not an automatic fallback.

## Context

The Benchy roof's underside/overhang remains stepped when only the top skin is
warped and an unchanged collar is retained. Sinusoidal toolpath design,
projection of an upper shell, and inverse mapping of an entire object solve
different problems. Native Orca Z Contouring already changes both Z and E; it
must not be processed by the inverse-map engine a second time.

The user approved a digital study with original geometry, a vertical nozzle,
angles relative to the horizontal bed, paired top/underside/border, ordinary
removable supports, and an all-selected-regions acceptance rule. Nominal setup:
stock SV06, 0.4 mm nozzle, PETG, 0.20 mm layers. GUI control requires a separate
user authorization. No physical print is authorized in this study.

## Decision

Compare three distinct paths: native planar, native ZAA, and a planar proxy
with paired-skin inverse mapping. ZAA is disabled in the proxy settings and
rejected by the processor if enabled in captured metadata.

The first paired transform accepts only rectangular parallel planar skins and
compatible vertical connecting walls. It fixes the base, flattens both skins
and maps the complete selected object's labelled paths, including its supports
and connecting travels. It uses a continuous XY-clamped extension, positive
vertical Jacobian, exact layer-cell averaged Jacobian for E, and an analytic
piecewise-quadratic chord bound. No collar, angular fade, or STL deformation is
accepted as a substitute for the original roof.

The Studio automatically proposes a plane candidate. A top-view map and list
allow correcting that reference. Candidates are revision-bound; the processor
still validates the complete paired shell and refuses holes, interior cuts or
unproven transitions. Selecting a region never approves printability.

Evaluate three independent gates:

1. File/transform integrity: native version/configuration, labels, positive J,
   continuous path generation, chord limits, source preservation and hashes.
2. Deposited-surface estimate: separate top/underside/border and support
   measurements. The swept horizontal-disk model is explicitly uncalibrated;
   samples can identify model counterexamples but cannot certify a 0.05 mm
   maximum over an entire face. Ideal mesh gaps and deposited-material gaps
   are separate quantities.
3. Head clearance: registered TCP-relative conservative component envelopes
   and the temporal material prefix. Continuous segment/slab intersections
   include support and travel. Missing real geometry is UNKNOWN. Synthetic
   inputs validate the checker only. Growing-bead contact is UNCERTIFIED,
   without a blanket nozzle-contact exception.

Every regional result has `digital_approval=false`, `print_allowed=false` and
`physical_validation=false` until all selected regions can actually be
certified. An incomplete result may be inspected in Preview with its reasons
visible. Transport tests use the separate approved synthetic fixture and
identified loopback receiver; they do not promote a regional study to printable.

## Consequences

The five roof coupons are reproducible without editing the original model or
active Orca profile. The original Benchy is refused by the current restricted
transform; it is not replaced by a partial top or a different boat. Solving its
holes and curved paired boundaries needs a richer region/transition solver.

The 0.15 mm deposition minimum remains strict by default. An explicit Preview
exception can retain original short edges, recording them separately. Their
mapped XYZ must be emitted even when E and feed happen to remain unchanged.

The stock SV06 CAD establishes provenance, not a registered or measured head
envelope. This version installs no Orca fork, external slicer, or real-printer
connection. A native Preview observation and a physical test are separate
evidence gates.

## Evidence

See [digital study](../ESTUDO_TETO_20_25.md), `tests/test_regional_shell.py`,
`tests/test_head_clearance.py`, `tests/test_roof_audit.py`, and
`tests/test_regional_controller.py`. Numerical outputs are under
`study/evidence/roof-study/` and identify source revisions and SHA-256 values.
