#!/usr/bin/env python3
"""Deep-enrich an account with ICP-relevant *signals* from public sources.

Firmographics (enrich.py) tell you size/industry. Signals tell you *intent*:
a company hiring LangChain engineers is actively closing an AI gap — direct
evidence for an ICP's commercial-urgency / ai-gap dimensions, not a guess.

This script fetches the homepage, careers/jobs pages, public ATS job boards
(Greenhouse / Lever / Ashby), and GitHub repos for an account, then scans them
for the keyword groups the ICP declares. Each group names the scoring
`dimension` it informs, so the detected signals flow straight into classify's
evidence. ATS boards expose structured per-posting text via public JSON APIs —
far more reliable than scraping a `/careers` HTML page — and are where hiring
signals like "LangChain" actually live. Absence is evidence too: "checked job
boards + github, found no AI hiring" legitimately widens an incumbent's ai_gap.

Signal groups come from `icp.criteria.json`:

    "signals": [
      {"key": "ai_hiring", "informs": "commercial_urgency",
       "keywords": ["langchain", "llm", "rag", "vector database"],
       "interpretation": "Hiring AI/LLM talent = feels AI pressure, building in-house."}
    ]

Reads  .gtm/<slug>/enrich.json  (falls back to input.json) for domain/company.
Writes .gtm/<slug>/signals.json

stdlib only. No key required; GITHUB_TOKEN (optional) raises the GitHub rate
limit. All fetches are best-effort and SSRF-guarded — failures degrade to
warnings, never raise.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import socket
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import gtm_lib  # noqa: E402

USER_AGENT = "gtm-icp/0.1 (+https://github.com/knowledge2-ai/gtm-icp)"
GITHUB_SEARCH = "https://api.github.com/search/repositories"
# Pages worth scanning for intent signals, relative to the domain root.
CANDIDATE_PATHS = ["", "/careers", "/jobs", "/company/careers", "/about"]
SNIPPET_RADIUS = 110


# --------------------------------------------------------------------------- #
# Fetching (SSRF-guarded, HTML -> text)
# --------------------------------------------------------------------------- #
def _is_public_url(url: str) -> bool:
    """Only http(s) to a publicly-routable host — blocks SSRF to internal nets."""
    try:
        parts = urlparse(url)
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parts.hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    return True


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = (text.replace("&amp;", "&").replace("&lt;", "<")
                .replace("&gt;", ">").replace("&nbsp;", " ").replace("&#39;", "'"))
    return re.sub(r"\s+", " ", text).strip()


def http_get_text(url: str, timeout: float = 8.0) -> tuple[str | None, str | None]:
    """Return (text, error). Never raises; SSRF-guarded."""
    if not _is_public_url(url):
        return None, f"skipped non-public url: {url}"
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read(2_000_000).decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return None, f"fetch failed {url}: {exc}"
    return _html_to_text(raw), None


def github_repos(company: str, domain: str, timeout: float = 8.0) -> dict:
    """Best-effort GitHub repo metadata for the account. Never raises."""
    query = quote_plus(f'"{company}" OR "{domain}"')
    url = f"{GITHUB_SEARCH}?q={query}&per_page=5&sort=updated"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urlopen(Request(url, headers=headers), timeout=timeout) as resp:
            payload = json.loads(resp.read(1_000_000).decode("utf-8", errors="replace"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return {"status": "warning", "warning": f"github search failed: {exc}", "repositories": []}
    repos = [{
        "name": it.get("full_name"), "url": it.get("html_url"),
        "description": it.get("description") or "", "language": it.get("language") or "",
        "stars": it.get("stargazers_count") or 0, "updated_at": it.get("updated_at"),
    } for it in (payload.get("items") or [])[:5]]
    return {"status": "ok", "repositories": repos}


# --------------------------------------------------------------------------- #
# Hiring boards (public ATS JSON APIs — no key, structured per-posting text)
# --------------------------------------------------------------------------- #
def http_get_json(url: str, timeout: float = 8.0) -> tuple[object | None, str | None]:
    """Return (parsed_json, error). Never raises; SSRF-guarded."""
    if not _is_public_url(url):
        return None, f"skipped non-public url: {url}"
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read(4_000_000).decode("utf-8", errors="replace")), None
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        return None, f"fetch failed {url}: {exc}"


def _board_slugs(company: str, domain: str) -> list[str]:
    """Guess ATS board tokens from the company name and domain (best-effort)."""
    cands = []
    if domain:
        cands.append(domain.split(".")[0])
    if company:
        cands.append(re.sub(r"[^a-z0-9]+", "", company.lower()))
        cands.append(re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-"))
    seen, out = set(), []
    for s in cands:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out[:3]


def _parse_greenhouse(data) -> list[dict]:
    out = []
    for j in (data or {}).get("jobs", []) or []:
        out.append({"title": j.get("title", ""), "url": j.get("absolute_url", ""),
                    "text": f"{j.get('title','')} {_html_to_text(j.get('content','') or '')}"})
    return out


def _parse_lever(data) -> list[dict]:
    out = []
    for j in data or []:
        if not isinstance(j, dict):
            continue
        desc = j.get("descriptionPlain") or _html_to_text(j.get("description", "") or "")
        out.append({"title": j.get("text", ""), "url": j.get("hostedUrl", ""),
                    "text": f"{j.get('text','')} {desc}"})
    return out


def _parse_ashby(data) -> list[dict]:
    out = []
    for j in (data or {}).get("jobs", []) or []:
        desc = j.get("descriptionPlain") or _html_to_text(j.get("descriptionHtml") or j.get("description") or "")
        out.append({"title": j.get("title", ""), "url": j.get("jobUrl") or j.get("applyUrl") or "",
                    "text": f"{j.get('title','')} {desc}"})
    return out


ATS_BOARDS = [
    ("greenhouse", "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", _parse_greenhouse),
    ("lever", "https://api.lever.co/v0/postings/{slug}?mode=json", _parse_lever),
    ("ashby", "https://api.ashbyhq.com/posting-api/job-board/{slug}", _parse_ashby),
]


def hiring_boards(company: str, domain: str, *, fetcher=http_get_json) -> dict:
    """Find the account's public ATS board and return its job postings.

    Tries Greenhouse/Lever/Ashby by guessed slug. A company uses one ATS, so we
    stop at the first board that returns postings. A 404 on a wrong slug is
    expected and silent. Never raises.
    """
    slugs = _board_slugs(company, domain)
    for provider, template, parse in ATS_BOARDS:
        for slug in slugs:
            data, err = fetcher(template.format(slug=slug))
            if err:
                continue
            postings = parse(data)
            if postings:
                return {"status": "ok", "provider": provider, "board_slug": slug,
                        "postings": postings[:25]}
    return {"status": "not_found", "provider": None, "board_slug": None, "postings": [],
            "note": "no public Greenhouse/Lever/Ashby board matched slugs: " + ", ".join(slugs)}


# --------------------------------------------------------------------------- #
# Keyword scanning
# --------------------------------------------------------------------------- #
def scan_text(text: str, keywords: list[str]) -> list[tuple[str, str]]:
    """Return (keyword, snippet) for each keyword found (word-boundary, case-insensitive)."""
    hits, low = [], text.lower()
    for kw in keywords:
        m = re.search(r"\b" + re.escape(kw.lower()) + r"\b", low)
        if not m:
            continue
        start = max(0, m.start() - SNIPPET_RADIUS)
        end = min(len(text), m.end() + SNIPPET_RADIUS)
        snippet = re.sub(r"\s+", " ", text[start:end]).strip()
        hits.append((kw, ("…" + snippet + "…") if snippet else kw))
    return hits


def gather_signals(account: dict, signal_groups: list[dict], *,
                   fetcher=http_get_text, gh=github_repos, boards=hiring_boards) -> dict:
    """Fetch public sources for the account and detect ICP signal keywords.

    `fetcher(url) -> (text, error)`, `gh(company, domain) -> {...}`, and
    `boards(company, domain) -> {...}` are injectable so this runs fully offline
    under test.
    """
    company = account.get("company_name") or account.get("company") or ""
    domain = (account.get("domain") or account.get("website") or "").replace(
        "https://", "").replace("http://", "").strip("/")
    warnings: list[str] = []

    # 1. Collect text per source URL.
    urls: list[str] = []
    if domain:
        urls += [f"https://{domain}{p}" for p in CANDIDATE_PATHS]
    # Any careers/source URLs the discover/enrich step already found.
    for key in ("careers_urls", "source_url", "linkedin_urls"):
        val = account.get(key)
        urls += val if isinstance(val, list) else ([val] if isinstance(val, str) else [])
    seen, source_texts = set(), []
    for url in urls:
        if not url or url in seen:
            continue
        seen.add(url)
        text, err = fetcher(url)
        if err:
            warnings.append(err)
        if text:
            source_texts.append((url, text))

    # 2. GitHub repos -> a synthetic text blob (name + description + language).
    gh_result = gh(company, domain) if (company or domain) else {"status": "skipped", "repositories": []}
    if gh_result.get("warning"):
        warnings.append(gh_result["warning"])
    for repo in gh_result.get("repositories", []):
        blob = f"{repo.get('name','')} {repo.get('description','')} {repo.get('language','')}"
        source_texts.append((f"github:{repo.get('name') or 'repo'}", blob))

    # 2c. Public ATS job board -> one rich text source per posting.
    boards_result = boards(company, domain) if (company or domain) else {"status": "skipped", "postings": []}
    if boards_result.get("note"):
        warnings.append(boards_result["note"])
    provider = boards_result.get("provider")
    for post in boards_result.get("postings", []):
        title = (post.get("title") or "role")[:50]
        source_texts.append((f"hiring:{provider}:{title}", post.get("text", "")))

    # 3. Scan every source against every signal group.
    detected = []
    for group in signal_groups:
        keywords = group.get("keywords", [])
        evidence, matched = [], set()
        for source, text in source_texts:
            for kw, snippet in scan_text(text, keywords):
                matched.add(kw)
                evidence.append({"source": source, "keyword": kw, "snippet": snippet})
        detected.append({
            "key": group.get("key"),
            "informs": group.get("informs"),
            "interpretation": group.get("interpretation", ""),
            "found": bool(matched),
            "matched_keywords": sorted(matched),
            "evidence": evidence[:8],
        })

    return {
        "company_name": company,
        "domain": domain,
        "sources_checked": [u for u, _ in source_texts],
        "signals_detected": detected,
        "hiring_boards": {
            "status": boards_result.get("status"),
            "provider": provider,
            "board_slug": boards_result.get("board_slug"),
            "postings": [{"title": p.get("title"), "url": p.get("url")}
                         for p in boards_result.get("postings", [])],
        },
        "github": gh_result,
        "warnings": warnings,
    }


def _load_signal_groups(criteria_path: Path) -> list[dict]:
    if not criteria_path.exists():
        return []
    return gtm_lib.read_json(criteria_path).get("signals", []) or []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Collect ICP signals for an account.")
    ap.add_argument("--slug", required=True, help="account slug under the artifact root")
    ap.add_argument("--criteria", type=Path, default=Path("icp.criteria.json"),
                    help="ICP file declaring the `signals` keyword groups")
    args = ap.parse_args(argv)

    acct_dir = gtm_lib.account_dir(args.slug)
    enrich_path = acct_dir / "enrich.json"
    src = enrich_path if enrich_path.exists() else (acct_dir / "input.json")
    account = gtm_lib.read_json(src)

    groups = _load_signal_groups(args.criteria)
    if not groups:
        out = {"company_name": account.get("company_name"), "signals_detected": [],
               "warnings": ["no `signals` groups declared in ICP; nothing to scan"]}
    else:
        out = gather_signals(account, groups)

    path = gtm_lib.write_json(gtm_lib.stage_path(args.slug, "signals"), out)
    found = [s["key"] for s in out.get("signals_detected", []) if s.get("found")]
    board = out.get("hiring_boards", {})
    print(json.dumps({"slug": args.slug, "signals_found": found,
                      "sources": len(out.get("sources_checked", [])),
                      "hiring_board": board.get("provider"),
                      "postings": len(board.get("postings", [])),
                      "warnings": len(out.get("warnings", [])), "artifact": str(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
