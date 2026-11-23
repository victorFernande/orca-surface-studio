# Sidebar callback storage fix — 0.15.4

The native sidebar could fail at **Study motion** with
`plugin.storage() must be called from a plugin callback`. WebView callbacks
do not retain the SDK plugin callback context. Cache the plugin-owned storage
path after its first successful resolution during capability/controller setup,
and reuse it in dock callbacks and workers. A failed lookup is not cached;
a different SDK instance cannot reuse the previous path. No grants are edited.

Three regression tests cover those cases. All 299 Python tests passed locally
with `-B -W error`; standalone distribution checks passed. A read-only
Windows/macOS/Linux CI matrix now verifies tests and builds without installing
or publishing. Publication approval and physical qualification gates remain.
The first CI matrix exposed temporary-path aliases in permission test fixtures
on Windows/macOS. Resolve the fixture root before comparing audited paths;
production permission checks and authorization behavior remain unchanged.

Native Windows OrcaSlicer 2.5.1: page and sidebar recognize the selected roof
coupon, selection painting and back-navigation work. Retrying the study passed
the original storage failure and reached the planner. The whole-model attempt
then returned `SPLINE_PLAN`; a localized attempt returned `WALL_NO_EFFECT`.
These are recorded planner limitations, not successful toolpath generation.
This fix does not change the planning algorithms or approve printing.
