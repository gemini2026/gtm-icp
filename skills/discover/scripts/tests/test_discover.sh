#!/usr/bin/env bash
# Offline test for discover.py — seed-list path, no network, no keys.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DISCOVER="$HERE/../discover.py"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { echo "FAIL: $1" >&2; exit 1; }

# Mixed seed formats: header row, "Name, domain", and bare domains on one line.
cat >"$WORK/seeds.csv" <<'CSV'
Company, Domain
Acme Robotics, acme.example
Globex, globex.example
moj.io, automate.example
# a comment line, ignored
CSV

out="$(cd "$WORK" && GTM_ARTIFACT_ROOT="$WORK/.gtm" python3 "$DISCOVER" --seeds "$WORK/seeds.csv")"

echo "$out" | grep -q '"provider": "seeds"' || fail "expected provider seeds ($out)"
# Acme + Globex + two bare domains (moj.io, automate.example) = 4 candidates.
echo "$out" | grep -q '"discovered": 4' || fail "expected 4 discovered ($out)"

[ -f "$WORK/.gtm/acme-example/input.json" ] || fail "acme input.json not written"
grep -q '"company_name": "Acme Robotics"' "$WORK/.gtm/acme-example/input.json" || fail "name not mapped"
[ -f "$WORK/.gtm/_discover/candidates.json" ] || fail "rollup not written"

echo "PASS test_discover.sh"
