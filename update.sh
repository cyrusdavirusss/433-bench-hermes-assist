#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────────────────────
# UPDATE YOURSELF. One command, no other context needed.
#
# This repo IS the shared bench knowledge. If this directory is in your instance's
# skills.external_dirs, then updating is nothing more than a git pull — the skills load from
# HERE, so there is no copy step and nothing to install.
#
#   ./update.sh            pull, verify, and say what you now know that you didn't before
#   ./update.sh --check    report whether you are behind, change nothing
#
# Run it from inside the clone. Exit 0 = up to date and visible.
# ─────────────────────────────────────────────────────────────────────────────────────────────
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

echo "== shared store: $HERE"
[ -d "$HERE/.git" ] || { echo "  !! not a git clone. Clone it first:"; \
  echo "     git clone https://github.com/cyrusdavirusss/433-bench-hermes-assist.git ~/433-bench-hermes-assist"; exit 1; }

BEFORE="$(git -C "$HERE" rev-parse HEAD)"
BEHIND="$(git -C "$HERE" rev-list --count HEAD..@{u} 2>/dev/null || echo '?')"
echo "  local  : $(git -C "$HERE" rev-parse --short HEAD)"
echo "  behind : ${BEHIND} commit(s)"

if [ "$CHECK_ONLY" = "1" ]; then
  [ "${BEHIND:-0}" = "0" ] && echo "  => up to date" || echo "  => run: git -C $HERE pull"
  exit 0
fi

echo
echo "== pulling"
git -C "$HERE" pull --ff-only 2>&1 | sed 's/^/  /'
AFTER="$(git -C "$HERE" rev-parse HEAD)"

if [ "$BEFORE" != "$AFTER" ]; then
  echo
  echo "== what arrived"
  git -C "$HERE" --no-pager log --oneline --name-status "$BEFORE..$AFTER" | sed 's/^/  /' | head -40
else
  echo
  echo "  (no new commits — already current)"
fi

echo
echo "== is the store actually LOADED by this instance?"
EXTERNAL="$(hermes config get skills.external_dirs 2>/dev/null || echo '')"
if printf '%s' "$EXTERNAL" | grep -q "$HERE"; then
  echo "  yes — $HERE is in skills.external_dirs"
else
  echo "  NO — it is not wired up. Without this the skills below are invisible to you."
  echo "  Set it (one line, takes effect for new sessions):"
  echo
  echo "    hermes config set skills.external_dirs '[\"$HERE/skills\", \"\$HOME/hermes-private/skills\"]'"
  echo
  echo "  The private half is optional — it needs account access. The public half never does."
fi

echo
echo "== the bench skill is now:"
SKILLDIR="$HERE/skills/rf-security-research"
if [ -d "$SKILLDIR" ]; then
  echo "  $SKILLDIR"
  echo "  references:"
  ls -1t "$SKILLDIR/references" 2>/dev/null | sed 's/^/    /'
  echo "  scripts:"
  ls -1 "$SKILLDIR/scripts" 2>/dev/null | sed 's/^/    /'
  echo
  echo "  READ FIRST: the newest file in $HERE/handoffs/ — it is written for an instance"
  echo "  with zero context, and carries what is verified, what is not, and the gotchas."
else
  echo "  !! skills/rf-security-research missing from the clone"
fi

echo
echo "== check a specific skill loaded (do this, don't assume):"
echo "     hermes skills list | grep rf-security-research"
exit 0
