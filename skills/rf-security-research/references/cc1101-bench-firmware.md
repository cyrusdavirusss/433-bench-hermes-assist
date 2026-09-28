# ESP32 + CC1101 bench firmware (fw 1.0.0)

The user's ESP32 bench rig runs a purpose-built firmware with a textual command set over
115200 baud serial (CP2102 bridge, `/dev/ttyUSB0`). It is a RAW CAPTURE tool: it emits edge
durations, it does not decode protocols.

## Command set (from its own boot banner)

```
PING INFO CFG [FREQ= DR= BW= SQUELCH= GAP= PWR= INV=]
RX ON|OFF  TX OPT REPEAT=<n> GAP=<ms>  TX RAW <us..>  TX STOP
SCAN <f0> <f1> <step_kHz> <dwell_ms>  RSSI  STATS
CAP LIST|GET <n>|CLEAR  REG <addr> <val>  REGS  STROBE <cmd>
SELFTEST  LOG 0|1  RESET  HELP
```

Settings are written through `CFG` with `KEY=VALUE` (e.g. `CFG SQUELCH=-92`). Sending a bare
`SQUELCH=-92` returns `ERR unknown command`.

## Line formats

```
RDY fw=1.0.0 chip=ESP32 layout=vspi-documented cc1101_partnum=0x00 cc1101_version=0x14
    spi=ok gdo0=4 csn=5 sck=18 mosi=23 miso=19 gdo2=27
CFG freq=433.9200 dr=4.80 bw=100 pwr=0xC0 squelch=-85.0 gap=15000 rx=0 inv=0
INFO fw=1.0.0 cc1101_partnum=0x00 cc1101_version=0x14 marcstate=0x0D rssi=-102.5 rx=1
STATS rx=0 drop=0 noise=68 edges=3673 ovf=0 tx=0 uptime_ms=3987
RSSI -102.5
FRAME <seq> <t_ms> <rssi> <lvl> <dur_us> <edge durations in us, ~25.6 us quantisation>
LOG dropped burst n=<edges> rssi=<rssi> (squelch <threshold>)
LOG cap <idx> seq=<seq> t_ms=<t_ms> rssi=<rssi> n=<edges> lvl=<0|1>
LOG cap total=<n> stored=8
OK <command echoed>
ERR <reason>
```

`marcstate=0x0D` is the CC1101 RX state. `edges` counting up proves the demodulator sees
energy. `LOG ... dropped burst` means the squelch rejected a burst — noise by default, not a
fault.

## Register image this bench ships (decoded)

```
FREQ     10 B0 71   433.91 MHz (26 MHz xtal)
MDMCFG2  0x30       modulation bits 6:4 = 3 (ASK/OOK); sync bits 2:0 = 0 (no sync word)
PKTCTRL0 0x32       format bits 5:4 = 3 (ASYNC SERIAL out on GDO0); whitening off; CRC off
IOCFG0   0x0D       GDO0 = serial data output
IOCFG2   0x0B       GDO2 = serial clock
MDMCFG4  0xC7       RX filter BW ≈101 kHz, DRATE_E=7
MDMCFG3  0x22       DRATE_M=34 → ≈3.6 kbps
MCSM0    0x18       auto-calibrate on IDLE→RX
AGCCTRL0 0x92       OOK-style AGC
```

This is a correct fixed-code OOK receiver configuration. If a firmware summary claims one
thing and the registers say another, the registers win.

## Frequency measurement on this bench

No frequency counter and no readable FREQEST: the firmware's `REG` reaches config registers
0x00-0x2E only, so the demodulator's frequency-offset register (0x3A) is out of reach. The
only route is a peak search by sweeping the receiver.

    SCAN <f0> <f1> <step> <dwell_ms>
      f0, f1  in kHz  (433700 = 433.700 MHz)
      step    in Hz   (the help text says kHz — it lies: 15 is rejected as "too many steps",
                       15000 gives 15 kHz steps)
      max 400 points; prints "SCAN <kHz>.<rssi>" per point then its own peak line
      ~30 points/s (25 points in 0.80 s)
    plain RSSI costs ~800 ms per round trip -> a hand-rolled sweep is ~1.2 points/s
    CFG BW= accepts 200/100/58/25 kHz; resolution of a peak search is set by the filter BW,
    NOT by the step size, so narrow BW sharpens the estimate and costs sensitivity

