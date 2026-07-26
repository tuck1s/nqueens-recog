#!/usr/bin/env bash
# git-diff-notime.sh — diff files under a path while ignoring a leading
# "N.Ns:" timestamp column, so only *real* content changes show up.
#
# Usage:
#   ./git-diff-notime.sh <rev1> [rev2] [-- <pathspec>]
#
# Examples:
#   ./git-diff-notime.sh HEAD~1                 # HEAD~1 vs working tree
#   ./git-diff-notime.sh HEAD~1 HEAD             # HEAD~1 vs HEAD
#   ./git-diff-notime.sh HEAD~1 HEAD -- all_solutions/
#
# Defaults to comparing against the working tree if rev2 is omitted,
# and to the all_solutions/ folder if no pathspec is given.

set -euo pipefail

rev1="${1:-HEAD}"; shift || true
rev2=""
if [[ "${1:-}" != "" && "${1:-}" != "--" ]]; then
  rev2="$1"; shift || true
fi
if [[ "${1:-}" == "--" ]]; then shift; fi
pathspec=("${@:-all_solutions/}")

# Strip timestamps wherever they appear, replacing each with a fixed
# placeholder so otherwise-identical lines compare equal:
#   - all_solutions/level_*.html: leading trace prefix, e.g. "0.2s:"
#   - all_solutions/index.html:   Runtime column, e.g. "<td>0.116s</td>"
#   - all_solutions/index.html:   build-time header, e.g.
#       "Solutions Index built: 2026-07-16 23:13:01 UTC"
strip_ts() {
  sed -E \
    -e 's/^[0-9]+\.[0-9]+s:/<T>s:/' \
    -e 's/<td>[0-9]+\.[0-9]+s<\/td>/<td><T>s<\/td>/' \
    -e 's/Solutions Index built: [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} UTC/Solutions Index built: <T>/'
}

# List of changed files between the two revs (or rev1..working tree)
if [[ -n "$rev2" ]]; then
  files=$(git diff --name-only "$rev1" "$rev2" -- "${pathspec[@]}")
else
  files=$(git diff --name-only "$rev1" -- "${pathspec[@]}")
fi

if [[ -z "$files" ]]; then
  echo "No changed files under: ${pathspec[*]}"
  exit 0
fi

any_real_diff=0
while IFS= read -r f; do
  [[ -z "$f" ]] && continue

  old=$(git show "$rev1:$f" 2>/dev/null | strip_ts || true)
  if [[ -n "$rev2" ]]; then
    new=$(git show "$rev2:$f" 2>/dev/null | strip_ts || true)
  else
    new=$(strip_ts < "$f" 2>/dev/null || true)
  fi

  if ! diff -q <(printf '%s' "$old") <(printf '%s' "$new") >/dev/null; then
    any_real_diff=1
    echo "=== $f ==="
    diff -u <(printf '%s' "$old") <(printf '%s' "$new") | sed '1,2d' || true
    echo
  fi
done <<< "$files"

if [[ "$any_real_diff" -eq 0 ]]; then
  echo "All changes under ${pathspec[*]} were timestamp-only ($(wc -l <<< "$files") file(s) touched)."
fi
