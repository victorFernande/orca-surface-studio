# ADR-0012 — Guided surface workflow with explicit Preview transfer

Status: Implemented and native Orca GUI flow verified in 0.9.0; physical qualification remains pending.

The default interface presents four steps: choose one model, choose areas,
study the motion, and send the current result to the native plate Preview.
Existing controls remain accessible through More options. This is a workflow
change, not a new contouring or physical qualification algorithm.

`build_surface(open_preview=false)` builds and retains the result without
scheduling the native open operation. The final button sends `open_preview`
with the displayed result SHA-256. The controller rejects an obsolete hash;
existing source-revision, package and cache identity checks still apply.
The legacy command defaults to opening after generation for compatibility.

Source/selection changes invalidate the current study in the guided UI. A new
project revision resets the steps. One selected object can be studied from a
multi-object snapshot: the private slicing model contains only that object,
while the original full-project backup and revision remain authoritative.
An unqualified result keeps its physical warning. Transfer opens Preview and
does not upload or print. The nominal head-envelope and transition limitations
from previous reports remain unresolved by this interface change.

Verification includes Python controller/native-copy tests and local browser
checks of step navigation, no automatic open, explicit hash transfer, stale
selection invalidation, software rendering and compact layout. Local browser
fixtures are not evidence of native Orca behavior.
