# PTX-4 hop: framing proven, public-key corpus exhausted (2026-09-29)

Research on the operator's OWN Bunnings PTX-4 remote. Companion to `ata-ptx4-remote.md`.

## What the frame actually is

66-bit OOK frame, ~1184 us bit period, 1T ~375 us / 2T ~775 us (measured on the rig at
us resolution; rtl_433 confirms 376/780 us on a 4 us grid).

Field layout, established by a data-driven boundary search rather than a documented offset
(the split that makes the serial constant is the correct one):

| field | bits | value / behaviour |
|---|---|---|
| encrypted hop | ~30 | completely different on every press |
| serial | ~26 | **0x0a438af**, constant across 13 presses |
| button/status | 4+2 | varies with the button pressed |

DISC (if this is HCS-style Keeloq) would be `serial & 0x3FF` = `0x0af`.

## Framing validation — the important result

`src/urh/util/KeeLoq.py` in PentHertz/urh-ng documents the packet as LSB-first
`[encrypted 32][serial 28][button 4][battery][repeat]`. Applying that literally (reversing
the bit string) put the CONSTANT data in the "encrypted" field — i.e. inverted.

Correct handling: rtl_433 prints ON-AIR order, so its output is used **as printed**, no
reversal. Evidence: with that framing the 28/26-bit serial window collapses to a single
value, and the low bit toggles only between 0xa438af9 and 0xa438af8 (the first-transmission
vs repeat flag).

Independent cross-check on the bit stream itself: my own rig decode and rtl_433's decode
agree **66/66 bits at a 3-bit shift**, no inversion, no reversal — my polarity convention was
right, and the frame simply starts 3 bits earlier than my sync-skipping assumed.

## Key attempt — negative, and why it is conclusive

13 presses (3 sessions), 13 public manufacturer keys x 4 learning modes
(simple, normal, magic_xor, secure seed=0), DISC rule + multi-frame counter validation.

Result: no key. Only two chance hits (all-ones/magic_xor and Beninca/magic_xor), each on
1 of 13 frames — statistically expected, since a 10-bit DISC check passes ~1/1024 at random
and 676 trials were run. Both are in the linear magic_xor derivation. A genuine key passes
DISC on every frame and produces an incrementing counter.

Conclusion: with the framing proven by a constant serial, the hop is **not** decryptable with
the public manufacturer-key corpus. The frame is HCS301/Keeloq-SHAPED (66 bits, hop + serial
+ button) but the cipher itself is unconfirmed — a different rolling-code cipher with the same
frame shape would look identical from the air.

## Remaining routes, in order of cost

1. **Larger public key corpus** — Flipper-ARF `keeloq_common.c`, ProtoPirate, Flipper keystore
   (the last is encrypted in the repo). Cheap to try: same script, bigger key list.
2. **DPA / side-channel** — the documented practical attack on HCS-class devices
   (~10 power traces). This is the Micsig's real job on this project: capture the transmitter
   chip's power trace and recover the key by differential power analysis.
3. **Device dump** — read the remote's EEPROM/chip (hcs-programmer-soft style tooling),
   which yields the key directly.

## Tools installed on this box

- `~/.local/venvs/rf` — `urh` (Universal Radio Hacker), `rfcat` (imports as `rflib`), `rfox`
  (rfcat-based CLI: `devices/scan/sweep/replay/decode/diff/crc/find-sync/preset`, sees the
  YARD Stick One as DonsDongle 0x1d50:0x605b)
- `~/.local/venvs/scope` — scope MCP + analysis
- `rtl_433` (apt) — reads synthesised IQ files, no hardware needed
- `/home/cyrus/Documents/rf/keeloq.py` — KeeLoq cipher, verified against published vectors
  (0x5cec6701b79fd949/0xf741e2db -> 0xe44f4cdf etc.), import-time self-test
- `/home/cyrus/Documents/rf/keeloq_attack.py`, `keeloq_conclusive.py` — the key attempts
- `~/Documents/rf/serial-mcp-server` — Rust serial MCP server (needs `libudev-dev` to build;
  `serve` = MCP mode, also has a one-shot CLI: `write --port .. --data .. --read`)

## DPA rehearsal on the published HCS301 traces (2026-09-29)

Sets downloaded from `marc-invalid/chipwhisperer-marc` (`doc/marc/keeloq/examples_hcs301/`) into
`~/Documents/rf/keeloq-dpa/`. They ship 501 power traces PLUS the matching ciphertexts, but NO key
(`knownkey.npy` is empty). So the validation is the same oracle used on the PTX-4: a correct key
decrypts every message into a constant discrimination field with advancing counters.

- `HCS301_bits_peak`: 501 x 365 samples, 3 samples per round (trimmed to the leak region)
- `HCS301_sync`: 501 x 24200 samples, 200 samples per round, clock-drift compensated
- `textout.npy` rows carry the 32-bit ciphertext big-endian in the first 4 bytes

### Calibration recipe that works (verified)

