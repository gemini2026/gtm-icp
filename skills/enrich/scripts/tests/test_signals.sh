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

PAGES = {
    "https://incumbent.example/": "<html><body>Fleet dispatch and work order software with an open API.</body></html>",
}
def fake_fetch(url):
    return (signals._html_to_text(PAGES[url]) if url in PAGES else None,
            None if url in PAGES else f"fetch failed {url}")
def fake_gh(company, domain):
    return {"status": "ok", "repositories": [
        {"name": "incumbent/sdk", "description": "Java client for our dispatch API", "language": "Java", "stars": 3}]}
# Hiring signal now comes from a public ATS board posting, not a scraped careers page.
def fake_boards(company, domain):
    return {"status": "ok", "provider": "greenhouse", "board_slug": "incumbent", "postings": [
        {"title": "Senior Machine Learning Engineer", "url": "https://boards.greenhouse.io/incumbent/jobs/1",
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

# The hiring board provider/slug are surfaced for the GTM rep.
assert out["hiring_boards"]["provider"] == "greenhouse", out["hiring_boards"]
assert out["hiring_boards"]["postings"][0]["url"].startswith("https://boards.greenhouse.io/"), out["hiring_boards"]

# ai_product_surface keywords are absent -> found is False (absence is evidence).
assert by["ai_product_surface"]["found"] is False, "ai_product_surface should not fire"

# workflow_data_surface fires from both the homepage and the github repo blob.
wf = by["workflow_data_surface"]
assert wf["found"] and wf["informs"] == "data_workflow_moat"
assert any(e["source"].startswith("github:") for e in wf["evidence"]), "github repo should be scanned"

print("OK: ai_hiring->commercial_urgency, absence handled, github scanned")
PY

echo "PASS test_signals.sh"
