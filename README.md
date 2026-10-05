# 433-bench-hermes-assist (public)

The **433 / RF bench** store: one copy of the bench skill, its tools and its findings, so every
Hermes instance — every profile on this machine, and the other machines — works from the same
state instead of re-deriving it.

**This repo is public. Nothing personal goes in it.** Where someone lives, phone numbers,
subscriber or account data, internal IPs, hostnames, SSH details, credentials, plates, VINs or
target lists belong in `~/hermes-private`, which is the private half of this store. `publish.sh`
enforces the direction: only `rf-security-research` routes here; anything else routes private.

## What's in it

    skills/rf-security-research/     the bench skill
      references/cc1101-bench-firmware.md   pinout, register image, command reference, BW=58 finding,
                                            the loose-MISO signature, the dead-remote evidence
      references/hackrf-diagnostics.md      HackRF failure modes and the DFU decision table
      scripts/                              eight bench tools, see the handoff
    diagnostics/                     RF write-ups: HackRF diagnosis, the JJX601 reports
    handoffs/                        state for the next instance, newest first
    publish.sh                       route a skill to the right store, fan it out to every profile

## Start here on a new machine

```bash
git clone https://github.com/cyrusdavirusss/433-bench-hermes-assist.git ~/433-bench-hermes-assist
```

then in that instance's `~/.hermes/config.yaml`:

```yaml
skills:
  external_dirs:
    - /home/<user>/433-bench-hermes-assist/skills   # public half (this repo)
    - /home/<user>/hermes-private/skills    # private half — needs account access
```

Read the newest file in `handoffs/` first: it is written for an instance with zero context, and it
carries what is verified, what is unverified, and the gotchas that already cost time.

## Update an existing machine — the one command

**For an instance that already has this clone, updating is nothing but a `git pull`.** The skills
are loaded from THIS directory through `skills.external_dirs`, so there is no copy step and nothing
to install:

```bash
~/433-bench-hermes-assist/update.sh
```

It pulls, says what arrived, checks the store is actually wired into `skills.external_dirs` (and
prints the exact line if it is not), and lists the skill files you now hold. `./update.sh --check`
reports whether you are behind without changing anything.

Told to "update yourself from GitHub" and unsure what that means? It means that one command, run
from inside the clone. No clone yet? Do the "Start here" step above, then run it.

**If `update.sh` says the store is not in `skills.external_dirs`, the pull changed nothing you can
see.** That is the failure that reads as "the update did not work" — the files are on disk and no
instance is loading them. Fix it with the `hermes config set` line the script prints.

## History

Rebuilt from scratch on 2026-09-28 with a single commit, when this repo was made public. The
earlier history — which contained the private half, including a tarball of the whole store — is
preserved only in `hermes-private`.
