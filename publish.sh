#!/usr/bin/env bash
# Fan a skill out to every Hermes profile on this machine, mirror it into the CORRECT store, and
# commit. Two stores, because the bench can be public and personal facts cannot:
#
#   ~/hermes-shared    PUBLIC   - the 433/RF bench only. NOTHING personal goes here, ever.
#   ~/hermes-private   PRIVATE  - everything else: the verified-facts ledger, vp-overwatch
#                                 research (incl. the copper site list), infra details.
#
#   publish.sh <skill-name>    one skill, routed by name
#   publish.sh --route <name>  print where a skill would go, change nothing
#   publish.sh --list          which skills differ between profiles
#   publish.sh --all           mirror the whole default tree into the routed stores
#
# ROUTING FAILS CLOSED: only the names in PUBLIC_SKILLS go public. Anything else — including a
# typo, a new skill, a renamed one — goes to the PRIVATE store. Publishing a bench fact a day
# late costs nothing; publishing a personal fact costs an incident.
#
# Exit codes: 0 ok · 1 usage/not found · 2 nothing to do
set -uo pipefail

PUBLIC="${HERMES_SHARED:-/home/cyrus/hermes-shared}"
PRIVATE="${HERMES_PRIVATE:-/home/cyrus/hermes-private}"
DEFAULT_TREE="$HOME/.hermes/skills"
PROFILE_ROOT="$HOME/.hermes/profiles"

PUBLIC_SKILLS=(rf-security-research)

route_for() {
  local s="$1" p
  for p in "${PUBLIC_SKILLS[@]}"; do [ "$s" = "$p" ] && { printf '%s' "$PUBLIC"; return; }; done
  printf '%s' "$PRIVATE"
}

find_skill() {  # $1 = skill name -> absolute path
  find "$DEFAULT_TREE" -maxdepth 3 -type d -name "$1" -print -quit 2>/dev/null
}

mirror_to_profiles() {  # $1 = absolute source dir, $2 = relative path
  local src="$1" rel="$2" n=0 p dest
  for p in "$PROFILE_ROOT"/*/skills; do
    [ -d "$p" ] || continue
    dest="$p/$rel"
    mkdir -p "$(dirname "$dest")"
    if [ -d "$dest" ] && diff -rq "$src" "$dest" >/dev/null 2>&1; then
      echo "  = $(basename "$(dirname "$p")"): already identical"
    else
      rm -rf "$dest"; cp -r "$src" "$dest"
      echo "  > $(basename "$(dirname "$p")"): updated"; n=$((n+1))
    fi
  done
  echo "  profiles updated: $n"
}

commit_store() {  # $1 = store path
  local store="$1"
  [ -d "$store/.git" ] || { echo "  !! $store is not a git repo"; return 1; }
  ( cd "$store" && git add -A
    if git diff --cached --quiet; then echo "  nothing to commit in $(basename "$store")"; return 2; fi
    git commit -q -m "publish skill(s) + verifications"
    echo "  committed $(basename "$store"): $(git log -1 --format='%h %s' | cut -c1-60)"
    echo "  push: git -C $store push" )
}

publish_one() {  # $1 = skill name
  local name="$1" src rel store
  src="$(find_skill "$name")"
  [ -n "$src" ] || { echo "no skill named '$name' in $DEFAULT_TREE" >&2; return 1; }
  rel="${src#"$DEFAULT_TREE"/}"
  store="$(route_for "$name")"
  echo "Publishing '$name' ($rel)"
  echo "  -> $store  $([ "$store" = "$PUBLIC" ] && echo '(PUBLIC)' || echo '(private)')"
  mkdir -p "$store/skills/$(dirname "$rel")"
  rm -rf "$store/skills/$rel"; cp -r "$src" "$store/skills/$rel"
  echo "  -> fanning out to every profile"
  mirror_to_profiles "$src" "$rel"
  commit_store "$store"
}

case "${1:-}" in
  ""|--help)
    grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
  --route)
    [ -n "${2:-}" ] || { echo "usage: publish.sh --route <skill>" >&2; exit 1; }
    echo "$(route_for "$2")" ;;
  --list)
    echo "Skills that differ between the default tree and each profile:"
    for p in "$PROFILE_ROOT"/*/skills; do
      [ -d "$p" ] || continue
      echo "  profile $(basename "$(dirname "$p")"):"
      while read -r f; do
        rel="${f#"$DEFAULT_TREE"/}"; rel="${rel%/SKILL.md}"
        if [ -d "$p/$rel" ]; then
          diff -rq "$DEFAULT_TREE/$rel" "$p/$rel" >/dev/null 2>&1 || echo "    ~ $rel"
        else
          echo "    - $rel (missing in this profile)"
        fi
      done < <(find "$DEFAULT_TREE" -name SKILL.md)
    done ;;
  --all)
    echo "Mirroring every skill in $DEFAULT_TREE into its routed store..."
    while read -r f; do
      rel="${f#"$DEFAULT_TREE"/}"; rel="${rel%/SKILL.md}"
      name="$(basename "$rel")"
      store="$(route_for "$name")"
      mkdir -p "$store/skills/$(dirname "$rel")"
      rm -rf "$store/skills/$rel"; cp -r "$DEFAULT_TREE/$rel" "$store/skills/$rel"
      echo "  -> $name$([ "$store" = "$PUBLIC" ] && echo ' (PUBLIC)' || echo ' (private)')"
      mirror_to_profiles "$DEFAULT_TREE/$rel" "$rel" >/dev/null
    done < <(find "$DEFAULT_TREE" -name SKILL.md)
    commit_store "$PUBLIC"; commit_store "$PRIVATE" ;;
  *)
    publish_one "$1" ;;
esac
