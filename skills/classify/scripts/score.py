#!/usr/bin/env python3
"""Deterministically score a classified account.

The classify *judgment* is made by the LLM (the skill itself), which writes a
classify.json holding a per-criterion verdict grounded on the corpus. This
script turns those verdicts into a transparent, reproducible 0-100 fit score
and a tier — no LLM in the loop, so the same classify.json always yields the
same score and the math is auditable.

Expected classify.json shape:
    {
      "company_name": "Acme",
      "criteria": [
        {"key": "vertical_match", "weight": 0.4, "met": true,  "evidence": "..."},
        {"key": "size_fit",       "weight": 0.3, "met": true,  "evidence": "..."},
        {"key": "ai_posture",     "weight": 0.3, "met": false, "evidence": "..."}
      ]
    }

Writes .gtm/<slug>/score.json with {score, tier, criteria_hit, rationale}.

Tier thresholds (overridable via env GTM_TIER_A / GTM_TIER_B):
    score >= A  -> "A"     default A = 75
    score >= B  -> "B"     default B = 45
    else        -> "C"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import gtm_lib  # noqa: E402


def score_account(classify: dict) -> dict:
    criteria = classify.get("criteria", [])
    total_weight = sum(c.get("weight", 0) for c in criteria)
    if total_weight <= 0:
        raise ValueError("criteria weights sum to zero; cannot score")
    earned = sum(c.get("weight", 0) for c in criteria if c.get("met"))
    score = round(100 * earned / total_weight, 1)

    tier_a = float(os.environ.get("GTM_TIER_A", "75"))
    tier_b = float(os.environ.get("GTM_TIER_B", "45"))
    tier = "A" if score >= tier_a else "B" if score >= tier_b else "C"

    hits = [c["key"] for c in criteria if c.get("met")]
    misses = [c["key"] for c in criteria if not c.get("met")]
    return {
        "company_name": classify.get("company_name"),
        "score": score,
        "tier": tier,
        "criteria_hit": hits,
        "criteria_missed": misses,
        "rationale": f"{len(hits)}/{len(criteria)} criteria met "
                     f"({earned:.2f}/{total_weight:.2f} weight) -> {score} -> tier {tier}",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Score a classified account.")
    ap.add_argument("--slug", required=True, help="account slug under the artifact root")
    args = ap.parse_args(argv)

    classify = gtm_lib.read_json(gtm_lib.stage_path(args.slug, "classify"))
    out = score_account(classify)
    path = gtm_lib.write_json(gtm_lib.stage_path(args.slug, "score"), out)
    print(json.dumps({"slug": args.slug, "score": out["score"], "tier": out["tier"],
                      "artifact": str(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
