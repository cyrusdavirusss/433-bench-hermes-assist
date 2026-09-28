# ATA PTX-4 — the bench's known-good 433 remote

A brand-new Automatic Technology **PTX-4** (sold at Bunnings) became the bench's reference
transmitter on 2026-09-28: the first *real* remote this bench has read end-to-end, and the positive
control for the dead gate remote.

## The model

| property | value |
|---|---|
| maker / model | Automatic Technology Australia, PTX-4 (SecuraCode, blue keyring shell) |
| frequency | **433.92 MHz** |
| coding | **SecuraCode** code-hopping — new code from >4.29 billion each use |
| buttons | 4, each independently programmable to a different door/gate |
| battery | **12V 23A (A23)** alkaline; case screw, mind polarity |
| fits | ATA GDO-2v7/6/7/8/9, EasyRoller, Securalift, ATA slide/swing gates (ESV-24 etc.) |
| not interchangeable with | PTX-5 (looks similar, different coding) |

## Measured on the bench (2026-09-28)

- **It transmits without ever being paired.** Programming teaches the *receiver* to accept it; the
  remote radiates the moment a button is pressed. That is what makes it usable as a bench reference
  straight out of the packet.
- Level at contact range: **−66.5 to −72.5 dBm**; a metre or two out: −76 to −79.5 dBm.
- Protocol: OOK, PWM 1:2 — 1T ≈ 390 us, 2T ≈ 793 us, bit period ≈ 1.18 ms (**~845 bps**);
  ~154 pulses/frame ≈ 77 bits with a ~23-symbol preamble; frame ≈ 91 ms, repeating every ~100 ms
  while held.
- **Within one press** the repeats are identical (0.99–1.00). **Between presses** the code changes
  every time — four presses of the *same* button matched only 0.75–0.86, the same range as presses of
  different buttons (0.73–0.79). So it hops on every press: **capture-and-replay cannot drive it**,
  which is the whole point of the technology.
- Four buttons = four distinct codes (4 of 4), identical frame layout, only the payload differs.

## Pairing it to a door or gate

Needs the opener in front of you. Two ways:

**At the opener** (blue Door Code button, or SW1/SW2 on a receiver board):

1. Press and hold the opener's blue **Door Code** button.
2. Press the remote button you want, for 2 seconds.
3. Release, pause 2 seconds, press the same button again for 2 seconds.
4. Release the Door Code button and test.

**From a remote location** (needs one transmitter already coded into the opener):

1. Press the already-coded transmitter's button to activate the door, then release.
2. With a needle, press through the **coding hole** and hold firmly for 2 seconds.
3. Within 10 seconds, press the new remote's button for 2 s, pause 2 s, press it again for 2 s.
4. Wait 10 seconds and test.

**Wipe a receiver's memory:** power the opener off, hold Door Code (or SW1), power on while holding —
the coding LED lights to show all stored transmitter codes are gone.

## Why this matters for the project

The gate remote captured nothing across five sessions on this bench. After the PTX-4 was read
immediately and repeatedly, that silence is no longer ambiguous: the bench works, and that remote is
dead. A fresh cell is still the cheap test, but the instrument is no longer the suspect.
