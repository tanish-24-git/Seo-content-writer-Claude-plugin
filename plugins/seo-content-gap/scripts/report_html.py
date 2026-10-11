"""HTML renderer: a self-contained, comparison-only competitive content report.

render(ctx, print_mode=False) -> str

Written for senior readers: light-blue and white only, plain tables, statuses in words
(Covered / Mentioned / Not covered; Good / Needs improvement / Poor), percentages where
they help, and a fixed sidebar index. Every section states what each page has — search
visibility, page speed, on-page SEO, headings, topic coverage, the content each page wrote
side by side, FAQs, figures — plus a full detail view per page (outline, verbatim content
by section, FAQs, examples, links, images). It compares; it does not recommend.

Standard library only; no external CSS, fonts or scripts.
"""
import os
import re
from datetime import datetime
from urllib.parse import urlparse

from report_core import _load, clean_text, esc, internal_link_count, keyword_checks, onpage_internal_links, rate

COVER = {3: "Covered", 2: "Covered", 1: "Mentioned", 0: "Not covered"}
INTENT = {"high": "Key topics for a premium calculator", "medium": "Supporting topics", "low": "Background topics"}
CATS = (("performance", "Performance"), ("accessibility", "Accessibility"), ("best-practices", "Best practices"), ("seo", "SEO"))
LAB = (("lcp_ms", "Main content visible", "Largest Contentful Paint (LCP)"), ("fcp_ms", "First content visible", "First Contentful Paint (FCP)"),
       ("si_ms", "Visual loading speed", "Speed Index"), ("tbt_ms", "Time the page is unresponsive", "Total Blocking Time (TBT)"),
       ("cls", "Layout stability", "Cumulative Layout Shift (CLS) — lower is better"), ("ttfb_ms", "Server response", "Time to First Byte (TTFB)"),
       ("bytes", "Page size", "Total download size"))
RATING = {"good": "Good", "ni": "Needs improvement", "poor": "Poor"}

CSS = """
:root{--navy:#0B2545;--blue:#1F5FA8;--mid:#6F9BD1;--sky:#F3F7FC;--sky2:#E4EEF9;--sky3:#D3E3F5;--line:#DCE6F2;
--ink:#1F2937;--muted:#5F6F84;--side:280px}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:16px}
body{margin:0;background:#fff;color:var(--ink);font:15px/1.6 "Segoe UI",Calibri,Arial,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.side{position:fixed;inset:0 auto 0 0;width:var(--side);background:var(--sky);border-right:1px solid var(--line);overflow-y:auto;padding:22px 0 40px}
.side .rt{padding:0 22px 16px;border-bottom:1px solid var(--line);margin-bottom:8px}
.side .rt b{display:block;color:var(--navy);font-size:15px;line-height:1.35}.side .rt span{color:var(--muted);font-size:12.5px}
.side h6{margin:16px 22px 4px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600}
.side a{display:flex;gap:10px;align-items:baseline;padding:6px 22px 6px 19px;color:var(--navy);font-size:14px;border-left:3px solid transparent}
.side a .no{color:var(--muted);font-size:12px;min-width:18px}
.side a:hover{background:var(--sky2);text-decoration:none}.side a.on{background:#fff;border-left-color:var(--blue);font-weight:600}
.side a.sub{padding-left:47px;font-size:13.5px}
main{margin-left:var(--side);padding:0 48px 80px;max-width:calc(1220px + var(--side))}
.top{padding:34px 32px 26px;margin:0 -48px 6px;background:linear-gradient(180deg,var(--sky2),#fff)}
.top .k{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--blue);font-weight:600}
.top h1{margin:6px 0 8px;color:var(--navy);font-size:29px;line-height:1.25}
.top p{margin:2px 0;color:var(--muted)}
section{padding:30px 0 12px;border-bottom:1px solid var(--line)}section:last-of-type{border-bottom:0}
h2{color:var(--navy);font-size:23px;margin:0 0 4px}h2 .n{color:var(--blue);margin-right:10px}
.lede{color:var(--muted);margin:0 0 18px;max-width:900px}
h3{color:var(--navy);font-size:17px;margin:26px 0 10px}h4{color:var(--navy);font-size:15px;margin:18px 0 8px}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:8px;margin:8px 0 16px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}
thead th{background:var(--sky2);color:var(--navy);font-weight:600;font-size:13.5px;position:sticky;top:0;z-index:1}
thead th.us{background:var(--sky3)}
table.cmp{table-layout:fixed}table.cmp th:first-child{width:27%}table.cmp th.xtra{width:11%}
tbody tr:last-child td{border-bottom:0}
td.lab{font-weight:600;color:var(--navy);background:var(--sky);overflow-wrap:anywhere}
td.us{background:#F1F6FD}td.c,th.c{text-align:center}td.num{text-align:right;font-variant-numeric:tabular-nums}
tr.tot td{font-weight:600;background:var(--sky);color:var(--navy)}tr.tot td.us{background:var(--sky2)}
.small{font-size:12.5px;color:var(--muted)}.mono{font-family:Consolas,"Courier New",monospace;font-size:12px;word-break:break-all}
.dim{color:#98A6B8}.em{font-weight:700;color:var(--navy)}
.ours{display:inline-block;margin-left:6px;padding:0 7px;border-radius:4px;background:var(--sky3);color:var(--navy);font-size:10.5px;font-weight:700;letter-spacing:.04em;vertical-align:2px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:6px 0 18px}
.card{border:1px solid var(--line);border-radius:10px;padding:14px 16px;background:#fff}
.card .v{font-size:26px;font-weight:700;color:var(--navy);line-height:1.2}.card .l{font-size:13px;color:var(--muted)}
.card.us{background:var(--sky)}
.obs{margin:6px 0 18px;padding:0;list-style:none;counter-reset:o}
.obs li{padding:10px 14px 10px 48px;background:var(--sky);margin:0 0 8px;border-radius:8px;position:relative}
.obs li:before{counter-increment:o;content:counter(o);position:absolute;left:14px;top:9px;width:22px;height:22px;border-radius:50%;background:var(--blue);color:#fff;font-size:12px;font-weight:700;text-align:center;line-height:22px}
.tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:4px 0 14px}
.tools label{font-size:13px;color:var(--muted)}
.btn{border:1px solid var(--line);background:#fff;color:var(--navy);padding:5px 12px;border-radius:6px;font:inherit;font-size:13px;cursor:pointer}
.btn.on,.btn:hover{background:var(--sky2);border-color:var(--mid)}
select,input.q{border:1px solid var(--line);border-radius:6px;padding:5px 10px;font:inherit;font-size:13.5px;background:#fff;color:var(--navy)}
input.q{min-width:280px}
details.topic{border:1px solid var(--line);border-radius:10px;margin:0 0 12px;background:#fff}
details.topic>summary{cursor:pointer;list-style:none;padding:12px 16px}
details.topic>summary::-webkit-details-marker{display:none}
details.topic>summary b{color:var(--navy);font-size:15.5px}
details.topic>summary .who-line{display:block;font-size:12.5px;color:var(--muted);margin-top:2px}
details.topic[open]>summary{border-bottom:1px solid var(--line);background:var(--sky);border-radius:10px 10px 0 0}
.row{display:grid;grid-template-columns:200px 1fr;gap:18px;padding:14px 16px;border-bottom:1px solid var(--line)}.row:last-child{border-bottom:0}
.row.us{background:#F7FAFE}.row .who b{color:var(--navy);display:block}.row .who .small{display:block;margin-top:2px}
.cap{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:600;margin:0 0 3px}
.sum{margin:0 0 10px}.quote{margin:0;padding:10px 14px;background:var(--sky);border-radius:6px;font-size:14px;white-space:pre-line}
.quote.more{margin-top:6px}.nc{color:var(--muted);font-style:italic}
details.more>summary{cursor:pointer;color:var(--blue);font-size:13px;margin-top:6px}
.grid5{display:grid;grid-template-columns:repeat(5,minmax(200px,1fr));gap:12px;overflow-x:auto}
.col{border:1px solid var(--line);border-radius:8px;padding:10px 12px;min-width:200px}.col.us{background:var(--sky)}
.col h4{margin:0 0 6px}.col .h1{font-weight:600;color:var(--navy);margin:0 0 8px;font-size:13.5px}
ol.h2s{margin:0;padding-left:20px;font-size:13.5px}ol.h2s li{margin:0 0 3px}
.ol{list-style:none;margin:0;padding:0}.ol li{padding:3px 0;font-size:13.5px;display:flex;gap:10px}
.lvl{flex:none;width:26px;font-size:11.5px;font-weight:600;color:var(--muted)}
.ol li.l3{padding-left:20px}.ol li.l4{padding-left:40px}.ol li.l5,.ol li.l6{padding-left:60px}
.kv{display:grid;grid-template-columns:200px 1fr;border:1px solid var(--line);border-radius:8px;overflow:hidden;margin:8px 0 16px}
.kv div{padding:8px 12px;border-bottom:1px solid var(--line)}.kv div:nth-child(odd){background:var(--sky);font-weight:600;color:var(--navy)}
.kv div:nth-last-child(-n+2){border-bottom:0}
.sec{margin:0 0 14px;padding:0 0 12px;border-bottom:1px dashed var(--line)}.sec:last-child{border-bottom:0}
.sec h5{margin:0 0 6px;font-size:15px;color:var(--navy);display:flex;gap:10px;align-items:baseline}
.sec p{margin:0;max-width:980px;white-space:pre-line}
.faq{border:1px solid var(--line);border-radius:8px;margin:0 0 8px}.faq summary{cursor:pointer;padding:9px 14px;font-weight:600;color:var(--navy)}
.faq div{padding:0 14px 12px;max-width:980px}
.cols2{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}
ul.plain{margin:6px 0 0;padding-left:18px}ul.plain li{margin:0 0 4px}
.foot{margin-top:40px;color:var(--muted);font-size:12.5px}
@media (max-width:980px){.side{position:static;width:auto;border-right:0;border-bottom:1px solid var(--line)}
main{margin-left:0;padding:0 16px 60px}.top{margin:0 -16px 6px;padding:24px 16px}.row{grid-template-columns:1fr}.kv{grid-template-columns:1fr}}
@media print{.side,.tools{display:none!important}main{margin:0;padding:0;max-width:none}.top{margin:0}details{break-inside:avoid}
thead th{position:static}section{break-before:page}a{color:var(--ink)}}
"""

