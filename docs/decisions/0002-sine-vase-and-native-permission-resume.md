# ADR-0002 — Combine radial/Z vase waves and preserve pending native reads

Status: Accepted for the digital study, 2026-11-20.

## Context

The requested FullControl-style vase changes radius and Z together during
extrusion. Following the unchanged upper mesh is a different operation.
FullControl accepts explicit point sequences; it does not provide a general
STL surface planner. The first useful implementation must use the object's
sliced contour with simple controls and show the actual G-code in Orca.

Orca's audited file reads may fail on the worker while a permission prompt is
posted to its GUI. Treating that temporary failure as a completed rejection
destroys the slice or Preview session before the user can approve access.
Conversely, the modal dialog runs a nested message loop: polling can reenter
the same verification and queue duplicate prompts if no read is marked active.

## Decision

Use a dedicated combined mode with an integer number of radial waves, aligned
spatial phase and quadratic amplitude growth. Preserve conventional layer
contours/seams; do not claim a continuous FullControl helix. Use an integrated
volume Jacobian rather than multiplying E by the 3D length alone. Reject
unsupported topology, invalid vertical gaps and unsatisfied sampling limits.

Keep a pending slice or Preview read bound to its original model, plate,
revision and path for up to three minutes. For capture, also retain the file
size, modification time and identity until the read can be retried. Resume
from GUI polling after completion of the matching native task. Never grant
permissions, broaden their scope or change activation preferences.

Allow one retry for an asynchronous audit failure, then stop on another
failure. Resume pending audited reads only when the Studio document has focus,
so hidden WebViews and native modal dialogs cannot trigger another prompt.
Mark verification/capture reads as active before entering code that
may display a modal dialog. Nested polls do no work. Before publishing a
Preview receipt, verify that the result/request still belong to the same
operation, including after a nested project mutation.

## Consequences

Native permissions and Open as project/save/cancel dialogs remain part of the
host flow. Tests of asynchronous denial and nested callbacks are necessary;
ordinary synchronous mocks alone missed the duplicate-prompt failure.
Evidence distinguishes a native controller receipt from independent hash
inspection. Combined results cannot authorize transport. Physical validation
and the real SV06 head-clearance envelope remain separate work.
