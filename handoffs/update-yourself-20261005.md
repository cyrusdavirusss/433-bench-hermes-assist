# Handoff → the instance on the other machine: how to update yourself (5 Oct 2026)

**From:** the `kali` instance (profile `default`)
**For:** any Hermes instance on any machine that works the 433 bench

You were told to "update yourself through GitHub" and it did not land. That is not your fault — the
instructions were spread across three places. This file is the whole thing, in order.

## 1. Update — one command

If `~/433-bench-hermes-assist` already exists on your machine, updating is **only** a pull. The
skills load from that directory via `skills.external_dirs`; there is no copy step and nothing to
install.

```bash
~/433-bench-hermes-assist/update.sh
```

Run from anywhere. It pulls, tells you what arrived, verifies the store is actually wired into
`skills.external_dirs` (printing the exact `hermes config set` line if it is not), and lists the
skill files you now hold.

If the clone does not exist yet:

```bash
git clone https://github.com/cyrusdavirusss/433-bench-hermes-assist.git ~/433-bench-hermes-assist
hermes config set skills.external_dirs '["/home/<user>/433-bench-hermes-assist/skills", "/home/<user>/hermes-private/skills"]'
~/433-bench-hermes-assist/update.sh
```

This repository is **public**, so it clones with no credentials. The `hermes-private` half needs
account access — skip it if you do not have it; everything bench-related is in the public half.

**Verify by capability, not by reading config back.** Do this and see the skill named in the list:

```bash
hermes skills list | grep rf-security-research
```

If that returns nothing, the store is not in `skills.external_dirs` and the pull changed nothing you
can see. That is the failure that looks like "the update did not work".

## 2. Read, in this order

1. `skills/rf-security-research/SKILL.md` — the bench skill.
2. `skills/rf-security-research/references/cc1101-bench-firmware.md` — the authoritative record of
   the ESP32 + CC1101 rig: pinout, register image, command reference, **BW=58**, the loose-MISO
   signature, the TEST0 result, and the evidence that ruled things out.
3. `skills/rf-security-research/references/hackrf-diagnostics.md` — HackRF failure modes.
4. Newly published since the last handoff:
   - `references/dpa-bench-plan.md` — the physical side of the PTX-4 KeeLoq key recovery. The attack
     software is proven offline; the rest needs hands.
   - `references/ptx4-hop-cryptanalysis.md` — the 66-bit OOK frame, field layout, and the result that
     the public manufacturer-key corpus is exhausted.
5. `scripts/` — the bench tools, including `rig_tx_verify.py`, `ys1_tx_carrier.py`, `ys1_send_code.py`,
   `rfsoak.py`, `spi_stress.py`, `bench_selftest.sh`.

## 3. State of the bench as of 2026-10-05

- **Rig:** ESP32 + CC1101 (E07-M1101D) on `/dev/ttyUSB0`. RX and SPI are verified. **The CC1101
  needs `BW=58`; the firmware defaults to 100.** A loose MISO reads a plausible-looking
  **−74.0 dBm**, so a "dead" receiver that still reports a level is probably a wiring fault, not a
  dead part — run `bench_selftest.sh` before believing any "no signal" result.
- **Sender:** YARD Stick One (RfCat), venv at `/tmp/ys1venv`. TX verified (`setPower(0xC0)`).
- **Dongle RX:** needs a real antenna, and needs a replug after a `USBTimeoutError`.
- **Open:** rig TX — `scripts/rig_tx_verify.py` is the tool; the result is not recorded yet. If you
  run it, record the outcome in the private ledger and say so here.
- **The old 315 MHz car key** is 315 MHz; the rig covers 387–464 MHz and will not see it. The gate
  remote is dead.

## 4. Rules that already cost time

- **This public repo takes bench facts only.** No addresses, hostnames, serials tied to a person,
  credentials, or anything about the operator's own life. Internal network addresses live in the
  private ledger — a reference file carried one publicly until 2026-10-05 and it was removed.
- **The operator's own record is authoritative.** If they say work was done elsewhere, record it in
  the turn they report it. Never ask them to re-prove their own history — trees are per-machine, so
  a build done elsewhere leaves no trace here by construction.
- **Handoffs are FILES, not messages.** If you learn something, write it into this store and commit,
  so the next instance pulls it instead of being told.
