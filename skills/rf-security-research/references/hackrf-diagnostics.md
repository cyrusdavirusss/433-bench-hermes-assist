# HackRF One — hardware, failure modes, and a diagnosis order

Researched 2026-09-21 in preparation for an existing, non-working HackRF One. Sources: the official
HackRF docs (hackrf.readthedocs.io — troubleshooting + hackrf_one + hardware_components) and the
greatscottgadgets GitHub issues where the maintainer diagnoses real failures (notably #1515 and
#1221). Those issue threads are the most valuable part of this file: they contain the actual
fault-finding logic, not just "try another cable".

## What it is, and its hard limits

- Half-duplex SDR, **1 MHz to 6 GHz**, USB 2.0 (bus-limited to ~20 Msps), 8-bit I/Q.
- **Maximum input power −5 dBm.** Above that is permanent damage. Up to +10 dBm is *theoretically*
  survivable with the RX amplifier off, but a software or user error can enable it — use an
  attenuator rather than accepting the risk. This is the single most common way one of these dies.
- Typical TX power 0 to +10 dBm up to 4 GHz (−10 to 0 dBm above 4 GHz); best range 2170–2740 MHz.
- **It cannot receive 125 kHz.** The floor is 1 MHz, and the PKES work is three orders of magnitude
  below that. The HackRF is not an LF tool — the Proxmark3 and Flipper Zero are. Don't plan LF work
  around it.

## The parts that matter when repairing one

| Part | Role | Revision note |
|---|---|---|
| LPC4320 (LPC4330FET180) | MCU; USB peripheral; **pin 21 = USB0_VBUS** | the pin that dies in overvoltage deaths |
| MAX2837 | 2.3–2.7 GHz transceiver | all revisions **except r9** |
| MAX2839 | same role, substitution | **r9 uses this** — order the part your revision needs |
| MAX5864 | ADC/DAC | |
| RFFC5072 | mixer / synthesizer | |
| Si5351C | clock generation | |
| XC2C64A | CPLD | bitstream lives in the SPI flash, not the CPLD |
| W25Q80 | SPI flash | firmware + CPLD bitstream |
| U15 | ESD protection diode array on D+/D− | VBUS54CV-HSF-G4-08; Diodes DRTR5V0U4LP16-7 / Semtech RCLAMP0504P suggested as possibly-compatible subs (unverified by GSG) |
| R57 / R58 | 0 Ω, D+/D− to the MCU | |
| R62 / R65 | USB0_VBUS divider | **pre-r7: R62 = 0 Ω, R65 = 10 k (VBUS direct, 5 V). r7+: 10 k / 18 k → ~3.3 V.** |

**Check the board revision before ordering anything.** r9 needs a MAX2839, not a MAX2837.

## Failure modes, with the symptom that identifies each

**1. Not detected — nothing in `lsusb`.** Work down this order:
1. Cable. **Charge-only USB cables are common and produce exactly this symptom.** Test the cable on
   another device that transfers data.
2. PortaPack attached? It must be in "HackRF" mode.
3. VM/WSL? USB passthrough must be configured.
4. **DFU mode: hold the DFU button while plugging in.** It should appear as *NXP LPC4330FET180
   [ARM Cortex M4 + M0] (device firmware upgrade mode)*. If it appears → firmware problem →
   recover the SPI flash. If it does NOT appear in DFU → hardware.
5. If it never appears in DFU and r57/r58/U15 check out, suspect the MCU itself (see #4 below).

**2. Detected, but `hackrf_info` says "No HackRF boards found."** Usually firmware / CPLD, not
hardware. Recover the SPI flash (DFU + `hackrf_spiflash -w`), which rewrites firmware and the CPLD
bitstream.

**3. Front end dead — it runs, but hears nothing.** Symptom: a noise floor that does not change
when the LNA/VGA gain settings change, and no signals even at high gain. Cause: input power over
−5 dBm, or transmitting into a bad load. This is RF hardware damage — the MAX2837/2839, the RF
switch, or an amplifier. Not a firmware problem, and not fixable in software.

**4. Overvoltage death — the classic.** A fast-charge / QuickCharge USB port, or a misbehaving
PortaPack pushing >5 V into VIN (which reaches VBUS through Q5), puts >5 V on USB0_VBUS and **blows
that pin of the MCU**. The only fix is replacing the LPC4320. Tell-tale: the MCU gets **warm** when
connected, and the USB0_VBUS pin draws high current. Do not plug a HackRF into a QuickCharge port,
ever — issue #1221 is exactly this failure.

**5. Big spike in the centre of the spectrum (DC offset).** This is usually **not** a hardware
fault: a common cause is a software version mismatch, e.g. an old gr-osmosdr against newer
firmware. Check versions before touching hardware.

**6. USB connector lifting off the board.** Mechanical, common on well-used units. Inspect the pads
under magnification; a reflow is often the whole repair.

## Baseline numbers to measure and compare

- Current draw: **~180 mA** running, **~70 mA** in DFU mode.
- 25 MHz crystal oscillating at the LPC XTAL pins.
- Rails: 3.3 V and 1.8 V both present and steady.
- **USB0_VBUS (MCU pin 21): ~3.3 V on r7 and later, ~5 V on r6 and earlier** (the pin is 5 V
  tolerant on those revisions, so seeing 5 V there is normal, not a fault).
- With the board connected and powered, there should be **activity on D+ and D−**. None = the
  MCU is not talking to USB, which points at the MCU or the lines to it.
- `dmesg` should change when plugging and unplugging. If it doesn't change in either normal or DFU
  mode, the host never saw an enumeration attempt.

## Is it even a genuine Great Scott Gadgets board?

Ask before ordering parts. In issue #1221 the maintainer's verdict was blunt: *"This is not a Great
Scott Gadgets HackRF"* — clones are widespread, and their parts and schematics differ. Identify the
board first: a genuine HackRF One carries the GSG branding and a serial.

## Tooling

`hackrf_info` identify + version · `hackrf_transfer` raw I/Q RX/TX · `hackrf_sweep` FFT sweep across
a range (the fast "is the front end alive at all" tool) · `hackrf_debug` read/write the transceiver,
mixer, ADC/DAC and clock registers over SPI — **the most informative single diagnostic**, because it
proves the MCU can talk to the RF chips · `hackrf_clock` clock status · `hackrf_spiflash` read/write
firmware and CPLD bitstream · `hackrf_cpldjtag` JTAG CPLD flashing · `hackrf_gpio` test the expansion
pins.

Companion software worth having: `inspectrum` (offline waveform/ASK analysis — the right tool for
LF and OOK work), GQRX (live spectrum), GNU Radio + gr-osmosdr, Universal Radio Hacker (protocol
reverse engineering).

## First plug-in order

1. `lsusb` before and after; check `dmesg` follows the plug/unplug.
2. `hackrf_info`. If "No HackRF boards found", do the DFU test before concluding anything.
3. Current draw if you can measure it (~180 mA / ~70 mA DFU).
4. If it enumerates: `hackrf_debug` register reads to prove MCU↔RF-chip SPI works, then
   `hackrf_sweep` across a known-strong band (e.g. FM broadcast) with gain changes to see whether
   the front end responds.
5. Record every result in the shared ledger with the command that produced it.

## Buttons, and how to actually enter DFU (official procedure)

Two buttons: **RESET** (resets the MCU, causes USB re-enumeration) and **DFU** (invokes the ROM USB
DFU bootloader).

> **To invoke DFU mode: press and hold the DFU button. While holding it, either press and release
> RESET, or power the board on (i.e. plug it in while holding DFU).**

The DFU bootloader lives in ROM and **cannot be overwritten**, which is why a board with damaged
firmware can always be recovered this way. In DFU it enumerates as *NXP LPC4330FET180 [ARM Cortex
M4 + M0] (device firmware upgrade mode)* — that descriptor says 4330 even though the fitted part is
an LPC4320. That is normal, not a mismatch, and not evidence of a clone.

## The MCU: LPC4320FBD144,551

LQFP-144 (20 x 20 mm), 204 MHz Cortex-M4 + M0, **ROMless** — which is exactly why DFU unbricking
always works: the boot ROM is inside the chip, the application firmware lives in the external SPI
flash. Still orderable as of 2026-09 (Newark lists LPC4320FBD144,551 as part 91T5007; brokers show
~USD 7-10). **The MCU is the same across all HackRF One revisions**, so unlike the RF chips there is
no revision guesswork in ordering a replacement.

Reality check before planning a swap: 144 pins at 0.5 mm pitch needs hot air or paste-and-stencil
reflow plus magnification, and the fault that kills this chip (overvoltage on USB0_VBUS, pin 21)
can take other parts with it (U15 on the USB lines). Even a dead board keeps value as a donor — the
RF section, clock, shields and connectors all survive.

## Before powering a suspect board — do this first

If there is ANY visible damage near the MCU, measure rail resistance to ground **before plugging it
in**: 3.3 V, 1.8 V and VBUS. A reading of a few ohms means a short — do not power it, it will cook
further. Then, when you do connect it: **feel the MCU**. The documented tell-tale of the blown-pin
failure is the MCU getting warm while connected. Unplug immediately if it does.

## Distinguishing flux residue from real damage

A brown mark is not automatically damage. **Flux residue** is glossy, amber/clear, and wipes off
with IPA on a cotton bud. **Burnt damage** is matt brown/black, sometimes blistered or cracked,
does not clean off, and usually smells. Also look for solder balls or bridges between the LQFP pins
— common on reworked and clone boards, and a bridge across rails is itself the short.

## Clones, and search-result slop

Identify the board before ordering parts; in GSG issue #1221 the maintainer's verdict was flatly
*"This is not a Great Scott Gadgets HackRF."* Clones differ in parts and schematic.

**Warning about searching for HackRF information:** results from commercialtoolry.com,
tradegradetools.com and sitewisetools.com describe a "HackRF One H4M" / "H4M Clifford Edition" with
Skyworks SKY65113 PA chips, a 40 MHz TCXO and "Rev C" silkscreens. **No such product line exists** —
GSG's revisions are r1-r9 (and HackRF Pro r1.2.1). Those pages are AI-generated SEO text and their
"revision tables" are invented. Ignore anything mentioning H4M.

## Documented repair precedent

Dangerous Prototypes / t4f.org documented a HackRF One that could receive but would not transmit at
medium-high power (low power still worked): **the TX power amplifier stage was blown**. RF-stage
repairs are a normal outcome, distinct from MCU/USB failures. (The full t4f.org article itself was
not retrievable from here — the fetch was blocked as a private-network address, so only the summary
is recorded. Do not claim to have read it.)

## THE DIAGNOSTIC THAT SETTLES IT: DFU enumeration

**If the board will not enumerate in DFU mode, the MCU is not booting.** Reason, straight from the
docs: in DFU boot mode the LPC43xx runs its ROM bootloader and *"the SPIFI is normally unused and
unaltered in DFU mode"*. The ROM bootloader is inside the MCU and does not depend on the SPI flash.
So:

| Symptom | Meaning |
|---|---|
| Appears in DFU | the MCU is alive. Firmware/flash problem. Recoverable. |
| Detected in normal mode, `hackrf_info` fails | firmware/CPLD problem. Recoverable. |
| **Does NOT appear in DFU** | **the MCU is not executing at all.** Check cable, port and power first, then the MCU itself. |

Before calling the MCU dead, rule out, in this order: charge-only USB cable; hub/port; whether the
**3V3 LED illuminates** in DFU (docs: it should on a HackRF One); whether the MCU gets warm when
connected (warm = the blown-pin-21 overvoltage signature); rail-to-ground resistance (a few ohms =
short, do not power it again).

## The complete recovery chain (both commands, in order)

```bash
# 1. DFU boot (hold DFU, then tap RESET / power on while holding), then load firmware to RAM:
dfu-util --device 1fc9:000c --alt 0 --download hackrf_one_usb.dfu
# 2. now that it is running from RAM, write the .dfu's .bin counterpart to SPI flash:
hackrf_spiflash -w hackrf_one_usb.bin
```

Note the two filenames: **`.dfu` goes over DFU, `.bin` goes to SPI flash.** Using a `.bin` over DFU
(the first step) is a documented mistake. Get both from the firmware-bin directory of the latest
GSG release package. `HACKRF_ERROR_NOT_FOUND` from hackrf_spiflash is usually a permissions problem.
After writing, press RESET or replug. Older firmware (< 2021.03.1) also needs a CPLD step:
`hackrf_cpldjtag -x firmware/cpld/sgpio_if/default.xsvf` (three LEDs blink on success).
