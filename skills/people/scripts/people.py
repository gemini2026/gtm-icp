#!/usr/bin/env python3
"""Find the right contacts inside a qualified account (the `people` stage).

Qualification (discover -> enrich -> classify -> score) tells you *which*
accounts to pursue. This stage answers *who* to reach inside each one: it maps
the ICP's buying personas to real contacts via Apollo's people-search API.

Apollo-first with a no-key fallback that still produces value:

  * With APOLLO_API_KEY set, search people at the account's domain for the
    persona titles the ICP declares, and return compacted contacts (name,
    title, matched persona, email status, LinkedIn).
  * Without a key (or --local), return the *persona targets* — the exact titles
    a rep should go find — so the stage is still actionable with zero secrets.
    This mirrors the boundary in enrich: verified contact data needs a paid key.

By default a Reject-tier account is skipped (don't spend Apollo credits on an
account the rubric already disqualified); pass --force to search anyway.

Personas come from `icp.criteria.json`:

    "personas": [
      {"title": "Chief Product Officer", "priority": "primary",
       "apollo_titles": ["chief product officer", "vp product", "head of product"]}
    ]

Reads  .gtm/<slug>/enrich.json (falls back to input.json) for domain/company,
       .gtm/<slug>/score.json   (optional) for the tier gate.
Writes .gtm/<slug>/people.json

stdlib only. Apollo is called over urllib; no dependencies.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import gtm_lib  # noqa: E402

USER_AGENT = "gtm-icp/0.1 (+https://github.com/knowledge2-ai/gtm-icp)"
# Verify against current Apollo docs before relying in production:
# https://docs.apollo.io/reference/people-search
APOLLO_PEOPLE_SEARCH = "https://api.apollo.io/api/v1/mixed_people/api_search"

# Used when the ICP declares no `personas`.
DEFAULT_PERSONAS = [
    {"title": "Chief Product Officer", "priority": "primary",
     "apollo_titles": ["chief product officer", "vp product", "head of product"]},
    {"title": "CTO / VP Engineering", "priority": "primary",
     "apollo_titles": ["chief technology officer", "vp engineering", "head of engineering"]},
    {"title": "Head of Data / AI", "priority": "secondary",
     "apollo_titles": ["chief data officer", "vp data", "head of data"]},
]


def _clean_domain(value: str) -> str:
    return (value or "").replace("https://", "").replace("http://", "").strip("/").split("/")[0]


def _personas_from_icp(criteria_path: Path) -> list[dict]:
    if criteria_path.exists():
        declared = gtm_lib.read_json(criteria_path).get("personas")
        if isinstance(declared, list) and declared:
            return [p for p in declared if isinstance(p, dict)]
    return DEFAULT_PERSONAS


def _target_titles(personas: list[dict]) -> list[str]:
    """Flatten persona apollo_titles into a de-duplicated, order-stable list."""
    seen, out = set(), []
    for persona in personas:
        for title in persona.get("apollo_titles") or [persona.get("title", "")]:
            t = (title or "").strip().lower()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
    return out


def _terms(value: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (value or "").lower())
            if len(t) > 1 and t not in {"of", "and", "the"}}


def _match_persona(title: str, personas: list[dict]) -> dict:
    """Best persona for a person's title by term overlap with its apollo_titles."""
    title_terms = _terms(title)
    if not title_terms:
        return personas[0] if personas else {}
    best = (0, {})
    for persona in personas:
        haystack = persona.get("title", "") + " " + " ".join(persona.get("apollo_titles", []))
        overlap = len(title_terms & _terms(haystack))
        if overlap > best[0]:
            best = (overlap, persona)
    return best[1] or (personas[0] if personas else {})


def _compact_people(payload: dict) -> list[dict]:
    raw = payload.get("people") or payload.get("contacts") or []
    items = raw if isinstance(raw, list) else []
    out = []
    for item in items[:25]:
        if not isinstance(item, dict):
            continue
        org = item.get("organization") if isinstance(item.get("organization"), dict) else {}
        location = ", ".join(p for p in [item.get("city"), item.get("state"), item.get("country")] if p)
        out.append({
            "name": item.get("name") or "",
            "title": item.get("title") or "",
            "email": item.get("email") or "",
            "email_status": item.get("email_status") or "",
            "linkedin_url": item.get("linkedin_url") or "",
            "location": location,
            "organization_name": org.get("name") or "",
        })
    return out


