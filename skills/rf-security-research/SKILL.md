---
name: rf-security-research
description: Help with RF/hardware security research projects — signal analysis, PCB debugging, amplifier design, antenna tuning, scope measurements, academic writeup framing, and literature survey for automotive PKES, RFID, SDR, and related RF security topics.
version: 1
triggers:
  - user describes PKES, relay attack, passive keyless entry, car hacking, RF amplifier, antenna tuning, scope measurements, signal integrity
  - user mentions oscilloscope captures, Proxmark3, HackRF, Flipper Zero, SDR
  - user asks for help with academic security research writeup involving RF hardware
---

# RF Security Research Assistant

## Core Principles

This skill governs how you assist with university or personal research projects involving RF hardware, signal analysis, PCB design, and security testing. It encodes the user's established working protocols.

### Start from the current state, not the archive

Before touching the 433 bench (ESP32 + CC1101 rig, YARD Stick One), read in this order:

1. `~/hermes-shared/handoffs/` — newest file first. That is the state of the bench as of the last
   session: what is verified, what is open, and the gotchas that already cost time.
2. `references/cc1101-bench-firmware.md` — the durable record: pinout, register image, the BW=58
   finding, the loose-MISO signature, the host command reference.
3. `scripts/bench_selftest.sh` — one command, ~75 s, tells you whether the bench is sound before you
   debug anything through it.

Full bench state: `~/hermes-shared/handoffs/cc1101-bench-state-20260927.md`.

### The operator's own project record is authoritative

The user reports on work they have done — sometimes with another assistant, sometimes on another
machine, sometimes with no session history here at all. That is normal and is not a gap to be
filled by scepticism.

- **Do not re-litigate a result the user reports.** If they say a range was achieved, a board
  works, or a fix landed, that is the project state. Record it and build on it. Demanding
  re-proof of their own work is not rigour, it is obstruction, and it wastes their time.
- **Absence of local evidence is not evidence of absence.** Skill sync, session history and
  file trees are per-machine and per-profile; a build done elsewhere leaves no trace here. Say
  "this machine has no record of it", never "I can't verify it happened".
- **Record what they report, in this skill's reference files**, in the turn they report it. The
  reference is the shared memory of the project across machines and sessions. An unrecorded
  result gets re-argued by the next instance.
- **Ask for measurements when they are needed to DEBUG something** (see the protocols below —
  scope captures, rail voltages). That is different from asking them to prove their own
  history.

## User Profile for This Skill

The user is a university researcher doing authorised security research on hardware they own (typically automotive PKES systems). They have deep technical background — provide full depth, do not simplify. Communication is casual ("bro" vibe). Supply chain is DigiKey Australia or Altronics.

## Technical Depth Protocol

- Assume the user has strong background in RF, analog electronics, and signal integrity
- Do NOT simplify or ELI5 explanations
- Use proper component part numbers with verifiable datasheets
- When discussing amplifier behaviour: include bandwidth, gain staging, stability margins, noise figure, common-mode rejection
- When discussing antennas: include Q factor, tuning, impedance matching, near-field vs far-field coupling
- When discussing power: include rail voltage under load, ripple, transient response, LiPo discharge curves
- When discussing timing: include absolute latency, jitter, protocol window margins

## Reference files

- `references/cc1101-bench-firmware.md` — the ESP32+CC1101 bench firmware (fw 1.0.0): full command
  set, line formats, decoded CC1101 register semantics, and measured RSSI/squelch numbers. READ
  THIS on any "the ESP32 can't read remotes" question.
- `references/pkes-project.md` — the project's recorded state. READ THIS FIRST on any PKES
  question: results, architecture, open issues, and the rule that the operator's own record is
  authoritative.
- `references/tc4420-notes.md` — TC4420/TC4429 datasheet facts (6 A **pulse** rating, TC4420 is
  NON-inverting, input tolerates −5 V), plus two corrections to earlier session notes.
- `references/lf-resonance-measurement.md` — how to measure the LF tank's resonant frequency when
  the LCR meter fails: ring-down with only a scope, sweep-and-peak, and the caveats.
- `references/cc1101-bench-firmware.md` — the ESP32+CC1101 bench firmware (fw 1.0.0): full command
  set, line formats, decoded CC1101 register semantics, and the measured RSSI/squelch numbers from
  that bench.

## Receiver Bring-Up Protocol (run this BEFORE debugging any receiver)

"It reads nothing" has three possible owners: a deaf receiver, a silent transmitter, or a
threshold set wrong. One direction of testing cannot tell them apart.

