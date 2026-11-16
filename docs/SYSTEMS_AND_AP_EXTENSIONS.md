# AP-first extensions with embedded Linux systems support

User-selected priority, clarified 2026-11-05: **Application Processor engineering
is the primary learning outcome**. Spatial application remains the workload;
embedded Linux systems work supports measured processor/resource questions.
The [v1 acceptance review](SPATIAL_V1_ACCEPTANCE_RESULTS.md) exposes a scheduling
and recording issue to investigate now. Do not delay profiling until the
application is perfect. See [priority decision](decisions/2026-11-05-ap-first-priority.md).

## AP-led sequence

1. **Explain current stalls:** correlate CPU/thread activity, scheduling delays,
   sensor gaps and recording intervals. Question: why does a nominally light
   sensor task miss its window while vision and evidence recording run?
2. **Establish the exact spatial workload:** adapt the profiler for detector-off
   scene/orientation work; retain rates, CPU/RSS, latency tails, skipped jobs,
   temperature/throttling and orientation quality. Record observer overhead.
3. **Optimize a demonstrated bottleneck:** test one scheduling, copying,
   threading or native/SIMD change with before/after evidence and quality limits.
   Inspect supported hardware counters to explain instruction/cache behavior.
4. **Evaluate detection's incremental cost and value:** semantic-memory and
   foreground-exclusion experiments follow the bounded plan below. Compare
   recognition robustness against CPU, memory traffic, latency and continuity.
5. **Study power/energy:** supported frequency policies and external electrical
   measurement when available; include all powered devices in the stated boundary.
6. **Hands-on low-level AP track (explicitly requested):** build and boot a
   recoverable custom kernel/BSP image; trace the camera/I²C/scheduler path;
   implement and test a relevant sensor-driver or kernel change after auditing
   existing support. Keep before/after timing and resource evidence. Accelerator
   integration/scheduling remains optional and hardware-dependent.
   The concrete driver target is the user-written
   [Pi ↔ Tang Primer 20K link driver](#user-written-pi--tang-primer-20k-link-driver) below.

Each experiment has a fixed input/configuration, an AP hypothesis, a quality
constraint and a reproducible result. New models or features must earn their
compute/memory budget. No optimization is assumed from fewer operations alone.

## Computer systems engineering — supporting track

The user explicitly wants experience below application code, including kernel,
BSP and drivers. These are planned practical milestones, not merely background
reading or contingent interests. First correlate thread scheduling, sensor continuity and recording backpressure
in the existing application. Then assess one architectural change from evidence.
Follow with reproducible embedded Linux deployment/BSP work if useful: pinned
boot/kernel configuration, device descriptions and application startup. A kernel
or IIO sensor-driver extension is a later specialization, contingent on existing
driver support, sensor documentation and accessible wiring. Building a kernel
alone does not demonstrate a driver or scheduler implementation. Real-time work
begins with measured deadline misses; hard guarantees require bounded behavior
throughout the chosen path. Full OS design remains a separate substantial branch.

## User-written Pi ↔ Tang Primer 20K link driver

**User direction, 2026-11-17:** once the Tang Primer 20K (core + Dock) arrives,
the user will personally write a Linux kernel driver for the link between the
Raspberry Pi 4 and the FPGA. The assistant explains concepts, reviews code,
designs tests and measures; it does not write the driver for the user. Status:
**planned**; nothing is built, wired or measured.

**First interface: SPI** (to confirm before wiring). The Pi is the SPI controller
(in-tree `spi-bcm2835` driver); the FPGA implements an SPI target with an ID
register, a small register map and a FIFO. SPI is simple to debug with a logic
analyzer and fast enough for the first offload: one image's ORB descriptors are
600 × 32 B ≈ 19 KB, about 8 ms at an assumed 20 MHz clock (derived, unmeasured).
Faster links (parallel GPIO, Ethernet on the Dock) wait until SPI is measured.

Must be verified before any wiring (hardware change → reviewed procedure first):
which header pins the Fusion HAT already uses (SPI0 is GPIO 8–11, physical pins
19/21/23/24); the Dock pins' I/O bank voltage (assumed 3.3 V LVCMOS, matching the
Pi); a common ground; short wires; and which pin carries an FPGA-to-Pi interrupt.

