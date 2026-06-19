#!/usr/bin/env bash
# Offline test for signals.py — keyword detection over injected page text, no network.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SIGNALS="$HERE/../signals.py"

fail() { echo "FAIL: $1" >&2; exit 1; }

# Drive gather_signals() directly with an injected fetcher (no network, no key).
python3 - "$SIGNALS" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("signals", sys.argv[1])
signals = importlib.util.module_from_spec(spec); spec.loader.exec_module(signals)

# The careers page embeds a real Greenhouse board link with a slug we could NOT
# guess from the name ("incumbent" -> board token "incumbent-hq").
PAGES = {
    "https://incumbent.example/": "<html><body>Fleet dispatch and work order software with an open API.</body></html>",
    "https://incumbent.example/careers": '<html><body>Join us — <a href="https://boards.greenhouse.io/incumbenthq">see open roles</a>.</body></html>',
}
def fake_fetch(url):
    if url not in PAGES:
        return (None, [], f"fetch failed {url}")
    html = PAGES[url]
    return (signals._html_to_text(html), signals._extract_ats_refs(html), None)
def fake_gh(company, domain):
    return {"status": "ok", "repositories": [
        {"name": "incumbent/sdk", "description": "Java client for our dispatch API", "language": "Java", "stars": 3}]}
# Hiring signal comes from a public ATS board posting. The board is only reachable
# via the slug discovered on the careers page, so assert `discovered` is honored.
def fake_boards(company, domain, *, discovered=None):
    refs = discovered or []
    assert any(r["provider"] == "greenhouse" and r["slug"] == "incumbenthq" for r in refs), \
        f"careers-page slug should reach hiring_boards, got {refs}"
    return {"status": "ok", "provider": "greenhouse", "board_slug": "incumbenthq",
            "discovery": "careers-link", "postings": [
        {"title": "Senior Machine Learning Engineer", "url": "https://boards.greenhouse.io/incumbenthq/jobs/1",
         "text": "Senior Machine Learning Engineer — build our LLM features with LangChain and a vector database."}]}

ICP_SIGNALS = [
  {"key": "ai_hiring", "informs": "commercial_urgency",
   "keywords": ["langchain", "llm", "vector database", "machine learning engineer"]},
  {"key": "ai_product_surface", "informs": "ai_gap",
   "keywords": ["ai assistant", "gpt", "ai agent"]},
  {"key": "workflow_data_surface", "informs": "data_workflow_moat",
   "keywords": ["api", "work order", "dispatch"]},
]
account = {"company_name": "Incumbent", "domain": "incumbent.example"}
out = signals.gather_signals(account, ICP_SIGNALS, fetcher=fake_fetch, gh=fake_gh, boards=fake_boards)

by = {s["key"]: s for s in out["signals_detected"]}

# ai_hiring must fire on the ATS job posting and map to commercial_urgency.
ai = by["ai_hiring"]
assert ai["found"], "ai_hiring should be detected"
assert ai["informs"] == "commercial_urgency", ai["informs"]
assert "langchain" in ai["matched_keywords"], ai["matched_keywords"]
assert "machine learning engineer" in ai["matched_keywords"], ai["matched_keywords"]
assert any(e["source"].startswith("hiring:greenhouse:") for e in ai["evidence"]), \
    "evidence should cite the ATS job posting"

# The hiring board provider/slug are surfaced for the GTM rep, with provenance.
assert out["hiring_boards"]["provider"] == "greenhouse", out["hiring_boards"]
assert out["hiring_boards"]["board_slug"] == "incumbenthq", out["hiring_boards"]
assert out["hiring_boards"]["discovery"] == "careers-link", out["hiring_boards"]
assert out["hiring_boards"]["postings"][0]["url"].startswith("https://boards.greenhouse.io/"), out["hiring_boards"]

# ATS-link extraction handles the embed form and rejects the stop-word slug.
refs = signals._extract_ats_refs(
    '<a href="https://boards.greenhouse.io/embed/job_board?for=acmeco">x</a>'
    '<a href="https://jobs.lever.co/acme-eng">y</a>')
assert {"provider": "greenhouse", "slug": "acmeco"} in refs, refs
assert {"provider": "lever", "slug": "acme-eng"} in refs, refs
assert all(r["slug"] not in signals._ATS_SLUG_STOP for r in refs), refs