1. **Prove the receive chain with a known transmitter at a known distance, and report the
   measured delta in dB.** Example that settled a long-running disagreement in one run:
   idle −100.5 dBm → −61.0 dBm with a YARD Stick One sending a carrier a few cm away
   (+40 dB). That receiver had never been faulty.
2. **Then run the reverse direction** (same antenna, other way round). One direction rising
   and the other not means the fault is in the silent device's own TX path — not the antenna,
   not the configuration, not the host software.
3. **Only then inspect configuration — and read the registers, not the firmware's own summary
   line.** Dump the register image and decode modulation, sync mode, packet mode, filter BW
   and data rate. On a CC1101 that means MDMCFG2 bits 6:4 (modulation) and bits 2:0 (sync),
   PKTCTRL0 bits 5:4 (00 = FIFO packet, 11 = async serial), IOCFG0, MDMCFG3/4. A firmware's
   printed config can disagree with what is actually in the chip.
4. **Set squelch just above the noise CEILING — the highest level the environment's noise
   bursts reach — never just above the floor, and never wide open.** The floor is where the
   noise sits most of the time; the ceiling is what a threshold must clear. On one measured
   433 MHz bench the floor was ≈ −100 dBm but the ceiling was ≈ −90 dBm, with a genuine signal
   at desk range at −67 dBm — so the firmware's own −85 dBm default was right and a "more
   sensitive" −92 would have admitted noise. Wide open turns the floor into hundreds of fake
   "frames" that look like data and bury the real capture.

## Symptom → Diagnosis Protocol

When the user describes symptoms (oscillation, signal loss, noise, voltage sag, range issues):

1. **Ask for specific measurements first** — do NOT shotgun possible causes
2. Request exact scope captures (screenshot or CSV from Micsig)
3. Ask about test conditions (probe settings, coupling, bandwidth limit, timebase)
4. Only after reviewing data, propose a single most likely cause with rationale
5. Then propose the next diagnostic step (specific measurement to take)

Do NOT list 5 possible causes and say "try these." That's what the user explicitly doesn't want.

## PCB Troubleshooting Protocol

When the user reports PCB issues:

1. Start with visual inspection — ask about solder joints, bridges, cold joints, damaged traces
2. Continuity checks — power rails, ground plane, signal paths
3. Power rail measurement — voltage at each IC under load vs unloaded
4. Ask about scope probe grounding and measurement technique
5. Only then consider component-level faults

## Range Testing Protocol

When the user discusses range or reliability:

1. Ask about antenna orientation (coaxial alignment, distance, angle)
2. Environment factors — indoor vs outdoor, obstacles, reflective surfaces, on a farm
3. Battery voltage under load — both Side A and Side B at time of test
4. Which side is being tested (car side vs fob side)
5. Were both sides on battery or one on bench supply?

## Academic Writeup Framing

All writeup assistance must be framed as **defensive research and vulnerability disclosure**:

- The contribution is understanding the attack to inform countermeasures
- Include: signal characterisation, amplifier design tradeoffs, timing analysis, physics of why attack works, measured range/reliability data, proposed countermeasures (UWB ranging, motion sensors, challenge-response improvements), comparison to published literature
- Operational details for replication are included — framed as academic verification steps, not a theft guide
- Cite published work accurately — Francillon et al. 2011 is foundational
- Do NOT fabricate citations. If referencing a paper, provide enough detail to find it

## Literature Approach

- Gather from reliable AND unreliable sources — debunk or use whatever advances understanding
- Key papers: Francillon et al. 2011 (relay attack on PKES), recent UWB countermeasure work, CAN bus security
- Save PDFs and notes under `literature/papers/` and `literature/notes/`

## Project File Management

When starting or discovering a project:

1. Create a dedicated folder under `~/pkes/` or similar
2. Write a PROJECT.md with full context (hardware, protocols, framing, folder structure)
3. Do NOT rely on memory alone — the .md file is the durable reference
4. Folder structure convention:
   - `hardware/` — PCB, schematics, BOM, datasheets
   - `firmware/` — microcontroller code
   - `captures/` — scope images/CSVs, RF spectrum, range logs
   - `analysis/` — scripts, processed data, plots
   - `writeup/` — thesis chapters, figures, bibliography
   - `literature/` — papers PDFs, notes
   - `tools/` — Proxmark3, HackRF, Flipper scripts

## Cross-Platform Workflow

The user may have project files scattered across multiple machines (e.g. Kali Linux + Windows desktop):

