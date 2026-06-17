---
name: enrich
description: >-
  Enrich a B2B account with firmographics (industry, size, revenue, location,
  description) before ICP classification. Apollo-first when an APOLLO_API_KEY is
  configured; otherwise a no-key local path that keeps whatever the caller
  already knows. Use after discover, or directly on accounts the user supplies.
---

# Enrich

Turn a bare account record (a name + domain, or a discover result) into a
firmographic profile the `classify` skill can judge against the ICP.

## When to use

- The user hands you a company, a domain, or a list of accounts to qualify.
- A `discover` run produced raw accounts that need firmographic fill-in.
- You have an account but are missing size / industry / revenue to score it.

## Inputs

A single account record as JSON with at least one of `domain` / `website`, plus
any fields already known (`company_name`, `industry`, `employee_count`, …). The
record lives at `.gtm/<slug>/input.json` (write it there first if the user gave
you the account conversationally — see `_shared/artifact-structure.md`).

## Workflow

1. Resolve the account slug (`scripts/gtm_lib.py:slugify` on the company name or
   domain) and make sure `.gtm/<slug>/input.json` exists.
2. Run the enrichment script:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/enrich/scripts/enrich.py --slug <slug>
   ```

   - With `APOLLO_API_KEY` set, this calls Apollo's organization-enrichment
     endpoint by domain and maps firmographics. Apollo is a **synchronous REST
     API**, so it works fine from a skill with no backend.
   - Without a key (or with `--local`), it runs the **no-key fallback**:
     firmographic-only, sourced from what the record already carries. This is the
     clone-and-run path — no paid vendor required to qualify on firmographics.
3. The script writes `.gtm/<slug>/enrich.json` and prints a one-line summary
   (slug, enrichment_source, artifact path). Surface the `enrichment_source` to
   the user so they know whether the data came from Apollo or the local path.
4. For a batch, loop the script per account — one artifact dir each. (Entity
   fan-out across many accounts is the natural place to dispatch parallel
   subagents; keep each account's enrich isolated to its own slug.)

## Notes

- **Contacts vs firmographics.** The local path qualifies on *firmographics*
  only. Verified contact data (direct dials, valid emails) requires a paid
  vendor key — that's a deliberate boundary, not a gap to paper over.
- **Clay** is async/webhook-based, so it does not fit a backend-free skill the
  way Apollo's sync REST does. Prefer Apollo (or a direct provider) here.
- The script is stdlib-only and offline-testable:
  `bash scripts/tests/test_enrich.sh`.

This is the data stage. The judgment happens next in `classify`.
