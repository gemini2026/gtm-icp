#!/usr/bin/env bash
# Offline test for enrich.py — local fallback path, no network, no keys.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ENRICH="$HERE/../enrich.py"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { echo "FAIL: $1" >&2; exit 1; }

cat >"$WORK/account.json" <<'JSON'
{"company_name": "Acme Robotics", "domain": "acme.example",
 "industry": "Industrial Automation", "employee_count": 320}
JSON

# Force local mode so the test never touches the network.
out="$(GTM_ARTIFACT_ROOT="$WORK/.gtm" APOLLO_API_KEY="" \
  python3 "$ENRICH" --input "$WORK/account.json" --local)"

echo "$out" | grep -q '"enrichment_source": "local"' || fail "expected local enrichment_source ($out)"

artifact="$WORK/.gtm/acme-robotics/enrich.json"
[ -f "$artifact" ] || fail "enrich.json not written at $artifact"
grep -q '"company_name": "Acme Robotics"' "$artifact" || fail "company_name not preserved"
grep -q '"employee_count": 320' "$artifact" || fail "firmographics not preserved"

echo "PASS test_enrich.sh"
