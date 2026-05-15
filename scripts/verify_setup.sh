#!/usr/bin/env bash
# Verify that the Tech Pulse API setup is complete and healthy.
# Usage: ./scripts/verify_setup.sh https://<your-vercel-app>.vercel.app
set -euo pipefail

BASE="${1:-}"
if [[ -z "$BASE" ]]; then
  echo "usage: $0 <vercel-base-url>"
  echo "  example: $0 https://tech-pulse-api.vercel.app"
  exit 1
fi

pass=0
fail=0

check() {
  local label="$1" url="$2" expect="${3:-200}"
  local code
  code=$(curl -sS -o /dev/null -w "%{http_code}" "$url" || echo "ERR")
  if [[ "$code" == "$expect" ]]; then
    printf "  \033[32m✓\033[0m %-40s %s\n" "$label" "$code"
    pass=$((pass + 1))
  else
    printf "  \033[31m✗\033[0m %-40s %s (expected %s)\n" "$label" "$code" "$expect"
    fail=$((fail + 1))
  fi
}

echo "Checking $BASE..."
echo
echo "Public endpoints (should be reachable):"
check "Landing page (/)"           "$BASE/"          200
check "Dashboard (/dashboard)"     "$BASE/dashboard" 200
check "Health (/health)"           "$BASE/health"    200
check "OpenAPI (/openapi.json)"    "$BASE/openapi.json" 200

echo
echo "Authenticated endpoints (should reject unauthenticated):"
check "Latest snapshot (no auth)"  "$BASE/v1/pulse/latest"   401
check "Trending (no auth)"         "$BASE/v1/pulse/trending" 401

echo
echo "----"
echo "Pass: $pass  Fail: $fail"
if [[ $fail -gt 0 ]]; then
  echo "Some checks failed. See QUICKSTART.md → Troubleshooting."
  exit 1
fi
echo "All checks passed. Your deploy is healthy."
echo
echo "Next: list on RapidAPI per QUICKSTART.md step 5."
