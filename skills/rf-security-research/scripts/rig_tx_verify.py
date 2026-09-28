#!/usr/bin/env python3
"""Close the last open question on the bench: does the ESP32+CC1101 RIG actually transmit?

The YARD Stick One used as the receiver (it has a working antenna now), the rig used as the
transmitter via its own firmware commands. The dongle samples RSSI before / during / after
the rig transmits, so the answer is a level rise, not an opinion.

    sudo /tmp/ys1venv/bin/python rig_tx_verify.py

Needs both devices plugged in. Only reads the rig's serial port and the dongle's USB - it does
not reconfigure the rig beyond the TX commands, and it restores RX on the rig when done.
"""
import statistics
import sys
import time

import serial
from rflib import RfCat, MOD_ASK_OOK

RIG_PORT = "/dev/ttyUSB0"
FREQ = 433920000
BAUD = 4800


def rssi_dbm(d):
    v = d.getRSSI()
    if isinstance(v, (bytes, bytearray)):
        v = int.from_bytes(v[:1], "big")
    try:
        v = int(v)
    except (TypeError, ValueError):
        return None
    return (v - 256) / 2.0 - 74 if v > 127 else v / 2.0 - 74


def sample(d, seconds, label):
    vals, deadline = [], time.monotonic() + seconds
    while time.monotonic() < deadline:
        c = rssi_dbm(d)
        if c is not None:
            vals.append(c)
        time.sleep(0.12)
    if not vals:
        print(f"  {label:<22} no samples")
        return None
    med = statistics.median(vals)
    print(f"  {label:<22} median {med:7.1f}  max {max(vals):7.1f}  min {min(vals):7.1f}  "
          f"({len(vals)} samples)")
    return med


def rig_cmd(s, cmd, wait=0.8):
    s.write((cmd + "\n").encode())
    time.sleep(wait)
    return s.read(8000).decode(errors="replace")


def main():
    print("opening the dongle as receiver...")
    d = RfCat(debug=False)
    d.setFreq(FREQ)
    d.setMdmModulation(MOD_ASK_OOK)
    d.setMdmDRate(BAUD)
    try:
        d.setMdmSyncMode(0)
        d.setMdmNumPreamble(0)
    except Exception:
        pass
    d.setModeRX()
    time.sleep(1.0)

    print("opening the rig...")
    try:
        s = serial.Serial(RIG_PORT, 115200, timeout=1)
    except Exception as exc:
        print(f"  rig not available on {RIG_PORT}: {exc}")
        d.cleanup()
        return 1
    time.sleep(1.2)
    s.reset_input_buffer()
    for k in ("INFO", "CFG"):
        for l in rig_cmd(s, k).splitlines():
            if l.startswith(k):
                print("   ", l.strip()[:130])

    base = sample(d, 6.0, "baseline (rig quiet)")
    print("\n  -> commanding the rig to TRANSMIT (TX OPT REPEAT=20 GAP=100)")
    rig_cmd(s, "TX OPT REPEAT=20 GAP=100")
    during = sample(d, 12.0, "during rig TX")

    print("\n  -> TX STOP")
    rig_cmd(s, "TX STOP")
    after = sample(d, 5.0, "after TX stop")

    print("\n=== verdict ===")
    if base is None or during is None:
        print("  inconclusive: no dongle samples")
    else:
        delta = during - base
        print(f"  rig-quiet {base:.1f} dBm  ->  rig-TX {during:.1f} dBm   delta {delta:+.1f} dB")
        if delta > 10:
            print("  RIG TRANSMITS: the dongle heard the rig on air.")
        elif delta > 3:
            print("  MARGINAL: some rise. Re-run at 1-2 cm separation and check the rig's antenna.")
        else:
            print("  RIG DID NOT RADIATE (or is far from the dongle / has no antenna). Try:\n"
                  "    * put the antennas 2-5 cm apart\n"
                  "    * check the rig's antenna is fitted\n"
                  "    * try 'TX RAW 500 500 500 500 500 500' and repeat")
        if after is not None:
            print(f"  after stop {after:.1f} dBm (should fall back towards {base:.1f})")

    rig_cmd(s, "RX ON")
    s.close()
    try:
        d.setModeIDLE()
        d.cleanup()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
