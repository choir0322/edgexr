# CS:APP reading plan (mid-November to April/May)

At about 1 hour a day you have roughly 160 hours. That's enough for about 60–65%
of the book read carefully with its practice problems, so this plan skips or
skims the less relevant parts. Do the practice problems (their solutions are in
the book) and mostly skip the homework.

One adjustment: the book uses Intel x86-64 machine code, while your Pi uses ARM
(aarch64). The concepts carry over fully. When you study Chapters 3 and 5,
compile small C examples on the Pi with `gcc -O2 -S` and compare the ARM output
with the book's.

| Weeks (approx.) | Read | Why it matters for EdgeXR |
|---|---|---|
| 1–2 (Nov 17–30) | Ch 1, all. Then 2.1–2.3 (bits, bytes, byte order, integers, two's complement, bit operations, integer arithmetic). | The big-picture map of hardware, OS, processes, threads and caches, plus Amdahl's Law. Chapter 2 covers how the IMU's raw readings arrive as signed 16-bit numbers, byte order in I2C registers, ORB descriptor bits, and XOR/bit counting. |
| 3–4 (Dec 1–14) | 2.4 floating point. Ch 6 memory hierarchy (skim 6.1 on storage hardware; read 6.2–6.6 carefully). | Floating point leads into fixed-point and 8-bit design for the FPGA and the depth network. Ch 6 explains why conv1 and conv13 stress memory differently, why descriptors fit in cache, and the microSD stalls. Run the book's "memory mountain" experiment on your Pi. This lines up with step 5. |
| 5–8 (Dec 15–Jan 11) | Ch 3 core: 3.1–3.8 and 3.9 (structures, alignment). Skim 3.10–3.11. Skip the attack/defence details in 3.10.3–3.10.4. | You need to read what the compiler produces before you can optimize it in Ch 5. Pointers, arrays and alignment also matter for buffers you'll send to the FPGA. |
| 9–11 (Jan 12–Feb 1) | Ch 5, all. | The core application-processor chapter: how a modern CPU actually executes code, loop unrolling, multiple accumulators, and profiling with a profiler. Apply it by writing the Hamming matcher in C on the Pi and measuring each version. That becomes the CPU baseline your FPGA design must beat. |
| 12–15 (Feb 2–Mar 1) | Ch 4: skim 4.1 (the book's toy instruction set). Read 4.2 logic design, 4.3 sequential processor and 4.4 pipelining principles carefully. In 4.5 read hazards (4.5.5) and performance analysis (4.5.9). | This is the bridge to FPGA design: logic gates, clocking, pipeline registers and throughput versus latency. Your FPGA matcher will be a pipeline. Tip: read 4.2 (~15 pages) early, as soon as the board arrives and before your first LED-blink design. |
| 16–18 (Mar 2–22) | Ch 8: 8.1–8.4, signals 8.5 lightly. Ch 9: 9.1–9.8 (address translation, the TLB, and mmap). Skip 9.9–9.10 (memory allocator and garbage collection internals). | Context switches and scheduling explain your worker stalls. Virtual memory and mmap explain how a driver hands buffers to a program, which matters when you move data between the Pi and the FPGA or write a kernel driver. |
| 19–21 (Mar 23–Apr 12) | Ch 10, which is short. Ch 12 concurrency: threads, shared variables, semaphores, using threads for parallelism, races, deadlocks. | Ch 10 covers buffered versus unbuffered I/O and why storage writes stall. Ch 12 is the theory behind EdgeXR's threads, latest-frame slots, locks and bounded queue. |
| 22–24 (Apr 13–May) | Optional: Ch 7 (7.1–7.4 and 7.10–7.12 on shared libraries). Ch 11 skim. Use the rest as catch-up time. | OpenCV and NumPy load as shared libraries. Ch 11 explains your preview's HTTP traffic over SSH. Both are lower priority. |

## What to skip or treat lightly

- Ch 3: buffer-overflow attacks and defences.
- Ch 4: the details of the toy instruction set's encoding.
- Ch 9.9–9.10: memory allocator and garbage collector internals.
- Ch 11: the full web server.
- Most homework problems.

## One gap the book won't fill

CS:APP doesn't teach a hardware description language or FPGA tools. When you
start Tang Primer work, you'll need a short Verilog resource alongside Chapter 4.
One option is Harris & Harris, *Digital Design and Computer Architecture* (ARM
edition), its HDL and sequential-logic chapters.

## Making the reading stick

After each chapter, write one sentence linking it to a measured EdgeXR number.
For example: "Chapter 6: descriptors per view ≈ 19 KB, smaller than the cache,
so matching should be compute-limited. Test this in step 5." Those notes become
the systems section of your project write-up.

## Related roadmap

Weeks 16–21 (Chapters 8–10 and 12) are the background for the user-written
[Pi ↔ Tang Primer 20K link driver](../SYSTEMS_AND_AP_EXTENSIONS.md#user-written-pi--tang-primer-20k-link-driver).
