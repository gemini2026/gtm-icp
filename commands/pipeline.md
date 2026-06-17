---
description: "Run the ICP pipeline end to end over one or more accounts (currently: enrich -> classify -> score)."
argument-hint: "[company | domain | path to accounts.json]"
---

# Pipeline (orchestrator)

Run the account(s) through the ICP pipeline stages in order. The implemented
vertical slice is **enrich -> classify -> score**; later stages (discover,
persist, personalize) are stubbed and skipped until built.

## Invocation

`/gtm-icp:pipeline [company | domain | accounts.json]`

## Behavior

For each account in the input:

1. Ensure `.gtm/<slug>/input.json` exists (write it from the supplied record).
2. Execute the `enrich` skill (read `skills/enrich/SKILL.md`).
3. Execute the `classify` skill (read `skills/classify/SKILL.md`), which also
   runs the deterministic scorer.
4. Report the per-account tier + score + driving evidence.

Honor the interaction mode in `skills/_shared/interaction-modes.md`: in
`interactive` pause to confirm the ICP criteria before classifying; in
`confident`/`autopilot` proceed and summarize at the end. Track progress in
`.gtm/<slug>/state.md` per `skills/_shared/state-tracking.md` so a re-run
resumes instead of redoing completed stages.

This file is a thin delegator — the stage logic lives in each skill.

$ARGUMENTS
