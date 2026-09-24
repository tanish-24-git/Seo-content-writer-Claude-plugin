#!/usr/bin/env python3
"""Core Web Vitals for every page in a run, via Google PageSpeed Insights v5.

    python fetch_pagespeed.py <run_dir> [--strategies mobile,desktop] [--workers 4] [--refresh]

Reads meta.json (your_url + competitors[].url) and writes <run_dir>/pagespeed.json:
lab metrics (Lighthouse), real-user field metrics (CrUX p75, 28-day window) when
Chrome has enough traffic for the URL, Lighthouse category scores and the top
failing audits ("fixes") per page and device.

Auth, first match wins (the PSI API itself is free; a credential only lifts quota):
  PSI_API_KEY                 API key from a Google Cloud project with the PSI API enabled
  PSI_SERVICE_ACCOUNT_JSON    path to a service-account key file (needs `google-auth`)
  (none)                      keyless: works, but Google rate-limits it hard

Ported from the SEO platform's PSI adapter: shared token-bucket rate limiter,
retry with Retry-After / jittered exponential backoff on 429/5xx, 7-day disk
cache under <run_dir>/_cache/psi. Standard library only (google-auth optional).
Never raises per page: a failed page/device carries an "error" string instead.
"""
import argparse
import hashlib
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
# The only scope combo PSI accepts from a service account (cloud-platform alone
# returns ACCESS_TOKEN_SCOPE_INSUFFICIENT).
SA_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email"]
CATEGORIES = ("performance", "accessibility", "best-practices", "seo")
RETRYABLE = {429, 500, 502, 503}
CACHE_TTL = 7 * 24 * 3600
TIMEOUT = 120
MAX_RETRIES = 4


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RateLimiter:
    """Token bucket shared by all worker threads: PSI's per-minute quota is the
    real ceiling, so a burst never trips 429."""

    def __init__(self, qps):
        self.qps = max(0.05, float(qps))
        self.cap = max(1.0, self.qps)
        self.tokens = self.cap
        self.at = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(self.cap, self.tokens + (now - self.at) * self.qps)
                self.at = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                wait = (1.0 - self.tokens) / self.qps
            time.sleep(min(wait, 1.0))


class Auth:
    def __init__(self):
        self.key = (os.environ.get("PSI_API_KEY") or "").strip()
        self.sa_path = (os.environ.get("PSI_SERVICE_ACCOUNT_JSON") or "").strip()
        self.creds = None
        self.lock = threading.Lock()
        self.mode = "api_key" if self.key else "keyless"
        if not self.key and self.sa_path:
            if not os.path.isfile(self.sa_path):
                print(f"PSI_SERVICE_ACCOUNT_JSON not found: {self.sa_path} — using keyless mode", file=sys.stderr)
            else:
                try:
                    import google.oauth2.service_account  # noqa: F401
                    self.mode = "service_account"
                except ImportError:
                    print("google-auth not installed (pip install google-auth) — using keyless mode", file=sys.stderr)

    def apply(self, params, headers):
        if self.mode == "api_key":
            params["key"] = self.key
        elif self.mode == "service_account":
            from google.auth.transport.requests import Request
            from google.oauth2 import service_account
            with self.lock:
                if self.creds is None:
                    self.creds = service_account.Credentials.from_service_account_file(self.sa_path, scopes=SA_SCOPES)
                if not self.creds.valid:
                    self.creds.refresh(Request())
                headers["Authorization"] = f"Bearer {self.creds.token}"


def retry_after(raw):
    try:
        return max(0.0, float((raw or "").strip()))
    except ValueError:
        return None


def backoff(attempt, hint):
    exp = min(60.0, 2.0 * (2 ** attempt))
    jit = random.uniform(0.0, exp)
    return min(60.0, max(hint, jit)) if hint is not None else jit