Correlate the KNOWN ciphertext bits against the traces and the ladder appears immediately.
On the sync set: ciphertext bit 0 -> sample 13856, bit 1 -> 14056, ... bit 31 -> 20056, i.e.
**200 samples per round**, |r| 0.24-0.54. (Matches the documented "Round 528 pos=20000, width=200".)
On the bits_peak set it is 3 samples per round instead, bit 1 -> 212 ... bit 31 -> 302.
Bit 0 shows a strong peak ~105 samples late on the trimmed set: that is the documented
post-cipher hardware artifact (ciphertext being shifted out to the next stage), not its round.

Then calibrate the UNDO-STEP lane map using only key-independent predictions: after n undo
rounds the state's MSB is ciphertext bit (31-n), which needs no key. Measured on the sync set:

    step 1 -> sample 19856   (predicting ciphertext bit 30)
    step 2 -> sample 19656
    ...
    step 31 -> sample 13856   (predicting ciphertext bit 0)
    gaps exactly -200, thirty times

So **lane(step n) = 19856 - 200*(n-1)**. Note this is 200 lower than the ciphertext-bit-31 lane:
using 20056 (one round too high) gives strong-looking correlations against the WRONG round.

### SOLVED — the working recipe (verified 2026-09-29)

`keeloq_dpa_port.py` ports chipwhisperer-marc's encoder bit-model attack faithfully and recovers
the full 64-bit key from the HCS301_sync set in one pass, validating perfectly:

    key 300b2b45ba1e7114 | keystream 0111000100010100001100000000101100101011010001011011101000011110
    disc=0x394 constant on 100.0% of 501 messages | counters advance 100.0%, stepping +2
    per-bit Welch t-statistics 5.75-10.15

Four things had to be right, and each one alone breaks the attack:

1. **DUMMY BIT.** The probe keystream is `recovered + guess + "0"`. KeeLoq XORs the last key bit
   into the attacked bit, so without the dummy the two guesses partition the traces
   COMPLEMENTARILY and neither can win — you get equal |r| for both and pick noise. This is the
   single reason my Pearson-correlation attempts could not choose.
2. **ATTACK ROUNDS 495 DOWN TO 432**, not the last rounds: lanes descend as the attack deepens
   (round r at `round528 - (528-r)*width`), i.e. windows 13400..800 on the sync set. That region
   is BELOW the ciphertext-bit ladder (13856..20056), which is why nothing key-dependent showed up
   before.
3. **WELCH T-TEST between partitions**, not a Pearson correlation against a single-trace-derived
   prediction. The partition value is the LSB of the state after decrypting by the probe keystream
   (`(data >> 0) & 1`, little-endian convention).
4. **KEY ASSEMBLY ROTATES 16 BITS**: `key = keystream[16:64] + keystream[0:16]`.

Cipher convention that matches the chip (from the reference model, differs from the published
test-vector formulation in NLF argument order):
`lsb = keybit ^ bit31 ^ bit15 ^ NLF(a=30,b=25,c=19,d=8,e=0)`, `state = ((state & 0x7FFFFFFF) << 1) ^ lsb`,
key bit for undo round r = `(591 - r) % 64`.

The previously reported "down/HD" candidate key (300b2b45ba1e7114) was in fact the correct key —
the recovered BITS were right all along; only the assembly and the partition statistic were wrong.

### Brute force — CLOSED (2026-09-29 19:50)

All four derivations swept over 0..2^32 with the 13-frame oracle (130 bits of filtering, so a hit
would be conclusive, and 0 hits means genuinely none):

    simple   1041 s   0 hits        magic    1044 s   0 hits
    normal   3131 s   0 hits        secure0  3123 s   0 hits
    patterns 1,114,181 keys x 4 modes   0 hits (12 s)
    wordlist   552 memorable keys x 4 modes   0 hits
    ascii    exhaustive 6-char A-Z0-9 and a-z0-9, both alignments, simple+normal

**Why this closes the chapter rather than disappointing.** The operator read the chip: it is a
Microchip HCS301, which holds a PROGRAMMED 64-bit device key. If ATA programmed a unique random key
per remote — the normal thing to do — the search space is 2^64 = 1.8e19. At the best measured rate
of 4.13 M candidates/s that is roughly 140,000 years. No amount of sweeping reaches it. So for
this target the brute force cannot succeed by construction, and DPA is the only way in.

That is why the chip identification mattered more than any sweep: it converted "keep trying keys"
into "stop, and go read the key off the silicon". The sweep cost ~1.7e10 candidate evaluations and
answered exactly the question it could answer.

### Where the key recovery stands — SOLVED (was: not yet solved)

Kept for the record of what was ruled out:

- `down` + bit model, correct lanes: peaks land exactly on the lane (in-round offset +0) at
  |r| 0.24-0.40, which matches the calibration precisely. But for steps 1-31 the bit model's MSB
  prediction is KEY-INDEPENDENT, so those steps carry no key information at all, and the greedy
  selector just keeps guess 0 (hence the all-zero keys above). Deeper steps (32+) do become
  key-dependent but need the earlier bits already fixed.