Tool: `~/Documents/rf/cc1101_live.py --measure` (fast SCAN) and `--measure --slow`
(step-and-read via RSSI). Both report a noise reference, peak, prominence, sub-step
parabolic interpolation and +/- (BW/2) uncertainty, and both REFUSE to report when the peak
is under 12 dB above the reference, moves with a step-size change, or is absent from some sweeps.

### Two traps found the hard way

1. **The fast sweep failed a sanity check.** A known carrier on air at -61 dBm (verified by
   parking on it) produced NO sweep point above -92 dBm inside a window that contained it.
   So SCAN's per-point values are suspect (AGC/PLL settling after retune, or not signal levels
   at all). Use `--slow` where the level matters.
2. **Interference mimics carriers.** A window at 433.820-434.020 consistently reported a
   +16.5 dB "peak" at 434.005 MHz, and a 100 kHz window a +20.5 dB "peak" at 434.044 MHz.
   Both were rejected once the tool re-swept at a different step: the peak moved 0.08-0.17 MHz.
   Interference bursts here reach -83 to -90 dBm.

**No calibration figure exists yet** (accuracy vs a known transmitter) — the YARD Stick One
went intermittent before one could be completed. Do not quote an accuracy number for this tool.

## Measured numbers on that bench (Kali host, room with normal 433 traffic)

| quantity | value |
|---|---|
| noise floor | ≈ −100 dBm |
| **noise ceiling** (highest level ambient bursts reach) | **≈ −90 dBm** (−98.5 … −91 observed) |
| ambient bursts | ~15 ms of dense 25–500 µs edges (noise, not data) |
| YS1 carrier a few cm away | −61.0 dBm (+40 dB over idle) |
| capture of that carrier | `FRAME … -67.5 …`, stored, `cap total=1` |
| squelch −85 (default) | correctly above the ceiling; passes a real signal, rejects noise |
| squelch −92 | starts admitting noise bursts as captures |
| squelch −110 | the floor becomes 122 junk frames in ~5 s |
| margin between a real desk-range signal and the noise ceiling | ~23 dB |

Rule of thumb the hard way: the threshold goes just above the noise **ceiling**, not the floor.

## Known firmware defects

```
E (366) gpio: gpio_isr_handler_remove(576): GPIO isr service is not installed,
           call gpio_install_isr_service() first
```

An ISR handler is removed without the ISR service ever being installed. Capture still works,
but the receive path's interrupt handling is not sound.

`TX OPT REPEAT=<n> GAP=<ms>` returns `OK` yet produced no measurable radiation (YS1 saw
+2.0 dB while its idle floor was −112.5 dBm), while the same pair's RX direction showed
+40 dB. So the TX path was broken or the command did not key the PA — unresolved as of
24 Sep 2026.

## TEST / override registers — live image read off the rig (27 Sep 2026)

Read with `REGS` over `/dev/ttyUSB0`, fw 1.0.0, nothing changed. Format is `REG <aa> <vv>`
(hex, no 0x), registers 0x00–0x2E.

| reg | name | chip | datasheet reset | note |
|---|---|---|---|---|
| 0x29 | FSTEST | 0x59 | 0x59 | "For test only. Do not write to this register." |
| 0x2A | PTEST | 0x7F | 0x7F | "Production test"; 0xBF = temp sensor in IDLE |
| 0x2B | AGCTEST | 0x3F in IDLE | 0x3F | AGC test/status window. In IDLE it reads the reset 0x3F; **in RX it reads live AGC values** (0x07/0x47/0x84/0x87 all observed). Not a writable deviation — do not "fix" it. |
| 0x2C | TEST2 | **0x81** | 0x88 | = the ADC_RETENTION=1 wake value |
| 0x2D | TEST1 | **0x35** | 0x31 | = the ADC_RETENTION=1 wake value |
| 0x2E | TEST0 | **0x09** | 0x0B | bit1 VCO_SEL_CAL_EN = 0 (reset/reference export = 1) |
| 0x03 | FIFOTHR | 0x47 | — | bit6 ADC_RETENTION = 1, FIFO_THR = 7 |

