# gtm-icp

**GTM-as-code: an ICP qualification pipeline that runs as a Claude plugin — no backend, no markup, grounded on your own corpus.**

> Working name. This is an early scaffold: one end-to-end vertical slice
> (`enrich → classify → score`) is implemented; the rest of the pipeline is
> stubbed.

Most ICP/lead-scoring tools are hosted SaaS that mark up data you already pay
for and score accounts with a generic prompt. `gtm-icp` flips both:

- **No hosted backend.** The pipeline is a set of Claude skills with bundled,
  stdlib-only Python scripts. Clone it, install it as a plugin, run it.
- **Bring your own keys, no markup.** Enrichment calls your Apollo key directly
  (sync REST). The orchestration and LLM reasoning cost cents; the data is
  yours at vendor cost, not resold.
- **Grounded, not guessed.** Classification cites *your* won-deal patterns,
  positioning, and case studies — from a local corpus or a K2 corpus — instead
  of a bare LLM judgment. That grounding is the part a commodity wrapper can't
  trivially copy.
- **A real no-key path.** Without any paid key, enrich runs firmographic-only
  and classify grounds on local corpus files. You get a working
  clone-and-run demo with zero secrets.

## Pipeline stages

| Stage | Status | What it does |
|-------|--------|--------------|
| `discover` | planned | Internet-grounded account discovery (Perplexity). |
| **`enrich`** | **implemented** | Firmographic enrichment — Apollo-first, no-key local fallback. |
| **`classify`** | **implemented** | Corpus-grounded ICP verdict + deterministic 0-100 score & A/B/C tier. |
| `persist` | planned | Write qualified accounts to a store / CRM. |
| `personalize` | planned | Corpus-grounded outreach drafting (with a human approval gate). |

## Quickstart (no keys)

Requires Python 3.10+. From the repo root:

```bash
# 1. Enrich the example account (local, no paid key)
python3 skills/enrich/scripts/enrich.py --input examples/acme.json --local

# 2. Classify is the LLM step — in Claude, run /gtm-icp:classify acme-robotics
#    Claude reads enrich.json + icp.criteria.json, grounds on corpus/, and
#    writes .gtm/acme-robotics/classify.json. Then score it:
python3 skills/classify/scripts/score.py --slug acme-robotics
```

Artifacts land in `.gtm/<slug>/` (git-ignored). See
`skills/_shared/artifact-structure.md`.

## As a Claude plugin

Installed as a plugin, the stages are slash commands:

- `/gtm-icp:enrich <company | domain | account.json>`
- `/gtm-icp:classify <slug>`
- `/gtm-icp:pipeline <company | accounts.json>` — runs the slice end to end

Configure keys via the plugin's `userConfig` (`apollo_api_key`,
`perplexity_api_key`, `k2_api_host` / `k2_api_key`) — all optional; absent keys
fall back to the local path.

## Configuration

| Key | Used by | Effect when absent |
|-----|---------|--------------------|
| `apollo_api_key` | enrich | Firmographic-only local enrichment. |
| `perplexity_api_key` | discover (planned) | Discovery disabled; supply accounts directly. |
| `k2_api_host` + `k2_api_key` | classify, personalize | Grounding falls back to local `corpus/` files. |

Tier cutoffs: `GTM_TIER_A` (default 75), `GTM_TIER_B` (default 45). Artifact
root: `GTM_ARTIFACT_ROOT` (default `.gtm`).

## Testing

Offline, no network, no keys:

```bash
bash skills/enrich/scripts/tests/test_enrich.sh
bash skills/classify/scripts/tests/test_score.sh
```

## Design notes

The open-core boundary is deliberate: everything backend-free lives here as
skills (interactive, BYO-keys, developer-first). The parts that genuinely need
a server — scheduling, durable multi-day sequences, team state — are a separate
hosted layer, not part of this OSS core. See the companion design docs in the
`knowledge2-icp` repo for the full rationale.

## License

MIT — see [LICENSE](LICENSE).
