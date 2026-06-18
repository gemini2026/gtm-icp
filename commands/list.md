---
description: "Build the GTM hand-off: a ranked CSV + per-account markdown dossier across every scored account."
argument-hint: "[--include-reject]"
---

# List (shorthand)

Aggregate every scored account into the prioritized target list for outreach.

## Invocation

`/gtm-icp:list [--include-reject]`

## Behavior

Read `skills/list/SKILL.md` and execute its workflow with the arguments below as the skill input. This file is a thin delegator — do not reimplement skill logic here.

$ARGUMENTS
