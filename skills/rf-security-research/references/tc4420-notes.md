# TC4420 / TC4429 — the actual datasheet facts

Source: Microchip DS21419 (TC4420/TC4429, "6A High-Speed MOSFET Drivers"). Researched 2026-09-21
after the first fetch returned the WRONG part (DS21425, the TC4467/4468/4469 quad 1.2 A family) —
worth naming, because the wrong family's numbers look plausible and would have gone straight into
the notes.

## Key specifications

| Parameter | Value | Notes |
|---|---|---|
| Peak output current | **6 A** | single output, measured at VDD = 18 V, **duty ≤ 2 %, t ≤ 300 µs** |
| Supply range | 4.5 – 18 V | abs max +20 V |
| Logic polarity | **TC4420 = NON-INVERTING · TC4429 = INVERTING** | TC4429 is pin-compatible with TC429 |
| Input range | **−5 V to VDD + 0.3 V** | and driving it to −5 V does NOT damage it |
| Input thresholds | VIH 2.4 V min · VIL 0.8 V max | TTL/CMOS compatible |
| Output swing | rail-to-rail | ROH ≈ 2.1–3 Ω, ROL ≈ 1.5–2.3 Ω at 18 V |
| Propagation delay | 55 ns typ | rise/fall 25 ns typ into 2500 pF, matched |
| Capacitive load | 10,000 pF | |
| Latch-up | > 1.5 A reverse output current | essentially latch-up proof |
| ESD | 4 kV | |
| Listed applications | motor control, **pulse transformer driver, Class D switching amplifiers** | |

## Two corrections to what the earlier sessions recorded

**1. "The TC4420 can't take negative input" is wrong.** The datasheet is explicit: the input may be
driven as low as **−5 V** with no upset or damage. What is true is that the input is *logic*, so a
negative excursion is simply read as logic LOW (VIL ≤ 0.8 V) — it produces no useful output state.
So the AC-coupling + 10k/10k DC-bias arrangement the notes describe is still REQUIRED, but for
signal reasons (producing a valid 0–VDD logic swing from a bipolar signal), **not** to protect the
part. Worth stating the reason correctly in the writeup, because "I biased it to stop it dying" is
a claim a marker can falsify from the datasheet.

**2. The 6 A peak rating is a PULSE rating, not a continuous one.** The datasheet conditions it on
duty cycle ≤ 2 % and t ≤ 300 µs. A continuous 125 kHz square drive applies a peak every 8 µs —
nowhere near ≤ 2 % duty at that rate in the thermal sense. So the TC4420 is fine as a *gate/pulse*
driver into a high-Q tank, but it is not a 6 A continuous power stage, and leaning on 6 A for the
LF power amplifier is how a driver dies or droops. If the "amplifier update" is meant to raise
sustained LF field strength, the honest path is a proper power stage (or paralleled/rescoped drive
with attention to the RMS and thermal numbers), not more peak current out of the driver.

## Why a square drive into an LC tank is not automatically bad

The tank is a bandpass: driven at resonance with Q ≈ 40 (as measured on this project), harmonics at
3f, 5f… are attenuated by roughly the harmonic order times Q. So a rail-to-rail square out of the
TC4420 into a resonant 125 kHz tank produces a largely sinusoidal coil current, which is exactly
why "Class D switching amplifier" is a listed application. The tank's Q is doing the filtering —
which also means the **drive frequency must be right**, or the tank stops filtering and the coil
current collapses. That is why the resonance question outranks the amplifier question.
