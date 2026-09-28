# Review — "Diagnostic Analysis of RF Infrastructure and DUT Parameters" (JJX601 report)

Reviewed 2026-09-23. The report itself is saved verbatim alongside this file as
`rf-report-jjx601-as-posted.md`. This is the technical review: what holds up, what doesn't, and
what test was missed.

## What checks out (verified against datasheets, not taken on trust)

| Claim in the report | Verdict |
|---|---|
| CC1101 bands 300–348 / 387–464 / 779–928 MHz | **exact datasheet match** |
| CC1101 max channel filter bandwidth 812 kHz | **correct** — datasheet gives 58–812 kHz; the silent rejection of an out-of-range request is real behaviour |
| FSPL at 433.92 MHz over 1 m ≈ 25.2 dB | **correct** (λ = 0.691 m, 20·log₁₀(4πd/λ)) |
| A working remote at ~1 m should present −50 to −70 dBm | **sound**, given 0–10 dBm TX and a poor PCB loop antenna |
| RSSI is only valid in RX; garbage in IDLE | **correct** |
| rflib `RExmit` is async → script exits → libusb context dies → FIFO flushed | **correct**, and a genuine rflib trap |
| 24C02 = 256 bytes, I2C base address 0x50 | **correct** |
| The three software bug diagnoses (stdout None, Tk cross-thread variable access, async USB teardown) | **all real, all properly reasoned** |
| YS1 unofficial bands 281–361 / 378–481 / 749–962 MHz | **correct** — GSG document these as unofficial but reliable (the report states only the chip's official bands) |

## One real error — chip versus module

The **E07-M1101D is a 433 MHz module**, with a SAW filter and matching network. The CC1101 *chip*
can tune 387–464 MHz; **that module cannot** — its passband is set by hardware around 433 MHz.

Consequence: **the 281–361 MHz sweep on the ESP32/CC1101 side was effectively deaf.** "No signals
found in that window" is therefore not evidence of anything. Only the YARD Stick One can legitimately
look there, and its own range (281–361 unofficial) covers it.

The report never separates which instrument measured which window, and quotes the chip's bands as if
they were the module's. That conflation is the single most important thing to fix.

## One overclaim — a sweep is the wrong instrument for a short burst

"The absolute flatness of the spectral recording definitively proves that the remote emitted zero RF
energy" is too strong. A gate remote transmits roughly a one-second burst per press, and is usually
repeated while the button is held. A **swept** receiver only sits on each frequency briefly, so it can
miss a burst entirely.

**Correct method:** park the receiver on 433.92 MHz and monitor continuously — raw RSSI stream,
packet monitor, or `rtl_433`. A flat sweep is *consistent with* zero emission; it does not prove it.

The noise-floor reasoning is fine (−113 dBm settled floor is a sensitive chain), and the raised floor
at 650 kHz filter width is expected physics. The problem is the inference drawn from a sweep.

## The test nobody ran — and it's free

**Does the JJX601 actually open the gate?**

- Yes → it **is** transmitting, and the bench missed it → the problem is method/instrument, not the remote.
- No → it is blank or faulty → the EEPROM hypothesis is live.

That one check splits the entire problem in ten seconds, needs no instrumentation, and settles the
"most scientifically probable" ranking the report builds its conclusion on. It should be step 1 of
any follow-up.

## Citations

Several sources are eBay, AliExpress, YouTube and Scribd listings. Fine for working notes; fatal in a
university writeup. The primary sources all exist and should replace them: the TI CC1101/CC1111
datasheets, the ACMA LIPD class licence instrument, and AS/NZS 4268.

Related caution: the RF-hobby product space now contains AI-generated slop. Fake "HackRF One H4M"
product pages with invented revision tables were encountered during the same session. Verify every
product or revision claim against the manufacturer.

## Cross-link worth knowing

For the 27/40 MHz legacy question, an RTL-SDR works (V4 has a built-in HF upconverter; V3 needs
direct sampling). But the **HackRF One** tunes 27 and 40 MHz natively and would answer it directly —
that machine owns one, though it is currently out of action (see `hackrf-full-diagnosis.md`).

## Tool / frequency map, for avoiding the chip-vs-module trap

| Tool | Range | Notes |
|---|---|---|
| HackRF One | 1 MHz – 6 GHz | half-duplex; max input −5 dBm or permanent damage |
| YARD Stick One (CC1111) | official 300–348 / 391–464 / 782–928; unofficial 281–361 / 378–481 / 749–962 | the sub-GHz tool |
| CC1101 **module** (E07-M1101D) | ~433 MHz in practice (SAW/matching) | **the chip, not the module, covers 387–464** |
| Proxmark3 | LF 125/134 kHz + HF 13.56 MHz | the LF tool |
| Flipper Zero | sub-GHz, LF, HF, NFC | see operator's notes on firmware updates erasing AKL/simulator keys |

## Summary

The software work in that report is strong — three real bugs, correctly diagnosed, with the fixes
verified by the transmission actually going out. The RF conclusions are undermined by two errors:
treating a module as if it had the chip's tuning range, and treating a flat sweep as proof of zero
emission. Both are fixable in a paragraph, and the gate test would confirm or kill the whole EEPROM
hypothesis before anyone buys or builds anything.
