#!/usr/bin/env python3
"""Query, filter and export what rfsoak.py captured — the second half of the workflow.

The soak tool stores everything; this one lets you say "give me just that signal" and then
hands it to cryptanalysis or to a decoder (URH / inspectrum / GNU Radio).

    rfselect.py sessions                        # what soaks exist
    rfselect.py list                            # every signal found, with its structure
    rfselect.py show   --sig 1 --limit 20       # the transmissions of one signal
    rfselect.py crypt  --sig 1                  # constant/varying bit analysis + counter hunt
    rfselect.py export --sig 1 --format bits --out /tmp/codes.txt
    rfselect.py export --sig 1 --format raw  --out /tmp/sig1.iq8   # for URH/inspectrum

Filters available on show/export/crypt: --sig, --since, --until (HH:MM[:SS] or ISO), --min-level,
--max-level, --label (session label substring), --limit.

WHY THIS EXISTS: recovering a hopping code needs many codes from the SAME device, and the key
question is which bit positions carry the fixed identity (serial, channel) versus the part that
changes every press. That is a filtering problem before it is a cryptanalysis problem.
"""
import argparse
import datetime
import json
import os
import re
import sqlite3
import statistics
import sys
from collections import Counter

DB_DEFAULT = "/home/cyrus/Documents/rf/rfsoak.db"


def connect(path):
    if not os.path.exists(path):
        sys.exit(f"no database at {path} — run rfsoak.py first")
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    return db


