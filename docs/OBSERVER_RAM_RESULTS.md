# Observer RAM control: reviewed 2026-11-08

Source: transferred `Desktop/edgexr-observer-ram` four trial folders, pasted
comparison and trace summaries. Compact website-ready evidence:
[observer-ram-control-01.json](../benchmarks/results/observer-ram-control-01.json).
Raw images, samples and traces remain outside Git.

## Question and configuration

Is the measuring program's storage activity disturbing its measurements or app
recording? A writes profiler samples during collection. B buffers only those
samples in bounded process RAM, exporting later. Application images/JSON remain
on microSD in both. Same revision 5f6cf57, Pi 4, 180 s scene workload, 250 ms
observer target, 10 ms IMU pause, detector off; no controlled warm-up. Passive
heatsink/no fan; power unknown. The linked JSON preserves conditions and values.

| Observed metric | File A | RAM B |
| --- | ---: | ---: |
| Maximum observer gap | 2016.62 ms | 253.90 ms |
| Maximum observer output operation | 1989.57 ms | 0.75 ms (RAM admission) |
| Maximum app image write | 2109.89 ms | 39.21 ms |
| Maximum scene queue wait | 1109.89 ms | 6.11 ms |
| Queue high water / capacity | 2 / 4 | 1 / 4 |
| App records written / dropped | 180 / 0 | 180 / 0 |
| IMU gaps over 200 ms | 0 | 0 |
| Average observer CPU, one-core scale | 9.93% | 9.92% |
| Maximum sampled observer RSS | 19.91 MiB | 68.05 MiB |

Both trace windows cover collection; loss counters are zero and exports are
not truncated. B's deferred export starts 24.40 s after tracing stops. No swap
activity was reported. RAM payload 50,700,725 bytes stayed below the 64 MiB cap.
Buffered export is not a power-loss durability guarantee.

## Interpretation and limits

Long pauses disappeared from the measured observer and app image writes in B.
This supports shared-storage interference as an explanation, but does not prove
it was the only cause or diagnose a defective card. Most operations were quick
even in A: maxima describe rare latency tails, not typical sustained slowness.
CPU was essentially unchanged: waiting time is not CPU computation time.
We traded roughly 48 MiB more sampled peak observer memory for steadier records.
All images were eventually written and IMU continuity survived in both runs.

File writes already pass through Linux RAM caches: A is not a direct physical
card write on every call. B deliberately defers filesystem submission for the
samples file. Preview logs and application files still use the filesystem.

Manual scenes differed (known counts 150 versus 101, not accuracy scores), and
median temperature was 53.56 versus 56.48 C. One ordered pair does not establish
repeatability. Close this bounded diagnostic milestone with these limits;
reverse-order replication remains needed before stronger causal claims.

## Future visualization contract

Show two independent lanes: spatial recognition → bounded queue → image/JSON
writer; profiler → measurement sink. Both file writers enter the shared Linux
filesystem/storage path in A. In B, only the profiler sink changes to a capped
RAM buffer, followed by a separately timed post-collection export. Draw CPU
execution separately from data flow. Annotate waiting versus CPU time, payload
versus RSS, queue capacity, trace coverage and missing measurements. Do not draw
the microSD as broken or RAM as permanent storage. Distinguish observations,
hypotheses and deferred experiments. No learning HTML change in this milestone.
