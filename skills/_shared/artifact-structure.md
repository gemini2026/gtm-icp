# Artifact Structure

Every account the pipeline touches gets its own directory under the artifact
root (`.gtm/` by default; override with `GTM_ARTIFACT_ROOT`). One directory per
account keeps stages isolated and makes entity fan-out trivial — parallel
workers never contend.

```
.gtm/<account-slug>/
    input.json        # the raw account record the pipeline started from
    enrich.json       # firmographic profile           (enrich stage)
    signals.json      # deep intent signals             (enrich stage, signals.py)
    classify.json     # per-criterion ICP verdict       (classify stage)
    score.json        # normalized score + tier         (score, run by classify)
    people.json       # contacts / persona targets      (people stage)
    state.md          # per-account stage status        (see state-tracking.md)
```

Rules:

- **Slug** is derived once from the company name or domain
  (`scripts/gtm_lib.py:slugify`) and is stable across re-runs.
- Each stage **reads the prior stage's artifact and writes its own** — never
  mutate an upstream file in place. This is what makes resume and replay safe.
- Artifacts are JSON (machine-readable) so a re-run can detect "this stage
  already produced output" and skip it.
- The artifact root is git-ignored — runs are working data, not source.