def parse_time(text):
    if not text:
        return None
    for fmt in ("%H:%M:%S", "%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            t = datetime.datetime.strptime(text, fmt)
        except ValueError:
            continue
        if "%Y" not in fmt:
            t = t.replace(year=datetime.date.today().year, month=datetime.date.today().month,
                          day=datetime.date.today().day)
        return t
    sys.exit(f"could not parse time {text!r} (use HH:MM[:SS] or 2026-09-28T22:30:00)")


def select(db, a):
    q = ("SELECT t.*, s.signature, s.npulses AS sig_npulses, s.preamble, s.baud, ses.label "
         "FROM transmissions t JOIN signals s ON s.sig=t.sig "
         "LEFT JOIN sessions ses ON ses.id=t.session WHERE 1=1")
    p = []
    if getattr(a, "sig", None) is not None:
        q += " AND t.sig=?"; p.append(a.sig)
    if getattr(a, "label", None):
        q += " AND IFNULL(ses.label,'') LIKE ?"; p.append(f"%{a.label}%")
    if getattr(a, "min_level", None) is not None:
        q += " AND t.rssi>=?"; p.append(a.min_level)
    if getattr(a, "max_level", None) is not None:
        q += " AND t.rssi<=?"; p.append(a.max_level)
    q += " ORDER BY t.ts"
    rows = db.execute(q, p).fetchall()
    since, until = parse_time(getattr(a, "since", None)), parse_time(getattr(a, "until", None))
    out = []
    for r in rows:
        iso = r["ts"]
        try:
            t = datetime.datetime.fromisoformat(iso)
        except ValueError:
            out.append(r); continue
        if since and t < since:
            continue
        if until and t > until:
            continue
        out.append(r)
    if getattr(a, "limit", None):
        out = out[:a.limit]
    return out


def bits_of(rows):
    """Align to the modal length so positions are comparable."""
    if not rows:
        return []
    lens = Counter(len(r["bits"] or "") for r in rows)
    modal = lens.most_common(1)[0][0]
    return [(r["t_dev_ms"], r["ts"], r["rssi"], r["bits"]) for r in rows if r["bits"] and len(r["bits"]) == modal]


def do_sessions(db, a):
    rows = db.execute("SELECT * FROM sessions ORDER BY id").fetchall()
    if not rows:
        print("  no sessions")
        return 0
    print(f"  {'id':>3}  {'started':<20} {'seconds':>8}  {'label':<38} notes")
    for r in rows:
        print(f"  {r['id']:>3}  {r['started'][:19]:<20} {r['seconds'] or 0:>8.0f}  "
              f"{(r['label'] or '')[:38]:<38} {r['notes'] or ''}")
    return 0


def do_list(db, a):
    rows = db.execute("""SELECT s.*, (SELECT MIN(rssi) FROM transmissions t WHERE t.sig=s.sig) lo,
                                (SELECT MAX(rssi) FROM transmissions t WHERE t.sig=s.sig) hi,
                                (SELECT COUNT(DISTINCT substr(ts,1,8)) FROM transmissions t WHERE t.sig=s.sig) secs
                         FROM signals s WHERE s.count+s.weak_count > 0 ORDER BY s.count DESC""").fetchall()
    if not rows:
        print("  nothing captured yet")
        return 0
    print(f"  {'sig':>3}  {'frames':>6} {'weak':>5}  {'pulses':>6}  {'1T/2T us':>12}  {'bps':>7}  "
          f"{'pream':>5}  {'level dBm':>14}  {'first':>8}  signature")
    for r in rows:
        print(f"  {r['sig']:>3}  {r['count']:>6} {r['weak_count']:>5}  {r['npulses']:>6}  "
              f"{r['pulse_lo']:>5.0f}/{r['pulse_hi']:<6.0f} {r['baud']:>7.0f}  {r['preamble']:>5}  "
              f"{r['lo']:>6.1f}..{r['hi']:<6.1f}  {r['first_seen'][11:19]:>8}  {r['signature']}")
    print("\n  next: rfselect.py crypt --sig <n>     (constant/varying bit analysis)")
    return 0


def do_show(db, a):
    rows = select(db, a)
    if not rows:
        print("  no transmissions matched those filters")
        return 0
    print(f"  {len(rows)} transmissions")
    print(f"  {'ts':<23} {'t_dev':>9} {'rssi':>7}  {'pulses':>6}  bits")
    for r in rows:
        print(f"  {r['ts'][:23]:<23} {r['t_dev_ms']:>9} {r['rssi']:>7.1f}  {r['npulses']:>6}  "
              f"{(r['bits'] or '')[:40]}")
    return 0


def similarity(a, b):
    best = 0.0
    for off in range(-3, 4):
        aa, bb = a[max(0, off):], b[max(0, -off):]
        n = min(len(aa), len(bb))
        if n > 0:
            best = max(best, sum(1 for x, y in zip(aa[:n], bb[:n]) if x == y) / n)
    return best


def do_crypt(db, a):
    rows = select(db, a)
    f = bits_of(rows)
    if len(f) < 2:
        print(f"  need at least 2 comparable frames of one signal, got {len(f)}")
        return 1
    nbits = len(f[0][3])
    print(f"  signal analysis over {len(f)} frames of {nbits} bits\n")

    # per-position spread
    const, varying = [], []
    entropy = []
    for i in range(nbits):
        vals = Counter(b[i] for _, _, _, b in f)
        entropy.append(sum(-(c / len(f)) * __import__("math").log2(c / len(f)) for c in vals.values()))
        (const if len(vals) == 1 else varying).append(i)
    mask = "".join("." if i in const else f[0][3][i] for i in range(nbits))
    print(f"  constant across all frames : {len(const):>3} bit(s)")
    print(f"  changes on every press     : {len(varying):>3} bit(s)")
    print(f"\n  frame with constant positions dotted out:\n    {mask}")
    print(f"    press 1: {f[0][3]}")
    print(f"    press 2: {f[1][3]}")

    # presses = groups separated by a device-clock gap. A clock that goes BACKWARDS means a new
    # capture session (the device clock restarts), not a press — treat it as a clean boundary, or
    # frames imported from several logs merge into fake presses.
    groups = [[f[0]]]
    for item in f[1:]:
        prev = groups[-1][-1][0]
        if item[0] >= prev and item[0] - prev < 500:
            groups[-1].append(item)
        else:
            groups.append([item])
    print(f"\n  {len(groups)} press(es) detected from device-clock gaps")
    if len({r["session"] for r in rows}) > 1:
        print(f"    NOTE: this set mixes {len({r['session'] for r in rows})} capture sessions — "
              f"filter with --since/--until or --label for a clean single-session answer")
    within, between = [], []
    for g in groups:
        for i in range(len(g) - 1):
            within.append(similarity(g[i][3], g[i + 1][3]))
    for i in range(len(groups) - 1):
        between.append(similarity(groups[i][0][3], groups[i + 1][0][3]))
    if within:
        print(f"    repeats WITHIN a press : median {statistics.median(within):.3f}  "
              f"(min {min(within):.3f})")
    if between:
        print(f"    separate presses       : median {statistics.median(between):.3f}  "
              f"(min {min(between):.3f})")
        verdict = ("HOPS on every press (repeats inside a press match, presses do not)"
                   if statistics.median(between) < 0.95 and (not within or statistics.median(within) > 0.97)
                   else "no evidence of hopping in this set — the code repeats across presses")
        print(f"    -> {verdict}")

    # counter hunt on the varying region
    if varying:
        nums = []
        for _, ts, _, b in f:
            num = 0
            for i in varying:
                num = (num << 1) | int(b[i])
            nums.append(num)
        diffs = [nums[i + 1] - nums[i] for i in range(len(nums) - 1)]
        mono = all(d > 0 for d in diffs)
        print(f"\n  varying bits read as an integer (MSB-first), in time order:")
        print(f"    {nums[:8]}{' ...' if len(nums) > 8 else ''}")
        print(f"    deltas: {diffs[:8]}{' ...' if len(diffs) > 8 else ''}")
        print(f"    monotonic increase (a plaintext counter)? {'YES' if mono else 'NO'}")
        if not mono:
            print("    -> no visible sequence: consistent with a KEYED/encrypted hop field, which is")
            print("       what an HCS301-class device looks like. Decryption then needs the device key")
            print("       (side-channel, or the manufacturer key from a receiver), not more captures.")
    print(f"  distinct codes seen: {len({b for _, _, _, b in f})} of {len(f)}")
    if 64 <= nbits <= 70:
        print(f"\n  payload is {nbits} bits — that is the HCS301/KEELOQ code-hopping payload size")
        print("  expected layout there:  [1 repeat][1 battery-low][4 button][28 serial][32 encrypted]")
        print(f"  measured here:          constant region at {const[0] if const else '-'}"
              f"..{const[-1] if const else '-'} ({len(const)} bits)")
        if len(const) in range(26, 33):
            print("  -> the constant region is the size of a 28-bit serial: this is an HCS301-class")
            print("     device in spirit, so the published KEELOQ attacks are the ones that apply:")
            print("       * algebraic/slide key recovery needs 2^16 known codes (a capture campaign)")
            print("       * differential power analysis needs ~10 traces of the remote's MCU")
            print("       * the manufacturer key lives in a receiver (needs an opener)")
    print(f"  bit-position entropy (bits, max 1.0 = maximally varying):")
    print("    " + " ".join(f"{e:.2f}" for e in entropy[:nbits]))
    return 0


def do_export(db, a):
    rows = select(db, a)
    if not rows:
        print("  nothing matched")
        return 1
    out = a.out or f"/tmp/rfexport-sig{a.sig or 'any'}.{a.format}"
    kind = a.format
    if kind == "jsonl":
        with open(out, "w") as fh:
            for r in rows:
                fh.write(json.dumps({"ts": r["ts"], "t_dev_ms": r["t_dev_ms"], "sig": r["sig"],
                                     "signature": r["signature"], "rssi": r["rssi"],
                                     "npulses": r["npulses"],
                                     "pulses": [int(x) for x in (r["pulses"] or "").split(",") if x],
                                     "bits": r["bits"]}) + "\n")
    elif kind == "bits":
        with open(out, "w") as fh:
            fh.write(f"# bits from {a.sig and 'sig '+str(a.sig) or 'all signals'} — {len(rows)} frames\n")
            fh.write("# one code per line, MSB-first as transmitted; polarity assumes short-first = 1\n")
            for r in rows:
                fh.write((r["bits"] or "") + "\n")
    elif kind == "csv":
        with open(out, "w") as fh:
            fh.write("frame,index,width_us\n")
            for n, r in enumerate(rows):
                for i, w in enumerate((r["pulses"] or "").split(",")):
                    if w:
                        fh.write(f"{n},{i},{w}\n")
    elif kind in ("ook", "raw"):
        # rebuild an OOK waveform at 1 MSps: 1 us per sample, carrier = high
        samples = []
        for r in rows:
            pulses = [int(x) for x in (r["pulses"] or "").split(",") if x]
            level = 1
            for w in pulses:
                samples.extend([level] * max(1, w))
                level ^= 1
            samples.extend([0] * 5000)   # 5 ms of silence between frames
        if kind == "ook":
            with open(out, "w") as fh:
                fh.write(f"# OOK waveform rebuilt at 1 MSps (1 sample = 1 us), {len(samples)} samples\n")
                fh.write("# 1 = carrier on. Import as 8-bit unsigned real, 1 MSps.\n")
                step = max(1, len(samples) // 200000)
                fh.write("".join(str(samples[i]) for i in range(0, len(samples), step)))
        else:
            with open(out, "wb") as fh:
                fh.write(bytes(255 if s else 0 for s in samples))
            with open(out + ".txt", "w") as fh:
                fh.write("raw 8-bit unsigned OOK, 1 MSps (1 sample = 1 us), 255 = carrier on.\n"
                         "inspectrum: open as 8-bit unsigned, sample rate 1e6.\n"
                         "URH: import as raw, '8 bit unsigned', sample rate 1e6, no DC offset.\n")
    else:
        sys.exit(f"unknown format {kind}")
    print(f"  exported {len(rows)} transmission(s) as {kind} -> {out}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="filter/export/cryptanalyse a soak capture")
    ap.add_argument("--db", default=DB_DEFAULT)
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name, fn in (("sessions", do_sessions), ("list", do_list),
                     ("show", do_show), ("crypt", do_crypt), ("export", do_export)):
        sp = sub.add_parser(name)
        sp.add_argument("--sig", type=int)
        sp.add_argument("--since")
        sp.add_argument("--until")
        sp.add_argument("--min-level", type=float, dest="min_level")
        sp.add_argument("--max-level", type=float, dest="max_level")
        sp.add_argument("--label")
        sp.add_argument("--limit", type=int)
        if name == "export":
            sp.add_argument("--format", choices=["jsonl", "bits", "csv", "ook", "raw"], default="jsonl")
            sp.add_argument("--out")
        sp.set_defaults(func=fn)

    a = ap.parse_args()
    db = connect(a.db)
    return a.func(db, a)


if __name__ == "__main__":
    sys.exit(main())
