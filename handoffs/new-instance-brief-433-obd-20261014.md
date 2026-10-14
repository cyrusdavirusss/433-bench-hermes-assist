# Handoff → the NEW instance on the new laptop: you own the 433 bench and OBD (2026-10-14)

**From:** the `kali` instance (profile `default`)
**For:** the Hermes instance being set up on the new laptop. You have zero context; this file is
written to be read cold.

## 1. Your brief, in the operator's words

The operator is putting this bench — **433 MHz RF work and OBD / J2534 vehicle diagnostics** — under
your direct responsibility. That means:

- The **state of the bench is yours to know**: what is verified, what is open, what was retracted.
- **You drive the work**, not just answer questions about it. Propose the next measurement, run it,
  and report the number that came back — not the number you expected.
- **You record it.** Results go into the stores (sections 6 and 7), in the turn you establish them.
- **You report honestly.** "The rig did not radiate" is a valid result; a plausible-sounding level
  that no instrument returned is a fabrication and the one thing that ends this working
  relationship. An empty capture is an empty capture.
- **Never re-litigate the operator's own record.** Work done on another machine leaves no trace
  here by construction. If you cannot see it, say what the local record shows — never that it did
  not happen.

## 2. First three commands, in order

```bash
git clone https://github.com/cyrusdavirusss/433-bench-hermes-assist.git ~/433-bench-hermes-assist
~/433-bench-hermes-assist/update.sh          # pulls, then tells you whether you can SEE the skills
hermes config set skills.external_dirs '["/home/<you>/433-bench-hermes-assist/skills", "/home/<you>/hermes-private/skills"]'
git clone https://github.com/cyrusdavirusss/j2534-mcp-server.git ~/j2534-mcp-server   # the OBD/J2534 tooling
```

That repo is **public** — it clones with no credentials. `update.sh` is how you update yourself from
then on: this directory *is* the shared knowledge, loaded through `skills.external_dirs`, so there is
no copy step. If it reports the store is **not** in `external_dirs`, the pull changed nothing you can
see — that is the failure that reads as "the update did not work".

The **private** half (`hermes-private`) is a separate clone that needs account access, and it is
where the ledger and the car/keys material live. Ask the operator for that access; the public half
never needs it.

## 3. Read in this order

1. **This file**, then the other files in `handoffs/`, newest first — each is the frozen state of a
   session, written for an instance with no context.
2. `skills/rf-security-research/references/cc1101-bench-firmware.md` — the durable bench record:
   pinout, register image, the BW=58 finding, the loose-MISO signature, the host command reference.
3. `skills/rf-security-research/SKILL.md` — the working protocols for this project.
4. `diagnostics/` — the HackRF full diagnosis and the two RF reports as posted/reviewed.
5. `skills/j2534-vehicle-diagnostics/SKILL.md` — the car side: J2534/OBD method, preconditions and
   findings, plus the public tooling repo it points at.
6. The **private** ledger (`verifications/verified-facts.md`) — every fact that has been CHECKED,
   with the command that proved it. It is the closest thing to ground truth this project has.

## 4. Where the 433 bench stands — verified, do not re-derive

- **Rig**: ESP32 (classic) + E07-M1101D CC1101, firmware `fw=1.0.0`, CP2102 serial at 115200.
  Command set: PING/INFO/CFG/RX ON|OFF/TX OPT|RAW/STOP/SCAN/RSSI/STATS/CAP/REG/REGS. On Windows the
  same rig enumerates as `COM8`; on Linux it is `/dev/ttyUSB0`.
- **Rig RX: good.** Reads a −57.5 dBm carrier on demand; synthetic PT2262 frames arrive as 53 frames
  with exactly 26 edges each and clean 1T/3T widths (350/1050 µs).
- **Dongle TX (YARD Stick One, CC1111): verified.** −48.5…−57.5 dBm into the rig. The PA must be set
  explicitly (`setMaxPower()` **and** `setPower(0xC0)`) or it reports success and radiates nothing.
- **Dongle RX: works — with a decent antenna.** −67 dBm peak, 40.5 dB spread, demodulating bytes.
  The earlier "deaf receiver, transmit-only" verdict was measured on a DIY quarter-wave whip with no
  counterpoise; that was the antenna, not the radio. rflib's RX goes unstable on long runs
  (`USBTimeoutError(110)`) and then needs a **physical replug** — never USB-reset the dongle.
- **`CFG BW=58`, not the firmware's 100.** At 100 kHz the same OOK transmission arrives as 800+
  chatter edges with smeared widths; at 58 kHz it is 26–32 edges with clean 1T/3T. Costs ~1.5 dB of
  level. **Volatile** — the rig's image restores `bw=100` on boot/RESET.
- **A loose MISO (E07 pin 7) presents as write-OK / read-corrupt.** RSSI, REGS, STATS and MARCSTATE
  all lie while the radio keeps being configured; the pulse path still works because GDO0 is a
  separate pin. Signature: RSSI readings landing on exactly **−74.0 dBm** (raw 0x00 = no data).
  Proved fixed with `scripts/spi_stress.py`.
- **The gate remote does not radiate.** Five sessions, contact range, squelch wide open, plus a
  433.0–435.0 sweep: nothing, on the rig and on the operator's car-key tool.
- **Retracted claims — never repeat them:** "the ESP32's transmit does not radiate" (measured on a
  bad antenna) and "the dongle is a deaf receiver" (same cause).