JS = """
(function(){
var links=[].slice.call(document.querySelectorAll('.side a[href^="#"]'));
var map={};links.forEach(function(a){map[a.getAttribute('href').slice(1)]=a;});
var obs=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){
links.forEach(function(a){a.classList.remove('on');});var a=map[e.target.id];if(a)a.classList.add('on');}});},{rootMargin:'0px 0px -70% 0px'});
document.querySelectorAll('section[id]').forEach(function(s){obs.observe(s);});
})();
var topicFilter='all',pageFilter='all';
function applyContent(){document.querySelectorAll('#ctopics details.topic').forEach(function(d){
var t=d.getAttribute('data-tf').split(' ');d.style.display=(topicFilter==='all'||t.indexOf(topicFilter)>=0)?'':'none';});
document.querySelectorAll('#ctopics .row').forEach(function(r){var b=r.getAttribute('data-b');
r.style.display=(pageFilter==='all'||r.classList.contains('us')||b===pageFilter)?'':'none';});}
function setTopic(btn,v){document.querySelectorAll('#tfbtns .btn').forEach(function(b){b.classList.remove('on');});btn.classList.add('on');topicFilter=v;applyContent();}
function setPage(sel){pageFilter=sel.value;applyContent();}
function accAll(open){document.querySelectorAll('#ctopics details.topic').forEach(function(d){d.open=open;});}
function search(inp,tbl){var q=inp.value.toLowerCase();document.querySelectorAll('#'+tbl+' tbody tr').forEach(function(r){r.style.display=r.textContent.toLowerCase().indexOf(q)>=0?'':'none';});}
"""


