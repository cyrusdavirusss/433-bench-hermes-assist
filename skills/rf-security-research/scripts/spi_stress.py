#!/usr/bin/env python3
"""SPI integrity stress test for the ESP32 + CC1101 bench rig.

Built to prove a repair, not to assume one. A loose MISO (pin 7 on the E07-M1101D) lets
the firmware WRITE configuration but corrupts everything it READS BACK, so this leans on
the read paths available in fw 1.0.0:

  * REGS   - 47 register reads per dump. All dumps must be byte-identical; a mismatch or
             a value outside the known-good image means MISO swallowed data.
  * INFO   - partnum/version must be 0x00/0x14 every single time. Anything else (0x00
             partnum with 0x00 version, or 0xFF) is a dropout.
  * RSSI   - many reads; reports spread and any non-numeric/absent replies.

Run it BEFORE the repair to record the fault, and AFTER to prove it's gone:

    python3 spi_stress.py --dumps 10 --rssi 40
"""
import argparse
import statistics
import sys
import time

import serial

# the bench's known-good register image (firmware writes this every boot)
KNOWN = {0x02: 0x0D, 0x03: 0x47, 0x08: 0x32, 0x12: 0x30, 0x18: 0x18,
         0x29: 0x59, 0x2A: 0x7F, 0x2C: 0x81, 0x2D: 0x35, 0x2E: 0x09}


def send(s, cmd, wait=1.0, n=40000):
    s.write((cmd + "\n").encode())
    time.sleep(wait)
    return s.read(n).decode(errors="replace")


def line_starting(txt, key):
    for l in txt.splitlines():
        if l.strip().startswith(key):
            return l.strip()
    return ""


def dump_regs(s):
    out = send(s, "REGS", 3.5, 60000)
    d = {}
    for l in out.splitlines():
        p = l.split()
        if len(p) == 3 and p[0] == "REG":
            try:
                d[int(p[1], 16)] = int(p[2], 16)
            except ValueError:
                pass
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--dumps", type=int, default=10)
    ap.add_argument("--rssi", type=int, default=40)
    args = ap.parse_args()

    with serial.Serial(args.port, 115200, timeout=1) as s:
        time.sleep(1.5)
        s.reset_input_buffer()
        print("=" * 62)
        print(line_starting(send(s, "INFO"), "INFO"))
        send(s, "RX ON")

        # --- INFO version/partnum stability -------------------------------
        bad_info, seen = 0, {}
        for _ in range(15):
            info = line_starting(send(s, "INFO", 0.9), "INFO")
            seen[info] = seen.get(info, 0) + 1
            if "partnum=0x00" not in info or "version=0x14" not in info:
                bad_info += 1
        print(f"\nINFO x15  : {15 - bad_info}/15 correct (partnum 0x00, version 0x14)")
        if bad_info:
            print(f"            {bad_info} bad reads -> MISO dropouts")
            for info, n in seen.items():
                if "partnum=0x00" not in info or "version=0x14" not in info:
                    print(f"            x{n}: {info[:110]}")

        # --- register image stability ------------------------------------
        print(f"\nREGS x{args.dumps}:")
        dumps, mismatches, missing = [], 0, 0
        for i in range(args.dumps):
            d = dump_regs(s)
            dumps.append(d)
            if len(d) < 40:
                missing += 1
            if i and d != dumps[0]:
                diffs = [f"0x{a:02X}:{dumps[0].get(a)}->{d.get(a)}"
                         for a in sorted(set(dumps[0]) | set(d)) if dumps[0].get(a) != d.get(a)]
                mismatches += 1
                print(f"  dump {i+1} DIFFERS: {', '.join(diffs[:8])}")
        print(f"  {args.dumps - mismatches}/{args.dumps} dumps identical"
              f"   short dumps (<40 regs): {missing}")
        last = dumps[-1] if dumps else {}
        print("  known-good image check:")
        for a, want in KNOWN.items():
            got = last.get(a)
            flag = "" if got == want else "   <-- EXPECTED 0x%02X" % want
            print(f"    0x{a:02X}: {'0x%02X' % got if got is not None else '--'}{flag}")
        if 0x2B in last:
            print(f"    0x2B AGCTEST = 0x{last[0x2B]:02X} (AGC status window; varies in RX)")

        # --- RSSI read stability -----------------------------------------
        vals, bad_rssi = [], 0
        for _ in range(args.rssi):
            for l in send(s, "RSSI", 0.75).splitlines():
                if l.startswith("RSSI "):
                    try:
                        vals.append(float(l.split()[1]))
                    except (IndexError, ValueError):
                        bad_rssi += 1
        print(f"\nRSSI x{args.rssi}: {len(vals)} parsed, {bad_rssi} unparseable")
        if vals:
            print(f"  median {statistics.median(vals):.1f}  min {min(vals):.1f}  max {max(vals):.1f}"
                  f"  spread {max(vals)-min(vals):.1f} dB")
            zeros = [v for v in vals if v == -74.0]      # raw 0x00 -> -74.0 dBm
            print(f"  reads landing exactly on -74.0 dBm (raw 0x00 = MISO dead): {len(zeros)}")
        s.close()

    print("\nverdict:")
    problems = []
    if bad_info:
        problems.append(f"{bad_info}/15 INFO reads wrong")
    if mismatches:
        problems.append(f"{mismatches}/{args.dumps} REGS dumps inconsistent")
    if missing:
        problems.append(f"{missing}/{args.dumps} short REGS dumps")
    if bad_rssi:
        problems.append(f"{bad_rssi} unparseable RSSI replies")
    if problems:
        print("  SPI IS NOT SOLID: " + "; ".join(problems))
        return 1
    print("  all read paths consistent - MISO delivering every byte")
    return 0


if __name__ == "__main__":
    sys.exit(main())
