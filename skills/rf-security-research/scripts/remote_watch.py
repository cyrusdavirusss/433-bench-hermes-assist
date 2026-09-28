#!/usr/bin/env python3
"""Watch the rig and report EVERY remote-shaped burst, with a structural verdict.

For a pile of remotes: park once, then press each one in turn at contact range. Each
frame is logged with a wall-clock timestamp, its level, its edge count and its pulse-width
structure, so the log can be segmented afterwards ("which remote was at 19:04:12?").

Verdicts:
  * level  - frame RSSI vs the bench noise ceiling (-90 dBm). Below it = noise, not a remote.
  * edges  - a genuine fixed-code frame lands in the tens (e.g. 26 for a 12-symbol PT2262);
             ambient noise bursts run to hundreds.
  * widths - clustered into distinct values. A fixed-code OOK remote shows 2-3 clusters in
             roughly 1:3 (PT2262/EV1527); a smear means noise or a bit-rate mismatch.

    python3 remote_watch.py --seconds 300
"""
import argparse
import datetime
import os
import statistics
import sys
import time
from collections import Counter

import serial

BUFFER_KEEP = 25.0      # seconds between bursts still considered the same press
CEILING = -90.0


def parse_frame(line):
    p = line.split()
    if len(p) < 6 or p[0] != "FRAME":
        return None
    try:
        return {"seq": int(p[1]), "t_ms": int(p[2]), "rssi": float(p[3]),
                "lvl": int(p[4]), "gap": int(p[5]), "edges": [int(x) for x in p[6:]]}
    except ValueError:
        return None


def structure(edges, bucket=50):
    buckets = Counter(int(round(e / bucket) * bucket) for e in edges if e > 0)
    total = sum(buckets.values()) or 1
    main = [(w, n) for w, n in buckets.most_common() if n / total >= 0.08]
    verdict = "smear (noise or rate mismatch)"
    ratio = None
    if 1 <= len(main) <= 3:
        ws = sorted(w for w, _ in main)
        ratio = ws[-1] / ws[0] if ws[0] else None
        verdict = f"clean {len(main)}-width pattern"
    return main[:4], ratio, verdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--seconds", type=float, default=300.0)
    ap.add_argument("--freq", type=float, default=433.920)
    ap.add_argument("--bw", type=int, default=58)
    ap.add_argument("--squelch", type=float, default=-85.0)
    ap.add_argument("--outdir", default="/home/cyrus/Documents/rf")
    args = ap.parse_args()

    out = os.path.join(args.outdir, time.strftime("remote-watch-%Y%m%d-%H%M%S.log"))
    with serial.Serial(args.port, 115200, timeout=0.2) as s:
        time.sleep(1.2)
        s.reset_input_buffer()
        for c in (f"CFG FREQ={args.freq:.6f}", f"CFG BW={args.bw}",
                  f"CFG SQUELCH={args.squelch}", "RX ON", "LOG 1"):
            s.write((c + "\n").encode())
            time.sleep(0.7)
        print(f"watching {args.freq:.3f} MHz, BW={args.bw}, squelch={args.squelch} for "
              f"{args.seconds:.0f}s -> {out}", flush=True)
        print("press each remote in turn, at contact range, a few times each", flush=True)

        frames, bursts = [], []
        deadline = time.monotonic() + args.seconds
        last_report = time.monotonic()
        buf = ""
        with open(out, "w") as fh:
            fh.write(f"# remote watch {time.strftime('%F %T')} freq={args.freq} bw={args.bw} "
                     f"squelch={args.squelch}\n")
            while time.monotonic() < deadline:
                try:
                    chunk = s.read(s.in_waiting or 1)
                except serial.SerialException as exc:
                    print(f"  serial hiccup: {exc}", flush=True)
                    time.sleep(0.3)
                    continue
                if not chunk:
                    continue
                buf += chunk.decode("utf-8", "replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line.startswith("FRAME"):
                        continue
                    f = parse_frame(line)
                    if not f:
                        continue
                    now = datetime.datetime.now()
                    main, ratio, verdict = structure(f["edges"])
                    real = f["rssi"] > CEILING
                    frames.append((now, f))
                    tag = "SIGNAL" if real else "weak  "
                    print(f"  {now:%H:%M:%S} {tag} rssi={f['rssi']:7.1f} dBm  "
                          f"edges={len(f['edges']):5d}  {verdict}"
                          + (f"  ~1:{ratio:.1f}" if ratio else ""), flush=True)
                    fh.write(f"{now:%H:%M:%S.%f}  rssi={f['rssi']:.1f}  "
                             f"edges={len(f['edges'])}  widths={[w for w, _ in main]}  "
                             f"{verdict}  raw={line}\n")
                    fh.flush()
                if time.monotonic() - last_report > 30:
                    last_report = time.monotonic()
                    strong = sum(1 for _, f in frames if f["rssi"] > CEILING)
                    print(f"  ...{len(frames)} frames so far, {strong} above the ceiling",
                          flush=True)

            s.write(b"LOG 0\n"); time.sleep(0.5)
            s.write(f"CFG SQUELCH=-85\n".encode()); time.sleep(0.5)

    print("\n=== summary ===")
    if not frames:
        print("  no frames at all - nothing passed the squelch in that window")
        return 0
    strong = [(t, f) for t, f in frames if f["rssi"] > CEILING]
    print(f"  {len(frames)} frames, {len(strong)} above the {CEILING} dBm ceiling")
    if strong:
        lv = [f["rssi"] for _, f in strong]
        ed = [len(f["edges"]) for _, f in strong]
        print(f"  signal frames: rssi median {statistics.median(lv):.1f} dBm, "
              f"edges median {statistics.median(ed):.0f}")
        print(f"  first signal at {strong[0][0]:%H:%M:%S}, last at {strong[-1][0]:%H:%M:%S}")
    print(f"  log: {out}")
    print("  tell me the order you pressed them in and I'll map it to the timestamps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