# ----------------------------------------------------------------------------- helpers
def _int(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def _host(url):
    h = (urlparse(url or "").netloc or "").lower()
    return h[4:] if h.startswith("www.") else h


def _ms(v):
    return "—" if v is None else (f"{v / 1000:.1f} s" if v >= 1000 else f"{int(v)} ms")


def _metric(key, v):
    if v is None:
        return "—"
    if key == "cls":
        return f"{v:.3f}"
    if key == "bytes":
        return f"{v / 1048576:.1f} MB"
    return _ms(v)


def pct(n, d):
    return f"{round(100 * n / d)}%" if d else "—"


def scored(v, metric="score"):
    """'33 · Poor' — the value plus its rating in words (no colour)."""
    if v is None:
        return '<span class="dim">n/a</span>'
    return f'<span class="em">{esc(v)}</span><div class="small">{RATING.get(rate(metric, v), "")}</div>'


def dim(t):
    return f'<span class="dim">{esc(t)}</span>'


# Legal / regulatory boilerplate (disclaimers, fraud warnings, UIN lists) is never quoted as a
# page's coverage of a topic, and form pickers ("4 5 6 ... 82") are not prose.
_LEGAL = re.compile(r"IRDAI|\bUIN\b|risk factors|beware|spurious|fictitious|terms (?:and|&) conditions|"
                    r"disclaimer|formerly known as|registered office|\bCIN\b|trade ?logo", re.I)
_NUM_RUN = re.compile(r"(?:\b\d{1,3}\b[\s,]+){8,}")


def _sec_text(sec):
    if not sec:
        return ""
    t = sec.get("spa_model_text") or clean_text(sec.get("text") or "") or ""
    return re.sub(r"\s{2,}", " ", _NUM_RUN.sub(" … ", t)).strip()


def _quotable(sec):
    """A section whose text can stand for a page's coverage of a topic (not legal boilerplate)."""
    if not sec:
        return False
    blob = (sec.get("heading") or "") + " " + (sec.get("text") or "")[:1500]
    return len(_LEGAL.findall(blob)) < 3


def links_cell(page, quality):
    n, raw = internal_link_count(page, quality), len(onpage_internal_links(page))
    return str(n) + (f'<div class="small">{raw} including link lists</div>' if raw != n else "")


class R:
    def __init__(self, ctx, print_mode):
        self.c, self.p = ctx, print_mode
        self.meta = ctx["meta"]
        self.order, self.you, self.pages = ctx["order"], ctx["your"], ctx["pages"]
        self.names = self.meta.get("display_names") or {}
        self.out = []

    def A(self, s):
        self.out.append(s)

    def name(self, b):
        return self.names.get(b, b)

    def label(self, b):
        return esc(self.name(b)) + ('<span class="ours">OUR PAGE</span>' if b == self.you else "")

    def th(self, first=None):
        cells = [f"<th>{esc(first)}</th>"] if first is not None else []
        return "".join(cells) + "".join(f'<th class="c{" us" if b == self.you else ""}">{esc(self.name(b))}'
                                        + ('<div class="small">our page</div>' if b == self.you else "") + "</th>" for b in self.order)

    def td(self, b, html_, cls="c"):
        return f'<td class="{cls}{" us" if b == self.you else ""}">{html_}</td>'

    def table(self, first, rows, tid="", extra_th=""):
        """rows: [(label, fn(brand)->html, tr_class)]"""
        body = "".join(f'<tr class="{k}"><td class="lab">{esc(l)}</td>' + "".join(self.td(b, fn(b)) for b in self.order) + "</tr>"
                       for l, fn, k in [(r + ("",))[:3] for r in rows])
        self.A(f'<div class="tw"><table class="cmp"{f" id={tid}" if tid else ""}><thead><tr>' + self.th(first) + extra_th
               + "</tr></thead><tbody>" + body + "</tbody></table></div>")

    def section(self, sid, num, title, lede=""):
        self.A(f'<section id="{sid}"><h2><span class="n">{num}</span>{esc(title)}</h2>' + (f'<p class="lede">{lede}</p>' if lede else ""))

    def end(self):
        self.A("</section>")

    def pid(self, b):
        return "page-" + (re.sub(r"[^a-z0-9]+", "-", self.name(b).lower()).strip("-") or "x")


# ----------------------------------------------------------------------------- data shaping
def serp_queries(c):
    """[(query, [ {rank, domain, url} ])] from ranking.json (v0.7) or serp.json (per_query)."""
    rk = c.get("ranking") or {}
    if rk.get("per_query"):
        src = rk
    else:
        src = _load(os.path.join(c["run_dir"], "serp.json"), {}) or {}
        if not src.get("per_query"):
            src = rk
    if src.get("per_query"):
        return [(q.get("query") or "", q.get("results") or []) for q in src["per_query"]]
    groups = {}
    for r in src.get("ranking_pages") or []:
        groups.setdefault(r.get("query") or "", []).append(r)
    return list(groups.items())


def brand_domains(c):
    meta, out = c["meta"], {}
    out[c["your"]] = {_host(meta.get("your_url"))} | set(meta.get("your_domains") or [])
    for comp in meta.get("competitors") or []:
        out[comp.get("brand")] = {_host(comp.get("url")), _host(comp.get("user_supplied_url"))} | set(comp.get("domains") or [])
    return {b: {d for d in ds if d} for b, ds in out.items()}


def page_kind(url):
    u = (url or "").lower()
    if re.search(r"blog|insurance-guide|knowledge|article|/guide", u):
        return "article"
    if "calculator" in u:
        return "calculator"
    return "page"


def psi_rec(c, b, device):
    rec = (c.get("psi_by") or {}).get(b) or {}
    r = rec.get(device) or {}
    return None if not r or r.get("error") else r


def psi_score(c, b, device, cat="performance"):
    return ((psi_rec(c, b, device) or {}).get("scores") or {}).get(cat)


def covered(c, b, topics=None, min_depth=2):
    return sum(1 for t in (topics if topics is not None else c["topics"]) if _int(t["brands"][b]["info"].get("depth")) >= min_depth)


def serp_hits(c):
    """{brand: [rank or None per buyer query]} plus the buyer queries."""
    doms = brand_domains(c)
    you = c["your"]
    buyer = [(q, r) for q, r in serp_queries(c) if not any(d in (q or "").lower() for d in doms.get(you, ()))]
    hits = {}
    for b in c["order"]:
        hits[b] = []
        for q, res in buyer:
            hit = next((r for r in sorted(res, key=lambda r: r.get("rank") or 99)
                        if any((r.get("domain") or _host(r.get("url"))).endswith(d) for d in doms.get(b, ()))), None)
            hits[b].append(hit)
    return buyer, hits


# ----------------------------------------------------------------------------- sections
def nav(h):
    c = h.c
    items = [("summary", "1", "Summary"), ("pages", "2", "Pages compared"), ("visibility", "3", "Search visibility"),
             ("speed", "4", "Page speed"), ("onpage", "5", "SEO basics"), ("headings", "6", "Headings"),
             ("topics", "7", "Topic coverage"), ("content", "8", "Content side by side"), ("faqs", "9", "FAQs"),
             ("claims", "10", "Figures & claims")]
    groups = [("Overview", items[:2]), ("Search & speed", items[2:4]), ("Structure", items[4:6]), ("Content", items[6:])]
    h.A('<nav class="side" aria-label="Report contents"><div class="rt"><b>Competitive Content Comparison</b>'
        f'<span>{esc(c["topic"].title() or "Content comparison")}</span></div>')
    for g, its in groups:
        h.A(f"<h6>{esc(g)}</h6>")
        for sid, n, t in its:
            h.A(f'<a href="#{sid}"><span class="no">{n}</span>{esc(t)}</a>')
    h.A("<h6>Each page in full</h6>")
    for b in h.order:
        h.A(f'<a class="sub" href="#{h.pid(b)}">{esc(h.name(b))}{" (our page)" if b == h.you else ""}</a>')
    h.A("</nav>")


def header(h):
    c, meta = h.c, h.meta
    date = meta.get("created_at") or datetime.now().strftime("%Y-%m-%d")
    comps = ", ".join(esc(h.name(b)) for b in h.order if b != h.you)
    h.A(f'<div class="top"><div class="k">Competitive content comparison · {esc(meta.get("page_type") or "page")} page</div>'
        f'<h1>{esc((c["topic"] or "Content").title())}: {esc(h.name(h.you))} vs competitors</h1>'
        f'<p>Our page: <a href="{esc(meta.get("your_url"))}" target="_blank" rel="noopener">{esc(meta.get("your_url"))}</a></p>'
        f'<p>Compared with {comps} · Data collected {esc(date)}</p>'
        + (f'<p>Prepared by {esc(meta.get("prepared_by"))}</p>' if meta.get("prepared_by") else "") + "</div>")


def summary(h):
    c, P = h.c, h.pages
    high = [t for t in c["topics"] if t.get("intent") == "high"]
    ntop, nhigh = len(c["topics"]), len(high)
    buyer, hits = serp_hits(c)
    best = {b: min((x["rank"] for x in hits[b] if x and x.get("rank")), default=None) for b in h.order}
    kc = {b: keyword_checks(P[b], c["topic"]) for b in h.order} if c["topic"] else {}
    h.section("summary", "1", "Summary", "The headline comparison, grouped into three short tables. Every row is explained in the sections that follow.")

    h.A("<h3>Search and speed</h3>")
    h.table("Measure", [
        ("Best search position", lambda b: f'<span class="em">#{best[b]}</span>' if best[b] else dim("Not in results")),
        (f"Searches where the brand appears (of {len(buyer)})", lambda b: f'{sum(1 for x in hits[b] if x)} of {len(buyer)}'),
        ("Page speed score — mobile (out of 100)", lambda b: scored(psi_score(c, b, "mobile"))),
        ("Page speed score — desktop (out of 100)", lambda b: scored(psi_score(c, b, "desktop"))),
        ("SEO score — mobile (out of 100)", lambda b: scored(psi_score(c, b, "mobile", "seo"))),
    ])
    h.A("<h3>SEO basics</h3>")
    seo_rows = [
        ("Visible to search engines", lambda b: '<span class="em">No (noindex)</span>' if "noindex" in (P[b].get("robots_meta") or "").lower() else "Yes"),
        ("Main heading (H1)", lambda b: '<span class="em">Missing</span>' if c["hcounts"][b][1] == 0 else "Present"),
    ]
    if kc:
        seo_rows += [(f"“{c['topic']}” in page title", lambda b: "Yes" if kc[b]["title"] else dim("No")),
                     (f"“{c['topic']}” in main heading", lambda b: "Yes" if kc[b]["h1"] else dim("No"))]
    seo_rows += [
        ("Structured data present", lambda b: "Yes" if P[b].get("schema_types") else dim("No")),
        ("Images with a text description", lambda b: pct(_int(P[b].get("image_alt_count")), _int(P[b].get("image_count")))),
        ("Author or reviewer named", lambda b: "Yes" if (P[b].get("author") or P[b].get("reviewer")) else dim("No")),
    ]
    h.table("Measure", seo_rows)
    h.A("<h3>Content</h3>")
    h.table("Measure", [
        (f"Topics covered (of {ntop})", lambda b: f'<span class="em">{pct(covered(c, b), ntop)}</span> <span class="small">({covered(c, b)})</span>'),
        (f"Key calculator topics covered (of {nhigh})", lambda b: f'<span class="em">{pct(covered(c, b, high), nhigh)}</span> <span class="small">({covered(c, b, high)})</span>'),
        ("Words on the page", lambda b: f'{_int(P[b].get("word_count_total")):,}'),
        ("FAQs on the page", lambda b: str(len(P[b].get("faqs") or []))),
        ("Data tables", lambda b: str(_int(P[b].get("tables_count")))),
        ("Worked examples", lambda b: str(len(P[b].get("examples") or []))),
    ])

    obs = []
    for b in h.order:
        if "noindex" in (P[b].get("robots_meta") or "").lower():
            obs.append(f"<b>{esc(h.name(b))}</b>'s page is set to “{esc(P[b].get('robots_meta'))}”, so search engines are told not to list it.")
    for b in h.order:
        if c["hcounts"][b][1] == 0:
            obs.append(f"<b>{esc(h.name(b))}</b>'s page has no main heading (H1)" + (f"; its title reads “{esc(P[b].get('title'))}”." if P[b].get("title") else "."))
    ranked = {b: r for b, r in best.items() if r}
    if ranked:
        lead = min(ranked, key=ranked.get)
        obs.append(f"<b>{esc(h.name(lead))}</b> holds the best search position (#{ranked[lead]})"
                   + (f"; {esc(h.name(h.you))} does not appear in the results for any of the {len(buyer)} searches." if h.you not in ranked else "."))
    perf = {b: psi_score(c, b, "mobile") for b in h.order if psi_score(c, b, "mobile") is not None}
    if perf:
        hi, lo = max(perf, key=perf.get), min(perf, key=perf.get)
        obs.append(f"On mobile, page speed scores range from {perf[lo]} ({esc(h.name(lo))}) to {perf[hi]} ({esc(h.name(hi))}); "
                   f"{esc(h.name(h.you))} scores {perf.get(h.you, 'n/a')}."
                   + (f" All {len(perf)} pages are rated “Poor” on mobile." if all(rate("score", v) == "poor" for v in perf.values()) else ""))
    cov = {b: covered(c, b) for b in h.order}
    top = max(cov, key=cov.get)
    obs.append(f"{esc(h.name(top))} covers the most topics ({pct(cov[top], ntop)}); {esc(h.name(h.you))} covers {pct(cov[h.you], ntop)}"
               f" overall and {pct(covered(c, h.you, high), nhigh)} of the key calculator topics.")
    fq = {b: len(P[b].get("faqs") or []) for b in h.order}
    fb = max(fq, key=fq.get)
    gaps = (c.get("gaps") or {}).get("faq_gaps") or []
    obs.append(f"{esc(h.name(fb))} answers the most FAQs ({fq[fb]}); {esc(h.name(h.you))} answers {fq[h.you]}"
               + (f", and {len(gaps)} questions answered by competitors are not on its page." if gaps else "."))
    h.A("<h3>Key observations</h3><ol class=obs>" + "".join(f"<li>{o}</li>" for o in obs) + "</ol>")
    h.end()


def pages_compared(h):
    h.section("pages", "2", "Pages compared", "The pages compared, as published on the date of comparison.")
    rows = []
    for b in h.order:
        p = h.pages[b]
        rows.append(f'<tr><td class="lab">{h.label(b)}</td><td><a class="mono" href="{esc(p.get("url"))}" target="_blank" rel="noopener">{esc(p.get("url"))}</a></td>'
                    f'<td>{esc(p.get("title"))}</td><td>{esc(p.get("h1")) or dim("No H1")}</td>'
                    f'<td class="num">{_int(p.get("word_count_total")):,}</td></tr>')
    h.A('<div class="tw"><table><thead><tr><th>Brand</th><th>Page</th><th>Page title</th><th>Main heading (H1)</th><th class="c">Words</th></tr></thead><tbody>'
        + "".join(rows) + "</tbody></table></div>")
    h.end()


def visibility(h):
    c = h.c
    buyer, hits = serp_hits(c)
    h.section("visibility", "3", "Search visibility",
              "Where each brand appears in search results for the searches tested (best position of any page on the brand's website).")
    if not buyer:
        h.A('<p class="nc">No search-ranking data was collected for this run.</p>')
        return h.end()
    rows = [(q, (lambda i: lambda b: (f'<span class="em">#{hits[b][i]["rank"]}</span> <span class="small">{page_kind(hits[b][i].get("url"))}</span>'
                                      if hits[b][i] else dim("Not in results")))(i)) for i, (q, _) in enumerate(buyer)]
    rows.append(("Searches where the brand appears", lambda b: f'{sum(1 for x in hits[b] if x)} of {len(buyer)}', "tot"))
    h.table("Search", rows)
    depth = max((len(r) for _, r in serp_queries(c)), default=0)
    h.A(f'<p class="small">Based on the top {depth} results for each search. Positions vary by location, device and date.</p>')
    doms = brand_domains(c)
    h.A('<details class="topic"><summary><b>See the full results for every search</b></summary><div style="padding:12px 16px">')
    for q, res in serp_queries(c):
        h.A(f"<h4>{esc(q)}</h4><div class=tw><table><thead><tr><th class=c style='width:60px'>#</th><th>Website</th><th>Page</th></tr></thead><tbody>")
        for r in sorted(res, key=lambda r: r.get("rank") or 99):
            owner = next((b for b in h.order if any((r.get("domain") or _host(r.get("url"))).endswith(d) for d in doms.get(b, ()))), None)
            h.A(f'<tr><td class=c>{esc(r.get("rank"))}</td><td>{esc(r.get("domain") or _host(r.get("url")))}'
                + (f' <span class="small">({esc(h.name(owner))})</span>' if owner else "")
                + f'</td><td class=mono>{esc(r.get("url"))}</td></tr>')
        h.A("</tbody></table></div>")
    h.A("</div></details>")
    h.end()


def speed(h):
    c = h.c
    psi = c.get("psi") or {}
    h.section("speed", "4", "Page speed",
              "Google Lighthouse scores each page out of 100 (90+ Good, 50–89 Needs improvement, under 50 Poor), "
              "and measures how quickly it loads on a typical phone and on a desktop.")
    if not c.get("psi_by"):
        h.A('<p class="nc">Page-speed data was not collected for this run.</p>')
        return h.end()
    h.A("<h3>Scores out of 100</h3>")
    rows = [("Page speed — mobile", lambda b: scored(psi_score(c, b, "mobile"))),
            ("Page speed — desktop", lambda b: scored(psi_score(c, b, "desktop")))]
    for key, lab in CATS[1:]:
        rows.append((f"{lab} — mobile", (lambda k: lambda b: scored(psi_score(c, b, "mobile", k)))(key)))
    h.table("Score", rows)
    h.A('<p class="small">Accessibility, best-practices and SEO scores on desktop are within a few points of mobile; all scores are in each page\'s detail view.</p>')
    for dev in ("mobile", "desktop"):
        rows = []
        for key, plain, tech in LAB:
            def fn(b, key=key):
                v = ((psi_rec(c, b, dev) or {}).get("lab") or {}).get(key)
                if v is None:
                    return dim("—")
                word = RATING.get(rate(key, v), "") if key != "bytes" else ""
                return f'<span class="em">{esc(_metric(key, v))}</span>' + (f'<div class="small">{word}</div>' if word else "")
            rows.append((f"{plain}", fn))
        h.A(f"<h3>Loading measurements — {dev}</h3>")
        body = "".join(f'<tr><td class="lab">{esc(plain)}<div class="small" style="font-weight:400">{esc(tech)}</div></td>'
                       + "".join(h.td(b, fn(b)) for b in h.order) + "</tr>" for (plain, fn), (_, _, tech) in zip(rows, LAB))
        h.A('<div class="tw"><table class="cmp"><thead><tr>' + h.th("Measurement") + "</tr></thead><tbody>" + body + "</tbody></table></div>")
    when = (psi.get("fetched_at") or "")[:10]
    h.A(f'<p class="small">Measured with Google Lighthouse{f" on {esc(when)}" if when else ""}.</p>')
    h.end()


def onpage(h):
    c, P = h.c, h.pages
    h.section("onpage", "5", "SEO basics", "What search engines read first on each page, exactly as published.")

    def txt(v, n=False):
        v = (v or "").strip()
        if not v:
            return dim("None")
        return esc(v) + (f'<div class="small">{len(v)} characters</div>' if n else "")

    def canon(b):
        cu, u = (P[b].get("canonical") or "").rstrip("/"), (P[b].get("url") or "").rstrip("/")
        return dim("Not recorded") if not cu else ("Points to itself" if cu == u else f'<span class="mono">{esc(cu)}</span>')

    h.A("<h3>Title, description and main heading</h3>")
    h.table("Element", [
        ("Page title (title tag)", lambda b: txt(P[b].get("title"), True)),
        ("Search description (meta description)", lambda b: txt(P[b].get("meta_description"), True)),
        ("Main heading (H1)", lambda b: txt(P[b].get("h1")) if P[b].get("h1") else '<span class="em">No H1</span>'),
    ])
    h.A("<h3>Technical signals</h3>")
    h.table("Signal", [
        ("Robots instruction", lambda b: (f'<span class="em">{esc(P[b].get("robots_meta"))}</span>' if "noindex" in (P[b].get("robots_meta") or "").lower()
                                          else esc(P[b].get("robots_meta")) or "Not set (visible to search)")),
        ("Canonical tag", canon),
        ("Structured data", lambda b: ", ".join(esc(s) for s in P[b].get("schema_types") or []) or dim("None found")),
        ("Words · data tables", lambda b: f'{_int(P[b].get("word_count_total")):,} · {_int(P[b].get("tables_count"))}'),
        ("Images with a text description", lambda b: f'{_int(P[b].get("image_alt_count"))} of {_int(P[b].get("image_count"))} '
                                                     f'<span class="small">({pct(_int(P[b].get("image_alt_count")), _int(P[b].get("image_count")))})</span>'),
        ("Links to other pages of the site, in the article", lambda b: links_cell(P[b], c.get("quality") or {})),
        ("Links to other websites", lambda b: str(_int(P[b].get("external_link_count")))),
        ("Author", lambda b: esc(P[b].get("author")) or dim("Not named")),
        ("Reviewer", lambda b: esc(P[b].get("reviewer")) or dim("Not named")),
        ("Date shown on the page", lambda b: esc(" / ".join(x for x in (P[b].get("published_date"), P[b].get("modified_date")) if x)) or dim("None")),
    ])
    if c["topic"]:
        kc = {b: keyword_checks(P[b], c["topic"]) for b in h.order}
        yn = lambda v: "Yes" if v else dim("No")
        places = lambda b: sum(bool(kc[b][k]) for k in ("title", "meta", "h1", "url", "first100"))
        h.A(f'<h3>Where the phrase “{esc(c["topic"])}” appears</h3>')
        h.table("Place", [("Page title", lambda b: yn(kc[b]["title"])), ("Search description", lambda b: yn(kc[b]["meta"])),
                          ("Main heading (H1)", lambda b: yn(kc[b]["h1"])), ("Web address (URL)", lambda b: yn(kc[b]["url"])),
                          ("First 100 words", lambda b: yn(kc[b]["first100"])),
                          ("Sub-headings that contain it", lambda b: f'{kc[b]["subheads"]} of {kc[b]["subheads_total"]}'),
                          ("Times it appears in the text", lambda b: str(kc[b]["exact_body"])),
                          ("Key places that contain it (of 5)", lambda b: f"{places(b)} of 5", "tot")])
    h.end()


def headings(h):
    c, P = h.c, h.pages
    h.section("headings", "6", "Headings",
              "Headings organise a page. H1 is the main heading (one per page); H2 are section headings; H3 and H4 are sub-sections.")
    hc = c["hcounts"]
    h.table("Heading level", [
        ("H1 — main heading", lambda b: '<span class="em">Missing</span>' if hc[b][1] == 0 else (f"{hc[b][1]} (more than one)" if hc[b][1] > 1 else "1")),
        ("H2 — section headings", lambda b: str(hc[b][2])),
        ("H3 — sub-sections", lambda b: str(hc[b][3])),
        ("H4 — smaller sub-sections", lambda b: str(hc[b][4])),
    ])
    h.A("<h3>Main heading and section headings, side by side</h3><p class=small>Sub-section headings (H3, H4) are listed in each page's full view.</p><div class=grid5>")
    for b in h.order:
        out = h.pages[b].get("heading_outline") or []
        h1s = [x.get("text") for x in out if _int(x.get("level")) == 1]
        h2s = [x.get("text") for x in out if _int(x.get("level")) == 2]
        h.A(f'<div class="col{" us" if b == h.you else ""}"><h4>{h.label(b)}</h4>'
            + (f'<div class="h1">H1: {esc(" | ".join(h1s))}</div>' if h1s else '<div class="h1">H1: <span class="em">none</span></div>')
            + (f'<ol class="h2s">' + "".join(f"<li>{esc(t)}</li>" for t in h2s) + "</ol>" if h2s else '<p class="nc">No H2 headings</p>')
            + "</div>")
    h.A("</div>")
    tree = c.get("tree") or []
    shared = [r for r in tree if sum(r["present"].values()) >= 2]
    if shared:
        h.A(f'<details class="topic" style="margin-top:16px"><summary><b>Headings used by more than one page ({len(shared)} of {len(tree)})</b></summary><div style="padding:12px 16px">')
        body = "".join(f'<tr><td>H{r["level"]} · {esc(r["text"])}</td>' + "".join(h.td(b, "Yes" if r["present"][b] else dim("—")) for b in h.order) + "</tr>" for r in shared)
        h.A('<div class="tw"><table class="cmp"><thead><tr>' + h.th("Heading") + "</tr></thead><tbody>" + body + "</tbody></table></div></div></details>")
    h.end()


def topic_cov(h):
    c = h.c
    topics = c["topics"]
    h.section("topics", "7", "Topic coverage",
              f"{len(topics)} topics were found across the five pages. For each one: <b>Covered</b> means the page has a section on it, "
              "<b>Mentioned</b> means it is referred to briefly, and <b>—</b> means it is not on the page.")
    groups = [(k, [t for t in topics if (t.get("intent") or "medium") == k]) for k in ("high", "medium", "low")]
    rows = [(f"All topics ({len(topics)})", lambda b: f'<span class="em">{pct(covered(c, b), len(topics))}</span> <span class="small">({covered(c, b)})</span>', "tot")]
    for k, ts in groups:
        if ts:
            rows.append((f"{INTENT[k]} ({len(ts)})", (lambda ts: lambda b: f'{pct(covered(c, b, ts), len(ts))} <span class="small">({covered(c, b, ts)})</span>')(ts)))
    h.A("<h3>Share of topics covered</h3>")
    h.table("Topics", rows)
    for k, ts in groups:
        if not ts:
            continue
        ts = sorted(ts, key=lambda t: -sum(1 for b in h.order if _int(t["brands"][b]["info"].get("depth")) >= 2))
        h.A(f"<h3>{INTENT[k]} ({len(ts)})</h3>")
        body = []
        for t in ts:
            cells = []
            for b in h.order:
                d = _int(t["brands"][b]["info"].get("depth"))
                cells.append(h.td(b, '<span class="em">Covered</span>' if d >= 2 else ("Mentioned" if d == 1 else dim("—"))))
            n = sum(1 for b in h.order if _int(t["brands"][b]["info"].get("depth")) >= 2)
            body.append(f'<tr><td><a href="#t-{esc(t["id"])}">{esc(t["name"])}</a></td>' + "".join(cells) + f'<td class="c">{n} of {len(h.order)}</td></tr>')
        tot = "".join(h.td(b, f"{covered(c, b, ts)} ({pct(covered(c, b, ts), len(ts))})") for b in h.order)
        body.append(f'<tr class="tot"><td>Topics covered</td>{tot}<td></td></tr>')
        h.A('<div class="tw"><table class="cmp"><thead><tr>' + h.th("Topic") + '<th class="c xtra">Pages covering it</th></tr></thead><tbody>' + "".join(body) + "</tbody></table></div>")
    comps = [b for b in h.order if b != h.you]
    missing = [t for t in topics if _int(t["brands"][h.you]["info"].get("depth")) < 2
               and sum(1 for b in comps if _int(t["brands"][b]["info"].get("depth")) >= 2) >= 2]
    only_us = [t for t in topics if _int(t["brands"][h.you]["info"].get("depth")) >= 2
               and not any(_int(t["brands"][b]["info"].get("depth")) >= 2 for b in comps)]
    h.A('<h3>Differences at a glance</h3><div class="cols2">')
    h.A(f'<div class="card"><h4 style="margin-top:0">Covered by two or more competitors, not covered by {esc(h.name(h.you))} ({len(missing)})</h4><ul class="plain">'
        + "".join(f'<li><a href="#t-{esc(t["id"])}">{esc(t["name"])}</a> <span class="small">— {", ".join(esc(h.name(b)) for b in comps if _int(t["brands"][b]["info"].get("depth")) >= 2)}</span></li>' for t in missing)
        + "</ul></div>")
    h.A(f'<div class="card us"><h4 style="margin-top:0">Covered only by {esc(h.name(h.you))} ({len(only_us)})</h4><ul class="plain">'
        + "".join(f'<li><a href="#t-{esc(t["id"])}">{esc(t["name"])}</a></li>' for t in only_us) + "</ul></div>")
    h.A("</div>")
    h.end()


def content(h):
    c = h.c
    h.section("content", "8", "Content side by side",
              "For every topic, what each page wrote: where it appears, a short summary, and the page's own words. "
              "Use the filters to narrow the list or to compare our page with one competitor.")
    opts = "".join(f'<option value="{esc(b)}">{esc(h.name(b))}</option>' for b in h.order if b != h.you)
    h.A(f'<div class="tools"><span id="tfbtns"><button class="btn on" onclick="setTopic(this,\'all\')">All topics</button> '
        f'<button class="btn" onclick="setTopic(this,\'high\')">Key calculator topics</button> '
        f'<button class="btn" onclick="setTopic(this,\'notours\')">Not covered by {esc(h.name(h.you))}</button></span>'
        f'<span style="flex:1"></span><label for="pf">Compare {esc(h.name(h.you))} with</label> '
        f'<select id="pf" onchange="setPage(this)"><option value="all">All competitors</option>{opts}</select>'
        '<button class="btn" onclick="accAll(true)">Open all</button><button class="btn" onclick="accAll(false)">Close all</button></div><div id="ctopics">')
    order_i = {"high": 0, "medium": 1, "low": 2}
    for i, t in enumerate(sorted(c["topics"], key=lambda t: order_i.get(t.get("intent"), 1))):
        dep = {b: _int(t["brands"][b]["info"].get("depth")) for b in h.order}
        tags = [t.get("intent") or "medium"] + (["notours"] if dep[h.you] < 2 else [])
        who = []
        for lab, test in (("Covered by", lambda d: d >= 2), ("Mentioned by", lambda d: d == 1), ("Not on", lambda d: d == 0)):
            bs = [h.name(b) for b in h.order if test(dep[b])]
            if bs:
                who.append(f"{lab}: {', '.join(esc(x) for x in bs)}")
        h.A(f'<details class="topic" id="t-{esc(t["id"])}" data-tf="{" ".join(tags)}"{" open" if (h.p or i < 2) else ""}>'
            f'<summary><b>{esc(t["name"])}</b><span class="who-line">{" · ".join(who)}</span></summary>')
        for b in h.order:
            cell = t["brands"][b]
            info = cell["info"]
            d = dep[b]
            sec = cell.get("sec") if _quotable(cell.get("sec")) else None
            head = (f'<div class="row{" us" if b == h.you else ""}" data-b="{esc(b)}"><div class="who"><b>{esc(h.name(b))}</b>'
                    + ('<span class="ours">OUR PAGE</span>' if b == h.you else ""))
            if not cell["present"] and d == 0:
                h.A(head + '<span class="small">Not covered</span></div><div class="nc">This topic is not on the page.</div></div>')
                continue
            where = ""
            if sec and sec.get("heading"):
                tag = cell.get("tag") or ""
                where = (f"Section heading ({tag}): “{esc(sec.get('heading'))}”" if tag.startswith("H") else f"Within “{esc(sec.get('heading'))}”")
            extras = [x for x, k in (("includes a table", "has_table"), ("includes a worked example", "has_example")) if info.get(k)]
            meta = COVER.get(d, "Covered") + ("; " + ", ".join(extras) if extras else "")
            head += f'<span class="small">{esc(meta)}</span>' + (f'<span class="small">{where}</span>' if where else "") + "</div>"
            body = (f'<div class="cap">Summary</div><p class="sum">{esc(info.get("snippet"))}</p>') if info.get("snippet") else ""
            text = _sec_text(sec)
            if text:
                first, rest = text[:900], text[900:]
                if rest:
                    cut = first.rfind(" ")
                    first, rest = (first[:cut], first[cut:] + rest) if cut > 600 else (first, rest)
                body += f'<div class="cap">On the page</div><blockquote class="quote">{esc(first)}{"…" if rest else ""}</blockquote>'
                if rest:
                    body += f'<details class="more"><summary>Read the full section</summary><blockquote class="quote more">{esc(text)}</blockquote></details>'
            elif sec and sec.get("summary"):
                body += f'<blockquote class="quote">{esc(sec.get("summary"))}</blockquote>'
            h.A(head + f'<div>{body or "<span class=nc>Covered without a separate section.</span>"}</div></div>')
        h.A("</details>")
    h.A("</div>")
    h.end()


def faqs(h):
    c = h.c
    h.section("faqs", "9", "FAQs", "Frequently asked questions on each page. Questions asking the same thing in different words are grouped.")
    rows = c.get("faq_rows") or []
    gaps = (c.get("gaps") or {}).get("faq_gaps") or []
    h.table("FAQs", [("Questions answered on the page", lambda b: f'<span class="em">{len(h.pages[b].get("faqs") or [])}</span>'),
                     (f"Share of all distinct questions ({len(rows)})", lambda b: pct(sum(1 for r in rows if r["present"][b]), len(rows)))] if rows else
            [("Questions answered on the page", lambda b: str(len(h.pages[b].get("faqs") or [])))])
    if gaps:
        comps = [b for b in h.order if b != h.you]
        body = "".join(f'<tr><td>{esc(g.get("question"))}</td>' + "".join(h.td(b, "Yes" if b in (g.get("answered_by") or []) else dim("—")) for b in comps) + "</tr>" for g in gaps)
        h.A(f"<h3>Questions answered by competitors but not on {esc(h.name(h.you))}'s page ({len(gaps)})</h3>"
            '<div class="tw"><table class="cmp"><thead><tr><th style="width:52%">Question</th>' + "".join(f'<th class="c">{esc(h.name(b))}</th>' for b in comps)
            + "</tr></thead><tbody>" + body + "</tbody></table></div>")
    if rows:
        h.A(f'<details class="topic"><summary><b>All {len(rows)} questions across the five pages</b></summary><div style="padding:12px 16px">'
            '<div class="tools"><input class="q" placeholder="Search questions…" oninput="search(this,\'faqm\')"></div>')
        body = "".join(f'<tr><td>{esc(r["question"])}</td>' + "".join(h.td(b, "Yes" if r["present"][b] else dim("—")) for b in h.order) + "</tr>" for r in rows)
        h.A('<div class="tw" style="max-height:620px"><table class="cmp" id="faqm"><thead><tr>' + h.th("Question") + "</tr></thead><tbody>" + body + "</tbody></table></div></div></details>")
    h.end()


def claims(h):
    h.section("claims", "10", "Figures & claims", "Prices, ratios, discounts, plan features and riders, exactly as each page states them.")
    h.A('<div class="cols2">')
    for b in h.order:
        p = h.pages[b]
        nums, feats = p.get("numbers") or [], p.get("features_or_riders") or []
        h.A(f'<div class="card{" us" if b == h.you else ""}"><h4 style="margin-top:0">{h.label(b)}</h4>'
            + (f'<div class="cap">Figures stated ({len(nums)})</div><ul class="plain">' + "".join(f"<li>{esc(x)}</li>" for x in nums) + "</ul>" if nums else "")
            + (f'<div class="cap" style="margin-top:12px">Plans, features and riders ({len(feats)})</div><ul class="plain">' + "".join(f"<li>{esc(x)}</li>" for x in feats) + "</ul>" if feats else "")
            + "</div>")
    h.A("</div>")
    h.end()


def page_detail(h, b, idx):
    c, p = h.c, h.pages[b]
    hc = c["hcounts"][b]
    h.A(f'<section id="{h.pid(b)}"><h2><span class="n">P{idx}</span>{esc(h.name(b))}' + ('<span class="ours">OUR PAGE</span>' if b == h.you else "") + "</h2>")
    h.A(f'<p class="lede"><a class="mono" href="{esc(p.get("url"))}" target="_blank" rel="noopener">{esc(p.get("url"))}</a></p>')
    sc = lambda dev: " · ".join(f'{lab} {psi_score(c, b, dev, k) if psi_score(c, b, dev, k) is not None else "n/a"}' for k, lab in CATS)
    kv = [("Page title", esc(p.get("title")) or "—"), ("Search description", esc(p.get("meta_description")) or "—"),
          ("Main heading (H1)", esc(p.get("h1")) or '<span class="em">No H1</span>'),
          ("Headings", f"H1 {hc[1]} · H2 {hc[2]} · H3 {hc[3]} · H4 {hc[4]}"),
          ("Size", f'{_int(p.get("word_count_total")):,} words · {_int(p.get("tables_count"))} data tables · {len(p.get("faqs") or [])} FAQs'),
          ("Scores — mobile (of 100)", sc("mobile")), ("Scores — desktop (of 100)", sc("desktop")),
          ("Structured data", ", ".join(esc(s) for s in p.get("schema_types") or []) or "None found"),
          ("Robots instruction", esc(p.get("robots_meta")) or "Not set"),
          ("Author / reviewer", esc(" / ".join(x for x in (p.get("author"), p.get("reviewer")) if x)) or "Not named")]
    h.A('<div class="kv">' + "".join(f"<div>{esc(k)}</div><div>{v}</div>" for k, v in kv) + "</div>")
    outline = p.get("heading_outline") or []
    h.A(f'<details class="topic"{" open" if h.p else ""}><summary><b>Heading outline ({len(outline)} headings)</b></summary><div style="padding:12px 16px"><ul class="ol">'
        + "".join(f'<li class="l{_int(x.get("level"))}"><span class="lvl">H{_int(x.get("level"))}</span><span>{esc(x.get("text"))}</span></li>' for x in outline)
        + "</ul></div></details>")
    secs = [s for s in p.get("sections") or [] if _sec_text(s) or s.get("summary")]
    h.A(f'<details class="topic" open><summary><b>Page content, section by section ({len(secs)} sections)</b></summary><div style="padding:14px 18px">')
    for s in secs:
        lvl = _int(s.get("level"))
        text = _sec_text(s)
        h.A(f'<div class="sec"><h5><span class="lvl">{"H%d" % lvl if lvl else "Intro"}</span><span>{esc(s.get("heading") or "(introduction)")}</span></h5>'
            f'<p>{esc(text) if text else "<span class=nc>" + esc(s.get("summary")) + "</span>"}</p></div>')
    h.A("</div></details>")
    fq = p.get("faqs") or []
    if fq:
        h.A(f'<details class="topic"{" open" if h.p else ""}><summary><b>FAQs ({len(fq)})</b></summary><div style="padding:12px 16px">')
        cats = {}
        for f in fq:
            cats.setdefault(f.get("category") or "", []).append(f)
        for cat, items in cats.items():
            if cat:
                h.A(f"<h4>{esc(cat)} ({len(items)})</h4>")
            for f in items:
                h.A(f'<details class="faq"{" open" if h.p else ""}><summary>{esc(f.get("question"))}</summary><div>{esc(f.get("answer"))}</div></details>')
        h.A("</div></details>")
    ex = p.get("examples") or []
    if ex:
        h.A(f'<details class="topic"{" open" if h.p else ""}><summary><b>Worked examples and illustrations ({len(ex)})</b></summary><div style="padding:12px 16px">'
            '<div class="tw"><table><thead><tr><th>Context</th><th>Figures</th></tr></thead><tbody>'
            + "".join(f'<tr><td>{esc(e.get("context"))}</td><td>{esc(e.get("figures"))}</td></tr>' for e in ex) + "</tbody></table></div></div></details>")
    links = onpage_internal_links(p)
    ext = p.get("external_links") or []
    h.A(f'<details class="topic"{" open" if h.p else ""}><summary><b>Links ({len(links)} to the same site · {len(ext)} to other websites)</b></summary><div style="padding:12px 16px">'
        '<div class="tw" style="max-height:480px"><table><thead><tr><th>Link text</th><th>Goes to</th><th>Section</th></tr></thead><tbody>'
        + "".join(f'<tr><td>{esc(l.get("anchor") or "(no text)")}</td><td class="mono">{esc(l.get("href"))}</td><td>{esc(l.get("section"))}</td></tr>' for l in links + ext)
        + "</tbody></table></div></div></details>")
    imgs = p.get("images") or []
    h.A(f'<details class="topic"{" open" if h.p else ""}><summary><b>Images ({len(imgs)}; {sum(1 for i in imgs if i.get("alt"))} with a text description)</b></summary><div style="padding:12px 16px">'
        '<div class="tw" style="max-height:420px"><table><thead><tr><th>Text description</th><th>Image file</th></tr></thead><tbody>'
        + "".join(f'<tr><td>{esc(i.get("alt")) or dim("None")}</td><td class="mono">{esc(i.get("src"))}</td></tr>' for i in imgs)
        + "</tbody></table></div></div></details>")
    h.A("</section>")


# ----------------------------------------------------------------------------- entry
def render(ctx, print_mode=False):
    h = R(ctx, print_mode)
    title = f'{(ctx["topic"] or "Content").title()} — Competitive Content Comparison'
    h.A(f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{esc(title)}</title><style>{CSS}</style></head><body>')
    nav(h)
    h.A("<main>")
    header(h)
    for fn in (summary, pages_compared, visibility, speed, onpage, headings, topic_cov, content, faqs, claims):
        fn(h)
    for i, b in enumerate(h.order, 1):
        page_detail(h, b, i)
    h.A(f"</main><script>{JS}</script></body></html>")
    return "".join(h.out)
