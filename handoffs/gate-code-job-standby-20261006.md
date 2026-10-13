# Handoff — RIG NOT CONNECTED, standby (2026-10-06, Windows box)

**State (SUPERSEDES the rest of this file's "blocker" framing): RIG CONNECTED, JOB POSTPONED BY
THE OWNER — go back early on 2026-10-07.** Owner's message at ~23:52 PDT 2026-10-06: "come back
tomorrow early". Nothing captured, nothing transmitted, no runner left alive. **The hardware
blocker below is CLEARED** — both radios enumerated at 23:48 and were verified, then released.

**Re-checked 2026-10-06 23:46 PDT**: no COM ports, stick absent (nothing plugged in yet).
**Then 23:48 PDT**: both appeared — see "Rig verified" below.

## Rig verified 2026-10-06 23:48-23:55 PDT (do not re-derive; re-check only if the pads move)

- `COM8` = **Silicon Labs CP210x** (VID:PID 10C4:EA60, SER 0001, LOCATION=1-1) — the ESP32/CC1101 rig.
- `rf433.py info` (auto-selects COM8): `RDY fw=1.0.0 chip=ESP32 layout=vspi-documented
  cc1101_partnum=0x00 cc1101_version=0x14 spi=ok gdo0=4 csn=5 sck=18 mosi=23 miso=19 gdo2=27`, then
  **`OK RX ON`**. `partnum=0x00` is the known-not-a-fault field (version 0x14 + live RSSI is the
  health check). Boot prints `E (366) gpio: gpio_isr_handler_remove ... isr service is not
  installed` — benign, RX still runs.
- ESP floor measured **-112.0 dBm** (`INFO ... rssi=-112.0 rx=1`, default cfg freq=433.92 bw=100
  squelch=-85), with `dropped burst ... rssi=-113.0/-114.0 (squelch -85.0)` — i.e. the receiver is
  live and the floor is where the record says it is.
- YARD Stick One present on the bus as **1d50:605b** (Great Scott Gadgets, iSerial 009a, bcdDevice
  101); `subghz.probe_stick()` -> **('free','')**.
- **315 control taken**: `watch315.py 315 1` ran the full minute 23:49:08-23:50:09 with nothing
  keyed — floor **-107.0 dBm**, top **-96.5 dBm = +10.5 dB over floor**, 45 hits / 11250 bytes over
  the last ~20 s, **DETECTED=False**, `dongle released (IDLE)`. So the watch is clean on a quiet band
  and +10.5 dB does not trip `SIG_DB=20`. Compare 2026-10-03: same -107.0 floor but a **+17.0 dB**
  ambient ceiling. **The 315 noise ceiling moves between sessions (10.5 vs 17 dB over floor)** — a
  reading near +17 dB is still ambient, never a press, and the control must be re-taken if the
  antennae move. Teardown printed `===== RESETUP set from recv thread` + a stray `]` — normal rflib
  recv-thread output on close, not a fault.
- After the kill: `probe_stick()` = free, `serial.Serial('COM8')` opens clean, and a process sweep
  matching `watch315`/`hunt_replay2` (with powershell self-matches excluded) returns **nothing**.
  **Beware the self-match trap when you re-run that sweep**: a `-match` on the script name matches
  the very powershell/python checking for it, so it reports a runner that is not there.

## Start here tomorrow (nothing to build, nothing to delete)

1. `hunt_replay2.py` and `watch315.py` in parallel; press the remote 1-2 s per press, several
   presses >1.5 s apart.
2. Step 2 of the old resume order (`bench_control.py`) is **not** a rig-health run — it needs
   `<capture.jsonl> <frame-index> [repeat]` and it TRANSMITS. Correction is inline below.
3. Still unanswered, and it decides the band up front: **remote make/model + opener/receiver model**.

**Superseded blocker note (kept for the record)** — the stale `STOP_REPLAY` was **deleted**
2026-10-06; `hunt_replay2.py`, `watch315.py`, `bench_control.py`, `holder.py` all `py_compile`
clean; device split re-confirmed from source: `hunt_replay2.py` hardcodes **COM8** and is the only
file referencing any COM port, `watch315.py` opens only the dongle via `subghz.get_stick()`, so the
two runners cannot contend. Re-check `STOP_REPLAY` has not reappeared before starting.

## The job

Operator's words: "its a real job oppertunety testing vulnarbiletys with full writen consent
from uni and owner". Recorded as the authorisation basis. Deliverable implied: capture a gate
remote's code, establish fixed vs rolling, and if fixed, replay it to demonstrate the
vulnerability. Gear is the owner's; school + owner consent on paper.

Still open, and it decides the band + the whole approach: **remote model and opener/receiver
model** — see "the one question" below.

## Blocker (measured, twice)

Neither radio is on the bus:
- `serial.tools.list_ports.comports()` -> **no COM ports at all** (so no COM8 = no ESP32/CC1101)
- `usb.core.find(idVendor=0x1D50, idProduct=0x605B)` -> **None** (YARD Stick One absent)
- `Get-PnpDevice -PresentOnly` class Ports/USB -> only root hubs + Intel xHCI. No USB serial
  bridge at all (no CH340/CP210x/FT232), so it is not a driver problem — nothing is plugged in.

Bounded 150 s watch for both to appear: both NOT SEEN.

## Tools, already built and on disk (nothing to rebuild)

    cd C:\Users\Cyrus\rfbench
    C:\Users\Cyrus\yardstick\.venv\Scripts\python.exe -u hunt_replay2.py   # 433: FIND->WATCH->REPLAY
    C:\Users\Cyrus\yardstick\.venv\Scripts\python.exe -u watch315.py      # 315 presence watch
    C:\Users\Cyrus\rfbench\subghz.py                                       # menu front end (ANALYZER/RECEIVE/SEND)
    C:\Users\Cyrus\rfbench\bench_control.py                                # rig health control run

- `hunt_replay2.py` — no timers anywhere (operator asked for "until I say stop").
  FIND sweeps 432.0-434.6 MHz @25 kHz until a bin JUMPS >= 6 dB between passes; WATCH parks and
  records forever, grouping frames into PRESSES by >1.5 s silence; REPLAY only fires when two
  PRESSES carry the SAME code, and refuses to transmit if they differ (rolling).
- Stop control: create `C:\Users\Cyrus\rfbench\STOP_REPLAY`. It exists STALE from 2026-10-03 —
  **delete it before starting** or both runners exit immediately.
- One holder per device: one process on COM8, one on the dongle. `rfbench/holder.py` names holders.
- Frames land in `C:\Users\Cyrus\rf433\captures\press_*.jsonl`; logs `hunt_replay2.txt`,
  `watch315.txt` (append).

## Resume order

1. Plug in the ESP32/CC1101 rig (must enumerate as **COM8**) and the YARD Stick One.
2. `rm STOP_REPLAY` (deleted 2026-10-06 — re-check it has not reappeared), then confirm the rig
   before trusting any null with `bench_control.py <capture.jsonl> <frame-index> [repeat]`.
   **It has no no-arg mode** (verified here: `IndexError` at `cap = sys.argv[1]`, line 18) and it
   **radiates**: 12 s quiet window, then it TXs that capture's frame from the ESP rig (via
   `rf433\.venv\...\rf433.py send --from-file ... --index ... --repeat ...`) while the dongle
   watches, then prints VERDICT. Working form:
   `bench_control.py C:/Users/Cyrus/rf433/captures/live_open.jsonl 0 20`
   Pick a capture+index holding a REAL frame, not noise. Clear any live gate/opener off the bench
   first — this step transmits.
