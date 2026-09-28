#!/usr/bin/env python3
"""Hunt a transmitter's frequency using the demodulated-edge counter, not RSSI.

Earlier sweeps on this bench sampled each frequency once with an RSSI read, which a short
burst can slip between. STATS "edges" counts transitions on GDO0 and is level-independent:
when a real signal is present the counter jumps hard (a captured PT2262 frame adds ~26
edges; 40 frames added >1,000). So park, settle, and measure the edge delta per frequency.

Hold the transmitter on continuously for the whole run.

    python3 edge_hunt.py --seconds 150
"""
import argparse
import os
import statistics
import sys
import time

import serial


def send(s, cmd, wait=0.9, n=20000):
    s.write((cmd + "\n").encode())
    time.sleep(wait)
    return s.read(n).decode(errors="replace")


def stat_value(txt, key):
    for line in txt.splitlines():
        if line.startswith("STATS"):
            for tok in line.split():
                if tok.startswith(key + "="):
                    try:
                        return float(tok.split("=")[1])
                    except ValueError:
                        return 0.0
    return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--seconds", type=float, default=150.0)
    ap.add_argument("--dwell", type=float, default=2.0)
    ap.add_argument("--step-khz", type=float, default=100.0)
    ap.add_argument("--start", type=float, default=433.0)
    ap.add_argument("--stop", type=float, default=435.0)
    ap.add_argument("--bw", type=int, default=58)
    ap.add_argument("--outdir", default=os.path.expanduser("~/Documents/rf"))
    args = ap.parse_args()

    freqs = []
    f = args.start
    while f <= args.stop + 1e-9:
        freqs.append(round(f, 6))
        f += args.step_khz / 1000.0

    out = os.path.join(args.outdir, time.strftime("edge-hunt-%Y%m%d-%H%M%S.log"))
    with serial.Serial(args.port, 115200, timeout=1) as s:
        time.sleep(1.5)
        s.reset_input_buffer()
        send(s, f"CFG BW={args.bw}")
        print(f"edge-rate hunt: {len(freqs)} frequencies, {args.dwell:.0f}s each, "
              f"BW={args.bw} kHz -> {out}", flush=True)
        print("hold the transmitter ON for the whole run", flush=True)

        results = []
        deadline = time.monotonic() + args.seconds
        with open(out, "w") as fh:
            fh.write(f"# edge-rate hunt, BW={args.bw}, dwell={args.dwell}s\n")
            for fr in freqs:
                if time.monotonic() > deadline:
                    break
                send(s, f"CFG FREQ={fr:.6f}")
                send(s, "RX ON", 0.4)
                e0 = stat_value(send(s, "STATS", 0.5), "edges")
                time.sleep(args.dwell)
                e1 = stat_value(send(s, "STATS", 0.5), "edges")
                rate = (e1 - e0) / args.dwell
                results.append((fr, rate))
                fh.write(f"{fr:.4f}  {e1 - e0:8.0f} edges  {rate:9.0f}/s\n")
                fh.flush()
                flag = "   <-- elevated" if rate > 200 else ""
                print(f"  {fr:.3f} MHz  {rate:9.0f} edges/s{flag}", flush=True)

    print("\n=== ranked ===")
    for fr, rate in sorted(results, key=lambda x: -x[1])[:8]:
        print(f"  {fr:.3f} MHz   {rate:9.0f} edges/s")
    if results:
        base = statistics.median([r for _, r in results])
        top = max(results, key=lambda x: x[1])
        print(f"  median across band {base:.0f} edges/s")
        if top[1] > max(200, base * 5):
            print(f"\n  SIGNAL at {top[0]:.3f} MHz ({top[1]:.0f}/s vs median {base:.0f}/s)")
            print("  park there and re-run the capture test")
        else:
            print("\n  nothing standing out above the band median - no transmission found")
    print(f"  log: {out}")
    # leave the rig parked on the bench's operating frequency, not on the last scanned one
    with serial.Serial(args.port, 115200, timeout=1) as s2:
        time.sleep(1.0)
        s2.write(b"CFG FREQ=433.920000\n")
        time.sleep(0.8)
    print("  rig re-parked on 433.920 MHz")
    return 0


if __name__ == "__main__":
    sys.exit(main())
