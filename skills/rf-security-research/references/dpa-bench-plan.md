# DPA bench plan — recovering the PTX-4's KeeLoq key with the Micsig

Status: the attack software is PROVEN end-to-end offline (`keeloq_dpa_port.py` recovers a full
device key from published HCS301 traces, validating on all 501 messages). Everything below is the
physical side, which needs hands.

## Step 0 — the one thing that decides everything: identify the chip

Open the PTX-4 (four screws under the case, then pry the halves apart). Read the marking on the
8-pin SOIC. Photograph it if unsure.

    HCS301 / HCS300 / HCS200 / HCS201 / HCS360 / HCS361 / HCS362 / HCS410
        -> these are the documented DPA targets. Proceed.
    EG301 or another clone
        -> may insert dummy instructions during the cipher and defeat the attack. Forum reports
           exist of clones resisting it. Still worth attempting, lower odds.
    ATA/Princeton fixed-code part (no rolling code)
        -> the frame we captured is 66 bits with a changing field, so it is NOT fixed-code.
           Report the marking anyway; it changes the plan.

Also note: package type matters. DIP parts need ~10 traces; SOIC ~30 (lower SNR). A fob will be
SOIC or a bare die, so expect to need 30+ traces — collect 100-500 if it's cheap to do.

## CHIP CONFIRMED: HCS301 (operator read the marking, 2026-09-29)

The PTX-4 contains a Microchip HCS301 — the exact part the published rehearsal traces came from,
and the documented DPA target. Datasheet confirms the profile we measured from the air:
programmable 28-bit serial, programmable 64-bit encryption key, each transmission unique,
PWM or Manchester output (ours is PWM — rtl_433 guessed Pulse Width Modulation unprompted).

Consequences:
- The cipher IS KeeLoq, so the brute-force work attacks the right algorithm.
- The DPA pipeline applies directly — same silicon as the traces the attack was proven on.
- HCS301 holds a **programmed** 64-bit device key. If ATA programmed a unique random key per
  remote, no brute force can ever find it and DPA is the only route. If they derive keys from a
  manufacturer key (Normal Learning), the sweep can still hit. Unknown which — DPA settles it.

### SOIC-8 pinout (datasheet 21143B)

    pin 1  S0        pin 8  VDD
    pin 2  S1        pin 7  LED    <- cathode, pulls low on transmit: ideal trigger
    pin 3  S2        pin 6  PWM    <- chip data output to the RF stage: alternate trigger/sync
    pin 4  S3        pin 5  VSS    <- GND: the shunt goes here
    pin 5  VSS

### Wiring

- **SHUNT:** 10-47 ohm between pin 5 (VSS) and the battery negative. Easiest is to interrupt the
  ground trace between pin 5 and the battery -, rather than lifting the pin. Probe across it,
  AC-coupled, high vertical gain (a few mA across 10 ohm is tens of mV).
- **TRIGGER:** pin 7 (LED) — pulls low when the chip transmits, giving a repeatable time zero with
  the cipher ~20 ms later. Pin 6 (PWM) works too and starts with the data.
- **Expected timing:** encryption runs ~20.5-24 ms after the falling edge; chip internal clock
  ~1.25 MHz, so expect roughly 160 samples per round at 200 MS/s, ~800 at 1 GS/s. That is the
  prior for the calibration ladder — if it comes out near those numbers, the capture is good.

## Step 1 — get the measurement point

Two options, either is in the paper:

    A. GND SHUNT (better SNR)
       Insert a small resistor (10-47 ohm; 10 ohm is safe for a fob drawing a few mA) in the
       chip's ground path — lift the GND pin, or break the battery negative through the resistor.
       Probe ACROSS the resistor with a passive 10x probe, AC-coupled, high vertical gain
       (a few mA across 10 ohm is tens of mV).
       Ch1 = shunt. Ch2 = trigger.

    B. EM NEAR-FIELD PROBE (no soldering, slightly worse)
       The paper got comparable results with a DEMA probe held near the chip's ground pin.
       A DIY H-field loop from a short length of coax (outer shield cut at the tip, inner
       connected to form a small loop) works. Position it touching the chip body.

