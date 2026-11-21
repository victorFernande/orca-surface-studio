# ADR-0009 — Native local surfaces remain separate from roof bending

Status: Implemented for digital validation in 0.7.0; native UI and physical
qualification pending.

The 0.6 roof-aligned whole-solid map did not align every hull region to its own
surface. Varying Z across many roles is insufficient evidence of local surface
following. The user clarified that bow/side/stern upper edges should follow
their own curves without modifying the original Benchy shape.

Use Orca's native Z Contouring on the original copied mesh as a separate
`native_local` backend. Do not feed that output to the inverse roof transform.
Native XYZ and E remain unchanged; only F is limited by the active profile.
The controller action, private CLI workspace, package checks and Preview hash
handshake are shared. The CLI needs an explicit `--zaa-enabled=1`; verify its
effective setting rather than accepting a silently planar output.

The default UI selects local upper-surface contouring; the previous roof
alignment is an explicit advanced alternative. Hide irrelevant angle/reference/
sampling controls in local mode. Do not offer a planar comparison without a
separate planar baseline. Upper-facing eligibility and unsupported undersides
remain explicit; this does not promise smooth vertical walls or every model.

Physical readiness is independent. The stock-SV06 nominal complete-body floor
provides a continuous vertical-separation bound against prefix material under
the stated uncalibrated bead model. It excludes nozzle-contact certification,
installed TCP/geometry uncertainty and opaque startup/footer macros. Even a
positive nominal bound never flips `print_allowed` to true.
