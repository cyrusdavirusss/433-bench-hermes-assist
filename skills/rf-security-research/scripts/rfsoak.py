#!/usr/bin/env python3
"""Long-duration 433 MHz soak logger: capture continuously, store everything, query later.

This is the collector half of the "measure for a long time, then filter by signal" workflow.
It parks the CC1101 rig on a frequency and logs EVERY burst that clears the squelch, for as long
as you ask, into both a JSONL file (complete, greppable) and a SQLite database (queryable, so the
later cryptanalysis can select by signal rather than by scrolling a log).

Each stored transmission carries the raw pulse train, so nothing is lost for later analysis:

    session, timestamp, device clock (ms), RSSI, gap, pulse count, all pulse widths,
    PWM-decoded bit string, and a signal signature

The signature groups transmissions that share a structure (pulse count + 1T/2T timing + preamble
length), which is what makes "filter by signal" work: a PTX-4, a weather station and a tyre sensor
land in different signal rows and can be exported separately.

    rfsoak.py --seconds 3600 --label "ptx4 button1, 2s presses"
    rfsoak.py --seconds 600 --freq 433.920 --squelch -95     # open it up, catch weaker things

Then:  rfselect.py list / rfselect.py crypt --sig N

Notes learned the hard way:
  * the rig buffers several frames and hands them over in one USB read, so host arrival times bunch
    together. All timing decisions use the DEVICE clock field, never the host clock.
  * squelch at -85 sees real remotes; wide open at -95 it sees more, plus far more noise. The
    `weak` rows are kept (rssi <= CEILING) because a weak signal now may be a close one later.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sqlite3
import statistics
import sys
import time
from collections import Counter

import serial

CEILING = -90.0          # below this it is not a real signal, just recorded as weak
SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(
  id INTEGER PRIMARY KEY, started TEXT, ended TEXT, freq REAL, bw INTEGER, squelch REAL,
  label TEXT, notes TEXT, seconds REAL);
CREATE TABLE IF NOT EXISTS signals(
  sig INTEGER PRIMARY KEY, signature TEXT UNIQUE, npulses INTEGER, pulse_lo REAL, pulse_hi REAL,
  baud REAL, preamble INTEGER, first_seen TEXT, last_seen TEXT, count INTEGER DEFAULT 0,
  weak_count INTEGER DEFAULT 0, label TEXT);
CREATE TABLE IF NOT EXISTS transmissions(
  id INTEGER PRIMARY KEY, session INTEGER, sig INTEGER, t_dev_ms INTEGER, ts TEXT,
  rssi REAL, gap INTEGER, npulses INTEGER, pulses TEXT, bits TEXT, weak INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS heartbeats(
  id INTEGER PRIMARY KEY, session INTEGER, ts TEXT, floor REAL, note TEXT);
CREATE INDEX IF NOT EXISTS tx_sig ON transmissions(sig, t_dev_ms);
CREATE INDEX IF NOT EXISTS tx_ts  ON transmissions(ts);
"""


def parse_frame(line):
    """FRAME <seq> <t_ms> <rssi> <lvl> <gap> <pulse widths...>"""
    p = line.split()
    if len(p) < 7 or p[0] != "FRAME":
        return None
    try:
        return {"seq": int(p[1]), "t_ms": int(p[2]), "rssi": float(p[3]),
                "lvl": int(p[4]), "gap": int(p[5]), "pulses": [int(x) for x in p[6:]]}
    except ValueError:
        return None


def _pairs(pulses, phase):
    return [(pulses[i], pulses[i + 1]) for i in range(phase, len(pulses) - 1, 2)]


