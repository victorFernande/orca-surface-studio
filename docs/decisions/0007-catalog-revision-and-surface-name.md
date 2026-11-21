# ADR-0007 — One revision per region catalogue and compatible display rename

Status: Implemented in 0.5.1; native Benchy preparation remains unsupported.

The human-flow Benchy test on 2026-11-21 found that the region catalogue
serialized the full project mesh once per candidate plane. Curved geometry
produced many distinct planes and the native UI remained busy. The catalogue
now reads the immutable source revision once and uses it for every candidate
identifier and the resulting catalogue, including the error path. A regression
test verifies a single read and consistent origin. A separate run of the
225,154-triangle input completed in 7.0523 seconds. This is not a native UI
latency measurement or an expansion of the geometry contract.

The user chose Orca Surface Studio as the public project name. The visible
Studio heading/title and author metadata use this name. Installed capability
IDs, names and directory retain the legacy identity so existing activation
and permission choices remain usable. Package/import names also remain stable.
A complete native capability rename requires a separate migration design.

After updating and recovering the original Benchy project, the actual native
preparation refused holes/internal boundaries and preserved the source. No
native conformal Preview, transport or physical Benchy print was reached.
See [the illustrated manual](../MANUAL_BENCHY.md) for observed actions and limits.
