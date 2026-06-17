---
name: discover
description: >-
  Find companies that fit an ICP from a natural-language brief — the front of
  the pipeline. Perplexity-grounded web research when a key is configured, with
  a no-key DuckDuckGo fallback and a deterministic seed-list path. Writes one
  account per company so enrich/classify/score/people pick them up unchanged.
---

# Discover

Turn an ICP description ("Series B logistics SaaS in NA, 100-500 employees,
hiring ML engineers") into a list of real candidate companies to qualify.

## When to use

- The user wants to *find* accounts matching an ICP, not score ones they have.
- You have a seed list of companies/domains to pull into the pipeline.

## Inputs

- A natural-language **brief**, or a **seed list** file (`Name, domain` per line,
  or bare domains, or a header row — all handled).
- `icp.criteria.json` at the repo root — used to ground the Perplexity research
  prompt so results match the actual ICP, not just the brief wording.

## Workflow

1. Resolve the request to a brief or a seed file.
2. Run the discovery script:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/discover/scripts/discover.py \
     --brief "<the ICP brief>" --max 10
   # or, deterministic / no network:
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/discover/scripts/discover.py --seeds <file>
   ```

   Provider cascade:
   - **Perplexity** (primary) — set `PERPLEXITY_API_KEY`. Returns a structured,
     web-cited company list grounded on the ICP criteria. This is the real
     engine.
   - **DuckDuckGo** (no-key fallback) — best-effort scrape of search results;
     may return little when DDG serves a JS page. Honest degraded mode.
   - **Seed list** (`--seeds`) — deterministic, offline; for lists you already
     have.
3. Each company is written to `.gtm/<slug>/input.json` (company, domain, source
   URL, discovery notes, any github/linkedin refs found). A roll-up lands at
   `.gtm/_discover/candidates.json`.
4. Report the count, the provider that produced them, and any warnings. Then the
   accounts are ready for `enrich` — typically you fan out enrich/classify/score
   across all discovered slugs.

## Notes

- **No-key reality:** Perplexity is what makes discovery good. Without a key you
  get the DuckDuckGo fallback (variable) or the seed path (deterministic). Say
  which path ran so the user knows the quality bar.
- **Hiring/GitHub signals** captured here (github/linkedin reference URLs) feed
  the later scrape/enrich stage; discover just collects the leads.

Offline test (seed path): `bash scripts/tests/test_discover.sh`.
