# ADR-0001 — Capture immutable slices and use an independent printer agent

Status: Accepted for the integration study, 2026-11-19.

## Context

The ordinary postprocessing hook changes exported G-code but not the native
preview. Opening a loose G-code disables Print. The existing legacy OctoPrint
route rejects a project without models. Python has no public operation to replace
the current plate preview while preserving its editable model.

## Decision

Read objects on the UI thread, copy the slicing graph within its callback, and
bind the completed G-code to that generation and plate. Generate only from an
immutable private capture. Build a sliced-only package for the native viewer.
An independent Python agent validates the exact approved plate/hash before
uploading to an explicitly identified loopback simulator.

Selection is by ModelObject. Linked instances share the rule. Ambiguous mapping
is an error, not a name or bounding-box guess. In-flight results cannot change a
newer generation. UI access and IPC opening stay on the native UI thread.

Page and Script capabilities stay independent. Users may hide the Page through
the native capability manager and keep the panel command. Updates preserve that
choice. This plugin does not manipulate other plugins' visibility.

## Consequences

Native capture permissions, package loading and Print readiness require tests
in the actual Orca process. Passing transport and parser tests does not approve
them. The benchmark agent cannot transmit to a physical printer. A future real
transport requires physical validation and an explicit profile implementation.

A missing native export/capture contract is reported as an integration gap;
the study does not silently add a fork or bypass host auditing.
