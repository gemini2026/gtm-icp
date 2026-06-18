---
description: "Run the ICP pipeline end to end over one or more accounts (discover -> enrich -> classify -> score -> people)."
argument-hint: "[company | domain | path to accounts.json]"
---

# Pipeline (orchestrator)

Run the account(s) through the ICP pipeline stages in order. Implemented today:
**discover -> enrich -> classify -> score -> people**; the final `list`
hand-off stage is being built incrementally.

## Invocation

`/gtm-icp:pipeline [ICP brief | company | domain | accounts.json]`

## Behavior

1. If the input is an **ICP brief** (not a specific account), execute the
   `discover` skill (read `skills/discover/SKILL.md`) to find candidate
   companies — each written to `.gtm/<slug>/input.json`. If the input is a
   specific account or accounts file, write the record(s) to `input.json`
   directly and skip discover.
2. For each account slug, execute the `enrich` skill (read `skills/enrich/SKILL.md`)
   — this includes both firmographic enrichment and the deep intent-signal scan
   (website / careers / GitHub), writing `enrich.json` and `signals.json`.
3. Execute the `classify` skill (read `skills/classify/SKILL.md`), which also
   runs the deterministic scorer.
4. For each account that scores A/B, execute the `people` skill (read
   `skills/people/SKILL.md`) to resolve contacts (or persona targets without an
   Apollo key). Reject-tier accounts are skipped.
5. Report the per-account tier + score + driving evidence + contacts, ranked.

Honor the interaction mode in `skills/_shared/interaction-modes.md`: in
`interactive` pause to confirm the ICP criteria before classifying; in
`confident`/`autopilot` proceed and summarize at the end. Track progress in
`.gtm/<slug>/state.md` per `skills/_shared/state-tracking.md` so a re-run
resumes instead of redoing completed stages.

This file is a thin delegator — the stage logic lives in each skill.

$ARGUMENTS