**The one open question you inherit: rig TX is unverified.** The tool for it is already written —
`scripts/rig_tx_verify.py`, dongle as receiver, both devices plugged in. That is the cheapest real
result available to you, and it settles a claim that was retracted once.

## 5. 315 MHz — the car half of the bench

- The operator's **car key is ~315 MHz** (the car-key tool read 312 & 314). That is **outside the
  E07's 387–464 MHz range**, so the rig can never see it. Do not use it as a 433 reference.
- The **YARD Stick One (CC1111) covers 300–348 MHz** — it is the only radio on this bench that can
  reach the car key's band. Anything at 315 is dongle work, not rig work.
- The **315 MHz noise ceiling moves between sessions**: a quiet-band floor of −107.0 dBm has shown a
  **+10.5 dB** ambient ceiling on one night and **+17.0 dB** on another. A reading near +17 dB over
  floor is *still ambient, never a press*. Re-take the control whenever the antennae move. The phone
  bench app encodes the same rule: at or below +17 dB at 315 is the room.
- LF/immobiliser work (125 kHz) and PKES relay work are **not** covered by any radio on this bench
  yet — that is a capability question to raise with the operator, not a code problem.

## 6. The OBD / J2534 half — where it actually lives

**J2534 (PassThru) diagnostics is a PUBLIC repo and clones with no credentials:**
`cyrusdavirusss/j2534-mcp-server` — J2534 PassThru device control, ISO15765/UDS, Toyota enhanced
mode 0x21 `read_lid`, 12,000+ DTCs across 33 brands, SAE J1979 PID decoding, and the bench scanners
(Toyota UDS scan, VAG UDS scans on a 2010-era A4, cranking/stall samplers, pedal-sweep sampler).

- **`skills/j2534-vehicle-diagnostics/` in this store is now the method skill** — read it before
  touching a car. It carries the Windows/32-bit-Python preconditions, the one-ISO15765-filter-at-a-
  time limit of the clone VIM, `7F 19 13` being a refusal rather than an all-clear, and the
  dropout-logging method for intermittent supply/ground faults.
- **This work is Windows-side.** It needs a Windows host, 32-bit Python (`C:/Python311-32/python.exe`
  for the PE32 `MVCI32.dll`) and the J2534 PassThru DLL; a **Linux instance cannot run it locally**
  and must drive a Windows host instead. Establish which you are before promising a scan.
- **One owner of the cable:** the MCP server or a script, never both at once.
- The Toyota ECU map is **not** established — `toyota_scan.json` shows 8 filters installed with empty
  `probes` and `functional`. That is an unresolved run, not a negative result about the car.

**There is no OTHER OBD skill anywhere.** Do not "recall" OBD procedures — that is inventing them.

What *does* exist is car/keys material that currently lives only in the operator's local profile
tree on the kali box — it is **not in either store yet**, which is why you will not see it after the
clone. It is: the car-key tool's capability matrix (the tool is **OBD-only** — no bench/EEPROM/MCU
work), the Toyota immobiliser module version history, the region-lock findings on All-Keys-Lost
functions, vehicle electrical/fuse diagnostics with workshop-manual sourcing, and the
hardware-security-research protocols that cover RF/PKES/automotive work. Expected home is the
**private** store under `skills/`. **Ask the operator to publish it, and ask which tools he actually
has** — do not proceed on assumed capability.

**Not yet in the store either:** the phone bench app tree and the phone-multitool-app research note
are local to the kali box and uncommitted, so they will not arrive with a clone. If you need them,
say so rather than reporting them missing.

## 7. The rules that cost time if broken

- **The public half is the bench only. Nothing personal goes in it** — no addresses, hostnames,
  internal IPs, credentials, plates, VINs or target lists. `publish.sh` routes by name and **fails
  closed**: only `rf-security-research` goes public; everything else, including a typo or a new
  skill, goes private.
- **A ledger of everything-checked cannot live in a public repo.** Facts go to the private ledger;
  procedures go to skills; task-local facts go nowhere.
- **Edit in the local profile tree, then publish.** Editing the store copy first loses the edit
  silently — the publish run overwrites it and still reports success. Read the change back out of
  every copy afterwards rather than trusting the summary.
- **A handoff is a FILE, not a chat message.** Write `handoffs/<topic>-<date>.md`, then tell the far
  instance to read that file.
- **Record every figure with its provenance**: who reported it, when, and whether it was ACHIEVED or
  a FORECAST with a fault corrected. Never quietly overwrite a figure the operator gave you; flag
  the conflict and ask.
- **The rig's firmware parses `REG` arguments as DECIMAL** — TEST0 (0x2E) is `REG 46 11`, not
  `REG 2E 0B`. Hex input silently writes a different register.
- **Never open the rig's serial port from a second process** while a capture owns it — it kills the
  capture with "device reports readiness to read but returned no data".
- Run `scripts/bench_selftest.sh` first (~75 s) — knowing the bench is sound before debugging
  through it is most of the debugging.

## 8. Other machines

The Windows box has its own instance and its own handoffs in this same store (the `rf433-pause-*`
and `gate-code-job-standby-*` files, and a Windows-bench half of the ledger). Pull before you
conclude anything about "the current state" — you may be reading a night that has since moved on.

---

*Written 2026-10-14 by the kali instance at the operator's request. Public-safe: bench material
only. Correct this file rather than working around it; it is the entry point every new instance
reads first.*
