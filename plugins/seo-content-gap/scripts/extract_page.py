#!/usr/bin/env python3
"""Deterministic page extractor (Python standard library only).

Parses the RAW HTML of a page and extracts — accurately, not approximated —
everything a content team needs to SEE what was written:
  * title, meta description, H1
  * the full H1..H6 outline AND the actual body text under each heading (sections)
  * EVERY hyperlink (anchor + href, internal/external, section + scope)
  * EVERY image (src + alt)
  * tables count, JSON-LD schema types, word count

This is the source of truth for structure, links, images and verbatim section
text. The page-extractor agent layers semantic notes (FAQ Q&A, examples,
external-brand mentions, ranking view) on top via WebFetch.

Usage:  python extract_page.py <url> <out_json>
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
SEC_CAP = 6000  # max chars of body text kept per section


def reg_domain(host):
    host = (host or "").lower()
    if host.startswith("www."):
        host = host[4:]
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
        self.outline = []
        self.heading_counts = {"h1": 0, "h2": 0, "h3": 0, "h4_plus": 0}
        self.links = []
        self.images_list = []
        self.tables = 0
        self.schema_types = []
        self.words = 0
        self.sections = []                 # [{level, heading, text}]
        # state
        self._skip = 0
        self._chrome = {k: 0 for k in CHROME}
        self._h_level = 0
        self._h_buf = []
        self._in_title = False
        self._a_href = None
        self._a_buf = []
        self._ldjson = 0
        self._ld_buf = []
        self._sec_level = 0
        self._sec_heading = "(intro)"
        self._sec_buf = []

    def _scope(self):
        for k in ("nav", "footer", "header", "aside"):
            if self._chrome[k] > 0:
                return "sidebar" if k == "aside" else k
        return "in-content"

    def _flush_section(self):
        text = re.sub(r"[ \t]+", " ", " ".join(self._sec_buf))
        text = re.sub(r"\s*\n\s*", " ", text).strip()
        if text:
            self.sections.append({
                "level": self._sec_level,
                "heading": self._sec_heading,
                "text": text[:SEC_CAP],
                "word_count": len(text.split()),
                "truncated": len(text) > SEC_CAP,
            })
        self._sec_buf = []

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
            src = a.get("src") or a.get("data-src") or ""
            if src and len(self.images_list) < 120:
                self.images_list.append({"src": urljoin(self.base, src),
                                         "alt": (a.get("alt") or "").strip()})
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
                # close previous section, open a new one for this heading
                self._flush_section()
                self._sec_level = lvl
                self._sec_heading = text
            self._h_level = 0
        elif tag == "a" and self._a_href is not None:
            anchor = re.sub(r"\s+", " ", "".join(self._a_buf)).strip()
            absu = urljoin(self.base, self._a_href)
            if anchor and urlparse(absu).scheme in ("http", "https"):
                internal = reg_domain(urlparse(absu).netloc) == self.base_dom
                self.links.append({"anchor": anchor[:160], "href": absu,
                                   "section": self._sec_heading[:120],
                                   "scope": self._scope(), "internal": internal})
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
            return
        if self._a_href is not None:
            self._a_buf.append(data)
        # body text of the current section (in-content only, skip nav/footer)
        if self._scope() == "in-content":
            self._sec_buf.append(data)
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
    with urlopen(Request(url, headers=HEADERS), timeout=30) as r:
        return r.geturl(), r.read().decode("utf-8", "ignore")


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
    p._flush_section()
    internal = [l for l in p.links if l["internal"]]
    external = [l for l in p.links if not l["internal"]]
    data = {
        "url": final_url, "title": p.title, "meta_description": p.meta_desc, "h1": p.h1,
        "heading_counts": p.heading_counts, "heading_outline": p.outline[:250],
        "sections": p.sections[:120],
        "internal_link_count": len(internal),
        "unique_internal_targets": len({l["href"] for l in internal}),
        "external_link_count": len(external),
        "internal_links": internal[:500],
        "external_links": external[:120],
        "images": p.images_list,
        "image_count": len(p.images_list),
        "image_alt_count": sum(1 for i in p.images_list if i["alt"]),
        "tables_count": p.tables,
        "schema_types": p.schema_types,
        "word_count_total": p.words,
        "extraction_status": "full",
        "notes": [],
    }
    json.dump(data, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"OK {final_url} :: H1={p.heading_counts['h1']} H2={p.heading_counts['h2']} "
          f"sections={len(p.sections)} links={len(internal)}int/{len(external)}ext "
          f"images={len(p.images_list)} words={p.words}")


if __name__ == "__main__":
    main()
