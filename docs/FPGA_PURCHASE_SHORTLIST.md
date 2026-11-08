# Budget FPGA shortlist for Mac + Raspberry Pi

Researched 2026-11-08. User has only MacBook Pro and Pi4; wants minimum cost
without blocking learning. Local Mac reports arm64. No hardware bought or
software installed. Prices/stock are observations, not a landed-cost quote.

## Recommendation

FPGA is a good systems/AP learning extension when paired with actual workloads:
build a small CPU/peripheral, understand registers/buses/interrupts, then add a
bounded EdgeXR accelerator and measure transfer+compute+return cost. It is not
a prerequisite for AP learning and not an automatic Pi replacement. The Pi can
already teach Linux drivers, memory, scheduling and I/O. Keep it as the host and
reference initially; do not require the full OpenCV/MobileNet app to fit a cheap
soft CPU. A peripheral beside the Pi is a practical start, not a standalone
AP SoC with cache-coherent DMA. Those are later, distinct milestones.

**Budget middle candidate: Tang Primer 20K core + Dock.** More external memory
than Nano20K gives room for computer-building exercises. Verify the exact bundle,
current delivered price and a Mac toolchain build before ordering. I could not
verify its current checkout price; do not use old blog prices as a quote.

| Board | Role / capacity | Recommendation |
| --- | --- | --- |
| Sipeed Tang Nano 20K | ~20K LUT4, 8 MiB SDRAM | Lowest-cost candidate for HDL, small soft CPU and Pi-attached peripheral; not the safest long-term whole-computer choice |
| Sipeed Tang Primer 20K **core + Dock** | ~20K LUT4, 128 MiB DDR3; Dock programming/UART and Ethernet interfaces | Preferred budget candidate for the user's progression, conditional on current quote and build validation; bare core alone is insufficient |
| ULX3S **85F** | ~84K LUT, 32 MB SDRAM, ECP5 open flow | More logic headroom for a custom soft-CPU SoC; not cheapest. Research listing: US$275 + $18 worldwide shipping, preorder estimate Dec 1 2026; recheck before purchase |

Manufacturer specs: [Nano20K](https://wiki.sipeed.com/hardware/en/tang/tang-nano-20k/nano-20k.html),
[Primer20K](https://wiki.sipeed.com/hardware/en/tang/tang-primer-20k/primer-20k.html).
ULX3S seller: [Crowd Supply](https://www.crowdsupply.com/radiona/ulx3s).
The ULX3S price/ship listing was available during research but a later fetch
returned 403; confirm current checkout. Taxes/import charges are additional.
Sipeed links to its store; no verified present stock/price claim here.

## Host/toolchain constraints

[OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build) provides macOS
arm64 and Linux arm64 distributions, plus Yosys/nextpnr and programming tools.
[Apicula](https://github.com/YosysHQ/apicula) lists the Tang boards. This is the
open-source route; do not assume the vendor IDE is native Mac software.
[Linux-on-LiteX](https://github.com/litex-hub/linux-on-litex-vexriscv) lists board
targets, but availability does not prove a full Linux/DDR build has been tested
on this Mac. Its documented tested Linux build environment differs from macOS.
Check synthesis, place/route, programming, CPU and memory-controller examples
before promising a board's complete capabilities. No whole-EdgeXR benchmark.

Avoid buying Zybo/PYNQ purely because older recommendations call them cheap:
the usual [AMD supported build hosts](https://docs.amd.com/r/2025.1-English/ug973-vivado-release-notes-install-license/Supported-Operating-Systems)
are x86-64 Windows/Linux, not this Apple-Silicon Mac or Pi. A new supported host
would add cost. Mac ARM virtualization is not the same as x86 Linux support.

## Buy only what the first milestone needs

- Correct USB **data** cable and Mac adapter as required by chosen board.
- Primer: core plus Dock, not just the SODIMM-shaped core module.
- Dedicated microSD + reader only when following a supported boot recipe.
- Board-specified power source; do not assume arbitrary adapters are safe.
- Later: jumper wires and perhaps a basic logic analyzer after interface planning.

No separate CPU/RAM chips, breadboard CPU, custom PCB, extra camera or expensive
oscilloscope is required to begin. Do not connect Fusion HAT/servos or Pi GPIO
until electrical levels, ground, pins and protocol are verified. No interface
wiring or installations are authorized by this recommendation.

Next pre-purchase check: choose an exact seller/bundle and total budget, obtain
permission for a temporary open-toolchain smoke test, compile a small peripheral
and CPU target, inspect utilization and confirm programming cable support. This
reduces the risk of buying a cheap board that creates expensive limitations.
