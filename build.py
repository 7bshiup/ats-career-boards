#!/usr/bin/env python3
"""Regenerate the ats-career-boards open-data files from the actor's verified
directory (project-b/apify-jobs-actor/jobs_actor/directory.json).

    python3 build.py             # write boards.csv, boards.json, README.md, hf/README.md, LICENSE
    python3 build.py --check     # rebuild in memory, verify, and fail if any file on disk differs
    python3 build.py --source PATH/directory.json

Standard library only. When the actor's jobs_actor package sits next to this
folder (as in the Recede repo), --check also confirms the endpoint templates
equal core.ENDPOINTS, Workday URLs and page size equal core's, and that every
board_url and api_url parses back to its (ats, slug) with core.parse_company.
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import os
import re
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ACTOR_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "apify-jobs-actor"))
DEFAULT_SOURCE = os.path.join(ACTOR_DIR, "jobs_actor", "directory.json")

ACTOR_URL = "https://apify.com/improved_gravity_qb7/greenhouse-lever-ashby-personio-jobs-scraper"
ATTRIBUTION = ("Company career boards by ATS (ats-career-boards), from the makers of the "
               "career-site-jobs Apify actor, " + ACTOR_URL + ", licensed CC BY 4.0.")

# From the check logs, not derivable from directory.json: 2026-11-23 results.jsonl and
# names.jsonl (six systems); 2026-11-24 SmartRecruiters probe results (res1-5.json, 323 names)
# and Workday search results (verify1.json, 31 sites, plus 3 sites read while building the reader).
CANDIDATES_CHECKED = 2265
NAMES_FROM_SLUG = 6
SR_CANDIDATES = 323
WORKDAY_CANDIDATES = 34

SYSTEMS = ("greenhouse", "lever", "ashby", "workable", "personio", "recruitee", "smartrecruiters", "workday")
LABELS = {"greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby",
          "workable": "Workable", "personio": "Personio", "recruitee": "Recruitee",
          "smartrecruiters": "SmartRecruiters", "workday": "Workday"}
NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
# Public job-board GET endpoints; must equal jobs_actor/core.py ENDPOINTS (Workday is a POST, below).
ENDPOINTS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true&pay_transparency=true",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true",
    "workable": "https://www.workable.com/api/accounts/{slug}?details=true",
    "personio": "https://{slug}.jobs.personio.de/xml?language=en",
    "recruitee": "https://{slug}.recruitee.com/api/offers/",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100",
}
# Workday: slug is 'tenant/wdN/site'; the career site's own search endpoint takes a JSON POST
# (core._workday_urls and core.read_workday; Workday answers HTTP 400 to a limit above 20).
WORKDAY_API = "https://{tenant}.{wdN}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
WORKDAY_BODY = '{"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}'
WORKDAY_SLUG = re.compile(r"([a-z0-9-]+)/(wd\d+)/([A-Za-z0-9_-]+)")
# Human-facing career page for each board.
BOARD_URLS = {
    "greenhouse": "https://job-boards.greenhouse.io/{slug}",
    "lever": "https://jobs.lever.co/{slug}",
    "ashby": "https://jobs.ashbyhq.com/{slug}",
    "workable": "https://apply.workable.com/{slug}/",
    "personio": "https://{slug}.jobs.personio.de/",
    "recruitee": "https://{slug}.recruitee.com/",
    "smartrecruiters": "https://jobs.smartrecruiters.com/{slug}",
    "workday": "https://{tenant}.{wdN}.myworkdayjobs.com/{site}",
}
SUBDOMAIN = {"personio", "recruitee"}
COLUMNS = ("ats", "slug", "company", "board_url", "live_checked_at", "open_jobs_at_check", "api_url",
           "api_method")
DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


def urls(system: str, slug: str) -> tuple[str, str, str]:
    """(board_url, api_url, api_method) of one board."""
    if system == "workday":
        tenant, wd, site = slug.split("/")
        parts = {"tenant": tenant, "wdN": wd, "site": site}
        return BOARD_URLS[system].format(**parts), WORKDAY_API.format(**parts), "POST"
    quoted = urllib.parse.quote(slug, safe="")
    return BOARD_URLS[system].format(slug=quoted), ENDPOINTS[system].format(slug=quoted), "GET"


def load(source: str) -> tuple[str, list[dict]]:
    with open(source, encoding="utf-8") as fh:
        data = json.load(fh)
    return data["verified"], data["boards"]


def to_rows(boards: list[dict]) -> list[dict]:
    rows = []
    for b in boards:
        slug = b["board"]
        board_url, api_url, api_method = urls(b["system"], slug)
        rows.append({
            "ats": b["system"],
            "slug": slug,
            "company": b["company"],
            "board_url": board_url,
            "live_checked_at": b["verified"],
            "open_jobs_at_check": int(b["jobs"]),
            "api_url": api_url,
            "api_method": api_method,
        })
    order = {s: i for i, s in enumerate(SYSTEMS)}
    rows.sort(key=lambda r: (order[r["ats"]], r["slug"]))
    return rows


def render_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def render_json(rows: list[dict]) -> str:
    return "[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n]\n"


def fmt(n: int) -> str:
    return f"{n:,}"


def stats(rows: list[dict]) -> dict:
    by = collections.Counter(r["ats"] for r in rows)
    jobs = collections.Counter()
    dates = collections.defaultdict(list)  # check date -> systems checked that day
    for r in rows:
        jobs[r["ats"]] += r["open_jobs_at_check"]
        if LABELS[r["ats"]] not in dates[r["live_checked_at"]]:
            dates[r["live_checked_at"]].append(LABELS[r["ats"]])
    return {"boards": by, "jobs": jobs, "total": len(rows), "total_jobs": sum(jobs.values()),
            "dates": dict(sorted(dates.items()))}


def checked_on(st: dict) -> str:
    if len(st["dates"]) == 1:
        return "on " + next(iter(st["dates"]))
    return "on " + " and ".join(f"{d} ({', '.join(s)})" for d, s in st["dates"].items())


def table(st: dict) -> str:
    lines = ["| ATS | Boards | Open jobs at check | Endpoint pattern |", "|---|---:|---:|---|"]
    for s in sorted(SYSTEMS, key=lambda s: (-st["boards"][s], s)):
        pattern = ("POST " + WORKDAY_API if s == "workday" else ENDPOINTS[s]).replace("https://", "")
        lines.append(f"| {LABELS[s]} | {fmt(st['boards'][s])} | {fmt(st['jobs'][s])} | `{pattern}` |")
    lines.append(f"| **Total** | **{fmt(st['total'])}** | **{fmt(st['total_jobs'])}** | |")
    return "\n".join(lines)


def body(st: dict) -> str:
    first = st["dates"][min(st["dates"])]
    day = {label: d for d, labels in st["dates"].items() for label in labels}
    return f"""# Company career boards by ATS (open data, CC BY 4.0)

