#!/usr/bin/env python3
"""Deterministic page structure + link extractor (Python standard library only).

Parses the RAW HTML of a page and extracts — accurately, not approximated —
the title, meta description, the full H1..H6 outline, EVERY hyperlink (anchor
text + href, classified internal/external, with its section + scope), tables,
JSON-LD schema types, images/alt, and a visible word count.

This solves the "internal linking looks fake" problem: links come straight from
the HTML `<a href>` tags, not from a summarised markdown view.

Usage:  python extract_page.py <url> <out_json>
        (the page-extractor agent runs this first, then layers semantic
         summaries/FAQs from WebFetch on top.)

If the fetch is blocked (e.g. HTTP 403), it writes a JSON with
extraction_status="blocked" so the agent can fall back to WebFetch / manual paste.
"""
import json
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "en-IN,en;q=0.9",
           "Accept": "text/html,application/xhtml+xml"}
SKIP = {"script", "style", "noscript", "svg", "template"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
CHROME = {"nav", "footer", "header", "aside"}


def reg_domain(host):
    host = (host or "").lower().lstrip("www.")
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


class PageParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base = base_url
        self.base_dom = reg_domain(urlparse(base_url).netloc)
        self.title = ""
        self.meta_desc = ""
        self.h1 = ""
        self.outline = []          # [{level, text}]
        self.heading_counts = {"h1": 0, "h2": 0, "h3": 0, "h4_plus": 0}
        self.links = []            # [{anchor, href, section, scope, internal}]
        self.images = 0
        self.images_alt = 0
        self.tables = 0
        self.schema_types = []
        self.words = 0
        # state
        self._skip = 0
        self._chrome = {k: 0 for k in CHROME}
        self._cur_section = ""
        self._h_level = 0
        self._h_buf = []
        self._in_title = False
        self._a_href = None
        self._a_buf = []
        self._ldjson = 0
        self._ld_buf = []

    def _scope(self):
        for k in ("nav", "footer", "header", "aside"):
            if self._chrome[k] > 0:
                return "sidebar" if k == "aside" else k
        return "in-content"

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in SKIP:
            self._skip += 1
            if tag == "script" and a.get("type", "").lower() == "application/ld+json":
                self._ldjson += 1
                self._ld_buf = []
            return
        if tag in CHROME:
            self._chrome[tag] += 1
        if tag == "title":
            self._in_title = True
        elif tag == "meta" and a.get("name", "").lower() == "description":
            self.meta_desc = (a.get("content") or "").strip()
        elif tag in HEADINGS:
            self._h_level = int(tag[1])
            self._h_buf = []
        elif tag == "a" and a.get("href"):
            self._a_href = a.get("href")
            self._a_buf = []
        elif tag == "img":
            self.images += 1
            if (a.get("alt") or "").strip():
                self.images_alt += 1
        elif tag == "table":
            self.tables += 1

    def handle_endtag(self, tag):
        if tag in SKIP:
            if tag == "script" and self._ldjson > 0:
                self._parse_ldjson("".join(self._ld_buf))
                self._ldjson -= 1
            if self._skip > 0:
                self._skip -= 1
            return
        if tag in CHROME and self._chrome[tag] > 0:
            self._chrome[tag] -= 1
        if tag == "title":
            self._in_title = False
        elif tag in HEADINGS:
            text = re.sub(r"\s+", " ", "".join(self._h_buf)).strip()
            if text:
                lvl = self._h_level
                self.outline.append({"level": lvl, "text": text})
                if lvl == 1:
                    self.heading_counts["h1"] += 1
                    if not self.h1:
                        self.h1 = text
                elif lvl == 2:
                    self.heading_counts["h2"] += 1
                elif lvl == 3:
                    self.heading_counts["h3"] += 1
                else:
                    self.heading_counts["h4_plus"] += 1
                self._cur_section = text
            self._h_level = 0
        elif tag == "a" and self._a_href is not None:
            anchor = re.sub(r"\s+", " ", "".join(self._a_buf)).strip()
            href = self._a_href
            absu = urljoin(self.base, href)
            scheme = urlparse(absu).scheme
            if anchor and scheme in ("http", "https"):
                internal = reg_domain(urlparse(absu).netloc) == self.base_dom
                self.links.append({
                    "anchor": anchor[:160], "href": absu,
                    "section": self._cur_section[:120], "scope": self._scope(),
                    "internal": internal,
                })
            self._a_href = None

    def handle_data(self, data):
        if self._ldjson > 0:
            self._ld_buf.append(data)
            return
        if self._skip > 0:
            return
        if self._in_title and not self.title:
            self.title = re.sub(r"\s+", " ", data).strip()
        if self._h_level:
            self._h_buf.append(data)
        if self._a_href is not None:
            self._a_buf.append(data)
        self.words += len(data.split())

    def _parse_ldjson(self, raw):
        try:
            obj = json.loads(raw)
        except Exception:
            return
        for node in (obj if isinstance(obj, list) else [obj]):
            if isinstance(node, dict):
                t = node.get("@type")
                for x in (t if isinstance(t, list) else [t]):
                    if x and x not in self.schema_types:
                        self.schema_types.append(str(x))


def fetch(url):
    if "://" not in url:
        url = "https://" + url
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as r:
        raw = r.read()
        return r.geturl(), raw.decode("utf-8", "ignore")


def main():
    if len(sys.argv) < 3:
        print("usage: python extract_page.py <url> <out_json>"); sys.exit(1)
    url, out = sys.argv[1], sys.argv[2]
    try:
        final_url, html = fetch(url)
    except Exception as exc:  # noqa: BLE001
        json.dump({"url": url, "extraction_status": "blocked",
                   "notes": [f"fetch failed: {type(exc).__name__}: {exc}"]},
                  open(out, "w", encoding="utf-8"), indent=2)
        print("BLOCKED:", exc); return
    p = PageParser(final_url)
    p.feed(html)
    internal = [l for l in p.links if l["internal"]]
    uniq_targets = sorted({l["href"] for l in internal})
    data = {
        "url": final_url,
        "title": p.title,
        "meta_description": p.meta_desc,
        "h1": p.h1,
        "heading_counts": p.heading_counts,
        "heading_outline": p.outline[:200],
        "internal_link_count": len(internal),
        "unique_internal_targets": len(uniq_targets),
        "external_link_count": len(p.links) - len(internal),
        "internal_links": internal[:400],
        "external_links_sample": [l for l in p.links if not l["internal"]][:60],
        "tables": p.tables,
        "image_count": p.images,
        "image_alt_count": p.images_alt,
        "schema_types": p.schema_types,
        "word_count_total": p.words,
        "extraction_status": "full",
        "notes": [],
    }
    json.dump(data, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"OK {final_url} :: H1={p.heading_counts['h1']} H2={p.heading_counts['h2']} "
          f"internal_links={len(internal)} (unique {len(uniq_targets)}) words={p.words}")


if __name__ == "__main__":
    main()
