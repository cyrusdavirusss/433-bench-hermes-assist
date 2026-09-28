# Measuring LF tank resonance when the LCR meter fails

The LCR meter came back a bust on this project's 125 kHz coil module. That is a common outcome,
not a dead end: an LCR meter applies its own test frequency (often 100 Hz / 1 kHz / 10 kHz), and a
high-Q LF tank measured at the wrong frequency reports a number that has nothing to do with where
it actually resonates. These methods all work with equipment already on this bench.

## 1. Ring-down — needs only the oscilloscope

The best option here, because it needs the Micsig and nothing else.

1. Leave the tank exactly as it sits, with the drive off (or the driver's output high-Z).
2. Excite it once — a brief step or pulse into the tank. The existing driver can do it; a manual
   momentary contact works; so does a function generator burst if one is handy.
3. Probe across the tank with a **10× probe** and capture in **single-shot** mode.
4. Read the ringing period T off the screen: **f₀ = 1 / T**. Ten cycles averaged beats one cycle
   eyeballed — measure across as many cycles as fit and divide.

Why it is the right method for this coil: it measures the tank's *actual* self-resonance with the
capacitors that are fitted, at its own natural frequency, with no test-frequency assumption. A high
Q shows as many visible rings — on this project Q ≈ 40 was already measured, so expect a long
decaying train and an easy period to read.

Caveats: a 10× probe adds ~10 MΩ ∥ ~15 pF, which shifts a small high-Q tank measurably — note the
probe capacitance rather than pretending it is zero. If the ring is heavily damped, something in
the tank or its load is dissipating (that itself is a finding).

## 2. Sweep and watch the peak — function generator (or an ESP32/Arduino)

Drive the tank through a series resistor and sweep the frequency, watching the tank voltage on the
scope. The **voltage across a PARALLEL tank peaks at resonance**, while the **source current dips**
— the opposite of a series tank, and mixing the two up is the classic way to find a "resonance"
that is not the one you want. The Tek application note (75W_28152) covers the equivalent I-V method
properly: a 1 kΩ reference resistor, measure amplitude and phase across the DUT, and you get L, C
and ESR at any frequency.

An ESP32 or Arduino PWM output makes a perfectly serviceable sweep source — this project already
has both, and no test equipment purchase is required.

## 3. The arithmetic is a starting point, never the answer

f₀ = 1 / (2π√(LC)) told this project that 20 nF should put the module at 125 kHz given 100 nF put
it at 8.4 kHz. That calculation is worth doing, and worth distrusting: it ignores the coil's own
self-capacitance, the probe, the driver's output capacitance and the wiring. **Verify by
measurement after soldering, exactly as the project's own notes say.** Methods 1 and 2 are how.

## 4. If a purchase is on the table

A NanoVNA-H (~AUD 60) measures the tank impedance directly across frequency and is the tool this
job actually wants. The Tek note benchmarks a cheap USB VNA against a lab LCR meter and finds them
within a couple of percent. Worth it if LF tuning continues past the October demonstration.

## Order of operations for this project

1. Ring-down the coil as fitted → get the real f₀. If it is 8.4 kHz, the tank is not filtering and
   no amplifier change will fix it.
2. Change to 20 nF, re-measure. Target 125 kHz ± a few kHz.
3. Only then apply the amplifier update, and re-measure range with conditions recorded.