3. `hunt_replay2.py` and `watch315.py` in parallel — both bands covered, so the unknown band is
   not a blocker for starting.
4. Press the remote 1-2 s per press, hand clear of the antenna, 0.5-2 m from the rig, several
   separate presses (separated by >1.5 s — separate presses are what the fixed/rolling test needs).

## Band limits that are already proven (do not re-derive)

- ESP32 + CC1101 / E07-M1101D: **387-464 MHz** — deaf to 315 and 868. OOK/ASK only.
- YARD Stick One (rfcat, CC1111): **281-361 / 378-481 / 749-962 MHz**.
- Nothing on this bench reaches **below 281 MHz**. AU legacy gate remotes at 27.045/27.145/27.195
  and 40.685 MHz are invisible to the entire setup — an RTL-SDR would be needed to even identify one.
- So a 433 fixed-code remote = easy; a 315 remote = stick only (bit-level OOK TX, not exact pulse
  widths); a 27/40 MHz remote = this bench cannot do the job.

## Already-verified findings this job must not re-litigate

- The old **JJX601 / R433** gate remote is **DEAD** (27 Sep): nothing above the floor in five
  sessions on a rig that reads -57.5 dBm on demand, plus an Autel KM100 null. Not a rig fault.
  Its car key reads 312 & 314 MHz.
- The **ATA PTX-4** (433.92, SecuraCode) is the bench's known-good reference: -66.5 to -72.5 dBm
  at contact, OOK PWM 1:2, 1T~390us, ~845 bps, ~154 pulses/frame, ~91 ms/frame every ~100 ms.
  It **hops on every press** (same button across presses matched 0.75-0.86 = same as different
  buttons) — so a rolling remote of that class cannot be replayed, and that is the expected result
  for any modern opener. Proving the vuln requires a FIXED-code device, or attacking something
  other than the code (receiver's lack of rolling check).
- Bench thresholds for reading a null honestly: floor ~-113 dBm at 433 (E07, 100 kHz BW),
  ~-107 dBm at 315 (stick). Real press = 20-30+ dB over floor; +17 dB at 315 is the noise ceiling,
  not a press. The 433 rig emits decoder frames down to about -97 dBm (+15 dB over floor).

## The one question that changes the plan

**Remote make/model and the opener/receiver it drives** (photo of any label, or the opener's board
model). It fixes the band before sweeping, and it is a strong prior on fixed vs rolling — 433
"R433 + 24C02 EEPROM" = classic fixed/learning code, a modern named brand = almost certainly hopping.