def fetch_raw(url, strategy, auth, limiter):
    """GET one PSI result. Returns (json_dict, error_str)."""
    last = ""
    for attempt in range(MAX_RETRIES + 1):
        params = [("url", url), ("strategy", strategy)] + [("category", c) for c in CATEGORIES]
        extra, headers = {}, {"Accept": "application/json"}
        try:
            auth.apply(extra, headers)
        except Exception as exc:  # noqa: BLE001
            return None, f"auth: {type(exc).__name__}: {exc}"[:300]
        params += list(extra.items())
        req = urllib.request.Request(ENDPOINT + "?" + urllib.parse.urlencode(params), headers=headers)
        limiter.acquire()
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8")), ""
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:300]
            last = f"http {exc.code}: {body}"
            if exc.code in RETRYABLE and attempt < MAX_RETRIES:
                time.sleep(backoff(attempt, retry_after(exc.headers.get("Retry-After"))))
                continue
            return None, last
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = f"network: {type(exc).__name__}: {exc}"
            if attempt < MAX_RETRIES:
                time.sleep(backoff(attempt, None))
                continue
            return None, last[:300]
        except ValueError as exc:
            return None, f"json decode: {exc}"
    return None, (last or "retries exhausted")[:300]


def _num(audits, key, as_int=True):
    v = (audits.get(key) or {}).get("numericValue")
    if isinstance(v, (int, float)):
        return int(round(v)) if as_int else float(v)
    return None


def _crux(metric):
    if not isinstance(metric, dict):
        return None, ""
    p75 = metric.get("percentile")
    return (int(p75) if isinstance(p75, (int, float)) else None), str(metric.get("category") or "")


def parse(data):
    """PSI JSON -> compact record (lab + field + category scores + top fixes)."""
    lh = data.get("lighthouseResult") or {}
    audits = lh.get("audits") or {}
    cats = lh.get("categories") or {}
    rec = {
        "final_url": lh.get("finalDisplayedUrl") or lh.get("finalUrl") or "",
        "lighthouse_version": lh.get("lighthouseVersion") or "",
        "fetch_time": lh.get("fetchTime") or "",
        "runtime_error": (lh.get("runtimeError") or {}).get("message", ""),
        "scores": {c: (round(cats[c]["score"] * 100) if isinstance((cats.get(c) or {}).get("score"), (int, float)) else None)
                   for c in CATEGORIES},
        "lab": {
            "lcp_ms": _num(audits, "largest-contentful-paint"),
            "cls": (round(_num(audits, "cumulative-layout-shift", False), 3)
                    if _num(audits, "cumulative-layout-shift", False) is not None else None),
            "fcp_ms": _num(audits, "first-contentful-paint"),
            "tbt_ms": _num(audits, "total-blocking-time"),
            "si_ms": _num(audits, "speed-index"),
            "tti_ms": _num(audits, "interactive"),
            "ttfb_ms": _num(audits, "server-response-time"),
            "bytes": _num(audits, "total-byte-weight"),
        },
        "field": {"has_data": False},
    }
    fm = (data.get("loadingExperience") or {}).get("metrics") or {}
    if fm:
        f = {"has_data": True, "origin_fallback": bool((data.get("loadingExperience") or {}).get("origin_fallback"))}
        for key, name in (("LARGEST_CONTENTFUL_PAINT_MS", "lcp_ms"), ("INTERACTION_TO_NEXT_PAINT", "inp_ms"),
                          ("FIRST_CONTENTFUL_PAINT_MS", "fcp_ms"), ("EXPERIMENTAL_TIME_TO_FIRST_BYTE", "ttfb_ms")):
            f[name], f[name.split("_")[0] + "_category"] = _crux(fm.get(key))
        cls, cat = _crux(fm.get("CUMULATIVE_LAYOUT_SHIFT_SCORE"))  # CrUX reports CLS x100
        f["cls"], f["cls_category"] = (cls / 100.0 if cls is not None else None), cat
        f["overall_category"] = (data.get("loadingExperience") or {}).get("overall_category", "")
        rec["field"] = f
    fixes = []
    for key, a in audits.items():
        score, mode = a.get("score"), a.get("scoreDisplayMode")
        if score is None or score >= 0.9 or mode not in ("numeric", "binary", "metricSavings"):
            continue
        saving = (a.get("details") or {}).get("overallSavingsMs") or 0
        ms = a.get("metricSavings") or {}
        if not saving and not any(ms.values()) and mode != "binary":
            continue
        fixes.append({"id": key, "title": a.get("title") or key, "display": a.get("displayValue") or "",
                      "savings_ms": int(saving or 0), "metrics": [k for k, v in ms.items() if v]})
    fixes.sort(key=lambda x: (-x["savings_ms"], -len(x["metrics"])))
    rec["fixes"] = fixes[:10]
    return rec


