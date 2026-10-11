#!/usr/bin/env python3
"""Core Web Vitals for every page in a run, via Google PageSpeed Insights v5.

    python fetch_pagespeed.py <run_dir> [--strategies mobile,desktop] [--workers 4] [--refresh]
                              [--engine auto|psi|lighthouse]

Reads meta.json (your_url + competitors[].url) and writes <run_dir>/pagespeed.json:
lab metrics (Lighthouse), real-user field metrics (CrUX p75, 28-day window) when
Chrome has enough traffic for the URL, Lighthouse category scores and the top
failing audits ("fixes") per page and device.

Auth, first match wins (the PSI API itself is free; a credential only lifts quota):
  PSI_API_KEY                 API key from a Google Cloud project with the PSI API enabled
  PSI_SERVICE_ACCOUNT_JSON    path to a service-account key file (needs `google-auth`)
  (none)                      keyless: works, but Google rate-limits it hard

Engines:
  psi         PageSpeed Insights only.
  lighthouse  Local Lighthouse (`npx lighthouse`, the engine PSI runs) against a local
              Chrome/Edge — lab data and category scores, no CrUX field data.
  auto        (default) PSI first; any page/device that fails on quota (429) or the
              network is re-measured with local Lighthouse when Chrome/Edge and npx
              are available. Local runs are sequential so CPU contention does not skew
              the performance score. Set CHROME_PATH to pick the browser.

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
import shutil
import subprocess
import sys
import tempfile
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
LIGHTHOUSE_PKG = os.environ.get("LIGHTHOUSE_PKG", "lighthouse@13.4.1")
LIGHTHOUSE_TIMEOUT = 300
CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/chromium-browser",
)


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


def find_chrome():
    """Path to a local Chrome/Edge for Lighthouse, or None."""
    env = os.environ.get("CHROME_PATH")
    if env and os.path.exists(env):
        return env
    for p in CHROME_CANDIDATES:
        if os.path.exists(p):
            return p
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge"):
        p = shutil.which(name)
        if p:
            return p
    return None


def lighthouse_raw(url, strategy, chrome):
    """Run Lighthouse locally; returns ({"lighthouseResult": lhr}, None) or (None, error)."""
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        return None, "lighthouse: npx not found (install Node.js)"
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "lh.json")
        cmd = [npx, "--yes", LIGHTHOUSE_PKG, url, "--output=json", f"--output-path={out}", "--quiet",
               "--only-categories=" + ",".join(CATEGORIES),
               "--chrome-flags=--headless=new --no-first-run --no-default-browser-check"]
        if strategy == "desktop":
            cmd.append("--preset=desktop")
        try:
            proc = subprocess.run(cmd, env=dict(os.environ, CHROME_PATH=chrome), capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", timeout=LIGHTHOUSE_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return None, f"lighthouse: {type(exc).__name__}: {exc}"[:300]
        # On Windows Lighthouse can exit non-zero after writing the report (EPERM while
        # deleting its temp Chrome profile), so trust the report file, not the exit code.
        if not os.path.exists(out):
            return None, f"lighthouse exit {proc.returncode}: {(proc.stderr or proc.stdout)[-280:]}"
        try:
            with open(out, encoding="utf-8") as fh:
                return {"lighthouseResult": json.load(fh)}, None
        except ValueError as exc:
            return None, f"lighthouse json: {exc}"


def measure(url, strategy, auth, limiter, cache, engine="psi", chrome=None):
    key = url if engine == "psi" else f"lighthouse|{url}"
    rec = cache.get(key, strategy)
    if rec is not None:
        rec["cached"] = True
        return rec
    t0 = time.monotonic()
    if engine == "psi":
        data, err = fetch_raw(url, strategy, auth, limiter)
    else:
        data, err = lighthouse_raw(url, strategy, chrome)
    if err:
        return {"error": err, "engine": engine, "fetched_at": now_iso()}
    rec = parse(data)
    rec.update(engine=engine, fetched_at=now_iso(), latency_ms=int((time.monotonic() - t0) * 1000), cached=False)
    if rec.get("runtime_error"):
        rec["error"] = "lighthouse: " + rec["runtime_error"][:280]
    else:
        cache.put(key, strategy, rec)
    return rec


def needs_fallback(rec):
    """PSI failures that local Lighthouse can stand in for (quota or network, not a bad URL)."""
    err = (rec or {}).get("error") or ""
    return bool(err) and (err.startswith("http 429") or "quota" in err.lower() or err.startswith("network:")
                          or "retries exhausted" in err)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_dir")
    ap.add_argument("--strategies", default="mobile,desktop")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--qps", type=float, default=float(os.environ.get("PSI_QPS", "1.5")))
    ap.add_argument("--refresh", action="store_true", help="ignore the 7-day cache")
    ap.add_argument("--engine", choices=("auto", "psi", "lighthouse"), default=os.environ.get("PSI_ENGINE", "auto"))
    a = ap.parse_args()

    with open(os.path.join(a.run_dir, "meta.json"), encoding="utf-8-sig") as fh:
        meta = json.load(fh)
    pages = [(meta.get("your_brand") or "your page", meta.get("your_url"))]
    pages += [(c.get("brand"), c.get("url")) for c in meta.get("competitors") or []]
    pages = [(b, u) for b, u in pages if u]
    strategies = [s.strip() for s in a.strategies.split(",") if s.strip() in ("mobile", "desktop")]

    auth, limiter = Auth(), RateLimiter(a.qps)
    cache = Cache(os.path.join(a.run_dir, "_cache", "psi"), a.refresh)
    chrome = find_chrome() if a.engine in ("auto", "lighthouse") else None
    print(f"PageSpeed: {len(pages)} pages x {len(strategies)} devices, engine={a.engine}, auth={auth.mode}"
          + (f", chrome={chrome}" if chrome else ""), file=sys.stderr)
    jobs = [(b, u, s) for b, u in pages for s in strategies]
    results = {}

    def report(b, s):
        r = results[(b, s)]
        print(f"  {s:7} {b} [{r.get('engine', '?')}]: "
              + (r["error"][:90] if r.get("error") else f'performance {r["scores"].get("performance")}'), file=sys.stderr)

    if a.engine in ("auto", "psi"):
        with ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex:
            futs = {ex.submit(measure, u, s, auth, limiter, cache): (b, u, s) for b, u, s in jobs}
            for f in futs:
                b, u, s = futs[f]
                try:
                    results[(b, s)] = f.result()
                except Exception as exc:  # noqa: BLE001
                    results[(b, s)] = {"error": f"{type(exc).__name__}: {exc}"[:300], "engine": "psi"}
                report(b, s)
    local = [(b, u, s) for b, u, s in jobs
             if a.engine == "lighthouse" or (a.engine == "auto" and needs_fallback(results.get((b, s))))]
    if local and not chrome:
        print("  local Lighthouse unavailable: no Chrome/Edge found (set CHROME_PATH)", file=sys.stderr)
    elif local:
        print(f"Lighthouse (local, sequential): {len(local)} page/device runs", file=sys.stderr)
        for b, u, s in local:  # sequential on purpose: parallel runs skew the CPU-bound metrics
            psi_err = (results.get((b, s)) or {}).get("error")
            results[(b, s)] = measure(u, s, auth, limiter, cache, engine="lighthouse", chrome=chrome)
            if psi_err:
                results[(b, s)]["psi_error"] = psi_err[:160]
            report(b, s)

    engines = sorted({r.get("engine") for r in results.values() if r and not r.get("error")})
    source = {"psi": "Google PageSpeed Insights API v5",
              "lighthouse": f"Lighthouse ({LIGHTHOUSE_PKG.split('@')[-1]}) run locally in headless Chrome"}
    out = {"source": " + ".join(source[e] for e in engines) or "Google PageSpeed Insights API v5",
           "engines": engines, "auth": auth.mode, "fetched_at": now_iso(),
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