{fmt(st['total'])} public job boards on {NUMBER_WORDS[len(SYSTEMS)]} applicant tracking systems, with the slug you
need to call each system's public job-board endpoint. Every board answered with at
least one open job when we checked it {checked_on(st)}.

{table(st)}

## Files

- `boards.csv` and `boards.json` (same rows; JSON is an array of objects).
- Columns: `ats`, `slug`, `company`, `board_url`, `live_checked_at`,
  `open_jobs_at_check`, `api_url`, `api_method`.
  - `board_url` is the company's public career page on that system; `api_url` is the
    board's public endpoint (the pattern above with the slug filled in).
  - `api_method` is `GET` for every system except Workday, whose `api_url` takes a
    `POST` with `Content-Type: application/json` and the body
    `{WORKDAY_BODY}` (page with
    `offset`; Workday answers HTTP 400 to a `limit` above 20). A Workday `slug` is
    `tenant/wdN/site`, the three parts of its career-site address.
  - `open_jobs_at_check` is the number of open jobs the endpoint returned on
    `live_checked_at` (UTC date); on SmartRecruiters and Workday it is the total the
    first page reports.
- `build.py` regenerates every file from our source list and verifies it
  (`python3 build.py --check`).

## How it was built

We compiled every candidate ourselves and checked each one through its public
endpoint, at most one request per second. No third-party directory or web-crawl
list was used.

- {', '.join(first)}: {fmt(CANDIDATES_CHECKED)} candidate (system, slug) pairs, each
  requested once on {min(st['dates'])}. A board was kept only if it answered with at least one open
  job; boards that were missing (404), failed, or listed zero jobs were dropped.
  Where two slugs on one system returned the same company with the same job count,
  one was kept.
