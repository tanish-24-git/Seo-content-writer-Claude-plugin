#!/usr/bin/env python3
"""Page-level authority + visibility for every page in a run, from Ahrefs API v3.

    python fetch_ahrefs.py <run_dir> [--country in] [--keywords 20]   # REST, needs AHREFS_API_KEY
    python fetch_ahrefs.py <run_dir> --assemble                        # build from saved raw responses

Writes <run_dir>/authority.json. Two ways to get the raw data, one parser:

1. REST: with AHREFS_API_KEY set, this script calls api.ahrefs.com/v3 itself.
2. Ahrefs MCP connector (no key): Claude calls the connector tools and saves each
   JSON response as <run_dir>/_cache/ahrefs/<n>__<endpoint>.json, where <n> is the
   page's index in `--list` output and <endpoint> is one of ENDPOINTS below; then
   runs this script with --assemble.

Per page (mode=exact on the URL; domain rating on the host):
  metrics          site-explorer/metrics          org_traffic, org_keywords, org_keywords_1_3
  backlinks        site-explorer/backlinks-stats  live backlinks, live referring domains
  url_rating       site-explorer/url-rating-history  latest URL Rating
  domain_rating    site-explorer/domain-rating    Domain Rating
  keywords         site-explorer/organic-keywords top keywords by traffic

Dates are UTC (Ahrefs rejects a "future" local date). Standard library only.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://api.ahrefs.com/v3"
ENDPOINTS = ("metrics", "backlinks", "url_rating", "domain_rating", "keywords")


def today():
    return datetime.now(timezone.utc).date()


def load_pages(run_dir):
    with open(os.path.join(run_dir, "meta.json"), encoding="utf-8-sig") as fh:
        meta = json.load(fh)
    pages = [(meta.get("your_brand") or "your page", meta.get("your_url"))]
    pages += [(c.get("brand"), c.get("url")) for c in meta.get("competitors") or []]
    return [(b, u) for b, u in pages if u]


def requests_for(url, country, n_kw):
    """(endpoint, api_path, params) for one page — the same params the MCP tools take."""
    d = today().isoformat()
    host = urllib.parse.urlparse(url).netloc
    return [
        ("metrics", "site-explorer/metrics", {"target": url, "mode": "exact", "date": d, "country": country}),
        ("backlinks", "site-explorer/backlinks-stats", {"target": url, "mode": "exact", "date": d}),
        ("url_rating", "site-explorer/url-rating-history",
         {"target": url, "date_from": (today() - timedelta(days=45)).isoformat()}),
        ("domain_rating", "site-explorer/domain-rating", {"target": host, "date": d}),
        ("keywords", "site-explorer/organic-keywords",
         {"target": url, "mode": "exact", "date": d, "country": country, "limit": n_kw,
          "select": "keyword,best_position,volume,sum_traffic", "order_by": "sum_traffic:desc"}),
    ]


def rest_get(path, params, key):
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(f"{BASE}/{path}?{q}", headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"error": f"http {exc.code}: {exc.read().decode('utf-8', 'replace')[:200]}"}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"error": f"{type(exc).__name__}: {exc}"[:200]}


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_page(raw):
    """raw: {endpoint: response_json} -> authority record for one page."""
    rec, errors = {}, {}
    for ep in ENDPOINTS:
        r = raw.get(ep)
        if r is None:
            errors[ep] = "not fetched"
        elif isinstance(r, dict) and r.get("error"):
            errors[ep] = str(r["error"])[:200]
    m = (raw.get("metrics") or {}).get("metrics") or {}
    rec.update(org_traffic=_int(m.get("org_traffic")), org_keywords=_int(m.get("org_keywords")),
               org_keywords_top3=_int(m.get("org_keywords_1_3")))
    b = (raw.get("backlinks") or {}).get("metrics") or {}
    rec.update(backlinks=_int(b.get("live")), refdomains=_int(b.get("live_refdomains")))
    ur = (raw.get("url_rating") or {}).get("url_ratings") or []
    rec["url_rating"] = round(ur[-1]["url_rating"], 1) if ur and isinstance(ur[-1].get("url_rating"), (int, float)) else None
    dr = ((raw.get("domain_rating") or {}).get("domain_rating") or {}).get("domain_rating")
    rec["domain_rating"] = round(dr, 1) if isinstance(dr, (int, float)) else None
    rec["top_keywords"] = [{"keyword": k.get("keyword"), "position": _int(k.get("best_position")),
                            "volume": _int(k.get("volume")), "traffic": _int(k.get("sum_traffic"))}
                           for k in (raw.get("keywords") or {}).get("keywords") or [] if k.get("keyword")]
    if errors:
        rec["errors"] = errors
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_dir")
    ap.add_argument("--country", default="in")
    ap.add_argument("--keywords", type=int, default=20)
    ap.add_argument("--assemble", action="store_true", help="build authority.json from _cache/ahrefs raw files")
    ap.add_argument("--list", action="store_true", help="print the per-page requests (for the MCP route) and exit")
    a = ap.parse_args()
    pages = load_pages(a.run_dir)
    raw_dir = os.path.join(a.run_dir, "_cache", "ahrefs")
    os.makedirs(raw_dir, exist_ok=True)

    if a.list:
        print(json.dumps([{"n": i, "brand": b, "url": u, "requests": [{"endpoint": ep, "api": p, "params": prm}
                          for ep, p, prm in requests_for(u, a.country, a.keywords)]} for i, (b, u) in enumerate(pages)], indent=1))
        return 0

    key = (os.environ.get("AHREFS_API_KEY") or "").strip()
    if not a.assemble:
        if not key:
            print("AHREFS_API_KEY not set. Use the Ahrefs connector route (see --list / --assemble), "
                  "or skip Ahrefs; the report then shows 'Not available yet'.", file=sys.stderr)
            return 2
        for i, (b, u) in enumerate(pages):
            for ep, path, prm in requests_for(u, a.country, a.keywords):
                with open(os.path.join(raw_dir, f"{i}__{ep}.json"), "w", encoding="utf-8") as fh:
                    json.dump(rest_get(path, prm, key), fh)
            print(f"  fetched {b}", file=sys.stderr)

    out_pages = []
    for i, (b, u) in enumerate(pages):
        raw = {}
        for ep in ENDPOINTS:
            p = os.path.join(raw_dir, f"{i}__{ep}.json")
            if os.path.exists(p):
                with open(p, encoding="utf-8-sig") as fh:
                    raw[ep] = json.load(fh)
        out_pages.append({"brand": b, "url": u, **parse_page(raw)})
    got = sum(1 for p in out_pages if p.get("url_rating") is not None or p.get("org_traffic") is not None)
    out = {"source": "Ahrefs API v3 (Site Explorer)", "route": "assemble" if a.assemble else "rest",
           "country": a.country.upper(), "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "pages": out_pages}
    path = os.path.join(a.run_dir, "authority.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"wrote {path} ({got}/{len(pages)} pages with data)")
    return 0 if got else 1


if __name__ == "__main__":
    sys.exit(main())
