# State Tracking & Safe Resume

Each account carries a small state file so a re-run resumes instead of redoing
completed stages — the backend-free equivalent of resume-from-step. Adapted from
the DLC orchestrator's state model, scoped to the ICP pipeline.

## State file

Location: `.gtm/<slug>/state.md`. Create it when the pipeline first touches an
account; update it after every stage transition. The schema is **append-only** —
never rename or remove a field.

## Format

Bold-prefix lines for top-level fields (read by exact string match) plus a
markdown table for per-stage status.

```markdown
# ICP State — <account-slug>

**Last updated:** <ISO-8601 timestamp>
**Current stage:** <stage id, e.g. classify>
**Interaction mode:** interactive | confident | autopilot
**Slug:** <account-slug>
**Grounding:** k2 | local | none

## Stage status

| Stage       | Status      | Artifact      |
|-------------|-------------|---------------|
| enrich      | completed   | enrich.json   |
| classify    | in_progress | —             |
| score       | pending     | —             |
| people      | pending     | —             |
| list        | pending     | —             |
| personalize | pending     | —             |

## Decisions Log

- **<date>** — enrich: Apollo key absent, used local firmographics
- **<date>** — classify: grounded on K2 corpus (vertical=industrial)
```

## Resume protocol

When asked to resume / continue an account:

1. Read `.gtm/<slug>/state.md`; the **`Current stage`** bold-prefix line is the
   single source of truth for routing.
2. For each stage the table marks `completed`, confirm its artifact exists on
   disk. If missing, mark it `in_progress` and re-run that stage.
3. Resume from `Current stage`. Stages are pure functions of their input
   artifact, so re-running a stage is always safe (it overwrites its own output).
4. No state file → start from the first unbuilt stage (currently `enrich`).

## Update points

Update the file (mutating `Last updated`, and `Current stage` on a boundary)
when a stage starts and when it completes, and append a Decisions Log line for
any material choice (grounding source, fallback taken, criteria edited).
