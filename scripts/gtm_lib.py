"""Shared helpers for gtm-icp skill scripts.

stdlib only — no external dependencies, so the plugin clones and runs with a
bare Python 3.10+ interpreter. Skill scripts import this for artifact-path
resolution and reading/writing the per-account run state.

Artifact layout (see skills/_shared/artifact-structure.md):

    .gtm/<account-slug>/
        input.json        # the raw account record the pipeline started from
        enrich.json       # output of the enrich stage
        classify.json     # output of the classify stage
        score.json        # output of the score stage
        state.md          # append-only stage status (see state-tracking.md)
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

STAGES = ["enrich", "classify", "score", "persist", "personalize"]


def artifact_root() -> Path:
    """Root for all run artifacts. Override with GTM_ARTIFACT_ROOT."""
    return Path(os.environ.get("GTM_ARTIFACT_ROOT", ".gtm"))


def slugify(name: str) -> str:
    """Stable, filesystem-safe slug for an account name or domain."""
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    return s.strip("-") or "account"


def account_dir(slug: str) -> Path:
    d = artifact_root() / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path


def stage_path(slug: str, stage: str) -> Path:
    return account_dir(slug) / f"{stage}.json"
