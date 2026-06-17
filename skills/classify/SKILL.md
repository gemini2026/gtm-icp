---
name: classify
description: >-
  Judge whether an enriched account fits the ICP, grounded on your own knowledge
  corpus (won-deal patterns, positioning, case studies) rather than a generic
  prompt. Emits a per-criterion verdict, then runs a deterministic scorer to
  produce a 0-100 fit score and an A/B/C tier. Use after enrich.
---

# Classify

Decide if an account fits the Ideal Customer Profile — and *why* — then score it
deterministically. This is the stage where corpus grounding is the edge: the
judgment is made against what has actually won, not a bare LLM guess.

## When to use

- An account has been enriched (`.gtm/<slug>/enrich.json` exists) and needs an
  ICP fit verdict + score.
- The user wants to know not just the score but the evidence behind it.

## Inputs

- `.gtm/<slug>/enrich.json` — the firmographic profile from `enrich`.
- The ICP **criteria** — a small set of weighted, checkable conditions. If the
  user hasn't supplied them, read `icp.criteria.json` at the repo root (or ask
  for them in interactive mode). Each criterion: `{key, weight, description}`.

## Workflow

1. **Ground the judgment.** Retrieve relevant context for this account:
   - If `k2_api_host` / `k2_api_key` are configured, query the corpus via the
     bundled K2 stdio MCP shim for won-deal patterns, positioning, and
     case-study evidence matching the account's vertical/size.
   - Otherwise, read local corpus files under `corpus/` (markdown notes on past
     wins, ICP rationale). Local grounding is the no-key path.
   - **You are the agent here** — there is no model call to orchestrate. Reason
     over the enrichment + the grounded evidence directly.
2. **Judge each criterion.** For every ICP criterion, decide `met: true|false`
   and write one line of `evidence` citing the enrichment field or the grounded
   corpus snippet that justifies it. Do not invent firmographics not present in
   `enrich.json`; if a criterion can't be evaluated, mark it `met: false` and say
   why in the evidence.
3. **Write the verdict** to `.gtm/<slug>/classify.json`:

   ```json
   {
     "company_name": "...",
     "criteria": [
       {"key": "vertical_match", "weight": 0.4, "met": true,  "evidence": "..."},
       {"key": "size_fit",       "weight": 0.3, "met": true,  "evidence": "..."},
       {"key": "ai_posture",     "weight": 0.3, "met": false, "evidence": "..."}
     ]
   }
   ```

   Keep the same `weight` values the criteria define — the scorer normalizes them.
4. **Score deterministically:**

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/classify/scripts/score.py --slug <slug>
   ```

   This reads `classify.json` and writes `.gtm/<slug>/score.json` with a
   normalized 0-100 `score`, an A/B/C `tier`, and the hit/miss breakdown. The
   score is pure arithmetic over your verdicts — **no LLM judges the score**, so
   it's reproducible and auditable. Tier cutoffs are tunable via `GTM_TIER_A` /
   `GTM_TIER_B`.
5. **Report** the tier, score, and the one or two criteria that drove it (the
   `criteria_hit` / `criteria_missed` lists), with the evidence lines. The
   evidence is the point — a number with no grounding is what every commodity
   wrapper already produces.

## Why grounding matters here

A bare LLM can guess ICP fit from firmographics. The defensible version cites
*your* won deals and positioning — that's the difference between a replaceable
wrapper and a tool that encodes what your team has learned. Lead with the
evidence, not the score.

Offline scorer test: `bash scripts/tests/test_score.sh`.
