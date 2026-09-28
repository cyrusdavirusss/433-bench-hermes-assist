#!/usr/bin/env python3
"""Hold a 433.92 MHz OOK carrier on air from the YARD Stick One for N seconds.

Built for A/B testing a CC1101 register bit: the transmitter must stay up and unmoved
for the whole run, so the only thing changing between phases is the receiver config.

Traps this handles (all found on this bench, 24 Sep 2026):
  * setMdmModulation(MOD_ASK_OOK) does NOT set PA power - it only flips an existing PA
    table, so on a zeroed table RFxmit reports success and radiates nothing.
    setMaxPower() is called after the modulation is set, and PATABLE is read back.
  * transmit only from the MAIN thread of a dedicated process (this is one).
  * ~7 s settle after the handle opens before the first transmit.
  * NEVER USB-reset / ep0Reset the dongle. cleanup() only.

Run:  sudo /tmp/ys1venv/bin/python /tmp/ys1_tx_carrier.py --seconds 240
      add --dry-run to configure and report without radiating.
"""
import argparse
import sys
import time

from rflib import RfCat, MOD_ASK_OOK

PATABLE = 0xDF3E


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=240)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--freq", type=int, default=433920000)
    ap.add_argument("--baud", type=int, default=2400)
    ap.add_argument("--bytes", type=int, default=255)
    args = ap.parse_args()

    payload = b"\xff" * args.bytes

    print("opening dongle...")
    d = RfCat(debug=False)

    d.setFreq(args.freq)
    d.setMdmModulation(MOD_ASK_OOK)
    d.setMdmDRate(args.baud)
    try:
        d.setMdmSyncMode(0)          # no sync word: raw on/off keying
        d.setMdmNumPreamble(0)
    except Exception as exc:
        print("  preamble/sync not set:", exc)
    d.setMaxPower()                  # the call that actually puts RF out
    try:
        d.setPower(0xC0)             # explicit max PA entry; setMdmModulation may leave
                                     # PATABLE[0] at 0 and FREND0 pointing elsewhere
    except Exception as exc:
        print("  setPower(0xC0) failed:", exc)
    time.sleep(0.5)

    try:
        print(f"  freq  = {d.getFreq()} Hz")
        print(f"  mod   = {d.getMdmModulation()}")
        print(f"  drate = {d.getMdmDRate()} baud")
    except Exception as exc:
        print("  query failed:", exc)

    try:
        pa = d.peek(PATABLE, 8)
        print(f"  PATABLE = {[hex(b) for b in pa]}"
              f"   {'OK non-zero' if any(pa) else 'ZERO -> would radiate nothing'}")
    except Exception as exc:
        print("  PATABLE read failed:", exc)

    if args.dry_run:
        print("dry run: configured, nothing transmitted")
        try:
            d.setModeIDLE()
            d.cleanup()
        except Exception:
            pass
        return 0

    print("settling 7 s before first transmit...")
    time.sleep(7)

    deadline = time.time() + args.seconds
    bursts = 0
    print(f"transmitting 433.92 MHz OOK carrier for ~{args.seconds} s "
          f"({len(payload)} x 0xFF at {args.baud} baud, repeating)", flush=True)
    try:
        while time.time() < deadline:
            d.RFxmit(payload, repeat=20)
            bursts += 1
            if bursts % 5 == 0:
                left = int(deadline - time.time())
                print(f"  bursts={bursts}  ~{left}s left", flush=True)
    except KeyboardInterrupt:
        print("interrupted")
    except Exception as exc:
        print("transmit error:", exc)
    finally:
        print(f"done: {bursts} transmit calls")
        try:
            d.setModeIDLE()
            d.cleanup()
        except Exception as exc:
            print("cleanup note:", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