## Step 2 — scope configuration (Micsig STO1004)

    sample rate    200 MS/s to start (exactly what the paper used and succeeded with).
                   1 GS/s is available and finer, but 200 MS/s gives a 140 ms window from the
                   28 Mpts, which comfortably covers the whole operation.
    window         ~100-140 ms. The cipher runs roughly 20.5-24 ms after the button press
                   (the EEPROM write happens first), so a window that starts at the press has
                   room to spare.
    coupling       AC, 1-2 mV/div as needed
    trigger        on the button press (wire it to ch2) or single-sequence armed by hand
    storage        save each capture to USB as CSV if the model supports it — the waveform SCPI
                   download path is disabled on this unit, so files are how traces leave the scope

## Step 3 — capture loop (I can drive most of this)

**CRITICAL: power traces and RF frames must be captured together, in order.** Every press produces
a DIFFERENT ciphertext (that is the whole point of the hop), and the DPA needs trace N matched with
ciphertext N. So before pressing anything:

    1. Start the rig (or the YARD Stick One) logging 433.92 MHz frames continuously - I can run
       this, and it records every code the remote sends, in order
    2. Then capture the power traces, one per press, triggered deterministically (LED pin 7)
    3. Pair them by order, and cross-check the counts - if the RF log has more frames than the
       scope has traces (a missed trigger), the pairing is broken and the capture must be redone

A deterministic hardware trigger is a real advantage here: the 2008 paper triggered off the RF
after the last bit, which left its traces poorly aligned (they needed thousands of traces for the
receiver attack as a result). With the LED as trigger, trace N and frame N line up.

The scope is on the bench LAN (address in the private ledger) and I have SCPI access. So:

    1. I configure the scope (timebase, channels, trigger, storage) over SCPI
    2. You press the button; I trigger and save each capture to the scope's storage
       (`:STORage:CAPTure:STARt` writes a PNG; `scope_save_waveform` writes the waveform)
    3. Every N captures, move the USB stick to the Kali box and I ingest the files
    4. I run keeloq_dpa_port.py against them

Optional full automation: the ESP32 rig can drive a transistor across the remote's button
contacts, so press -> capture -> save runs unattended. Then the only manual part is fetching
files.

## Step 4 — attack parameters to use

The ported attack needs to know where the cipher sits in the trace. Procedure that works:

    a. Calibrate: correlate the KNOWN ciphertext bits against the traces. A regular ladder appears
       at a constant spacing = samples per round. On the published set that was exactly 200
       samples/round with |r| 0.24-0.54, which also fixed the alignment.
    b. Feed round528 = the sample position of the last ciphertext bit's round, and width = samples
       per round, into the attack's window formula (round r -> round528 - (528-r)*width).
    c. Run the attack. Per-bit Welch t-statistics of 6-10 and a validated decryption mean success.
       If t-stats sit near 1-2, the alignment is wrong, not the model.

## What the validated result looks like

    disc field constant on ~100% of messages, counters advancing systematically
    (published set: disc=0x394, counters stepping exactly +2, 100% of 501 messages)

For the PTX-4 the equivalent check is: the 26-bit serial field (0x0a438af) staying constant while
the counter advances. That is the same oracle used throughout this project.

## Fallback if the chip is unreachable or a clone

1. Larger brute force / smarter key corpus (already running, wave 2 queued)
2. Device dump: read the remote's EEPROM if the part exposes it
3. Receiver-side attack: the paper also recovers the MANUFACTURER key by putting the receiver in
   learning mode and sending messages with chosen serials — then any fob of that brand can be
   decrypted from two captures with no physical access to the fob at all. For a Bunnings PTX-4
   that means the gate/receiver end, which is a different conversation about ownership.