def apollo_search_people(domain: str, titles: list[str], api_key: str, *,
                         per_page: int = 8, timeout: float = 12.0) -> dict:
    """POST Apollo people-search by domain + titles. Returns {status, people}."""
    params: list[tuple[str, str | int]] = [
        ("per_page", max(1, min(per_page, 100))),
        ("q_organization_domains_list[]", domain),
        ("include_similar_titles", "true"),
    ]
    for title in titles:
        params.append(("person_titles[]", title))
    url = f"{APOLLO_PEOPLE_SEARCH}?{urlencode(params)}"
    req = Request(url, data=b"{}", method="POST", headers={
        "accept": "application/json", "content-type": "application/json",
        "cache-control": "no-cache", "x-api-key": api_key, "User-Agent": USER_AGENT,
    })
    with urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read(2_000_000).decode("utf-8", errors="replace"))
    return {"status": "ok", "people": _compact_people(payload)}


def gather_people(account: dict, personas: list[dict], *, api_key: str | None,
                  searcher=apollo_search_people, per_page: int = 8) -> dict:
    """Resolve contacts for the account, degrading to persona targets w/o a key.

    `searcher(domain, titles, api_key, per_page=...)` is injectable for offline
    tests. Never raises — a failed Apollo call falls back to persona targets.
    """
    company = account.get("company_name") or account.get("company") or ""
    domain = _clean_domain(account.get("domain") or account.get("website") or "")
    titles = _target_titles(personas)
    persona_targets = [{"title": p.get("title"), "priority": p.get("priority") or "unknown",
                        "apollo_titles": p.get("apollo_titles", [])} for p in personas]

    base = {"company_name": company, "domain": domain, "titles_targeted": titles}

    if not api_key:
        return {**base, "source": "local", "people": [], "persona_targets": persona_targets,
                "warnings": ["APOLLO_API_KEY not set — returning persona targets "
                             "(the titles to pursue); no verified contacts."]}
    if not domain:
        return {**base, "source": "local", "people": [], "persona_targets": persona_targets,
                "warnings": ["no domain on the account — cannot search Apollo."]}

    try:
        result = searcher(domain, titles, api_key, per_page=per_page)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        return {**base, "source": "local", "people": [], "persona_targets": persona_targets,
                "warnings": [f"apollo people-search failed, returning persona targets: {exc}"]}

    people = []
    for person in result.get("people", []):
        persona = _match_persona(person.get("title", ""), personas)
        people.append({**person,
                       "persona": persona.get("title") or person.get("title", ""),
                       "persona_priority": persona.get("priority") or "unknown"})
    warnings = [] if people else ["Apollo returned no contacts for the targeted titles."]
    return {**base, "source": "apollo", "people": people,
            "persona_targets": [] if people else persona_targets, "warnings": warnings}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Find contacts in a qualified account.")
    ap.add_argument("--slug", required=True, help="account slug under the artifact root")
    ap.add_argument("--criteria", type=Path, default=Path("icp.criteria.json"),
                    help="ICP file declaring the buying `personas`")
    ap.add_argument("--per-page", type=int, default=8, help="contacts to request from Apollo")
    ap.add_argument("--local", action="store_true", help="force the no-key persona-target path")
    ap.add_argument("--force", action="store_true", help="search even a Reject-tier account")
    args = ap.parse_args(argv)

    acct_dir = gtm_lib.account_dir(args.slug)
    src = acct_dir / "enrich.json"
    account = gtm_lib.read_json(src if src.exists() else (acct_dir / "input.json"))

    score_path = acct_dir / "score.json"
    tier = gtm_lib.read_json(score_path).get("tier") if score_path.exists() else None
    if tier == "Reject" and not args.force:
        out = {"company_name": account.get("company_name"), "tier": tier, "source": "skipped",
               "people": [], "persona_targets": [],
               "warnings": ["tier is Reject — skipped people search (use --force to override)."]}
    else:
        personas = _personas_from_icp(args.criteria)
        api_key = None if args.local else os.environ.get("APOLLO_API_KEY", "").strip() or None
        out = gather_people(account, personas, api_key=api_key, per_page=args.per_page)
        out["tier"] = tier

    path = gtm_lib.write_json(gtm_lib.stage_path(args.slug, "people"), out)
    print(json.dumps({"slug": args.slug, "tier": tier, "source": out.get("source"),
                      "people": len(out.get("people", [])),
                      "persona_targets": len(out.get("persona_targets", [])),
                      "warnings": len(out.get("warnings", [])), "artifact": str(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
