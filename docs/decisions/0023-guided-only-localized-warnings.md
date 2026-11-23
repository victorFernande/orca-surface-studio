# ADR-0023 — Guided-only UI and localized warnings

Status: Implemented in 0.15.3; local component tests passed. Native UI reload verification pending.

The user asked to remove More options and its older layout, and chose a
plugin language selector with seven languages for the safety warning.
The old wave/preset forms, mode switch and duplicate action buttons are
removed from the generated document. The four-step workflow, mesh viewer,
placement, head map, cancellation and page/dock actions remain. This
supersedes the optional legacy UI described in ADR-0012; backend commands
remain available to existing tools.

Warnings use offline JSON packs with the same data-only discovery format as
Gear Studio, independently bundled here under MIT. Metadata supplies selector
options; adding a language does not require another allowlist. Missing keys
fall back to English. The controller persists the warning language in its
own storage and includes it in page/dock state. Changing language does not
invalidate a study or grant transport/printing approval. Technical diagnostics
and other interface copy remain Portuguese in this change.

Local verification covers Python, standalone and wheel imports, every warning
language in page and dock, restored results, the four-step workflow with GPU
and Canvas rendering, compact width, placement and mesh fidelity. This change
does not qualify physical printing or authorize OrcaCloud publication.
