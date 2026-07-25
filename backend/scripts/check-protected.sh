#!/usr/bin/env bash
# HUMAN-OWNED. Fails if any changed file matches a protected glob.
#   ./scripts/check-protected.sh              staged changes (pre-commit)
#   ./scripts/check-protected.sh origin/main  everything since a ref (CI)
# Human escape hatch: HUMAN=1 ./scripts/check-protected.sh
set -euo pipefail

if [[ "${HUMAN:-0}" == "1" ]]; then
  echo "check-protected: HUMAN=1 set, skipping."
  exit 0
fi

GLOBFILE="$(cd "$(dirname "$0")/.." && pwd)/quality/protected-paths.txt"
cd "$(git rev-parse --show-toplevel)"

BASE="${1:-}"
if [[ -n "$BASE" ]]; then
  CHANGED=$(git diff --name-only "$BASE"...HEAD)
else
  CHANGED=$(git diff --cached --name-only)
fi

[[ -z "$CHANGED" ]] && { echo "✓ no changes to check"; exit 0; }

GLOBS=$(grep -vE '^\s*(#|$)' "$GLOBFILE")

VIOLATIONS=()
while IFS= read -r file; do
  while IFS= read -r glob; do
    # shellcheck disable=SC2053
    if [[ "$file" == $glob ]]; then
      VIOLATIONS+=("$file")
      break
    fi
  done <<< "$GLOBS"
done <<< "$CHANGED"

if (( ${#VIOLATIONS[@]} > 0 )); then
  echo "✗ Protected files were modified:"
  printf '    %s\n' "${VIOLATIONS[@]}"
  echo
  echo "These define what 'correct' means. An agent changing them is an agent"
  echo "grading its own exam. If you are the human and this is intentional:"
  echo "    HUMAN=1 git commit ..."
  exit 1
fi

echo "✓ no protected files touched"