- SmartRecruiters: {fmt(SR_CANDIDATES)} candidate company identifiers, each requested once on
  {day['SmartRecruiters']}; the {st['boards']['smartrecruiters']} that listed at least one open job were kept (SmartRecruiters
  answers an unknown company with an empty list).
- Workday: {fmt(WORKDAY_CANDIDATES)} candidate career sites (tenant, wdN, site), each checked with a
  search request on {day['Workday']}; {st['boards']['workday']} were kept. Four were missing (HTTP 422 or
  404) and two small sites that answered with 5 and 6 jobs were left out.

Company names come from the feed itself on Greenhouse, Workable, Recruitee and
SmartRecruiters. On Lever, Ashby and Personio, whose feeds carry no company name, our
candidate name was kept only if it appears in the board's own job text; otherwise the
name is the slug ({NAMES_FROM_SLUG} boards). Workday's search feed carries no company name
either; there the name is our own candidate name for the site.

## Limits

- A snapshot, not a live feed: boards close, move and change size. Re-check before
  relying on a row.
- A curated starting set, not a census: each system hosts many thousands of boards.
- No Oracle or other systems beyond the {NUMBER_WORDS[len(SYSTEMS)]} above.
- We checked each board through its endpoint, not `board_url`; the career-page link
  is built from the same slug and was not fetched separately.

## Using it

Call the endpoints yourself (be gentle: about one request per second; Workable,
Recruitee and Personio throttle bursts for roughly 30 minutes), or paste slugs into
the Apify actor we built for this, which normalises all {NUMBER_WORDS[len(SYSTEMS)]} systems into one record
format: {ACTOR_URL}
($0.003 per job returned; disclosure: we built and sell it).

## Licence and attribution

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Credit it as:

> {ATTRIBUTION}
"""


DRAFT = ""  # released 24 Nov 2026 on the owner's instruction


def render_readme(st: dict) -> str:
    return DRAFT + body(st)


def render_card(st: dict) -> str:
    tags = ["jobs", "job-boards", "ats", "careers", "recruiting"] + list(SYSTEMS)
    front = "\n".join([
        "---",
        "license: cc-by-4.0",
        "pretty_name: Company career boards by ATS",
        "language:",
        "- en",
        "size_categories:",
        "- n<1K",
        "tags:",
        *[f"- {t}" for t in tags],
        "configs:",
        "- config_name: default",
        "  data_files:",
        "  - split: train",
        "    path: boards.csv",
        "---",
        "",
    ])
    return front + DRAFT + body(st)


def render_license() -> str:
    return f"""The data in this repository (boards.csv, boards.json) is licensed under the
Creative Commons Attribution 4.0 International licence (CC BY 4.0).

Full legal text: https://creativecommons.org/licenses/by/4.0/legalcode
Summary:         https://creativecommons.org/licenses/by/4.0/

Attribution line to use when you share or adapt the data:

  {ATTRIBUTION}