| Milestone | What the user builds | Evidence / AP question |
|---|---|---|
| D0 Audit | Check existing support: `spidev`, `spi-bcm2835`, SPI device-tree overlays, kernel `6.12.47+rpt-rpi-v8`, availability of matching kernel headers (installing them needs approval). | Written audit; no custom driver before a baseline exists |
| D1 First module | Out-of-tree "hello" module built on the Pi against the running kernel; load, unload, `dmesg`; recovery plan (not loaded at boot, SD backup). | Build/load log; module lifecycle understood |
| D2 User-space baseline | FPGA SPI echo + ID register (open toolchain on the Mac); Pi talks to it through `spidev`. | Throughput, per-transfer latency, CPU: the baseline the driver must match or beat |
| D3 Driver v1 | `spi_driver` bound by a custom device-tree overlay (e.g. `compatible = "edgexr,tang-link"`); `probe`/`remove`; character device `/dev/edgexr-link` with read/write/ioctl for registers; error paths; debugfs counters. | Same tests as D2; correctness under unload/reload and malformed requests |
| D4 Driver v2 | Batched transfers for descriptor matching; DMA-capable buffers; `mmap` to avoid copies; FPGA "done" interrupt on a GPIO waking the waiting reader instead of polling. | Copies avoided, interrupt-to-wakeup latency distribution, CPU while waiting |
| D5 Matcher offload | User code sends query/reference descriptors; FPGA returns distances or best matches; integrate behind the existing matcher interface. | End-to-end time including transfers versus the C/NEON CPU matcher (CS:APP Ch 5 baseline); identical match results |
| D6 Tracing and stress | Tracepoints in the driver; ftrace of syscall → SPI → IRQ path; long stress and fault tests. | Latency tails and failure behaviour, recorded in `docs/STAGE_RECORDS.md` |

Background: [CS:APP reading plan](learning/CSAPP_READING_PLAN.md) Chapters 8–10
(exceptional control flow, virtual memory and `mmap`, system-level I/O) and the
Linux kernel documentation on SPI protocol drivers and device-tree overlays.
Development stays Mac + Pi only: modules are built natively on the Pi; FPGA
bitstreams use the open Gowin toolchain on the Mac (to be validated, see
[FPGA shortlist](FPGA_PURCHASE_SHORTLIST.md)).

## Application processor performance engineering

Characterize current failures now, then freeze the spatial workload once the
blocking issues are understood. Extend the historical detector-specific profiler to validate this exact
scene/orientation configuration; do not reuse it unchanged (it requires a ready
detector). Measure total/per-process CPU, RSS, rates, latency tails, temperature
and throttling. Then inspect available hardware counters and profile a proven
bottleneck. Evaluate native/SIMD changes only against optimized library baselines.
Add measured energy and supported frequency-policy experiments when equipment
is available. Accelerator integration/scheduling is later optional work requiring
compatible hardware/runtime; no NPU result is claimed on this setup.

Do not install dependencies, change kernel/driver/frequency policies, add hardware
or launch motor tests implicitly as part of this roadmap. Retain reproducible
settings and quality outcomes for each comparison.

## Semantic spatial memory — direction approved; implementation planned

MobileNet-SSD can attach timestamped category, confidence and image-box context
to a recognized view: for example, a bottle was observed in View-2. Preserve
detector source sequence/time and only associate sufficiently fresh compatible
results; asynchronous latest results are not inherently the same frame. A
view-level semantic record is simpler than an object identity or 3D landmark.
Repeated labels such as chair are weak evidence for distinguishing views.

A later experiment could exclude potentially moving foreground boxes from ORB
feature extraction. Boxes include background, people can stand still and
non-person objects can move. Detection misses, box age and camera motion make
masking fallible. Compare moving-person clips with/without masking on the same
frames, retaining enough background features and using explicit unknowns.
Do not let object labels override geometric verification or repair gyro gaps.

Depthwise and **1×1 pointwise** convolution make the MobileNet feature extractor
efficient; SSD predicts classes and boxes from feature maps. These operations
do not independently supply position, depth or a persistent spatial map.
Learned place descriptors would be a separate model/representation experiment.

The user supports a potentially dynamic/person → foreground exclusion policy
and persistent furniture → semantic memory policy. These are conservative class
priors, not claims of measured motion or immovable objects. A standing person
still receives the potentially dynamic policy; a chair can be moved. Furniture
annotations describe observations and should expire or be marked last-seen,
not declare a chair permanently present. Retain transient person observations
separately when useful; they must not become location identity evidence.

First retain the detector-off baseline. Follow the
[semantic extension plan](exec-plans/active/semantic-spatial-memory.md) for
bounded source-aligned annotations, optional masking and separate AP profiles.
No semantic path is running yet. Sources supporting the concepts:

- [MobileNet paper](https://arxiv.org/abs/1704.04861): depthwise separable features.
- [SSD paper](https://arxiv.org/abs/1512.02325): category/box predictions.
- [DynaSLAM](https://arxiv.org/abs/1806.05620): research precedent for excluding
  dynamic content; its segmentation/geometry pipeline is more capable than
  simple MobileNet-SSD box masks, and its results do not transfer to this Pi.
