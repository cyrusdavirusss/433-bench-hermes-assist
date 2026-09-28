#!/usr/bin/env python3
"""Capture a real 433.92 remote on the ESP32+CC1101 rig and say whether it is decodable.

  python3 remote_test.py --seconds 45

Parked on one frequency (no sweep), squelch left at the bench default -85. Writes every
raw FRAME line to ~/Documents/rf/remote-<timestamp>.log and prints a verdict:

  * did any frame clear the noise ceiling (i.e. was it a real signal)
  * how many edges per frame
  * the pulse-width structure - a fixed-code OOK remote (PT2262/EV1527) shows 2-3 distinct
    widths in roughly 1:3 ratios; random widths = noise or a bit-rate mismatch
  * whether two presses produced an identical edge sequence (a fixed code repeats)

Bit-rate caveat: the rig samples in async-serial mode at its configured data rate, so a
remote with a very different symbol rate produces garbage rather than nothing.
"""
import argparse
import os
import statistics
import sys
import time
from collections import Counter

import serial

BENCH_SQUELCH = -85.0


def send(s, cmd, wait=1.0, n=20000):
    s.write((cmd + "\n").encode())
    time.sleep(wait)
    return s.read(n).decode(errors="replace")


def line_starting(txt, key):
    for line in txt.splitlines():
        if line.strip().startswith(key):
            return line.strip()
    return ""


def parse_frame(line):
    p = line.split()
    if len(p) < 6 or p[0] != "FRAME":
        return None
    try:
        return {
            "seq": int(p[1]), "t_ms": int(p[2]), "rssi": float(p[3]),
            "lvl": int(p[4]), "gap": int(p[5]), "edges": [int(x) for x in p[6:]],
        }
    except ValueError:
        return None


def cluster(widths, bucket=50):
    """Round pulse widths into buckets so 1T/3T structure is visible."""
    return Counter(int(round(w / bucket) * bucket) for w in widths if w > 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--seconds", type=float, default=45.0)
    ap.add_argument("--freq", type=float, default=433.920)
    ap.add_argument("--bw", type=int, default=58,
                    help="RX filter kHz. 58 measured clean on this bench for OOK pulses at "
                         "~1-3 kbaud; 100 (the firmware default) smears them into ~50us "
                         "chatter and 25 is too narrow. Verified 27 Sep 2026.")
    ap.add_argument("--outdir", default=os.path.expanduser("~/Documents/rf"))
    args = ap.parse_args()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = os.path.join(args.outdir, f"remote-{stamp}.log")

    with serial.Serial(args.port, 115200, timeout=0.05) as s:
        time.sleep(1.2)
        s.reset_input_buffer()
        print(line_starting(send(s, "INFO"), "INFO"))
        send(s, f"CFG FREQ={args.freq:.6f}")
        send(s, f"CFG BW={args.bw}")
        print(line_starting(send(s, "CFG"), "CFG"))
        send(s, "RX ON")
        send(s, "LOG 1")
        for line in send(s, "STATS").splitlines():
            if line.startswith("STATS"):
                s0 = line.strip()
                print("  before:", s0)

        print(f"\ncapturing {args.seconds:.0f} s - press the remote now, same button, "
              f"repeated presses\n")
        deadline = time.monotonic() + args.seconds
        buf, frames, caps = "", [], []
        while time.monotonic() < deadline:
            try:
                chunk = s.read(s.in_waiting or 1)
            except serial.SerialException as exc:
                # transient USB/serial hiccup, or another process grabbed the port -
                # do not abandon the whole capture for it
                print(f"  serial hiccup: {exc}", flush=True)
                time.sleep(0.2)
                continue
            if not chunk:
                continue
            buf += chunk.decode("utf-8", "replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if line.startswith("FRAME"):
                    f = parse_frame(line)
                    if f:
                        frames.append(f)
                        print(f"  CAPTURE seq={f['seq']} t={f['t_ms']}ms rssi={f['rssi']} dBm "
                              f"lvl={f['lvl']} gap={f['gap']}us edges={len(f['edges'])}")
                elif line.startswith(("LOG cap", "LOG dropped", "OK", "ERR")):
                    caps.append(line)

        send(s, "LOG 0")
        s1 = line_starting(send(s, "STATS"), "STATS")
        print("  after :", s1)

    with open(out, "w") as fh:
        fh.write(f"# remote_test {stamp}  freq={args.freq} MHz  seconds={args.seconds}\n")
        fh.write(f"# before: {s0}\n# after : {s1}\n")
        for f in frames:
            fh.write("FRAME {} {} {} {} {} {}\n".format(
                f["seq"], f["t_ms"], f["rssi"], f["lvl"], f["gap"],
                " ".join(str(e) for e in f["edges"])))
        fh.write("# misc:\n" + "\n".join(caps) + "\n")

    print(f"\n=== result ===\nraw log: {out}")
    if not frames:
        print("  NO captures. The rig heard nothing above squelch -85 for the whole window.")
        print("  Not a receiver fault by itself: check the remote is really 433.92 MHz before")
        print("  touching any setting (the trigger was proven with the YS1 carrier minutes ago).")
        return 0

    rssis = [f["rssi"] for f in frames]
    print(f"  {len(frames)} frames captured")
    print(f"  frame rssi: median {statistics.median(rssis):.1f}  min {min(rssis):.1f}  "
          f"max {max(rssis):.1f} dBm   (noise ceiling on this bench is about -90)")
    strong = [r for r in rssis if r > -90]
    print(f"  frames above the noise ceiling: {len(strong)}/{len(frames)}"
          + ("   -> real signal" if strong else "   -> these look like noise captures"))
    ecounts = Counter(len(f["edges"]) for f in frames)
    print(f"  edges per frame: {dict(ecounts.most_common(5))}")

    all_edges = [e for f in frames for e in f["edges"]]
    if all_edges:
        b = cluster(all_edges)
        top = b.most_common(8)
        total = sum(b.values())
        print(f"  pulse-width buckets (50 us): {top}")
        print("    ratio check: a fixed-code remote shows 2-3 buckets, the long ~3x the short"
              if len(top) <= 3 else
              "    many buckets -> widths are not a clean 1T/3T pattern (noise, or bit-rate mismatch)")

    sigs = Counter(tuple(f["edges"]) for f in frames)
    dupes = [(k, v) for k, v in sigs.items() if v > 1]
    if dupes:
        k, v = max(dupes, key=lambda x: x[1])
        print(f"  repeated identical edge sequence in {v}/{len(frames)} frames "
              f"({len(k)} edges) -> consistent with a fixed-code remote pressed repeatedly")
    else:
        print("  no two frames identical - either different buttons were pressed, or the")
        print("  capture is being cut/split (check against the remote's real frame length)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
