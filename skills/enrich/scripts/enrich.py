#!/usr/bin/env python3
"""Enrich a B2B account with firmographics.

Apollo-first waterfall with a no-key local fallback:

  * If APOLLO_API_KEY is set (and --local is not passed), call Apollo's
    organization-enrichment endpoint by domain and map the firmographic
    fields the ICP cares about.
  * Otherwise, run in local mode: pass through whatever the caller already
    knows, tagged enrichment_source="local". This keeps a real clone-and-run
    path with zero paid keys (firmographic-only, no verified contacts).

Reads  .gtm/<slug>/input.json   (or --input <path>)
Writes .gtm/<slug>/enrich.json

stdlib only. Apollo is called over urllib so there are no dependencies.

Usage:
    python enrich.py --slug acme            # uses .gtm/acme/input.json
    python enrich.py --input account.json   # slug derived from the record
    python enrich.py --slug acme --local    # force the no-key path
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import gtm_lib  # noqa: E402

# Verify against current Apollo docs before relying in production:
# https://docs.apollo.io/reference/organization-enrichment
APOLLO_ORG_ENRICH = "https://api.apollo.io/v1/organizations/enrich"

# Apollo firmographic fields -> normalized ICP fields.
FIELD_MAP = {
    "name": "company_name",
    "website_url": "website",
    "industry": "industry",
    "estimated_num_employees": "employee_count",
    "annual_revenue": "annual_revenue",
    "founded_year": "founded_year",
    "country": "country",
    "linkedin_url": "linkedin_url",
    "short_description": "description",
}


def _apollo_enrich(domain: str, api_key: str) -> dict:
    qs = urllib.parse.urlencode({"domain": domain})
    req = urllib.request.Request(
        f"{APOLLO_ORG_ENRICH}?{qs}",
        method="GET",
        headers={"X-Api-Key": api_key, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    org = body.get("organization") or {}
    mapped = {dst: org.get(src) for src, dst in FIELD_MAP.items() if org.get(src) is not None}
    mapped["enrichment_source"] = "apollo"
    return mapped


def _local_enrich(record: dict) -> dict:
    """No-key fallback: keep known firmographics, normalize a couple of keys."""
    keep = ("company_name", "website", "industry", "employee_count",
            "annual_revenue", "founded_year", "country", "description")
    mapped = {k: record[k] for k in keep if record.get(k) is not None}
    mapped["enrichment_source"] = "local"
    return mapped


def enrich(record: dict, *, local: bool) -> dict:
    api_key = os.environ.get("APOLLO_API_KEY", "").strip()
    domain = record.get("domain") or record.get("website")
    if not local and api_key and domain:
        domain = domain.replace("https://", "").replace("http://", "").strip("/")
        try:
            firmographics = _apollo_enrich(domain, api_key)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            firmographics = _local_enrich(record)
            firmographics["enrichment_warning"] = f"apollo call failed, fell back to local: {exc}"
    else:
        firmographics = _local_enrich(record)
    return {**record, **firmographics}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Enrich a B2B account.")
    ap.add_argument("--slug", help="account slug under the artifact root")
    ap.add_argument("--input", type=Path, help="path to an input.json record")
    ap.add_argument("--local", action="store_true", help="force no-key local enrichment")
    args = ap.parse_args(argv)

    if args.input:
        record = gtm_lib.read_json(args.input)
        slug = args.slug or gtm_lib.slugify(record.get("company_name") or record.get("domain") or "account")
    elif args.slug:
        slug = args.slug
        record = gtm_lib.read_json(gtm_lib.stage_path(slug, "input").with_name("input.json"))
    else:
        ap.error("provide --slug or --input")

    out = enrich(record, local=args.local)
    path = gtm_lib.write_json(gtm_lib.stage_path(slug, "enrich"), out)
    print(json.dumps({"slug": slug, "enrichment_source": out.get("enrichment_source"),
                      "artifact": str(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
