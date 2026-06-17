---
description: "Enrich a B2B account with firmographics (Apollo-first, no-key local fallback)."
argument-hint: "[company name | domain | path to account.json]"
---

# Enrich (shorthand)

Firmographic enrichment for a B2B account, ahead of ICP classification.

## Invocation

`/gtm-icp:enrich [company | domain | account.json]`

## Behavior

Read `skills/enrich/SKILL.md` and execute its workflow with the arguments below as the skill input. This file is a thin delegator — do not reimplement skill logic here.

$ARGUMENTS
