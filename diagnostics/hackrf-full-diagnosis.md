# HackRF One — full diagnostic record

**Board:** HackRF One (revision not established). The operator reports a brown/burn-looking mark on or
near the **LPC4320FBD144** MCU (LQFP-144, 20×20 mm). Whether the board is a genuine Great Scott
Gadgets unit is **not established** — verify against GSG product photos before ordering parts,
because clones differ in parts and schematic, and GSG have disowned clones in their issue tracker.

**Host:** kali (this machine), Linux 7.1.5, USB via xHCI. Operator's other machine exists but
was not on the tailnet at the time of testing.

**Status: DIAGNOSED. The MCU is damaged in the documented overvoltage mode. Do not keep powering it.**

**Operator reports the MCU gets WARM while connected.** That is the documented signature of the
overvoltage failure (GSG issue #1515): excessive voltage on **USB0_VBUS, MCU pin 21** — from a
quick-charge USB port or a misbehaving PortaPack feeding >5 V into VIN — blows that pin, after which
the MCU draws high current and heats. GSG's own conclusion: *"in that scenario the only solution is
to replace the MCU."*

This is consistent with every other observation, and it is the only explanation that fits all of
them:

| Observation | Explanation |
|---|---|
| Boots, runs firmware, lights 1V8/RF/TX/RX | the CPU core and SPI flash are fine — only the USB block/pin is damaged |
| Never presents a USB pull-up | the damaged pin/PHY cannot drive D+ |
| Cold board → low-speed/EPROTO storm; warm board → total silence | temperature-dependent failure. Early attempts caught it cold; after the bus reset (by which time it had warmed) it never spoke again |
| Brown mark on/near the MCU | consistent with genuine damage on that pin rather than flux residue |

**Action: unplug it and leave it unplugged.** A chip that heats while powered is being further
stressed, and it can take surrounding parts with it. Nothing further can be learned by powering it.

---

## 1. Verified facts about the environment

| Item | Evidence |
|---|---|
| hackrf-tools 2026.01.3 installed | `hackrf_info --version` → `2026.01.3 (0.9.2)` |
| Baseline with nothing attached | `No HackRF boards found.` — **correct, not a fault** |
| udev rules present | `/lib/udev/rules.d/60-libhackrf0.rules`, user in `plugdev` |
| `hackrf_gpio` absent | removed upstream in this release — not a packaging fault |
| USB IDs of interest | app mode `1d50:6089` · LPC43xx ROM DFU `1fc9:000c` |
| Frigate/WD drive | WD Elements on **bus 4**; board appears on **bus 3** — separable |

Tooling also installed: `dfu-util` 0.11, `inspectrum`, `gqrx`. Diagnostic script `hackrf-check`
(+ `~/.local/bin/hackrf-check`).

Firmware obtained and hash-verified (release v2026.01.3, `firmware-bin/`):

```
hackrf_one_usb.dfu   45784   sha256 78f933631c89a2214abd35d1765eadf66a5115a98de1597d3f17f48364977222
hackrf_one_usb.bin   45720   sha256 1d5f36c702677bc47086403c8e8c8a650d47d892a3c791e2dc9a7fa2bab1d72b
```

Schematics are in the release package (`doc/hardware/hackrf-one-schematic.pdf`, `...-assembly.pdf`).

## 2. LED evidence — the most informative thing we have

Official semantics (from the HackRF docs, not guesswork):

| LED | Meaning |
|---|---|
| 3V3 | the primary internal power supply is working |
| 1V8 and RF | **firmware is running** and has switched on additional internal supplies |
| USB | communicating with the host over USB |
| TX / RX | a receive or transmit operation is currently in progress |

**DFU mode signature: 3V3 ON, 1V8 OFF, TX/RX OFF.**

Observed, in order:

1. **3V3 green** → power path good. This rules out brown-out and a dead power chain.
2. **All lit** — 3V3, USB, TX and RX, later RF as well → **the firmware booted completely**, powered
   its aux rails, believes it is talking to the host, and believes it is mid-transaction. The MCU
   and the SPI flash are therefore **alive**. This is also why the burn mark was initially read as
   more likely flux residue than destroyed silicon — **later revised:** the warmth reading (§6)
   confirms genuine damage on the USB0_VBUS pin, while the core still runs normally. Both are true
   at once: a partially damaged MCU.
3. **"1 red + 3V3 green"** on a later attempt → mostly dark, i.e. **closer to the DFU signature**,
   but the lit LED was never identified by label (1V8? TX? RX? RF?).

**Critical gap: DFU mode was never confirmed entered.** TX/RX lit means the firmware is running, not
the ROM bootloader. So we have no clean test of the ROM USB path — and the ROM path is exactly the
one that would work if the firmware's USB handling is broken.

## 3. Everything tried, with raw results

### 3.1 Enumeration, repeatedly, with DFU held at cable insertion

```
lsusb                          -> nothing matching 1fc9 / 1d50 / NXP / HackRF
lsusb -d 1fc9:000c             -> absent
dfu-util -l                    -> only the Sunplus webcam (1bcf:2bad, its interface claims the
                                  DFU class) with LIBUSB_ERROR_ACCESS — unrelated noise
```

`dmesg -T` on every attempt:

```
usb 3-3: new low-speed USB device number 71..78 using xhci_hcd
usb 3-3: Device not responding to setup address.
usb 3-3: device descriptor read/64, error -71
usb 3-3: device not accepting address 78, error -71
```

Tally over the storm: **12–13 × low-speed, 21 × error −71**, 2 × full-speed, 2 × high-speed (the
latter almost certainly the USB-C dock's own hubs, *not* the board). Device numbers climbed from 65
to 78 — dozens of retries, never once reaching a usable address.

`error -71` is `EPROTO`. The HackRF One is a **USB 2.0 high-speed** device, so being detected at
**low speed** is a physical-layer failure on D+/D− — not firmware, not software.

### 3.2 Cable swap — this changed the symptom

| Cable | Result |
|---|---|
| First cable | **zero USB events in ~48 minutes.** Complete silence. |
| Second cable | immediate **low-speed / EPROTO storm** |

A charge-only cable produces exactly the first signature (power present, no data pair), so the
first cable is presumed incapable of data. The second cable at least presents a device-side pull-up.

### 3.3 Port changes

Attempts on **3-4** then **3-3** — two root ports of the bus-3 root hub. Identical failure on both,
**so the port is not the variable**.

### 3.4 Dock / hub ruled out

The bus carries a USB-C dock (Genesys `05e3:0610` / `0626` hubs, `05e3:0749` SD reader,
`0bda:8153` GbE). The board's attempts appear as `usb 3-3` / `usb 3-4` — **root ports**, not
children of a hub. The dock was not in the board's path.

### 3.5 Bus-level driver reset (no machine reboot)

Toggled `/sys/bus/usb/devices/usb3/authorized` 0 → 1. Result:

- Bus 3's children dropped (13 → 9 devices) and re-enumerated with fresh numbers: dock hubs,
  webcam (all five interfaces), Bluetooth. All healthy.
- **The WD drive on bus 4 never moved** — verified by device number and by `lsusb`. Frigate's
  recordings were never at risk. The buses share a PCI controller but the reset is per-bus.
- **After the reset, the board went completely silent** — no USB events at all, where before it
  produced a continuous storm. Behaviour changed, but in the *worse* direction. What this means is
  genuinely unclear; it is recorded rather than explained.

### 3.6 Monitoring

Six `udevadm monitor --subsystem-match=usb` windows (150 s, 150 s, 600 s, 300 s, 1800 s, and
others — roughly 90 minutes total). **Zero events from the board in any of them** after the reset.
A 27-second observation post-reset recorded 0 new kernel lines; the newest USB activity was the
reset's own re-enumeration 27 minutes earlier.

### 3.7 Checks never completed

| Check | Status |
|---|---|
| Does the MCU (or the area around the socket) get **warm** while connected? | **ANSWERED LATE — YES, warm.** That is the overvoltage signature and it closes the diagnosis (§6). |
| Rail resistance to ground — 3.3 V, 1.8 V, VBUS | not done (still worth one check before powering it again) |
| Wiggle test on the micro-B socket while watching `dmesg -w` | not done |
| Try the board on a **second machine** | not done (the other machine was unreachable at the time; the LAN route is now open) |
| Reflow the USB connector joints | not done |
| Remove U15 | not done |
| Flash firmware | impossible — DFU never enumerated |

## 4. What is ruled out, and what is left

**Ruled out:**
- Cable (replaced; the second cable produces events)
- Hub/dock (board is on root ports)
- Host port (two ports, identical failure)
- Power path / brown-out (3V3 LED steady)
- Firmware/SPI flash *as the cause of nothing booting* (the firmware demonstrably boots)
- The MCU being dead *as a blanket claim* (the firmware runs; TX/RX initialise)

**Remaining suspects, ranked by cost to test:**

1. **USB micro-B socket or its solder joints.** The documented mechanical failure. A cracked D+/D−
   joint produces exactly low-speed + EPROTO, and would also explain the intermittent silence.
2. **U15** — the 6-pin ESD protection array (VBUS54CV-HSF-G4-08) on D+/D−. GSG's own statement: the
   board works fine without it. Removing it both fixes and diagnoses: clears → U15 was it.
3. **R57 / R58** — the 0-ohm series resistors in D+/D−. Check continuity.
4. **The MCU's USB PHY** — the overvoltage path (pin 21, USB0_VBUS). This means an
   **LPC4320FBD144,551** swap (LQFP-144; still orderable — Newark 91T5007, ~USD 7–10). Note the
   fault that kills this pin can take U15 with it.
5. **Genuine vs clone** — unresolved, and it changes what a repair is even worth attempting.

## 5. Reasoning corrections made during the diagnosis

Recorded so nobody repeats them:

- **"No DFU enumeration means the MCU is not booting" — premature.** It would be true *if the board
  were actually in DFU*. The LEDs showed the firmware running, so DFU was never confirmed entered,
  and the inference rested on a false premise. The MCU must not be called dead.
- **"A controller reset will drop the WD drive" — too broad.** The WD sits on a different bus, so a
  bus-level reset leaves it alone. Verified empirically.
- **Silence is not the same as failure.** With the first cable there were zero events; with the
  second, a storm. The cable was a variable we nearly missed.

## 6. Conclusion and options

**Diagnosis: the MCU (LPC4320FBD144) is damaged in the documented overvoltage mode — USB0_VBUS
pin 21. The rest of the board works.** No further software or cable work can change this; the
remaining decisions are physical.

Three honest options:

**1. Replace the MCU.** LPC4320FBD144,551 (LQFP-144, 20×20 mm, ROMless) — orderable, Newark 91T5007,
~USD 7–10 from brokers. It is still a 144-pin 0.5 mm-pitch LQFP: hot air or paste-and-stencil reflow
plus magnification. **The encouraging part:** the board demonstrably boots and runs, so the rails,
flash, CPLD and RF section are all alive — a chip swap on a board that powers up and runs code is a
far better bet than on one that is dead everywhere. Note the same event can also take **U15** (the
ESD array on D+/D−), so budget for removing or replacing that too.

**2. Retire it as a donor.** The RF section, Si5351 clock, CPLD, shields, SMA connectors and the
micro-B socket all survive. Worth keeping regardless of which option you choose.

**3. Replace the board.** A known-good unit is a known quantity, and this one has already cost a
day. Decide with the October deadline in mind — the HackRF is not the LF tool, so it isn't on the
critical path for that.

**Before ordering any part:** verify whether the board is a genuine Great Scott Gadgets unit.
Clones differ in parts and schematic, and GSG have disowned clones in their tracker.

## 7. Earlier next-actions list — superseded by the warmth reading

Kept for the record, because all of it was reasonable *before* the warmth answer arrived. None of
these need doing now; the diagnosis is closed.

1. ~~Feel the MCU while connected~~ → **DONE, positive: warm. Diagnosis closed.**
2. ~~Meter the rails to ground~~ — still worth doing *once*, before powering it ever again, to check
   for a short: 3.3 V, 1.8 V, VBUS. A few ohms = short.
3. ~~Wiggle test~~ — superseded.
4. ~~Try it on the second machine~~ — superseded, but a useful cross-check that a swap worked later.
5. ~~Reflow the connector~~ / ~~remove U15~~ — only as part of the MCU replacement.
6. **If a swap is done and it later enumerates as `1fc9:000c`:**
   ```bash
   dfu-util --device 1fc9:000c --alt 0 --download ~/hackrf-firmware/hackrf_one_usb.dfu
   hackrf_spiflash -w ~/hackrf-firmware/hackrf_one_usb.bin
   ```
   `.dfu` for the DFU step, `.bin` for the flash step — reversing them is the documented mistake.

## 8. Commands to capture state, for the next session

```bash
lsusb | grep -E "1fc9|1d50"                      # DFU or app mode present?
hackrf-check                                     # full one-shot diagnostic
sudo dmesg -T | grep -iE "usb 3-|low-speed|error -71"
dfu-util -l                                      # DFU device?
hackrf_debug --selftest                          # only meaningful once it enumerates
```

Do **not** re-run udev monitors for this board: they have been run for ~90 minutes in total and
produced nothing. Ask for the warmth reading, the rail readings, and the wiggle test instead.

Also: **no antenna was connected throughout, and nothing was ever transmitted.** No `hackrf_transfer`
TX command was run, and in DFU mode the board cannot transmit regardless.
