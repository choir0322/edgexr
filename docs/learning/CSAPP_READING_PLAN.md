# Reading plan: CS:APP + Harris & Harris (updated 2026-11-22)

**Goal:** finish the reading needed before building the CPU by **December 31,
2026**; start FPGA work in January; build a RISC-V CPU (in simulation first,
then on the Tang Primer 20K); then build the EdgeXR accelerator. The remaining
CS:APP chapters are read just before they are used, so they are fresh when needed.

Books:

- *Computer Systems: A Programmer's Perspective* (CS:APP), Bryant & O'Hallaron.
  Chapter 1 done (2026-11-20).
- *Digital Design and Computer Architecture: RISC-V Edition* (H&H), Harris & Harris.
  The RISC-V edition matches the CPU you will build.

**Workload:** the December block is about 480 pages, roughly 12 pages or
**1.5–2 hours a day** with the practice problems. December also has the EdgeXR
step-2 trial, step 3 and step 5, so step 4 (depth network) is dropped unless
time is left over.

## Timeline

| When | Read | Hands-on | Why it matters |
|---|---|---|---|
| Nov 22 → ~Dec 6 | **CS:APP Ch 6** memory hierarchy (skim 6.1 storage hardware; read 6.2–6.6 carefully) | EdgeXR step-2 trial, step 3 | Why conv1 and conv13 stress memory differently, why ORB descriptors fit in cache, the microSD stalls. Run the book's "memory mountain" on the Pi; it feeds the step-5 profile. |
| ~Dec 7 → Dec 20 | **H&H Ch 2, 3, 4** (combinational logic, sequential logic, hardware description languages); skim Ch 1 | Ch 4 exercises **in simulation on the Mac** (Icarus Verilog). EdgeXR step 5. When the board arrives: a 30-minute tool check (install toolchain, blink an LED) | Gates, flip-flops, clocking and writing hardware as code: the base for everything on the FPGA. The tool check finds Mac toolchain problems before January. |
| Dec 21 → Dec 31 | **H&H Ch 5, 6, 7** (building blocks, RISC-V instructions, microarchitecture). Read Ch 7 carefully. | Finish EdgeXR (without step 4) | Adders, ALUs, registers and memories; the RV32I instruction set; single-cycle, multicycle and pipelined RISC-V CPUs: the design you will build. |
| January | — | FPGA basics on the board (counter, UART "hello", ALU), then a **single-cycle RV32I CPU: simulation first, then on the board** | Hardware is learned by building it. |
| February → mid-March | **CS:APP Ch 3** core (3.1–3.9; skim 3.10–3.11) and **Ch 5** (late February). Optional: **CS:APP 4.4–4.5** as a second look at pipelining. | **Pipelined CPU** (hazards, forwarding, stalls); passes RISC-V tests and runs compiled C. Then the **C/NEON Hamming matcher** on the Pi. | Ch 3 to read the compiler's output; Ch 5 to optimize the matcher. Its measured time is the baseline the FPGA accelerator is compared against. |
| Mid-March → June | **CS:APP Ch 8** (8.1–8.4; 8.5 lightly), **Ch 9** (9.1–9.8), **Ch 10**, **Ch 12**, read alongside the work | SPI link, **your own kernel driver**, Hamming accelerator, end-to-end measurement | Context switches, virtual memory and `mmap`, system I/O and concurrency: the theory behind the driver and EdgeXR's threads and queues. |

Optional later: CS:APP Ch 7 (7.1–7.4, 7.10–7.12, shared libraries), Ch 11 (skim).

## What to skip or treat lightly

- **CS:APP Ch 4 before the CPU:** it builds a CPU in a made-up instruction set (Y86)
  and description language (HCL). H&H Ch 7 covers the same ideas with the real
  RISC-V design you will build. Read 4.4–4.5 afterwards only if you want a second view.
- **CS:APP Ch 2:** mostly covered by H&H Ch 1 and 5 (binary, two's complement,
  arithmetic circuits). Read 2.4 (floating point) only if the depth-network work returns.
- **H&H Ch 8** (memory systems): CS:APP Ch 6 covers it better.
- CS:APP Ch 3 buffer-overflow attacks and defences; Ch 9.9–9.10 (allocator and
  garbage collector internals); Ch 11's full web server.
- Most homework problems; do the practice problems instead.

## Notes for this hardware

- **ARM, not x86:** CS:APP uses x86-64 machine code; the Pi is ARM (aarch64). The
  concepts carry over. For Ch 3 and 5, compile small C examples on the Pi with
  `gcc -O2 -S` and compare with the book.
- **SystemVerilog support:** H&H uses SystemVerilog, but the open-source tools that
  run on the Mac (yosys) support only part of it. Write plain Verilog-2005 style or
  simple SystemVerilog, and check that designs synthesize, not just simulate.
- **Write the CPU yourself.** Use H&H Ch 7 to get unstuck, not as code to copy.

## Making the reading stick

After each chapter, write one sentence linking it to a measured EdgeXR number.
For example: "CS:APP Ch 6: descriptors per view ≈ 19 KB, smaller than the cache,
so matching should be compute-limited. Test this in step 5." Those notes become
the systems section of your project write-up.

## Related roadmap

The March–June chapters (CS:APP 8–10 and 12) are the background for the
user-written [Pi ↔ Tang Primer 20K link driver](../SYSTEMS_AND_AP_EXTENSIONS.md#user-written-pi--tang-primer-20k-link-driver).
