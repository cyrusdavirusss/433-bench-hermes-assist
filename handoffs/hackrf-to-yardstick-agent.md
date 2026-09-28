# Handoff → the agent working on the YARD Stick One and the CC1101

**From:** the `kali` instance (profile `default`)
**Date:** 2026-09-22
**For:** the Hermes instance on the other machine, the one helping with the YARD Stick One and the
CC1101 (E07-M1101D) work.

## Why this file exists

The operator asked for the HackRF diagnosis to be handed to you. This is that handoff, plus the
shared-store rules, so you don't have to re-derive any of it.

## How to pick this up

Everything here lives in the shared store. On your machine:

```bash
git clone cyrus@<this-machine>:/home/cyrus/433-bench-hermes-assist ~/433-bench-hermes-assist   # first time
git -C ~/433-bench-hermes-assist pull                                      # after that
```

Then either read this directory directly, or point your own config at it so the shared skills load
for you too:

```yaml
skills:
  external_dirs: [/home/<you>/433-bench-hermes-assist/skills]
```

Every profile on this machine already does that, and it is what stopped the two profiles here from
disagreeing about the same skill.

## What is already verified (do not re-litigate, do not re-run)

Read `~/hermes-private/verifications/verified-facts.md` — it is the ledger, and the HackRF has
seven entries in it. (It moved to the private store on 2026-09-28, when the public half was split
out and this repo was made world-readable.)
Short version of the HackRF state:

- The board **powers up and its firmware runs** (official LED semantics: 1V8 + RF lit means firmware
  is running; TX/RX lit means a receive/transmit is in progress). The MCU is NOT dead.
- The host never enumerated it: only ever a **low-speed USB device failing SET_ADDRESS with
  error -71 (EPROTO)** — across two cables and two ports, ~78 attempts.
- A **bus-level reset** (toggling `/sys/bus/usb/devices/usb3/authorized`) was performed safely, with
  the WD drive on a different bus and unaffected. Afterwards the board went **completely silent** —
  no USB events at all.
- Suspected: a marginal physical link — the micro-B socket or its solder joints, or U15 (the ESD
  array on D+/D-). Repair order: reflow the connector, then remove U15, then R57/R58, then the MCU.
- **A second cable and a second port are already ruled out.** Do not send the operator back round
  the replug loop; it has been done exhaustively.
- DFU mode was **never confirmed reached**. The signature to look for: 3V3 on, **1V8 off, TX/RX
  off**. If TX/RX are lit, it is the firmware running, not the ROM bootloader.

## What is installed on the kali box, if that helps you

`hackrf-tools` 2026.01.3 (info / transfer / sweep / debug / spiflash / clock / cpldjtag), `dfu-util`,
`inspectrum`, `gqrx`. Firmware binaries and the full official release package (including the
**schematics**) are in `/home/cyrus/hackrf-firmware/`. The full diagnosis write-up is
`skills/rf-security-research/references/hackrf-diagnostics.md`.

## Cross-links to your YARD Stick One and CC1101 work

Worth knowing before the two projects get blended, because the frequency ranges decide which tool
can do what:

| Tool | Range | Notes |
|---|---|---|
| HackRF One | **1 MHz – 6 GHz**, half-duplex | not an LF tool. **Cannot do 125 kHz.** Max input −5 dBm or permanent damage |
| YARD Stick One (RfCat/CC1111) | ~300–928 MHz | the right tool for sub-GHz; pairs naturally with the CC1101 work |
| CC1101 / E07-M1101D | 300–928 MHz (module here is 433 MHz) | the transceiver, needs a host SPI and an antenna |
| Proxmark3 | LF (125/134 kHz) + HF (13.56 MHz) | the LF/HF tool the PKES work actually needs |
| Flipper Zero | sub-GHz, LF, HF, NFC | see the operator's own notes on firmware updates erasing AKL/simulator keys |

The shared rule (in `skills/verified-facts/SKILL.md`) applies to your work too: **when you verify
something, record it in `~/hermes-private/verifications/verified-facts.md` in the same turn, with the command that
proved it.** The operator has been burned by an instance that treated "I have no record of it" as
"it didn't happen" — his own project record is authoritative, and re-litigating it wastes his time.

Also recorded there, and relevant if you touch his RF projects: the reported results for the PKES
build (87 cm early accidental open-air, then **3.4 m on the later model before any amplifier
update**), the TC4420 datasheet corrections, and the LF resonance measurement methods for when an
LCR meter reads nonsense.
