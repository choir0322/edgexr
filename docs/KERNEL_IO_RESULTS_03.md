# Filtered trace run 03

Reviewed 2026-11-07 from Desktop kernel-io-03 and spatial-io-03. Raw logs/images
remain outside Git. [Configuration register](SYSTEMS_EXPERIMENTS.md) specifies
hardware, workload, routing and limitations; measured commit is 8296b53.

Both MMC event filters read back `name == "mmc0"`. All 4,009 parsed MMC
start/done events name mmc0. All four CPUs report available zero overrun,
commit-overrun and dropped-event counters. Export is 6,652,999 bytes, untruncated;
cleanup succeeded. Trace mono-clock interval 130.079887–340.080574 s encloses
observer interval 132.762823–316.151560 s. This verifies coverage and reported
retention for selected events, not visibility into all kernel operations.

All 180 accepted records saved; zero drops; queue high-water 4/4. Orientation
ready in 179/180 rows, first row unknown at startup. 13,934 IMU polls, no midpoint
gaps above 200 ms, maximum 30.910024 ms. This is not an image-recognition accuracy
pass or hard real-time guarantee.

## AP timing evidence

Observer elapsed 183.388737 s; CPU 16.426555 s (about 8.96% of one core).
Largest sample gap 4.603623 s. Longest observer write spans
246.597763–251.164705 s (4.566943 s wall), with 0.366056 ms process CPU.
Maximum serialization wall time 8.381330 ms, wake lateness 3.982649 ms.
Image write spans 246.543169–251.173268 s (4.630099 s).
The common long interval motivates storage investigation; its low CPU time
does not identify the entire wait as device time. No measured tracing-overhead,
electrical-energy or causal run-to-run CPU improvement claim.

## Linux systems evidence

JBD2 transaction 16634 on device 179,2 spans 246.544231–251.165219 s
(4.620988 s), overlapping both writes. Later transaction 16643 spans
291.608928–295.875069 s (4.266141 s), with observer/image writes about
4.250/4.270 s. These durations overlap, not add.

Example matching MMC host/request-token start/done pair: mmc0 token
0000000083156a1a, opcode 25, tag 34, 293.569179–295.829045 s = 2.259866 s,
240 x 512 bytes requested, 122880 transferred, reported command/data/stop/SBC
errors zero. This lies within the later journal/writer interval. Consume start
tokens once and check command/payload; block sector numbers alone are not unique
request identities. The trace narrows the path but does not prove a defective
card or isolate controller, driver, filesystem and scheduling contributions.

## Decision

Filtering achieved loss-free reported retention in this run. Saving still stalls;
the queue reaches capacity but catches up. Next proposed control moves only
observer measurement output to bounded RAM during collection. It has not been
implemented or run. The learning page separates schematic sequences, measured
intervals and proposed architectures explicitly.