def structure(pulses):
    """Symbol split, timings, baud, and the PWM payload with a data-driven bit alignment.

    Bit alignment is chosen from the data, not from the preamble: the preamble is a run of SHORT
    pulses, and that run crosses pair boundaries (a sync pair followed by a data pair still starts
    with a short pulse), so its length is NOT a bit boundary. Shifting by it misaligns every pair —
    similarity within a press collapsed from ~0.96 to ~0.76 when that was tried.

    Instead: pair the train both ways, keep the phase with the most consistent PWM pairs
    (~1180 us), then drop the sync pairs (short+short, ~780 us). What is left is the payload.
    """
    if not pulses:
        return None
    med = sorted(w for w in pulses if 100 < w < 2000)
    if not med:
        return None
    thr = med[len(med) // 2] * 1.5
    sym = "".join("S" if 100 < w < 2000 and w < thr else ("L" if 100 < w < 2000 else "?")
                  for w in pulses)
    lo = [w for w, s in zip(pulses, sym) if s == "S"]
    hi = [w for w, s in zip(pulses, sym) if s == "L"]
    m = re.match(r"^(S+)", sym)
    preamble = len(m.group(1)) if m else 0
    pulse_lo = statistics.median(lo) if lo else 0.0
    pulse_hi = statistics.median(hi) if hi else 0.0
    baud = 1e6 / (pulse_lo + pulse_hi) if (pulse_lo and pulse_hi) else 0.0

    best = None
    for phase in (0, 1):
        pr = _pairs(pulses, phase)
        if not pr:
            continue
        score = sum(1 for a, b in pr if 1050 <= a + b <= 1350)
        if best is None or score > best[0]:
            best = (score, phase, pr)
    if not best:
        return None
    _, phase, pr = best
    data = [(a, b) for a, b in pr if a + b >= 1000]      # drop short+short sync pairs
    bits = "".join("1" if a < b else "0" for a, b in data)
    return {"sym": sym, "lo": pulse_lo, "hi": pulse_hi, "preamble": preamble, "baud": baud,
            "bits": bits, "phase": phase, "sync": len(pr) - len(data), "data_bit_pairs": len(data)}


def signature_of(st, npulses):
    return f"{npulses}|{round(st['lo'] / 25) * 25:.0f}|{round(st['hi'] / 25) * 25:.0f}|{st['preamble']}"


def open_db(path):
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    return db


def upsert_signal(db, sig, st, npulses, ts, weak):
    row = db.execute("SELECT sig, count, weak_count FROM signals WHERE signature=?", (sig,)).fetchone()
    if row:
        db.execute("UPDATE signals SET last_seen=?, count=count+?, weak_count=weak_count+? WHERE sig=?",
                   (ts, 0 if weak else 1, 1 if weak else 0, row[0]))
        return row[0]
    cur = db.execute(
        "INSERT INTO signals(signature, npulses, pulse_lo, pulse_hi, baud, preamble, first_seen,"
        " last_seen, count, weak_count) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (sig, npulses, st["lo"], st["hi"], st["baud"], st["preamble"], ts, ts,
         0 if weak else 1, 1 if weak else 0))
    return cur.lastrowid


