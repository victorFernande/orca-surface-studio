# ADR-0006 — One supervised physical coupon trial

Status: A specific physical start was accepted by the real SV06 on
2026-11-21 at 03:31 UTC. The user subsequently reported that it printed
perfectly. This is a qualitative observation of that specific coupon, without
dimensional metrology or production qualification. This supplements ADR-0004/0005;
it does not relax the installed
Studio's general print gates.

The user explicitly requested the original small 25-degree coupon with XYZ
inclination, PLA Voolt3D without FP, a stock SV06 head, a clear bed and human
supervision. After being told that the transition and installed-head metrology
were still pending, the user confirmed: “pode imprimir tem espaço eu conferi a
peça que foi criado e a folga”. This authorizes this controlled experiment;
it is not a measured head profile or production/surface certification.

The isolated constant-pitch preparation preserves the original 14 x 14 x 1 mm
flat base and upper coupon geometry, rotated 180 degrees on the bed. Above the
base it shears the native source instead of compressing the stem/support
columns. Source-only dummy islands hold object Z during slicing and are
discarded. Four removable support slats share the inclined layer family.
The vertical pitch is 2/7 mm, with normal spacing about 0.259 mm. The first
clipped transition cell reaches 0.0377 mm, below the ordinary 0.07 mm planar
minimum; it remains an explicitly unvalidated deposition experiment. The
cut-cell E integral is mathematical, not a calibrated flow/adhesion model.

All upper transfers lift 3 mm above the printed prefix. The upper paths are
limited to approximately 5 mm/s Z and 3.26 mm3/s flow; every emitted endpoint
is inside the confirmed 220 x 220 x 250 mm volume. The exact copied material
profile supplies 200/195 degrees C nozzle, 65 degrees C bed and 0.97 flow.
The job corrects the copied startup's invalid Y index; saved user presets
are not changed.

The signed temporal body bound against the official nominal assembly is
disjoint under the stated uncalibrated material enclosure. It is a lower
bound of 0.0236 mm using the conservative square domain, not a measured actual
minimum gap. It excludes neither nozzle contact nor other physical issues
from the general gate: growing-bead contact and installed TCP registration
are still unqualified. The user's direct clearance observation is recorded
separately as trial authorization, not converted into measurement evidence.

The held native Preview opened with 35 layers. Its extracted payload matched
the generated held file byte for byte. The first physical upload was stopped
because server plugins inserted display and host object directives. Readback
reconciliation confirmed those were the only changes and that no job had
been selected or started. A compact physical copy removes comments, preserving
every executable command from the reviewed Preview. The server's exact inert
DisplayLayerProgress footer is included locally; the final local and server
payloads match SHA-256. Server plugins/settings are unchanged.

The final payload is bound to a separate, one-attempt trial journal. Upload
does not select or start. Selection happens only after readback equality,
and the start intent is saved before the single start POST. A repeated start
is rejected even after a lost response. No automatic physical retry exists.
The actual physical start used the OctoPrint API, not the native Orca Print
dialog; this does not validate that remaining native UI integration.

Evidence: `study/evidence/physical-preflight/constant-pitch25-held/`, including
`preview-verification.json`, `nominal-body-bound.json`, both upload journals
and the final physical payload. The installed plugin remains version 0.5.0;
the experiment is isolated source work, not a new installed release.
