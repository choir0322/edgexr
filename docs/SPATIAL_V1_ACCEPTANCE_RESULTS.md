# Spatial v1 acceptance review — 2026-11-05

Verdict: **needs investigation; not a clean v1 acceptance pass**. Private source
folder: `~/Desktop/spatial-v1-acceptance-01`. All 172 JSONL rows parse and all
172 referenced, unique images decode as 640×360 grayscale. No raw images/logs
are committed. [Structured evidence](../benchmarks/results/spatial-v1-acceptance-2026-11-05.json)
retains software/configuration, distributions and missing measurements.

## What worked

Three distinct images were explicitly enrolled about 13, 20 and 30 seconds
after the first logged frame. Inspection shows center shelving, a different
view with hanging clothing, and a view of a lamp/desk. Exact physical directions
are user observations, not ground truth supplied by the log. Later center
return imagery supports a real visual revisit.

Saved decisions contain 107 known results, 49 unknown/no-verified-match results,
13 startup empty-memory results and three enrollments. Known rows by label are
93/13/1. View-3's one saved known result is immediately after enrollment; this
does not establish the requested later right-view revisit. Ground-truth sequence
and failed-return accuracy are not available from decisions alone.

The final map has three nodes and four distinct directed links, with five
cumulative label changes. Query counts include seven known View-1 decisions
whose recording jobs were dropped: final map count 100 versus 93 saved rows.
Do not interpret links as physical paths or missing evidence as a camera loss.

## What blocks acceptance

| Requirement | Observation |
| --- | --- |
| Continuous orientation | One 878.90 ms midpoint gap, exceeding the 200 ms limit; integration remains unknown afterward |
| Orientation at enrollment | View-1 ready; View-2 and View-3 unknown, so their saved bearings remain unavailable |
| Evidence completeness | Recorder partial: 172 accepted/written, eight dropped, zero pending/error; queue reached four |
| Exact source provenance | Metadata revision bcc0d73 with dirty=true; changed-file details absent |

Of 172 saved frame contexts, 14 are ready and 158 unknown (including startup).
Visual recognition continued. This demonstrates useful failure isolation and
honest unknown handling, but fails the profile's continuous-orientation goal.
Do not loosen the gap limit or silently restart the quaternion reference to
make this pass; saved reference orientations would no longer share an epoch.

The slow IMU event begins reading at host monotonic 164.020692390 s, roughly
15 seconds after the first recorded frame. Its read takes only 4.895 ms and
reported late wake is 863.545 ms. The scene computation spanning
163.095409571–164.107663402 s takes 1012.254 ms wall time but 105.517 ms of
scene-thread CPU. The surrounding PNG writes take approximately 13–18 ms.
Thus the long IMU gap is not an observed 879 ms I²C transaction, nor does it
coincide with the longest image writes. The traces do not identify the source
of the pause: scheduler delay, runtime contention, faults/I/O or other processes
require further evidence. Wall-minus-thread-CPU is not a diagnosis of GIL time.

Later PNG writes take 2.25–9.24 seconds. Maximum recorded queue wait is 8.25 s;
the queue fills and drops query evidence as designed. Recognition continued,
but finite buffering cannot absorb arbitrarily long writes without loss.
The observed maximum previous JSON-write interval is also 1.98 s; final-file
completion does not make every disk operation fast. No storage attribution or
CPU/energy savings are inferred.

Saved scene compute wall median/p95 is 122.22/135.57 ms; map update is
0.279/0.386 ms. These are selected-row intervals, not total CPU utilization or
complete-workload latency. Eight missing query rows bias distributions.

## Decision and next investigation

Keep v1 acceptance open. The user selected embedded Linux systems engineering
and AP performance engineering. The immediate issue is the sensor scheduling
pause and recording backpressure exposed by this application run. This is a
goal-aligned systems investigation; new spatial features need not precede it.

1. Obtain `git status --short` and tracked diff from the Pi to explain dirty
   provenance. Do not discard changes or call this an exact clean baseline.
2. Prepare a bounded diagnostic run with thread names/native IDs and a common
   host timebase; correlate IMU lateness, scene intervals, writer intervals,
   process/thread CPU and system I/O activity. Check available tracing tools
   before installing anything or changing privileges/kernel settings.
3. Use per-thread scheduler evidence where available to distinguish sleeping,
   runnable-but-not-running and on-CPU time. Python-runtime contention needs
   its own evidence; no conclusion follows solely from scheduler data.
4. Reproduce with unchanged detector-off profile. If comparing image recording
   against JSON-only, label it an explicit workload experiment, not acceptance
   of the image-backed profile. Preserve quality/continuity and loss counters.
5. Make one justified fix, then rerun the affected acceptance checks. A larger
   queue or process separation is a hypothesis, not an automatic remedy.

Total CPU, RSS, temperature, frequency, hardware counters and energy were not
recorded in this run. Power/cooling, negotiated camera mode and actual full
launch argv are not retained; do not fill them from assumptions. The requested
180 seconds derives from the prescribed command; saved frame span is 179.096 s.
Scene metadata confirms two OpenCV threads, 10 ms sleep, target 1 Hz, detector
off and PNG recording on.
