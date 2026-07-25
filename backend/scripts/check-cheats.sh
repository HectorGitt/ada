#!/usr/bin/env bash
# HUMAN-OWNED. Fails on gate-dodging markers. Code-specific suppressions with a
# written reason (e.g. "# noqa: BLE001 — why") are allowed; bare ones are not.
set -uo pipefail

SCAN_DIRS=(src tests features)
ALLOWLIST="quality/cheat-allowlist.txt"

PATTERNS=(
  'pragma:[[:space:]]*no[[:space:]]*cover'
  'type:[[:space:]]*ignore[[:space:]]*$'
  'type:[[:space:]]*ignore[^[]'
  '#[[:space:]]*noqa[[:space:]]*$'
  '#[[:space:]]*noqa[^:]'
  '@pytest\.mark\.(skip|xfail)\b'
  'pytest\.skip\('
  'unittest\.skip'
  '\bassert True\b'
  'mutmut:[[:space:]]*disable'
  '(MIN_COVERAGE|MIN_MUTATION_SCORE)[[:space:]]*='
)

FAIL=0
for pat in "${PATTERNS[@]}"; do
  while IFS= read -r hit; do
    [[ -z "$hit" ]] && continue
    file="${hit%%:*}"
    if [[ -f "$ALLOWLIST" ]] && grep -Fqx -- "$file" "$ALLOWLIST"; then
      continue
    fi
    echo "✗ suppression marker: $hit"
    FAIL=1
  done < <(grep -rnE --include='*.py' --include='*.feature' "$pat" "${SCAN_DIRS[@]}" 2>/dev/null)
done

while IFS= read -r f; do
  if ! grep -qE '\b(assert|pytest\.raises)\b' "$f"; then
    echo "✗ test file with no assertions: $f"
    FAIL=1
  fi
done < <(find tests features -name 'test_*.py' 2>/dev/null)

if (( FAIL )); then
  echo
  echo "Gates were suppressed rather than satisfied. Fix the code, not the gate."
  exit 1
fi

echo "✓ no suppression markers"