build.py is provided under the same terms.
"""


def build(source: str) -> tuple[dict[str, str], list[dict], list[dict], str]:
    checked, boards = load(source)
    rows = to_rows(boards)
    st = stats(rows)
    files = {
        "boards.csv": render_csv(rows),
        "boards.json": render_json(rows),
        "README.md": render_readme(st),
        os.path.join("hf", "README.md"): render_card(st),
        "LICENSE": render_license(),
    }
    return files, rows, boards, checked


def verify(files: dict[str, str], rows: list[dict], boards: list[dict]) -> list[str]:
    errs = []
    # Counts per system equal the source directory.
    src = collections.Counter(b["system"] for b in boards)
    got = collections.Counter(r["ats"] for r in rows)
    if src != got or len(rows) != len(boards):
        errs.append(f"counts differ: source {dict(src)} vs rows {dict(got)}")
    # No duplicates: (ats, slug) and board_url.
    for key in (lambda r: (r["ats"], r["slug"].lower()), lambda r: r["board_url"].lower()):
        dup = [k for k, n in collections.Counter(map(key, rows)).items() if n > 1]
        if dup:
            errs.append(f"duplicates: {dup[:5]}")
    # Well-formed URLs per system.
    for r in rows:
        s, slug = r["ats"], r["slug"]
        if s in SUBDOMAIN and not DNS_LABEL.fullmatch(slug):
            errs.append(f"{s}:{slug} is not a valid host label")
        if s == "workday":
            m = WORKDAY_SLUG.fullmatch(slug)
            if not (m and DNS_LABEL.fullmatch(m.group(1))):
                errs.append(f"{s}:{slug} is not tenant/wdN/site")
                continue
        want = dict(zip(("board_url", "api_url", "api_method"), urls(s, slug)))
        for col in ("board_url", "api_url"):
            u = urllib.parse.urlsplit(r[col])
            if u.scheme != "https" or not u.netloc or r[col] != want[col]:
                errs.append(f"{s}:{slug} bad {col}: {r[col]}")
        if r["api_method"] != ("POST" if s == "workday" else "GET") or r["api_method"] != want["api_method"]:
            errs.append(f"{s}:{slug} bad api_method: {r['api_method']}")
        if not (r["company"].strip() and r["open_jobs_at_check"] >= 1
                and re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["live_checked_at"])):
            errs.append(f"{s}:{slug} bad row: {r}")
    # CSV and JSON round-trip to the same rows.
    back = list(csv.DictReader(io.StringIO(files["boards.csv"])))
    for row in back:
        row["open_jobs_at_check"] = int(row["open_jobs_at_check"])
    if back != rows:
        errs.append("boards.csv does not round-trip")
    if json.loads(files["boards.json"]) != rows:
        errs.append("boards.json does not round-trip")
    # README counts equal the rows.
    for name in ("README.md", os.path.join("hf", "README.md")):
        for s in SYSTEMS:
            if f"| {LABELS[s]} | {fmt(got[s])} |" not in files[name]:
                errs.append(f"{name}: count for {s} missing")
        if "DRAFT: not released" in files[name]:
            errs.append(f"{name}: draft marker still present")
        if WORKDAY_BODY not in files[name]:
            errs.append(f"{name}: Workday POST body missing")
    # Kept boards never exceed the candidates checked.
    if got["smartrecruiters"] > SR_CANDIDATES or got["workday"] > WORKDAY_CANDIDATES \
            or sum(got[s] for s in SYSTEMS[:6]) > CANDIDATES_CHECKED:
        errs.append("more boards than candidates checked")
    # Against the actor's own code when it is present.
    if os.path.isdir(os.path.join(ACTOR_DIR, "jobs_actor")):
        sys.path.insert(0, ACTOR_DIR)
        from jobs_actor import core  # noqa: E402
        if core.ENDPOINTS != ENDPOINTS:
            errs.append("ENDPOINTS differ from jobs_actor/core.py")
        if json.loads(WORKDAY_BODY) != {"appliedFacets": {}, "limit": core.WORKDAY_PAGE, "offset": 0,
                                        "searchText": ""}:
            errs.append("WORKDAY_BODY differs from core.read_workday's search body")
        for r in rows:
            for col in ("board_url", "api_url"):
                try:
                    parsed = core.parse_company(r[col])
                except ValueError as e:
                    parsed = str(e)
                if parsed != (r["ats"], r["slug"]):
                    errs.append(f"core.parse_company({r[col]}) -> {parsed}")
            if r["ats"] == "workday":
                try:
                    site, api = core._workday_urls(r["slug"])
                except ValueError as e:
                    site, api = str(e), ""
                if (site, api + "/jobs") != (r["board_url"], r["api_url"]):
                    errs.append(f"core._workday_urls({r['slug']}) -> {site}, {api}")
    else:
        print("note: jobs_actor not found; skipped core.ENDPOINTS / parse_company checks", file=sys.stderr)
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", default=DEFAULT_SOURCE, help="directory.json to build from")
    ap.add_argument("--check", action="store_true", help="verify; do not write")
    args = ap.parse_args()
    files, rows, boards, _ = build(args.source)
    errs = verify(files, rows, boards)
    if args.check:
        for name, text in files.items():
            path = os.path.join(HERE, name)
            if not os.path.exists(path) or open(path, encoding="utf-8").read() != text:
                errs.append(f"{name} is stale: run python3 build.py")
    else:
        for name, text in files.items():
            path = os.path.join(HERE, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
    st = stats(rows)
    print(f"{st['total']} boards, {st['total_jobs']} open jobs at check {', '.join(st['dates'])}: "
          + ", ".join(f"{s} {st['boards'][s]}" for s in SYSTEMS))
    for e in errs:
        print("FAIL", e, file=sys.stderr)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
