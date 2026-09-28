#!/usr/bin/env bash
# hackrf-check.sh — full diagnosis of a HackRF One in one shot.
#
# Run it FIRST with nothing plugged in to record the baseline, then again with the board attached.
# Every line is printed with the command that produced it, so the output can be pasted straight
# into the shared ledger, a GitHub issue, or the buyer if it turns out to be a clone.
#
# Command syntax here was verified against hackrf_info/clock/debug/sweep 2026.01.3 on this box.
set -uo pipefail

echo "############ HackRF One diagnosis — $(date '+%F %T %Z') ############"
echo
echo "### 1. USB presence (1d50:6089 = HackRF One app mode; NXP LPC4330 = DFU mode) ###"
lsusb | grep -iE "1d50|hackrf|LPC4330" || echo "  nothing matching HackRF / NXP LPC4330 on the bus"
echo
echo "### 2. kernel view — attach/detach MUST appear here ###"
if sudo -n dmesg >/dev/null 2>&1; then
  sudo -n dmesg | tail -25 | grep -iE "usb|hackrf|1d50" | tail -12 | sed 's/^/  /'
else
  echo "  (dmesg needs privilege — run: echo kali | sudo -S dmesg | tail -30   and read the USB lines)"
fi
echo
echo "### 3. does libhackrf see it? ###"
echo "  $(hackrf_info --version 2>&1 | tr '\n' ' ')"
if ! hackrf_info >/dev/null 2>&1; then
  cat <<'EOF'
  NOT DETECTED by libhackrf. Work down in this order:
    a. SWAP THE CABLE. Charge-only USB cables produce exactly this symptom and are common.
       Test the cable on another device that transfers data.
    b. PortaPack fitted? It must be in "HackRF" mode.
    c. DFU MODE: hold the DFU button WHILE plugging in. The board should appear as
       "NXP LPC4330FET180 [ARM Cortex M4 + M0] (device firmware upgrade mode)".
         - appears in DFU  -> firmware fault, recoverable (hackrf_spiflash -w ...)
         - does NOT appear in DFU -> hardware fault. See references/hackrf-diagnostics.md for the
           USB0_VBUS / MCU-pin-21 / overvoltage path, and check whether the MCU gets WARM.
    d. Also note: the USB0_VBUS divider differs by revision (pre-r7: R62=0R, R65=10k, VBUS direct;
       r7+: 10k/18k -> ~3.3V). Know your revision before measuring.
EOF
  exit 1
fi
echo
echo "### 4. identity ###"
hackrf_info 2>&1 | sed -n '2,12p' | sed 's/^/  /'
echo
echo "### 5. firmware self-test report (requires recent firmware; empty output is itself informative) ###"
hackrf_debug --selftest 2>&1 | head -14 | sed 's/^/  /'
echo
echo "### 6. M0 state ###"
hackrf_debug --state 2>&1 | head -4 | sed 's/^/  /'
echo
echo "### 7. clock ###"
hackrf_clock -i 2>&1 | head -4 | sed 's/^/  CLKIN: /'
hackrf_debug --si5351c -c 2>&1 | head -10 | sed 's/^/  /'
echo
echo "### 8. SPI to the RF chips — the decisive MCU<->RF health test ###"
echo "  -- si5351c reg 0 --";  hackrf_debug --si5351c -n 0 -r   2>&1 | head -3 | sed 's/^/    /'
echo "  -- max283x reg 0 --";  hackrf_debug --max283x -n 0 -r   2>&1 | head -3 | sed 's/^/    /'
echo "  -- rffc5072 all  --";  hackrf_debug --rffc5072 -r       2>&1 | head -6 | sed 's/^/    /'
echo "  Plausible values = the MCU can talk to the RF chips. Garbage/failures = that path is broken."
echo
echo "### 9. internal ADC channels ###"
for ch in 0 1 2 3 4 5 6 7; do
  v=$(hackrf_debug --adc "$ch" 2>/dev/null | tail -1)
  [ -n "$v" ] && echo "  ADC ch$ch: $v"
done
echo
echo "### 10. front-end liveness — 88-108 MHz FM broadcast is always busy ###"
echo "  A healthy front end shows MORE signal at high gain. Identical empty results at both = dead front end."
timeout 25 hackrf_sweep -f 88:108 -w 100000 -l 8  -g 8  -N 2 2>&1 | tail -2 | sed 's/^/  low-gain : /'
timeout 25 hackrf_sweep -f 88:108 -w 100000 -l 40 -g 40 -N 2 2>&1 | tail -2 | sed 's/^/  high-gain: /'
echo
echo "############ done — this whole output is safe to paste anywhere ############"
