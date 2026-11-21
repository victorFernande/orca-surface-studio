# ADR-0005 — Independent coupon supports and conditional physical preflight

Status: Implemented for isolated coupon preparation. Physical transport remains
held. Supplements ADR-0004; it does not grant production approval or replace its
regional geometry, deposition and head-clearance gates.

## Context

The user subsequently authorized a physical trial of the small 25° coupon on
`Sovol SV06 0.4 nozzle -3DPrinter`, with the factory head, PLA Voolt3D without FP,
a clear bed and supervision. The authorization is conditional on successful
checks. Mouse/keyboard control was separately approved for this preparation.
The earlier Preview-only study's authorization scope is therefore historical;
the present hold is a technical result, not a missing user permission.

Mapping model and support through the same vertical field compresses the
native support gap unevenly. Raising the native gap alone removes some bead
intersections but gives different clearances at the low and high roof edges.
The active user's presets are inherited from packaged system profiles, so a
complete native configuration was captured by saving a separate Orca project.
An isolated project must clear parent-relative override tracking; otherwise
the native CLI silently restores process settings such as support and labels.

## Decision

For this restricted single-ceiling rectangular coupon, retain the original
model field and give labelled support paths a separate field. The native
support ceiling maps to the target underside minus a requested vertical gap.
The base stays fixed; the same analytic column-Jacobian integral scales support
E. Travel endpoints use their respective model/support frames, with straight
transitions between frames. The analytic chord and segment checks still apply.

`with_paired_support_gap` returns a copy and refuses mismatched ownership,
duplicate application, invalid ceilings and a gap reaching the fixed base.
This helper is used by the isolated preparation script. It is not wired into
the installed Studio's automatic UI flow and is not an arbitrary-support solver.

The held candidate uses the exact Voolt3D non-FP preset, 200/195 °C nozzle,
65 °C bed, copied flow ratio 0.97, 0.25 mm native layers and restrained speeds.
The 0.6 mm proxy gap is replaced by an independent 0.42 mm geometric vertical
gap. This geometric setting is distinct from the sampled finite-material gap.
The invalid `first_layer_print_min[5]` reference in the copied startup is changed
to index 1 only in this job. Persistent user presets remain unchanged.

The original engine's PRINT DISABLED marker and transport restrictions remain.
The candidate is held until head and deposition checks can release the exact
payload; adding temperatures or viewing it in Orca never performs that release.
Factory CAD provides nominal dimensions and nozzle placement, not measurements
of the installed head. An exact CAD point classification can reject a proposed
deposition estimate, but sampling without a witness cannot approve a full path.

## Consequences

The support correction preserves all 14,829 model deposition commands' XYZ,
relative E values, feed and role in the actual candidate comparison. Unit tests
exercise model preservation, both travel directions, support-volume integration,
absolute/relative E, following resets and rejection cases.

The 0.05 mm XY audit sampled 32,000 underside locations. It found no support/model
intersection and a minimum estimated normal material gap of about 0.206 mm.
Uncovered samples and sparse-support voids remain explicit: these numbers are
not complete support coverage, removability, surface or physical certification.

The stock-nozzle comparison has produced earlier-layer interference witnesses
under the horizontal-bead estimate, including with 0.25 mm layers. It must be
reported as an estimated contact with stated frame/material assumptions, not
proof that every factory SV06 is physically unable to print 25°. The candidate
remains held; no real printer is contacted while that issue is unresolved.

## Evidence

- `scripts/prepare_held_coupon.py`: isolated native settings, startup correction,
  support field, heated candidate and byte-identical Preview package payload.
- `scripts/find_stock_head_counterexample.py`: official nominal BREP / earlier
  logical-layer bead witnesses, explicit sampling budget and no approval path.
- `tests/test_paired_support.py`: independent support and state regressions.
- `study/evidence/physical-preflight/`: source project, trials, assessments,
  candidate, hashes, native logs and model-preservation comparison.
- Official CAD revision: `Sovol3d/SV06-Fully-Open-Source` at
  `75f8a0da6ff822c67b6aff62cfa85c7a441e2271`.
