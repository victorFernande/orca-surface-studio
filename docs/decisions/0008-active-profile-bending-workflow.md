# ADR-0008 — Active-profile bending with a bounded model viewport

Status: Implemented in 0.6.0; physical qualification is separate.

The rectangular paired-shell contract could not represent the Benchy roof's
internal boundary. A second coordinate transform now fits a connected roof
patch and applies one invertible, positive-Jacobian map to the complete solid.
It preserves holes and tall features without a planar collar. Branch planes
are split exactly, and face refinement bounds the complete mesh roundtrip by
barycentric quadratic residuals, not a sampling claim. Residual curvature from
the fitted plane remains in the solid. The original rectangular pilot stays
available for its existing reproducible tests.

The integrated action exports the complete active project on the GUI thread,
then prepares, slices with the running Orca executable, transforms and packages
on a worker. The package opens and its cache is checked on the GUI thread.
The public Plater binding exposes export but no slice/print action, so the
orchestrator uses the official CLI and retains the native printer agent rather
than replacing it with the simulator. There is no printer upload in this path.

The audit host requires process permissions at discovery and matches commands
exactly. A stable command uses relative arguments; Popen receives an explicit
working directory inside callback-provided private plugin storage. Discovery
declares only the exact process command and never calls plugin.storage(), which
is callback-only. No external cache filesystem grant is needed. The user grants
the process permission in Orca; the installer never modifies grants.
An exclusive directory lock prevents concurrent workspace use. Each generation
gets immutable copies of its inputs/results and hash checks. Cancellation
invalidates publication and terminates only the owned slicing child process.

Machine/material values come from the resolved exported configuration. Twenty-two
critical fields are compared against the native output configuration. Startup,
shutdown, heating, retracts and transport remain intact. Competing geometry
transforms are disabled only in the private copy; external post-processors
are refused. Unknown body commands are not interpreted as harmless macros.

The viewport receives a bounded display mesh independently of calculation
results, with WebGL and software drawing. It stays visible during errors;
changing projects clears stale geometry. Full processing uses the original
solid, not this display mesh. Snapshot revision calculation is reused across
polls, and reopening the page reuses an analysis already in flight.

This does not infer a complete head envelope from a printer profile. Physical
print gates remain unqualified until actual clearance/deposition evidence
supports them. See the [user flow and measured limits](../FLUXO_SUPERFICIE_V060.md).
