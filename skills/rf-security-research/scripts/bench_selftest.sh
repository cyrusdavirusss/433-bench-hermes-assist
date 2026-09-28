#!/bin/bash
# One-command sanity check for the 433 bench: ESP32+CC1101 rig + YARD Stick One as the
# reference transmitter.
#
# Run this BEFORE trusting any "I can't hear it" result. It proves each link in the chain:
#   1. SPI read paths on the rig      (a loose MISO corrupts every number the firmware reports)
#   2. YS1 transmits -> rig hears it  (both radios' TX/RX, the antenna path, and the tuning)
#   3. Synthetic PT2262 frame capture (that the rig produces a decodable pulse train)
#
# Usage:  bash ~/Documents/rf/bench_selftest.sh
#
# Notes learned the hard way:
#   * the rig's firmware parses REG arguments as DECIMAL
#   * never open /dev/ttyUSB0 from a second process while a capture owns it
#   * the script puts the rig back on 433.920/BW=58/-85 dBm squelch when it finishes
#   * the dongle must be physically replugged if rflib reports USBTimeoutError

set -u
RF=/home/cyrus/Documents/rf
RIG=/dev/ttyUSB0
YS1PY=/tmp/ys1venv/bin/python
PASS=0; FAIL=0

rig() { python3 - "$@" <<'PY'
import sys, time, serial
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=1)
time.sleep(1.0); s.reset_input_buffer()
for c in sys.argv[1:]:
    s.write((c+"\n").encode()); time.sleep(0.8)
print(s.read(8000).decode(errors="replace"), end="")
s.close()
PY
}

rigrssi() { python3 - "$1" <<'PY'
import sys, statistics, time, serial
n = int(sys.argv[1])
s = serial.Serial("/dev/ttyUSB0", 115200, timeout=1)
time.sleep(1.0); s.reset_input_buffer()
vals = []
for _ in range(n):
    s.write(b"RSSI\n"); time.sleep(0.8)
    for l in s.read(8000).decode(errors="replace").splitlines():
        if l.startswith("RSSI "):
            try: vals.append(float(l.split()[1]))
            except ValueError: pass
s.close()
print(f"{statistics.median(vals):.1f} {min(vals):.1f} {max(vals):.1f}" if vals else "none none none")
PY
}

echo "############################################################"
echo "# 433 bench self-test   $(date '+%F %T')"
echo "############################################################"

echo
echo "--- 0. rig present? ---"
if [ ! -e "$RIG" ]; then echo "FAIL: $RIG missing - plug the rig in"; exit 1; fi
rig "CFG FREQ=433.920000" "CFG BW=58" "CFG SQUELCH=-85" "RX ON" >/dev/null
INFO=$(rig "INFO" | grep '^INFO' | head -1)
echo "  $INFO"
case "$INFO" in
  *partnum=0x00*version=0x14*) echo "  PASS: CC1101 answering, version 0x14"; PASS=$((PASS+1));;
  *) echo "  FAIL: unexpected chip identity - check wiring/power"; FAIL=$((FAIL+1));;
esac

echo
echo "--- 1. SPI read paths (loose MISO = write-OK/read-corrupt) ---"
if python3 "$RF/spi_stress.py" --dumps 6 --rssi 20 | tee /tmp/selftest_spi.txt | tail -3 | grep -q "all read paths consistent"; then
  echo "  PASS: every read path consistent"; PASS=$((PASS+1))
else
  echo "  FAIL: SPI read paths inconsistent (see /tmp/selftest_spi.txt)"; FAIL=$((FAIL+1))
fi

echo
echo "--- 2. YS1 transmits a carrier -> does the rig hear it? ---"
if [ -x "$YS1PY" ]; then
  ( echo kali | sudo -S "$YS1PY" "$RF/ys1_tx_carrier.py" --seconds 30 >/tmp/selftest_tx.log 2>&1 ) &
  sleep 14
  LEVEL=$(rigrssi 6 | awk '{print $1}')
  echo "  rig level while the YS1 transmits: $LEVEL dBm"
  if [ "$LEVEL" != "none" ] && awk -v v="$LEVEL" 'BEGIN{exit !(v > -90)}'; then
    echo "  PASS: rig hears the reference transmitter"; PASS=$((PASS+1))
  else
    echo "  FAIL: rig did not hear the reference transmitter - antenna, tuning or RX path"
    FAIL=$((FAIL+1))
  fi
  wait
else
  echo "  SKIP: no $YS1PY (rflib venv missing - rebuild: python3 -m venv /tmp/ys1venv && /tmp/ys1venv/bin/pip install rfcat)"
fi

echo
echo "--- 3. synthetic PT2262 frame -> decodable pulse train? ---"
if [ -x "$YS1PY" ]; then
  ( echo kali | sudo -S "$YS1PY" "$RF/ys1_send_code.py" --seconds 30 --T-us 350 >/tmp/selftest_frame.log 2>&1 ) &
  sleep 8
  OUT=$(python3 "$RF/remote_test.py" --seconds 20 --bw 58 2>&1)
  wait
  FRAMES=$(echo "$OUT" | grep -oE '^  [0-9]+ frames captured' | grep -oE '[0-9]+')
  EDGES=$(echo "$OUT" | grep -oE '^  edges per frame: .*' | head -1)
  echo "  frames captured: ${FRAMES:-0}"
  echo "  $EDGES"
  echo "$OUT" | grep -A3 "pulse-width buckets" | head -4
  if [ "${FRAMES:-0}" -ge 5 ]; then
    echo "  PASS: remote-shaped frames captured and structured"; PASS=$((PASS+1))
  else
    echo "  FAIL: no synthetic frames captured - capture path or squelch"; FAIL=$((FAIL+1))
  fi
else
  echo "  SKIP: no rflib venv"
fi

echo
echo "--- restoring bench state: 433.920 MHz, BW=58, squelch -85 ---"
rig "CFG FREQ=433.920000" "CFG BW=58" "CFG SQUELCH=-85" "RX ON" | grep '^CFG' || true

echo
echo "############################################################"
echo "# RESULT: $PASS passed, $FAIL failed"
if [ "$FAIL" -eq 0 ]; then
  echo "# Bench is sound. If something is not being heard, it is not this bench."
else
  echo "# Bench has faults - fix these before believing any 'no signal' result."
fi
echo "############################################################"
exit "$FAIL"
