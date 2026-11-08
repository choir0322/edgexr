# A DIY computer as an AP learning extension

2026-11-08 update: user has Apple-Silicon Mac + Pi only and prioritizes price.
Use the [current purchase shortlist](FPGA_PURCHASE_SHORTLIST.md), not a Zynq
recommendation that assumes an x86 build host. User also added a proposed
[bounded 3D milestone](decisions/2026-11-08-reconstruction-before-fpga.md) before
FPGA implementation. The foundational distinctions below still apply.

2026-11-07 evaluation; exploratory, not a hardware purchase or roadmap reset.

## Recommendation

Yes, but start with a **small FPGA SoC on an existing development board**, after
the current storage-control result. Keep the Pi as the working application and
measurement reference. Do not initially move all of EdgeXR to a soft CPU or
design a DDR/USB PCB. This is a learning extension, not an assumed performance
upgrade. No budget, FPGA board, toolchain host or procurement choice is settled.

## Different meanings of “build a computer”

| Route | What you build | Most relevant learning | Tradeoff |
|---|---|---|---|
| Discrete/breadboard CPU | Gates/registers, simple bus and memory | Instruction execution and digital logic | Valuable fundamentals, but far from Linux/AP workloads |
| Soft CPU in FPGA | CPU logic plus bus, SRAM/BRAM and peripherals in programmable fabric | Address maps, bus transactions, interrupts, firmware, HDL | Best manageable way to make a small computer; not Pi-class performance by default |
| Hard-CPU + FPGA SoC | Custom peripheral/accelerator beside a physical CPU subsystem | Linux drivers, device tree, DMA, memory/coherency, hardware/software boundaries | Closer to AP integration; vendor tools and memory plumbing add complexity |
| Custom CPU/DDR board | PCB, power, clocks, reset, high-speed memory and boot | Board bring-up, signal/power integrity, BSP | Large detour for a beginner; not necessary to study AP scheduling/performance |

An FPGA is configurable logic. A **soft CPU** is a processor circuit implemented
in that logic, not a Python CPU simulation. A **hard CPU** already exists as
fixed silicon on an SoC. A computer also needs memory, an interconnect, clock/
reset, firmware and I/O; collecting an FPGA, CPU and RAM alone does not connect
them into a working system. CPU design is one specialization; AP engineering
also includes making existing compute/memory/I/O resources serve workloads well.

## Small, useful progression

1. Simulate a supported small RISC-V SoC; run a program that prints over UART.
2. On a suitable board, use on-chip RAM first. Explain every memory-map address
   and measure cycles for a small computation; add a timer/interrupt.
3. Add one memory-mapped peripheral, such as a frame-checksum or pixel-threshold
   unit. Verify it against a CPU reference with saved, non-private test arrays.
4. If the chosen CPU/board supports Linux, add device-tree description and a
   minimal driver. Otherwise do bare-metal first. Linux needs a suitable CPU,
   memory and board support; it is not automatic for every RISC-V FPGA design.
5. Only then consider DMA/offloading. Measure transfer/setup + compute + result
   latency, CPU time and memory traffic—not accelerator compute alone. A tiny
   kernel can lose to the CPU after transfer overhead.

This provides concrete low-level AP experience without dropping the current
project's measured workload. Kernel/BSP exercises on the existing Pi are also
possible without buying an FPGA. Hard real-time guarantees and a full operating
system are separate scoped projects, not automatic consequences of this work.

## Primary references reviewed

- [LiteX](https://github.com/enjoy-digital/litex): SoC builder with soft CPU,
  memory/peripheral integration, board targets, simulation and software support.
  Useful framework to study/integrate blocks rather than designing everything
  simultaneously. Toolchain/board compatibility must be checked before purchase.
- [LiteX research paper](https://arxiv.org/abs/2005.02506): architecture and design
  approach for FPGA SoCs.
- [BeagleV-Fire](https://www.beagleboard.org/boards/beaglev-fire): example of a
  hard RISC-V processor subsystem plus FPGA fabric and on-board memory. It
  illustrates the hybrid route, **not a vetted purchase recommendation**. Check
  current tool licensing, supported development-host OS, board I/O and learning
  examples against budget before choosing hardware.

The ranking and progression above are engineering recommendations/inferences,
not benchmarks of these boards or a claim that they run EdgeXR well. We have
not built or measured an FPGA system in this project yet.
