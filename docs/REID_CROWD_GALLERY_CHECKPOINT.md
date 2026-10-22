# Re-identification checkpoint — 2026-10-23

Implementation checkpoint: `6a2093e`. Private recording:
`reid-crowd-gallery-01` on the user's Desktop; raw footage and detector PNGs
remain outside Git. Raspberry Pi 4, requested 1280x720 MJPEG 30 fps, 90-second
capture, fixed-camera/steady-light notes, gallery-only live recording followed
by offline replay of identical detections with retry windows of 0 and 2 seconds.
This is not a Pi retry-runtime benchmark. See `BENCHMARKING.md` for protocol.

The user reports one person leaving while another stays; roles were not reversed
and spatial test C was not run. Visual inspection of all 132 saved detector
frames suggests the persistent person box surrounds hanging clothing. That
interpretation needs user confirmation; do not call this validated crowd accuracy.

| Return input time (s) | Gallery only | Two-second retry replay |
| --- | --- | --- |
| 8.6 | New ID | Previous ID not restored |
| 18.1 | Restore | Restore |
| 27.1 | New ID | Restore about 0.5 s later |
| 57.5 | Restore | Previous ID not restored |
| 65.5 | Restore immediately | Restore about 0.5 s later |
| 74.7 | Restore immediately | Restore immediately |
| 86.2 | New ID | Restore about 0.5 s later |

Times use the first saved detector input as origin, not video exposure time.
The last event follows crouching out of useful detection, not a sideways exit.
The three retry events are rows 55, 89 and 127 (zero-based), with similarities
0.9435, 0.8728 and 0.8708. They are not three incremental successes: gallery
history diverges after earlier restores, and one gallery-only success becomes
a retry-run failure. No overall accuracy claim is justified yet.

Known unresolved issues:

- Replay's `returns: []` and zero continuity counts are misleading here: its
  single-target counting logic does not evaluate individual returns in a scene
  with multiple person detections. They do not mean zero successful returns.
- Saved detector inputs have a 19.9-second gap around 34.1–54.0 seconds; cause
  unknown. Do not infer continuous observations or uninterrupted runtime.
- False person detections and duplicate/partial boxes complicate identity
  evaluation. Physical presence and detection presence are different.
- Reciprocal roles, genuine lookalikes, spatial cues and retry runtime remain
  unvalidated. Reporting fixes and gallery-history investigation are deferred.

Decision: preserve this evidence, pause further identity tuning, and prioritize
relative orientation and directional scene memory. No tracker behavior changed
in this checkpoint.
