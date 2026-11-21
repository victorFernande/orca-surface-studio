# ADR-0010 — Persisted, user-approved read-only Preview cache scope

Status: Implemented in 0.7.1; first native approval remains user-owned.

Fresh Orca model caches receive different per-file paths and therefore produce
repeated exact-file permission prompts. The Orca host API supports persisted
directory-tree grants using a final `/*` component. Request only `fs_read` for
the environment's absolute `orcaslicer_model` cache subtree at discovery.
Do not request writes, the entire temporary directory, arbitrary event grants,
or full access. The user sees the scope and the host persists its approval;
the plugin and installer never write grants. Canonical matching and host deny
rules remain owned by Orca. Invalid/missing environment paths fall back to
ordinary exact-file prompts.

Keep runtime source validation (current PID, Metadata, plate filename, lifecycle
identity and hashes). A covering read grant is not trust in any returned file.
The folder can contain other temporary model data, so describe the scope as a
model cache tree rather than pretending it is a G-code-extension-only grant.

Pause the Preview processing deadline only for a recognized audited-read
permission wait. Resume on a focused Studio and retain all integrity checks.
Ordinary processing still times out, and denial or mutation does not produce
an infinite retry loop. This avoids counting a user's time in a native security
dialog as a failed parsing operation.