class Cache:
    def __init__(self, root, refresh):
        self.root, self.refresh = root, refresh
        os.makedirs(root, exist_ok=True)

    def path(self, url, strategy):
        return os.path.join(self.root, hashlib.sha1(f"{strategy}|{url}".encode()).hexdigest() + ".json")

    def get(self, url, strategy):
        p = self.path(url, strategy)
        if self.refresh or not os.path.exists(p) or time.time() - os.path.getmtime(p) > CACHE_TTL:
            return None
        try:
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def put(self, url, strategy, rec):
        p = self.path(url, strategy)
        tmp = p + f".{os.getpid()}.tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(rec, fh)
            os.replace(tmp, p)
        except OSError:
            pass


def measure(url, strategy, auth, limiter, cache):
    rec = cache.get(url, strategy)
    if rec is not None:
        rec["cached"] = True
        return rec
    t0 = time.monotonic()
    data, err = fetch_raw(url, strategy, auth, limiter)
    if err:
        return {"error": err, "fetched_at": now_iso()}
    rec = parse(data)
    rec.update(fetched_at=now_iso(), latency_ms=int((time.monotonic() - t0) * 1000), cached=False)
    if rec.get("runtime_error"):
        rec["error"] = "lighthouse: " + rec["runtime_error"][:280]
    else:
        cache.put(url, strategy, rec)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_dir")
    ap.add_argument("--strategies", default="mobile,desktop")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--qps", type=float, default=float(os.environ.get("PSI_QPS", "1.5")))
    ap.add_argument("--refresh", action="store_true", help="ignore the 7-day cache")
    a = ap.parse_args()

    with open(os.path.join(a.run_dir, "meta.json"), encoding="utf-8-sig") as fh:
        meta = json.load(fh)
    pages = [(meta.get("your_brand") or "your page", meta.get("your_url"))]
    pages += [(c.get("brand"), c.get("url")) for c in meta.get("competitors") or []]
    pages = [(b, u) for b, u in pages if u]
    strategies = [s.strip() for s in a.strategies.split(",") if s.strip() in ("mobile", "desktop")]

    auth, limiter = Auth(), RateLimiter(a.qps)
    cache = Cache(os.path.join(a.run_dir, "_cache", "psi"), a.refresh)
    print(f"PageSpeed: {len(pages)} pages x {len(strategies)} devices, auth={auth.mode}", file=sys.stderr)
    jobs = [(b, u, s) for b, u in pages for s in strategies]
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:
        futs = {ex.submit(measure, u, s, auth, limiter, cache): (b, u, s) for b, u, s in jobs}
        for f in futs:
            b, u, s = futs[f]
            try:
                results[(b, s)] = f.result()
            except Exception as exc:  # noqa: BLE001
                results[(b, s)] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
            r = results[(b, s)]
            print(f"  {s:7} {b}: " + (r["error"][:90] if r.get("error") else f'performance {r["scores"].get("performance")}'), file=sys.stderr)

    out = {"source": "Google PageSpeed Insights API v5", "auth": auth.mode, "fetched_at": now_iso(),
           "strategies": strategies,
           "pages": [{"brand": b, "url": u, **{s: results.get((b, s)) for s in strategies}} for b, u in pages]}
    ok = sum(1 for v in results.values() if not v.get("error"))
    out["summary"] = {"requested": len(jobs), "succeeded": ok, "failed": len(jobs) - ok}
    path = os.path.join(a.run_dir, "pagespeed.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"wrote {path} ({ok}/{len(jobs)} succeeded)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