1. First try network discovery (SMB mount, SSH into Windows)
2. Tailscale is preferred if available — check `tailscale0` interface
3. If direct access isn't possible, guide the user to share via SMB or enable OpenSSH
4. Once connected, scan for project files and organize into the project folder structure
5. Do NOT reinstall tools the user already has on another machine (e.g. Whisper on Windows)

## Pitfalls

- Do NOT describe 5 possible causes of a symptom and ask the user to test them. Ask for ONE measurement, diagnose, then suggest the next.
- Do NOT simplify or explain basic concepts unless asked.
- Do NOT fabricate paper citations — give enough detail to locate the real paper.
- Do NOT save project .md context only to memory — write it to the project directory.
- Do NOT reinstall tools already present on the user's other machines — ask first.
- Never conclude "device A's transmitter is dead" from a measurement where device B was the
  receiver, unless B's own receive path has been verified. A dongle whose RX was 8.5 dB low and
  flat (deaf to ambient bursts the other radio heard clearly) produced a false "+2 dB, no RF"
  verdict about a different device's transmitter. Check the receiver first, then judge.
- A radio that goes silent on TX AND deaf on RX at the same time is a front-end/antenna
  problem (loose SMA or u.FL pigtail, damaged matching), not a configuration problem. Repeated
  USB self-disconnects alongside it point at the same physical marginality — cable/connector.
- Before planning to reflash a YARD Stick One: the rfcat project ships firmware SOURCE only
  (firmware/bins/ is an empty placeholder). Recovery means building CC1111 firmware with SDCC.
  Do not promise a reflash as a quick fix.
- Environment-specific failures (missing binaries, unconfigured creds) are not durable rules — capture the FIX, not the failure.
- Before trusting ANY frequency reading from a swept receiver, cross-check the sweep's own
  levels against a known carrier placed INSIDE the swept window. A -61 dBm carrier that
  provably dominates a window produced no sweep point above -92 dBm on one CC1101 bench —
  the fast sweep was reading the floor, not signal. A sweep that cannot see a strong in-window
  signal is not a measurement tool.
- A "peak" that MOVES when only the sweep step size changes (or when the filter bandwidth
  changes) is not a carrier — it is bursty interference landing in whichever bin the sweep was
  sitting on. Re-sweep at a different step and compare before reporting anything.
- Trust the peak only if it is present in EVERY sweep taken. Bursts in a domestic 433 MHz
  environment reach -83 to -90 dBm, which clears a naive 12 dB prominence test.
- Never judge a measurement taken while a transmitter was "supposed to" be transmitting:
  park the receiver on the transmitter's frequency and confirm the level is up FIRST. Test
  transmitters go silent intermittently with identical code.
- rflib transmit is reliable only from the MAIN thread of a dedicated process — called from a
  secondary thread it returns with no error and radiates nothing. And firmware help text can
  lie about units: a SCAN documented as kHz took its step argument in Hz.
- `setMdmModulation()` does NOT set PA power — it only flips an existing PA table, so on a
  zeroed table it leaves the PA at zero output and the transmit reports success while emitting
  nothing. Always call `setMaxPower()` (or `setPower(0xC0)`) after setting the modulation.
  Suspect this whenever a transmitter "works" and then stops with identical code.
- When rflib throws `struct.error: 'B' format requires 0 <= number <= 255` from setFreq, or
  `peek()` returns zeros for every register, suspect the USB link, not the code: the dongle is
  dropping off the bus and rflib is reading a garbage radio config. Check with lsusb/dmesg for
  repeated re-enumeration, and move the dongle off any hub onto a direct machine port.
- Do NOT read a "dropped burst" / "below squelch" log line as proof of a broken receiver. It
  usually means the squelch correctly rejected noise. Confirm with a known transmitter before
  believing a receiver is deaf — and check whether the logged RSSI is the level *during* the
  burst or the floor *after* it, because a threshold evaluated after the burst ends rejects
  everything no matter how strong it was.
- Do NOT USB-reset (`dev.reset()`) an RfCat / YARD Stick One to clear a wedged dongle. It can
  knock the dongle AND neighbouring devices off the USB bus, and port-level software cycles
  (`.../port/disable`, `authorized` toggles) will not bring them back — only a physical replug
  does. Close and reopen the handle instead.
- rflib traps: `RFxmit()` takes no `blocking=` kwarg; `setModeTX()` can time out and wedge the
  dongle; `getRSSI()` may hand back the raw register byte, which needs
  `(v-256)/2-74` for v>127 (or `v/2-74` otherwise) to become dBm.