Facts that pin this down (CC1101 datasheet, Rev C and Rev I, both checked):

- TEST2/TEST1/TEST0 + FSTEST/PTEST/AGCTEST are exactly the registers §29.2 lists as
  **"Registers that Loose Programming in SLEEP State"** — "the TESTn registers (n = 0, 1, or 2)
  content is not retained in SLEEP state, and thus it is necessary to re-write these registers
  when returning from the SLEEP state". The Energia CC1101 driver says the same and adds
  PATABLE (all but the first byte).
- Rev I: TEST2 "will be forced to 0x88 or 0x81 when it wakes up from SLEEP mode, depending on
  FIFOTHR.ADC_RETENTION"; ADC_RETENTION=1 is required if an RX filter bandwidth below 325 kHz
  is wanted at wake-up. This bench runs 101 kHz with ADC_RETENTION=1 → the 0x35/0x81 pair is
  coherent with the intent, not random.
- TEST0 bit 1 = `VCO_SEL_CAL_EN` "Enable VCO selection calibration stage when 1". TI: "the
  recommended settings for TEST0.VCO_SEL_CAL_EN will change with frequency … always use
  SmartRF Studio to get the correct settings for a specific frequency before doing a
  calibration". The chip's own reset is 0x0B (bit1 = 1); the TI/ELECHOUSE 433 MHz reference
  export also uses 0x0B. **This bench (and the friend's sketch) writes 0x09 → calibration stage
  disabled.**

  TESTED 27 Sep 2026 — no measurable effect, do not chase this again:
  A/B on the live rig with the YARD Stick One holding a carrier at 433.92 MHz (rig parked,
  −56 dBm at the antenna, BW 101 kHz, PA fixed with `setPower(0xC0)`):
    0x09 → median −57.0 dBm (spread 0.5 dB), 39 frames, 0 dropped
    0x0B → median −56.5 dBm (spread 0.5 dB), 39 frames, 0 dropped
  Repeat with the phase order swapped: 0x0B −57.0 then 0x09 −56.8 → the sign of the 0.2–0.5 dB
  difference follows the ORDER, not the register value. TEST0.VCO_SEL_CAL_EN is neutral here.
  Reverted to 0x09. Tool: `~/Documents/rf/test0_ab.py` (writes, verifies the readback, samples
  parked RSSI per phase; the firmware parses REG arguments as DECIMAL — 0x2E is `REG 46 11`).
- TI keeps TEST2/TEST1/TEST0 as "Various test settings — the value to use in this register is
  given by the SmartRF Studio software". They are not optional decoration.
- No factory/persistent test mode exists to disable: CC1101 has no non-volatile memory and the
  E07-M1101D has no MCU, so nothing survives a power cycle; the host writes the whole image every
  boot. What is real: §4.9 — if the supply ramp does not meet Table 12 (≥5 ms to 1.8 V, ≥1 ms
  off), "the chip should be assumed to have unknown state until transmitting an SRES strobe over
  the SPI interface" (§19.1: hold CSn low, wait for CHIP_RDYn/SO low, issue SRES → IDLE); and
  IOCFG0 resets to GDO0 = CLK_XOSC/192 (135–141 kHz clock), which TI says to disable in
  initialisation "in order to optimize RF performance".
- Ebyte's E07 manual has one related line, no mention of any shipped mode: "After the CC1101
  recovers the IDLE mode or configures the sleep mode, it is recommended to reinitialize the
  power configuration table."

The friend's sketch (`~/Downloads/E07cc11DickkkkFLASH_THIS.ino`, fw 2.0.0) writes FSTEST 0x59,
PTEST 0x7F, AGCTEST 0x3F, TEST2 0x88, TEST1 0x31, TEST0 **0x09**, FIFOTHR 0x07
(ADC_RETENTION=0). Compiled clean on arduino-cli 1.5.1 / esp32 core 3.3.11. Review, including
two defects that matter (FRAME rssi sampled after the burst; command set incompatible with both
host drivers): `~/Documents/rf/friend-2026-09-26/REVIEW.md`.

## RX filter bandwidth decides whether a capture is readable (measured 27 Sep 2026)

Symptom it explains: "the rig demodulates the signal but every capture looks like noise" —
frames arrive with hundreds of edges and garbage pulse widths, in a room where the signal is
demonstrably strong.

Method: the YS1 transmitted a synthetic PT2262 frame (tri-state `FF0F0F0F0FFF`, T = 350 us ->
2857 baud, real 1T/3T pulses plus a 31T sync gap), rig parked on 433.920, capturing. Nothing
else changed between runs.

| `CFG BW` | edges per frame | width histogram | frame RSSI |
|---|---|---|---|
| 100 kHz (firmware boot default) | 800-830 | smear: 4,264 @50 us, 722 @350 us | -57.5 dBm |
| **58 kHz** | **26-32** | **clean: 436 @350 us (1T), 94 @1050 us (3T)** | -59.0 dBm |
| 25 kHz | 700-1025 | smear: 4,710 @100 us | -59.5 dBm |

- For OOK pulse capture at ~1-3 kbaud use `CFG BW=58`, never the firmware's 100 kHz default.
  It costs 1.5 dB and buys a decodable frame.
- 25 kHz is too narrow: it smears 2.9 kbaud pulses back into chatter.
- Detection is not the problem: 25/25 frames cleared the noise ceiling (-54...-60 dBm) at every
  bandwidth. The bandwidth decides whether the pulse *widths* survive the slicer.
- The setting is volatile - the rig's image restores `bw=100` on boot/RESET, so set it per
  session or in the host tool. `~/Documents/rf/remote_test.py` now defaults to 58.
- Known-good receiver test without any physical remote: `~/Documents/rf/ys1_send_code.py`
  (YS1 as synthetic PT2262 transmitter) captured by `remote_test.py`. A good capture shows
  ~26-32 edges per frame with the histogram peaks at 1T and 3T.

## A real code-hopping remote read end-to-end: ATA PTX-4 (28 Sep 2026)

The bench read a **brand-new ATA PTX-4** (Bunnings, SecuraCode, 433.92 MHz) — the real-remote proof
the synthetic PT2262 frame could never give. 50 real transmissions captured at contact range,
level **−66.5 to −72.5 dBm**, no dead zones.

Measured protocol:

| property | value |
|---|---|
| modulation | OOK (ASK) — pulse-width coded, not FSK |
| symbols | 1:2 set — 1T ≈ **390 us**, 2T ≈ **793 us** (ratio 2.03) |
| bit period | ≈ 1.18 ms → **~845 bps** |
| frame | ~154 pulses ≈ **77 bits**, first ~23 symbols are a preamble of short pulses |
| frame duration | ≈ 91 ms |
| repeat rate while held | ~100 ms (≈ 10 frames/s) |

- **Within one held press the code is IDENTICAL frame to frame** — repeats matched 0.99–1.00 after
  preamble alignment. Do not expect a per-frame counter.
- **Every PRESS is a new code — it hops.** Four separate presses of the *same* button gave pairwise
  similarities of 0.75–0.86, the same range as presses of *different* buttons (0.73–0.79), while the
  repeats **inside** one press matched 0.99–1.00. So that variation is the rolling code, not
  measurement noise: capture-and-replay cannot work on this remote, by design.
- **Four buttons = four distinct codes** (4 of 4 compared presses differed), all on the same frame
  layout — only the payload changes. Same protocol parameters on every button.
- **Frames must be captured from the frame start to be comparable.** Frames caught mid-burst cannot
  be aligned, and comparing them produces meaningless similarity scores: an unsynchronised
  comparison reported 0.68–0.84 similarity between frames that turned out to be identical. Only
  compare frames whose preamble is intact.
- **The rig re-dumps one burst several times within 0.1 ms.** Treat reports <50 ms apart as ONE
  transmission before counting anything, or a 2-second hold looks like hundreds of "frames".

### Gotcha: killing an rflib TX script leaves the dongle transmitting

A killed `ys1_send_code.py` / self-test does NOT stop the dongle — rflib does not reset the radio
when the process dies, so it kept radiating the synthetic 350/1050 us frame for ~27 s and **jammed a
live capture**, which is why later presses of a real remote went missing from that window. It went
silent the instant `setModeIDLE()` was issued, which is how the pollution was identified. Always run
`scripts/ys1_stop_tx.py` after killing any dongle TX.

The same kill-by-name trap bites the shell: `pkill -f <pattern>` matches its own command line, and
even a *bracketed* pattern is defeated when the plain name appears elsewhere in the same command
line — an `echo` mentioning the script was enough for the command to SIGTERM itself. Kill by pid.

**Diagnosed (2026-09-28):** `rig_tx_verify.py` (rig TX → dongle RX) **hung in the dongle-open step**,
and the cause was found the same night: `RfCat()` sat inside `resetup()` printing
`USBTimeoutError(110, 'Operation timed out')` about twenty times. That is the dongle's documented
wedged state, **not a bug in the script** — it looks like a hang with no output, which is why it cost
a run. The rig was healthy throughout the same check (`INFO fw=1.0.0 cc1101_partnum=0x00
cc1101_version=0x14 marcstate=0x0D rssi=-115.5 rx=1`). **Remedy: physically replug the dongle**, then
re-run. The rig's transmitter remains unverified — do not record it as working or broken until this
reports a level.

## Receiver comparison and one dead remote (27 Sep 2026)

- YS1 RX re-measured on a direct USB port (3-3): RSSI flat at **-110 to -113.5 dBm** (spread
  3.5 dB) while the rig in the same room saw ambient bursts at -88 to -97 dBm. The dongle does
  not hear the room. TX stays excellent (-48.5 dBm into the rig). Use it to transmit, not to
  receive.

  **CORRECTED later the same day: that deafness was the ANTENNA, not the radio.** With a
  different antenna fitted, the same dongle recorded 297 samples with a -103 dBm floor, a
  **-67 dBm peak, a 40.5 dB spread**, and five 255-byte demodulated bursts. The earlier verdict
  was measured with a DIY quarter-wave whip — do not repeat it without noting the antenna.
  (Its RX path is also unstable in long runs: rflib throws `USBTimeoutError(110)` and it then
  needs a physical replug. Its TX side is unaffected.)

- **A 433 MHz gate remote is CONFIRMED DEAD (27 Sep 2026) — on the rig's evidence, not the Autel's.**
  Five sessions (single press, repeated press, both buttons at once, contact range, squelch wide
  open at -110, plus a 433.0-435.0 sweep with the level-independent edge counter) produced nothing
  above the noise floor, on a receiver that reads a -57.5 dBm carrier on demand and captures
  synthetic PT2262 frames with textbook 1T/3T structure. That is the instrument for a garage
  remote, and it heard nothing. Fix path: fresh cell first, then the unit.
  The operator's **Autel KM100** also reported no signal, but treat that as supporting only: the
  KM100 is a car-key tool. Its own feature matrix lists **"Garage Remote: X"** (VVDI Key Tool
  Max/Mini, Lonsdor KH100+, KD-X2 all support it) and the manual describes Frequency Detection as
  "smart key frequency detection". It cannot be used to condemn a fixed-code garage remote.
  (Its detector does work for what it is for: it read the operator's car key as 312 & 314 MHz.)

- **The operator's car key is ~315 MHz, not 433.** The Autel KM100 read it as **312 & 314 MHz**.
  That retro-explains the earlier "car key, 3 bursts of 4 s" null on the rig: the E07-M1101D covers
  **387-464 MHz only**, so a 315 MHz fob is physically invisible to it. Not a fault, and nothing to
  fix — but never use that fob as a 433 reference again. (The YS1's CC1111 tunes 300-348 MHz, so it
  could hear it if the work ever needs to.)

- Do not open /dev/ttyUSB0 from a second process while a capture runs. Doing that raised
  "device reports readiness to read but returned no data" and killed a capture mid-window.