# _filter_repos keeps only repos owned by the account, drops forks + name-mentions,
# and ranks survivors by stars.
RAW = [
    {"full_name": "incumbent/dispatch", "owner": {"login": "incumbent"},
     "fork": False, "homepage": "", "stargazers_count": 12},
    {"full_name": "randos/awesome-incumbent-list", "owner": {"login": "randos"},
     "fork": False, "homepage": "", "stargazers_count": 9000},   # name-mention, wrong owner
    {"full_name": "someone/incumbent-fork", "owner": {"login": "incumbent"},
     "fork": True, "homepage": "", "stargazers_count": 50},        # fork of our org -> drop
    {"full_name": "contrib/plugin", "owner": {"login": "contrib"},
     "fork": False, "homepage": "https://incumbent.example/docs", "stargazers_count": 4},
]
kept = signals._filter_repos(RAW, "Incumbent", "incumbent.example")
names = [r["full_name"] for r in kept]
assert "incumbent/dispatch" in names, names           # owner match
assert "contrib/plugin" in names, names                # homepage match
assert "randos/awesome-incumbent-list" not in names, names  # noisy name-mention dropped
assert "someone/incumbent-fork" not in names, names    # fork dropped
assert names[0] == "incumbent/dispatch", names         # ranked by stars (12 > 4)

# ai_product_surface keywords are absent -> found is False (absence is evidence).
assert by["ai_product_surface"]["found"] is False, "ai_product_surface should not fire"

# workflow_data_surface fires from both the homepage and the github repo blob.
wf = by["workflow_data_surface"]
assert wf["found"] and wf["informs"] == "data_workflow_moat"
assert any(e["source"].startswith("github:") for e in wf["evidence"]), "github repo should be scanned"

# --- Recency: publish dates flow from sources onto evidence (for personalize). ---
# Date parsers normalize each ATS provider's native field (+ epoch ms / RFC 2822).
assert signals._parse_greenhouse({"jobs": [{"title": "ML Eng", "updated_at": "2026-05-01T10:00:00-04:00",
    "content": "LangChain"}]})[0]["published_at"] == "2026-05-01", "greenhouse updated_at"
assert signals._parse_lever([{"text": "ML Eng", "createdAt": 1777593600000,
    "descriptionPlain": "LangChain"}])[0]["published_at"] == "2026-05-01", "lever epoch ms"
assert signals._parse_ashby({"jobs": [{"title": "ML Eng", "publishedDate": "2026-05-01",
    "descriptionPlain": "LangChain"}]})[0]["published_at"] == "2026-05-01", "ashby publishedDate"
assert signals._to_iso_date("Thu, 01 May 2026 10:00:00 GMT") == "2026-05-01", "RFC 2822 Last-Modified"
assert signals._to_iso_date(None) is None and signals._to_iso_date("") is None, "undated stays neutral"

# A dated page (meta tag) + a 4-tuple fetcher -> evidence carries published_at;
# the older 3-tuple fetcher path stays valid (no date).
DATED = {"https://fresh.example": '<html><head>'
         '<meta property="article:published_time" content="2026-06-01">'
         '</head><body>We ship dispatch workflow software with an open API.</body></html>'}
def dated_fetch(url):
    html = DATED.get(url)
    if not html:
        return (None, [], None, f"fetch failed {url}")
    return (signals._html_to_text(html), signals._extract_ats_refs(html),
            signals._html_published_date(html), None)
no_boards = lambda c, d, *, discovered=None: {"status": "not_found", "provider": None, "postings": []}
no_gh = lambda c, d: {"status": "skipped", "repositories": []}
dout = signals.gather_signals({"company_name": "Fresh", "domain": "fresh.example"},
    [{"key": "workflow_data_surface", "informs": "data_workflow_moat", "keywords": ["dispatch", "api"]}],
    fetcher=dated_fetch, gh=no_gh, boards=no_boards)
dated_ev = dout["signals_detected"][0]["evidence"]
assert dated_ev and all(e.get("published_at") == "2026-06-01" for e in dated_ev), dated_ev

print("OK: ai_hiring->commercial_urgency, absence handled, github scanned, recency dates captured")
PY

echo "PASS test_signals.sh"
