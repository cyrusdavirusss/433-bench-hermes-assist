#!/usr/bin/env python3
"""Transmit a synthetic PT2262-style OOK frame from the YARD Stick One.

Gives the bench a known-good, remote-shaped test signal that needs no physical remote:
real 1T/3T pulse widths, a tri-state 12-bit code, a carrier-burst sync gap, repeated
like a held button.

How the pulse widths are made: with OOK, the dongle keys the carrier per BIT at the
configured baud, so one bit = 1T. Setting baud = 1/T gives us exact 1T/3T/31T pulses.

    sudo /tmp/ys1venv/bin/python ys1_send_code.py --seconds 20 --T-us 350

Default code FF0F0F0F0FFF (tri-state: 0, 1 and F are all valid symbols), T = 350 us
which is the common PT2262 timing. The rig should capture 1T/3T widths near 350/1050 us.
"""
import argparse
import sys
import time

from rflib import RfCat, MOD_ASK_OOK


def encode_pt2262(code, T_us):
    """Return (bytes, baud) for a PT2262-style frame: '0'/'1'/'F' tri-state symbols."""
    bits = []
    for sym in code.upper():
        if sym == "0":                      # 1T on, 3T off
            bits += [1, 0, 0, 0]
        elif sym == "1":                    # 3T on, 1T off
            bits += [1, 1, 1, 0]
        elif sym == "F":                    # 1T on, 1T off
            bits += [1, 0]
        else:
            raise ValueError(f"bad symbol {sym!r} (use 0/1/F)")
    bits += [1] + [0] * 31                  # sync: 1T on, 31T off
    while len(bits) % 8:
        bits.append(0)

    data = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for b in bits[i:i + 8]:
            byte = (byte << 1) | b
        data.append(byte)
    baud = int(round(1e6 / T_us))
    return bytes(data), baud


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--code", default="FF0F0F0F0FFF")
    ap.add_argument("--T-us", type=int, default=350)
    ap.add_argument("--freq", type=int, default=433920000)
    ap.add_argument("--repeat", type=int, default=4)
    args = ap.parse_args()

    payload, baud = encode_pt2262(args.code, args.T_us)
    print(f"code {args.code} (tri-state), T={args.T_us} us -> baud {baud}, "
          f"{len(payload)} bytes")
    print(f"payload hex: {payload.hex()}")
    print("expect 1T/3T pulses at "
          f"{args.T_us} us and {3*args.T_us} us, sync gap {31*args.T_us} us")

    d = RfCat(debug=False)
    d.setFreq(args.freq)
    d.setMdmModulation(MOD_ASK_OOK)
    d.setMdmDRate(baud)
    try:
        d.setMdmSyncMode(0)
        d.setMdmNumPreamble(0)
    except Exception as exc:
        print("  config note:", exc)
    d.setMaxPower()
    try:
        d.setPower(0xC0)
    except Exception as exc:
        print("  setPower note:", exc)
    print("settling 7 s before the first transmit...")
    time.sleep(7)

    deadline = time.time() + args.seconds
    n = 0
    while time.time() < deadline:
        d.RFxmit(payload, repeat=args.repeat)
        n += 1
        time.sleep(0.35)                    # gap between repeats, like a held button
        if n % 5 == 0:
            print(f"  sent {n} frames", flush=True)
    print(f"done: {n} transmit calls")
    try:
        d.setModeIDLE()
        d.cleanup()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
