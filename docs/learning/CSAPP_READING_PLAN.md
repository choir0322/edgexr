# Integrated learning plan: reading + hands-on (updated 2026-11-22)

**Goals (all kept):** (1) finish EdgeXR on the Pi; (2) a RISC-V CPU, simulated then
on the Tang Primer 20K; (3) an EdgeXR accelerator with a user-written Pi kernel
driver, compared against a C/NEON baseline; (4) after June 2027, a reduced EdgeXR on
the ESP32-P4-Nano ([roadmap](../SYSTEMS_AND_AP_EXTENSIONS.md#added-goal-reduced-edgexr-on-the-esp32-p4-nano)).

**What changed from the previous version.** Reading is no longer a separate block that
must end by December 31. Every week pairs a reading slice with a hands-on task that uses
it, mostly on EdgeXR's own code and data. Two things make the whole plan shorter:

- **The accelerator core is built during the HDL chapters.** The H&H Ch 2–5 exercises
  are the Hamming-matching unit itself, so by mid-January the core exists in simulation,
  instead of starting it in March.
- **One set of test vectors serves every implementation.** Real ORB descriptors exported
  once from EdgeXR check the Verilog unit, the C/NEON matcher, the program on your own
  CPU, the driver path and the later ESP32-P4 port.

The end dates stay the same (CPU by mid-March, accelerator and driver by June, P4
July–October). There's slack for slippage, and the board is in use from December.

**Weekly budget:** about 14 hours: 5–6 h reading (practice problems included) and
8–9 h hands-on. Each phase ends with a **done line**. Do not start the next phase's
extras before it is met; that is the guard against dragging.

**Books:** *CS:APP* (Bryant & O'Hallaron; Ch 1 done 2026-11-20) and *Digital Design
and Computer Architecture: RISC-V Edition* (H&H).

## What EdgeXR offers each topic

| Topic | Real EdgeXR target | Source |
|---|---|---|
| Memory hierarchy (CS:APP 6) | 600 descriptors × 32 B ≈ 19 KB per view, up to 12 views; 720p frames; microSD stalls | `spatial/scene_memory.py`, `profiling/` |
| Combinational/sequential logic, HDL (H&H 2–5) | XOR + popcount of 256-bit descriptors; best/second-best search with ratio test | `scene_memory.verify()` (`BFMatcher.knnMatch`, k=2) |
| ISA and assembly (H&H 6, CS:APP 3) | The same Hamming loop, as RV32I and as ARM code | C matcher (to be written) |
| CPU microarchitecture (H&H 7) | The Hamming program runs on your CPU; its cycle count is measured | your RV32I core |
| Program optimization (CS:APP 5) | C/NEON matcher versus OpenCV's matcher on the Pi | scene-memory timing: median 116 ms per whole recognition |
| Exceptions, VM, I/O, concurrency (CS:APP 8–10, 12) | SPI driver, `mmap` buffers, IRQ wake-up; EdgeXR's threads, latest-frame slots, bounded writer queue | `app/live_preview.py`, `spatial/scene_recorder.py` |

## Week-by-week plan

Weeks start on Monday. ⚙ = needs your approval first (installing software,
downloading, wiring or buying hardware).

### Phase A: finish EdgeXR + memory hierarchy (Nov 23 → Dec 20)

| Week | Read | Hands-on |
|---|---|---|
| 1 · Nov 23 | CS:APP 6.1–6.3 (storage technologies: skim; locality; the memory hierarchy) | EdgeXR **step-2 trial** (stay / removed / moved). Write one locality note: why matching one view (19 KB) should fit in the Pi's 32 KB L1 data cache |
| 2 · Nov 30 | CS:APP 6.4–6.5 (cache memories, cache-friendly code) | **Step 3 drift correction:** implement and unit-test (re-anchor the gyro on recognised ORB views; cross-check with phase-correlation shift) |
| 3 · Dec 7 | CS:APP 6.6 (memory mountain); H&H Ch 1 (skim), Ch 2 (combinational logic) | Memory mountain on the Pi ⚙ (book's `mountain.c`). Export ORB **test vectors** from recorded EdgeXR frames. Install Icarus Verilog ⚙; write a combinational **popcount-256** in simulation, checked against the vectors. **Board arrives:** toolchain check ⚙ + LED blink |
| 4 · Dec 14 | H&H Ch 3 (sequential logic, finite-state machines, timing) | **Step 3 trial** on the Pi. FPGA: UART transmitter state machine on the board ("hello") |

**Done line A:** step-2 trial passes all three cases; step 3 implemented with a Pi
trial; ORB vectors exported; popcount-256 passes; board blinks and prints over UART.

### Phase B: HDL, building blocks, accelerator core, EdgeXR profile (Dec 21 → Jan 17)

| Week | Read | Hands-on |
|---|---|---|
| 5 · Dec 21 | H&H Ch 4 (hardware description languages), all | **Hamming distance unit:** pipelined (registers between adder-tree levels), synthesized with yosys; record LUT count and maximum clock. UART receiver |
| 6 · Dec 28 | H&H Ch 5 (adders, ALUs, shifters, counters, memory arrays) | **Matcher core v0:** descriptors in block RAM, streaming best + second-best search with the ratio test, results identical to `scene_memory` on the vectors. **EdgeXR step 5 profile:** per-stage CPU, latency percentiles, memory and temperature in one documented run ⚙ (`perf` if not installed). **Freeze EdgeXR v1 (Dec 31).** |
| 7 · Jan 4 | H&H Ch 6 (RISC-V architecture, assembly, machine code) | Write the Hamming loop in **RV32I assembly**; run it in a RISC-V simulator ⚙ (RARS or Spike + GNU toolchain). Compile the C version for RV32I and for the Pi (`gcc -O2 -S`); compare the two |
| 8 · Jan 11 | H&H 7.1–7.3 (performance analysis, single-cycle processor) | **Single-cycle RV32I in simulation**, running your assembly Hamming program and producing the same distances |

**Done line B:** matcher core v0 passes every test vector in simulation and
synthesizes; EdgeXR v1 is frozen with its step-5 profile in `benchmarks/results/`;
single-cycle CPU runs the Hamming program in simulation.

### Phase C: CPU on the board + C/NEON baseline (Jan 18 → Mar 14)

| Week | Read | Hands-on |
|---|---|---|
| 9–10 · Jan 18 | H&H 7.4 (multicycle; skim) and the H&H I/O chapter (memory-mapped I/O) | Single-cycle CPU **on the board**: memory-mapped UART, a cycle counter, C programs compiled on the Mac; pass the RV32I subset of `riscv-tests` ⚙ |
| 11–12 · Feb 1 | CS:APP Ch 3 core (3.1–3.9; skim 3.10–3.11) and 5.1–5.8 | **C Hamming matcher on the Pi:** naive → `__builtin_popcountll` → unrolled with several accumulators → NEON (`vcntq_u8`). Time each version against OpenCV's `BFMatcher` on the same vectors; read the ARM assembly of each |
| 13–14 · Feb 15 | H&H 7.5 (pipelined processor, hazards); CS:APP 5.9–5.14 (limiting factors, profiling, bottlenecks); optional CS:APP 4.4–4.5 | **Pipelined RV32I:** forwarding and stalls; run the Hamming program and measure CPI (cycles per instruction) on your own CPU; `perf stat` counters for the C/NEON versions on the Pi ⚙ |
| 15–16 · Mar 1 | (catch-up) | Pipelined CPU passes the tests on the board. **One comparison table:** Hamming throughput on the Pi (OpenCV, C, NEON), on your CPU, and on matcher core v0 (core only, no transfer). Optional ESP32-P4 probe P0 (~2 days) |

**Done line C:** pipelined CPU passes the RV32I tests on the board and runs compiled
C; the C/NEON matcher matches OpenCV's results and has measured timings; the
comparison table is in `benchmarks/results/`.

### Phase D: link, your kernel driver, accelerator in EdgeXR (Mar 15 → Jun 6)

| Week | Read | Hands-on (milestones D0–D6 in the [driver plan](../SYSTEMS_AND_AP_EXTENSIONS.md#user-written-pi--tang-primer-20k-link-driver)) |
|---|---|---|
| 17–18 · Mar 15 | CS:APP Ch 8 (8.1–8.4; signals 8.5 lightly) | D0 audit (SPI pins versus Fusion HAT; voltage levels) and **reviewed wiring procedure** ⚙; SPI target in Verilog; D2 `spidev` echo baseline: throughput, latency, CPU |
| 19–21 · Mar 29 | CS:APP Ch 9 (9.1–9.8: address translation, TLB, `mmap`), Ch 10 | D1 "hello" module ⚙ (kernel headers); **D3 driver v1** (`spi_driver`, device-tree overlay, `/dev/edgexr-link`) |
| 22–24 · Apr 19 | CS:APP Ch 12 (threads, synchronization, races, deadlocks) | D4 batched transfers, `mmap`, FPGA "done" interrupt; matcher core behind the driver; **D5:** `scene_memory` can use the accelerator behind a flag, with identical results |
| 25–27 · May 10 | (optional: CS:APP 7.1–7.4, 7.10–7.12) | D6 tracing and stress; final end-to-end measurement (transfer + compute) versus NEON; write-up |
| 28 · May 31 | — | Buffer week |

**Done line D:** EdgeXR's scene memory gives identical recognition results with the
accelerator on and off; end-to-end timing, CPU and latency tails are measured against
the NEON baseline. The result is explained even if the accelerator is not faster.

### Phase E: ESP32-P4 migration (Jul → Oct 2027)

Unchanged: phases P1–P8 in the
[systems roadmap](../SYSTEMS_AND_AP_EXTENSIONS.md#added-goal-reduced-edgexr-on-the-esp32-p4-nano),
with the reading listed at the end of this file. The ORB test vectors and the C matcher
from phases A–C are reused directly.

## Cut order if time runs short

1. EdgeXR step 4 (depth network): already off the critical path.
2. Optional ESP32-P4 probe P0 in March.
3. Multicycle CPU details (H&H 7.4): read only, never build.
4. D6 stress testing reduced to one long run.

Never cut: done lines A–D, writing the CPU and driver yourself, and the test vectors.

## Still true from the previous plan

- **ARM, not x86:** CS:APP uses x86-64; the Pi is aarch64. Compile small examples with
  `gcc -O2 -S` on the Pi and compare with the book.
- **Write simple Verilog:** H&H uses SystemVerilog, but the open-source tools on the Mac
  (yosys) support only part of it. Check that every design synthesizes, not just simulates.
- **Write the CPU and the driver yourself.** Use H&H Ch 7 and the kernel docs to get
  unstuck, not as code to copy. I explain, review and build tests.
- **Skip or treat lightly:** CS:APP Ch 4 before the CPU (H&H 7 covers it with RISC-V) and
  most of Ch 2 (H&H 1 and 5 cover it; 2.4 floating point only if the depth network
  returns); H&H Ch 8 (CS:APP 6 is better); CS:APP 3's buffer-overflow sections, 9.9–9.10
  and Ch 11's web server; most homework (do the practice problems).
- **One sentence per chapter linked to a measured EdgeXR number.** Example: "CS:APP 6:
  a view's descriptors are 19 KB, below the 32 KB L1 data cache, so matching should be
  compute-limited; test it in week 11." These become the systems section of the write-up.

## ESP32-P4 migration reading (July 2027 onward)

Added 2026-11-22 for the [ESP32-P4 migration goal](../SYSTEMS_AND_AP_EXTENSIONS.md#added-goal-reduced-edgexr-on-the-esp32-p4-nano).
Read each item just before its phase:

| Phase | Read |
|---|---|
| P1 bring-up (July) | ESP-IDF Programming Guide: getting started, build system, logging; FreeRTOS basics (tasks, queues, priorities; *Mastering the FreeRTOS Real Time Kernel*) |
| P2–P3 (July–Aug) | ESP32-P4 Technical Reference Manual: memory map, caches and PSRAM, DMA, I2C, USB host, MIPI-CSI/ISP, JPEG codec (selected sections) |
| P4 (Aug) | ESP-DSP library (FFT); revisit CS:APP Ch 5 and Ch 6 for the C kernels |
| P5 (Aug–Sep) | ESP-DL documentation: 8-bit quantization and model conversion |
| P7 (Sep–Oct) | ESP-IDF performance and memory-placement guides; revisit CS:APP Ch 12 for two-core concurrency |