def main():
    ap = argparse.ArgumentParser(description="Long-duration 433 soak logger")
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--seconds", type=float, default=3600.0)
    ap.add_argument("--freq", type=float, default=433.920)
    ap.add_argument("--bw", type=int, default=58)
    ap.add_argument("--squelch", type=float, default=-85.0)
    ap.add_argument("--outdir", default="/home/cyrus/Documents/rf")
    ap.add_argument("--label", default="", help="free text, stored with the session")
    ap.add_argument("--heartbeat", type=float, default=30.0)
    args = ap.parse_args()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    os.makedirs(args.outdir, exist_ok=True)
    jsonl = os.path.join(args.outdir, f"soak-{stamp}.jsonl")
    dbpath = os.path.join(args.outdir, "rfsoak.db")
    db = open_db(dbpath)
    started = datetime.datetime.now()
    cur = db.execute("INSERT INTO sessions(started, freq, bw, squelch, label, seconds) VALUES (?,?,?,?,?,?)",
                     (started.isoformat(timespec="seconds"), args.freq, args.bw, args.squelch,
                      args.label, args.seconds))
    session = cur.lastrowid
    db.commit()

    print(f"soak session {session}: {args.freq:.3f} MHz BW={args.bw} squelch={args.squelch} "
          f"for {args.seconds:.0f}s", flush=True)
    print(f"  jsonl: {jsonl}", flush=True)
    print(f"  db:    {dbpath}", flush=True)
    if args.label:
        print(f"  label: {args.label}", flush=True)

    stored = weak_n = dup_n = 0
    per_sig = Counter()
    deadline = time.monotonic() + args.seconds
    last_hb = time.monotonic()
    prev_dev = None
    buf = ""

    with serial.Serial(args.port, 115200, timeout=0.2) as s, open(jsonl, "w") as jf:
        time.sleep(1.2)
        s.reset_input_buffer()
        for c in (f"CFG FREQ={args.freq:.6f}", f"CFG BW={args.bw}",
                  f"CFG SQUELCH={args.squelch}", "RX ON", "LOG 1"):
            s.write((c + "\n").encode())
            time.sleep(0.7)
        jf.write(json.dumps({"kind": "header", "session": session, "started": started.isoformat(),
                             "freq": args.freq, "bw": args.bw, "squelch": args.squelch,
                             "label": args.label}) + "\n")
        jf.flush()

        while time.monotonic() < deadline:
            try:
                chunk = s.read(s.in_waiting or 1)
            except serial.SerialException as exc:
                print(f"  serial hiccup: {exc}", flush=True)
                time.sleep(0.3)
                continue
            if chunk:
                buf += chunk.decode("utf-8", "replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line.startswith("FRAME"):
                        continue
                    f = parse_frame(line)
                    if not f:
                        continue
                    st = structure(f["pulses"])
                    if not st:
                        continue
                    # duplicate delivery: the rig hands a buffered frame over twice at the device-clock
                    # level. Real repeats are ~100 ms apart on the device clock, so anything under
                    # 5 ms with the same pulse count is the same transmission.
                    dup = (prev_dev is not None and 0 <= f["t_ms"] - prev_dev < 5)
                    prev_dev = f["t_ms"]
                    now = datetime.datetime.now()
                    weak = f["rssi"] <= CEILING
                    sig = signature_of(st, len(f["pulses"]))
                    sig_id = upsert_signal(db, sig, st, len(f["pulses"]),
                                           now.isoformat(timespec="milliseconds"), weak)
                    db.execute("INSERT INTO transmissions(session, sig, t_dev_ms, ts, rssi, gap,"
                               " npulses, pulses, bits, weak) VALUES (?,?,?,?,?,?,?,?,?,?)",
                               (session, sig_id, f["t_ms"], now.isoformat(timespec="milliseconds"),
                                f["rssi"], f["gap"], len(f["pulses"]), ",".join(map(str, f["pulses"])),
                                st["bits"], 1 if weak else 0))
                    db.commit()
                    jf.write(json.dumps({"kind": "tx", "sig": sig, "sig_id": sig_id, "ts": now.isoformat(),
                                         "t_dev_ms": f["t_ms"], "rssi": f["rssi"], "gap": f["gap"],
                                         "npulses": len(f["pulses"]), "lo": st["lo"], "hi": st["hi"],
                                         "preamble": st["preamble"], "baud": round(st["baud"], 1),
                                         "bits": st["bits"], "pulses": f["pulses"],
                                         "dup": dup, "weak": weak}) + "\n")
                    jf.flush()
                    if dup:
                        dup_n += 1
                        continue
                    if weak:
                        weak_n += 1
                        continue
                    stored += 1
                    per_sig[sig_id] += 1
                    print(f"  {now:%H:%M:%S}  sig {sig_id:<3} {f['rssi']:7.1f} dBm  "
                          f"{len(f['pulses']):>4} pulses  {st['baud']:6.1f} bps  "
                          f"pre {st['preamble']:<3} bits {len(st['bits'])}", flush=True)
            if time.monotonic() - last_hb >= args.heartbeat:
                last_hb = time.monotonic()
                s.write(b"RSSI\n")
                time.sleep(0.3)
                floor = None
                txt = s.read(400).decode(errors="replace")
                m = re.search(r"RSSI\s+(-?[\d.]+)", txt)
                if m:
                    floor = float(m.group(1))
                db.execute("INSERT INTO heartbeats(session, ts, floor, note) VALUES (?,?,?,?)",
                           (session, datetime.datetime.now().isoformat(timespec="seconds"), floor,
                            f"{stored} stored, {weak_n} weak, {dup_n} dup"))
                db.commit()
                jf.write(json.dumps({"kind": "heartbeat", "ts": time.time(), "floor": floor,
                                     "stored": stored, "weak": weak_n}) + "\n")
                jf.flush()
                print(f"  ...heartbeat: {stored} stored, {weak_n} weak, {dup_n} duplicate "
                      f"(floor {floor} dBm)", flush=True)

        s.write(b"LOG 0\n"); time.sleep(0.4)
        s.write(b"CFG SQUELCH=-85\n"); time.sleep(0.4)

    ended = datetime.datetime.now()
    db.execute("UPDATE sessions SET ended=?, notes=? WHERE id=?",
               (ended.isoformat(timespec="seconds"),
                f"stored={stored} weak={weak_n} dup={dup_n}", session))
    db.commit()
    print(f"\n=== session {session} done after {args.seconds:.0f}s ===")
    print(f"  {stored} transmissions stored, {weak_n} below the {CEILING} dBm ceiling, "
          f"{dup_n} duplicate deliveries")
    for sig_id, n in per_sig.most_common(8):
        row = db.execute("SELECT signature, npulses, pulse_lo, pulse_hi, baud, preamble FROM signals"
                         " WHERE sig=?", (sig_id,)).fetchone()
        print(f"  sig {sig_id:<3} {n:>5} frames  {row[1]:>4} pulses  "
              f"{row[2]:.0f}/{row[3]:.0f} us  {row[4]:.0f} bps  preamble {row[5]}   [{row[0]}]")
    print(f"  query it with:  rfselect.py list    (db: {dbpath})")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
