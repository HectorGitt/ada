#!/usr/bin/env bash
# HUMAN-OWNED. Installs the pre-commit hook that runs the protected-path check.
set -euo pipefail
HOOK="$(git rev-parse --git-dir)/hooks/pre-commit"
cat > "$HOOK" << 'HOOKEOF'
#!/usr/bin/env bash
exec backend/scripts/check-protected.sh
HOOKEOF
chmod +x "$HOOK"
echo "✓ pre-commit hook installed"
