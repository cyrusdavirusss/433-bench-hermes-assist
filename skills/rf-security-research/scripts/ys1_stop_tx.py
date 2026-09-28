#!/usr/bin/env python3
"""Force the YARD Stick One into IDLE and report the radio state.

Used to stop a transmission that a killed script left running: rflib does not reset the dongle
on process death, so a TX loop killed mid-flight keeps radiating until something tells it
otherwise (or it is physically unplugged).
"""
import sys

from rflib import RfCat

try:
    d = RfCat(debug=False)
except Exception as exc:
    print(f"dongle not reachable: {exc}")
    sys.exit(0)

print("dongle opened")
for meth in ("setModeIDLE", "setModeRX"):
    try:
        getattr(d, meth)()
        print(f"  {meth}: ok")
    except Exception as exc:
        print(f"  {meth}: {exc}")

try:
    # 0x35 = MARCSTATE: 0x01 = IDLE, 0x13/0x14/0x15/0x16 = TX states
    state = d.peek(0x35)[0]
    names = {0x01: "IDLE", 0x02: "MANCAL", 0x03: "FS_WAKEUP", 0x11: "RX", 0x13: "TX", 0x14: "TX_END",
             0x15: "RXTX_SETTLING", 0x16: "TXFIFO_UNDERFLOW", 0x17: "FSTXON"}
    print(f"  MARCSTATE = 0x{state:02X} ({names.get(state & 0x1F, 'unknown')})")
except Exception as exc:
    print(f"  marcstate read failed: {exc}")

try:
    d.cleanup()
    print("cleaned up")
except Exception as exc:
    print(f"cleanup: {exc}")
