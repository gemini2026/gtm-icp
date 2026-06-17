#!/usr/bin/env bash
# Offline test for score.py — deterministic weighted scoring + tiers.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCORE="$HERE/../score.py"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fail() { echo "FAIL: $1" >&2; exit 1; }

mkdir -p "$WORK/.gtm/acme"
cat >"$WORK/.gtm/acme/classify.json" <<'JSON'
{"company_name": "Acme",
 "criteria": [
   {"key": "vertical_match", "weight": 0.4, "met": true,  "evidence": "x"},
   {"key": "size_fit",       "weight": 0.3, "met": true,  "evidence": "y"},
   {"key": "ai_posture",     "weight": 0.3, "met": false, "evidence": "z"}
 ]}
JSON

# 0.7 of 1.0 weight met -> 70.0 -> tier B (45 <= 70 < 75)
out="$(GTM_ARTIFACT_ROOT="$WORK/.gtm" python3 "$SCORE" --slug acme)"
echo "$out" | grep -q '"score": 70.0' || fail "expected score 70.0 ($out)"
echo "$out" | grep -q '"tier": "B"'   || fail "expected tier B ($out)"

# Custom threshold: lower tier-A boundary makes the same 70.0 an A.
out_a="$(GTM_ARTIFACT_ROOT="$WORK/.gtm" GTM_TIER_A=65 python3 "$SCORE" --slug acme)"
echo "$out_a" | grep -q '"tier": "A"' || fail "expected tier A with GTM_TIER_A=65 ($out_a)"

echo "PASS test_score.sh"
