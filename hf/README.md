---
license: cc-by-4.0
pretty_name: Company career boards by ATS
language:
- en
size_categories:
- n<1K
tags:
- jobs
- job-boards
- ats
- careers
- recruiting
- greenhouse
- lever
- ashby
- workable
- personio
- recruitee
- smartrecruiters
- workday
configs:
- config_name: default
  data_files:
  - split: train
    path: boards.csv
---
# Company career boards by ATS (open data, CC BY 4.0)

488 public job boards on eight applicant tracking systems, with the slug you
need to call each system's public job-board endpoint. Every board answered with at
least one open job when we checked it on 2026-11-23 (Greenhouse, Lever, Ashby, Workable, Personio, Recruitee) and 2026-11-24 (SmartRecruiters, Workday).

| ATS | Boards | Open jobs at check | Endpoint pattern |
|---|---:|---:|---|
| Greenhouse | 168 | 25,634 | `boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true&pay_transparency=true` |
| Ashby | 120 | 7,856 | `api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true` |
| Personio | 45 | 927 | `{slug}.jobs.personio.de/xml?language=en` |
| Lever | 40 | 3,715 | `api.lever.co/v0/postings/{slug}?mode=json` |
| SmartRecruiters | 33 | 18,687 | `api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100` |
| Recruitee | 28 | 734 | `{slug}.recruitee.com/api/offers/` |
| Workday | 28 | 42,229 | `POST {tenant}.{wdN}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` |
| Workable | 26 | 396 | `www.workable.com/api/accounts/{slug}?details=true` |
| **Total** | **488** | **100,178** | |

## Files

- `boards.csv` and `boards.json` (same rows; JSON is an array of objects).
- Columns: `ats`, `slug`, `company`, `board_url`, `live_checked_at`,
  `open_jobs_at_check`, `api_url`, `api_method`.
  - `board_url` is the company's public career page on that system; `api_url` is the
    board's public endpoint (the pattern above with the slug filled in).
  - `api_method` is `GET` for every system except Workday, whose `api_url` takes a
    `POST` with `Content-Type: application/json` and the body
    `{"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}` (page with
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

- Greenhouse, Lever, Ashby, Workable, Personio, Recruitee: 2,265 candidate (system, slug) pairs, each
  requested once on 2026-11-23. A board was kept only if it answered with at least one open
  job; boards that were missing (404), failed, or listed zero jobs were dropped.
  Where two slugs on one system returned the same company with the same job count,
  one was kept.
- SmartRecruiters: 323 candidate company identifiers, each requested once on
  2026-11-24; the 33 that listed at least one open job were kept (SmartRecruiters
  answers an unknown company with an empty list).
- Workday: 34 candidate career sites (tenant, wdN, site), each checked with a
  search request on 2026-11-24; 28 were kept. Four were missing (HTTP 422 or
  404) and two small sites that answered with 5 and 6 jobs were left out.

Company names come from the feed itself on Greenhouse, Workable, Recruitee and
SmartRecruiters. On Lever, Ashby and Personio, whose feeds carry no company name, our
candidate name was kept only if it appears in the board's own job text; otherwise the
name is the slug (6 boards). Workday's search feed carries no company name
either; there the name is our own candidate name for the site.

## Limits

- A snapshot, not a live feed: boards close, move and change size. Re-check before
  relying on a row.
- A curated starting set, not a census: each system hosts many thousands of boards.
- No Oracle or other systems beyond the eight above.
- We checked each board through its endpoint, not `board_url`; the career-page link
  is built from the same slug and was not fetched separately.

## Using it

Call the endpoints yourself (be gentle: about one request per second; Workable,
Recruitee and Personio throttle bursts for roughly 30 minutes), or paste slugs into
the Apify actor we built for this, which normalises all eight systems into one record
format: https://apify.com/improved_gravity_qb7/greenhouse-lever-ashby-personio-jobs-scraper
($0.003 per job returned; disclosure: we built and sell it).

## Licence and attribution

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Credit it as:

> Company career boards by ATS (ats-career-boards), from the makers of the career-site-jobs Apify actor, https://apify.com/improved_gravity_qb7/greenhouse-lever-ashby-personio-jobs-scraper, licensed CC BY 4.0.