- `down` + HD model: strong correlations (mean|r| 0.54, max 0.62, constant +49 in-round offset),
  so it is measuring something real, but the two guesses differ by only a 1-bit Hamming distance
  among ~16 changing bits, so greedy peak-following is too fine-grained and mis-guesses. The
  assembled key never validates.

Conclusion: cipher-adjacent leakage is nailed down (positions, content, strength); assembling a
correct 64-bit key needs the paper's approach — contribute ALL known rounds' evidence per key bit
rather than greedy per-step picking — or the proven `chipwhisperer-marc` Keeloq attack module.
That fork is CW3-era but its attack code and tutorials are the reference to port.

### Capture requirements for the real thing (from Eisenbarth et al., Crypto 2008)

- **GND shunt** (small resistor in the ground path) + a scope; EM near-field probe works too
- 200 MS/s suffices for 10 traces (DIP) / 30 traces (SOIC). The Micsig does 1 GS/s = 5x that,
  and at 1 GS/s the 28 Mpts memory gives a 28 ms window, enough to cover the whole operation
  since the cipher runs ~20.5-24 ms after the button press (the chip's EEPROM write happens first)
- Trigger: the paper triggered off the RF transmission; a button-press GPIO works as well
- Clones (e.g. EG301) may insert dummy instructions and defeat the attack; genuine HCS301/200/300
  parts are the documented targets

## Pipeline that works without any hardware

Pulse timings -> synthesised OOK IQ (cu8, 250 kSa/s) -> `rtl_433 -r file -s 250k -X 'n=x,m=OOK_PWM,s=380,l=760,r=2000,t=0,y=6000'`
gives per-press `codes : {66}<hex>`. This put a 200+ decoder corpus and the crypto toolkit to work
on captures alone.

## Brute force (in progress as of 2026-09-29 evening)

`keeloq_brute.c` (OpenMP, ~0.53 M candidates/s/thread; verified against the published vectors
via `--selftest`). Modes: `simple`, `normal`, `secure0`, `magic`, plus `keys <file>` (wordlist,
tests all four) and `ascii <len> <upper|lower> <mode>` (exhaustive short ASCII keys, both
alignments).

Oracle design that makes a hit conclusive: DISC must equal `serial & 0x3FF` on EVERY frame.
13 frames x 10 bits = ~130 bits of filtering, so over a 2^32 sweep the expected false-positive
count is ~0. The low serial bit is treated as unreliable (frames carry ...af9/...af8): the
derivation uses the serial with bit0 cleared and DISC is accepted for either variant, costing
1 bit of filtering and removing a class of false negatives.

Launched, running, logging to `keeloq-sweep.log`:
- `simple`, `magic`, `normal`, `secure0` over 0 .. 2^32, 8 threads, ~17 min per mode

Queued behind it (`keeloq-wave2.log`): structured patterns (16-bit blocks repeated, serial-derived
keys, AU car manufacturer-code prefixes) then exhaustive 6-char ASCII keys (A-Z0-9 and a-z0-9,
both alignments) under the simple and normal derivations.

Already negative: 552 memorable/pattern keys x 4 modes; the full public corpus.

### Key corpus reality check

There is NO large public keeloq manufacturer-key list. What exists:
- urh-ng `src/urh/util/KeeLoq.py`: 13 public keys (13 of the "26 built-in" are not in the repo)
- Flipper's built-in `keeloq_mfcodes` is AES-encrypted with the key in the DEVICE's secure
  enclave -> cannot be decrypted off-device (Lechnio/SubGHz-Keystore-Decryptor confirms this)
- `flipper-zero-au-subghz`: `keeloq_mfcodes_user` is a BRAND LOOKUP table, not keys
  (format `SER_MSB:LEARNING_METHOD:BRAND`, e.g. `7F00000:2:Toyota_Hilux_B41TA`) — but it usefully
  confirms that manufacturer entries are 28-bit serial prefixes, matching our 0x0a438af field
- That repo also ships 15 `ata_princeton_*_ook650.sub` fixed-code gate captures (24-bit, TE 400)
  = usable as ATA calibration data

So the brute force IS the remaining public route. If it comes back empty, the key is not a small
integer, not a memorable text string, and not one of the public keys -> then: DPA on the
transmitter chip (~10 power traces, the Micsig's actual job here) or an EEPROM dump.

### Operational lessons (cost real time today)

- Never `pkill -f '<name>'` when the binary name also appears in your own command line — it
  matches your own shell and SIGTERMs it. Use `pkill -x <exact-name>`.
- Launcher loops respawn the next mode after a kill, so repeated pkills silently advance a sweep
  while destroying its results.
- Do not filter command output with grep while diagnosing: a missing tool (`/usr/bin/time` isn't
  installed here) produced empty output that looked like a crash.
- Long sweeps need progress printing AND `fflush`, otherwise a run is unverifiable and a buffered
  summary line can be lost.
- Two calls compiling the same source in parallel race on the output binary; compile once.
